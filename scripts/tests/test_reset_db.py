"""Guard tests cho scripts/reset_db.py (stdlib unittest, không cần Docker)."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "reset_db.py"
SPEC = importlib.util.spec_from_file_location("reset_db", SCRIPT)
assert SPEC and SPEC.loader
reset_db = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = reset_db
SPEC.loader.exec_module(reset_db)


class ResetParserTests(unittest.TestCase):
    def test_apply_requires_database_and_confirmation(self):
        self.assertEqual(reset_db.main(["--apply"]), 2)
        self.assertEqual(
            reset_db.main(["--apply", "--database", "eyetracking"]), 2
        )

    def test_mismatched_confirmation_fails_before_any_mutation(self):
        self.assertEqual(
            reset_db.main(
                [
                    "--apply",
                    "--database",
                    "eyetracking",
                    "--confirm-reset",
                    "other",
                ]
            ),
            2,
        )

    def test_parse_dsn_rejects_wrong_scheme(self):
        with self.assertRaises(reset_db.GuardError):
            reset_db._parse_dsn("not-a-dsn")

    def test_parse_dsn_returns_connection_parts(self):
        host, database, port, user, password = reset_db._parse_dsn(
            "postgresql+asyncpg://user:secret@localhost:5435/eyetracking"
        )
        self.assertEqual(
            (host, database, port, user, password),
            ("localhost", "eyetracking", 5435, "user", "secret"),
        )

    def test_env_parser_handles_export_and_quotes(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text(
                "export POSTGRES_DB='eyetracking'\nIGNORED\n# comment\n"
                'POSTGRES_USER="postgres"\n'
            )
            env = reset_db._parse_env_file(path)
        self.assertEqual(env, {"POSTGRES_DB": "eyetracking", "POSTGRES_USER": "postgres"})


if __name__ == "__main__":
    unittest.main()
