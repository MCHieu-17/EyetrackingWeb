"""Ánh xạ (pitch, yaw) -> (x, y) chuẩn hóa bằng hồi quy tuyến tính (numpy).

Thay vì lưu cả object `sklearn.LinearRegression` bằng `pickle` (rủi ro RCE khi
nhận file từ client), model được serialize thuần dưới dạng hệ số:

    x = a1 * pitch + a2 * yaw + b1
    y = a3 * pitch + a4 * yaw + b2

Format `.ubj` v2:
    {"format": "gaze-lr-v2", "coef": [[a1, a3], [a2, a4]], "intercept": [b1, b2]}

`coef` xếp sao cho `coef @ [pitch, yaw] + intercept` ra `[x, y]`. Không có
`pickle`, không cần scikit-learn ở đường predict.

Model được giữ trong một object bất biến và hoán đổi nguyên tử, nhờ đó thread
suy luận luôn đọc được cặp (coef, intercept) nhất quán khi `/train` hoặc
`/import` chạy song song.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import ubjson

FORMAT = "gaze-lr-v2"


@dataclass(frozen=True)
class LinearModel:
    coef: np.ndarray  # shape (2, 2)
    intercept: np.ndarray  # shape (2,)


class Calibration:
    def __init__(self):
        self._model: LinearModel | None = None

    @property
    def ready(self) -> bool:
        return self._model is not None

    # Fit / predict
    def fit(self, x, y) -> None:
        """Fit bình phương nhỏ nhất từ mẫu (X: Nx2, y: Nx2)."""
        x = np.asarray(x, dtype=float).reshape(-1, 2)
        y = np.asarray(y, dtype=float).reshape(-1, 2)
        if len(x) == 0:
            raise ValueError("cần ít nhất 1 mẫu để fit")
        design = np.hstack([x, np.ones((len(x), 1))])
        sol, *_ = np.linalg.lstsq(design, y, rcond=None)  # (3, 2)
        self._model = LinearModel(coef=sol[:2].T, intercept=sol[2])

    def predict(self, pitch: float, yaw: float) -> tuple[float, float]:
        model = self._model
        if model is None:
            raise RuntimeError("model chưa được train/import")
        point = model.coef @ np.array([pitch, yaw], dtype=float) + model.intercept
        return float(point[0]), float(point[1])

    # Serialize (ubjson v2, không pickle)
    def serialize(self) -> bytes:
        model = self._model
        if model is None:
            raise RuntimeError("model chưa được train")
        return ubjson.dumpb(
            {
                "format": FORMAT,
                "coef": model.coef.tolist(),
                "intercept": model.intercept.tolist(),
            }
        )

    def deserialize(self, data: bytes) -> None:
        """Nạp model từ bytes .ubj v2. Sai format/shape -> ValueError.

        KHÔNG dùng pickle: dữ liệu từ client chỉ được đọc như số.
        """
        if not isinstance(data, (bytes, bytearray)) or not data:
            raise ValueError("model rỗng")
        try:
            obj = ubjson.loadb(bytes(data))
        except Exception as exc:  # ubjson ValueError / TypeError
            raise ValueError("không parse được model .ubj") from exc
        if not isinstance(obj, dict) or obj.get("format") != FORMAT:
            raise ValueError("format model không được hỗ trợ")

        coef = np.asarray(obj.get("coef"), dtype=float)
        intercept = np.asarray(obj.get("intercept"), dtype=float)
        if coef.shape != (2, 2) or intercept.shape != (2,):
            raise ValueError("shape model không hợp lệ")
        if not (np.all(np.isfinite(coef)) and np.all(np.isfinite(intercept))):
            raise ValueError("model chứa giá trị không hợp lệ")

        self._model = LinearModel(coef=coef, intercept=intercept)
