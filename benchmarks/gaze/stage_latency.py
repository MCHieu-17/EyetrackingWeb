#!/usr/bin/env python3
"""Đo latency từng stage của gaze pipeline trên một ảnh cố định.

Chạy trong image gaze (có torch/mediapipe/opencv):
    docker compose ... exec -T gaze \
      python /bench/gaze/stage_latency.py --image /fixtures/face_sample.jpg \
      --iterations 200 --warmup 20 --out /bench/.../gaze/stage-latency.json

Không sửa code production; script dùng trực tiếp CpuStage/GpuStage/Calibration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import resource
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, "/app")

import cv2
import numpy as np
import torch

from app.services.calibration import Calibration
from app.services.pipeline import CpuStage, GpuStage, PreparedFace, decode_image
from app.services.smoothing import OneEuroFilter2D
from app.settings import Settings


def pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(len(ordered) * q))
    return round(ordered[index], 3)


def stats(values: list[float]) -> dict:
    return {
        "count": len(values),
        "mean": round(statistics.mean(values), 3) if values else None,
        "p50": pct(values, 0.50),
        "p95": pct(values, 0.95),
        "p99": pct(values, 0.99),
        "min": round(min(values), 3) if values else None,
        "max": round(max(values), 3) if values else None,
    }


def maybe_sync(device: str) -> None:
    if device.startswith("cuda") and torch.cuda.is_available():
        torch.cuda.synchronize()


def run_image(
    image_bytes: bytes,
    *,
    cpu: CpuStage,
    gpu: GpuStage,
    settings: Settings,
    calib: Calibration,
    smoother: OneEuroFilter2D,
    warmup: int,
    iterations: int,
) -> dict:
    frame = decode_image(image_bytes)
    for _ in range(warmup):
        prepared = cpu.prepare(image_bytes)
        if prepared is None:
            raise RuntimeError("MediaPipe không detect được mặt trong ảnh fixture")
        gpu.predict(prepared)
    maybe_sync(str(gpu.device))

    stages = {
        "decode": [],
        "cvt_color": [],
        "mediapipe_detect": [],
        "warp_preprocess": [],
        "tensor_prep": [],
        "unigaze_forward": [],
        "calibration": [],
        "smoothing": [],
        "total": [],
    }
    last_pitch = last_yaw = 0.0
    for i in range(iterations):
        total_start = time.perf_counter()

        t0 = time.perf_counter()
        frame = decode_image(image_bytes)
        t1 = time.perf_counter()
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        t2 = time.perf_counter()
        detection = cpu.detector.detect(rgb)
        t3 = time.perf_counter()
        if detection is None:
            raise RuntimeError("MediaPipe không detect được mặt ở iteration")
        (xmin, ymin, xmax, ymax), landmarks = detection
        face = np.ascontiguousarray(rgb[ymin:ymax, xmin:xmax])
        landmarks_crop = landmarks - np.array([xmin, ymin], dtype=np.float32)
        warped = cpu.preprocessor.process(face, landmarks_crop)
        t4 = time.perf_counter()
        if warped is None:
            raise RuntimeError("Preprocessor trả None (head pose?)")
        prepared = PreparedFace(warped)

        t5 = time.perf_counter()
        tensor = gpu._to_tensor(prepared)
        maybe_sync(str(gpu.device))
        t6 = time.perf_counter()
        with torch.inference_mode():
            pred = gpu.model(tensor)["pred_gaze"]
            maybe_sync(str(gpu.device))
            pitch, yaw = pred[0].tolist()
        t7 = time.perf_counter()
        x, y = calib.predict(float(pitch), float(yaw))
        t8 = time.perf_counter()
        x, y = smoother.process([x, y], timestamp=time.perf_counter())
        t9 = time.perf_counter()

        stages["decode"].append((t1 - t0) * 1000)
        stages["cvt_color"].append((t2 - t1) * 1000)
        stages["mediapipe_detect"].append((t3 - t2) * 1000)
        stages["warp_preprocess"].append((t4 - t3) * 1000)
        stages["tensor_prep"].append((t6 - t5) * 1000)
        stages["unigaze_forward"].append((t7 - t6) * 1000)
        stages["calibration"].append((t8 - t7) * 1000)
        stages["smoothing"].append((t9 - t8) * 1000)
        stages["total"].append((t9 - total_start) * 1000)
        last_pitch, last_yaw = float(pitch), float(yaw)

    return {
        "stages_ms": {name: stats(values) for name, values in stages.items()},
        "last_prediction": {"pitch": last_pitch, "yaw": last_yaw},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--widths", default="480,720,1080")
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    settings = Settings.from_env()
    settings.validate()
    cpu = CpuStage(settings)
    gpu = GpuStage(settings)
    cpu.warmup()
    gpu.warmup()
    maybe_sync(settings.device)

    calib = Calibration()
    xs = [[-0.4 + i * 0.04, -0.2 + (i % 5) * 0.08] for i in range(64)]
    ys = [[0.1 + i * 0.01, 0.2 + (i % 7) * 0.02] for i in range(64)]
    calib.fit(xs, ys)
    smoother = OneEuroFilter2D(
        min_cutoff=settings.oneeuro_min_cutoff,
        beta=settings.oneeuro_beta,
        d_cutoff=settings.oneeuro_d_cutoff,
    )

    original = cv2.imread(args.image, cv2.IMREAD_COLOR)
    if original is None:
        raise SystemExit(f"Không đọc được ảnh {args.image}")
    widths = [int(item) for item in args.widths.split(",") if item.strip()]
    results = {}
    for width in widths:
        scale = width / original.shape[1]
        resized = cv2.resize(
            original,
            (width, max(1, int(round(original.shape[0] * scale)))),
            interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC,
        )
        ok, encoded = cv2.imencode(".jpg", resized, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        if not ok:
            raise RuntimeError("JPEG encode failed")
        data = encoded.tobytes()
        results[f"{width}px"] = {
            "width": resized.shape[1],
            "height": resized.shape[0],
            "jpeg_bytes": len(data),
            "jpeg_sha256": hashlib.sha256(data).hexdigest(),
            **run_image(
                data,
                cpu=cpu,
                gpu=gpu,
                settings=settings,
                calib=calib,
                smoother=smoother,
                warmup=args.warmup,
                iterations=args.iterations,
            ),
        }

    payload = {
        "device": str(gpu.device),
        "precision": gpu.precision,
        "model": gpu.model_name,
        "gpu_name": gpu.gpu_name,
        "cuda_available": torch.cuda.is_available(),
        "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "cuda_max_memory_allocated_mib": (
            round(torch.cuda.max_memory_allocated() / 1024**2, 1)
            if torch.cuda.is_available()
            else None
        ),
        "cuda_max_memory_reserved_mib": (
            round(torch.cuda.max_memory_reserved() / 1024**2, 1)
            if torch.cuda.is_available()
            else None
        ),
        "iterations": args.iterations,
        "warmup": args.warmup,
        "images": results,
    }
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: v["stages_ms"]["total"] for k, v in results.items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
