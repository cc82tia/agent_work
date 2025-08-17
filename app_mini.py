# ================================================================
# ファイル名: app_mini.py
# 概要    : Alexa→Lambda→FastAPI のブリッジ。/intent でLLM側ロジックに振り分け、
#           OAuth(Web)の開始(/auth/start)とコールバック(/oauth2/callback)も担当。
# 使い方  : 1) Fly secrets で GOOGLE_CLIENT_ID/SECRET, OAUTH_REDIRECT_BASE を設定
#           2) ブラウザで https://<app>.fly.dev/auth/start を開きGoogle同意
#           3) /intent に note:/event: をPOSTすると Sheets/Calendar へ反映
# 前提    : 環境変数 BRIDGE_SECRET（Lambda→FastAPIの共有鍵）
#           NOTES_DIR=/data（Fly Volume）、NOTES_FILE=/data/notes.json
# 更新日  : 2025-08-17
# ================================================================

import os
import json
import logging
from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from intent_router import route_intent

# ログ設定（INFO以上を標準出力へ）
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = FastAPI()

# --- 共有シークレット：Lambda→FastAPI の簡易認証 ---
BRIDGE_SECRET = os.getenv("BRIDGE_SECRET", "")

# --- 永続化ファイルの保存先（Fly Volume /data を想定）---
NOTES_DIR = os.getenv("NOTES_DIR", "/data")
os.makedirs(NOTES_DIR, exist_ok=True)
NOTES_FILE = os.path.join(NOTES_DIR, "notes.json")

# ======================= OAuth(Web) 設定 ========================
# ここでは「1ユーザ（default）分」のトークンを /data/oauth/default.json に保存します。
# 来週以降は /auth/start?user=alice のように state=alice で複数ユーザ化できます。

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar",
]

OAUTH_MODE = os.getenv("GOOGLE_AUTH_MODE", "oauth")  # "oauth" を明示
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
REDIRECT_BASE = os.getenv("OAUTH_REDIRECT_BASE", "")  # 例: https://agent-work-bridge-dev.fly.dev
REDIRECT_URI = f"{REDIRECT_BASE}/oauth2/callback" if REDIRECT_BASE else ""

TOKENS_DIR = os.path.join(NOTES_DIR, "oauth")
os.makedirs(TOKENS_DIR, exist_ok=True)

def _token_path(user: str) -> str:
    """ユーザごとのトークン保存パス（default.json など）"""
    return os.path.join(TOKENS_DIR, f"{user}.json")

def _build_flow() -> Flow:
    """クライアントID/Secret とリダイレクトURIから Flow を組み立てる"""
    if not (CLIENT_ID and CLIENT_SECRET and REDIRECT_URI):
        raise RuntimeError("OAuth client settings missing (CLIENT_ID/SECRET or REDIRECT_URI)")
    client_config = {
        "web": {
            "client_id": CLIENT_ID,
            "project_id": "agent-bridge",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_secret": CLIENT_SECRET,
            "redirect_uris": [REDIRECT_URI],
        }
    }
    return Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=REDIRECT_URI)

@app.get("/auth/start")
def auth_start(user: str = "default"):
    """
    (1) OAuth 開始URL
    ブラウザで /auth/start にアクセス → Google同意画面へ遷移。
    user= でユーザ名を渡せば /data/oauth/<user>.json に保存可能。
    """
    flow = _build_flow()
    # state に user を入れて、コールバック側で取り出す
    auth_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent", state=user
    )
    return RedirectResponse(auth_url)

@app.get("/oauth2/callback")
def auth_callback(state: str, code: str):
    """
    (2) Google から戻ってくるコールバック
    ここでトークンを取得し、/data/oauth/<user>.json に保存します。
    """
    user = state or "default"
    flow = _build_flow()
    flow.fetch_token(code=code)            # ここでアクセストークン/リフレッシュトークン発行
    creds = flow.credentials

    # 保存先を作成して JSON を書き込み
    os.makedirs(TOKENS_DIR, exist_ok=True)
    with open(_token_path(user), "w", encoding="utf-8") as f:
        f.write(creds.to_json())

    return HTMLResponse(
        f"<h3>Google 連携 成功（ユーザ: {user}）</h3>"
        "<p>この画面は閉じてOK。Alexa / curl から note: / event: を投げて確認してください。</p>"
    )
# ===================== /OAuth(Web) 設定ここまで =====================

@app.get("/health")
def health():
    """死活監視用"""
    return {"status": "ok"}

@app.get("/notes")
def read_notes():
    """確認用：サーバ側に溜めた notes.json を返す"""
    try:
        if os.path.exists(NOTES_FILE):
            with open(NOTES_FILE, "r", encoding="utf-8") as f:
                return {"ok": True, "notes": json.load(f)}
        return {"ok": True, "notes": []}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.post("/intent")
async def intent_endpoint(request: Request, x_bridge_secret: str | None = Header(default=None)):
    """
    Alexa/Lambda → FastAPI の本線エンドポイント。
    共有シークレットを検証後、intent_router へ委譲します。
    """
    # 共有シークレット（早期リターン）
    if BRIDGE_SECRET and (not x_bridge_secret or x_bridge_secret != BRIDGE_SECRET):
        raise HTTPException(status_code=401, detail="unauthorized")

    payload = await request.json()

    # 今回は1ユーザ想定：OAuthで保存した default を使う
    payload["_oauth_user"] = "default"

    try:
        result = await route_intent(payload, NOTES_FILE)
        return JSONResponse({"ok": True, "result": result})
    except Exception as e:
        log.exception("intent error: %s", e)  # Fly logs で原因を追える
        return JSONResponse({"ok": False, "error": str(e)}, status_code=200)
