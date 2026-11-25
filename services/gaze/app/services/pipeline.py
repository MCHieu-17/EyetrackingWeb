"""Pipeline hai tầng: CPU (decode/landmark/chuẩn hoá) và GPU (UniGaze ONNX).

Tách stage để runtime có thể overlap CPU và GPU: trong khi GPU chạy ViT cho
frame trước, CPU thread đã decode + landmark + warp frame kế tiếp.

Chỉ được import lazily (qua `app.services.runtime`) vì kéo theo onnxruntime/
opencv nặng. Runtime không cần torch/mediapipe: mọi ONNX (UniGaze, detector,
landmarks) được export sẵn bởi service `gaze-export`.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass

import cv2
import numpy as np
import onnxruntime as ort

from app.services.errors import InvalidImage
from app.services.gaze_geometry import denormalize_gaze, expand_bbox
from app.services.landmarker import OnnxFaceLandmarker
from app.services.preprocessing import ROI_SIZE, Preprocessor
from app.settings import Settings

logger = logging.getLogger("app.gaze")

#: Hệ số mở rộng bbox quanh mặt trước khi chuẩn hoá (như UniGaze gốc).
CROP_SCALE = 2.0
#: 4 góc mắt + 2 cánh mũi trong 478 điểm FaceLandmarker (iBUG 36,39,42,45,31,35).
LANDMARK_INDEX = [33, 133, 362, 263, 75, 290]


def decode_image(data: bytes | bytearray | memoryview) -> np.ndarray:
    """bytes/view ảnh (JPEG/PNG) -> ảnh RGB; raise InvalidImage nếu hỏng.

    Giữ `imdecode` + `cvtColor`: opencv 4.10 trong image không có
    `IMREAD_COLOR_RGB`; đổi decoder (Pillow) sẽ đổi pixel và ảnh hưởng gaze.
    """
    if not data:
        raise InvalidImage("ảnh rỗng")
    buf = np.frombuffer(data, dtype=np.uint8)
    frame = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if frame is None:
        raise InvalidImage("không decode được ảnh")
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


@dataclass(frozen=True)
class PreparedFace:
    """Mặt đã warp về ROI chuẩn (RGB uint8) + ma trận xoay camera ảo `rotation`."""

    rgb: np.ndarray
    rotation: np.ndarray


class FaceDetector:
    """FaceLandmarker ONNX: bbox từ 478 điểm + 6 điểm cho solvePnP."""

    def __init__(self, settings: Settings):
        self.landmarker = OnnxFaceLandmarker(
            settings.face_detector_onnx_path(),
            settings.face_landmarks_onnx_path(),
            settings.device,
        )

    def detect(self, frame_rgb: np.ndarray):
        """Trả ((xmin, ymin, xmax, ymax), landmarks 6 điểm) hoặc None."""
        points = self.landmarker.detect_points(frame_rgb)
        if points is None:
            return None
        xmin, ymin = points.min(axis=0)
        xmax, ymax = points.max(axis=0)
        bbox = (int(xmin), int(ymin), int(xmax), int(ymax))
        return bbox, points[LANDMARK_INDEX]


class CpuStage:
    """decode JPEG -> landmark -> warp 224x224. Chạy trong 1 thread riêng."""

    def __init__(self, settings: Settings):
        self.detector = FaceDetector(settings)
        self.preprocessor = Preprocessor()

    def prepare(self, image_bytes: bytes | memoryview) -> PreparedFace | None:
        rgb = decode_image(image_bytes)

        detection = self.detector.detect(rgb)
        if detection is None:
            return None
        bbox, landmarks = detection

        h, w = rgb.shape[:2]
        xmin, ymin, xmax, ymax = expand_bbox(bbox, CROP_SCALE, w, h)
        if xmax <= xmin or ymax <= ymin:
            return None
        face = np.ascontiguousarray(rgb[ymin:ymax, xmin:xmax])
        landmarks_crop = landmarks - np.array([xmin, ymin], dtype=np.float32)
        warped = self.preprocessor.process(face, landmarks_crop)
        if warped is None:
            return None
        image, rotation = warped
        return PreparedFace(image, rotation)

    def warmup(self) -> None:
        """Chạy detector + landmarks một lần để tránh spike ở frame đầu."""
        blank = np.zeros((360, 480, 3), dtype=np.uint8)
        self.detector.detect(blank)


def _nvidia_gpu_name() -> str | None:
    exe = shutil.which("nvidia-smi")
    if exe is None:
        return None
    try:
        out = subprocess.run(
            [exe, "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return out.splitlines()[0].strip() if out else None


class GpuStage:
    """UniGaze ONNX (onnxruntime) + denormalize về hệ camera. 1 thread riêng."""

    def __init__(self, settings: Settings):
        path = settings.unigaze_onnx_path()
        if not path.is_file():
            raise RuntimeError(
                f"Không thấy ONNX UniGaze tại {path}. Chạy service gaze-export "
                "(scripts.export_onnx) hoặc kiểm tra volume gaze-weights."
            )
        self.is_cuda = settings.device == "cuda"
        providers = ["CPUExecutionProvider"]
        if self.is_cuda:
            if "CUDAExecutionProvider" not in ort.get_available_providers():
                raise RuntimeError(
                    "DEVICE=cuda nhưng onnxruntime không có CUDAExecutionProvider"
                )
            ort.preload_dlls()
            providers = [("CUDAExecutionProvider", {}), "CPUExecutionProvider"]

        options = ort.SessionOptions()
        options.log_severity_level = 3
        self.session = ort.InferenceSession(
            str(path), sess_options=options, providers=providers
        )
        if self.is_cuda and self.session.get_providers()[0] != "CUDAExecutionProvider":
            raise RuntimeError("onnxruntime không nạp được CUDAExecutionProvider")

        self.device = "cuda:0" if self.is_cuda else "cpu"
        self.gpu_name = _nvidia_gpu_name() if self.is_cuda else None
        self.model_name = settings.unigaze_model
        self.precision = settings.precision
        self.batch_hint = settings.gpu_batch
        self._input = self.session.get_inputs()[0].name

    def predict_batch(
        self, prepareds: list[PreparedFace]
    ) -> list[tuple[float, float]]:
        if not prepareds:
            return []
        batch = np.stack([item.rgb for item in prepareds])
        pred = self.session.run(None, {self._input: batch})[0]
        return [
            denormalize_gaze(float(pitch), float(yaw), item.rotation)
            for (pitch, yaw), item in zip(pred.tolist(), prepareds)
        ]

    def predict(self, prepared: PreparedFace) -> tuple[float, float]:
        return self.predict_batch([prepared])[0]

    def warmup(self) -> None:
        """Chạy forward vài lần để CUDA autotune/kernel sẵn sàng."""
        dummy = PreparedFace(
            rgb=np.zeros((ROI_SIZE[1], ROI_SIZE[0], 3), dtype=np.uint8),
            rotation=np.eye(3),
        )
        reps = min(self.batch_hint, 8) if self.is_cuda else 1
        for _ in range(3):
            self.predict_batch([dummy] * reps)
