"""Cấu hình dùng chung cho gaze service.

Gom mọi biến môi trường về một chỗ. Module này KHÔNG import onnxruntime/opencv
để script nhẹ (download_weights, test) cũng dùng được.

`Settings.from_env()` chỉ đọc env; `Settings.validate()` mới fail-fast. Nhờ vậy
test có thể dựng Settings trực tiếp mà không cần biến môi trường.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

VALID_DEVICES = ("cpu", "cuda")
VALID_PRECISIONS = ("fp32", "fp16")
#: Trần cứng theo contract backend (calibration tối đa 64 điểm).
MAX_POINTS_HARD_CAP = 64


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return float(raw)


def _env_str(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


def frame_interval_ms(fps: int) -> int:
    """Khoảng cách tối thiểu giữa 2 frame của cùng session (ms).

    Trừ 15% dung sai để jitter của setTimeout/event loop phía client không làm
    rớt frame hợp lệ. Trước đây 5% quá sát: ở 15 FPS ngưỡng là 63ms trong khi
    client gửi 66.7ms, chỉ cần trễ ~4ms là frame bị throttle. FPS ngoài 1..60
    bị coi là cấu hình sai -> fail-fast.
    """
    if not 1 <= fps <= 60:
        raise ValueError("GAZE_FPS phải nằm trong khoảng 1..60")
    return max(1, int(1000 / fps * 0.85))


@dataclass(frozen=True)
class Settings:
    """Toàn bộ cấu hình runtime của gaze service."""

    weights_dir: Path = Path("/app/weights")
    device: str = ""
    unigaze_model: str = ""
    precision: str = "fp32"

    min_samples: int = 1
    max_points: int = 64
    max_samples_per_point: int = 50

    max_upload_bytes: int = 5 * 1024 * 1024
    max_frame_bytes: int = 1024 * 1024

    session_ttl_seconds: int = 1800
    max_sessions: int = 100

    gaze_fps: int = 15
    max_queue: int = 8
    gpu_queue: int = 12
    gpu_batch: int = 8
    cpu_workers: int = 2
    frame_max_age_ms: int = 200
    inference_timeout_s: float = 5.0

    oneeuro_beta: float = 0.5
    oneeuro_min_cutoff: float = 0.5
    oneeuro_d_cutoff: float = 1.0

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            weights_dir=Path(_env_str("WEIGHTS_DIR", "/app/weights")),
            device=_env_str("DEVICE", "").lower(),
            unigaze_model=_env_str("UNIGAZE_MODEL", ""),
            precision=_env_str("INFERENCE_PRECISION", "fp32").lower(),
            min_samples=_env_int("MIN_SAMPLES", 1),
            max_points=_env_int("MAX_POINTS", 64),
            max_samples_per_point=_env_int("MAX_SAMPLES_PER_POINT", 50),
            max_upload_bytes=_env_int("MAX_UPLOAD_BYTES", 5 * 1024 * 1024),
            max_frame_bytes=_env_int("MAX_FRAME_BYTES", 1024 * 1024),
            session_ttl_seconds=_env_int("SESSION_TTL_SECONDS", 1800),
            max_sessions=_env_int("MAX_SESSIONS", 100),
            gaze_fps=_env_int("GAZE_FPS", 15),
            max_queue=_env_int("MAX_QUEUE", 8),
            gpu_queue=_env_int("GPU_QUEUE", 12),
            gpu_batch=_env_int("GPU_BATCH", 8),
            cpu_workers=_env_int("CPU_WORKERS", 2),
            frame_max_age_ms=_env_int("FRAME_MAX_AGE_MS", 200),
            inference_timeout_s=_env_float("INFERENCE_TIMEOUT_S", 5.0),
            oneeuro_beta=_env_float("ONEEURO_BETA", 0.5),
            oneeuro_min_cutoff=_env_float("ONEEURO_MIN_CUTOFF", 0.5),
            oneeuro_d_cutoff=_env_float("ONEEURO_D_CUTOFF", 1.0),
        )

    # ---- Giá trị dẫn xuất ----

    @property
    def min_frame_interval_s(self) -> float:
        return frame_interval_ms(self.gaze_fps) / 1000.0

    @property
    def frame_max_age_s(self) -> float:
        return self.frame_max_age_ms / 1000.0

    def unigaze_weights_path(self) -> Path:
        return self.weights_dir / f"{self.unigaze_model}.safetensors"

    def unigaze_onnx_path(self) -> Path:
        return self.weights_dir / f"{self.unigaze_model}.{self.precision}.onnx"

    def face_landmarker_path(self) -> Path:
        """File `.task` nguồn; chỉ service gaze-export đọc để convert sang ONNX."""
        return self.weights_dir / "face_landmarker.task"

    def face_detector_onnx_path(self) -> Path:
        return self.weights_dir / "face_detector.onnx"

    def face_landmarks_onnx_path(self) -> Path:
        return self.weights_dir / "face_landmarks.onnx"

    # ---- Validate ----

    def validate(self) -> None:
        """Fail-fast cấu hình sai. Gọi trong lifespan trước khi load model."""
        if self.device not in VALID_DEVICES:
            raise RuntimeError(
                "Thiếu hoặc sai DEVICE. Đặt DEVICE=cpu hoặc DEVICE=cuda "
                "trong .env (local) hoặc stack.env (production)."
            )
        if self.precision not in VALID_PRECISIONS:
            raise RuntimeError(
                f"INFERENCE_PRECISION={self.precision!r} không hợp lệ; "
                f"chỉ dùng {', '.join(VALID_PRECISIONS)}."
            )
        if self.precision == "fp16" and self.device == "cpu":
            raise RuntimeError("INFERENCE_PRECISION=fp16 cần DEVICE=cuda")
        if not self.unigaze_model:
            raise RuntimeError(
                "Thiếu UNIGAZE_MODEL. Đặt tên weights trong .env/stack.env, "
                "ví dụ UNIGAZE_MODEL=unigaze_b16_joint."
            )
        model = self.unigaze_model
        if (
            "/" in model
            or "\\" in model
            or model in {".", ".."}
            or model.startswith(".")
        ):
            raise RuntimeError(
                f"UNIGAZE_MODEL={model!r} không hợp lệ; chỉ dùng tên file "
                "không có đường dẫn, ví dụ unigaze_b16_joint."
            )
        frame_interval_ms(self.gaze_fps)  # raise nếu FPS ngoài 1..60
        if not 1 <= self.max_points <= MAX_POINTS_HARD_CAP:
            raise RuntimeError("MAX_POINTS phải nằm trong khoảng 1..64")
        if self.min_samples < 1:
            raise RuntimeError("MIN_SAMPLES phải >= 1")
        if self.max_samples_per_point < self.min_samples:
            raise RuntimeError("MAX_SAMPLES_PER_POINT phải >= MIN_SAMPLES")
        if self.max_upload_bytes <= 0 or self.max_frame_bytes <= 0:
            raise RuntimeError("MAX_UPLOAD_BYTES/MAX_FRAME_BYTES phải > 0")
        if self.max_queue < 1:
            raise RuntimeError("MAX_QUEUE phải >= 1")
        if not 1 <= self.gpu_queue <= 64:
            raise RuntimeError("GPU_QUEUE phải nằm trong khoảng 1..64")
        if not 1 <= self.gpu_batch <= 16:
            raise RuntimeError("GPU_BATCH phải nằm trong khoảng 1..16")
        if not 1 <= self.cpu_workers <= 8:
            raise RuntimeError("CPU_WORKERS phải nằm trong khoảng 1..8")
        if self.frame_max_age_ms < 1:
            raise RuntimeError("FRAME_MAX_AGE_MS phải >= 1")
        if self.inference_timeout_s <= 0:
            raise RuntimeError("INFERENCE_TIMEOUT_S phải > 0")
