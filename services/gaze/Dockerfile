# syntax=docker/dockerfile:1
#
# Gaze service — multi-stage:
#   runtime: python 3.12 + onnxruntime-gpu (CUDA 12 / cuDNN 9 từ wheel pip) +
#            OpenCV. Landmarker chạy bằng ONNX. KHÔNG có torch/mediapipe.
#   export:  runtime + torch CPU + unigaze + mediapipe/tflite, chỉ để export
#            UniGaze và FaceLandmarker -> ONNX
#            (service `gaze-export`, chạy một lần rồi Exited (0)).
#   test:    runtime + dev deps cho pytest.
#
# Gaze là service DUY NHẤT cần GPU trong stack. CUDA/cuDNN đến từ wheel pip
# (extras `cuda`,`cudnn` của onnxruntime-gpu) nên KHÔNG cần base image NVIDIA;
# host chỉ cần NVIDIA driver + nvidia-container-toolkit (docker-compose đặt
# `gpus: all`). Chạy CPU vẫn được qua DEVICE=cpu nhưng chậm hơn nhiều.

# ---- Stage 1: runtime ----
FROM python:3.12.8-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive \
    PYUBJSON_NO_EXTENSION=1

# libgomp1: OpenMP cho onnxruntime/numpy. curl: HEALTHCHECK. libgl1/libglib2.0-0:
# OpenCV runtime khi giải mã ảnh (không cần EGL/GLES: runtime không có MediaPipe).
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cache wheel của pip bằng BuildKit cache mount; `env -u` vì base tắt pip cache.
# Chỉ import + kiểm tra metadata, KHÔNG nạp model ở bước build.
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    env -u PIP_NO_CACHE_DIR pip install -r requirements.txt \
    && pip check \
    && python -c "import cv2, ubjson, onnxruntime as ort; ort.preload_dlls(); assert 'CUDAExecutionProvider' in ort.get_available_providers(), ort.get_available_providers()"

# Chạy bằng user không phải root. Tạo sẵn /app/weights thuộc appuser để volume
# `gaze-weights` (mount đè lên đây) ghi được weights lúc runtime.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/weights \
    && chown appuser:appuser /app/weights

COPY --chown=appuser:appuser app ./app
COPY --chown=appuser:appuser scripts ./scripts
COPY --chown=appuser:appuser entrypoint.sh export-entrypoint.sh ./
RUN chmod +x entrypoint.sh export-entrypoint.sh \
    && python -c "from app.main import app; paths={r.path for r in app.routes}; assert {'/health','/ready','/session','/session/{sid}'} <= paths, paths" \
    && python -c "import app.services.pipeline"

USER appuser

EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]

# ---- Stage 2: export (torch chỉ có ở đây, không vào image runtime) ----
FROM runtime AS export

USER root
# libegl1/libgles2: MediaPipe (chỉ có trong stage export).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libegl1 \
    libgles2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-export.txt .
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    env -u PIP_NO_CACHE_DIR pip install -r requirements-export.txt \
    && python -c "import torch, onnx, tflite, mediapipe, unigaze.loader as l; assert 'unigaze_b16_joint' in l.MODEL_INDEX"
USER appuser

ENTRYPOINT ["/app/export-entrypoint.sh"]

# ---- Stage 3: test (dev deps, không dùng cho production) ----
FROM runtime AS test

USER root
COPY requirements-dev.txt .
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    env -u PIP_NO_CACHE_DIR pip install -r requirements-dev.txt
USER appuser

ENTRYPOINT ["python", "-m", "pytest"]
