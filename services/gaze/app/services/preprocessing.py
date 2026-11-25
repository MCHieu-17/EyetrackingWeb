"""Chuẩn hoá khuôn mặt (alignment kiểu Zhang) trước khi đưa vào UniGaze.

Quy trình: crop mặt -> solvePnP 6 điểm (4 góc mắt + 2 cánh mũi) -> chuẩn hoá
phối cảnh về 224x224. Face model và thứ tự điểm theo unigaze/research.

Trả về ảnh RGB uint8 đã warp cùng ma trận xoay `R` của camera ảo; `R` cần để
denormalize gaze về hệ camera thật (`gaze_geometry.denormalize_gaze`). Việc
chuyển tensor/normalize nằm ở tầng GPU (`app/services/pipeline.py`).

Việc làm mượt POG nằm ở `app/services/smoothing.py`.
"""

from __future__ import annotations

import cv2
import numpy as np

# Kích thước input UniGaze (ViT patch 16 -> 14x14 patch).
ROI_SIZE = (224, 224)

# Số điểm mốc dùng cho solvePnP: 4 góc mắt + 2 cánh mũi.
N_EYE = 4
N_NOSE = 2


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
    """Tâm mặt trong hệ toạ độ camera (trung bình tâm mắt và tâm mũi)."""
    fc = np.dot(hR, face_model.T) + ht
    eye_center = np.mean(fc[:, :N_EYE], axis=1).reshape(3, 1)
    nose_center = np.mean(fc[:, N_EYE : N_EYE + N_NOSE], axis=1).reshape(3, 1)
    return np.mean(
        np.concatenate((eye_center, nose_center), axis=1), axis=1
    ).reshape(3, 1)


def normalize_image(img, focal_norm, distance_norm, roi_size, center, hr, cam):
    """Warp mặt về ROI chuẩn (224x224) theo pose đầu -> (ảnh, R, hR_norm)."""
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

    forward = (center / distance).reshape(3)
    down = np.cross(forward, hR[:, 0])
    down /= np.linalg.norm(down)
    right = np.cross(down, forward)
    right /= np.linalg.norm(right)
    rotation = np.c_[right, down, forward].T
    warp = cam_norm @ s @ rotation @ np.linalg.inv(cam)

    return cv2.warpPerspective(img, warp, roi_size), rotation, rotation @ hR


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

        # 6 điểm chuẩn của UniGaze (rows [20, 23, 26, 29, 15, 19] của
        # unigaze/data/face_model.txt): 4 góc mắt + 2 cánh mũi.
        self.face_model = np.array(
            [
                [-46.509, -38.327, 36.416],  # góc ngoài mắt phải
                [-17.761, -32.585, 29.076],  # góc trong mắt phải
                [18.044, -30.957, 29.063],  # góc trong mắt trái
                [44.738, -34.108, 36.732],  # góc ngoài mắt trái
                [-10.612, 12.958, 21.623],  # cánh mũi phải
                [11.289, 13.864, 21.840],  # cánh mũi trái
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

        Trả về (ảnh RGB uint8 224x224, R) hoặc None nếu tư thế đầu vượt ngưỡng.
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

        img_norm, rotation, h_r_norm = normalize_image(
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
        return img_norm, rotation
