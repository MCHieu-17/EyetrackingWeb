#!/usr/bin/env python3
"""Guarded reset cho database development.

Mặc định là PREVIEW: chỉ đọc và in kế hoạch, không stop/drop/seed.
Muốn áp dụng phải chỉ định đủ:

    ./scripts/reset_db.sh --apply --database eyetracking --confirm-reset eyetracking

Các guard bắt buộc (theo PLAN.md Phase 0):
  1. Docker endpoint là local socket.
  2. Container PostgreSQL thuộc đúng Compose project/service/config/working dir.
  3. Database đích khớp POSTGRES_DB và không phải database hệ thống.
  4. DSN backend khớp database + PostgreSQL đã xác minh.
  5. --database và --confirm-reset trùng khớp.
  6. Tên database được quote bằng identifier của PostgreSQL (psql :"dbname").

Không dùng `docker compose down -v`, không xóa volume, không đụng database khác.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Protocol, Sequence
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = "eyetracking"
SYSTEM_DATABASES = {"postgres", "template0", "template1"}
COMPOSE_PROJECT = "eyelearning"
COMPOSE_SERVICE = "postgres"
CONTAINER_NAME = "eyetracking-postgres"
LOCAL_DOCKER_PREFIXES = ("unix://", "npipe://")
RUNTIME_SERVICES = (
    "backend",
    "chatbot",
    "worker",
    "content-worker",
    "db-maintenance",
)


class GuardError(RuntimeError):
    """Lỗi guard; exit_code dùng cho CLI."""

    def __init__(self, message: str, exit_code: int = 3):
        super().__init__(message)
        self.exit_code = exit_code


@dataclass(frozen=True)
class CommandResult:
    args: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def run(
        self,
        args: Sequence[str],
        *,
        input: str | None = None,
        check: bool = True,
    ) -> CommandResult: ...


class SubprocessRunner:
    def run(
        self,
        args: Sequence[str],
        *,
        input: str | None = None,
        check: bool = True,
    ) -> CommandResult:
        proc = subprocess.run(
            list(args),
            input=input,
            capture_output=True,
            text=True,
            check=False,
        )
        result = CommandResult(tuple(args), proc.returncode, proc.stdout, proc.stderr)
        if check and proc.returncode != 0:
            raise GuardError(
                f"Lệnh thất bại ({proc.returncode}): {shlex.join(args)}\n{proc.stderr.strip()}",
                exit_code=4,
            )
        return result


@dataclass
class Target:
    database: str
    docker_host: str
    compose_project: str
    compose_service: str
    compose_config_files: list[str]
    compose_working_dir: str
    container: str
    container_running: bool
    dsn: str
    dsn_database: str
    dsn_host: str
    dsn_port: int
    db_exists: bool
    db_owner: str | None
    active_connections: int
    app_instance_id: str | None
    postgres_user: str
    postgres_db: str

    @property
    def dsn_redacted(self) -> str:
        parsed = urlparse(self.dsn.replace("postgresql+asyncpg://", "postgresql://"))
        if parsed.password is None:
            return self.dsn
        netloc = parsed.netloc.replace(f":{parsed.password}@", ":***@")
        return parsed._replace(netloc=netloc).geturl()


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _parse_dsn(dsn: str) -> tuple[str, str, int, str, str]:
    normalized = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    parsed = urlparse(normalized)
    if parsed.scheme not in {"postgresql", "postgres"}:
        raise GuardError("DSN backend không phải PostgreSQL.")
    host = parsed.hostname or ""
    port = parsed.port or 5432
    database = unquote(parsed.path.lstrip("/"))
    user = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    return host, database, port, user, password


class ResetGuard:
    def __init__(
        self,
        root: Path = ROOT,
        runner: CommandRunner | None = None,
        env: Mapping[str, str] | None = None,
        out=None,
        err=None,
    ):
        self.root = root.resolve()
        self.runner = runner or SubprocessRunner()
        self.env = dict(os.environ if env is None else env)
        self.out = out or sys.stdout
        self.err = err or sys.stderr

    # ------------------------------------------------------------------
    # Compose helpers
    # ------------------------------------------------------------------
    def _compose(self, *args: str) -> list[str]:
        return [
            "docker",
            "compose",
            "--project-name",
            COMPOSE_PROJECT,
            "--project-directory",
            str(self.root),
            "-f",
            str(self.root / "docker-compose.yml"),
            *args,
        ]

    def _psql(
        self,
        database: str,
        sql: str,
        *,
        variables: Mapping[str, str] | None = None,
        check: bool = True,
    ) -> CommandResult:
        args = self._compose(
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            self._env()["POSTGRES_USER"],
            "-d",
            database,
            "-v",
            "ON_ERROR_STOP=1",
            "-tA",
            "-f",
            "-",
        )
        for key, value in (variables or {}).items():
            args.extend(["-v", f"{key}={value}"])
        return self.runner.run(args, input=sql, check=check)

    def _env(self) -> dict[str, str]:
        values = _parse_env_file(self.root / ".env")
        # Env truyền vào (process/test) được ưu tiên hơn file .env.
        for key in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "DATABASE_URL_DOCKER"):
            if self.env.get(key):
                values[key] = self.env[key]
        for key in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "DATABASE_URL_DOCKER"):
            if not values.get(key):
                raise GuardError(f"Thiếu {key} trong .env.")
        return values

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------
    def _docker_host(self) -> str:
        env_host = self.env.get("DOCKER_HOST", "").strip()
        if env_host:
            if not env_host.startswith(LOCAL_DOCKER_PREFIXES):
                raise GuardError(
                    f"DOCKER_HOST không phải local socket: {env_host}. "
                    "Script chỉ reset Docker local."
                )
            return env_host

        result = self.runner.run(
            ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
            check=False,
        )
        host = result.stdout.strip() if result.returncode == 0 else ""
        if not host:
            host = "unix:///var/run/docker.sock"
        if not host.startswith(LOCAL_DOCKER_PREFIXES):
            raise GuardError(
                f"Docker endpoint không phải local socket: {host}. "
                "Script chỉ reset Docker local."
            )
        return host

    def _compose_labels(self) -> dict[str, str]:
        result = self.runner.run(
            [
                "docker",
                "inspect",
                CONTAINER_NAME,
                "--format",
                "{{json .Config.Labels}}",
            ],
            check=False,
        )
        if result.returncode != 0:
            raise GuardError(
                f"Không tìm thấy container {CONTAINER_NAME}. "
                "Hãy chạy `docker compose up -d postgres` trước."
            )
        try:
            labels = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise GuardError(f"Không đọc được label container {CONTAINER_NAME}.") from exc
        if not isinstance(labels, dict):
            raise GuardError(f"Label container {CONTAINER_NAME} không hợp lệ.")

        running = self.runner.run(
            ["docker", "inspect", CONTAINER_NAME, "--format", "{{.State.Running}}"],
            check=False,
        )
        if running.returncode != 0 or running.stdout.strip().lower() != "true":
            raise GuardError(f"Container {CONTAINER_NAME} không chạy.")

        project = labels.get("com.docker.compose.project", "")
        service = labels.get("com.docker.compose.service", "")
        config_files = labels.get("com.docker.compose.project.config_files", "")
        working_dir = labels.get("com.docker.compose.project.working_dir", "")

        if project != COMPOSE_PROJECT:
            raise GuardError(
                f"Compose project không khớp: {project!r} (cần {COMPOSE_PROJECT!r})."
            )
        if service != COMPOSE_SERVICE:
            raise GuardError(
                f"Compose service không khớp: {service!r} (cần {COMPOSE_SERVICE!r})."
            )
        expected_config = (self.root / "docker-compose.yml").resolve()
        config_paths = [Path(item.strip()).resolve() for item in config_files.split(",") if item.strip()]
        if expected_config not in config_paths:
            raise GuardError(
                f"Compose config không khớp: {config_files!r} "
                f"(cần {str(expected_config)!r})."
            )
        if Path(working_dir).resolve() != self.root:
            raise GuardError(
                f"Compose working dir không khớp: {working_dir!r} (cần {str(self.root)!r})."
            )
        return labels

    def _validate_database(self, database: str, env: Mapping[str, str]) -> None:
        if not database or "\x00" in database or "\n" in database or "\r" in database:
            raise GuardError("Tên database không hợp lệ.")
        if database in SYSTEM_DATABASES:
            raise GuardError(f"Không được reset database hệ thống: {database}.")
        if database != env["POSTGRES_DB"]:
            raise GuardError(
                f"Database đích {database!r} không khớp POSTGRES_DB={env['POSTGRES_DB']!r}."
            )
        if database != DEFAULT_DATABASE:
            raise GuardError(
                f"Script này chỉ reset development database {DEFAULT_DATABASE!r}; "
                f"nhận {database!r}. Không dùng cho test database."
            )

    def _validate_dsn(self, database: str, env: Mapping[str, str]) -> str:
        dsn = env["DATABASE_URL_DOCKER"]
        host, dsn_db, port, user, password = _parse_dsn(dsn)
        if host != "postgres":
            raise GuardError(f"DSN backend host không khớp: {host!r} (cần 'postgres').")
        if port != 5432:
            raise GuardError(f"DSN backend port không khớp: {port} (cần 5432).")
        if dsn_db != database:
            raise GuardError(
                f"DSN backend database không khớp: {dsn_db!r} (cần {database!r})."
            )
        if user != env["POSTGRES_USER"]:
            raise GuardError("DSN backend user không khớp POSTGRES_USER.")
        if password != env["POSTGRES_PASSWORD"]:
            raise GuardError("DSN backend password không khớp POSTGRES_PASSWORD.")
        return dsn

    def _db_info(self, database: str) -> tuple[bool, str | None, int]:
        sql = """
