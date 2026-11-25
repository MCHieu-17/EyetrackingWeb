"""Smoke: landmarker ONNX thật khớp 478 điểm của MediaPipe trên ảnh mẫu (golden)."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from app.services.landmarker import OnnxFaceLandmarker
from app.settings import Settings

pytestmark = pytest.mark.smoke

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="module")
def landmarker():
    settings = Settings.from_env()
    detector = settings.face_detector_onnx_path()
    landmarks = settings.face_landmarks_onnx_path()
    if not detector.is_file() or not landmarks.is_file():
        pytest.skip(f"thiếu ONNX landmarker: {detector} / {landmarks}")
    return OnnxFaceLandmarker(detector, landmarks, "cpu")


def test_landmarks_match_mediapipe_golden(landmarker):
    golden = np.load(FIXTURES / "face_sample_landmarks.npz")
    frame = cv2.cvtColor(cv2.imread(str(FIXTURES / "face_sample.jpg")), cv2.COLOR_BGR2RGB)
    assert list(golden["size"]) == [frame.shape[1], frame.shape[0]]

    points = landmarker.detect_points(frame)
    assert points is not None and points.shape == (478, 2)
    error = np.linalg.norm(points - golden["points"], axis=1)
    assert error.mean() < 0.3
    assert np.percentile(error, 99) < 1.5


def test_blank_frame_has_no_face(landmarker):
    assert landmarker.detect_points(np.zeros((360, 480, 3), dtype=np.uint8)) is None
