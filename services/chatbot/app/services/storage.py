"""Đọc file slide từ local, S3, Cloudflare R2 hoặc URL http(s).

Chỉ cần gọi `load(source)` — hàm tự nhận diện nguồn dựa vào scheme/URL.
Có chặn SSRF: chỉ host trong allowlist, không resolve về IP private/loopback.
"""

import ipaddress
import os
import socket
from pathlib import Path
from urllib.parse import unquote, urlparse

import boto3
import httpx

from app.settings import (
    local_media_dir,
    r2_values,
    storage_http_allowed_hosts,
    storage_max_bytes,
)


class FileStorage:
    """Đọc file slide từ local, S3, Cloudflare R2 hoặc URL http(s)."""

    BUCKET_ENV = {"s3": "S3_BUCKET", "r2": "R2_BUCKET_NAME"}

    def __init__(self):
        self.provider = os.getenv("STORAGE_PROVIDER", "local").lower()
        self.local_root = Path(local_media_dir()).resolve()
        public_url = r2_values()[4]
        configured_hosts = storage_http_allowed_hosts()
        self.allowed_http_hosts = {
            host.strip().lower() for host in configured_hosts.split(",") if host.strip()
        }
        if public_url and (host := urlparse(public_url).hostname):
            self.allowed_http_hosts.add(host.lower())
        self.max_bytes = storage_max_bytes()
        self.http = httpx.Client(timeout=60, follow_redirects=False)
        self._clients: dict = {}

    def load(self, source: str) -> bytes:
        """Trả về bytes của file từ bất kỳ nguồn nào."""
        parsed = urlparse(source)

        # s3://bucket/key hoặc r2://bucket/key
        if parsed.scheme in ("s3", "r2"):
            return self._load_object(
                parsed.scheme,
                parsed.netloc,
                unquote(parsed.path.lstrip("/")),
            )

        # URL công khai hoặc presigned URL
        if parsed.scheme in ("http", "https"):
            host = (parsed.hostname or "").lower()
            if host not in self.allowed_http_hosts:
                raise ValueError("HTTP slide host is not allowed")
            for address in socket.getaddrinfo(host, parsed.port or 443):
                ip = ipaddress.ip_address(address[4][0])
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    raise ValueError("Private slide host is not allowed")
            response = self.http.get(source)
            response.raise_for_status()
            if len(response.content) > self.max_bytes:
                raise ValueError("Slide file is too large")
            return response.content

        # file:///duong/dan
        if parsed.scheme == "file":
            raise ValueError("file:// sources are not allowed")

        # Không có scheme -> đường dẫn local hoặc object key (theo provider)
        if self.provider == "local":
            relative = source.removeprefix("/media/").lstrip("/")
            path = (self.local_root / relative).resolve()
            if path != self.local_root and self.local_root not in path.parents:
                raise ValueError("Local slide path escapes media directory")
            data = path.read_bytes()
            if len(data) > self.max_bytes:
                raise ValueError("Slide file is too large")
            return data

        return self._load_object(
            self.provider,
            os.environ[self.BUCKET_ENV[self.provider]],
            source.lstrip("/"),
        )

    def _get_client(self, provider: str):
        if provider not in self._clients:
            if provider == "s3":
                self._clients[provider] = boto3.client("s3")
            else:  # r2
                account_id, _, access_key, secret_key, _ = r2_values()
                endpoint = os.getenv("R2_ENDPOINT") or (
                    f"https://{account_id}.r2.cloudflarestorage.com"
                )
                self._clients[provider] = boto3.client(
                    "s3",
                    endpoint_url=endpoint,
                    aws_access_key_id=access_key,
                    aws_secret_access_key=secret_key,
                    region_name="auto",
                )
        return self._clients[provider]

    def _load_object(self, provider: str, bucket: str, key: str) -> bytes:
        body = self._get_client(provider).get_object(
            Bucket=bucket,
            Key=key,
        )["Body"]
        try:
            return body.read()
        finally:
            body.close()

    def close(self) -> None:
        self.http.close()
