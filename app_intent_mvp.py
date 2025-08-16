# app_intent_mvp.py
from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse, RedirectResponse
import os, re, json
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional, Dict, Any, Tuple
from pydantic import BaseModel
from dotenv import load_dotenv
from loguru import logger
from pathlib import Path
import httpx, asyncio


# === 基本設定 ===
load_dotenv(override=False)
JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent

# app_intent_mvp.py 共通スコープを定義
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/spreadsheets",
]

# ※ Calendar でも Sheets でも、InstalledAppFlow / Credentials 生成時は必ず SCOPES を渡す
#   例）flow = InstalledAppFlow.from_client_secrets_file(str(client_json), SCOPES)
#       creds = flow.run_local_server(port=0)



# DRY_RUN=false で実実行
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"

import re
import datetime as dt

# 日本語→weekday番号（Mon=0 ... Sun=6）
_JP_WD = {"月":0,"火":1,"水":2,"木":3,"金":4,"土":5,"日":6}

def _next_week_same_weekday(base: dt.date, wd: int) -> dt.date:
    """「来週X曜」を日付にする。ベース日から次週の同じ曜日を返す。"""
    # 次の月曜（次週の頭）を求める
    days_to_next_monday = (7 - base.weekday()) % 7 or 7
    next_monday = base + dt.timedelta(days=days_to_next_monday)
    return next_monday + dt.timedelta(days=wd)  # 次週のwd

def _all_day_payload(date: dt.date, summary: str):
    # Google Calendarの終日は end が翌日（exclusive）
    return {
        "summary": summary,
        "start": {"date": date.isoformat()},
        "end":   {"date": (date + dt.timedelta(days=1)).isoformat()},
    }




# ---- Helper: パス/内容の両対応 ----
def _resolve_path(p: str) -> Path:
    pp = Path(p.strip())
    return pp if pp.is_absolute() else (BASE_DIR / pp).resolve()

def _materialize_if_content(value: str|None, fname: str) -> Path|None:
    if not value: return None
    v = value.strip()
    p = _resolve_path(v)
    if p.exists():
        return p
    if v.startswith("{"):  # JSON本文なら temp に吐く
        tmp = (BASE_DIR / f".tmp_{fname}").resolve()
        tmp.write_text(v, encoding="utf-8")
        return tmp
    return p

# 👇 共通の資格情報取得：Calendar/Sheets の両方が必ず同じ token を使う
def get_google_creds():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    client_json = _materialize_if_content(
        os.getenv("GOOGLE_OAUTH_CLIENT_JSON"), "google_oauth_client.json")
    token_file  = _resolve_path(os.getenv("GOOGLE_OAUTH_TOKEN_PATH", ".env.variables/google_token.json"))

    if not client_json or not client_json.exists():
        raise RuntimeError("GOOGLE_OAUTH_CLIENT_JSON が見つかりません")
    if not token_file.exists():
        raise RuntimeError("OAuth トークンがありません。先に `python token_setup.py` を実行して同意コードで発行してください。")

    import json
    raw = json.loads(token_file.read_text(encoding="utf-8"))
    cfg = json.loads(client_json.read_text(encoding="utf-8")).get("web", {})
    client_id = cfg.get("client_id"); client_secret = cfg.get("client_secret")
    token_uri = cfg.get("token_uri", "https://oauth2.googleapis.com/token")
    if not client_id or not client_secret:
        raise RuntimeError("client_secret.json が Webクライアント形式ではありません。『ウェブアプリ』で作り直してください。")

    # ←← ここがポイント：expires_at(秒) があれば ISO8601 にして expiry に入れる 0815GPT提案上手くいかないからコメントアウト
    # expiry_iso = None
    # try:
    #     ea = raw.get("expires_at")
    #     if isinstance(ea, (int, float)) and ea > 0:
    #         from datetime import datetime, timezone
    #         expiry_iso = datetime.fromtimestamp(ea, tz=timezone.utc).isoformat()
    # except Exception:
    #     pass

        # ←← ここがポイント：expires_at(秒) があれば RFC3339 "Z" 形式に
    expiry_iso = None
    try:
        ea = raw.get("expires_at")
        if isinstance(ea, (int, float)) and ea > 0:
            from datetime import datetime, timezone
            # 例: 2025-08-15T09:12:34Z  ← コロン付きオフセットを避ける
            expiry_iso = datetime.fromtimestamp(ea, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        pass

    scopes = raw.get("scopes") or raw.get("scope")
    if isinstance(scopes, str):
        scopes = scopes.split()

    authorized_user = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": raw.get("refresh_token"),
        "token": raw.get("access_token"),
        "scopes": scopes or SCOPES,
        "token_uri": token_uri,
        # ここを追加：有効期限が未来なら creds.valid になり refresh を走らせない
        "expiry": expiry_iso,
        "type": "authorized_user",
    }
    creds = Credentials.from_authorized_user_info(authorized_user, SCOPES)

    # ネット不通で refresh 失敗させないための安全弁：
    # expiry が設定され有効ならそのまま使い、期限切れ時だけ refresh を試みる
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            # ここでネット疎通が必要になる点に注意（長期運用はネット修復が必須）
            creds.refresh(Request())
            token_file.parent.mkdir(parents=True, exist_ok=True)
            token_file.write_text(creds.to_json(), encoding="utf-8")
        else:
            raise RuntimeError("OAuth トークンを更新できません。再同意が必要です。")

    _assert_token_has_scopes(creds)
    return creds


