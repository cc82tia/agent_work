# app_mini.py  ← 既存 app_min.py をこの構成に寄せるだけでもOK
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os

from intent_router import route_intent  # ← 追加

app = FastAPI(title="agent_work (minimal)")

class IntentIn(BaseModel):
    text: str

class IntentOut(BaseModel):
    ok: bool
    result: dict

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/intent", response_model=IntentOut)
def intent(body: IntentIn):
    try:
        result = route_intent(body.text)
        return {"ok": True, "result": result}
    except Exception as e:
        # 将来、ここに型別エラー(認証・バリデーション等)を分けていく
        raise HTTPException(status_code=500, detail=str(e))
