"""Benchmark gaze service qua HTTP + WebSocket.

Chạy trong image gaze (đã có websockets) để đo đúng đường serving:

    docker compose exec -T gaze python -m scripts.bench \
        --image /tmp/face.jpg --sessions 1,4,8,12 --fps 15 --duration 10

Script tạo session, calibration 1 điểm + train, rồi mở N WebSocket gửi frame
đều theo FPS. Kết quả: FPS/phiên, tổng response/s, drop, RTT p50/p95.

Cần ảnh có mặt người rõ ràng; nếu calibrate trả `no_face`, đổi ảnh khác.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import struct
import time
import urllib.request
import uuid

try:
    import websockets
except ImportError as exc:  # pragma: no cover - chỉ chạy trong image
    raise SystemExit("Thiếu websockets; chạy trong image gaze.") from exc


def _post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _post_multipart(
    url: str, fields: dict[str, str], field: str, filename: str, content: bytes
) -> dict:
    boundary = f"----gazebench{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode()
        )
    chunks.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode()
        + content
        + b"\r\n"
    )
    chunks.append(f"--{boundary}--\r\n".encode())
    req = urllib.request.Request(
        url,
        data=b"".join(chunks),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _post(url: str) -> dict:
    req = urllib.request.Request(url, data=b"", method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _delete(url: str) -> None:
    req = urllib.request.Request(url, method="DELETE")
    try:
        urllib.request.urlopen(req, timeout=10).read()
    except Exception:
        pass


def create_ready_session(base_url: str, image: bytes) -> str:
    created = _post_json(
        f"{base_url}/session", {"points": [{"id": "c", "x": 0.5, "y": 0.5}]}
    )
    sid = created["session_id"]
    calibrated = _post_multipart(
        f"{base_url}/session/{sid}/calibrate",
        {"point_id": "c"},
        "image",
        "face.jpg",
        image,
    )
    if calibrated.get("status") != "accepted":
        _delete(f"{base_url}/session/{sid}")
        raise RuntimeError(
            f"calibrate trả {calibrated.get('status')}; cần ảnh có mặt người"
        )
    trained = _post(f"{base_url}/session/{sid}/train")
    if trained.get("status") != "ok":
        _delete(f"{base_url}/session/{sid}")
        raise RuntimeError(f"train trả {trained}")
    return sid


def encode_frame(sequence: int, jpeg: bytes, presentation: str) -> bytes:
    header = {
        "v": 2,
        "frameId": f"bench-{sequence}",
        "sequence": sequence,
        "captureMonotonicNs": int(time.perf_counter() * 1e9),
        "eventTime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "presentationId": presentation,
        "layoutGeneration": 0,
    }
    raw = json.dumps(header).encode()
    return struct.pack(">I", len(raw)) + raw + jpeg


def percentiles(values: list[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    ordered = sorted(values)
    p50 = statistics.median(ordered)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    return round(p50, 1), round(p95, 1)


async def run_client(
    ws_url: str,
    sid: str,
    jpeg: bytes,
    fps: float,
    duration: float,
) -> dict:
    interval = 1.0 / fps
    send_times: dict[int, float] = {}
    rtts: list[float] = []
    statuses: dict[str, int] = {}
    received = 0
    sent = 0

    async with websockets.connect(
        f"{ws_url}/session/{sid}/stream", max_size=2 * 1024 * 1024
    ) as ws:

        async def reader() -> None:
            nonlocal received
            while True:
                raw = await ws.recv()
                now = time.perf_counter()
                data = json.loads(raw)
                received += 1
                status = str(data.get("status", "unknown"))
                statuses[status] = statuses.get(status, 0) + 1
                sequence = data.get("sequence")
                sent_at = send_times.pop(sequence, None)
                if sent_at is not None:
                    rtts.append((now - sent_at) * 1000.0)

        reader_task = asyncio.create_task(reader())
        try:
            # Gửi đúng nhịp; nếu trễ hơn 1 slot thì bỏ slot, KHÔNG gửi bù
            # (gửi bù tạo burst và bị server throttle, làm sai số đo).
            next_at = time.perf_counter()
            end_at = next_at + duration
            sequence = 0
            while True:
                now = time.perf_counter()
                if now >= end_at:
                    break
                if now < next_at:
                    await asyncio.sleep(min(next_at - now, end_at - now))
                    continue
                send_times[sequence] = now
                await ws.send(encode_frame(sequence, jpeg, sid))
                sent += 1
                sequence += 1
                next_at += interval
                if next_at < time.perf_counter():
                    next_at = time.perf_counter() + interval
            await asyncio.sleep(1.0)  # drain
        finally:
            reader_task.cancel()
            try:
                await reader_task
            except asyncio.CancelledError:
                pass

    p50, p95 = percentiles(rtts)
    return {
        "sent": sent,
        "received": received,
        "fps_effective": received / duration,
        "p50_ms": p50,
        "p95_ms": p95,
        "statuses": statuses,
    }


async def run_scenario(
    base_url: str,
    ws_url: str,
    image: bytes,
    sessions: int,
    fps: float,
    duration: float,
) -> dict:
    sids = [create_ready_session(base_url, image) for _ in range(sessions)]
    try:
        results = await asyncio.gather(
            *(run_client(ws_url, sid, image, fps, duration) for sid in sids)
        )
    finally:
        for sid in sids:
            _delete(f"{base_url}/session/{sid}")

    sent = sum(item["sent"] for item in results)
    received = sum(item["received"] for item in results)
    rtts = [item["p50_ms"] for item in results if item["p50_ms"] is not None]
    statuses: dict[str, int] = {}
    for item in results:
        for status, count in item["statuses"].items():
            statuses[status] = statuses.get(status, 0) + count
    return {
        "sessions": sessions,
        "fps": fps,
        "duration": duration,
        "sent": sent,
        "received": received,
        "responses_per_s": round(received / duration, 1),
        "fps_per_session": round(received / duration / sessions, 1),
        "drop": sent - received,
        "drop_rate": round((sent - received) / sent, 4) if sent else 0.0,
        "p50_ms_avg": round(statistics.mean(rtts), 1) if rtts else None,
        "statuses": statuses,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--image", required=True, help="Ảnh JPEG/PNG có mặt người")
    parser.add_argument("--sessions", default="1,4,8,12")
    parser.add_argument("--fps", type=float, default=15.0)
    parser.add_argument("--duration", type=float, default=10.0)
    args = parser.parse_args()

    base_url = args.url.rstrip("/")
    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
    image = open(args.image, "rb").read()
    session_counts = [int(value) for value in args.sessions.split(",") if value]

    print(
        f"# Gaze bench: url={base_url} fps={args.fps} "
        f"duration={args.duration}s image={args.image}"
    )
    print()
    print(
        "| sessions | sent | received | resp/s | fps/phiên | drop | drop% | "
        "p50 RTT (ms) | status |"
    )
    print("|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for sessions in session_counts:
        result = asyncio.run(
            run_scenario(
                base_url, ws_url, image, sessions, args.fps, args.duration
            )
        )
        print(
            f"| {sessions} | {result['sent']} | {result['received']} | "
            f"{result['responses_per_s']} | {result['fps_per_session']} | "
            f"{result['drop']} | {result['drop_rate'] * 100:.1f}% | "
            f"{result['p50_ms_avg']} | {result['statuses']} |"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
