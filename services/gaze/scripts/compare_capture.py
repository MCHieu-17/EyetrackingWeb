#!/usr/bin/env python3
"""A/B capture (width × JPEG quality) so với baseline, kèm px error.

Chạy trong image gaze (có model/GPU):

    docker compose exec -T gaze python -m scripts.compare_capture \
        --dir /fixtures/faces --baseline 480:0.78 \
        --variants 320:0.7,480:0.7 --calibration /tmp/calib.ubj \
        --out /tmp/capture-ab.json

Gate mặc định: Δ(pitch,yaw) mean ≤5% baseline và Δ px mean ≤10% cạnh ngắn
viewport. Không có ground-truth nên Δ px là độ lệch so với baseline sau khi
chiếu qua model calibration thật, không phải MAE tuyệt đối.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

import cv2
import numpy as np

from app.services.calibration import Calibration
from app.services.pipeline import CpuStage, GpuStage
from app.settings import Settings

SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
DEFAULT_VIEWPORT = (1536, 730)


def _deg(value: float) -> float:
    return math.degrees(abs(value))


def _spec(raw: str) -> tuple[int, float]:
    width, _, quality = raw.partition(":")
    return int(width), float(quality or 0.78)


def _encode(original: np.ndarray, width: int, quality: float) -> bytes:
    scale = width / original.shape[1]
    resized = cv2.resize(
        original,
        (width, max(1, int(round(original.shape[0] * scale)))),
        interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC,
    )
    ok, encoded = cv2.imencode(
        ".jpg", resized, [int(cv2.IMWRITE_JPEG_QUALITY), int(round(quality * 100))]
    )
    if not ok:
        raise RuntimeError("JPEG encode failed")
    return encoded.tobytes()


def _p95(values: list[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True)
    parser.add_argument("--baseline", default="480:0.78")
    parser.add_argument("--variants", default="320:0.7,480:0.7")
    parser.add_argument("--calibration")
    parser.add_argument("--viewport", default="1536x730")
    parser.add_argument("--max-delta-pct", type=float, default=5.0)
    parser.add_argument("--max-px-pct", type=float, default=10.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    settings = Settings.from_env()
    settings.validate()
    cpu = CpuStage(settings)
    gpu = GpuStage(settings)
    cpu.warmup()
    gpu.warmup()

    calib = None
    if args.calibration:
        calib = Calibration()
        calib.deserialize(Path(args.calibration).read_bytes())
    vw, vh = (int(value) for value in args.viewport.lower().split("x"))

    files = sorted(
        path
        for path in Path(args.dir).rglob("*")
        if path.is_file() and path.suffix.lower() in SUFFIXES
    )
    if args.limit > 0:
        files = files[: args.limit]
    if not files:
        raise SystemExit(f"Không thấy ảnh trong {args.dir}")

    base_width, base_quality = _spec(args.baseline)
    variants = [_spec(item) for item in args.variants.split(",") if item.strip()]
    specs = [(base_width, base_quality)] + [
        item for item in variants if item != (base_width, base_quality)
    ]

    rows: dict[str, dict] = {
        f"{width}:{quality:g}": {
            "width": width,
            "quality": quality,
            "bytes": [],
            "pose_delta_deg": [],
            "px_delta": [],
            "no_face": 0,
        }
        for width, quality in specs
    }

    for path in files:
        original = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if original is None:
            print(f"skip {path.name}: không đọc được ảnh")
            continue
        baseline = None
        for width, quality in specs:
            data = _encode(original, width, quality)
            key = f"{width}:{quality:g}"
            row = rows[key]
            row["bytes"].append(len(data))
            prepared = cpu.prepare(data)
            if prepared is None:
                row["no_face"] += 1
                continue
            pitch, yaw = gpu.predict(prepared)
            if baseline is None:
                baseline = (pitch, yaw)
                row["pose_delta_deg"].append(0.0)
                row["px_delta"].append(0.0)
                continue
            delta = math.hypot(_deg(pitch - baseline[0]), _deg(yaw - baseline[1]))
            row["pose_delta_deg"].append(delta)
            if calib is not None:
                x, y = calib.predict(pitch, yaw)
                bx, by = calib.predict(*baseline)
                row["px_delta"].append(
                    math.hypot((x - bx) * vw, (y - by) * vh)
                )

    baseline_mag = 1.0
    # Baseline pose magnitude lấy từ ảnh đầu để chuẩn hoá tương đối 5%.
    first = files[0] if files else None
    if first is not None:
        original = cv2.imread(str(first), cv2.IMREAD_COLOR)
        if original is not None:
            prepared = cpu.prepare(_encode(original, base_width, base_quality))
            if prepared is not None:
                pitch, yaw = gpu.predict(prepared)
                baseline_mag = max(1.0, math.hypot(_deg(pitch), _deg(yaw)))

    result: dict[str, dict] = {}
    passed = True
    for width, quality in specs:
        key = f"{width}:{quality:g}"
        row = rows[key]
        deltas = row["pose_delta_deg"]
        px = row["px_delta"]
        mean_delta = statistics.mean(deltas) if deltas else None
        mean_px = statistics.mean(px) if px else None
        delta_pct = (
            mean_delta / baseline_mag * 100.0 if mean_delta is not None else None
        )
        px_pct = mean_px / min(vw, vh) * 100.0 if mean_px is not None else None
        ok = (
            delta_pct is not None
            and delta_pct <= args.max_delta_pct
            and (px_pct is None or px_pct <= args.max_px_pct)
        )
        if key != f"{base_width}:{base_quality:g}" and not ok:
            passed = False
        result[key] = {
            "width": width,
            "quality": quality,
            "images": len(deltas),
            "no_face": row["no_face"],
            "jpeg_bytes_mean": (
                round(statistics.mean(row["bytes"]), 1) if row["bytes"] else None
            ),
            "jpeg_bytes_p95": _p95(row["bytes"]),
            "pose_delta_deg_mean": round(mean_delta, 4) if mean_delta is not None else None,
            "pose_delta_pct": round(delta_pct, 2) if delta_pct is not None else None,
            "px_delta_mean": round(mean_px, 2) if mean_px is not None else None,
            "px_delta_pct": round(px_pct, 2) if px_pct is not None else None,
            "pass": ok,
        }

    payload = {
        "baseline": f"{base_width}:{base_quality:g}",
        "viewport": [vw, vh],
        "gates": {
            "max_delta_pct": args.max_delta_pct,
            "max_px_pct": args.max_px_pct,
        },
        "variants": result,
        "pass": passed,
    }
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    print("| variant | bytes mean | bytes p95 | Δ pose % | Δ px % | pass |")
    print("|---|---:|---:|---:|---:|---|")
    for key, value in result.items():
        print(
            f"| {key} | {value['jpeg_bytes_mean']} | {value['jpeg_bytes_p95']} | "
            f"{value['pose_delta_pct']} | {value['px_delta_pct']} | "
            f"{'PASS' if value['pass'] else 'FAIL'} |"
        )
    print()
    print(f"gate -> {'PASS' if passed else 'FAIL'}; out={target}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
