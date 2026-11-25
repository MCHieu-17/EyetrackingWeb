#!/bin/sh
set -e

# Chạy một lần: tải safetensors + FaceLandmarker rồi export UniGaze + landmarker -> ONNX vào
# volume gaze-weights. Idempotent (manifest khớp sha256 thì bỏ qua).
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-2}"
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"

echo "== Gaze export =="
python -m scripts.download_weights --unigaze
python -m scripts.export_onnx
python -m scripts.export_landmarker
