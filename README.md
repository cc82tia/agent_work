
（最初のクイックスタート、`app_min.py` → `app_mini.py` の誤字あるかも？）


````markdown
# agent_work

## Quick Start
```bash
# サーバ起動（自動リロード）
uvicorn app_mini:app --reload --port 8080

# 健康チェック
curl -s http://127.0.0.1:8080/health; echo

# サンプル呼び出し
curl -s -X POST http://127.0.0.1:8080/intent \
  -H "Content-Type: application/json" \
  -d '{"text":"hello"}'; echo
````

## Requirements

* Python 3.10+（WSL/Unix 系で動作確認）
* pip

## Setup

```bash
# 依存パッケージ
pip install -r requirements.txt

# 環境変数ファイル
cp .env.sample .env
# ※ 秘密情報は .env に記載（.env は git ignore 済み）
```

## Run

```bash
# ローカル起動
uvicorn app_mini:app --reload --host 0.0.0.0 --port 8080
```

## API

### GET /health

* 200 OK

```json
{"status": "ok"}
```

### POST /intent

* Request

```json
{"text": "hello"}
```

* Response（最小スタブ）

```json
{"ok": true, "result": {"echo": "hello", "handled_by": "minimal_stub"}}
```

## Tests (optional)

```bash
pytest -q
```

## Project Layout（抜粋）

```
.
├─ app_mini.py        # 最小FastAPI（/health, /intent）
├─ tools/             # 補助スクリプト
├─ tests/             # pytest
├─ requirements.txt
├─ .env.sample        # 環境変数のテンプレ
└─ .env               # 本番値（コミットしない）
```

## Troubleshooting

* **curl が `Not Found` を返す**
  → `uvicorn app_mini:app ...`（モジュール/アプリ名が `app_mini:app` になっているか確認）
* **ポートが使用中**
  → `lsof -i :8080` などでプロセスを停止 or `--port` を変更

```

---

必要最低限で“動かす→把握する→広げる”ができる内容になってます。  

```
<!-- 2025-08-21: 理由= 次任者が最初に見るべき運用手順をワンラインで案内 -->
> 運用中の Fly.io デプロイ状況と復旧手順は **doc/最新日付\_Flyio\_Deploy\_Runbook.md** を参照してください。  
> 例: `doc/2025-08-21_Flyio_Deploy_Runbook.md`
