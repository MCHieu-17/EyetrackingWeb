"""So sánh output UniGaze fp32 vs fp16 trên một thư mục ảnh.

Chạy trong image gaze (có torch/CUDA):

    docker compose exec -T gaze python -m scripts.compare_precision \
        --dir /tmp/faces --max-mean-deg 0.05 --max-abs-deg 0.3

Gate mặc định: mean |Δ| <= 0.05° và max |Δ| <= 0.3° (đổi bằng CLI).
Exit code 1 nếu vượt gate hoặc không đọc được ảnh nào có mặt.
"""

from __future__ import annotations

import argparse
import math
import statistics
from dataclasses import replace
from pathlib import Path

from app.services.pipeline import CpuStage, GpuStage
from app.settings import Settings

SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _deg(value_rad: float) -> float:
    return math.degrees(abs(value_rad))


def _summary(values: list[float]) -> tuple[float, float, float]:
    ordered = sorted(values)
    mean = statistics.mean(ordered)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    return mean, p95, ordered[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True)
    parser.add_argument("--max-mean-deg", type=float, default=0.05)
    parser.add_argument("--max-abs-deg", type=float, default=0.3)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    settings = Settings.from_env()
    settings.validate()
    if settings.device != "cuda":
        raise SystemExit("Script cần DEVICE=cuda.")

    cpu = CpuStage(settings)
    gpu32 = GpuStage(replace(settings, precision="fp32"))
    gpu16 = GpuStage(replace(settings, precision="fp16"))

    files = sorted(
        path
        for path in Path(args.dir).rglob("*")
        if path.is_file() and path.suffix.lower() in SUFFIXES
    )
    if args.limit > 0:
        files = files[: args.limit]
    if not files:
        raise SystemExit(f"Không thấy ảnh trong {args.dir}")

    deltas: list[float] = []  # norm Δ(pitch, yaw), độ
    no_face = 0
    failed = 0
    for path in files:
        try:
            prepared = cpu.prepare(path.read_bytes())
        except Exception as exc:
            failed += 1
            print(f"skip {path.name}: {exc}")
            continue
        if prepared is None:
            no_face += 1
            continue
        pitch32, yaw32 = gpu32.predict(prepared)
        pitch16, yaw16 = gpu16.predict(prepared)
        deltas.append(
            math.hypot(_deg(pitch32 - pitch16), _deg(yaw32 - yaw16))
        )

    if not deltas:
        raise SystemExit(
            f"Không có ảnh nào detect được mặt (no_face={no_face}, lỗi={failed})"
        )

    mean, p95, maximum = _summary(deltas)
    print(f"# So sánh fp32 vs fp16 — {len(deltas)} ảnh")
    print(f"no_face={no_face} lỗi={failed} model={settings.unigaze_model}")
    print()
    print("| metric | giá trị |")
    print("|---|---:|")
    print(f"| mean Δ(pitch,yaw) | {mean:.4f}° |")
    print(f"| p95 Δ(pitch,yaw) | {p95:.4f}° |")
    print(f"| max Δ(pitch,yaw) | {maximum:.4f}° |")

    ok = mean <= args.max_mean_deg and maximum <= args.max_abs_deg
    print()
    print(
        f"gate: mean <= {args.max_mean_deg}° và max <= {args.max_abs_deg}° "
        f"-> {'PASS' if ok else 'FAIL'}"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
