"""Cấu hình dùng chung cho gaze service.

Gom mọi biến môi trường về một chỗ; phần còn lại của code chỉ import từ đây.
Module này KHÔNG import torch/mediapipe/opencv để script nhẹ (download_weights,
test) cũng dùng được.
"""

import os
from pathlib import Path

# Thư mục chứa weights (unigaze + mediapipe), tải lúc runtime bởi
# scripts/download_weights.py. Mặc định /app/weights khớp volume `gaze-weights`
# của docker-compose; đặt WEIGHTS_DIR khi chạy ngoài image.
WEIGHTS_DIR = Path(os.getenv("WEIGHTS_DIR", "/app/weights"))

# Số mẫu tối thiểu cho mỗi điểm calibration trước khi train.
MIN_SAMPLES = int(os.getenv("MIN_SAMPLES", "1"))

# Số điểm calibration tối đa được khai báo trong 1 session (khớp cap num_points
# phía backend = 64).
MAX_POINTS = int(os.getenv("MAX_POINTS", "64"))

# Giới hạn số mẫu giữ lại cho mỗi điểm (giữ mẫu mới nhất) để RAM không phình khi
# client gửi liên tục.
MAX_SAMPLES_PER_POINT = int(os.getenv("MAX_SAMPLES_PER_POINT", "50"))

# Kích thước ảnh upload tối đa cho /calibrate và /import (bytes).
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))

# Vòng đời session (giây) và số session đồng thời tối đa.
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "1800"))
MAX_SESSIONS = int(os.getenv("MAX_SESSIONS", "100"))

# Số worker suy luận. torch/mediapipe không thread-safe nên mặc định 1;
# tăng lên khi chạy nhiều GPU/process riêng biệt.
INFER_WORKERS = int(os.getenv("INFER_WORKERS", "1"))

# Giới hạn số frame chờ trong executor. Khi đầy, trả lỗi overload thay vì
# để queue phình vô hạn làm tăng latency toàn hệ thống.
MAX_INFERENCE_QUEUE = int(os.getenv("MAX_INFERENCE_QUEUE", "32"))

# FPS tối thiểu giữa 2 frame của cùng một session (ms). Client có thể gửi dày
# hơn; server drop bớt để bảo vệ GPU khi đông người.
MIN_FRAME_INTERVAL_MS = int(os.getenv("MIN_FRAME_INTERVAL_MS", "80"))

# Quyết định model chạy local phải đặt tường minh trong .env/stack.env.
# Không tự dò GPU và không hardcode tên weights trong code.
DEVICE = os.getenv("DEVICE", "").strip().lower()
UNIGAZE_MODEL = os.getenv("UNIGAZE_MODEL", "").strip()

VALID_DEVICES = ("cpu", "cuda")


def get_device() -> str:
    """Trả về DEVICE đã đặt tường minh; thiếu/sai -> fail-fast."""
    if DEVICE not in VALID_DEVICES:
        raise RuntimeError(
            "Thiếu hoặc sai DEVICE. Đặt DEVICE=cpu hoặc DEVICE=cuda "
            "trong .env (local) hoặc stack.env (production)."
        )
    return DEVICE


def get_unigaze_model() -> str:
    """Tên weights UniGaze, ví dụ unigaze_b16_joint."""
    if not UNIGAZE_MODEL:
        raise RuntimeError(
            "Thiếu UNIGAZE_MODEL. Đặt tên weights trong .env/stack.env, "
            "ví dụ UNIGAZE_MODEL=unigaze_b16_joint."
        )
    if (
        "/" in UNIGAZE_MODEL
        or "\\" in UNIGAZE_MODEL
        or UNIGAZE_MODEL in {".", ".."}
        or UNIGAZE_MODEL.startswith(".")
    ):
        raise RuntimeError(
            f"UNIGAZE_MODEL={UNIGAZE_MODEL!r} không hợp lệ; chỉ dùng tên file "
            "không có đường dẫn, ví dụ unigaze_b16_joint."
        )
    return UNIGAZE_MODEL


def unigaze_weights_path() -> Path:
    """Đường dẫn weights theo UNIGAZE_MODEL (không hardcode trong pipeline)."""
    return WEIGHTS_DIR / f"{get_unigaze_model()}.safetensors"


# One-Euro smoothing (làm mượt POG, xem app/services/smoothing.py)
# Tọa độ là [0, 1] theo viewport nên các ngưỡng tính theo "bề rộng viewport/giây".
# `beta` là nút chính để BỚT TRỄ: cao hơn -> bám nhanh khi lia mắt.
ONEEURO_BETA = float(os.getenv("ONEEURO_BETA", "0.5"))
# Cutoff khi gần như đứng yên: thấp -> ít rung, cao -> bớt trễ nhưng run hơn.
ONEEURO_MIN_CUTOFF = float(os.getenv("ONEEURO_MIN_CUTOFF", "0.5"))
# Cutoff làm mượt ước lượng vận tốc: cao -> thích ứng tốc độ nhanh hơn.
ONEEURO_D_CUTOFF = float(os.getenv("ONEEURO_D_CUTOFF", "1.0"))
