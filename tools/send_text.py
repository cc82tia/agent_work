# tools/send_text.py
"""
LINE WORKS Incoming Webhook へテキストを送る最小ユーティリティ。
.env の LINEWORKS_WEBHOOK_URL が無ければ何もしない（安全側）。
"""
import os, httpx
from loguru import logger

async def send_text_to_lineworks(text: str) -> bool:
    url = os.getenv("LINEWORKS_WEBHOOK_URL")
    if not url:
        logger.info("LINEWORKS_WEBHOOK_URL 未設定のため送信スキップ")
        return False
    try:
        async with httpx.AsyncClient(timeout=3.0) as cli:
            r = await cli.post(url, json={"text": text})
            if r.status_code // 100 == 2:
                return True
            logger.warning(f"LINE WORKS webhook status={r.status_code} body={r.text}")
            return False
    except Exception as e:
        logger.warning(f"LINE WORKS webhook error: {e}")
        return False
    
# async def issue_access_token(cfg: dict) -> str:
#     """
#     LINE WORKS のアクセストークンを取得する。
#     cfg は辞書型で、必要な情報（client_id, service_account, private_key_path, token_url, scope）を含む。
#     """
    
#     try:
#         token = await get_access_token(cfg)
#         if not token:
#             raise ValueError("アクセストークンが取得できませんでした。")
#         return token
#     except Exception as e:
#         logger.error(f"アクセストークン取得失敗: {e}")
#         raise
#     return token
