"""Phase 1 schema gate: ORM metadata phải khớp catalog PostgreSQL.

Chạy sau khi dựng test DB bằng `./scripts/test_db.sh`.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import NullType

from app.db.base import Base
from app.db.session import engine
import app.models  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
DIALECT = postgresql.dialect()
IGNORED_TABLES = {"schema_migrations"}
PARTITION_PREFIX = "gaze_samples_"


def _norm_type(value) -> str:
    text_value = str(value).lower()
    text_value = text_value.replace("character varying", "varchar")
    text_value = text_value.replace("timestamp with time zone", "timestamptz")
    text_value = text_value.replace("timestamp without time zone", "timestamp")
    text_value = text_value.replace("double precision", "double")
    return text_value


def _norm_default(value) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    if text_value.startswith("nextval("):
        return None
    text_value = re.sub(r"::[a-zA-Z_ ]+(\[\])?$", "", text_value)
    return text_value.strip("'").lower()


def _db_tables(insp) -> set[str]:
    return {
        name
        for name in insp.get_table_names()
        if name not in IGNORED_TABLES and not name.startswith(PARTITION_PREFIX)
    }


def _run(coro):
    return asyncio.run(coro)


async def _inspect_all():
    async with engine.connect() as conn:
        def collect(sync_conn):
            insp = inspect(sync_conn)
            tables = _db_tables(insp)
            data = {
                "tables": tables,
                "columns": {},
                "pk": {},
                "fk": {},
                "uq": {},
                "ck": {},
                "idx": {},
            }
            for name in tables:
                data["columns"][name] = insp.get_columns(name)
                data["pk"][name] = insp.get_pk_constraint(name)
                data["fk"][name] = insp.get_foreign_keys(name)
                data["uq"][name] = insp.get_unique_constraints(name)
                data["ck"][name] = insp.get_check_constraints(name)
                data["idx"][name] = insp.get_indexes(name)
            return data

        return await conn.run_sync(collect)


@pytest.fixture(scope="module")
def catalog():
    return _run(_inspect_all())


def test_tables_match_orm(catalog):
    meta_tables = set(Base.metadata.tables)
    assert catalog["tables"] == meta_tables


def test_columns_types_nullable_defaults_match_orm(catalog):
    problems: list[str] = []
    for name, table in Base.metadata.tables.items():
        db_cols = {c["name"]: c for c in catalog["columns"][name]}
        for col in table.columns:
            db = db_cols.get(col.name)
            if db is None:
                problems.append(f"{name}.{col.name}: thiếu trong DB")
                continue
            if not isinstance(db["type"], NullType):
                db_type = _norm_type(db["type"].compile(dialect=DIALECT))
                meta_type = _norm_type(col.type.compile(dialect=DIALECT))
                if db_type != meta_type:
                    problems.append(
                        f"{name}.{col.name}: type db={db_type} meta={meta_type}"
                    )
            if bool(db["nullable"]) != bool(col.nullable):
                problems.append(
                    f"{name}.{col.name}: nullable db={db['nullable']} meta={col.nullable}"
                )
            db_default = _norm_default(db.get("default"))
            meta_default = _norm_default(
                col.server_default.arg if col.server_default is not None else None
            )
            if db_default != meta_default:
                problems.append(
                    f"{name}.{col.name}: default db={db_default!r} meta={meta_default!r}"
                )
    assert not problems, "\n".join(problems)


def test_primary_keys_match_orm(catalog):
    problems: list[str] = []
    for name, table in Base.metadata.tables.items():
        db_pk = set(catalog["pk"][name]["constrained_columns"])
        meta_pk = set(table.primary_key.columns.keys())
        if db_pk != meta_pk:
            problems.append(f"{name}: db={sorted(db_pk)} meta={sorted(meta_pk)}")
    assert not problems, "\n".join(problems)


def test_foreign_keys_match_orm(catalog):
    problems: list[str] = []
    for name, table in Base.metadata.tables.items():
        db_fks = {
            (
                tuple(fk["constrained_columns"]),
                fk["referred_table"],
                tuple(fk["referred_columns"]),
            )
            for fk in catalog["fk"][name]
            if not fk["referred_table"].startswith(PARTITION_PREFIX)
        }
        meta_fks = set()
        for fk in table.foreign_key_constraints:
            meta_fks.add(
                (
                    tuple(fk.column_keys),
                    fk.elements[0].column.table.name,
                    tuple(element.column.name for element in fk.elements),
                )
            )
        if db_fks != meta_fks:
            problems.append(
                f"{name}: db_only={sorted(db_fks - meta_fks)} "
                f"meta_only={sorted(meta_fks - db_fks)}"
            )
    assert not problems, "\n".join(problems)


def test_unique_constraints_match_orm(catalog):
    problems: list[str] = []
    for name, table in Base.metadata.tables.items():
        db_uqs = {tuple(uq["column_names"]) for uq in catalog["uq"][name]}
        meta_uqs = {
            tuple(constraint.columns.keys())
            for constraint in table.constraints
            if constraint.__class__.__name__ == "UniqueConstraint"
        }
        if db_uqs != meta_uqs:
            problems.append(
                f"{name}: db_only={sorted(db_uqs - meta_uqs)} "
                f"meta_only={sorted(meta_uqs - db_uqs)}"
            )
    assert not problems, "\n".join(problems)


def test_check_constraints_match_orm(catalog):
    problems: list[str] = []
    for name, table in Base.metadata.tables.items():
        db_checks = {ck["name"] for ck in catalog["ck"][name]}
        meta_checks = {
            constraint.name
            for constraint in table.constraints
            if constraint.__class__.__name__ == "CheckConstraint"
        }
        if db_checks != meta_checks:
            problems.append(
                f"{name}: db_only={sorted(db_checks - meta_checks)} "
                f"meta_only={sorted(meta_checks - db_checks)}"
            )
    assert not problems, "\n".join(problems)


def test_indexes_match_orm(catalog):
    problems: list[str] = []
    for name, table in Base.metadata.tables.items():
        db_indexes = {idx["name"]: idx for idx in catalog["idx"][name]}
        db_uq_cols = {tuple(uq["column_names"]) for uq in catalog["uq"][name]}
        meta_indexes = {idx.name: idx for idx in table.indexes}

        # Unique constraint indexes are reported by get_indexes; bỏ qua chúng.
        filtered = {
            key: value
            for key, value in db_indexes.items()
            if not (
                value["unique"]
                and tuple(value["column_names"]) in db_uq_cols
                and key not in meta_indexes
            )
        }
        if set(filtered) != set(meta_indexes):
            problems.append(
                f"{name}: db_only={sorted(set(filtered) - set(meta_indexes))} "
                f"meta_only={sorted(set(meta_indexes) - set(filtered))}"
            )
            continue
        for key in set(filtered) & set(meta_indexes):
            db_cols = tuple(filtered[key]["column_names"])
            meta_cols = tuple(col.name for col in meta_indexes[key].columns)
            # Expression index (lower(email)) không có column name trong inspector.
            if db_cols == (None,) and not meta_cols:
                continue
            if db_cols != meta_cols:
                problems.append(
                    f"{name}.{key}: columns db={db_cols} meta={meta_cols}"
                )
            if bool(filtered[key]["unique"]) != bool(meta_indexes[key].unique):
                problems.append(
                    f"{name}.{key}: unique db={filtered[key]['unique']} "
                    f"meta={meta_indexes[key].unique}"
                )
    assert not problems, "\n".join(problems)


def test_reference_seed(catalog):
    async def check():
        async with engine.connect() as conn:
            roles = (
                await conn.execute(text("SELECT count(*) FROM roles"))
            ).scalar_one()
            settings = (
                await conn.execute(text("SELECT count(*) FROM calibration_settings"))
            ).scalar_one()
            generation = (
                await conn.execute(
                    text("SELECT value FROM app_metadata WHERE key = 'schema_generation'")
                )
            ).scalar_one_or_none()
            return roles, settings, generation

    roles, settings, generation = _run(check())
    assert roles == 3
    assert settings == 1
    assert generation == "1"


def test_migration_checksums_match_files(catalog):
    async def check():
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text("SELECT filename, checksum FROM schema_migrations ORDER BY filename")
                )
            ).all()
            return rows

    rows = _run(check())
    assert [row[0] for row in rows] == ["001_baseline.sql", "002_reference_seed.sql"]
    import hashlib

    for filename, checksum in rows:
        path = ROOT / "db" / "migrations" / filename
        assert hashlib.sha256(path.read_bytes()).hexdigest() == checksum


def test_gaze_samples_partitioned(catalog):
    async def check():
        async with engine.connect() as conn:
            partitioned = (
                await conn.execute(
                    text(
                        "SELECT relkind FROM pg_class WHERE oid = 'gaze_samples'::regclass"
                    )
                )
            ).scalar_one()
            partitions = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM pg_inherits "
                        "WHERE inhparent = 'gaze_samples'::regclass"
                    )
                )
            ).scalar_one()
            return partitioned, partitions

    partitioned, partitions = _run(check())
    assert partitioned in ("p", b"p")
    assert partitions >= 2  # default + ít nhất một tháng


def test_views_exist(catalog):
    async def check():
        async with engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT table_name FROM information_schema.views "
                        "WHERE table_schema = 'public' ORDER BY 1"
                    )
                )
            ).scalars().all()
            return set(rows)

    views = _run(check())
    assert {
        "v_published_course_outline",
        "v_chatbot_slide_documents",
        "v_session_metrics",
        "v_lesson_version_metrics",
        "v_class_heatmap",
    } <= views


def test_immutability_triggers(catalog):
    """Published version / calibration / submitted attempt phải bất biến."""

    async def check():
        async with engine.connect() as conn:
            trans = await conn.begin()
            try:
                await conn.execute(text("TRUNCATE TABLE users, courses CASCADE"))
                user_id = (
                    await conn.execute(
                        text(
                            "INSERT INTO users (email, status) "
                            "VALUES ('trigger@test.local', 'active') RETURNING id"
                        )
                    )
                ).scalar_one()
                await conn.execute(
                    text(
                        "INSERT INTO teacher_profiles (user_id, teacher_code) "
                        "VALUES (:uid, 'GV-TRIGGER')"
                    ),
                    {"uid": user_id},
                )
                course_id = (
                    await conn.execute(
                        text(
                            "INSERT INTO courses (owner_id, created_by) "
                            "VALUES (:uid, :uid) RETURNING id"
                        ),
                        {"uid": user_id},
                    )
                ).scalar_one()
                version_id = (
                    await conn.execute(
                        text(
                            "INSERT INTO course_versions "
                            "(course_id, version_no, state, title, created_by) "
                            "VALUES (:cid, 1, 'published', 'V1', :uid) RETURNING id"
                        ),
                        {"cid": course_id, "uid": user_id},
                    )
                ).scalar_one()
                with pytest.raises(Exception):
                    await conn.execute(
                        text(
                            "UPDATE course_versions SET title = 'changed' "
                            "WHERE id = :vid"
                        ),
                        {"vid": version_id},
                    )
            finally:
                if trans.is_active:
                    await trans.rollback()

    _run(check())
