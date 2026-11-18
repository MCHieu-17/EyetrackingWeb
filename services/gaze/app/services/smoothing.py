"""Bộ lọc làm mượt One-Euro cho tọa độ điểm nhìn (POG).

Tách riêng khỏi `preprocessing.py` để không phải kéo theo numpy/torchvision/opencv
khi chỉ cần làm mượt — nhờ đó test nhẹ và module độc lập.
"""

from __future__ import annotations

import time

import numpy as np


class OneEuroFilter2D:
    """One-Euro filter cho tín hiệu 2 chiều (x, y) chuẩn hóa.

    Tham số mặc định phù hợp tọa độ [0, 1] và có thể chỉnh qua biến môi trường
    (xem ``app.settings.Settings.oneeuro_*``):

    - ``min_cutoff``: cutoff khi đứng yên — thấp để giảm rung, cao để bớt trễ.
    - ``beta``: độ nhạy theo tốc độ — càng cao càng bám nhanh khi lia mắt.
    - ``d_cutoff``: cutoff làm mượt vận tốc — cao hơn để thích ứng nhanh hơn.
    """

    #: Khoảng nghỉ tối đa (giây). Lớn hơn -> reset thay vì trộn với vị trí cũ.
    MAX_GAP_SECONDS = 1.0

    def __init__(self, min_cutoff=0.5, beta=0.5, d_cutoff=1.0):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.x_prev: np.ndarray | None = None
        self.dx_prev = np.zeros(2)
        self.t_prev: float | None = None

    @staticmethod
    def _alpha(dt: float, cutoff: float) -> float:
        return 1.0 / (1.0 + (1.0 / (2 * np.pi * cutoff)) / dt)

    def reset(self, coord=None, timestamp: float | None = None) -> None:
        self.dx_prev = np.zeros(2)
        if coord is None:
            self.x_prev = None
            self.t_prev = None
            return
        self.x_prev = np.asarray(coord, dtype=float)
        self.t_prev = time.monotonic() if timestamp is None else timestamp

    def process(self, coord, timestamp: float | None = None):
        """Nhận [x, y], trả về [x, y] đã làm mượt.

        ``timestamp`` nên là thời điểm capture (monotonic, giây) để dt không bị
        méo khi frame xếp hàng; bỏ trống thì dùng thời điểm hiện tại.
        """
        coord_np = np.asarray(coord, dtype=float)
        t = time.monotonic() if timestamp is None else timestamp

        if (
            self.x_prev is None
            or self.t_prev is None
            or t - self.t_prev > self.MAX_GAP_SECONDS
        ):
            self.reset(coord_np, t)
            return coord_np.tolist()

        dt = t - self.t_prev
        if dt <= 0:
            return self.x_prev.tolist()

        # 1. Vận tốc (làm mượt với cutoff riêng `d_cutoff`)
        dx = (coord_np - self.x_prev) / dt
        a_d = self._alpha(dt, self.d_cutoff)
        self.dx_prev = a_d * dx + (1 - a_d) * self.dx_prev

        # 2. Cường độ lọc phụ thuộc tốc độ
        velocity = float(np.linalg.norm(self.dx_prev))
        cutoff = self.min_cutoff + self.beta * velocity
        a = self._alpha(dt, cutoff)

        # 3. Lọc và cập nhật
        self.x_prev = a * coord_np + (1 - a) * self.x_prev
        self.t_prev = t
        return self.x_prev.tolist()
