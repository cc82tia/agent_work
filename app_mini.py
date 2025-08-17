# app_mini.py
# -----------------------------------------------------------------------------
# 概要:
#   - Alexa→FastAPIブリッジの最小実装
#   - /intent : "note:" と "event:" を /data に永続化（Googleは後段で呼ぶ）
#   - /oauth2/start : Google OAuth 同意画面へリダイレクト
#   - /oauth2/callback : 認可コードをアクセストークンに交換し /data/oauth/token.json に保存
# 更新日: 2025-08-17
# 注意:
#   - Secrets 必須: GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, OAUTH_REDIRECT_BASE,
#                   GOOGLE_SCOPES(任意: スペース区切り), BRIDGE_SECRET
#   - SHEETS_ID, GOOGLE_CALENDAR_ID も必要に応じて Secrets に設定
# -----------------------------------------------------------------------------

from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from intent_router import route_intent
import os, json, pathlib, urllib.parse

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
from google_auth_oauthlib.flow import Flow

app = FastAPI()

BRIDGE_SECRET = os.getenv("BRIDGE_SECRET", "").strip()
NOTES_DIR = os.getenv("NOTES_DIR", "/data")
NOTES_FILE = os.path.join(NOTES_DIR, "notes.json")
EVENTS_FILE = os.path.join(NOTES_DIR, "events.json")

# OAuth 関連
OAUTH_DIR = os.path.join(NOTES_DIR, "oauth")
TOKEN_PATH = os.path.join(OAUTH_DIR, "token.json")   # ここに保存される
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
REDIRECT_BASE = os.getenv("OAUTH_REDIRECT_BASE", "").rstrip("/")
REDIRECT_URI = f"{REDIRECT_BASE}/oauth2/callback"
# スコープ（デフォルトは最小権限）
SCOPES = os.getenv("GOOGLE_SCOPES",
                   "https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/calendar.events"
                  ).split()

def _ensure_dir(path: str):
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)

def _client_config_dict() -> dict:
    # google_auth_oauthlib.flow.Flow で使う "client_config" 形式の dict を構築
    return {
        "web": {
            "client_id": CLIENT_ID,
            "project_id": "agent-work",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": CLIENT_SECRET,
            "redirect_uris": [REDIRECT_URI],
            "javascript_origins": [REDIRECT_BASE] if REDIRECT_BASE else [],
        }
    }

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/intent")
async def intent_endpoint(request: Request, x_bridge_secret: str | None = Header(default=None)):
    # 共有シークレット検証
    if BRIDGE_SECRET:
        if not x_bridge_secret or x_bridge_secret != BRIDGE_SECRET:
            raise HTTPException(status_code=401, detail="unauthorized")

    payload = await request.json()
    # route_intent は Google が無くても /data 保存は動く
    try:
        result = await route_intent(payload, NOTES_FILE, EVENTS_FILE)
        return JSONResponse({"ok": True, "result": result})
    except Exception as e:
        # 5秒以内に返すため詳細はログに留める
        return JSONResponse({"ok": False, "error": str(e)}, status_code=200)

# ---- OAuth: 同意開始 ---------------------------------------------------------
@app.get("/oauth2/start")
def oauth2_start():
    if not (CLIENT_ID and CLIENT_SECRET and REDIRECT_BASE):
        return JSONResponse({"ok": False, "error": "OAuth secrets not set"}, status_code=500)

    flow = Flow.from_client_config(
        client_config=_client_config_dict(),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",  # 常に同意画面を出す（スコープ変更時も確実に取れる）
    )
    return RedirectResponse(auth_url)

# ---- OAuth: コールバック（コード→トークン保存） ------------------------------
@app.get("/oauth2/callback")
def oauth2_callback(state: str | None = None, code: str | None = None):
    if not code:
        return JSONResponse({"ok": False, "error": "missing code"}, status_code=400)

    flow = Flow.from_client_config(
        client_config=_client_config_dict(),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )
    # 認可コードをトークンに交換
    flow.fetch_token(code=code)
    creds = flow.credentials

    _ensure_dir(TOKEN_PATH)
    # token.json を保存（必要最低限の項目）
    data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or SCOPES),
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
    }
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return JSONResponse({"ok": True, "token_saved": True, "path": TOKEN_PATH})
