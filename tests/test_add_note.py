"""test_add_note_to_sheets.py
Google Sheetsにメモを追加するためのテストスクリプト"""

import sys
import os
os.environ["DRY_RUN"] = "true"  # 外部APIを叩かない
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import logging 
from add_note_to_sheets import add_note_to_sheets
os.environ["DRY_RUN"] = "true"


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_add_note_basic():
    res = add_note_to_sheets("pytestメモ")
    assert isinstance(res, dict)
    assert "updated" in res

