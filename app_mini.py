# app_mini.py
# 概要: Alexa-Lambda ブリッジ用 FastAPI（最小）＋ Google OAuth(開始/状態/コールバック)
# 目的: note/event のローカル保存に加えて、OAuth 承認後は Sheets/Calendar へ実通信
# 更新日: 2025-08-17

from __future__ import annotations
from fastapi import FastAPI, Request, Header, HTTPException, Query
from fastapi.responses import JSONResponse, RedirectResponse, PlainTextResponse
import os, json, pathlib, base64, logging
from typing import Optional
from intent_router import route_intent
from fastapi import Query
from fastapi.responses import RedirectResponse
import urllib.parse
import os

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
OAUTH_REDIRECT_BASE = os.getenv("OAUTH_REDIRECT_BASE", "")
GOOGLE_SCOPES = os.getenv(
    "GOOGLE_SCOPES",
    "https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/calendar.events",
)

app = FastAPI()
@app.get("/oauth2/start")
def oauth2_start():
    """
    Google 同意画面へリダイレクトするだけの入口。
    今日は"同意画面が開ける"ことの確認まで。
    """
    if not (GOOGLE_CLIENT_ID and OAUTH_REDIRECT_BASE):
        # Secrets 未設定のときはエラーメッセージ
        return JSONResponse(
            {"ok": False, "error": "GOOGLE_CLIENT_ID / OAUTH_REDIRECT_BASE not set"},
            status_code=500,
        )

    auth_endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
    redirect_uri = f"{OAUTH_REDIRECT_BASE.rstrip('/')}/oauth2/callback"
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "access_type": "offline",
        "include_granted_scopes": "true",
        # スペース区切りで渡す
        "scope": GOOGLE_SCOPES,
        "state": "default",
        "prompt": "consent",
    }
    url = f"{auth_endpoint}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url)

@app.get("/oauth2/callback")
def oauth2_callback(state: str = Query(...), code: str = Query(...)):
    """
    今日は 200 を返すだけ。
    （本番はここで code を token に交換→ /data/oauth/token.json 保存）
    """
    return {"ok": True, "state": state, "code_received": bool(code)}
# ---- 共通設定 ---------------------------------------------------------
BRIDGE_SECRET = os.getenv("BRIDGE_SECRET", "")
NOTES_DIR = os.getenv("NOTES_DIR", "/data")
NOTES_FILE = os.path.join(NOTES_DIR, "notes.json")

# Google OAuth/API 関連（Secrets/Fly のものを使う）
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
OAUTH_REDIRECT_BASE = os.getenv("OAUTH_REDIRECT_BASE", "").rstrip("/")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")
SHEETS_ID = os.getenv("SHEETS_ID", "")

# トークンの保存先（Fly Volume 上）
OAUTH_DIR = os.path.join(NOTES_DIR, "oauth")
TOKEN_PATH = os.path.join(OAUTH_DIR, "token.json")

# 実通信をするか（0/falseでオフ）
DRY_RUN = str(os.getenv("DRY_RUN", "0")).lower() in ("1", "true", "yes")

# ログを見やすく
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bridge")

# ---- ヘルス -----------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}

# ---- OAuth: 状態確認（トークンがあるか？）-----------------------------
@app.get("/oauth2/status")
def oauth_status():
    has = os.path.exists(TOKEN_PATH)
    return {"has_token": has, "token_path": TOKEN_PATH, "dry_run": DRY_RUN}

# ---- OAuth: 開始エンドポイント ---------------------------------------
@app.get("/oauth2/start")
def oauth_start():
    """
    ここをブラウザで開く → Google の同意画面へ遷移
    成功後は /oauth2/callback に "code" 付きで戻してもらう
    """
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET or not OAUTH_REDIRECT_BASE:
        return PlainTextResponse("OAuth is not configured (missing client id/secret or redirect base).", status_code=500)

    # 要: pip install google-auth-oauthlib
    from google_auth_oauthlib.flow import Flow

    redirect_uri = f"{OAUTH_REDIRECT_BASE}/oauth2/callback"
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        },
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/calendar.events",
        ],
    )
    flow.redirect_uri = redirect_uri

    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    # state は今回は固定運用でも良いが、将来は CSRF 対策で検証を入れる
    return RedirectResponse(auth_url, status_code=302)

# ---- OAuth: コールバック（code を token に交換）----------------------
@app.get("/oauth2/callback")
def oauth_callback(
    state: Optional[str] = Query(None),
    code: Optional[str] = Query(None),
):
    if not code:
        return JSONResponse({"ok": False, "error": "missing code"}, status_code=400)

    try:
        from google_auth_oauthlib.flow import Flow
        import google.oauth2.credentials  # ensure installed

        redirect_uri = f"{OAUTH_REDIRECT_BASE}/oauth2/callback"
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri],
                }
            },
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/calendar.events",
            ],
        )
        flow.redirect_uri = redirect_uri

        # code → token 交換
        token = flow.fetch_token(code=code)

        # 保存先を必ず作成
        pathlib.Path(OAUTH_DIR).mkdir(parents=True, exist_ok=True)
        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            json.dump(token, f, ensure_ascii=False, indent=2)

        log.info("OAuth token saved: %s", TOKEN_PATH)
        return JSONResponse({"ok": True, "saved": TOKEN_PATH})
    except Exception as e:
        log.exception("OAuth callback failed")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

# ---- Alexa-Lambda ブリッジ --------------------------------------------
@app.post("/intent")
async def intent_endpoint(request: Request, x_bridge_secret: str | None = Header(default=None)):
    # 共有シークレット検証（早期リターン）
    if BRIDGE_SECRET:
        if not x_bridge_secret or x_bridge_secret != BRIDGE_SECRET:
            raise HTTPException(status_code=401, detail="unauthorized")

    payload = await request.json()

    try:
        # intent_router で note/event を振り分け
        # ここで TOKEN_PATH/SHEETS_ID/GOOGLE_CALENDAR_ID/DRY_RUN を渡せるようにしておく
        result = await route_intent(
            payload,
            NOTES_FILE,
            token_path=TOKEN_PATH,
            sheets_id=SHEETS_ID,
            calendar_id=GOOGLE_CALENDAR_ID,
            dry_run=DRY_RUN,
        )
        return JSONResponse({"ok": True, "result": result})
    except Exception as e:
        log.exception("intent error")
        # Lambda 側は5秒で待ち切れやすいので200で返しつつ内部エラー表示
        return JSONResponse({"ok": False, "error": str(e)}, status_code=200)
