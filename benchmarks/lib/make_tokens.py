#!/usr/bin/env python3
"""Sinh access token benchmark từ user IDs trong fixtures.json.

Chạy trong image backend:
    docker compose ... exec -T backend \
      python /bench/lib/make_tokens.py --fixtures ... --out .../.runtime/tokens.json

File output chứa token thật; chỉ ghi vào `.runtime/` đã gitignore.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import jwt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--ttl-seconds", type=int, default=86400)
    args = parser.parse_args()

    secret = os.environ.get("JWT_SECRET", "")
    algorithm = os.environ.get("JWT_ALGORITHM", "HS256")
    if not secret:
        raise SystemExit("Thiếu JWT_SECRET")

    fixtures = json.loads(Path(args.fixtures).read_text(encoding="utf-8"))
    ids = fixtures["ids"]
    now = int(time.time())

    def token(user_id: str) -> str:
        return jwt.encode(
            {
                "sub": user_id,
                "type": "access",
                "iat": now,
                "exp": now + args.ttl_seconds,
            },
            secret,
            algorithm=algorithm,
        )

    out = {
        "admin": {"user_id": ids["admin_id"], "token": token(ids["admin_id"])},
        "teacher": {"user_id": ids["teacher_id"], "token": token(ids["teacher_id"])},
        "student": {
            "user_id": fixtures["student_ids"][0],
            "token": token(fixtures["student_ids"][0]),
        },
        "students": [
            {"index": i, "user_id": uid, "token": token(uid)}
            for i, uid in enumerate(fixtures["student_ids"])
        ],
        "ids": ids,
    }
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    target.chmod(0o644)
    print(f"wrote {target} ({len(out['students'])} student tokens)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
