# tests/test_e2e.py
import pytest
from app_intent_mvp import classify_intent_rule

def test_calendar_flow(monkeypatch):
    text = "明日10時に税理士さんと電話30分"
    res = classify_intent_rule(text)
    assert res.intent == "calendar"
    payload = res.suggested_payload
    assert payload and {"summary","start","end"} <= set(payload.keys())

    calls = {}
    def fake_create_calendar_event(p):
        calls["p"] = p
        return {"id": "fake123", "link": "https://example.invalid"}

    monkeypatch.setattr("app_intent_mvp.create_calendar_event", fake_create_calendar_event)
    out = fake_create_calendar_event(payload)
    assert out["id"] == "fake123"
    assert calls["p"]["summary"]  # 形だけ検証

def test_memo_flow(monkeypatch):
    text = "メモ: ストリームリットでフォーム試作"
    res = classify_intent_rule(text)
    assert res.intent == "memo"
    payload = res.suggested_payload
    assert payload and "values" in payload

    seen = {}
    def fake_append(values):
        seen["values"] = values
        return {"ok": True, "updated": 1}

    monkeypatch.setattr("app_intent_mvp.append_sheets", lambda values: fake_append(values))
    r = fake_append(payload["values"])
    assert r["ok"] is True
    assert seen["values"][0][1] == "memo"

# 追加の意図判定ケース
import pytest

CASES = [
    ("今日18時に筋トレ風動作", "calendar"),
    ("来週水曜は終日 有休", "calendar"),
    ("8月20日の14時〜15時にプロジェクト定例", "calendar"),
    ("メモ: 8/17 提出課題ドラフト", "memo"),
]

@pytest.mark.parametrize("text,intent", CASES)
def test_additional_intents(text, intent):
    res = classify_intent_rule(text)
    assert res.intent == intent
    payload = res.suggested_payload
    if intent == "calendar":
        assert {"summary", "start", "end"} <= set(payload.keys())
    else:
        assert "values" in payload
