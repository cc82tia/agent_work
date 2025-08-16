# tests/test_api_integration.py  
import os, time, pytest
from app_intent_mvp import create_calendar_event, append_sheets

# DRY_RUN=true のときは実APIテストをスキップ（安全運用）
skip_when_dry = pytest.mark.skipif(
    os.getenv("DRY_RUN", "true").lower() == "true",
    reason="DRY_RUN中は実APIテストをスキップ"
)

@skip_when_dry
def test_calendar_create_real(monkeypatch):
    # 念のため、このテストプロセス内では DRY_RUN=false を強制
    monkeypatch.setenv("DRY_RUN", "false")
    evt = create_calendar_event({
        "summary": "pytest-統合テスト0815",
        "start": "2025-08-20T10:00:00+09:00",
        "end":   "2025-08-20T10:30:00+09:00",
        "description": "from pytest"
    })
    assert "id" in evt and evt["id"]

@skip_when_dry
def test_sheets_append_real(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    updated = append_sheets([[time.strftime("%Y-%m-%d %H:%M:%S"), "memo", "pytest-統合テスト0815"]])
    assert updated["ok"] is True
