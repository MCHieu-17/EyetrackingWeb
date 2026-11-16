# syntax=docker/dockerfile:1
#
# Gaze service — multi-stage:
#   ai-base: python 3.12 + torch/torchvision CUDA 12.4 + libgomp1/curl
#   runtime: thêm lib GL/EGL cho OpenCV/MediaPipe + deps gaze
#
# Gaze là service DUY NHẤT cần GPU trong stack. CUDA/cuDNN đến từ wheel pip
# cu124 nên KHÔNG cần base image NVIDIA; host chỉ cần NVIDIA driver +
# nvidia-container-toolkit (docker-compose đặt `gpus: all`). Chạy CPU vẫn
# được qua DEVICE=cpu nhưng rất chậm.

# ---- Stage 1: AI base (torch CUDA 12.4) ----
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

# Assert ngay trong build để phát hiện sớm nếu pip chọn nhầm wheel (CPU sai CUDA).
# Cache wheel bằng BuildKit cache mount; `env -u` vì base tắt pip cache.
COPY requirements-torch.txt .
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    env -u PIP_NO_CACHE_DIR pip install -r requirements-torch.txt \
    && pip check \
    && python -c "import torch, torchvision; assert torch.__version__.startswith('2.6.0'), torch.__version__; assert torch.version.cuda == '12.4', torch.version.cuda; assert torchvision.__version__.startswith('0.21.0'), torchvision.__version__"

# ---- Stage 2: gaze runtime ----
FROM ai-base AS runtime

# Thư viện hệ thống cho OpenCV / MediaPipe (GL, EGL) — stage ai-base chỉ có
# libgomp1/curl.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libegl1 \
    libgles2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cài dependencies trước để tận dụng cache layer. Chỉ import + kiểm tra
# metadata, KHÔNG build model ở bước này: build model có thể tải weights từ
# HuggingFace (network) và cấp phát vài GB RAM. Model thật được kiểm tra ở RUN
# cuối (đọc từ app/services/pipeline.py).
#
# Cache wheel của pip bằng BuildKit cache mount; stage ai-base đặt
# PIP_NO_CACHE_DIR=1 nên phải `env -u` cho riêng lệnh pip.
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    env -u PIP_NO_CACHE_DIR pip install -r requirements.txt \
    && pip check \
    && python -c "import cv2, mediapipe, ubjson, unigaze.loader as l; assert 'unigaze_b16_joint' in l.MODEL_INDEX"

# Chạy bằng user không phải root. Tạo sẵn /app/weights thuộc appuser để volume
# `gaze-weights` (mount đè lên đây) ghi được weights lúc runtime.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/weights \
    && chown appuser:appuser /app/weights

COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser scripts ./scripts
COPY --chown=appuser:appuser entrypoint.sh ./
RUN chmod +x entrypoint.sh \
    && python -c "from app.main import app; paths={r.path for r in app.routes}; assert {'/health','/ready','/session','/session/{sid}'} <= paths, paths" \
    && python -c "import app.services.pipeline; import unigaze.loader as l; assert l.MODEL_INDEX, sorted(l.MODEL_INDEX)"

USER appuser

EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
