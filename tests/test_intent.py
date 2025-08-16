# tests/test_intent.py
import re
from app_intent_mvp import classify_intent_rule

def test_memo_detection():
    r = classify_intent_rule("メモ:顧客Aに折返し")
    assert r.intent == "memo"
    assert r.suggested_payload["values"][0][1] == "memo"

def test_calendar_detection_time_jp():
    r = classify_intent_rule("明後日 13:15 打合せ 45分")
    assert r.intent == "calendar"
    p = r.suggested_payload
    assert re.match(r"\d{4}-\d{2}-\d{2}T13:15:00\+09:00", p["start"])
    assert re.match(r"\d{4}-\d{2}-\d{2}T14:00:00\+09:00", p["end"])

def test_calendar_detection_kanji():
    r = classify_intent_rule("明日10時に商談B30分")
    assert r.intent == "calendar"
