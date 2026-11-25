"""Đo độ chính xác gaze offline trên dữ liệu thu (100 target/800 frame).

Chạy pipeline THẬT của service (`CpuStage` + `GpuStage`) trên mọi frame của
mỗi target, lấy median (pitch, yaw) theo target, rồi fit calibration bằng đúng
`app.services.calibration.Calibration` của service:

- split chính: `--calib-points` target (mặc định 25) để fit, phần còn lại để chấm;
- `--repeats` split ngẫu nhiên lặp lại (cùng số điểm fit) để lấy trung bình/độ lệch;
- `--folds` k-fold theo target (giống giao thức k-fold của nghiên cứu gốc).

Sai số: L2 pixel màn hình, và quy ra độ nhờ Jacobian của mapping
(px/độ = RMS theo 2 trục (pitch, yaw)).

Dữ liệu ảnh mặt KHÔNG nằm trong repo; truyền đường dẫn qua `--data`.

    docker compose run --rm --no-deps --user root --entrypoint python \
        -v "$PWD/benchmarks":/bench -v "$PWD/benchmarks/gaze/testdata":/data:ro gaze \
        /bench/gaze/tools/eval_offline.py --data /data/20261124_175802_frontal \
        --out /tmp/eval.json --frames-out /tmp/frames.json

So khớp frame-by-frame với pipeline khác (ví dụ `benchmarks/baseline/post-onnx/accuracy.frames.json`) bằng
`--parity <frames.json>`; file frames.json là map `md5(frame) -> {ok,pitch,yaw}`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, "/app")

import numpy as np

from app.services.calibration import Calibration
from app.settings import Settings


def _fmt(value: float | None, nd: int = 2) -> float | None:
    return None if value is None else round(float(value), nd)


def load_samples(data_dir: Path, limit: int = 0) -> tuple[dict, list[dict]]:
    meta = json.loads((data_dir / "meta.json").read_text(encoding="utf-8"))
    samples = []
    with open(data_dir / "samples.jsonl", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    if limit:
        samples = samples[:limit]
    return meta, samples


def run_frames(cpu, gpu, data_dir: Path, samples: list[dict], batch: int):
    """Chạy pipeline trên mọi frame -> (per_frame, order, timing)."""
    per_frame: dict[str, dict] = {}
    order: list[tuple[str, str]] = []  # (sample_id, md5)
    cpu_ms: list[float] = []
    gpu_ms: list[float] = []

    for sample in samples:
        pending: list[tuple[str, object]] = []
        for rel in sample.get("frames", []):
            path = data_dir / rel
            if not path.exists():
                continue
            data = path.read_bytes()
            key = hashlib.md5(data).hexdigest()
            order.append((sample["id"], key))
            if key in per_frame:
                continue
            started = time.perf_counter()
            try:
                prepared = cpu.prepare(data)
            except Exception as exc:  # frame hỏng không làm dừng cả đợt đo
                per_frame[key] = {"ok": False, "why": f"error:{exc}"}
                continue
            cpu_ms.append((time.perf_counter() - started) * 1000.0)
            if prepared is None:
                per_frame[key] = {"ok": False, "why": "no_face_or_gate"}
                continue
            pending.append((key, prepared))

        for start in range(0, len(pending), batch):
            chunk = pending[start : start + batch]
            started = time.perf_counter()
            preds = gpu.predict_batch([item[1] for item in chunk])
            gpu_ms.append(
                (time.perf_counter() - started) * 1000.0 / len(chunk)
            )
            for (key, _), (pitch, yaw) in zip(chunk, preds):
                per_frame[key] = {
                    "ok": True,
                    "pitch": float(pitch),
                    "yaw": float(yaw),
                }
    timing = {
        "cpu_stage_ms_mean": _fmt(np.mean(cpu_ms)) if cpu_ms else None,
        "cpu_stage_ms_p95": _fmt(np.percentile(cpu_ms, 95)) if cpu_ms else None,
        "gpu_stage_ms_per_frame_mean": _fmt(np.mean(gpu_ms), 3) if gpu_ms else None,
    }
    return per_frame, order, timing


def summarize_targets(samples, per_frame, order):
    by_sample: dict[str, list[dict]] = {}
    for sid, key in order:
        by_sample.setdefault(sid, []).append(per_frame[key])

    records = []
    for sample in samples:
        results = by_sample.get(sample["id"], [])
        ok = [r for r in results if r.get("ok")]
        rec = {
            "id": sample["id"],
            "target": [float(v) for v in sample["target_px"]],
            "screen": [float(v) for v in sample["screen_px"]],
            "n_frames": len(results),
            "n_ok": len(ok),
            "pitch": None,
            "yaw": None,
            "std_pitch": None,
            "std_yaw": None,
        }
        if ok:
            pitch = np.array([r["pitch"] for r in ok])
            yaw = np.array([r["yaw"] for r in ok])
            rec["pitch"] = float(np.median(pitch))
            rec["yaw"] = float(np.median(yaw))
            if len(ok) > 1:
                rec["std_pitch"] = float(pitch.std())
                rec["std_yaw"] = float(yaw.std())
        records.append(rec)
    return records


def fit(records) -> Calibration:
    x = [[r["pitch"], r["yaw"]] for r in records]
    y = [
        [r["target"][0] / r["screen"][0], r["target"][1] / r["screen"][1]]
        for r in records
    ]
    calib = Calibration()
    calib.fit(x, y)
    return calib


def predict_px(calib: Calibration, records) -> np.ndarray:
    out = []
    for r in records:
        x, y = calib.predict(r["pitch"], r["yaw"])
        out.append([x * r["screen"][0], y * r["screen"][1]])
    return np.array(out)


def px_per_deg(calib: Calibration, screen) -> float | None:
    coef = calib._model.coef  # (2, 2): hàng = (x, y), cột = (pitch, yaw)
    per_rad = np.linalg.norm(coef * np.array(screen)[:, None], axis=0)
    value = math.sqrt(float(np.mean(per_rad**2))) / math.degrees(1.0)
    return value if value > 1e-6 else None


def score(calib: Calibration, test) -> dict:
    pred = predict_px(calib, test)
    truth = np.array([r["target"] for r in test])
    err = pred - truth
    l2 = np.linalg.norm(err, axis=1)
    ppd = px_per_deg(calib, test[0]["screen"])
    width = test[0]["screen"][0]
    return {
        "n": len(test),
        "l1_px_mean": float(np.mean(np.abs(err).sum(axis=1))),
        "l2_px_mean": float(np.mean(l2)),
        "l2_px_median": float(np.median(l2)),
        "l2_px_p95": float(np.percentile(l2, 95)),
        "bias_px": [float(err[:, 0].mean()), float(err[:, 1].mean())],
        "l2_pct_width": float(np.mean(l2) / width * 100),
        "px_per_deg": ppd,
        "l2_deg_mean": float(np.mean(l2) / ppd) if ppd else None,
        "_l2": l2,
    }


def public(result: dict) -> dict:
    out = {k: v for k, v in result.items() if not k.startswith("_")}
    cleaned = {}
    for key, value in out.items():
        if isinstance(value, float):
            cleaned[key] = _fmt(value, 3)
        elif isinstance(value, list) and value and isinstance(value[0], float):
            cleaned[key] = [_fmt(v, 3) for v in value]
        else:
            cleaned[key] = value
    return cleaned


def primary_split(usable, n_fit: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(usable))
    fit_idx, test_idx = order[:n_fit], order[n_fit:]
    calib = fit([usable[i] for i in fit_idx])
    result = score(calib, [usable[i] for i in test_idx])
    result["fit_ids"] = sorted(usable[i]["id"] for i in fit_idx)
    return result


def repeated_splits(usable, n_fit: int, repeats: int, seed: int) -> dict:
    rng = np.random.default_rng(seed + 1)
    means, medians, p95s, degs = [], [], [], []
    for _ in range(repeats):
        order = rng.permutation(len(usable))
        calib = fit([usable[i] for i in order[:n_fit]])
        res = score(calib, [usable[i] for i in order[n_fit:]])
        means.append(res["l2_px_mean"])
        medians.append(res["l2_px_median"])
        p95s.append(res["l2_px_p95"])
        if res["l2_deg_mean"] is not None:
            degs.append(res["l2_deg_mean"])
    return {
        "repeats": repeats,
        "l2_px_mean": _fmt(np.mean(means)),
        "l2_px_mean_std": _fmt(np.std(means)),
        "l2_px_median": _fmt(np.mean(medians)),
        "l2_px_p95": _fmt(np.mean(p95s)),
        "l2_deg_mean": _fmt(np.mean(degs)) if degs else None,
    }


def kfold(usable, folds: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(usable))
    k = min(folds, len(usable))
    errs = []
    for f in range(k):
        test_idx = order[f::k]
        train_idx = np.setdiff1d(np.arange(len(usable)), test_idx)
        calib = fit([usable[i] for i in train_idx])
        res = score(calib, [usable[i] for i in test_idx])
        errs.extend(res["_l2"].tolist())
    errs = np.array(errs)
    return {
        "folds": k,
        "n": int(len(errs)),
        "l2_px_mean": _fmt(errs.mean()),
        "l2_px_median": _fmt(np.median(errs)),
        "l2_px_p95": _fmt(np.percentile(errs, 95)),
    }


def parity(per_frame: dict, other_path: Path) -> dict:
    """So frame-by-frame pitch/yaw với một frames.json khác (độ)."""
    other = json.loads(other_path.read_text(encoding="utf-8"))
    deltas = []
    only_mine = only_other = 0
    for key, mine in per_frame.items():
        theirs = other.get(key)
        if theirs is None:
            continue
        if mine.get("ok") and theirs.get("ok"):
            dp = math.degrees(mine["pitch"] - theirs["pitch"])
            dy = math.degrees(mine["yaw"] - theirs["yaw"])
            deltas.append(math.hypot(dp, dy))
        elif mine.get("ok"):
            only_mine += 1
        elif theirs.get("ok"):
            only_other += 1
    if not deltas:
        return {"n_compared": 0}
    arr = np.array(deltas)
    return {
        "n_compared": int(len(arr)),
        "only_this_ok": only_mine,
        "only_other_ok": only_other,
        "delta_deg_mean": _fmt(arr.mean(), 4),
        "delta_deg_p50": _fmt(np.percentile(arr, 50), 4),
        "delta_deg_p99": _fmt(np.percentile(arr, 99), 4),
        "delta_deg_max": _fmt(arr.max(), 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, help="thư mục một phiên thu")
    parser.add_argument("--out", required=True)
    parser.add_argument("--frames-out", default="")
    parser.add_argument("--parity", default="")
    parser.add_argument("--calib-points", type=int, default=25)
    parser.add_argument("--repeats", type=int, default=200)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--label", default="")
    args = parser.parse_args()

    from app.services.pipeline import CpuStage, GpuStage

    settings = Settings.from_env()
    settings.validate()
    cpu = CpuStage(settings)
    gpu = GpuStage(settings)
    cpu.warmup()
    gpu.warmup()

    data_dir = Path(args.data)
    meta, samples = load_samples(data_dir, args.limit)
    started = time.time()
    per_frame, order, timing = run_frames(
        cpu, gpu, data_dir, samples, settings.gpu_batch
    )
    elapsed = time.time() - started

    records = summarize_targets(samples, per_frame, order)
    usable = [r for r in records if r["pitch"] is not None]
    n_fit = min(args.calib_points, max(2, len(usable) - 1))

    frames_total = sum(r["n_frames"] for r in records)
    frames_ok = sum(r["n_ok"] for r in records)
    pitch_std = [r["std_pitch"] for r in usable if r["std_pitch"] is not None]
    yaw_std = [r["std_yaw"] for r in usable if r["std_yaw"] is not None]
    payload = {
        "label": args.label,
        "session": data_dir.name,
        "condition": meta.get("condition"),
        "model": gpu.model_name,
        "precision": gpu.precision,
        "device": str(gpu.device),
        "targets": len(records),
        "targets_usable": len(usable),
        "frames_total": frames_total,
        "frames_ok": frames_ok,
        "frames_failed": frames_total - frames_ok,
        "fail_rate_pct": _fmt(100 * (1 - frames_ok / max(1, frames_total))),
        "run_seconds": _fmt(elapsed, 1),
        "timing": timing,
        "calib_points": n_fit,
        "primary_split": public(primary_split(usable, n_fit, args.seed)),
        "repeated_splits": repeated_splits(
            usable, n_fit, args.repeats, args.seed
        ),
        "kfold": kfold(usable, args.folds, args.seed),
        "jitter_deg": {
            "pitch_std_mean": _fmt(np.degrees(np.mean(pitch_std)), 3)
            if pitch_std
            else None,
            "yaw_std_mean": _fmt(np.degrees(np.mean(yaw_std)), 3)
            if yaw_std
            else None,
        },
    }
    if args.parity:
        payload["parity"] = parity(per_frame, Path(args.parity))

    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    if args.frames_out:
        Path(args.frames_out).write_text(json.dumps(per_frame))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
