# app.py - 極薄ミニマム版
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="agent_work (minimal)")

class IntentIn(BaseModel):
    text: str

@app.get("/health")
def health():
    return {"status": "ok"}

# 将来: ここで tools/ や lw/ の関数を呼ぶ
def handle_intent(text: str) -> dict:
    # TODO: 後で本実装に差し替える
    return {"echo": text, "handled_by": "minimal_stub"}

@app.post("/intent")
def intent(body: IntentIn):
    result = handle_intent(body.text)
    return {"ok": True, "result": result}
