# intent_router.py
# ------------------------------------------------------------
# 概要  : /intent に来た payload を判定し、note/event を /data に保存する最小ルータ
# 互換性: app_mini.py から await route_intent(payload, ...) で呼ばれてもOK
# 注意  : Google 連携は "queued" を返すだけ（まずは土台を安定）
# 更新日: 2025-08-17
# ------------------------------------------------------------
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def _append_json_array(file_path: Path, obj: dict) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if file_path.exists():
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                data = []
        except Exception:
            data = []
    else:
        data = []
    data.append(obj)
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _add_note(content: str, store: str = "/data/notes.json") -> dict:
    note_obj = {"type": "note", "content": content.strip(), "ts": _utc_now_iso()}
    _append_json_array(Path(store), note_obj)
    return {
        "handled_by": "add_note",
        "saved_to": store,
        "note": note_obj,
        "sheets": "queued",
    }

def _add_event(raw: str, store: str = "/data/events.json") -> dict:
    event_obj = {"type": "event", "raw": raw.strip(), "ts": _utc_now_iso()}
    _append_json_array(Path(store), event_obj)
    return {
        "handled_by": "add_event",
        "saved_to": store,
        "event": event_obj,
        "calendar": "queued",
    }

def _echo(text: str) -> dict:
    return {"handled_by": "echo", "echo": text}

# ★ここが重要：async def になっていること！
async def route_intent(payload: Dict[str, Any], *args, **kwargs) -> dict:
    """
    payload 例: {"text":"note: ..."} / {"q":"event: ..."} / {"utterance": "..."}
    """
    text = (
        (payload or {}).get("text")
        or (payload or {}).get("q")
        or (payload or {}).get("utterance")
        or ""
    )
    if not isinstance(text, str):
        return {"handled_by": "error", "error": "text is not str"}

    t = text.strip()
    low = t.lower()

    if low.startswith("note:"):
        return _add_note(t.split(":", 1)[1])

    if low.startswith("event:"):
        return _add_event(t.split(":", 1)[1])

    return _echo(t)
