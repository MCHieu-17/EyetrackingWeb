"""Đăng ký marker ``performance`` khi thư mục này được pytest collect.

``backend/pytest.ini`` (owner: A4) chưa khai báo marker này nên nếu không có
hook, pytest sẽ cảnh báo ``PytestUnknownMarkWarning``. Follow-up là khai báo
marker trong ``pytest.ini`` rồi bỏ file này.
"""

from __future__ import annotations


def pytest_configure(config) -> None:
    config.addinivalue_line("markers", "performance: query-count regression tests (P4 harness)")