# === イントント判定 ===
class IntentResult(BaseModel):
    intent: Literal["calendar","memo","unknown"]
    suggested_payload: Optional[Dict[str, Any]] = None

def _parse_relative_date(text: str) -> datetime:
    now = datetime.now(JST)
    if any(k in text for k in ["明日","あした","tomorrow"]):
        return (now+timedelta(days=1)).replace(hour=0,minute=0,second=0,microsecond=0)
    if any(k in text for k in ["今日","きょう","today"]):
        return now.replace(hour=0,minute=0,second=0,microsecond=0)
    return now.replace(hour=0,minute=0,second=0,microsecond=0)

def _extract_time(text: str) -> Tuple[int,int]:
    m = re.search(r'(\d{1,2})\s*時\s*(\d{1,2})?\s*分?', text)
    if m: return int(m.group(1)), int(m.group(2) or 0)
    m2 = re.search(r'(\d{1,2}):(\d{2})', text)
    if m2: return int(m2.group(1)), int(m2.group(2))
    return 10,0

def _extract_duration(text: str) -> int:
    m = re.search(r'(\d{1,3})\s*分', text)
    return int(m.group(1)) if m else 30

def classify_intent_rule(text: str) -> IntentResult:
    t = (text or "").strip()
    if not t:
        return IntentResult(intent="unknown")

    # ① メモ → Sheets
    if any(k in t for k in ["メモ","日報","memo"]):
        ts = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
        body = re.sub(r'^(メモ[:：]?)', '', t).strip()
        return IntentResult(
            intent="memo",
            suggested_payload={"values": [[ts, "memo", body]]}
        )

    # ② 「来週(◯)曜 … 終日 … 有休/休暇」→ カレンダー終日
    m = re.search(r"(来週)?(?P<wd>[月火水木金土日])曜.*?(終日|全日).*(有休|休暇)", t)
    if m:
        # ヘルパーはファイル上部で宣言済み：
        # _JP_WD, _next_week_same_weekday, _all_day_payload
        wd = _JP_WD[m.group("wd")]
        today = datetime.now(JST).date()
        if m.group(1):  # 「来週」
            target = _next_week_same_weekday(today, wd)
        else:
            # 今週のその曜日（過ぎていれば翌週）
            days_ahead = (wd - today.weekday()) % 7
            target = today + timedelta(days=days_ahead)
        return IntentResult(
            intent="calendar",
            suggested_payload=_all_day_payload(target, "有休")
        )

    # ③ 時刻あり → カレンダー（デフォ30分）
    if "時" in t or re.search(r'\d{1,2}:\d{2}', t):
        base = _parse_relative_date(t)
        hh, mm = _extract_time(t)
        dur = _extract_duration(t)
        start = base.replace(hour=hh, minute=mm)
        end = start + timedelta(minutes=dur)
        title = re.sub(r'\d+時|\d+分|\d{1,2}:\d{2}|明日|今日|あした|に|から', '', t).strip() or "無題の予定"
        return IntentResult(
            intent="calendar",
            suggested_payload={
                "summary": title,
                "start": start.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                "end":   end.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                "description": ""
            }
        )

    return IntentResult(intent="unknown")


# === LLMフォールバック（任意） ===
def classify_intent_llm(text: str) -> Optional[IntentResult]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        sys = "日本語指示を calendar/memo/unknown に分類し、payloadをJSONで簡潔に返して。時間あいまいは+09:00で30分。"
        r = client.chat.completions.create(
            model=os.getenv("INTENT_LLM_MODEL","gpt-4o-mini"),
            messages=[{"role":"system","content":sys},{"role":"user","content":text}],
            temperature=0.1
        )
        data = json.loads(r.choices[0].message.content)
        return IntentResult(intent=data.get("intent","unknown"),
                            suggested_payload=data.get("suggested_payload"))
    except Exception as e:
        logger.warning(f"LLM fallback failed: {e}")
        return None

