# syntax=docker/dockerfile:1
#
# Backend image dùng chung cho API + worker.
#
#   target api            -> FastAPI (không LibreOffice, image nhẹ)
#   target content-worker -> thêm LibreOffice + fonts để chuyển PPTX/PPT/ODP -> PDF
#
# Worker `app.worker` (analysis) dùng lại target api; chỉ content-worker cần
# LibreOffice. Cả hai chạy bằng user không phải root.

# ---- base: Python + runtime deps dùng chung ----
FROM python:3.12.8-slim AS base

# Tránh buffer log để thấy log realtime trong `docker logs`.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Cài dependencies trước (tận dụng layer cache). Cache wheel của pip bằng
# BuildKit cache mount: wheel nằm ngoài image và tái sử dụng khi requirements
# đổi. Base đặt PIP_NO_CACHE_DIR=1 nên phải `env -u` cho riêng lệnh pip.
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    env -u PIP_NO_CACHE_DIR pip install -r requirements.txt

# Tạo user không phải root để chạy.
RUN useradd --create-home --shell /bin/bash appuser

# ---- api: FastAPI, không LibreOffice ----
FROM base AS api

COPY --chown=appuser:appuser app ./app
RUN mkdir -p /app/media && chown -R appuser:appuser /app

USER appuser

EXPOSE 8001

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8001/health').status==200 else 1)"

# --proxy-headers: dùng X-Forwarded-For/-Proto từ proxy tin cậy để suy ra IP
#   client thật (request.client.host) + scheme.
# FORWARDED_ALLOW_IPS: CHỈ tin header từ nginx trong mạng docker nội bộ.
#   KHÔNG dùng "*": backend có publish port 127.0.0.1:8001 để debug, nên nếu
#   tin mọi peer thì request local có thể giả mạo X-Forwarded-For và bypass
#   rate limit. Dải mặc định bao trùm network Docker bridge.
ENV FORWARDED_ALLOW_IPS=172.16.0.0/12,10.0.0.0/8,192.168.0.0/16
# Số process API. Mỗi process có pool DB riêng; giữ DB_POOL_MAX nhỏ (4-10)
# để tổng connection không vượt max_connections của Postgres.
ENV WEB_CONCURRENCY=2
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers ${WEB_CONCURRENCY} --proxy-headers"]

# ---- test: API + dev deps (không dùng cho production) ----
FROM api AS test

USER root
COPY requirements-dev.txt .
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    env -u PIP_NO_CACHE_DIR pip install -r requirements-dev.txt
USER appuser

# ---- content-worker: thêm LibreOffice + font ----
FROM base AS content-worker

# LibreOffice + font cho chuyển đổi PPTX/PPT/ODP -> PDF.
# Font Noto/Liberation/Carlito/Caladea giữ đúng dấu tiếng Việt và layout.
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libreoffice-impress \
        libreoffice-core \
        libreoffice-common \
        fonts-noto-core \
        fonts-noto-extra \
        fonts-dejavu-core \
        fonts-liberation \
        fonts-crosextra-carlito \
        fonts-crosextra-caladea \
    && rm -rf /var/lib/apt/lists/*

COPY --chown=appuser:appuser app ./app
RUN mkdir -p /app/media && chown -R appuser:appuser /app

USER appuser

CMD ["python", "-m", "app.content_worker"]
