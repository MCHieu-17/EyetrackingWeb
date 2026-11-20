#!/usr/bin/env python3
"""So sánh hai summary.json và xuất bảng delta."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def flatten(value, prefix=""):
    out = {}
    if isinstance(value, dict):
        for key, item in value.items():
            out.update(flatten(item, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        out[prefix] = float(value)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    base = flatten(json.loads((Path(args.baseline) / "summary.json").read_text()))
    after = flatten(json.loads((Path(args.after) / "summary.json").read_text()))
    keys = sorted(set(base) & set(after))
    rows = []
    for key in keys:
        b, a = base[key], after[key]
        if b == 0:
            delta = None
        else:
            delta = (a - b) / abs(b)
        rows.append((key, b, a, delta))

    lines = [
        "# Benchmark comparison",
        "",
        f"- baseline: `{args.baseline}`",
        f"- after: `{args.after}`",
        "",
        "| Metric | Baseline | After | Delta |",
        "|---|---:|---:|---:|",
    ]
    for key, b, a, delta in rows:
        pct = "-" if delta is None else f"{delta * 100:+.2f}%"
        lines.append(f"| {key} | {b:.3f} | {a:.3f} | {pct} |")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    print(f"wrote {out} ({len(rows)} metrics)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
