"""Runtime suy luận: pipeline 2 tầng, queue bounded, deadline, thống kê.

Thiết kế:

    CPU thread: decode -> detect -> warp 224x224   (queue MAX_QUEUE)
        -> GPU queue (1 slot)
    GPU thread: normalize -> UniGaze -> calibration -> smoothing
        -> future -> event loop

- Mỗi session chỉ có tối đa 1 frame trong pipeline (mailbox ở tầng WS), nên
  không lệch thứ tự response.
- Frame cũ hơn `FRAME_MAX_AGE_MS` bị bỏ thay vì inference, giữ p95 bounded.
- Queue đầy -> `InferenceOverloaded` ngay, không xếp hàng vô hạn.
- Mọi truy cập model/MediaPipe nằm trong đúng thread của nó (không thread-safe).
"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
import time
from collections import Counter, deque
from dataclasses import dataclass

from app.services.errors import (
    InferenceOverloaded,
    InvalidImage,
    ModelNotReady,
)
from app.services.sessions import Session
from app.settings import Settings

logger = logging.getLogger("app.gaze")

#: Cửa sổ thống kê cho percentile (số frame gần nhất).
STATS_WINDOW = 256
#: Cửa sổ thời gian để tính tỉ lệ drop cho suggestedFps.
RECENT_WINDOW_SECONDS = 5.0
#: Các lý do drop phản ánh quá tải (dùng cho suggestedFps).
OVERLOAD_REASONS = frozenset({"overload", "stale", "throttle", "timeout"})
#: Map lý do drop -> status trả client.
DROP_STATUS = {"overload": "overloaded"}


@dataclass(frozen=True)
class GazeFrame:
    """Kết quả 1 frame.

    ``status``: ok | no_face | invalid_image | stale | overloaded | error.
    Với stream, ``x``/``y`` là toạ độ viewport; ``pitch``/``yaw`` là output model.
    """

    status: str
    x: float | None = None
    y: float | None = None
    pitch: float | None = None
    yaw: float | None = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"


@dataclass
class FrameJob:
    """Một frame chờ suy luận, kèm future để trả về event loop."""

    jpeg: bytes
    received_at: float
    loop: asyncio.AbstractEventLoop
    future: asyncio.Future
    session: Session | None = None
    header: dict | None = None


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * q))
    return round(ordered[index], 2)


class RuntimeStats:
    """Counter + rolling percentile, an toàn khi đọc/ghi từ nhiều thread."""

    def __init__(self, window: int = STATS_WINDOW):
        self._lock = threading.Lock()
        self.started_at = time.time()
        self.frames_in = 0
        self.frames_inferred = 0
        self.no_face = 0
        self.dropped: Counter[str] = Counter()
        self._infer_ms: deque[float] = deque(maxlen=window)
        self._cpu_ms: deque[float] = deque(maxlen=window)
        self._gpu_ms: deque[float] = deque(maxlen=window)
        self._recent: deque[tuple[float, bool]] = deque(maxlen=512)

    def count_in(self) -> None:
        """Gọi khi frame vào hệ thống (kể cả frame sau đó bị throttle)."""
        with self._lock:
            self.frames_in += 1

    def count_drop(self, reason: str) -> None:
        with self._lock:
            self.dropped[reason] += 1
            self._recent.append(
                (time.monotonic(), reason not in OVERLOAD_REASONS)
            )

    def count_no_face(self) -> None:
        with self._lock:
            self.no_face += 1
            self._recent.append((time.monotonic(), True))

    def record(self, infer_ms: float, cpu_ms: float, gpu_ms: float) -> None:
        with self._lock:
            self.frames_inferred += 1
            self._infer_ms.append(infer_ms)
            self._cpu_ms.append(cpu_ms)
            self._gpu_ms.append(gpu_ms)
            self._recent.append((time.monotonic(), True))

    def _rates(self) -> tuple[float, float]:
        total = self.frames_in
        if total <= 0:
            return 0.0, 0.0
        dropped = sum(self.dropped.values())
        overload = sum(
            count
            for reason, count in self.dropped.items()
            if reason in OVERLOAD_REASONS
        )
        return dropped / total, overload / total

    def snapshot(self) -> dict:
        with self._lock:
            infer = list(self._infer_ms)
            cpu = list(self._cpu_ms)
            gpu = list(self._gpu_ms)
            dropped = dict(self.dropped)
            drop_rate, overload_rate = self._rates()
            return {
                "frames_in": self.frames_in,
                "frames_inferred": self.frames_inferred,
                "no_face": self.no_face,
                "dropped": dropped,
                "drop_rate": round(drop_rate, 4),
                "overload_rate": round(overload_rate, 4),
                "infer_ms": {
                    "p50": _percentile(infer, 0.50),
                    "p95": _percentile(infer, 0.95),
                },
                "cpu_ms": {
                    "p50": _percentile(cpu, 0.50),
                    "p95": _percentile(cpu, 0.95),
                },
                "gpu_ms": {
                    "p50": _percentile(gpu, 0.50),
                    "p95": _percentile(gpu, 0.95),
                },
                "uptime_s": round(time.time() - self.started_at, 1),
            }

    def suggested_fps(self, target: int) -> int:
        """FPS gợi ý theo tỉ lệ drop gần đây (client tự giảm tải)."""
        now = time.monotonic()
        with self._lock:
            recent = [
                ok for ts, ok in self._recent if now - ts <= RECENT_WINDOW_SECONDS
            ]
        if len(recent) < 10:
            return target
        drop_rate = 1.0 - (sum(recent) / len(recent))
        if drop_rate > 0.25:
            return max(5, target // 2)
        return target


class InferenceRuntime:
    """Sở hữu 2 thread suy luận và toàn bộ trạng thái model."""

    def __init__(
        self,
        settings: Settings,
        *,
        cpu_stage_factory=None,
        gpu_stage_factory=None,
    ):
        self.settings = settings
        self.stats = RuntimeStats()
        self.device = settings.device
        self.model_name = settings.unigaze_model
        self.precision = settings.precision
        self.gpu_name: str | None = None
        self.gpu_available = False

        self._cpu_factory = cpu_stage_factory
        self._gpu_factory = gpu_stage_factory
        self._cpu_stage = None
        self._gpu_stage = None

        self._cpu_q: queue.Queue = queue.Queue(maxsize=settings.max_queue)
        # 1 slot đủ để overlap CPU/GPU mà không tạo latency dài.
        self._gpu_q: queue.Queue = queue.Queue(maxsize=1)
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._cpu_thread: threading.Thread | None = None
        self._gpu_thread: threading.Thread | None = None

    # ---- Vòng đời ----

    def start(self) -> None:
        if self._ready.is_set():
            raise RuntimeError("runtime đã start")
        self.settings.validate()
        self._apply_thread_caps()

        cpu_factory = self._cpu_factory or (
            lambda: _make_cpu_stage(self.settings)
        )
        gpu_factory = self._gpu_factory or (
            lambda: _make_gpu_stage(self.settings)
        )
        self._cpu_stage = cpu_factory()
        self._gpu_stage = gpu_factory()

        self.device = str(getattr(self._gpu_stage, "device", self.settings.device))
        self.model_name = getattr(
            self._gpu_stage, "model_name", self.settings.unigaze_model
        )
        self.precision = getattr(
            self._gpu_stage, "precision", self.settings.precision
        )
        self.gpu_name = getattr(self._gpu_stage, "gpu_name", None)
        self.gpu_available = bool(getattr(self._gpu_stage, "is_cuda", False))

        _call_optional(self._cpu_stage, "warmup")
        _call_optional(self._gpu_stage, "warmup")

        self._cpu_thread = threading.Thread(
            target=self._cpu_main, name="gaze-cpu", daemon=True
        )
        self._gpu_thread = threading.Thread(
            target=self._gpu_main, name="gaze-gpu", daemon=True
        )
        self._cpu_thread.start()
        self._gpu_thread.start()
        self._ready.set()
        logger.info(
            "Runtime sẵn sàng: device=%s model=%s precision=%s gpu=%s",
            self.device,
            self.model_name,
            self.precision,
            self.gpu_name or "-",
        )

    def close(self) -> None:
        if not self._ready.is_set():
            return
        self._stop.set()
        for q in (self._cpu_q, self._gpu_q):
            try:
                q.put_nowait(None)
            except queue.Full:
                pass
        for thread in (self._cpu_thread, self._gpu_thread):
            if thread is not None:
                thread.join(timeout=2.0)
        self._ready.clear()

    def pipeline_ready(self) -> bool:
        return self._ready.is_set()

    # ---- API cho tầng HTTP/WS ----

    def new_job(
        self,
        *,
        jpeg: bytes,
        session: Session | None = None,
        header: dict | None = None,
    ) -> FrameJob:
        loop = asyncio.get_running_loop()
        return FrameJob(
            jpeg=jpeg,
            received_at=time.monotonic(),
            loop=loop,
            future=loop.create_future(),
            session=session,
            header=header,
        )

    async def submit(self, job: FrameJob) -> GazeFrame:
        """Đưa frame vào pipeline và chờ kết quả.

        Caller chịu trách nhiệm `stats.count_in()` khi frame vào hệ thống.
        """
        if not self._ready.is_set():
            raise ModelNotReady("pipeline chưa sẵn sàng")
        try:
            self._cpu_q.put_nowait(job)
        except queue.Full as exc:
            self.stats.count_drop("overload")
            raise InferenceOverloaded("inference queue full") from exc
        try:
            return await asyncio.wait_for(
                job.future, timeout=self.settings.inference_timeout_s
            )
        except asyncio.TimeoutError:
            self.stats.count_drop("timeout")
            return GazeFrame("error")

    def suggested_fps(self) -> int:
        return self.stats.suggested_fps(self.settings.gaze_fps)

    def snapshot(self) -> dict:
        return {
            "status": "ok" if self._ready.is_set() else "degraded",
            "pipeline_ready": self._ready.is_set(),
            "device": self.device,
            "model": self.model_name,
            "precision": self.precision,
            "gpu_available": self.gpu_available,
            "gpu_name": self.gpu_name,
            "queue": {
                "cpu": self._cpu_q.qsize(),
                "gpu": self._gpu_q.qsize(),
            },
            "stats": self.stats.snapshot(),
        }

    # ---- Thread loops ----

    def _cpu_main(self) -> None:
        while not self._stop.is_set():
            try:
                job = self._cpu_q.get(timeout=0.2)
            except queue.Empty:
                continue
            if job is None:
                break
            self._process_cpu(job)

    def _process_cpu(self, job: FrameJob) -> None:
        if self._is_stale(job):
            self._finish_drop(job, "stale")
            return

        started = time.perf_counter()
        try:
            prepared = self._cpu_stage.prepare(job.jpeg)
        except InvalidImage:
            self._finish_drop(job, "invalid_image")
            return
        except Exception:  # lỗi 1 frame không được làm chết thread
            logger.exception("CPU stage lỗi")
            self._finish_drop(job, "error")
            return
        cpu_ms = (time.perf_counter() - started) * 1000.0

        if prepared is None:
            self.stats.count_no_face()
            self._settle(job, GazeFrame("no_face"))
            return

        try:
            self._gpu_q.put(
                (job, prepared, cpu_ms), timeout=self.settings.frame_max_age_s
            )
        except queue.Full:
            self._finish_drop(job, "overload")

    def _gpu_main(self) -> None:
        while not self._stop.is_set():
            try:
                item = self._gpu_q.get(timeout=0.2)
            except queue.Empty:
                continue
            if item is None:
                break
            job, prepared, cpu_ms = item
            self._process_gpu(job, prepared, cpu_ms)

    def _process_gpu(self, job: FrameJob, prepared, cpu_ms: float) -> None:
        if self._is_stale(job):
            self._finish_drop(job, "stale")
            return

        started = time.perf_counter()
        try:
            pitch, yaw = self._gpu_stage.predict(prepared)
        except Exception:
            logger.exception("GPU stage lỗi")
            self._finish_drop(job, "error")
            return
        gpu_ms = (time.perf_counter() - started) * 1000.0

        if job.session is None:
            result = GazeFrame("ok", pitch=pitch, yaw=yaw)
        else:
            try:
                x, y = job.session.calib.predict(pitch, yaw)
                x, y = job.session.smoother.process(
                    [x, y], timestamp=job.received_at
                )
            except Exception:
                logger.exception("Calibration/smoothing lỗi")
                self._finish_drop(job, "error")
                return
            result = GazeFrame("ok", x=x, y=y, pitch=pitch, yaw=yaw)

        self.stats.record(cpu_ms + gpu_ms, cpu_ms, gpu_ms)
        self._settle(job, result)

    # ---- Helpers ----

    def _is_stale(self, job: FrameJob) -> bool:
        return time.monotonic() - job.received_at > self.settings.frame_max_age_s

    def _finish_drop(self, job: FrameJob, reason: str) -> None:
        self.stats.count_drop(reason)
        self._settle(job, GazeFrame(DROP_STATUS.get(reason, reason)))

    def _settle(self, job: FrameJob, result: GazeFrame) -> None:
        def _set() -> None:
            if not job.future.done():
                job.future.set_result(result)

        try:
            job.loop.call_soon_threadsafe(_set)
        except RuntimeError:
            # Event loop đã đóng (shutdown); bỏ kết quả.
            pass

    @staticmethod
    def _apply_thread_caps() -> None:
        """Cap thread trước khi load model.

        Container bị giới hạn CPU (vd 2 core) nhưng OpenCV/torch vẫn thấy toàn
        bộ core của host; oversubscription gây throttling và stall ~80ms/frame.
        """
        try:
            import cv2

            cv2.setNumThreads(1)
        except Exception:  # test không cài cv2
            logger.debug("Không cap được OpenCV threads", exc_info=True)
        try:
            import torch

            torch.set_num_threads(1)
            torch.backends.cudnn.benchmark = True
        except Exception:  # test không cài torch
            logger.debug("Không cap được torch threads", exc_info=True)


def _call_optional(stage, method: str) -> None:
    fn = getattr(stage, method, None)
    if callable(fn):
        fn()


def _make_cpu_stage(settings: Settings):
    from app.services.pipeline import CpuStage

    return CpuStage(settings)


def _make_gpu_stage(settings: Settings):
    from app.services.pipeline import GpuStage

    return GpuStage(settings)
