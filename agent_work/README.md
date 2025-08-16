# agent_work

#### クイックスタート
uvicorn app_min.py:app --reload --port 8080
curl http://127.0.0.1:8080/health
curl -X POST http://127.0.0.1:8080/intent -H "Content-Type: application/json" -d '{"text":"hello"}'
