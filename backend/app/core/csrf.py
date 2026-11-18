import secrets
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, status

from app.core.config import settings


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def _origin_key(value: str) -> tuple[str, str, int | None] | None:
    """Chuẩn hoá origin thành (scheme, host, port) để so với allowlist."""
    try:
        parts = urlsplit(value)
        host = parts.hostname
        port = parts.port
    except ValueError:
        return None
    if not parts.scheme or not host:
        return None
    scheme = parts.scheme.lower()
    default_port = 443 if scheme == "https" else 80 if scheme == "http" else None
    return scheme, host.lower(), None if port == default_port else port


def _host_name(value: str) -> str | None:
    try:
        host = urlsplit(value).hostname
    except ValueError:
        return None
    return host.lower() if host else None


def _is_same_host(value: str, request: Request) -> bool:
    """Cùng host với request hiện tại.

    Bỏ qua scheme vì TLS thường kết thúc ở nginx/Cloudflare; cookie cũng không
    phân biệt port nên host là mức phân tách phù hợp cho CSRF.
    """
    request_host = request.url.hostname
    return bool(request_host and _host_name(value) == request_host.lower())


def _origin_allowed(value: str, request: Request) -> bool:
    if _is_same_host(value, request):
        return True
    origin = _origin_key(value)
    if origin is None:
        return False
    return origin in {
        key
        for item in settings.cors_origin_list
        if (key := _origin_key(item)) is not None
    }


def verify_csrf(request: Request) -> None:
    """Double-submit + Origin check cho state-changing khi auth qua cookie.

    - Nếu có Authorization header → coi như auth qua memory token → bỏ qua CSRF
      (header không tự gửi cross-site).
    - Nếu chỉ có cookie access_token → yêu cầu header X-CSRF-Token == cookie
      csrf_token.
    - Request cùng host với request hiện tại luôn hợp lệ sau khi double-submit
      khớp; chỉ request cross-origin mới phải nằm trong CORS_ORIGINS.
    """
    method = request.method.upper()
    if method in ("GET", "HEAD", "OPTIONS"):
        return
    has_auth_header = bool(request.headers.get("authorization"))
    has_cookie = bool(
        request.cookies.get("access_token")
        or request.cookies.get("refresh_token")
    )
    if not has_cookie or has_auth_header:
        return
    # Chỉ khi auth thuần cookie mới cần CSRF
    cookie_token = request.cookies.get("csrf_token")
    header_token = request.headers.get(
        "x-csrf-token"
    ) or request.headers.get("X-CSRF-Token")
    if not cookie_token or not header_token or cookie_token != header_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token không hợp lệ",
        )

    origin = request.headers.get("origin")
    if origin is not None:
        if not _origin_allowed(origin, request):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Origin không hợp lệ",
            )
        return

    # Một số client cũ không gửi Origin; dùng Referer nếu có. Không có cả hai
    # thì vẫn phải vượt qua double-submit token ở trên.
    referer = request.headers.get("referer")
    if referer and not _origin_allowed(referer, request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origin không hợp lệ",
        )
