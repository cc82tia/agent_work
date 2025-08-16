# token_setup.py （プロジェクト直下）
from pathlib import Path
import os, json
from urllib.parse import urlencode
from requests_oauthlib import OAuth2Session
from dotenv import load_dotenv

load_dotenv(override=False)

CLIENT_JSON = os.getenv("GOOGLE_OAUTH_CLIENT_JSON", ".env.variables/google_oauth_client.json")
TOKEN_PATH  = os.getenv("GOOGLE_OAUTH_TOKEN_PATH",  ".env.variables/google_token.json")

# ★ここを3つに統一（順不同）
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/calendar.events"
]

REDIRECT_URI = "http://localhost"  # コンソールの Web クライアントと一致させる

cfg = json.loads(Path(CLIENT_JSON).read_text(encoding="utf-8"))
web = cfg.get("web") or {}
client_id     = web.get("client_id")
client_secret = web.get("client_secret")
auth_uri      = web.get("auth_uri",  "https://accounts.google.com/o/oauth2/auth")
token_uri     = web.get("token_uri", "https://oauth2.googleapis.com/token")
if not client_id or not client_secret:
    raise RuntimeError("client_secret.json が Web クライアント形式ではありません。『ウェブアプリ』で作り直してください。")

oauth = OAuth2Session(client_id=client_id, scope=SCOPES, redirect_uri=REDIRECT_URI)
params = {
    "response_type": "code",
    "client_id": client_id,
    "redirect_uri": REDIRECT_URI,
    "scope": " ".join(SCOPES),
    "state": "manual-console",
    "prompt": "consent",
    "access_type": "offline",
    "include_granted_scopes": "true",
}
print("== ブラウザでこのURLを開いて同意してください ==")
print(auth_uri + "?" + urlencode(params))
print("\n同意後、ブラウザは http://localhost/?code=... にリダイレクトされます（接続エラー表示でOK）。")
code = input("確認コード(code= の値) > ").strip()

# ★fetch_token では redirect_uri を渡さない（OAuth2Session が保持）
token = oauth.fetch_token(
    token_url=token_uri,
    code=code,
    client_id=client_id,
    client_secret=client_secret,
    include_client_id=True,
)

Path(TOKEN_PATH).parent.mkdir(parents=True, exist_ok=True)
Path(TOKEN_PATH).write_text(json.dumps(token, ensure_ascii=False, indent=2), encoding="utf-8")
print("✅ token saved:", TOKEN_PATH)
