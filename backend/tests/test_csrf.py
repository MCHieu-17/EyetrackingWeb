"""Kiểm tra CSRF cho auth bằng cookie: same-origin và allowlist cross-origin."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core.config import settings
from app.core.csrf import verify_csrf

TOKEN = "csrf-token-test"


def _request(
    *,
    method: str = "PUT",
    host: str = "app.example",
    scheme: str = "https",
    origin: str | None = None,
    referer: str | None = None,
    cookies: str | None = f"access_token=access; csrf_token={TOKEN}",
    csrf_header: str | None = TOKEN,
    authorization: str | None = None,
) -> Request:
    headers = [(b"host", host.encode())]
    if origin is not None:
        headers.append((b"origin", origin.encode()))
    if referer is not None:
        headers.append((b"referer", referer.encode()))
    if cookies is not None:
        headers.append((b"cookie", cookies.encode()))
    if csrf_header is not None:
        headers.append((b"x-csrf-token", csrf_header.encode()))
    if authorization is not None:
        headers.append((b"authorization", authorization.encode()))
    return Request(
        {
            "type": "http",
            "method": method,
            "scheme": scheme,
            "headers": headers,
            "server": ("app.example", 443),
            "path": "/api/aois/slides/test",
            "query_string": b"",
        }
    )


def _assert_origin_rejected(request: Request) -> None:
    with pytest.raises(HTTPException) as exc:
        verify_csrf(request)
    assert exc.value.status_code == 403
    assert exc.value.detail == "Origin không hợp lệ"


def test_same_origin_is_allowed_even_when_cors_origins_is_empty(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", "")
    verify_csrf(_request(origin="https://app.example"))


def test_same_host_is_allowed_when_proxy_scheme_differs(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", "https://other.example")
    verify_csrf(
        _request(scheme="http", origin="https://app.example")
    )


def test_cross_origin_is_rejected_when_not_allowlisted(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", "https://other.example")
    _assert_origin_rejected(_request(origin="https://evil.example"))


def test_cross_origin_is_allowed_when_allowlisted(monkeypatch):
    monkeypatch.setattr(
        settings, "cors_origins", "https://frontend.example, https://other.example"
    )
    verify_csrf(_request(origin="https://frontend.example"))


def test_null_origin_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", "https://other.example")
    _assert_origin_rejected(_request(origin="null"))


def test_missing_origin_falls_back_to_same_origin_referer(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", "https://other.example")
    verify_csrf(
        _request(referer="https://app.example/teacher/courses/1?tab=aoi")
    )


def test_missing_origin_rejects_foreign_referer(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", "https://other.example")
    _assert_origin_rejected(
        _request(referer="https://evil.example/teacher/courses/1")
    )


def test_missing_origin_and_referer_still_accepts_valid_token(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", "")
    verify_csrf(_request(origin=None, referer=None))


def test_wrong_csrf_token_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", "")
    with pytest.raises(HTTPException) as exc:
        verify_csrf(_request(origin="https://app.example", csrf_header="wrong"))
    assert exc.value.status_code == 403
    assert exc.value.detail == "CSRF token không hợp lệ"


def test_authorization_header_skips_csrf(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", "")
    verify_csrf(
        _request(
            cookies="access_token=access",
            csrf_header=None,
            authorization="Bearer token",
        )
    )


def test_safe_methods_skip_csrf():
    verify_csrf(
        _request(
            method="GET",
            cookies="access_token=access",
            csrf_header=None,
            origin="https://evil.example",
        )
    )
