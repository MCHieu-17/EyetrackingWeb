"""Tạo/cập nhật tài khoản admin hoặc teacher cho production.

Chạy trong container backend (Portainer → Containers → backend → Console):

    python -m app.cli.create_admin \
        --email admin@example.com \
        --name "Quản trị viên" \
        --role admin

Mật khẩu sẽ được hỏi bằng getpass, không lưu vào shell history. Có thể truyền
`--password` cho script không tương tác, nhưng phải cẩn thận log/history.

Không dùng script này để tạo hàng loạt sinh viên; sinh viên tự đăng ký OTP.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.models.auth import User
from app.models.profile import TeacherProfile

MIN_PASSWORD_LENGTH = 8


def _prompt_password(explicit: str | None) -> str:
    if explicit is not None:
        password = explicit
    else:
        password = getpass.getpass("Mật khẩu: ")
        confirm = getpass.getpass("Nhập lại mật khẩu: ")
        if password != confirm:
            raise SystemExit("Mật khẩu nhập lại không khớp.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(
            f"Mật khẩu phải dài ít nhất {MIN_PASSWORD_LENGTH} ký tự."
        )
    return password


async def _upsert_user(
    *,
    email: str,
    name: str,
    role: str,
    password: str,
    department: str | None,
    force: bool,
) -> None:
    normalized_email = email.strip().lower()
    if "@" not in normalized_email:
        raise SystemExit(f"Email không hợp lệ: {email}")

    async with SessionLocal() as db:
        user = (
            await db.execute(
                select(User).where(func.lower(User.email) == normalized_email)
            )
        ).scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if user is None:
            user = User(
                email=normalized_email,
                password_hash=hash_password(password),
                role=role,
                status="active",
                full_name=name,
                email_verified_at=now,
            )
            db.add(user)
            await db.flush()
            await db.refresh(user)
            action = "Đã tạo"
        else:
            if not force:
                raise SystemExit(
                    f"User {normalized_email} đã tồn tại. Dùng --force để cập nhật."
                )
            user.password_hash = hash_password(password)
            user.role = role
            user.status = "active"
            user.full_name = name
            user.deleted_at = None
            user.email_verified_at = now
            action = "Đã cập nhật"

        if role == "teacher":
            profile = await db.get(TeacherProfile, user.id)
            if profile is None:
                db.add(
                    TeacherProfile(
                        user_id=user.id,
                        teacher_code=f"T{user.id[:8].upper()}",
                        department=department,
                    )
                )
            elif department is not None:
                profile.department = department

        await db.commit()
        print(f"{action} {role}: {normalized_email} (id={user.id})")


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tạo/cập nhật tài khoản admin hoặc teacher."
    )
    parser.add_argument("--email", required=True, help="Email đăng nhập")
    parser.add_argument(
        "--name",
        default=None,
        help="Họ tên hiển thị (mặc định lấy phần trước @ của email)",
    )
    parser.add_argument(
        "--role",
        choices=("admin", "teacher"),
        default="admin",
        help="Role cần tạo (mặc định admin)",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Mật khẩu; bỏ trống để nhập bằng getpass",
    )
    parser.add_argument(
        "--department",
        default=None,
        help="Khoa/bộ môn (chỉ dùng cho teacher)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Cập nhật nếu email đã tồn tại",
    )
    return parser.parse_args(argv)


async def _main(argv: list[str]) -> None:
    args = _parse_args(argv)
    password = _prompt_password(args.password)
    name = (args.name or args.email.split("@", 1)[0]).strip() or args.email
    try:
        await _upsert_user(
            email=args.email,
            name=name,
            role=args.role,
            password=password,
            department=args.department,
            force=args.force,
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main(sys.argv[1:]))
