# intent_router.py  の add_note / add_event 内の末尾を以下に置き換え

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import os, json, datetime as dt

TOKEN_PATH = "/data/oauth/token.json"
TIMEZONE   = os.getenv("GOOGLE_TIMEZONE", "Asia/Tokyo")
SHEETS_ID  = os.getenv("SHEETS_ID")
CAL_ID     = os.getenv("G_CALENDAR_ID") or os.getenv("GOOGLE_CALENDAR_ID") or "primary"

def _load_creds() -> Credentials:
    with open(TOKEN_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Credentials(
        token=data["token"],
        refresh_token=data.get("refresh_token"),
        token_uri=data["token_uri"],
        client_id=data["client_id"],
        client_secret=data["client_secret"],
        scopes=data["scopes"],
    )

def _append_to_sheets(text: str) -> str:
    creds = _load_creds()
    svc = build("sheets", "v4", credentials=creds)
    values = [[dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "memo", text]]
    body = {"values": values}
    svc.spreadsheets().values().append(
        spreadsheetId=SHEETS_ID,
        range=os.getenv("GOOGLE_SHEETS_RANGE", "Sheet1!A:C"),
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body=body
    ).execute()
    return "ok"

def _insert_event(raw: str) -> str:
    # ざっくり "8/20 14:00 タイトル" の形式を想定した簡易パース（必要に応じて強化）
    try:
        import re
        m = re.search(r"(\d{1,2}/\d{1,2})\s+(\d{1,2}:\d{2})\s+(.+)", raw)
        if not m:  # 失敗時は丸ごとタイトルで今から1時間枠
            start = dt.datetime.now() + dt.timedelta(hours=1)
            end   = start + dt.timedelta(hours=1)
            summary = raw
        else:
            # 今年の日時にする
            month, day = map(int, m.group(1).split("/"))
            hour, minute = map(int, m.group(2).split(":"))
            now = dt.datetime.now()
            start = dt.datetime(now.year, month, day, hour, minute)
            end   = start + dt.timedelta(hours=1)
            summary = m.group(3)

        creds = _load_creds()
        svc = build("calendar", "v3", credentials=creds)
        event = {
            "summary": summary,
            "start": {"dateTime": start.isoformat(), "timeZone": TIMEZONE},
            "end":   {"dateTime": end.isoformat(),   "timeZone": TIMEZONE},
        }
        svc.events().insert(calendarId=CAL_ID, body=event).execute()
        return "ok"
    except Exception as e:
        return f"error:{e}"

# --- add_note の最後をこうする ---
# result = {"handled_by":"add_note", ... , "sheets":"queued"} を
result = {
    "handled_by":"add_note",
    "saved_to":"/data/notes.json",
    "note": note_obj,
    "sheets": _append_to_sheets(note_obj["content"])
}

# --- add_event の最後をこうする ---
result = {
    "handled_by":"add_event",
    "saved_to":"/data/events.json",
    "event": ev_obj,
    "calendar": _insert_event(ev_obj["raw"])
}
