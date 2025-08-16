# tests/conftest.py
import sys
from pathlib import Path

# プロジェクトルートを sys.path に追加
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
