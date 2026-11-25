"""FaceLandmarker (478 điểm) chạy bằng ONNX Runtime, không cần MediaPipe.

Tái hiện đồ thị `face_landmarker.task` ở chế độ IMAGE: BlazeFace (128x128) ->
weighted NMS -> ROI xoay x1.5 -> mạng landmark 256x256 -> chiếu 478 điểm về ảnh
gốc. Hai mạng được `scripts/export_landmarker.py` convert từ TFLite sang ONNX.

Phần số học (anchor, decode, NMS, ROI, chiếu) là numpy thuần để test không cần
model/GPU. `OnnxFaceLandmarker` chỉ gắn thêm hai session ORT.
"""

from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

DETECTOR_SIZE = 128
LANDMARK_SIZE = 256
NUM_LANDMARKS = 478
#: Ngưỡng điểm phát hiện mặt và ngưỡng suppression (mặc định của FaceLandmarker).
MIN_DETECTION_SCORE = 0.5
NMS_IOU_THRESHOLD = 0.3
#: Ngưỡng face-presence của mạng landmark (sigmoid).
MIN_PRESENCE_SCORE = 0.5
SCORE_CLIP = 100.0
ROI_SCALE = 1.5


def generate_anchors(
    size: int = DETECTOR_SIZE, strides: tuple[int, ...] = (8, 16, 16, 16)
) -> np.ndarray:
    """896 anchor SSD cố định kích thước: (x_center, y_center) chuẩn hoá."""
    anchors: list[tuple[float, float]] = []
    layer = 0
    while layer < len(strides):
        last = layer
        per_cell = 0
        while last < len(strides) and strides[last] == strides[layer]:
            per_cell += 2  # aspect 1.0 + interpolated scale
            last += 1
        fmap = math.ceil(size / strides[layer])
        for y in range(fmap):
            for x in range(fmap):
                for _ in range(per_cell):
                    anchors.append(((x + 0.5) / fmap, (y + 0.5) / fmap))
        layer = last
    return np.asarray(anchors, dtype=np.float32)


ANCHORS = generate_anchors()


def letterbox(width: int, height: int, size: int = DETECTOR_SIZE):
    """Ma trận affine ảnh -> tensor `size`², giữ tỉ lệ, đệm 0 hai bên."""
    scale = min(size / width, size / height)
    pad_x = (size - width * scale) / 2.0
    pad_y = (size - height * scale) / 2.0
    matrix = np.array([[scale, 0.0, pad_x], [0.0, scale, pad_y]], dtype=np.float64)
    return matrix, scale, pad_x, pad_y


