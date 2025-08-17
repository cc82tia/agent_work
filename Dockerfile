# syntax=docker/dockerfile:1
FROM python:3.11-slim

# 必要最低限のツール
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl tini && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依存インストール（キャッシュ効かせる）
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# アプリ本体
COPY . /app

# 永続化ディレクトリ（Fly Volumeを /data にマウント）
RUN mkdir -p /data && chown -R 1000:1000 /data
ENV NOTES_DIR=/data
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# コンテナ内ヘルスチェック
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -fsS http://127.0.0.1:${PORT}/health || exit 1

# PID1対策
ENTRYPOINT ["/usr/bin/tini", "--"]

# FastAPI 起動（uvicorn / 0.0.0.0:8080）
CMD ["uvicorn", "app_mini:app", "--host", "0.0.0.0", "--port", "8080"]

# 必要ツールに build-essential を追加
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl tini build-essential && rm -rf /var/lib/apt/lists/*

# （その下の pip インストール行も強化すると安全）
RUN pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /app/requirements.txt

