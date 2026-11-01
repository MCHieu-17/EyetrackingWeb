#!/usr/bin/env python3
"""So sánh biến trong `.env.example` với biến code/compose thực sự đọc.

Mục đích: phát hiện sớm biến stale (có trong .env.example nhưng không ai đọc)
và biến thiếu (code đọc nhưng chưa có trong .env.example).

Chạy: python scripts/check_env_example.py
Exit code luôn 0 (cảnh báo, không chặn CI) — xem output để dọn dần.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = ROOT / ".env.example"

# Biến do runtime/framework tự set hoặc chỉ dùng trong CI — không cần .env.example.
IGNORE = {
    "TESTING",
    "WEIGHTS_DIR",
    "NEXT_STANDALONE",
    "NODE_ENV",
    "PORT",
    "HOSTNAME",
    "PYTHONUNBUFFERED",
    "PYTHONDONTWRITEBYTECODE",
    "PATH",
    "HOME",
    "TZ",
    "APP_NAME",
    # Biến nội bộ compose/container, không đặt trong .env.
    "BACKEND_INTERNAL_URL",
    "API_URL",
    "GAZE_URL",
}

# Biến đọc qua bảng ánh xạ chuỗi (không phải os.getenv("TÊN")).
MANUAL_USED = {"S3_BUCKET", "S3_PREFIX"}

# Field pydantic-settings có default, là tuỳ chọn tinh chỉnh — không cần đưa vào
# .env.example để tránh phình file.
OPTIONAL_SETTINGS = {
    "AGGREGATE_REFRESH_THROTTLE_SECONDS",
    "COOKIE_DOMAIN",
    "HEATMAP_CACHE_TTL_SECONDS",
    "MASTERY_AOI_PADDING",
    "MASTERY_COVERAGE_THRESHOLD",
    "MASTERY_GRID_COLS",
    "MASTERY_GRID_ROWS",
    "MASTERY_KEY_WEIGHT",
    "MASTERY_MAX_DWELL_MS",
    "MASTERY_MIN_AOI_DWELL_MS",
    "MAX_PDF_BYTES",
    "MAX_PDF_PAGES",
    "MAX_SLIDE_RENDER_PIXELS",
    "MEDIA_DIR",
    "MIN_SAMPLES",
}

SCAN_DIRS = [
    ROOT / "backend" / "app",
    ROOT / "services" / "gaze" / "app",
    ROOT / "services" / "gaze" / "scripts",
    ROOT / "services" / "chatbot" / "app",
    ROOT / "services" / "chatbot" / "scripts",
    ROOT / "frontend" / "app",
    ROOT / "frontend" / "components",
    ROOT / "frontend" / "lib",
    ROOT / "frontend" / "hooks",
]
SCAN_FILES = [
    ROOT / "docker-compose.yml",
    ROOT / "frontend" / "next.config.ts",
    ROOT / "frontend" / "Dockerfile",
    ROOT / "nginx" / "default.conf",
]

GETENV_PATTERNS = [
    re.compile(r"""os\.getenv\(\s*["']([A-Z][A-Z0-9_]+)["']"""),
    re.compile(r"""os\.environ\.get\(\s*["']([A-Z][A-Z0-9_]+)["']"""),
    re.compile(r"""os\.environ\[\s*["']([A-Z][A-Z0-9_]+)["']"""),
    re.compile(r"""process\.env\.([A-Z][A-Z0-9_]+)"""),
    re.compile(r"""process\.env\[\s*["']([A-Z][A-Z0-9_]+)["']"""),
]
COMPOSE_RE = re.compile(r"\$\{([A-Z][A-Z0-9_]+)")
# Field pydantic-settings: `    database_url: str` -> DATABASE_URL.
PYDANTIC_FIELD_RE = re.compile(r"^    ([a-z][a-z0-9_]*)\s*:\s*[^=\n]+(?:=|$)", re.MULTILINE)


def env_example_keys() -> set[str]:
    keys: set[str] = set()
    for path in (ENV_EXAMPLE, ROOT / "frontend" / ".env.example"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            keys.add(line.split("=", 1)[0].strip())
    return keys


def code_keys() -> set[str]:
    keys: set[str] = set()
    for directory in SCAN_DIRS:
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if path.suffix not in {".py", ".ts", ".tsx", ".js"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in GETENV_PATTERNS:
                keys.update(pattern.findall(text))
    for path in SCAN_FILES:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        keys.update(COMPOSE_RE.findall(text))
        for pattern in GETENV_PATTERNS:
            keys.update(pattern.findall(text))

    # pydantic-settings đọc field theo tên (case-insensitive).
    config = ROOT / "backend" / "app" / "core" / "config.py"
    if config.is_file():
        keys.update(
            name.upper()
            for name in PYDANTIC_FIELD_RE.findall(config.read_text(encoding="utf-8"))
        )
    return (keys | MANUAL_USED) - IGNORE - OPTIONAL_SETTINGS


def main() -> int:
    if not ENV_EXAMPLE.is_file():
        print("Không thấy .env.example", file=sys.stderr)
        return 0

    documented = env_example_keys()
    used = code_keys()

    stale = sorted(documented - used)
    missing = sorted(used - documented)

    if stale:
        print("CẢNH BÁO — có trong .env.example nhưng không code/compose nào đọc:")
        for key in stale:
            print(f"  - {key}")
    if missing:
        print("CẢNH BÁO — code/compose đọc nhưng thiếu trong .env.example:")
        for key in missing:
            print(f"  - {key}")
    if not stale and not missing:
        print("OK: .env.example khớp với biến code/compose đang đọc.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