def detector_input(frame_rgb: np.ndarray) -> tuple[np.ndarray, tuple]:
    """Ảnh RGB uint8 -> tensor [1,128,128,3] trong [-1,1] + thông số letterbox."""
    h, w = frame_rgb.shape[:2]
    matrix, scale, pad_x, pad_y = letterbox(w, h)
    resized = cv2.warpAffine(
        frame_rgb,
        matrix,
        (DETECTOR_SIZE, DETECTOR_SIZE),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    tensor = resized.astype(np.float32) * (1.0 / 127.5) - 1.0
    return tensor[None], (scale, pad_x, pad_y)


def _iou(box: np.ndarray, boxes: np.ndarray) -> np.ndarray:
    x1 = np.maximum(box[0], boxes[:, 0])
    y1 = np.maximum(box[1], boxes[:, 1])
    x2 = np.minimum(box[2], boxes[:, 2])
    y2 = np.minimum(box[3], boxes[:, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    area = (box[2] - box[0]) * (box[3] - box[1])
    areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    union = area + areas - inter
    return np.where(union > 0, inter / np.maximum(union, 1e-12), 0.0)


def decode_detection(
    regressors: np.ndarray, scores: np.ndarray
) -> tuple[np.ndarray, np.ndarray] | None:
    """Raw BlazeFace -> (box[xmin,ymin,xmax,ymax], keypoints[6,2]) chuẩn hoá.

    Weighted NMS như MediaPipe, chỉ giữ mặt có điểm cao nhất (num_faces=1).
    Toạ độ trả về còn ở hệ tensor 128x128 (chưa bỏ letterbox).
    """
    logits = np.clip(scores.reshape(-1).astype(np.float64), -SCORE_CLIP, SCORE_CLIP)
    probs = 1.0 / (1.0 + np.exp(-logits))
    keep = np.nonzero(probs >= MIN_DETECTION_SCORE)[0]
    if keep.size == 0:
        return None
    raw = regressors.reshape(-1, regressors.shape[-1])[keep]
    anchors = ANCHORS[keep]
    scale = float(DETECTOR_SIZE)
    cx = raw[:, 0] / scale + anchors[:, 0]
    cy = raw[:, 1] / scale + anchors[:, 1]
    w = raw[:, 2] / scale
    h = raw[:, 3] / scale
    boxes = np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], axis=1)
    keypoints = raw[:, 4:16].reshape(-1, 6, 2) / scale + anchors[:, None, :]
    conf = probs[keep]

    order = np.argsort(-conf, kind="stable")
    best = order[0]
    group = order[_iou(boxes[best], boxes[order]) > NMS_IOU_THRESHOLD]
    weights = conf[group]
    total = weights.sum()
    box = (boxes[group] * weights[:, None]).sum(axis=0) / total
    kps = (keypoints[group] * weights[:, None, None]).sum(axis=0) / total
    return box, kps


def roi_from_detection(
    box: np.ndarray,
    keypoints: np.ndarray,
    scale: float,
    pad_x: float,
    pad_y: float,
) -> tuple[float, float, float, float]:
    """Detection (chuẩn hoá theo tensor) -> ROI (cx, cy, side, rotation) theo pixel ảnh."""

    def to_image(points: np.ndarray) -> np.ndarray:
        px = np.asarray(points, dtype=np.float64) * DETECTOR_SIZE
        return np.stack([(px[..., 0] - pad_x) / scale, (px[..., 1] - pad_y) / scale], -1)

    xmin, ymin = to_image(box[:2])
    xmax, ymax = to_image(box[2:])
    eye_a, eye_b = to_image(keypoints[0]), to_image(keypoints[1])
    rotation = -math.atan2(-(eye_b[1] - eye_a[1]), eye_b[0] - eye_a[0])
    rotation -= 2 * math.pi * math.floor((rotation + math.pi) / (2 * math.pi))
    side = max(xmax - xmin, ymax - ymin) * ROI_SCALE
    return float((xmin + xmax) / 2.0), float((ymin + ymax) / 2.0), float(side), rotation


def roi_matrix(cx: float, cy: float, side: float, rotation: float) -> np.ndarray:
    """Ma trận affine ảnh gốc -> ROI 256x256 (đã xoay), dùng cho warpAffine."""
    cos, sin = math.cos(rotation), math.sin(rotation)
    k = side / LANDMARK_SIZE
    # roi -> ảnh: p = c + R * (q - 128) * k
    forward = np.array(
        [
            [cos * k, -sin * k, cx - (cos - sin) * 0.5 * side],
            [sin * k, cos * k, cy - (sin + cos) * 0.5 * side],
        ],
        dtype=np.float64,
    )
    return cv2.invertAffineTransform(forward)


def project_landmarks(
    raw: np.ndarray, cx: float, cy: float, side: float, rotation: float
) -> np.ndarray:
    """1434 giá trị của mạng landmark -> [478,2] pixel ảnh gốc."""
    pts = raw.reshape(NUM_LANDMARKS, 3)[:, :2] / LANDMARK_SIZE - 0.5
    cos, sin = math.cos(rotation), math.sin(rotation)
    x = (pts[:, 0] * cos - pts[:, 1] * sin) * side + cx
    y = (pts[:, 0] * sin + pts[:, 1] * cos) * side + cy
    return np.stack([x, y], axis=1).astype(np.float32)


class OnnxFaceLandmarker:
    """Detector + landmarker ONNX. Mỗi instance giữ session riêng (mỗi thread một)."""

    def __init__(self, detector_path: Path, landmarks_path: Path, device: str):
        import onnxruntime as ort

        for path in (detector_path, landmarks_path):
            if not path.is_file():
                raise RuntimeError(
                    f"Không thấy ONNX landmarker tại {path}. Chạy service "
                    "gaze-export hoặc kiểm tra volume gaze-weights."
                )
        options = ort.SessionOptions()
        options.log_severity_level = 3
        providers: list = ["CPUExecutionProvider"]
        if device == "cuda":
            if "CUDAExecutionProvider" not in ort.get_available_providers():
                raise RuntimeError(
                    "DEVICE=cuda nhưng onnxruntime không có CUDAExecutionProvider"
                )
            ort.preload_dlls()
            # TF32 làm lệch landmark ~0.1 px; tắt vì mạng nhỏ, không chậm hơn.
            providers = [
                ("CUDAExecutionProvider", {"use_tf32": 0}),
                "CPUExecutionProvider",
            ]
        self._detector = ort.InferenceSession(
            str(detector_path), sess_options=options, providers=providers
        )
        self._landmarks = ort.InferenceSession(
            str(landmarks_path), sess_options=options, providers=providers
        )
        if device == "cuda":
            for session in (self._detector, self._landmarks):
                if session.get_providers()[0] != "CUDAExecutionProvider":
                    raise RuntimeError(
                        "onnxruntime không nạp được CUDAExecutionProvider"
                    )
        # Output đặt theo thứ tự TFLite: detector (regressors, scores),
        # landmarks (1434 điểm, face-presence, ...).
        self._det_out = ["out0", "out1"]
        self._lm_out = ["out0", "out1"]

    def detect_points(self, frame_rgb: np.ndarray) -> np.ndarray | None:
        """Ảnh RGB uint8 -> [478,2] pixel ảnh gốc, hoặc None nếu không có mặt."""
        tensor, (scale, pad_x, pad_y) = detector_input(frame_rgb)
        reg, cls = self._detector.run(self._det_out, {"input": tensor})
        found = decode_detection(reg[0], cls[0])
        if found is None:
            return None
        box, keypoints = found
        cx, cy, side, rotation = roi_from_detection(box, keypoints, scale, pad_x, pad_y)
        if side <= 1.0:
            return None
        # Vùng ROI vượt ảnh: MediaPipe lặp pixel biên (không đệm 0) ở nhánh landmark.
        crop = cv2.warpAffine(
            frame_rgb,
            roi_matrix(cx, cy, side, rotation),
            (LANDMARK_SIZE, LANDMARK_SIZE),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
        tensor = crop.astype(np.float32) * (1.0 / 255.0)
        raw, flag = self._landmarks.run(self._lm_out, {"input": tensor[None]})
        logit = float(np.clip(flag.reshape(-1)[0], -SCORE_CLIP, SCORE_CLIP))
        if 1.0 / (1.0 + math.exp(-logit)) < MIN_PRESENCE_SCORE:
            return None
        return project_landmarks(raw[0], cx, cy, side, rotation)
