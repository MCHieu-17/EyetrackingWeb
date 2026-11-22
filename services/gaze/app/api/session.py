"""Session calibration + streaming gaze (HTTP + WebSocket).

Vòng đời 4 bước:
    POST /session                  -> tạo session, khai báo N điểm
    POST /session/{sid}/calibrate  -> thu 1 mẫu cho 1 điểm
    POST /session/{sid}/train      -> fit hồi quy tuyến tính
    WS   /session/{sid}/stream     -> streaming gaze

Model đã train có thể tải về (/model) và nạp lại (/import, format .ubj v2) để
khỏi calibration lại.

WebSocket dùng mô hình mailbox `maxsize=1`: receiver đọc frame liên tục và giữ
frame mới nhất, processor lấy frame đó đưa vào pipeline. Nhờ vậy khi GPU chậm,
frame cũ bị thay thế thay vì xếp hàng làm tăng latency.
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import suppress

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, WebSocket
from fastapi.responses import JSONResponse, Response

from app.protocol import apply_header_echo, parse_frame
from app.schemas import (
    CalibrateResult,
    DeletedResult,
    ImportResult,
    InsufficientSamples,
    SessionCreated,
    SessionRequest,
    SessionStatus,
    TrainResult,
)
from app.services.errors import InferenceOverloaded, ModelNotReady
from app.services.runtime import FrameJob, GazeFrame, InferenceRuntime
from app.services.sessions import SessionManager
from app.settings import Settings

logger = logging.getLogger("app.gaze")

router = APIRouter(tags=["session"])

settings = Settings.from_env()
sessions = SessionManager(settings)
runtime = InferenceRuntime(settings)


def _get_or_404(sid: str):
    session = sessions.get(sid)
    if session is None:
        raise HTTPException(404, "session not found")
    return session


async def _read_limited(upload: UploadFile, limit: int | None = None) -> bytes:
    """Đọc tối đa `limit` bytes; vượt -> 413 (không nạp cả file khổng lồ vào RAM)."""
    limit = settings.max_upload_bytes if limit is None else limit
    data = await upload.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, "file quá lớn")
    return data


def _put_latest(mailbox: asyncio.Queue, job: FrameJob | None) -> None:
    """Đặt job vào mailbox 1 slot; frame cũ hơn bị thay thế (freshness)."""
    try:
        mailbox.put_nowait(job)
        return
    except asyncio.QueueFull:
        pass
    with suppress(asyncio.QueueEmpty):
        old = mailbox.get_nowait()
        if isinstance(old, FrameJob):
            runtime.stats.count_drop("superseded")
    with suppress(asyncio.QueueFull):
        mailbox.put_nowait(job)


def _ws_payload(job: FrameJob, result: GazeFrame) -> dict:
    payload: dict = {"ok": result.ok, "status": result.status}
    if result.ok:
        payload["x"] = result.x
        payload["y"] = result.y
    else:
        payload["error"] = result.status
    if result.status in {"overloaded", "stale"}:
        payload["suggestedFps"] = runtime.suggested_fps()
    return apply_header_echo(payload, job.header)


@router.get("/session/{sid}", response_model=SessionStatus)
def session_status(sid: str):
    session = _get_or_404(sid)
    return SessionStatus(state=session.state.value, calibrated=session.ready)


@router.post("/session", response_model=SessionCreated)
def create_session(req: SessionRequest):
    if len(req.points) > settings.max_points:
        raise HTTPException(
            422, f"tối đa {settings.max_points} điểm calibration"
        )
    points = {p.id: (p.x, p.y) for p in req.points}
    try:
        sid = sessions.create(points)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    return SessionCreated(session_id=sid)


@router.delete("/session/{sid}", response_model=DeletedResult)
def delete_session(sid: str):
    if sessions.delete(sid) is None:
        raise HTTPException(404, "session not found")
    return DeletedResult()


@router.post("/session/{sid}/calibrate", response_model=CalibrateResult)
async def calibrate(sid: str, image: UploadFile = File(...), point_id: str = Form(...)):
    session = _get_or_404(sid)
    if point_id not in session.points:
        return CalibrateResult(status="unknown_point")
    if not runtime.pipeline_ready():
        raise HTTPException(503, "pipeline chưa sẵn sàng")

    data = await _read_limited(image)
    runtime.stats.count_in()
    try:
        result = await runtime.submit(runtime.new_job(jpeg=data))
    except InferenceOverloaded:
        raise HTTPException(
            503, "inference overloaded", headers={"Retry-After": "1"}
        )
    except ModelNotReady:
        raise HTTPException(503, "pipeline chưa sẵn sàng")

    if result.status == "invalid_image":
        return CalibrateResult(status="invalid_image")
    if result.status == "no_face":
        return CalibrateResult(status="no_face")
    if not result.ok or result.pitch is None or result.yaw is None:
        raise HTTPException(
            503, "inference failed", headers={"Retry-After": "1"}
        )

    count = session.add_sample(point_id, result.pitch, result.yaw)
    return CalibrateResult(status="accepted", count=count)


@router.post(
    "/session/{sid}/train",
    response_model=TrainResult,
    responses={422: {"model": InsufficientSamples}},
)
def train(sid: str):
    session = _get_or_404(sid)

    missing = {pid: len(session.samples.get(pid, [])) for pid in session.points}
    bad = {pid: n for pid, n in missing.items() if n < settings.min_samples}
    if bad:  # bảo đảm đủ N điểm × K mẫu
        return JSONResponse(
            InsufficientSamples(detail=bad).model_dump(), status_code=422
        )

    x = [m[:2] for ms in session.samples.values() for m in ms]
    y = [m[2:] for ms in session.samples.values() for m in ms]
    session.calib.fit(x, y)
    session.mark_ready()
    logger.info("Train xong sid=%s n_samples=%d", sid, len(x))
    return TrainResult(n_samples=len(x))


@router.get("/session/{sid}/model")
def download_model(sid: str):
    session = _get_or_404(sid)
    if not session.ready:
        raise HTTPException(409, "not calibrated")
    return Response(
        session.calib.serialize(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="calibration_{sid}.ubj"'
        },
    )


@router.post("/session/{sid}/import", response_model=ImportResult)
async def import_model(sid: str, model: UploadFile = File(...)):
    session = _get_or_404(sid)
    try:
        session.calib.deserialize(await _read_limited(model))
    except (ValueError, KeyError, TypeError):
        return ImportResult(status="invalid_model")
    session.mark_ready()  # bỏ qua calibration
    return ImportResult(status="ready")


@router.websocket("/session/{sid}/stream")
async def stream(ws: WebSocket, sid: str):
    await ws.accept()
    session = sessions.get(sid)
    if session is None or not session.ready:
        # accept() trước để client nhận đúng close code (không phải HTTP 403).
        await ws.close(code=1008, reason="not_calibrated")
        return
    if not runtime.pipeline_ready():
        await ws.close(code=1013, reason="pipeline_not_ready")
        return

    mailbox: asyncio.Queue[FrameJob | None] = asyncio.Queue(maxsize=1)
    send_q: asyncio.Queue[dict | None] = asyncio.Queue(maxsize=8)

    async def receive_loop() -> None:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                _put_latest(mailbox, None)
                return
            data = msg.get("bytes")
            if data is None:
                continue

            runtime.stats.count_in()
            now = time.monotonic()
            sessions.touch(sid)

            # Chỉ frame parse hợp lệ mới được tính vào cửa sổ throttle; frame
            # hỏng không được "ăn" slot của frame kế tiếp.
            header, jpeg = parse_frame(data)
            if not jpeg or len(jpeg) > settings.max_frame_bytes:
                runtime.stats.count_drop("invalid_image")
                continue
            if now - session.last_frame_at < settings.min_frame_interval_s:
                runtime.stats.count_drop("throttle")
                continue
            session.last_frame_at = now
            _put_latest(
                mailbox,
                runtime.new_job(jpeg=jpeg, session=session, header=header),
            )

    async def process_loop() -> None:
        while True:
            job = await mailbox.get()
            if job is None:
                await send_q.put(None)
                return
            if time.monotonic() - job.received_at > settings.frame_max_age_s:
                runtime.stats.count_drop("stale")
                await send_q.put(_ws_payload(job, GazeFrame("stale")))
                continue
            try:
                result = await runtime.submit(job)
            except InferenceOverloaded:
                result = GazeFrame("overloaded")
            except ModelNotReady:
                await ws.close(code=1013, reason="pipeline_not_ready")
                return
            await send_q.put(_ws_payload(job, result))

    async def send_loop() -> None:
        """Gửi response riêng task để client chậm không chặn pipeline."""
        while True:
            payload = await send_q.get()
            if payload is None:
                return
            try:
                await ws.send_json(payload)
            except Exception:
                return

    recv_task = asyncio.create_task(receive_loop())
    proc_task = asyncio.create_task(process_loop())
    send_task = asyncio.create_task(send_loop())
    try:
        done, pending = await asyncio.wait(
            {recv_task, proc_task, send_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            with suppress(asyncio.CancelledError, Exception):
                task.result()
    finally:
        for task in (recv_task, proc_task, send_task):
            if not task.done():
                task.cancel()
        await asyncio.gather(recv_task, proc_task, send_task, return_exceptions=True)