SELECT json_build_object(
  'exists', EXISTS (SELECT 1 FROM pg_database WHERE datname = :'dbname'),
  'owner', (SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = :'dbname'),
  'connections', (
      SELECT count(*) FROM pg_stat_activity
      WHERE datname = :'dbname' AND pid <> pg_backend_pid()
  )
);
"""
        result = self._psql("postgres", sql, variables={"dbname": database})
        try:
            payload = json.loads(result.stdout.strip())
        except json.JSONDecodeError as exc:
            raise GuardError("Không đọc được thông tin database đích.") from exc
        return bool(payload["exists"]), payload.get("owner"), int(payload["connections"])

    def _app_instance_id(self, database: str) -> str | None:
        sql = """
SELECT CASE
  WHEN to_regclass('public.app_metadata') IS NULL THEN NULL
  ELSE (SELECT value FROM app_metadata WHERE key = 'db_instance_id')
END;
"""
        result = self._psql(database, sql, check=False)
        if result.returncode != 0:
            return None
        value = result.stdout.strip()
        return value or None

    def inspect(self, database: str | None = None) -> Target:
        env = self._env()
        database = database or env["POSTGRES_DB"]
        self._validate_database(database, env)
        docker_host = self._docker_host()
        labels = self._compose_labels()
        dsn = self._validate_dsn(database, env)
        exists, owner, connections = self._db_info(database)
        if exists and owner and owner != env["POSTGRES_USER"]:
            raise GuardError(
                f"Database {database!r} thuộc owner {owner!r}, không xác định ownership. "
                "Dừng để tránh drop nhầm."
            )
        instance_id = self._app_instance_id(database) if exists else None
        return Target(
            database=database,
            docker_host=docker_host,
            compose_project=labels.get("com.docker.compose.project", ""),
            compose_service=labels.get("com.docker.compose.service", ""),
            compose_config_files=[
                item.strip()
                for item in labels.get("com.docker.compose.project.config_files", "").split(",")
                if item.strip()
            ],
            compose_working_dir=labels.get("com.docker.compose.project.working_dir", ""),
            container=CONTAINER_NAME,
            container_running=True,
            dsn=dsn,
            dsn_database=database,
            dsn_host="postgres",
            dsn_port=5432,
            db_exists=exists,
            db_owner=owner,
            active_connections=connections,
            app_instance_id=instance_id,
            postgres_user=env["POSTGRES_USER"],
            postgres_db=env["POSTGRES_DB"],
        )

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------
    def preview(self, database: str | None = None) -> Target:
        target = self.inspect(database)
        print("=== RESET PREVIEW (không thay đổi gì) ===", file=self.out)
        print(f"Docker endpoint : {target.docker_host}", file=self.out)
        print(f"Compose project : {target.compose_project}", file=self.out)
        print(f"Compose service : {target.compose_service}", file=self.out)
        print(f"Compose config  : {', '.join(target.compose_config_files)}", file=self.out)
        print(f"Working dir     : {target.compose_working_dir}", file=self.out)
        print(f"Container       : {target.container} (running)", file=self.out)
        print(f"Target database : {target.database}", file=self.out)
        print(f"Owner           : {target.db_owner or '<chưa tồn tại>'}", file=self.out)
        print(f"Connections     : {target.active_connections}", file=self.out)
        print(f"Backend DSN     : {target.dsn_redacted}", file=self.out)
        print(f"DB instance ID  : {target.app_instance_id or '<chưa có>'}", file=self.out)
        print("", file=self.out)
        print("Kế hoạch khi --apply:", file=self.out)
        print("  1. stop backend/chatbot/worker/db-maintenance (nếu có)", file=self.out)
        print("  2. kiểm tra không còn kết nối lạ tới database đích", file=self.out)
        print("  3. drop/recreate database đích (ngoài transaction)", file=self.out)
        print("  4. chạy 001_baseline.sql + 002_reference_seed.sql", file=self.out)
        print("  5. chạy grants cho chatbot role", file=self.out)
        print("  6. tạo app_metadata.db_instance_id mới", file=self.out)
        print("  7. (tùy chọn) seed development", file=self.out)
        print("  8. smoke test schema", file=self.out)
        print("  9. start runtime", file=self.out)
        print("", file=self.out)
        print("Để áp dụng:", file=self.out)
        print(
            f"  ./scripts/reset_db.sh --apply --database {target.database} "
            f"--confirm-reset {target.database}",
            file=self.out,
        )
        return target

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------
    def _runtime_services(self) -> list[str]:
        result = self.runner.run(self._compose("config", "--services"), check=False)
        if result.returncode != 0:
            return list(RUNTIME_SERVICES)
        available = {line.strip() for line in result.stdout.splitlines() if line.strip()}
        return [name for name in RUNTIME_SERVICES if name in available]

    def _stop_runtime(self) -> list[str]:
        services = self._runtime_services()
        if services:
            self.runner.run(self._compose("stop", *services))
        return services

    def _start_runtime(self, services: Sequence[str]) -> None:
        if services:
            # Dùng image/config mới nhất, không start lại container cũ.
            self.runner.run(
                self._compose("up", "-d", "--force-recreate", *services)
            )

    def _check_connections(self, database: str) -> None:
        sql = """
