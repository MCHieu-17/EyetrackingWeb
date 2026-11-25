"""Phần số học của landmarker ONNX (anchor, decode, NMS, ROI, chiếu), không cần model."""

from __future__ import annotations

import math

import cv2
import numpy as np
import pytest

from app.services import landmarker as lm

pytestmark = pytest.mark.fast


def _raw(entries: dict[int, tuple[float, float, float, float, float]], n: int = 896):
    """Tạo (regressors, logits) với vài anchor có mặt: (dx, dy, w, h, logit) theo pixel 128."""
    reg = np.zeros((n, 16), dtype=np.float32)
    logits = np.full((n, 1), -20.0, dtype=np.float32)
    for index, (dx, dy, w, h, logit) in entries.items():
        reg[index, :4] = (dx, dy, w, h)
        # keypoint 0/1 = hai mắt: ngang, cách nhau 20 px
        reg[index, 4:8] = (-10.0, 0.0, 10.0, 0.0)
        logits[index, 0] = logit
    return reg, logits


def test_anchor_layout():
    anchors = lm.ANCHORS
    assert anchors.shape == (896, 2)
    assert anchors.min() > 0.0 and anchors.max() < 1.0
    # 16x16 ô x 2 anchor (stride 8) rồi 8x8 ô x 6 anchor (stride 16)
    assert np.allclose(anchors[0], (0.5 / 16, 0.5 / 16))
    assert np.allclose(anchors[1], anchors[0])
    assert np.allclose(anchors[2], (1.5 / 16, 0.5 / 16))
    assert np.allclose(anchors[512], (0.5 / 8, 0.5 / 8))
    assert np.allclose(anchors[512 + 6], (1.5 / 8, 0.5 / 8))


def test_decode_returns_none_below_threshold():
    reg, logits = _raw({10: (0, 0, 30, 30, -0.5)})
    assert lm.decode_detection(reg, logits) is None


def test_decode_single_detection_uses_anchor_offset():
    index = 600
    reg, logits = _raw({index: (6.4, -12.8, 32.0, 64.0, 4.0)})
    box, keypoints = lm.decode_detection(reg, logits)
    ax, ay = lm.ANCHORS[index]
    cx, cy = ax + 6.4 / 128, ay - 12.8 / 128
    assert np.allclose(box, [cx - 0.125, cy - 0.25, cx + 0.125, cy + 0.25], atol=1e-6)
    assert np.allclose(keypoints[0], [ax - 10 / 128, ay], atol=1e-6)


def test_weighted_nms_merges_overlap_and_ignores_distant_box():
    near_a, near_b, far = 600, 601, 800
    reg, logits = _raw(
        {
            near_a: (0, 0, 40, 40, 6.0),
            near_b: (0, 0, 40, 40, 6.0),
            far: (0, 0, 40, 40, 5.0),
        }
    )
    box, _ = lm.decode_detection(reg, logits)
    centres = lm.ANCHORS[[near_a, near_b]]
    expected = centres.mean(axis=0)
    got = np.array([(box[0] + box[2]) / 2, (box[1] + box[3]) / 2])
    assert np.allclose(got, expected, atol=1e-5)


def test_letterbox_keeps_aspect_ratio_and_centres():
    matrix, scale, pad_x, pad_y = lm.letterbox(640, 320)
    assert scale == pytest.approx(0.2)
    assert pad_x == pytest.approx(0.0)
    assert pad_y == pytest.approx(32.0)
    assert np.allclose(matrix @ [640, 320, 1], [128, 96])


def test_detector_input_range_and_shape():
    frame = np.full((90, 160, 3), 255, dtype=np.uint8)
    tensor, _ = lm.detector_input(frame)
    assert tensor.shape == (1, 128, 128, 3)
    assert tensor.max() == pytest.approx(1.0)
    assert tensor[0, 0, 0, 0] == pytest.approx(-1.0)  # vùng đệm


def test_roi_level_eyes_has_zero_rotation_and_scaled_side():
    box = np.array([0.25, 0.25, 0.5, 0.75])
    keypoints = np.zeros((6, 2))
    keypoints[0] = (0.4, 0.4)
    keypoints[1] = (0.6, 0.4)
    cx, cy, side, rotation = lm.roi_from_detection(box, keypoints, 1.0, 0.0, 0.0)
    assert rotation == pytest.approx(0.0, abs=1e-9)
    assert (cx, cy) == pytest.approx((0.375 * 128, 0.5 * 128))
    assert side == pytest.approx(0.5 * 128 * lm.ROI_SCALE)


def test_roi_removes_letterbox_padding():
    box = np.array([0.25, 0.25, 0.5, 0.75])
    keypoints = np.zeros((6, 2))
    keypoints[1] = (0.1, 0.0)
    cx, cy, _, _ = lm.roi_from_detection(box, keypoints, 0.2, 0.0, 32.0)
    assert cx == pytest.approx(0.375 * 128 / 0.2)
    assert cy == pytest.approx((0.5 * 128 - 32.0) / 0.2)


@pytest.mark.parametrize("rotation", [0.0, 0.4, -0.7, math.pi / 2])
def test_roi_matrix_and_projection_are_inverse(rotation):
    cx, cy, side = 300.0, 200.0, 180.0
    matrix = lm.roi_matrix(cx, cy, side, rotation)
    # tâm ROI (128,128) <-> (cx,cy)
    assert matrix @ [cx, cy, 1] == pytest.approx([128, 128], abs=1e-6)
    rng = np.random.default_rng(1)
    roi_points = rng.uniform(0, 256, size=(lm.NUM_LANDMARKS, 2))
    raw = np.concatenate([roi_points, np.zeros((lm.NUM_LANDMARKS, 1))], axis=1)
    projected = lm.project_landmarks(raw.reshape(-1), cx, cy, side, rotation)
    back = cv2.transform(projected[None].astype(np.float64), matrix)[0]
    assert np.allclose(back, roi_points, atol=2e-3)


def test_roi_rotation_follows_eye_line():
    box = np.array([0.3, 0.3, 0.7, 0.7])
    keypoints = np.zeros((6, 2))
    keypoints[0] = (0.4, 0.4)
    keypoints[1] = (0.6, 0.5)  # mắt phải thấp hơn -> mặt nghiêng
    _, _, _, rotation = lm.roi_from_detection(box, keypoints, 1.0, 0.0, 0.0)
    assert rotation == pytest.approx(math.atan2(0.1, 0.2))
