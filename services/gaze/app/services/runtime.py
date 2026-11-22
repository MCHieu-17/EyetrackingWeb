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

    jpeg: bytes | memoryview
    received_at: float
    loop: asyncio.AbstractEventLoop
    future: asyncio.Future
    session: Session | None = None
    header: dict | None = None
    #: True khi caller đã timeout; CPU/GPU thread bỏ qua thay vì suy luận.
    cancelled: bool = False


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
        # EMA theo bucket 1 giây cho suggestedFps; tránh scan 512 entry/frame.
        self._ema_ok = 1.0
        self._bucket_started = time.monotonic()
        self._bucket_ok = 0
        self._bucket_total = 0
        self._events = 0

    def count_in(self) -> None:
        """Gọi khi frame vào hệ thống (kể cả frame sau đó bị throttle)."""
        with self._lock:
            self.frames_in += 1

    def _roll_bucket(self, now: float) -> None:
        elapsed = now - self._bucket_started
        if elapsed < 1.0:
            return
        if self._bucket_total:
            rate = self._bucket_ok / self._bucket_total
        else:
            rate = self._ema_ok
        alpha = min(1.0, elapsed / RECENT_WINDOW_SECONDS)
        self._ema_ok += alpha * (rate - self._ema_ok)
        self._bucket_started = now
        self._bucket_ok = 0
        self._bucket_total = 0

    def _mark(self, ok: bool) -> None:
        now = time.monotonic()
        self._roll_bucket(now)
        self._events += 1
        self._bucket_total += 1
        if ok:
            self._bucket_ok += 1

    def count_drop(self, reason: str) -> None:
        with self._lock:
            self.dropped[reason] += 1
            self._mark(reason not in OVERLOAD_REASONS)

    def count_no_face(self) -> None:
        with self._lock:
            self.no_face += 1
            self._mark(True)

    def record(self, infer_ms: float, cpu_ms: float, gpu_ms: float) -> None:
        with self._lock:
            self.frames_inferred += 1
            self._infer_ms.append(infer_ms)
            self._cpu_ms.append(cpu_ms)
            self._gpu_ms.append(gpu_ms)
            self._mark(True)

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
        with self._lock:
            self._roll_bucket(time.monotonic())
            if self._events < 10:
                return target
            drop_rate = 1.0 - self._ema_ok
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
        # Queue đủ sâu để gom batch xuyên session; mỗi session vẫn tối đa 1 frame
        # in-flight ở tầng WS nên batch bị chặn tự nhiên theo số session.
        self._gpu_q: queue.Queue = queue.Queue(maxsize=settings.gpu_queue)
        self._gpu_batch = settings.gpu_batch
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
        jpeg: bytes | memoryview,
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
            job.cancelled = True
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
        if job.cancelled:
            return
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

        if job.cancelled:
            return
        try:
            # Không block CPU thread chờ GPU: queue đầy thì frame đã quá cũ để
            # hữu ích, trả overloaded ngay thay vì làm cả hàng đợi già đi.
            self._gpu_q.put_nowait((job, prepared, cpu_ms))
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

            batch = [item]
            stop_after = False
            while len(batch) < self._gpu_batch:
                try:
                    nxt = self._gpu_q.get_nowait()
                except queue.Empty:
                    break
                if nxt is None:
                    stop_after = True
                    break
                batch.append(nxt)
            self._process_gpu_batch(batch)
            if stop_after:
                break

    def _process_gpu_batch(self, batch: list[tuple]) -> None:
        live: list[tuple[FrameJob, object, float]] = []
        for job, prepared, cpu_ms in batch:
            if job.cancelled:
                continue
            if self._is_stale(job):
                self._finish_drop(job, "stale")
                continue
            live.append((job, prepared, cpu_ms))
        if not live:
            return

        started = time.perf_counter()
        try:
            predictions = self._predict_batch([item[1] for item in live])
        except Exception:
            logger.exception("GPU stage lỗi")
            for job, _, _ in live:
                self._finish_drop(job, "error")
            return
        batch_ms = (time.perf_counter() - started) * 1000.0
        if len(predictions) != len(live):
            logger.error(
                "GPU trả %d kết quả cho batch %d", len(predictions), len(live)
            )
            for job, _, _ in live:
                self._finish_drop(job, "error")
            return
        gpu_ms = batch_ms / len(live)

        for (job, _, cpu_ms), (pitch, yaw) in zip(live, predictions):
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
                    continue
                result = GazeFrame("ok", x=x, y=y, pitch=pitch, yaw=yaw)

            self.stats.record(cpu_ms + gpu_ms, cpu_ms, gpu_ms)
            self._settle(job, result)

    def _predict_batch(self, prepareds: list) -> list[tuple[float, float]]:
        fn = getattr(self._gpu_stage, "predict_batch", None)
        if callable(fn):
            return fn(prepareds)
        # Stage giả/test cũ chỉ có predict đơn.
        return [self._gpu_stage.predict(prepared) for prepared in prepareds]

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
