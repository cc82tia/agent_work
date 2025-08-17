# intent_router.py
# ------------------------------------------------------------
# 概要  : 音声→テキストの命令を見分けて処理するルータ
# 目的  : 最低限「note: …」「event: …」を /data に永続化する
# 仕様  : Sheets / Calendar はまず "queued" にしておき、別処理で実行
# 更新日: 2025-08-17
# ------------------------------------------------------------

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

# ---- 共通ユーティリティ -------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

def _append_json_array(file_path: Path, obj: dict) -> None:
    """
    JSON配列ファイルにobjを追記する。ファイルが無ければ配列で新規作成。
    """
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

# ---- 各ハンドラ ---------------------------------------------------------

def add_note(content: str, store: str = "/data/notes.json") -> dict:
    """
    メモを /data/notes.json に追記するだけの最小実装。
    Sheets 連携はここでは queued として返す。
    """
    note_obj = {
        "type": "note",
        "content": content.strip(),
        "ts": _utc_now_iso(),
    }
    _append_json_array(Path(store), note_obj)
    return {
        "handled_by": "add_note",
        "saved_to": store,
        "note": note_obj,
        "sheets": "queued",  # 後続ワーカーが拾う想定
    }

def add_event(raw: str, store: str = "/data/events.json") -> dict:
    """
    予定を /data/events.json に追記するだけの最小実装。
    実カレンダー登録はここでは queued として返す。
    """
    event_obj = {
        "type": "event",
        "raw": raw.strip(),
        "ts": _utc_now_iso(),
    }
    _append_json_array(Path(store), event_obj)
    return {
        "handled_by": "add_event",
        "saved_to": store,
        "event": event_obj,
        "calendar": "queued",  # 後続ワーカーが拾う想定
    }

def echo(text: str) -> dict:
    """
    どれにも当てはまらない場合のフォールバック。
    """
    return {"handled_by": "echo", "echo": text}

# ---- ルータ本体 ---------------------------------------------------------

def route_intent(text: str, *args, **kwargs) -> dict:
    """
    音声テキストを受け取り、適切なハンドラに振り分ける。
    可変引数/キーワードを受けることで、古い呼び出しシグネチャでも壊れないように後方互換にしている。
    """
    if not isinstance(text, str):
        return {"handled_by": "error", "error": "text is not str"}

    t = text.strip()
    low = t.lower()

    # "note: xxx" → メモ
    if low.startswith("note:"):
        content = t.split(":", 1)[1]
        return add_note(content)

    # "event: yyy" → 予定（詳細解析は後続のワーカーで）
    if low.startswith("event:"):
        raw = t.split(":", 1)[1]
        return add_event(raw)

    # それ以外は一旦エコー
    return echo(t)
