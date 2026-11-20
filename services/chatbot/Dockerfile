# syntax=docker/dockerfile:1
#
# Chatbot RAG service — multi-stage:
#   ai-base: python 3.12 + torch/torchvision CPU + libgomp1/curl
#   runtime: deps chatbot + embedding local Qwen3-Embedding-0.6B
#
# Chatbot KHÔNG cần GPU: embedding chạy CPU, LLM/VLM gọi River API. GPU chỉ
# dành cho services/gaze.

# ---- Stage 1: AI base (torch CPU) ----
FROM python:3.12.8-slim AS ai-base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    PYUBJSON_NO_EXTENSION=1

# libgomp1: OpenMP cho torch/numpy. curl: dùng cho HEALTHCHECK của service.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Assert ngay trong build để phát hiện sớm nếu pip chọn nhầm wheel torch (CUDA
# thay vì CPU). Cache wheel bằng BuildKit cache mount; `env -u` vì base tắt
# pip cache.
COPY requirements-torch-cpu.txt .
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    env -u PIP_NO_CACHE_DIR pip install -r requirements-torch-cpu.txt \
    && pip check \
    && python -c "import torch, torchvision; assert torch.__version__.startswith('2.6.0'), torch.__version__; assert torch.version.cuda is None, torch.version.cuda; assert torchvision.__version__.startswith('0.21.0'), torchvision.__version__"

# ---- Stage 2: chatbot runtime ----
FROM ai-base AS runtime

WORKDIR /app

# Cài dependencies trước để tận dụng cache layer. Assert ngay trong build để
# phát hiện sớm nếu pip chọn nhầm wheel torch (CUDA thay vì CPU).
#
# Cache wheel của pip bằng BuildKit cache mount: wheel được giữ ngoài image
# (không làm tăng size) và tái sử dụng khi requirements thay đổi, tránh phải
# tải lại toàn bộ thư viện mỗi lần rebuild. Stage ai-base đặt PIP_NO_CACHE_DIR=1;
# pip luôn tắt cache khi biến này tồn tại (kể cả giá trị 0/false), nên phải
# `env -u PIP_NO_CACHE_DIR` cho riêng lệnh pip.
COPY requirements.txt requirements-embedding.txt ./
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    env -u PIP_NO_CACHE_DIR pip install -r requirements.txt -r requirements-embedding.txt \
    && pip check \
    && python -c "import torch; assert torch.version.cuda is None, torch.version.cuda"

# Chạy bằng user không phải root. Tạo sẵn /app/weights thuộc appuser để volume
# `chatbot-weights` (mount đè lên đây) ghi được weights embedding lúc runtime.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/weights \
    && chown appuser:appuser /app/weights

COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser scripts ./scripts
COPY --chown=appuser:appuser entrypoint.sh ./

RUN chmod +x entrypoint.sh

USER appuser

EXPOSE 8000

# Thống nhất với docker-compose: /ready kiểm tra DB (503 khi chưa sẵn sàng).
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS http://localhost:8000/ready || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]

# ---- Stage 3: test (dev deps, không dùng cho production) ----
FROM runtime AS test

USER root
COPY requirements-dev.txt .
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    env -u PIP_NO_CACHE_DIR pip install -r requirements-dev.txt
USER appuser

ENTRYPOINT ["python", "-m", "pytest"]
