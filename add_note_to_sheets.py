# add_note_to_sheets.py
"""
Google Sheets にメモを追記する “ラッパー” ツール。
実際の Sheets 追記ロジックは app_intent_mvp.append_sheets() に一本化し、
ここでは値の整形と例外ハンドリングだけを行う。

使い方（例）:
  python add_note_to_sheets.py "テストメモ"

前提 (.env):
  GOOGLE_OAUTH_CLIENT_JSON=.env.variables/google_oauth_client.json
  GOOGLE_OAUTH_TOKEN_PATH=.env.variables/google_token.json
  SHEETS_ID=...（スプレッドシートID）
  GOOGLE_SHEETS_RANGE=Sheet名!A:C  # 例: Sheet1!A:C / シート1!A:C
"""

from __future__ import annotations
import sys
from datetime import datetime, timedelta, timezone
from loguru import logger

JST = timezone(timedelta(hours=9))

def add_note_to_sheets(note: str) -> dict:
    """
    メモ文字列をアプリ本体の append_sheets() に渡して追記する。
    返り値: {'updated': <int>} を期待。例外時は例外を投げる。
    """
    if not note or not note.strip():
        msg = "メモが空です。文字を入力してください。"
        logger.warning(msg)
        raise ValueError(msg)

    # ← ここで遅延import：テスト時の環境変数(DRY_RUN)が正しく効く
    from app_intent_mvp import append_sheets

    ts = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
    values = [[ts, "memo", note.strip()]]
    logger.info(f"Sheets append start: {values!r}")

    try:
        result = append_sheets(values)
        logger.info(f"Sheets append done: {result}")
        # app側が {'updated': n, ...} を返す前提
        return {"ok": True, "updated": result.get("updated", 0)}
    except Exception as e:
        msg = str(e)
        # 人向け短文（よくある原因をパターン分け）
        if "Unable to parse range" in msg:
            message = "指定したシート名/範囲が不正です。GOOGLE_SHEETS_RANGE を確認してください。"
        elif "not found" in msg and "credentials" in msg.lower():
            message = "認証ファイルが見つかりません。GOOGLE_OAUTH_CLIENT_JSON/GOOGLE_OAUTH_TOKEN_PATH を確認。"
        elif "permission" in msg.lower() or "権限" in msg:
            message = "権限が不足しています。シートの共有設定とOAuth同意のスコープを確認。"
        else:
            message = "メモ追加に失敗しました。入力や設定を見直してください。"
        logger.warning(f"Sheets append failed: {msg}")
        return {"ok": False, "message": message, "detail": msg}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('使い方: python add_note_to_sheets.py "メモ本文"')
        sys.exit(1)
    note = sys.argv[1]
    res = add_note_to_sheets(note)
    if res.get("ok"):
        print(f"✅ 追記成功: {res}")
        sys.exit(0)
    else:
        print(f"❌ 追記失敗: {res.get('message')}\n詳細: {res.get('detail')}")
        sys.exit(2)
