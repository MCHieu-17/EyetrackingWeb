"""Hình học gaze thuần numpy (không phụ thuộc torch/opencv/mediapipe)."""

from __future__ import annotations

import numpy as np


def expand_bbox(
    bbox: tuple[float, float, float, float], scale: float, w: int, h: int
) -> tuple[int, int, int, int]:
    """Mở rộng bbox quanh tâm rồi cắt theo biên ảnh (giữ ngữ cảnh quanh mặt)."""
    xmin, ymin, xmax, ymax = bbox
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    hw, hh = (xmax - xmin) * scale / 2, (ymax - ymin) * scale / 2
    return (
        max(0, int(cx - hw)),
        max(0, int(cy - hh)),
        min(w, int(cx + hw)),
        min(h, int(cy + hh)),
    )


def pitchyaw_to_vector(pitch: float, yaw: float) -> np.ndarray:
    return np.array(
        [
            np.cos(pitch) * np.sin(yaw),
            np.sin(pitch),
            np.cos(pitch) * np.cos(yaw),
        ]
    )


def vector_to_pitchyaw(vector: np.ndarray) -> tuple[float, float]:
    vector = vector / np.linalg.norm(vector)
    return float(np.arcsin(vector[1])), float(np.arctan2(vector[0], vector[2]))


def denormalize_gaze(
    pitch: float, yaw: float, rotation: np.ndarray
) -> tuple[float, float]:
    """Đưa gaze từ hệ camera chuẩn hoá (đã xoay `rotation`) về hệ camera thật."""
    vector = np.dot(np.linalg.inv(rotation), pitchyaw_to_vector(pitch, yaw))
    return vector_to_pitchyaw(vector)
