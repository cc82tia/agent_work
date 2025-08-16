# tests/test_api.py
import os
os.environ["DRY_RUN"] = "true"

from fastapi.testclient import TestClient
from app_intent_mvp import app

client = TestClient(app)

def test_health():
    r = client.get("/health").json()
    assert r["status"] == "ok"

def test_route_memo():
    r = client.post("/intent/route", json={"text":"メモ：A"}).json()
    assert r["ok"] and r["intent"] == "memo"

def test_execute_calendar_dry():
    r = client.post("/execute", json={"text":"明日10時に打合せ30分"}).json()
    assert r["ok"] and r["tool"] in ("calendar","sheets")
