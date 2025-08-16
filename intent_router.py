# intent_router.py
import os
import re
from typing import Dict, Callable

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"

# ---- 将来差し替える“実処理”の入り口（今はスタブ） ----
def handle_echo(text: str) -> Dict:
    return {"echo": text, "handled_by": "echo"}

def handle_add_note(text: str) -> Dict:
    # TODO: tools/add_note_to_sheets.py を呼ぶ実装に差し替え
    return {"note": text, "handled_by": "add_note (stub)", "dry_run": DRY_RUN}

def handle_add_event(text: str) -> Dict:
    # TODO: tools/add_event.py を呼ぶ実装に差し替え
    return {"event": text, "handled_by": "add_event (stub)", "dry_run": DRY_RUN}

def handle_send_text(text: str) -> Dict:
    # TODO: tools/send_text.py を呼ぶ実装に差し替え
    return {"message": text, "handled_by": "send_text (stub)", "dry_run": DRY_RUN}

# ---- 簡単なルーティング規則（まずは分かりやすく正規表現一発）----
RULES: list[tuple[re.Pattern, Callable[[str], Dict]]] = [
    (re.compile(r"^note[:：]\s*(.+)", re.I), handle_add_note),
    (re.compile(r"^event[:：]\s*(.+)", re.I), handle_add_event),
    (re.compile(r"^send[:：]\s*(.+)", re.I), handle_send_text),
]

def route_intent(text: str) -> Dict:
    # ルールにマッチしたらそのハンドラへ
    for pat, handler in RULES:
        m = pat.match(text.strip())
        if m:
            return handler(m.group(1))
    # デフォルトは echo
    return handle_echo(text)
