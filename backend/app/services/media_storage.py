import shutil
import uuid
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings


class StorageError(RuntimeError):
    pass


@lru_cache
def _r2_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint_url,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
        config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
    )


def _safe_local_path(key: str) -> Path:
    path = settings.media_path / key
    try:
        path.resolve().relative_to(settings.media_path.resolve())
    except ValueError as exc:
        raise StorageError("Đường dẫn media không hợp lệ") from exc
    return path


def public_url(key: str) -> str:
    if settings.r2_enabled:
        return f'{settings.r2_public_url.rstrip("/")}/{quote(key, safe="/")}'
    return f"/media/{quote(key, safe='/')}"


def asset_file_url(asset_id: str) -> str:
    """URL same-origin để PDF.js tải file PDF (có kiểm tra quyền)."""
    return f"/media/assets/{asset_id}/file"


def put_bytes(key: str, data: bytes, content_type: str) -> str:
    if not settings.r2_enabled:
        target = _safe_local_path(key)
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_bytes(data)
            temporary.replace(target)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise StorageError("Không thể lưu tệp vào volume") from exc
        return public_url(key)

    cache_control = (
        "public, max-age=31536000, immutable"
        if content_type.startswith("image/")
        else "public, max-age=3600"
    )
    try:
        _r2_client().put_object(
            Bucket=settings.r2_bucket_name,
            Key=key,
            Body=data,
            ContentType=content_type,
            CacheControl=cache_control,
        )
    except (BotoCoreError, ClientError) as exc:
        raise StorageError("Không thể tải tệp lên R2") from exc
    return public_url(key)


def _delete_r2_keys(keys: list[str]) -> None:
    try:
        for start in range(0, len(keys), 1000):
            batch = keys[start : start + 1000]
            if batch:
                response = _r2_client().delete_objects(
                    Bucket=settings.r2_bucket_name,
                    Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True},
                )
                if response.get("Errors"):
                    raise StorageError("R2 không xóa được một số tệp")
    except (BotoCoreError, ClientError) as exc:
        raise StorageError("Không thể xóa tệp trên R2") from exc


def _get_r2_bytes(key: str) -> bytes | None:
    try:
        response = _r2_client().get_object(Bucket=settings.r2_bucket_name, Key=key)
        return response["Body"].read()
    except ClientError as exc:
        if str(exc.response.get("Error", {}).get("Code")) in {"NoSuchKey", "404"}:
            return None
        raise StorageError("Không thể đọc tệp từ R2") from exc
    except BotoCoreError as exc:
        raise StorageError("Không thể đọc tệp từ R2") from exc


def get_bytes(key: str) -> bytes:
    """Đọc toàn bộ object (dùng cho PDF cần render/convert)."""
    if settings.r2_enabled:
        data = _get_r2_bytes(key)
        if data is None:
            raise StorageError("Không tìm thấy tệp trên R2")
        return data
    path = _safe_local_path(key)
    try:
        return path.read_bytes()
    except OSError as exc:
        raise StorageError("Không thể đọc tệp từ volume") from exc


def iter_bytes(key: str, chunk_size: int = 1024 * 1024):
    """Stream object để proxy PDF, tránh nạp cả file vào RAM."""
    if settings.r2_enabled:
        try:
            response = _r2_client().get_object(
                Bucket=settings.r2_bucket_name, Key=key
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageError("Không thể đọc tệp từ R2") from exc
        body = response["Body"]
        try:
            yield from body.iter_chunks(chunk_size)
        finally:
            body.close()
        return

    path = _safe_local_path(key)
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(chunk_size):
                yield chunk
    except OSError as exc:
        raise StorageError("Không thể đọc tệp từ volume") from exc


def delete_key(key: str, backend: str | None = None) -> None:
    """Xóa object theo backend của asset (mặc định theo cấu hình hiện tại)."""
    use_r2 = settings.r2_enabled if backend is None else backend == "r2"
    if use_r2:
        _delete_r2_keys([key])
        return
    path = _safe_local_path(key)
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise StorageError("Không thể xóa tệp khỏi volume") from exc


def delete_keys(keys: list[str], backend: str | None = None) -> None:
    """Xóa nhiều object cùng backend; R2 gom theo batch 1000."""
    if not keys:
        return
    use_r2 = settings.r2_enabled if backend is None else backend == "r2"
    if use_r2:
        if not settings.r2_enabled:
            raise StorageError("R2 chưa được cấu hình để xóa tệp")
        _delete_r2_keys(keys)
        return
    for key in keys:
        delete_key(key, backend="local")


def delete_prefix(prefix: str, backend: str | None = None) -> int:
    """Xóa toàn bộ object dưới prefix (R2) hoặc thư mục (local).

    Trả về số object/tệp đã xóa. Dùng để dọn sạch mọi tệp của một khóa học,
    kể cả các object không còn được tham chiếu trong DB.
    """
    if not prefix.strip("/"):
        raise StorageError("Prefix xóa không hợp lệ")

    use_r2 = settings.r2_enabled if backend is None else backend == "r2"
    if use_r2:
        if not settings.r2_enabled:
            raise StorageError("R2 chưa được cấu hình để xóa tệp")
        keys: list[str] = []
        try:
            paginator = _r2_client().get_paginator("list_objects_v2")
            for page in paginator.paginate(
                Bucket=settings.r2_bucket_name, Prefix=prefix
            ):
                keys.extend(obj["Key"] for obj in page.get("Contents", []))
        except (BotoCoreError, ClientError) as exc:
            raise StorageError("Không thể liệt kê tệp trên R2") from exc
        _delete_r2_keys(keys)
        return len(keys)

    target = _safe_local_path(prefix)
    if not target.exists():
        return 0
    if target.is_dir():
        count = sum(1 for path in target.rglob("*") if path.is_file())
        try:
            shutil.rmtree(target)
        except OSError as exc:
            raise StorageError("Không thể xóa thư mục media") from exc
        return count
    try:
        target.unlink()
    except OSError as exc:
        raise StorageError("Không thể xóa tệp khỏi volume") from exc
    return 1
