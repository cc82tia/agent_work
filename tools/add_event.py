''' tools/add_event.py
LINE WORKS API でイベントを追加するための関数群
このスクリプトは、LINE WORKS のイベントを追加するための基本的なセットアップを行います。
1. 認証情報を取得し、トークンを保存
2. トークンを使ってイベントを追加
'''
# file: tools/add_event.py
from pathlib import Path
from dotenv import load_dotenv
import os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import datetime
import logging
# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# .envを読み込む
load_dotenv()
CLIENT_JSON = Path(os.getenv("GOOGLE_OAUTH_CLIENT_JSON", ".env.variables/google_oauth_client.json"))
TOKEN_PATH = Path(".env.variables/google_token.json")
SCOPES = ["https://www.googleapis.com/auth/calendar"]

def get_credentials():
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_JSON), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    return creds

def add_event(summary, start_dt, end_dt, calendar_id="primary"):
    #Copilot提案～2段構えエラー文・標準化・logger統一
    creds = get_credentials()
    service = build("calendar", "v3", credentials=creds)
    event = {
        "summary": summary,
        "start": {"dateTime": start_dt, "timeZone": "Asia/Tokyo"},
        "end": {"dateTime": end_dt, "timeZone": "Asia/Tokyo"},
    }
    try:
        result = service.events().insert(calendarId=calendar_id, body=event).execute()
        logger.info(f"✅ イベント登録成功: {result.get('htmlLink')}")
        logger.debug(f"[DEBUG] APIレスポンス: {result}")
        return {"ok": True, "link": result.get("htmlLink"), "result": result}
    except Exception as e:
        msg = str(e)
        #Copilot提案～エラー内容で人向け短文を標準化
        if "Unable to parse" in msg:
            message = f"カレンダーIDや日付形式が不正です: {msg}"
        elif "credentials" in msg or "認証" in msg:
            message = "認証情報が設定されていません。管理者にご連絡ください。"
        elif "権限" in msg or "permission" in msg:
            message = "権限が不足しています。Googleの共有設定を確認してください。"
        else:
            message = "イベント登録に失敗しました。入力内容や設定を見直してください。"
        logger.warning(f"❌ イベント登録失敗: {msg}")
        return {"ok": False, "message": message, "detail": msg}

def list_calendar_ids():
    """Googleアカウントに紐づくカレンダーID一覧を取得するTool関数"""
    #Copilot提案～logger統一
    creds = get_credentials()
    service = build("calendar", "v3", credentials=creds)
    calendars = service.calendarList().list().execute()
    for cal in calendars.get("items", []):
        logger.info(f"カレンダー名: {cal.get('summary')}, ID: {cal.get('id')}")
    return [cal.get("id") for cal in calendars.get("items", [])]

if __name__ == "__main__":
    # 例: 明日10:00〜10:30に「商談」
    tomorrow = (datetime.datetime.now() + datetime.timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    start = tomorrow.isoformat()
    end = (tomorrow + datetime.timedelta(minutes=30)).isoformat()
    result = add_event("商談", start, end, calendar_id="cawai1982c@gmail.com")
    if result["ok"]:
        logger.info(f"イベント登録成功: {result['link']}")
    else:
        logger.error(f"イベント登録失敗: {result['message']} (detail: {result['detail']})")