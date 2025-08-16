
from fastapi import FastAPI
from fastapi.responses import JSONResponse
# from app.schemas import CreateEventRequest, AppendSheetRequest, NotifyRequest
# from app.utils.messages import MessageBuilder as MB
# from app.services.google_calendar import create_event  #◇不存在関数-create_eventの機能が不足（外部モジュール依存）
# from app.services.google_sheets import append_rows    #◇不存在関数-append_rowsの機能が不足（外部モジュール依存）
# from app.services.lineworks import send_message       #◇不存在関数-send_messageの機能が不足（外部モジュール依存）
# from app.utils.env import DRY_RUN
import logging
from typing import List, Optional, Union
from pydantic import BaseModel
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 追加：/health 用の DRY_RUN フラグ（環境変数で切替）
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"

# 追加：未定義だった FastAPI のリクエストボディ用モデル
class CreateEventRequest(BaseModel):
    summary: str
    start: str            # ISO 例: "2025-08-16T10:00:00+09:00"
    end: str              # ISO 例: "2025-08-16T10:30:00+09:00"
    description: Optional[str] = ""

class AppendSheetRequest(BaseModel):
    # 1行でも複数行でも受けられるように緩めに
    values: Union[List[str], List[List[str]]]

class NotifyRequest(BaseModel):
    text: str
app = FastAPI(title="Google×LINE WORKS 効率化API", version="0.1.0")

@app.get("/health")
async def health():
    return {"status": "ok", "dry_run": DRY_RUN}


#Copilot提案～APIエンドポイントのエラーレスポンスを2段構え＆標準化
@app.post("/calendar/events")
async def post_calendar_event(req: CreateEventRequest):
    action = "Google Calendarへの予定登録"
    #Copilot提案～HTTP 429/5xxは0.5秒リトライ＋Calendar 403は再同意ガイド
    import asyncio
    for attempt in range(2):
        try:
            created = await create_event({
                "summary": req.summary,
                "description": req.description,
                "start": {"dateTime": req.start},
                "end": {"dateTime": req.end},
            })
            logger.info("Google Calendar登録成功: %s", created)
            return JSONResponse({"ok": True, "action": action, "created": created})
        except Exception as e:
            msg = str(e)
            # HTTPエラー判定例（本来はAPIレスポンスのstatus_codeで判定）
            if "403" in msg:
                logger.warning("Google Calendar 403: %s", e)
                return JSONResponse({
                    "ok": False, "action": action,
                    "message": "Google連携の有効期限が切れています。再度連携をやり直してください。",
                    "detail": msg
                }, status_code=403)
            if ("429" in msg or "5" in msg) and attempt == 0:
                logger.warning("Google Calendar 429/5xx: %s (リトライ)", e)
                await asyncio.sleep(0.5)
                continue
            if "credentials" in msg or "認証" in msg:
                message = "認証情報が設定されていません。管理者にご連絡ください。"
            elif "権限" in msg or "permission" in msg:
                message = "権限が不足しています。Googleの共有設定を確認してください。"
            elif "日付" in msg or "時刻" in msg or "parse" in msg:
                message = "日時の解釈に失敗しました。入力内容を見直してください。"
            else:
                message = "開始・終了の日時や必須項目を見直してください。"
            logger.warning("Google Calendar登録失敗: %s", e)
            return JSONResponse({
                "ok": False, "action": action,
                "message": message,
                "detail": msg
            }, status_code=400)


#Copilot提案～Google Sheets APIエラーも2段構え＆標準化
@app.post("/sheets/append")
async def post_sheets_append(req: AppendSheetRequest):
    action = "Google Sheetsへのメモ追記"

    #Copilot提案～Sheets 400 "Unable to parse range"はタブ名エラー文＋0.5秒リトライ
    import asyncio
    for attempt in range(2):
        try:
            result = await append_rows(req.values)
            logger.info("Google Sheetsメモ追加成功: %s", result)
            return JSONResponse({"ok": True, "action": action, "result": result})
        except Exception as e:
            msg = str(e)
            if "Unable to parse range" in msg:
                logger.warning("Sheetsタブ名不一致: %s", e)
                return JSONResponse({
                    "ok": False, "action": action,
                    "message": f"指定したシート名が見つかりません: {msg}",
                    "detail": msg
                }, status_code=400)
            if ("429" in msg or "5" in msg) and attempt == 0:
                logger.warning("Google Sheets 429/5xx: %s (リトライ)", e)
                await asyncio.sleep(0.5)
                continue
            if "credentials" in msg or "認証" in msg:
                message = "認証情報が設定されていません。管理者にご連絡ください。"
            elif "権限" in msg or "permission" in msg:
                message = "権限が不足しています。Googleの共有設定を確認してください。"
            else:
                message = "values は 2次元配列（行の配列）で指定してください。"
            logger.warning("Google Sheetsメモ追加失敗: %s", e)
            return JSONResponse({
                "ok": False, "action": action,
                "message": message,
                "detail": msg
            }, status_code=400)


