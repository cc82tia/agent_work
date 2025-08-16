'''tests/test_lineworks.py_(tools.send_text)削除しちゃったから関数利用できない'''

# file: tests/test_lineworks.py
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from tools.send_text import  send_text_to_lineworks, issue_access_token
from dotenv import load_dotenv
import logging  
# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

cfg = {
    "client_id": os.getenv("LW_CLIENT_ID"),
    "service_account": os.getenv("LW_SERVICE_ACCOUNT"),
    "private_key_path": os.path.abspath(os.getenv("LW_PRIVATE_KEY_PATH")),
    "token_url": "https://auth.worksmobile.com/oauth2/v2.0/token",
    "scope": "bot bot.message bot.read"
}

def test_get_access_token():
    logger.info("アクセストークン取得テスト開始")
    try:
        token = issue_access_token(cfg)
        assert isinstance(token, str) and len(token) > 0
        logger.info("アクセストークン取得成功: %s", token[:10] + "..." if token else "None")
    except AssertionError:
        logger.warning("アクセストークン取得失敗: 文字列でない、または空")
        raise
    except Exception as e:
        logger.exception("アクセストークン取得で想定外エラー: %s", e)
        raise

def test_send_text():
    logger.info("LINE WORKSメッセージ送信テスト開始")
    try:
        token = issue_access_token(cfg)
        send_text_to_lineworks(token, os.getenv("LW_ROOM_ID"), "テストメッセージ")
        logger.info("LINE WORKSメッセージ送信成功")
    except Exception as e:
        logger.exception("LINE WORKSメッセージ送信で想定外エラー: %s", e)
        raise
