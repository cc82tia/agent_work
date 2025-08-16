# run_once.py  ← 全置き換えOK
from __future__ import annotations
import os, json, datetime as dt
from typing import Any, List
from app_intent_mvp import create_calendar_event, append_sheets, get_google_creds
from googleapiclient.discovery import build

def jprint(tag: str, obj: Any):
    if os.getenv("LOG_PAYLOAD", "1") == "1":
        print(f"\n=== {tag} ===")
        try:
            print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))
        except TypeError:
            print(obj)

def iso_jst(ts: dt.datetime) -> str:
    # JST固定（+09:00）
    return ts.strftime("%Y-%m-%dT%H:%M:%S+09:00")

def calendar_service():
    return build("calendar", "v3", credentials=get_google_creds())

def sheets_service():
    return build("sheets", "v4", credentials=get_google_creds())

def verify_calendar(event_id: str, calendar_id: str = "primary") -> dict:
    svc = calendar_service()
    got = svc.events().get(calendarId=calendar_id, eventId=event_id).execute()
    jprint("CalendarVerification.get", got)
    return got

def tail_sheet(spreadsheet_id: str, rng: str = "Sheet1!A:Z", tail: int = 5) -> List[list]:
    svc = sheets_service()
    vr = svc.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=rng).execute()
    values = vr.get("values", [])
    tail_rows = values[-tail:] if values else []
    jprint("SheetsVerification.tail", tail_rows)
    return tail_rows

def main():
    # ---- 設定（環境変数）----
    calendar_id = os.getenv("GOOGLE_CALENDAR_ID", "primary")
    sheet_id    = os.getenv("SHEETS_ID")  # 必須（Sheets検証をするなら設定）
    sheet_range = os.getenv("GOOGLE_SHEETS_RANGE", "Sheet1!A:C")

    # ---- カレンダー用テストpayload（今から5分後〜30分）----
    start = dt.datetime.now() + dt.timedelta(minutes=5)
    end   = start + dt.timedelta(minutes=30)
    cal_payload = {
        "summary": "動作確認（run_once）",
        "description": "auto",
        "start": iso_jst(start),
        "end":   iso_jst(end),
    }

    # ---- 実行前ログ ----
    jprint("Calendar.request", {"calendarId": calendar_id, **cal_payload})
    if os.getenv("DRY_RUN", "true").lower() == "true":
        print("⚠ DRY_RUN=true → 実書き込みは行いません。`export DRY_RUN=false` で実行してください。")

    # ---- カレンダー書き込み ----
    cal_res = create_calendar_event(cal_payload)
    jprint("Calendar.response", cal_res)

    # ---- カレンダー読み戻し検証（dry-run時はスキップ）----
    if cal_res.get("dry_run"):
        print("ℹ DRY_RUNのため Calendar 検証スキップ")
    else:
        ev_id = cal_res.get("id")
        if not ev_id:
            print("❌ Calendar: idが返っていません。スコープ/権限/DRY_RUNを確認してください。")
        else:
            verify_calendar(ev_id, calendar_id)

    # ---- Sheets用テストpayload（A:C に1行）----
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sheet_values = [[ts, "memo", "動作確認（run_once）"]]
    jprint("Sheets.request", {"spreadsheetId": sheet_id, "range": sheet_range, "values": sheet_values})

    # ---- シート書き込み ----
    sh_res = append_sheets(sheet_values)
    jprint("Sheets.response", sh_res)

    # ---- シート読み戻し検証（dry-run時はスキップ）----
    if sh_res.get("dry_run"):
        print("ℹ DRY_RUNのため Sheets 検証スキップ")
    else:
        if sheet_id:
            tail_sheet(sheet_id, rng="Sheet1!A:Z", tail=5)
        else:
            print("⚠ SHEETS_ID 未設定のため検証スキップ（.envやexportで設定してください）")

if __name__ == "__main__":
    main()