#Copilot提案～LINE WORKS通知APIも2段構え＆標準化
@app.post("/notify")
async def post_notify(req: NotifyRequest):
    action = "LINE WORKS通知"
    try:
        result = await send_message(req.text)
        logger.info("LINE WORKS通知送信成功: %s", result)
        return JSONResponse({"ok": True, "action": action, "result": result})
    except ValueError as ve:
        logger.warning("LINE WORKS通知送信失敗: %s", ve)
        msg = str(ve)
        if "credentials" in msg or "認証" in msg:
            message = "認証情報が設定されていません。管理者にご連絡ください。"
        elif "権限" in msg or "permission" in msg:
            message = "権限が不足しています。LINE WORKSのBot権限や共有設定を確認してください。"
        elif "text" in msg or "空" in msg:
            message = "text を入力してください。"
        else:
            message = "通知送信に失敗しました。入力内容を見直してください。"
        return JSONResponse({
            "ok": False, "action": action,
            "message": message,
            "detail": msg
        }, status_code=400)
    except Exception as e:
        logger.exception("LINE WORKS通知送信で想定外エラー: %s", e)
        return JSONResponse({
            "ok": False, "action": action,
            "message": "しばらくしてから再度お試しください。",
            "detail": str(e)
        }, status_code=500)
    
    # --- ここから：ルール意図判定（テキスト版） --------------------------------------
from fastapi import Body
import re
from datetime import datetime, timedelta

def _parse_relative_date(text: str) -> datetime:
    """超簡易：明日/今日 のみ対応。なければ今日を返す。"""
    now = datetime.now()
    if "明日" in text or "あした" in text:
        base = now + timedelta(days=1)
    elif "今日" in text:
        base = now
    else:
        base = now
    # 日付だけ合わせ、時間は後で付ける
    return base.replace(hour=0, minute=0, second=0, microsecond=0)

def _extract_time(text: str) -> tuple[int,int]:
    """'10時30分' '14時' のような時刻を拾う。見つからなければ(10,0)。"""
    m = re.search(r'(\d{1,2})\s*時\s*(\d{1,2})?\s*分?', text)
    if m:
        h = int(m.group(1))
        mi = int(m.group(2)) if m.group(2) else 0
        return h, mi
    return 10, 0

def _extract_duration(text: str) -> int:
    """'30分' があれば分で返す。なければ30分。"""
    m = re.search(r'(\d{1,3})\s*分', text)
    if m:
        return int(m.group(1))
    return 30

def classify_intent(text: str) -> dict:
    """
    すごく単純なルール：
    - 'メモ' や '日報' を含む → memo
    - それ以外で '時' が入っていれば → calendar
    - どちらでもなければ unknown
    """
    t = text.strip()
    if not t:
        return {"intent": "unknown"}

    if "メモ" in t or "日報" in t:
        # Sheets 行の素案
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        body = t.replace("メモ：", "").replace("メモ:", "").replace("メモ", "").strip()
        return {
            "intent": "memo",
            "suggested_payload": {
                "values": [timestamp, "memo", body, ""]
            }
        }

   # app.py の classify_intent() の calendar 分岐だけ差し替え / 修正
    if "時" in t:
        base = _parse_relative_date(t)
        hh, mm = _extract_time(t)
        dur = _extract_duration(t)
        start = base.replace(hour=hh, minute=mm)
        end = start + timedelta(minutes=dur)

    # タイトルを簡易抽出（数字や助詞を除去しつつ末尾寄り）
    title = re.sub(r'\d+時|\d+分|明日|今日|あした|来週|再来週|に|から', '', t).strip() or "無題の予定"

    return {
        "intent": "calendar",
        "suggested_payload": {
            # /calendar/events 用に合わせる（summary/start/end）
            "summary": title,
            "start": start.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
            "end":   end.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
            "description": ""  # 任意
        }
    }


@app.post("/intent/route")
def intent_route(payload: dict = Body(..., example={"text": "明日10時に商談30分"})):
    """
    テキストを「予定 or メモ」に分類し、次に叩くAPIのペイロード案を返す。
    - 音声は後で置き換え予定。今日はテキストのみ。
    """
    text = str(payload.get("text", ""))
    result = classify_intent(text)
    return {"ok": True, "text": text, **result}
# --- ここまで：ルール意図判定 ------------------------------------------------------
# app.py の先頭付近（FastAPI, app = FastAPI() の直後あたり）に追加
from pydantic import BaseModel
from typing import List, Union

# ---- FastAPI のリクエストボディ用モデル（未定義で落ちていたやつ） ----
class CreateEventRequest(BaseModel):
    summary: str          # 予定タイトル（例: "商談"）
    start: str            # ISO日時（例: "2025-08-16T10:00:00+09:00"）
    end: str              # ISO日時（例: "2025-08-16T10:30:00+09:00"）

class AppendSheetsRequest(BaseModel):
    # Google Sheets に書く値
    # 使い方に合わせて柔らかく受ける（1行 or 複数行どちらも許可）
    values: Union[List[str], List[List[str]]]

# Lambda ブリッジ用（/execute で使う）
class BridgeIn(BaseModel):
    text: str

# --- ここから：Lambdaブリッジ用の最小 /execute 追加 -------------------------
from pydantic import BaseModel

class BridgeIn(BaseModel):
    text: str

@app.post("/execute")
def execute(inp: BridgeIn):
    """
    Lambda から {"text": "..."} が来る前提。
    既存の classify_intent() を使って memo/calendar を判定し、
    Lambda が期待する形で固定応答を返す。
    """
    t = inp.text
    res = classify_intent(t)  # 既存の関数を利用

    intent = res.get("intent")
    if intent == "memo":
        # Sheets 追記用の values をそのまま返す
        values = res["suggested_payload"]["values"]
        return {"ok": True, "tool": "sheets", "result": {"values": values}}

    if intent == "calendar":
        # Calendar 予定作成用の summary/start/end を返す
        payload = res["suggested_payload"]
        return {"ok": True, "tool": "calendar", "result": payload}

    # 判定できない場合
    return {"ok": False, "tool": "unknown", "message": "意図判定に失敗しました"}
# --- ここまで：/execute -----------------------------------------------------