SELECT coalesce(json_agg(row_to_json(t)), '[]'::json)
FROM (
  SELECT usename, application_name, client_addr::text, state
  FROM pg_stat_activity
  WHERE datname = :'dbname' AND pid <> pg_backend_pid()
) t;
"""
        result = self._psql("postgres", sql, variables={"dbname": database})
        try:
            rows = json.loads(result.stdout.strip() or "[]")
        except json.JSONDecodeError as exc:
            raise GuardError("Không đọc được danh sách kết nối.") from exc
        if rows:
            detail = ", ".join(
                f"{row.get('usename')}@{row.get('client_addr') or 'local'}"
                f"({row.get('application_name') or '?'})"
                for row in rows
            )
            raise GuardError(
                f"Còn {len(rows)} kết nối tới {database!r}: {detail}. "
                "Dừng để tránh drop database đang được dùng."
            )

    def _drop_create(self, database: str) -> None:
        sql = """
DROP DATABASE IF EXISTS :"dbname";
CREATE DATABASE :"dbname";
"""
        self._psql("postgres", sql, variables={"dbname": database})

    def _run_migrations(self) -> None:
        self.runner.run(self._compose("run", "--rm", "migrate"))

    def _run_grants(self) -> None:
        script = self.root / "ops" / "create_chatbot_role.sh"
        if script.is_file():
            self.runner.run(["bash", str(script)])

    def _create_instance_id(self, database: str) -> str:
        instance_id = str(uuid.uuid4())
        sql = """
