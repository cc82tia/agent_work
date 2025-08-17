# ================================================================
# ファイル名: intent_router.py
# 概要    : /intent で受け取ったテキストを解釈し、note/event を処理。
#           note: → /data/notes.json 保存 + OAuthトークンがあれば Google Sheets に追記
#           event: → /data/events.json 保存 + OAuthトークンがあれば Google Calendar 作成
# 使い方  : app_mini から route_intent(...) を呼ばれる想定
#           環境変数 SHEETS_ID, G_CALENDAR_ID, GOOGLE_TIMEZONE を使用
# 更新日  : 2025-08-17
# ================================================================

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ---------- Google API（OAuthトークン利用） ----------
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar",
]

SHEETS_ID = os.getenv("SHEETS_ID", "")
CAL_ID = os.getenv("G_CALENDAR_ID", "primary")       # primaryでもOK（同意ユーザのメイン）
TZ = os.getenv("GOOGLE_TIMEZONE", "Asia/Tokyo")      # タイムゾーン

def _token_path(user: str) -> str:
    """/data/oauth/<user>.json"""
    tokens_dir = os.path.join(os.getenv("NOTES_DIR", "/data"), "oauth")
    return os.path.join(tokens_dir, f"{user}.json")

def _load_user_creds(user: str) -> Optional[Credentials]:
    """OAuthトークンを読み込み、Credentialsを返す（未連携なら None）"""
    path = _token_path(user)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return Credentials.from_authorized_user_info(data, SCOPES)
        except Exception as e:
            log.exception("load creds failed: %s", e)
    return None
# ---------------------------------------------------------------

def utcnow() -> str:
    """ISO8601 UTC（Z）"""
    return datetime.utcnow().isoformat() + "Z"

def _read_list(path: str):
    """JSON配列ファイルの安全読み込み（なければ空配列）"""
    try:
        if os.path.exists(path) and os.path.getsize(path) > 0:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        log.exception("read json failed: %s", path)
    return []

def _write_list(path: str, data):
    """JSON配列を保存（親ディレクトリを自動作成）"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

async def route_intent(payload: Dict, notes_path: str) -> Dict:
    """
    文章の先頭が "note:" ならメモ、"event:" なら予定、それ以外は echo で返す。
    OAuth連携済みなら Google Sheets/Calendar にも反映する。
    """
    text = (payload.get("text") or payload.get("q") or payload.get("utterance") or "").strip()
    user = payload.get("_oauth_user", "default")  # ひとまず default 固定、将来 user 切替可

    # --- メモ保存 ---
    if text.lower().startswith("note:"):
        content = text.split(":", 1)[1].strip()

        # ローカルJSONへ追記（提出要件の「可視化」）
        note = {"type": "note", "content": content, "ts": utcnow()}
        notes = _read_list(notes_path)
        notes.append(note)
        _write_list(notes_path, notes)

        result = {"handled_by": "add_note", "saved_to": notes_path, "note": note}

        # Google Sheets へ追記（OAuthトークン＋SHEETS_IDがある場合のみ）
        try:
            creds = _load_user_creds(user)
            if creds and SHEETS_ID:
                svc = build("sheets", "v4", credentials=creds)
                body = {"values": [[datetime.now().isoformat(timespec="seconds"), "memo", content]]}
                svc.spreadsheets().values().append(
                    spreadsheetId=SHEETS_ID,
                    range="A1",
                    valueInputOption="USER_ENTERED",
                    body=body,
                ).execute()
                result["sheets"] = "ok"
            else:
                result["sheets"] = "skipped"
        except Exception as e:
            log.exception("sheets append error: %s", e)
            result["sheets"] = f"error:{e}"

        return result

    # --- 予定登録 ---
    if text.lower().startswith("event:"):
        raw = text.split(":", 1)[1].strip()

        # ローカルJSONへ追記
        events_path = os.path.join(os.path.dirname(notes_path), "events.json")
        ev = {"type": "event", "raw": raw, "ts": utcnow()}
        events = _read_list(events_path)
        events.append(ev)
        _write_list(events_path, events)

        result = {"handled_by": "add_event", "saved_to": events_path, "event": ev}

        # 暫定ロジック：今+5分〜+65分で予定を切る
        start = datetime.now() + timedelta(minutes=5)
        end = start + timedelta(hours=1)

        try:
            creds = _load_user_creds(user)
            if creds:
                svc = build("calendar", "v3", credentials=creds)
                event = {
                    "summary": raw,
                    "start": {"dateTime": start.isoformat(), "timeZone": TZ},
                    "end": {"dateTime": end.isoformat(), "timeZone": TZ},
                }
                svc.events().insert(calendarId=CAL_ID, body=event).execute()
                result["calendar"] = "ok"
            else:
                result["calendar"] = "skipped"
        except Exception as e:
            log.exception("calendar create error: %s", e)
            result["calendar"] = f"error:{e}"

        return result

    # --- どれにも該当しない場合はエコー ---
    return {"handled_by": "echo", "echo": text}