# === Google Calendar（Calendar 登録（OAuthのみ） ===
def create_calendar_event(payload: dict) -> dict:
    if DRY_RUN:
        return {"id":"dry_evt_123","link":"https://example.invalid","payload":payload,"dry_run":True}

    from googleapiclient.discovery import build
    creds = get_google_creds()  # ← 共通化！
    service = build("calendar", "v3", credentials=creds)

    calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
    event = {
        "summary": payload["summary"],
        "description": payload.get("description",""),
        "start": {"dateTime": payload["start"]},
        "end":   {"dateTime": payload["end"]},
    }
    created = service.events().insert(calendarId=calendar_id, body=event).execute()
    return {"id": created.get("id"), "link": created.get("htmlLink")}



# === Google Sheets（OAuth; 同じトークンを使用） ===

#Copilot提案～2段構えエラー文・標準化・logger統一
def append_sheets(values) -> dict:
    if DRY_RUN:
        return {"ok": True, "updated": len(values), "dry_run": True}

    from googleapiclient.discovery import build
    creds = get_google_creds()  # ← 共通化！
    spreadsheet_id = os.getenv("SHEETS_ID")
    rng = os.getenv("GOOGLE_SHEETS_RANGE", "Sheet1!A:C")
    if not spreadsheet_id:
        raise RuntimeError("SHEETS_ID が未設定です")

    service = build("sheets", "v4", credentials=creds)
    res = service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=rng,
        valueInputOption="RAW",
        body={"values": values}
    ).execute()
    return {"ok": True, "updated": res.get("updates", {}).get("updatedCells", 0)}

# === FastAPI ===
app = FastAPI(title="Intent Router MVP")

@app.get("/health")
def health():
    # Pydanticモデルは返してないのでシリアライズ問題なし
    return {"status":"ok","dry_run":DRY_RUN}

@app.post("/intent/route")
def route(payload: dict = Body(..., examples={"ex1":{"value":{"text":"明日12時に商談30分"}}})):
    text = str(payload.get("text",""))
    res = classify_intent_rule(text)
    if res.intent == "unknown":
        llm = classify_intent_llm(text)
        if llm: res = llm
    # ここで .model_dump() にして返す（JSONシリアライズ対策）
    return JSONResponse({"ok":True,"text":text, **res.model_dump()})

@app.get("/")
def root():
    return RedirectResponse("/docs")

@app.post("/execute")
def execute(payload: dict = Body(..., examples={"ex1":{"value":{"text":"明日10時に商談30分"}}})):
    try:
        text = str(payload.get("text",""))
        result = classify_intent_rule(text)
        if result.intent == "unknown":
            llm = classify_intent_llm(text)
            if llm: result = llm

        if result.intent == "calendar":
            created = create_calendar_event(result.suggested_payload)
            return JSONResponse({"ok": True, "tool": "calendar", "result": created})
        elif result.intent == "memo":
            updated = append_sheets(result.suggested_payload["values"])
            return JSONResponse({"ok": True, "tool": "sheets", "result": updated})
        else:
            return JSONResponse({"ok": False, "hint": "意図が不明です。"}, status_code=400)

    except Exception as e:
        logger.exception("execute failed")
        # 例外メッセージだけ返す（Pydanticオブジェクトは返さない）
        return JSONResponse(
            {"ok": False, "hint": "外部API呼び出しでエラー。ログを確認してください。", "detail": str(e)},
            status_code=500
        )

async def lw_notify(text: str) -> None:
    url = os.getenv("LINEWORKS_WEBHOOK_URL")
    if not url: return
    try:
        async with httpx.AsyncClient(timeout=3.0) as cli:
            await cli.post(url, json={"text": text})
    except Exception as e:
        logger.warning(f"LINE WORKS notify failed: {e}")


def _assert_token_has_scopes(creds):
    token_scopes = set(getattr(creds, "scopes", []) or [])
    need = set(SCOPES)
    if not need.issubset(token_scopes):
        raise RuntimeError(
            "トークンのスコープが不足しています。"
            f"\n期待: {sorted(need)}"
            f"\n実際: {sorted(token_scopes)}"
            "\n→ `rm .env.variables/google_token.json` → `python token_setup.py` で再同意してください。"
        )
