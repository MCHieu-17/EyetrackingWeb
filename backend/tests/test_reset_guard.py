"""Phase 0 guard tests — không chạm Docker/DB thật.

Dùng process adapter giả lập: mọi lệnh docker/psql được ghi lại, không thực thi.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.reset_db import (  # noqa: E402
    CommandResult,
    GuardError,
    ResetGuard,
)


class FakeRunner:
    def __init__(self, responses):
        self.responses = responses
        self.calls: list[tuple[tuple[str, ...], str | None]] = []

    def run(self, args, *, input=None, check=True):
        args = tuple(args)
        self.calls.append((args, input))
        for predicate, result in self.responses:
            if predicate(args, input):
                if callable(result):
                    result = result(args, input)
                if check and result.returncode != 0:
                    raise GuardError(
                        f"Lệnh thất bại ({result.returncode}): {' '.join(args)}\n{result.stderr}",
                        exit_code=4,
                    )
                return result
        return CommandResult(args, 0, "", "")

    def called(self, *needles: str) -> bool:
        return any(all(n in " ".join(args) for n in needles) for args, _ in self.calls)

    def psql_inputs(self) -> list[str]:
        return [sql or "" for args, sql in self.calls if "psql" in args]


def _ok(args, stdout=""):
    return CommandResult(tuple(args), 0, stdout, "")


def _labels(root: Path, **overrides):
    labels = {
        "com.docker.compose.project": "eyelearning",
        "com.docker.compose.service": "postgres",
        "com.docker.compose.project.config_files": str(root / "docker-compose.yml"),
        "com.docker.compose.project.working_dir": str(root),
    }
    labels.update(overrides)
    return json.dumps(labels)


def _db_info(exists=True, owner="postgres", connections=0):
    return json.dumps(
        {"exists": exists, "owner": owner if exists else None, "connections": connections}
    )


def _make_guard(tmp_path: Path, *, labels=None, db_info=None, connections=None, smoke=None, env=None):
    (tmp_path / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    (tmp_path / "db").mkdir(exist_ok=True)
    (tmp_path / "db" / "seed_dev_users.sql").write_text("-- seed\n", encoding="utf-8")
    (tmp_path / "ops").mkdir(exist_ok=True)
    (tmp_path / "ops" / "create_chatbot_role.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "POSTGRES_USER=postgres",
                "POSTGRES_PASSWORD=secret",
                "POSTGRES_DB=eyetracking",
                "DATABASE_URL_DOCKER=postgresql+asyncpg://postgres:secret@postgres:5432/eyetracking",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    labels_json = labels if labels is not None else _labels(tmp_path)
    db_info_json = db_info if db_info is not None else _db_info()
    connections_json = connections if connections is not None else "[]"
    smoke_json = smoke if smoke is not None else json.dumps(
        {"migrations": 2, "roles": 3, "core_tables": 4, "instance_id": "instance-1"}
    )

    def is_context(args, _input):
        return args[:3] == ("docker", "context", "inspect")

    def is_labels(args, _input):
        return args[:2] == ("docker", "inspect") and "Config.Labels" in " ".join(args)

    def is_running(args, _input):
        return args[:2] == ("docker", "inspect") and "State.Running" in " ".join(args)

    def is_psql(args, _input):
        return "psql" in args

    def psql_response(args, sql):
        sql = sql or ""
        if "pg_database" in sql and "json_build_object" in sql:
            return _ok(args, db_info_json)
        if "to_regclass('public.app_metadata')" in sql:
            return _ok(args, "instance-1\n")
        if "pg_stat_activity" in sql and "json_agg" in sql:
            return _ok(args, connections_json)
        if "INSERT INTO app_metadata" in sql:
            return _ok(args, "INSERT 0 2\n")
        if "SELECT json_build_object" in sql and "migrations" in sql:
            return _ok(args, smoke_json)
        if "DROP DATABASE" in sql:
            return _ok(args, "DROP DATABASE\nCREATE DATABASE\n")
        return _ok(args, "")

    def is_compose_config(args, _input):
        return "compose" in args and "config" in args and "--services" in args

    def is_compose(args, _input):
        return "compose" in args

    responses = [
        (is_context, _ok(("docker", "context", "inspect"), "unix:///var/run/docker.sock\n")),
        (is_labels, _ok(("docker", "inspect"), labels_json)),
        (is_running, _ok(("docker", "inspect"), "true\n")),
        (is_psql, lambda args, sql: psql_response(args, sql)),
        (is_compose_config, _ok(("docker", "compose", "config"), "postgres\nbackend\nchatbot\n")),
        (is_compose, _ok(("docker", "compose"), "")),
    ]
    runner = FakeRunner(responses)
    guard = ResetGuard(root=tmp_path, runner=runner, env=env or {})
    return guard, runner


def test_preview_default_has_no_side_effects(tmp_path):
    guard, runner = _make_guard(tmp_path)
    target = guard.preview()
    assert target.database == "eyetracking"
    assert not runner.called("stop")
    assert not runner.called("run", "--rm", "migrate")
    assert not runner.called("DROP DATABASE")
    assert not runner.called("INSERT INTO app_metadata")
    assert not runner.called("bash", "ops/create_chatbot_role.sh")
    assert not runner.called("up", "-d", "--force-recreate")


def test_apply_requires_matching_confirm(tmp_path):
    guard, _ = _make_guard(tmp_path)
    with pytest.raises(GuardError) as exc:
        guard.apply("eyetracking", "other")
    assert exc.value.exit_code == 2


def test_apply_requires_database_match(tmp_path):
    guard, _ = _make_guard(tmp_path)
    with pytest.raises(GuardError) as exc:
        guard.apply("other", "other")
    assert exc.value.exit_code == 3


def test_remote_docker_rejected(tmp_path):
    guard, _ = _make_guard(tmp_path, env={"DOCKER_HOST": "tcp://10.0.0.5:2375"})
    with pytest.raises(GuardError) as exc:
        guard.preview()
    assert "local socket" in str(exc.value)


def test_wrong_compose_project_rejected(tmp_path):
    guard, _ = _make_guard(
        tmp_path, labels=_labels(tmp_path, **{"com.docker.compose.project": "other"})
    )
    with pytest.raises(GuardError) as exc:
        guard.preview()
    assert "Compose project" in str(exc.value)


def test_wrong_working_dir_rejected(tmp_path):
    guard, _ = _make_guard(
        tmp_path,
        labels=_labels(tmp_path, **{"com.docker.compose.project.working_dir": "/tmp/other"}),
    )
    with pytest.raises(GuardError) as exc:
        guard.preview()
    assert "working dir" in str(exc.value)


def test_system_database_rejected(tmp_path):
    guard, _ = _make_guard(tmp_path)
    with pytest.raises(GuardError) as exc:
        guard.preview("postgres")
    assert "hệ thống" in str(exc.value)


def test_dsn_mismatch_rejected(tmp_path):
    guard, _ = _make_guard(tmp_path)
    guard.env["DATABASE_URL_DOCKER"] = (
        "postgresql+asyncpg://postgres:secret@postgres:5432/other"
    )
    with pytest.raises(GuardError) as exc:
        guard.preview()
    assert "DSN backend database" in str(exc.value)


def test_unknown_owner_rejected(tmp_path):
    guard, _ = _make_guard(tmp_path, db_info=_db_info(owner="someone_else"))
    with pytest.raises(GuardError) as exc:
        guard.preview()
    assert "ownership" in str(exc.value)


def test_remaining_connections_rejected_on_apply(tmp_path):
    guard, runner = _make_guard(
        tmp_path,
        connections=json.dumps(
            [{"usename": "postgres", "application_name": "psql", "client_addr": "127.0.0.1", "state": "active"}]
        ),
    )
    with pytest.raises(GuardError) as exc:
        guard.apply("eyetracking", "eyetracking")
    assert "kết nối" in str(exc.value)
    assert not runner.called("DROP DATABASE")


def test_special_database_name_is_quoted_not_interpolated(tmp_path):
    guard, runner = _make_guard(tmp_path)
    guard._psql("postgres", 'DROP DATABASE IF EXISTS :"dbname";', variables={"dbname": 'weird"name'})
    args, sql = runner.calls[-1]
    assert "-v" in args
    assert 'dbname=weird"name' in args
    assert ':"dbname"' in (sql or "")
    assert 'weird"name' not in (sql or "")


def test_apply_happy_path_order_and_no_volume_delete(tmp_path):
    guard, runner = _make_guard(tmp_path)
    guard.apply("eyetracking", "eyetracking", seed_dev=True)

    assert runner.called("stop")
    assert runner.called("run", "--rm", "migrate")
    assert runner.called("bash", "ops/create_chatbot_role.sh")
    assert runner.called("up", "-d", "--force-recreate")
    assert not runner.called("down", "-v")
    assert not runner.called("volume", "rm")

    sqls = "\n".join(runner.psql_inputs())
    assert 'DROP DATABASE IF EXISTS :"dbname"' in sqls
    assert "INSERT INTO app_metadata" in sqls
    assert "SELECT json_build_object" in sqls


def test_smoke_failure_does_not_start_runtime(tmp_path):
    guard, runner = _make_guard(
        tmp_path,
        smoke=json.dumps({"migrations": 0, "roles": 0, "core_tables": 0, "instance_id": None}),
    )
    with pytest.raises(GuardError) as exc:
        guard.apply("eyetracking", "eyetracking")
    assert exc.value.exit_code == 5
    assert not runner.called("up", "-d", "--force-recreate")
