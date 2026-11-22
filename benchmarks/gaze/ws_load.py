#!/usr/bin/env python3
"""Đo WebSocket gaze nhiều session, xuất JSON + p99.

Chạy trong image gaze:
    docker compose ... exec -T gaze \
      python /bench/gaze/ws_load.py --image /fixtures/face_sample.jpg \
      --sessions 1,4,8,12 --fps 15 --duration 30 \
      --out /bench/.../gaze/ws-load.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, "/app")

try:
    from scripts.bench import create_ready_session, encode_frame
except ImportError as exc:  # pragma: no cover
    raise SystemExit(f"Không import được scripts.bench: {exc}") from exc

try:
    import websockets
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Thiếu websockets") from exc


def pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(len(ordered) * q))], 3)


def health(url: str) -> dict | None:
    try:
        with urllib.request.urlopen(f"{url}/health", timeout=5) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


async def run_client(ws_url: str, sid: str, jpeg: bytes, fps: float, duration: float) -> dict:
    interval = 1.0 / fps
    send_times: dict[int, float] = {}
    rtts: list[float] = []
    statuses: dict[str, int] = {}
    sent = received = 0

    async with websockets.connect(f"{ws_url}/session/{sid}/stream", max_size=2 * 1024 * 1024) as ws:

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
            await asyncio.sleep(1.0)
        finally:
            reader_task.cancel()
            try:
                await reader_task
            except asyncio.CancelledError:
                pass

    return {
        "sent": sent,
        "received": received,
        "fps_effective": round(received / duration, 2),
        "rtts_ms": rtts,
        "statuses": statuses,
    }


async def run_scenario(
    base_url: str, ws_url: str, image: bytes, sessions: int, fps: float, duration: float
) -> dict:
    before = health(base_url)
    sids = [create_ready_session(base_url, image) for _ in range(sessions)]
    try:
        results = await asyncio.gather(
            *(run_client(ws_url, sid, image, fps, duration) for sid in sids)
        )
    finally:
        for sid in sids:
            try:
                urllib.request.urlopen(
                    urllib.request.Request(f"{base_url}/session/{sid}", method="DELETE"),
                    timeout=5,
                ).read()
            except Exception:
                pass
    after = health(base_url)

    sent = sum(item["sent"] for item in results)
    received = sum(item["received"] for item in results)
    all_rtts = [rtt for item in results for rtt in item["rtts_ms"]]
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
        "responses_per_s": round(received / duration, 2),
        "fps_per_session": round(received / duration / sessions, 2),
        "drop": sent - received,
        "drop_rate": round((sent - received) / sent, 4) if sent else 0.0,
        "rtt_ms": {
            "p50": pct(all_rtts, 0.50),
            "p95": pct(all_rtts, 0.95),
            "p99": pct(all_rtts, 0.99),
            "mean": round(statistics.mean(all_rtts), 3) if all_rtts else None,
            "max": round(max(all_rtts), 3) if all_rtts else None,
        },
        "statuses": statuses,
        "health_before": before,
        "health_after": after,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--image", required=True)
    parser.add_argument("--sessions", default="1,4,8,12")
    parser.add_argument("--fps", type=float, default=15.0)
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--width", type=int, default=0)
    parser.add_argument("--quality", type=float, default=0.78)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    base_url = args.url.rstrip("/")
    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
    image = Path(args.image).read_bytes()
    if args.width > 0:
        original = cv2.imdecode(
            np.frombuffer(image, dtype=np.uint8), cv2.IMREAD_COLOR
        )
        if original is None:
            raise SystemExit(f"Không decode được ảnh {args.image}")
        scale = args.width / original.shape[1]
        resized = cv2.resize(
            original,
            (args.width, max(1, int(round(original.shape[0] * scale)))),
            interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC,
        )
        ok, encoded = cv2.imencode(
            ".jpg",
            resized,
            [int(cv2.IMWRITE_JPEG_QUALITY), int(round(args.quality * 100))],
        )
        if not ok:
            raise SystemExit("JPEG encode failed")
        image = encoded.tobytes()
    levels = [int(item) for item in args.sessions.split(",") if item.strip()]
    scenarios = []
    for sessions in levels:
        print(f"[gaze] sessions={sessions} fps={args.fps} duration={args.duration}s")
        scenarios.append(
            asyncio.run(run_scenario(base_url, ws_url, image, sessions, args.fps, args.duration))
        )
    payload = {
        "url": base_url,
        "image": str(args.image),
        "frame_bytes": len(image),
        "scenarios": scenarios,
    }
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            [{k: s[k] for k in ("sessions", "responses_per_s", "rtt_ms")} for s in scenarios],
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
