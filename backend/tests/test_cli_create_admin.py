"""Test CLI tạo admin/teacher cho production."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.cli.create_admin import _upsert_user
from app.core import security
from app.db.session import SessionLocal
from app.models.auth import User
from app.models.profile import TeacherProfile


@pytest.mark.asyncio
async def test_create_admin_and_teacher_with_password_and_profile():
    suffix = uuid.uuid4().hex[:8]
    admin_email = f"cli-admin-{suffix}@example.com"
    teacher_email = f"cli-teacher-{suffix}@example.com"

    await _upsert_user(
        email=admin_email,
        name="CLI Admin",
        role="admin",
        password="AdminPass123!",
        department=None,
        force=False,
    )
    await _upsert_user(
        email=teacher_email,
        name="CLI Teacher",
        role="teacher",
        password="TeacherPass123!",
        department="Khoa CNTT",
        force=False,
    )

    async with SessionLocal() as db:
        admin = (
            await db.execute(select(User).where(User.email == admin_email))
        ).scalar_one()
        teacher = (
            await db.execute(select(User).where(User.email == teacher_email))
        ).scalar_one()
        profile = await db.get(TeacherProfile, teacher.id)

    assert admin.role == "admin"
    assert admin.status == "active"
    assert admin.email_verified_at is not None
    assert security.verify_password("AdminPass123!", admin.password_hash)
    assert teacher.role == "teacher"
    assert profile is not None
    assert profile.department == "Khoa CNTT"
    assert security.verify_password("TeacherPass123!", teacher.password_hash)


@pytest.mark.asyncio
async def test_create_admin_force_updates_existing_user():
    suffix = uuid.uuid4().hex[:8]
    email = f"cli-force-{suffix}@example.com"

    await _upsert_user(
        email=email,
        name="First",
        role="teacher",
        password="FirstPass123!",
        department=None,
        force=False,
    )
    await _upsert_user(
        email=email,
        name="Second",
        role="admin",
        password="SecondPass123!",
        department=None,
        force=True,
    )

    async with SessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.email == email))
        ).scalar_one()

    assert user.role == "admin"
    assert user.full_name == "Second"
    assert security.verify_password("SecondPass123!", user.password_hash)
    assert not security.verify_password("FirstPass123!", user.password_hash)
