'''tests/test_add_event.py
LINE WORKS API でイベントを追加するための関数群
このスクリプトは、LINE WORKS のイベントを追加するための基本的なセットアップを行います。
1. 認証情報を取得し、トークンを保存
2. トークンを使ってイベントを追加
'''
# file: tests/test_add_event.py
# file: tests/test_add_event.py
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import tools.add_event
import traceback
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_add_event():
    summary = "テストイベント"
    start = "2025-08-13T15:00:00+09:00"
    end = "2025-08-13T15:30:00+09:00"
    try:
        tools.add_event.add_event(summary, start, end, calendar_id="cawai1982c@gmail.com")
        assert True
    except Exception as e:
        print("エラー:", e)
        traceback.print_exc()
        assert False

# これを追加
if __name__ == "__main__":
    test_add_event()