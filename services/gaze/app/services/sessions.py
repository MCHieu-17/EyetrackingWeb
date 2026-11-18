"""Session calibration trong RAM + quản lý vòng đời (TTL, giới hạn số session).

Truy cập được bảo vệ bằng `RLock` vì endpoint sync (chạy trong threadpool) và
endpoint async (chạy trên event loop) cùng đọc/ghi `SessionManager`.

Calibration và smoother của mỗi session chỉ được ghi từ endpoint HTTP và đọc
từ thread GPU; `Calibration` hoán đổi model nguyên tử nên không cần khoá riêng.
"""

from __future__ import annotations

import threading
import time
import uuid
from enum import Enum

from app.services.calibration import Calibration
from app.services.smoothing import OneEuroFilter2D
from app.settings import Settings


class SessionState(str, Enum):
    COLLECTING = "collecting"
    READY = "ready"


class Session:
    def __init__(self, points, settings: Settings):
        self.points = points  # dict id -> (x, y)
        # point_id -> [[pitch, yaw, x, y], ...]
        self.samples: dict[str, list[list[float]]] = {}
        self.calib = Calibration()
        self.smoother = OneEuroFilter2D(
            min_cutoff=settings.oneeuro_min_cutoff,
            beta=settings.oneeuro_beta,
            d_cutoff=settings.oneeuro_d_cutoff,
        )
        self.state = SessionState.COLLECTING
        self.last_active = time.monotonic()
        self.last_frame_at = 0.0  # throttle FPS per session
        self._max_samples = settings.max_samples_per_point

    def add_sample(self, point_id: str, pitch: float, yaw: float) -> int:
        """Thêm 1 mẫu cho điểm; giữ tối đa `max_samples_per_point` mẫu mới nhất."""
        buf = self.samples.setdefault(point_id, [])
        x, y = self.points[point_id]
        buf.append([pitch, yaw, x, y])
        if len(buf) > self._max_samples:
            del buf[: len(buf) - self._max_samples]
        return len(buf)

    def mark_ready(self) -> None:
        self.state = SessionState.READY
        self.smoother.reset()

    @property
    def ready(self) -> bool:
        return self.state is SessionState.READY


class SessionManager:
    def __init__(self, settings: Settings):
        self._sessions: dict[str, Session] = {}
        self._lock = threading.RLock()
        self._settings = settings
        self.ttl = settings.session_ttl_seconds
        self.max = settings.max_sessions

    def create(self, points) -> str:
        with self._lock:
            self._cleanup_locked()  # dọn slot hết hạn trước khi check capacity
            if len(self._sessions) >= self.max:
                raise RuntimeError("too many sessions")
            sid = str(uuid.uuid4())
            self._sessions[sid] = Session(points, self._settings)
            return sid

    def get(self, sid: str) -> Session | None:
        with self._lock:
            session = self._sessions.get(sid)
            if session is not None:
                session.last_active = time.monotonic()
            return session

    def delete(self, sid: str) -> Session | None:
        with self._lock:
            return self._sessions.pop(sid, None)

    def count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def stats(self) -> dict:
        with self._lock:
            total = len(self._sessions)
            ready = sum(1 for session in self._sessions.values() if session.ready)
        return {"total": total, "ready": ready}

    def cleanup_expired(self) -> None:
        with self._lock:
            self._cleanup_locked()

    def _cleanup_locked(self) -> None:
        now = time.monotonic()
        expired = [
            sid
            for sid, session in self._sessions.items()
            if now - session.last_active > self.ttl
        ]
        for sid in expired:
            self._sessions.pop(sid, None)
