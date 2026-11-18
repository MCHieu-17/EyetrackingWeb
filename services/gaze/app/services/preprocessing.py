"""Chuẩn hoá khuôn mặt (alignment kiểu Zhang) trước khi đưa vào UniGaze.

Quy trình: crop mặt -> solvePnP 6 điểm -> chuẩn hoá phối cảnh về 224x224.

Trả về ảnh RGB uint8 đã warp; việc chuyển tensor/normalize nằm ở tầng GPU
(`app/services/pipeline.py`) để không tạo overhead PIL mỗi frame.

Việc làm mượt POG nằm ở `app/services/smoothing.py`.
"""

from __future__ import annotations

import cv2
import numpy as np

# Kích thước input UniGaze (ViT patch 16 -> 14x14 patch).
ROI_SIZE = (224, 224)


def estimate_head_pose(landmarks, face_model, camera, distortion):
    """Ước lượng rvec/tvec từ 6 điểm mốc; refine 1 lần cho ổn định."""
    _, rvec, tvec = cv2.solvePnP(
        face_model, landmarks, camera, distortion, flags=cv2.SOLVEPNP_EPNP
    )
    _, rvec, tvec = cv2.solvePnP(
        face_model, landmarks, camera, distortion, rvec, tvec, True
    )
    return rvec, tvec


def get_face_center_by_nose(hR, ht, face_model):
    """Tâm mặt trong hệ toạ độ camera (trung bình 2 mắt + chóp mũi)."""
    fc = np.dot(hR, face_model.T) + ht
    eye_center = np.mean(fc[:, 0:2], axis=1).reshape(3, 1)
    nose_center = fc[:, 2:3]
    return np.mean(
        np.concatenate((eye_center, nose_center), axis=1), axis=1
    ).reshape(3, 1)


def normalize_image(img, focal_norm, distance_norm, roi_size, center, hr, cam):
    """Warp mặt về ROI chuẩn (224x224) theo pose đầu."""
    hR = cv2.Rodrigues(hr)[0]
    distance = np.linalg.norm(center)
    z_scale = distance_norm / distance
    cam_norm = np.array(
        [
            [focal_norm, 0, roi_size[0] / 2],
            [0, focal_norm, roi_size[1] / 2],
            [0, 0, 1.0],
        ]
    )
    s = np.diag([1.0, 1.0, z_scale])

    h_rx = hR[:, 0]
    forward = (center / distance).reshape(3)
    down = np.cross(forward, h_rx)
    down /= np.linalg.norm(down)
    right = np.cross(down, forward)
    right /= np.linalg.norm(right)
    rotation = np.c_[right, down, forward].T
    warp = cam_norm @ s @ rotation @ np.linalg.inv(cam)

    return cv2.warpPerspective(img, warp, roi_size), rotation @ hR


class Preprocessor:
    """Chuẩn hoá mặt về 224x224 RGB uint8, kiểm tra biên tư thế đầu."""

    def __init__(
        self,
        focal_norm: float = 960,
        distance_norm: float = 600,
        roi_size: tuple[int, int] = ROI_SIZE,
        max_head_pose_deg: float = 80,
    ):
        self.focal_norm = focal_norm
        self.distance_norm = distance_norm
        self.roi_size = roi_size
        self.max_head_pose = max_head_pose_deg * np.pi / 180

        # 3D face model cho 6 điểm mediapipe, đã hiệu chỉnh convention trục
        # (đảo x, z) để khớp giao thức chuẩn hoá Zhang.
        self.face_model = np.array(
            [
                [-30.0, -30.0, 20.0],  # 1. Mắt phải
                [30.0, -30.0, 20.0],   # 2. Mắt trái
                [0.0, 0.0, 0.0],       # 3. Chóp mũi
                [0.0, 30.0, 15.0],     # 4. Tâm miệng
                [-75.0, 0.0, 80.0],    # 5. Tai phải
                [75.0, 0.0, 80.0],     # 6. Tai trái
            ],
            dtype=np.float64,
        )
        self.face_pts = self.face_model.reshape(6, 1, 3)

    @staticmethod
    def _dummy_camera(face):
        h, w = face.shape[:2]
        focal = w * 4
        cam = np.array(
            [[focal, 0, w // 2], [0, focal, h // 2], [0, 0, 1]], dtype="double"
        )
        return cam, np.zeros((1, 5))

    def process(self, face, landmarks):
        """face: RGB crop; landmarks: 6 điểm trong hệ ảnh crop.

        Trả về ảnh RGB uint8 224x224 hoặc None nếu tư thế đầu vượt ngưỡng.
        """
        lm = np.asarray(landmarks, dtype=np.float64)
        if lm.shape[0] != 6:
            return None

        cam, dist = self._dummy_camera(face)
        hr, ht = estimate_head_pose(
            lm.reshape(6, 1, 2), self.face_pts, cam, dist
        )
        h_r = cv2.Rodrigues(hr)[0]
        face_center = get_face_center_by_nose(h_r, ht, self.face_model)

        img_norm, h_r_norm = normalize_image(
            face,
            self.focal_norm,
            self.distance_norm,
            self.roi_size,
            face_center,
            hr,
            cam,
        )
        head_pose = np.array(
            [
                np.arcsin(np.clip(h_r_norm[1, 2], -1.0, 1.0)),
                np.arctan2(h_r_norm[0, 2], h_r_norm[2, 2]),
            ]
        )
        if np.linalg.norm(head_pose) > self.max_head_pose:
            return None
        return img_norm
