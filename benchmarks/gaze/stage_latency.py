#!/usr/bin/env python3
"""Đo latency từng stage của gaze pipeline trên một ảnh cố định.

Chạy trong image gaze (onnxruntime/opencv):
    docker compose ... exec -T gaze \
      python /bench/gaze/stage_latency.py --image /fixtures/face_sample.jpg \
      --iterations 200 --warmup 20 --out /bench/.../gaze/stage-latency.json

Không sửa code production; script dùng trực tiếp CpuStage/GpuStage/Calibration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, "/app")

import cv2
import numpy as np

from app.services.calibration import Calibration
from app.services.gaze_geometry import denormalize_gaze, expand_bbox
from app.services.pipeline import (
    CROP_SCALE,
    CpuStage,
    GpuStage,
    PreparedFace,
    decode_image,
)
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


def gpu_memory_mib() -> float | None:
    """VRAM đang dùng (MiB, toàn GPU) qua nvidia-smi; ORT không có API peak."""
    import subprocess

    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            text=True,
            timeout=5,
        )
        return float(out.splitlines()[0])
    except Exception:
        return None


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
    for _ in range(warmup):
        prepared = cpu.prepare(image_bytes)
        if prepared is None:
            raise RuntimeError("FaceLandmarker không detect được mặt trong ảnh fixture")
        gpu.predict(prepared)

    stages = {
        "decode": [],
        "landmark_detect": [],
        "warp_preprocess": [],
        "tensor_prep": [],
        "unigaze_forward": [],
        "denormalize": [],
        "calibration": [],
        "smoothing": [],
        "total": [],
    }
    last_pitch = last_yaw = 0.0
    for i in range(iterations):
        total_start = time.perf_counter()

        t0 = time.perf_counter()
        rgb = decode_image(image_bytes)
        t1 = time.perf_counter()
        detection = cpu.detector.detect(rgb)
        t2 = time.perf_counter()
        if detection is None:
            raise RuntimeError("FaceLandmarker không detect được mặt ở iteration")
        bbox, landmarks = detection
        xmin, ymin, xmax, ymax = expand_bbox(bbox, CROP_SCALE, *rgb.shape[1::-1])
        face = np.ascontiguousarray(rgb[ymin:ymax, xmin:xmax])
        landmarks_crop = landmarks - np.array([xmin, ymin], dtype=np.float32)
        warped = cpu.preprocessor.process(face, landmarks_crop)
        t3 = time.perf_counter()
        if warped is None:
            raise RuntimeError("Preprocessor trả None (head pose?)")
        prepared = PreparedFace(*warped)

        t4 = time.perf_counter()
        batch = prepared.rgb[None]
        t5 = time.perf_counter()
        raw = gpu.session.run(None, {gpu._input: batch})[0]
        t6a = time.perf_counter()
        pitch, yaw = denormalize_gaze(
            float(raw[0][0]), float(raw[0][1]), prepared.rotation
        )
        t6 = time.perf_counter()
        x, y = calib.predict(float(pitch), float(yaw))
        t7 = time.perf_counter()
        x, y = smoother.process([x, y], timestamp=time.perf_counter())
        t8 = time.perf_counter()

        stages["decode"].append((t1 - t0) * 1000)
        stages["landmark_detect"].append((t2 - t1) * 1000)
        stages["warp_preprocess"].append((t3 - t2) * 1000)
        stages["tensor_prep"].append((t5 - t4) * 1000)
        stages["unigaze_forward"].append((t6a - t5) * 1000)
        stages["denormalize"].append((t6 - t6a) * 1000)
        stages["calibration"].append((t7 - t6) * 1000)
        stages["smoothing"].append((t8 - t7) * 1000)
        stages["total"].append((t8 - total_start) * 1000)
        last_pitch, last_yaw = float(pitch), float(yaw)

    return {
        "stages_ms": {name: stats(values) for name, values in stages.items()},
        "last_prediction": {"pitch": last_pitch, "yaw": last_yaw},
    }


def run_batches(
    image_bytes: bytes,
    *,
    cpu: CpuStage,
    gpu: GpuStage,
    batch_sizes: list[int],
    warmup: int,
) -> dict:
    """Đo forward theo batch + delta so với single (cùng một ảnh)."""
    prepared = cpu.prepare(image_bytes)
    if prepared is None:
        return {}
    single = gpu.predict(prepared)
    results: dict[str, dict] = {}
    for size in batch_sizes:
        batch = [prepared] * size
        for _ in range(min(warmup, 5)):
            gpu.predict_batch(batch)
        times: list[float] = []
        predictions = []
        for _ in range(20):
            started = time.perf_counter()
            predictions = gpu.predict_batch(batch)
            times.append((time.perf_counter() - started) * 1000.0)
        p50 = pct(times, 0.50)
        results[str(size)] = {
            "batch": size,
            "p50_ms": p50,
            "p95_ms": pct(times, 0.95),
            "per_item_ms": round(p50 / size, 3) if p50 else None,
            "fps": round(1000.0 / (p50 / size), 1) if p50 else None,
            "max_delta_rad": max(
                math.hypot(pitch - single[0], yaw - single[1])
                for pitch, yaw in predictions
            ),
            "gpu_used_mib": gpu_memory_mib(),
        }
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--widths", default="480,720,1080")
    parser.add_argument("--qualities", default="0.78")
    parser.add_argument("--batch-sizes", default="1,2,4,8")
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
    qualities = [
        float(item) for item in args.qualities.split(",") if item.strip()
    ]
    batch_sizes = [
        int(item) for item in args.batch_sizes.split(",") if item.strip()
    ]
    results = {}
    for width in widths:
        scale = width / original.shape[1]
        resized = cv2.resize(
            original,
            (width, max(1, int(round(original.shape[0] * scale)))),
            interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC,
        )
        for quality in qualities:
            ok, encoded = cv2.imencode(
                ".jpg", resized, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality * 100)]
            )
            if not ok:
                raise RuntimeError("JPEG encode failed")
            data = encoded.tobytes()
            key = (
                f"{width}px"
                if len(qualities) == 1
                else f"{width}px_q{int(round(quality * 100))}"
            )
            results[key] = {
                "width": resized.shape[1],
                "height": resized.shape[0],
                "jpeg_quality": quality,
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
                "batch": run_batches(
                    data,
                    cpu=cpu,
                    gpu=gpu,
                    batch_sizes=batch_sizes,
                    warmup=args.warmup,
                ),
            }

    payload = {
        "device": str(gpu.device),
        "precision": gpu.precision,
        "model": gpu.model_name,
        "gpu_name": gpu.gpu_name,
        "runtime": "onnxruntime",
        "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "gpu_used_mib_after": gpu_memory_mib(),
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
