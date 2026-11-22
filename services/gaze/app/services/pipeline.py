"""Pipeline hai tầng: CPU (decode/detect/chuẩn hoá) và GPU (UniGaze).

Tách stage để runtime có thể overlap CPU và GPU: trong khi GPU chạy ViT cho
frame trước, CPU thread đã decode + detect + warp frame kế tiếp.

Chỉ được import lazily (qua `app.services.runtime`) vì kéo theo mediapipe/
torch/opencv nặng.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
import torch

from app.services.errors import InvalidImage
from app.services.preprocessing import ROI_SIZE, Preprocessor
from app.settings import Settings

logger = logging.getLogger("app.gaze")


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
    """Mặt đã warp về ROI chuẩn, RGB uint8, sẵn sàng đưa vào GPU."""

    rgb: np.ndarray


class FaceDetector:
    """MediaPipe BlazeFace (CPU) + 6 keypoint cho solvePnP."""

    def __init__(self, weights_path: Path):
        if not weights_path.is_file():
            raise RuntimeError(
                f"Không thấy MediaPipe weights tại {weights_path}. "
                "Kiểm tra WEIGHTS_DIR và volume gaze-weights."
            )
        base_options = mp.tasks.BaseOptions(
            model_asset_path=str(weights_path),
            delegate=mp.tasks.BaseOptions.Delegate.CPU,  # model rất nhẹ
        )
        options = mp.tasks.vision.FaceDetectorOptions(
            base_options=base_options,
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
        )
        self.detector = mp.tasks.vision.FaceDetector.create_from_options(options)

    def detect(self, frame_rgb: np.ndarray):
        """Trả ((xmin, ymin, xmax, ymax), landmarks) hoặc None."""
        h, w = frame_rgb.shape[:2]
        mp_frame = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        results = self.detector.detect(mp_frame)
        if not results.detections:
            return None

        detection = results.detections[0]
        # solvePnP cần đúng 6 điểm; detection lạ/không đủ điểm -> bỏ frame.
        if not detection.keypoints or len(detection.keypoints) != 6:
            return None

        box = detection.bounding_box
        xmin = max(0, box.origin_x)
        ymin = max(0, box.origin_y)
        xmax = min(w, box.origin_x + box.width)
        ymax = min(h, box.origin_y + box.height)
        if xmax <= xmin or ymax <= ymin:
            return None

        landmarks = np.array(
            [[pt.x * w, pt.y * h] for pt in detection.keypoints],
            dtype=np.float32,
        )
        return (xmin, ymin, xmax, ymax), landmarks


class CpuStage:
    """decode JPEG -> detect -> warp 224x224. Chạy trong 1 thread riêng."""

    def __init__(self, settings: Settings):
        self.detector = FaceDetector(settings.mediapipe_weights_path())
        self.preprocessor = Preprocessor()

    def prepare(self, image_bytes: bytes | memoryview) -> PreparedFace | None:
        rgb = decode_image(image_bytes)

        detection = self.detector.detect(rgb)
        if detection is None:
            return None
        (xmin, ymin, xmax, ymax), landmarks = detection

        face = np.ascontiguousarray(rgb[ymin:ymax, xmin:xmax])
        landmarks_crop = landmarks - np.array([xmin, ymin], dtype=np.float32)
        warped = self.preprocessor.process(face, landmarks_crop)
        if warped is None:
            return None
        return PreparedFace(warped)

    def warmup(self) -> None:
        """Chạy graph MediaPipe một lần để tránh spike ở frame đầu."""
        blank = np.zeros((360, 480, 3), dtype=np.uint8)
        self.detector.detect(blank)


class GpuStage:
    """UniGaze forward + normalize tensor. Chạy trong 1 thread riêng."""

    def __init__(self, settings: Settings):
        import unigaze.loader as loader

        weights = settings.unigaze_weights_path()
        if not weights.is_file():
            raise RuntimeError(
                f"Không thấy weights UniGaze tại {weights}. "
                "Kiểm tra UNIGAZE_MODEL và volume gaze-weights."
            )
        if weights.stem not in loader.MODEL_INDEX:
            raise RuntimeError(
                f"UNIGAZE_MODEL={weights.stem!r} không có trong "
                f"unigaze.loader.MODEL_INDEX: {sorted(loader.MODEL_INDEX)}"
            )

        self.device = torch.device(settings.device)
        if self.device.type == "cuda":
            if not torch.cuda.is_available():
                raise RuntimeError("DEVICE=cuda nhưng torch không thấy CUDA")
            if self.device.index is None:
                self.device = torch.device("cuda", torch.cuda.current_device())
            torch.cuda.set_device(self.device)
            self.gpu_name = torch.cuda.get_device_name(self.device)
        else:
            self.gpu_name = None

        self.dtype = (
            torch.float16 if settings.precision == "fp16" else torch.float32
        )
        self.model_name = settings.unigaze_model
        self.precision = settings.precision
        self.is_cuda = self.device.type == "cuda"
        self.batch_hint = settings.gpu_batch
        self._host_buf: torch.Tensor | None = None

        self.model = loader.build_unigaze_model(weights.stem)
        self.model.load_unigaze_weights(str(weights))
        self.model.to(self.device)
        # Module.half() sửa tại chỗ; chỉ gọi đúng một lần ở đây.
        if self.dtype == torch.float16:
            self.model.half()
        self.model.eval()

        self._mean = torch.tensor(
            [0.485, 0.456, 0.406], device=self.device, dtype=torch.float32
        ).view(1, 3, 1, 1)
        self._std = torch.tensor(
            [0.229, 0.224, 0.225], device=self.device, dtype=torch.float32
        ).view(1, 3, 1, 1)
        # Fuse /255 vào mean/std: (x/255 - mean)/std == (x - mean*255)/(std*255).
        self._norm_mean = self._mean * 255.0
        self._norm_std = self._std * 255.0

    def _to_batch_tensor(self, prepareds: list[PreparedFace]) -> torch.Tensor:
        """Ghép N mặt thành tensor [N, 3, H, W] đã normalize.

        Khi CUDA, copy từng ROI thẳng vào buffer pinned NCHW rồi H2D
        non_blocking một lần; normalize fuse bằng sub_/div_ để không tạo thêm
        temporary float32 trên GPU.
        """
        if not prepareds:
            raise ValueError("batch rỗng")
        count = len(prepareds)
        if self.is_cuda:
            if self._host_buf is None or self._host_buf.shape[0] < count:
                capacity = max(count, self.batch_hint)
                # Buffer phải là normal tensor: nếu tạo trong inference_mode,
                # các lần copy_ sau (vd stage_latency) sẽ bị PyTorch chặn.
                with torch.inference_mode(False):
                    self._host_buf = torch.empty(
                        (capacity, 3, ROI_SIZE[1], ROI_SIZE[0]),
                        dtype=torch.uint8,
                        pin_memory=True,
                    )
            for index, item in enumerate(prepareds):
                self._host_buf[index].copy_(
                    torch.from_numpy(item.rgb).permute(2, 0, 1)
                )
            tensor = self._host_buf[:count].to(
                self.device, dtype=torch.float32, non_blocking=True
            )
        else:
            stacked = np.stack([item.rgb for item in prepareds])
            tensor = (
                torch.from_numpy(stacked)
                .permute(0, 3, 1, 2)
                .contiguous()
                .to(self.device, dtype=torch.float32)
            )
        tensor.sub_(self._norm_mean).div_(self._norm_std)
        return tensor.to(self.dtype)

    def _to_tensor(self, prepared: PreparedFace) -> torch.Tensor:
        return self._to_batch_tensor([prepared])

    @torch.inference_mode()
    def predict_batch(
        self, prepareds: list[PreparedFace]
    ) -> list[tuple[float, float]]:
        if not prepareds:
            return []
        pred = self.model(self._to_batch_tensor(prepareds))["pred_gaze"]
        # Một lần D2H + synchronize cho cả batch.
        return [(float(pitch), float(yaw)) for pitch, yaw in pred.tolist()]

    @torch.inference_mode()
    def predict(self, prepared: PreparedFace) -> tuple[float, float]:
        return self.predict_batch([prepared])[0]

    def warmup(self) -> None:
        """Chạy forward vài lần để CUDA autotune/kernel sẵn sàng."""
        dummy = PreparedFace(
            rgb=np.zeros((ROI_SIZE[1], ROI_SIZE[0], 3), dtype=np.uint8)
        )
        reps = min(self.batch_hint, 8) if self.is_cuda else 1
        for _ in range(3):
            self.predict_batch([dummy] * reps)
        if self.is_cuda:
            torch.cuda.synchronize()
