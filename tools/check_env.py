# tools/check_env.py
import json, os, sys
ok = True
for k in ["GOOGLE_OAUTH_CLIENT_JSON","GOOGLE_OAUTH_TOKEN_PATH","SHEETS_ID","GOOGLE_SHEETS_RANGE"]:
    v = os.getenv(k)
    if not v or (k.endswith("_JSON") and not os.path.exists(v)):
        print(f"NG {k}: {v}"); ok = False
p = ".env.variables/google_token.json"
try:
    scopes = (json.load(open(p)).get("scopes")) or json.load(open(p)).get("scope","").split()
    need = {"https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/spreadsheets"}
    print("scopes ok:", need.issubset(set(scopes)))
except Exception as e:
    print("scope read error:", e); ok = False
sys.exit(0 if ok else 1)

# .envファイルの不可視文字を表示する
with open('.env', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f, 1):
        print(f"{i:02d}: {repr(line)}")