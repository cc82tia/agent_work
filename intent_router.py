# intent_router.py （置き換え・または該当部分を修正）
# 更新日: 2025-08-17
# 概要: Alexa→Lambda→FastAPI ブリッジの簡易ルータ。将来拡張のため余分なキーワードを受け流す。

import json
import os
from datetime import datetime

async def route_intent(payload: dict, notes_path: str, **kwargs):
    """
    Alexa/Lambda から渡ってくる payload を振り分ける簡易ルータ。
    - 将来の拡張で token_path / scopes などのキーワードが渡ってきても
      ここでは使わないので **kwargs で受け流す。
    """
    text = (
        payload.get("text")
        or payload.get("q")
        or payload.get("utterance")
        or ""
    ).strip()

    if text.lower().startswith("note:"):
        content = text.split(":", 1)[1].strip()
        return await add_note(content, notes_path)

    if text.lower().startswith("event:"):
        raw = text.split(":", 1)[1].strip()
        # ここは最小実装（/data/events.json に追記だけ）
        return await add_event(raw, notes_path)

    # それ以外は素のテキストを echo
    return {"handled_by": "echo", "echo": text}

async def add_note(content: str, notes_path: str):
    os.makedirs(os.path.dirname(notes_path), exist_ok=True)
    note = {
        "type": "note",
        "content": content,
        "ts": datetime.utcnow().isoformat() + "Z",
    }
    data = []
    try:
        if os.path.exists(notes_path):
            with open(notes_path, "r", encoding="utf-8") as f:
                raw = f.read().strip()
                if raw:
                    data = json.loads(raw)
        data.append(note)
        with open(notes_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return {"handled_by": "add_note", "saved_to": notes_path, "note": note}
    except Exception as e:
        raise e

async def add_event(raw: str, notes_path: str):
    # events.json は notes.json と同じ場所（/data）に作成
    events_path = os.path.join(os.path.dirname(notes_path), "events.json")
    os.makedirs(os.path.dirname(events_path), exist_ok=True)
    event = {
        "type": "event",
        "raw": raw,  # 解析は後で拡張
        "ts": datetime.utcnow().isoformat() + "Z",
    }
    data = []
    try:
        if os.path.exists(events_path):
            with open(events_path, "r", encoding="utf-8") as f:
                raw_ = f.read().strip()
                if raw_:
                    data = json.loads(raw_)
        data.append(event)
        with open(events_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return {"handled_by": "add_event", "saved_to": events_path, "event": event}
    except Exception as e:
        raise e
