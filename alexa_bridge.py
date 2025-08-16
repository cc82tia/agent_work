# alexa_bridge.py
from fastapi import FastAPI
from pydantic import BaseModel
from app_intent_mvp import classify_intent_rule, create_calendar_event, append_sheets

app = FastAPI()

class Utterance(BaseModel):
    text: str

@app.post("/alexa")
def handle(u: Utterance):
    res = classify_intent_rule(u.text)
    payload = res.suggested_payload
    if res.intent == "calendar":
        out = create_calendar_event(payload)
    else:
        out = append_sheets(payload["values"])
    return {"intent": res.intent, "payload": payload, "result": out}
