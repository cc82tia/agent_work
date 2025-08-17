# intent_router.py
# ------------------------------------------------------------
# 概要  : "note:" は /data/notes.json に追記し、可能なら Google Sheets にも追記
#        "event:" は /data/events.json に追記し、可能なら Google Calendar にも登録
# 目的  : 提出用の最小RAG（永続化+外部API実行）。外部APIは失敗しても処理を継続
# 仕様  : 1) /data への保存は常に行う
#         2) GOOGLE_* Secrets と token.json が揃い、DRY_RUN=0 のときのみ実書き込み
#         3) それ以外は "queued"（スキップ）として返す
# 更新日: 2025-08-17
# ------------------------------------------------------------

from __future__ import annotations
import os, json
from typing import Any, Dict, Tuple
from pathlib import Path
from datetime import datetime, timezone

# Google クライアント
# ※ requirements.txt に以下が入っている想定
#   google-api-python-client
#   google-auth-oauthlib
#   google-auth-httplib2
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ==== 共通ユーティリティ =====================================================

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def _append_json_array(file_path: Path, obj: dict) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if file_path.exists():
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                data = []
        except Exception:
            data = []
    else:
        data = []
    data.append(obj)
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _get_google_creds() -> Tuple[Credentials|None, dict]:
    """
    Secrets/環境変数と /data/oauth/token.json から Credentials を組み立てる。
    そろっていなければ (None, {"reason":...}) を返す。
    """
    # 必要な Secrets
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    redirect_base = os.getenv("OAUTH_REDIRECT_BASE", "").strip()
    dry_run = os.getenv("DRY_RUN", "").strip()
    scopes_env = os.getenv(
        "GOOGLE_SCOPES",
        "https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/calendar.events"
    )
    scopes = scopes_env.split()

    # token の場所
    token_path = Path(os.getenv("TOKEN_PATH", "/data/oauth/token.json"))

    # ガード
    if not client_id or not client_secret or not redirect_base:
        return None, {"reason": "missing_google_secrets"}
    if not token_path.exists():
        return None, {"reason": "missing_token"}
    if dry_run in ("", "false", "0", "False"):
        dry = False
    else:
        dry = True  # true/1 のときは実通信オフ扱い

    try:
        data = json.loads(token_path.read_text(encoding="utf-8"))
        # token.json に揃っているものを優先
        token = data.get("token")
        refresh_token = data.get("refresh_token")
        token_uri = data.get("token_uri") or "https://oauth2.googleapis.com/token"
        cid = data.get("client_id") or client_id
        csec = data.get("client_secret") or client_secret
        saved_scopes = data.get("scopes") or scopes

        creds = Credentials(
            token=token,
            refresh_token=refresh_token,
            token_uri=token_uri,
            client_id=cid,
            client_secret=csec,
            scopes=saved_scopes,
        )
        return creds, {"dry_run": dry, "scopes": saved_scopes}
    except Exception as e:
        return None, {"reason": f"invalid_token_json: {e}"}

# ==== Google 実処理（安全に失敗させる） ========================================

def _try_append_to_sheets(creds: Credentials, content: str) -> Tuple[str, Any]:
    """
    Sheets に 1 行追記。例外は握りつぶして "error: ..." を返す。
    """
    try:
        sheets_id = os.getenv("SHEETS_ID", "").strip()
        range_name = os.getenv("GOOGLE_SHEETS_RANGE", "Sheet1!A:C").strip()
        if not sheets_id:
            return "skipped", "missing SHEETS_ID"
        service = build("sheets", "v4", credentials=creds)
        body = {"values": [[datetime.now().isoformat(timespec="seconds"), "note", content]]}
        service.spreadsheets().values().append(
            spreadsheetId=sheets_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            body=body
        ).execute()
        return "done", {"range": range_name}
    except Exception as e:
        return "error", str(e)

def _try_insert_calendar_event(creds: Credentials, raw: str) -> Tuple[str, Any]:
    """
    Calendar に簡易イベント登録。ここでは raw をタイトルにし、開始は「今から+1h」。
    """
    try:
        cal_id = os.getenv("GOOGLE_CALENDAR_ID", os.getenv("G_CALENDAR_ID", "primary")).strip() or "primary"
        service = build("calendar", "v3", credentials=creds)
        now = datetime.now(timezone.utc)
        start = now.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        end = (now.replace(microsecond=0) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        event = {
            "summary": raw,
            "start": {"dateTime": start, "timeZone": "UTC"},
            "end": {"dateTime": end, "timeZone": "UTC"},
        }
        created = service.events().insert(calendarId=cal_id, body=event).execute()
        return "done", {"id": created.get("id")}
    except Exception as e:
        return "error", str(e)

# ==== パブリックAPI ============================================================

async def route_intent(payload: Dict[str, Any], notes_store: str = "/data/notes.json", events_store: str = "/data/events.json") -> dict:
    """
    app_mini.py から await される想定。内部では同期I/Oなので await しない。
    戻り値は常に dict。
    """
    # 1) ユーザーの文字列を拾う
    text = (payload.get("text") or payload.get("q") or payload.get("utterance") or "").strip()

    # 2) Google 実行可能かを確認（しなくても /data は保存する）
    creds, meta = _get_google_creds()
    can_call_google = isinstance(creds, Credentials) and not meta.get("dry_run", True)

    # 3) note:
    if text.lower().startswith("note:"):
        content = text.split(":", 1)[1].strip()
        note_obj = {"type": "note", "content": content, "ts": _utc_now_iso()}
        _append_json_array(Path(notes_store), note_obj)

        sheets_status, sheets_info = ("queued", None)
        if can_call_google:
            sheets_status, sheets_info = _try_append_to_sheets(creds, content)

        return {
            "handled_by": "add_note",
            "saved_to": notes_store,
            "note": note_obj,
            "sheets": sheets_status,
            "sheets_info": sheets_info,
        }

    # 4) event:
    if text.lower().startswith("event:"):
        raw = text.split(":", 1)[1].strip()
        event_obj = {"type": "event", "raw": raw, "ts": _utc_now_iso()}
        _append_json_array(Path(events_store), event_obj)

        cal_status, cal_info = ("queued", None)
        if can_call_google:
            from datetime import timedelta  # ローカル import（上の try_insert 内でも可）
            cal_status, cal_info = _try_insert_calendar_event(creds, raw)

        return {
            "handled_by": "add_event",
            "saved_to": events_store,
            "event": event_obj,
            "calendar": cal_status,
            "calendar_info": cal_info,
        }

    # 5) fallback
    return {"handled_by": "echo", "echo": text}
