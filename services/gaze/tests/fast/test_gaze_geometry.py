"""Hình học gaze + tiền xử lý mặt (thuần numpy/opencv, không cần model)."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.services.gaze_geometry import (
    denormalize_gaze,
    expand_bbox,
    pitchyaw_to_vector,
    vector_to_pitchyaw,
)
from app.services.preprocessing import ROI_SIZE, Preprocessor

pytestmark = pytest.mark.fast


def test_pitchyaw_vector_roundtrip():
    for pitch, yaw in [(0.0, 0.0), (0.3, -0.5), (-0.7, 0.9)]:
        vector = pitchyaw_to_vector(pitch, yaw)
        assert np.linalg.norm(vector) == pytest.approx(1.0)
        got = vector_to_pitchyaw(vector)
        assert got == pytest.approx((pitch, yaw), abs=1e-9)


def test_denormalize_identity_rotation_keeps_gaze():
    assert denormalize_gaze(0.2, -0.4, np.eye(3)) == pytest.approx(
        (0.2, -0.4), abs=1e-9
    )


def test_denormalize_inverts_rotation():
    rotation = cv2.Rodrigues(np.array([0.1, -0.2, 0.05]))[0]
    pitch, yaw = 0.15, 0.3
    normalized = rotation @ pitchyaw_to_vector(pitch, yaw)
    n_pitch, n_yaw = vector_to_pitchyaw(normalized)
    assert denormalize_gaze(n_pitch, n_yaw, rotation) == pytest.approx(
        (pitch, yaw), abs=1e-9
    )


def test_expand_bbox_scales_and_clips():
    assert expand_bbox((40, 40, 60, 60), 2.0, 100, 100) == (30, 30, 70, 70)
    assert expand_bbox((0, 0, 60, 60), 2.0, 100, 100) == (0, 0, 90, 90)
    assert expand_bbox((50, 50, 100, 100), 2.0, 100, 100) == (25, 25, 100, 100)


def _synthetic_face(size: int = 480):
    pre = Preprocessor()
    focal = size * 4
    cam = np.array(
        [[focal, 0, size // 2], [0, focal, size // 2], [0, 0, 1]], dtype=float
    )
    rvec = np.array([0.05, -0.1, 0.0])
    tvec = np.array([[0.0], [0.0], [600.0 * 4]])
    points, _ = cv2.projectPoints(pre.face_pts, rvec, tvec, cam, np.zeros(5))
    image = np.random.default_rng(3).integers(
        0, 256, (size, size, 3), dtype=np.uint8
    )
    return pre, image, points.reshape(6, 2)


def test_preprocessor_outputs_roi_and_orthonormal_rotation():
    pre, image, landmarks = _synthetic_face()
    result = pre.process(image, landmarks)
    assert result is not None
    roi, rotation = result
    assert roi.shape == (ROI_SIZE[1], ROI_SIZE[0], 3)
    assert roi.dtype == np.uint8
    assert rotation @ rotation.T == pytest.approx(np.eye(3), abs=1e-6)
    assert np.linalg.det(rotation) == pytest.approx(1.0, abs=1e-6)


def test_preprocessor_rejects_wrong_landmark_count():
    pre, image, landmarks = _synthetic_face()
    assert pre.process(image, landmarks[:5]) is None
