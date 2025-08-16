# file: quickstart_google.py
from pathlib import Path
from dotenv import load_dotenv
import os
from googleapiclient.discovery import build

# 既存の共通ローダーを再利用（Webクライアント+token_setup.pyで作ったトークンを使う）
from app_intent_mvp import get_google_creds

load_dotenv()

# .envからシートIDを読む（1行テキスト or 直接文字列でもOK）
SHEETS_ID = os.getenv("SHEETS_ID")
if not SHEETS_ID:
    # 予備: テキストファイルにIDがあるパターン
    sid_path = Path(os.getenv("SHEETS_ID_PATH", ".env.variables/sheets.id"))
    if sid_path.exists():
        SHEETS_ID = sid_path.read_text(encoding="utf-8").strip()

if not SHEETS_ID:
    raise RuntimeError("SHEETS_ID が見つかりません。.env か .env.variables/sheets.id を確認してください。")

def main():
    creds = get_google_creds()  # ← 既存の仕組みを流用

    # Sheets
    sheets = build("sheets", "v4", credentials=creds)
    val = sheets.spreadsheets().values().get(
        spreadsheetId=SHEETS_ID, range="A1:B2"
    ).execute()
    print("Sheets sample values:", val.get("values"))

    # Calendar
    cal = build("calendar", "v3", credentials=creds)
    lst = cal.calendarList().list(maxResults=5).execute()
    for item in lst.get("items", []):
        print("Calendar:", item.get("summary"))

if __name__ == "__main__":
    main()