INSERT INTO app_metadata (key, value)
VALUES ('db_instance_id', :'instance_id'),
       ('schema_generation', '1')
ON CONFLICT (key) DO UPDATE
SET value = EXCLUDED.value, updated_at = now();
"""
        self._psql(database, sql, variables={"instance_id": instance_id})
        return instance_id

    def _seed_dev(self, database: str) -> None:
        seed = self.root / "db" / "seed_dev_users.sql"
        if not seed.is_file():
            raise GuardError(f"Không thấy file seed: {seed}")
        self._psql(database, seed.read_text(encoding="utf-8"))

    def _smoke(self, database: str) -> None:
        sql = """
SELECT json_build_object(
  'migrations', (SELECT count(*) FROM schema_migrations),
  'roles', (SELECT count(*) FROM roles),
  'core_tables', (
      SELECT count(*) FROM pg_tables
      WHERE schemaname = 'public'
        AND tablename IN ('users', 'courses', 'course_versions', 'gaze_samples')
  ),
  'instance_id', (SELECT value FROM app_metadata WHERE key = 'db_instance_id')
);
"""
        result = self._psql(database, sql)
        try:
            payload = json.loads(result.stdout.strip())
        except json.JSONDecodeError as exc:
            raise GuardError("Smoke test schema thất bại: output không hợp lệ.", exit_code=5) from exc
        if int(payload.get("migrations", 0)) < 2:
            raise GuardError("Smoke test: baseline/reference seed chưa được áp.", exit_code=5)
        if int(payload.get("roles", 0)) < 3:
            raise GuardError("Smoke test: reference seed thiếu roles.", exit_code=5)
        if int(payload.get("core_tables", 0)) != 4:
            raise GuardError("Smoke test: thiếu bảng lõi của baseline.", exit_code=5)
        if not payload.get("instance_id"):
            raise GuardError("Smoke test: thiếu app_metadata.db_instance_id.", exit_code=5)

    def apply(self, database: str, confirm: str, seed_dev: bool = False) -> Target:
        if database != confirm:
            raise GuardError(
                "--database và --confirm-reset phải trùng nhau.", exit_code=2
            )
        target = self.inspect(database)
        print("=== RESET APPLY ===", file=self.out)
        print(f"Target database : {target.database}", file=self.out)
        print(f"Backend DSN     : {target.dsn_redacted}", file=self.out)

        services = self._stop_runtime()
        print(f"Đã stop runtime : {', '.join(services) or '<không có>'}", file=self.out)
        self._check_connections(database)
        print("Không còn kết nối lạ.", file=self.out)

        self._drop_create(database)
        print(f"Đã drop/recreate {database}.", file=self.out)

        self._run_migrations()
        print("Đã chạy baseline + reference seed.", file=self.out)

        self._run_grants()
        print("Đã chạy grants.", file=self.out)

        instance_id = self._create_instance_id(database)
        print(f"DB instance ID  : {instance_id}", file=self.out)

        if seed_dev:
            self._seed_dev(database)
            print("Đã seed development.", file=self.out)

        self._smoke(database)
        print("Smoke test schema: OK.", file=self.out)

        self._start_runtime(services)
        print(f"Đã start runtime: {', '.join(services) or '<không có>'}", file=self.out)
        print("OK: reset hoàn tất.", file=self.out)
        return target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Guarded reset cho database development (mặc định preview)."
    )
    parser.add_argument("--apply", action="store_true", help="Áp dụng reset (mặc định chỉ preview).")
    parser.add_argument("--database", default=None, help="Tên database đích (mặc định POSTGRES_DB).")
    parser.add_argument(
        "--confirm-reset",
        default=None,
        help="Phải trùng --database để xác nhận reset.",
    )
    parser.add_argument("--seed-dev", action="store_true", help="Seed tài khoản development sau reset.")
    parser.add_argument("--json", action="store_true", help="In target dưới dạng JSON (preview).")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    guard = ResetGuard()
    try:
        if args.apply:
            if not args.database or not args.confirm_reset:
                raise GuardError(
                    "Chế độ --apply bắt buộc có --database và --confirm-reset.",
                    exit_code=2,
                )
            guard.apply(args.database, args.confirm_reset, seed_dev=args.seed_dev)
        else:
            target = guard.preview(args.database)
            if args.json:
                print(json.dumps(target.__dict__, ensure_ascii=False, indent=2, default=str))
        return 0
    except GuardError as exc:
        print(f"LỖI: {exc}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
