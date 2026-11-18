#!/bin/sh
set -e

# Thread caps: container thường bị giới hạn CPU (vd 2 core) nhưng OpenCV/torch
# vẫn thấy toàn bộ core host. Oversubscription gây throttling và stall ~80ms.
# Đặt ở đây để đúng cả khi stack.env/compose chưa cập nhật biến mới.
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-1}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-1}"
# Weights đã nằm trong volume; không gọi HuggingFace lúc khởi động.
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"

echo "== Gaze API =="
python -m scripts.download_weights

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --ws-max-size 1048576 \
    --timeout-keep-alive 30
