"""Unit tests cho local/R2 media storage."""

from __future__ import annotations

from pathlib import Path

import pytest
from botocore.exceptions import ClientError

from app.core.config import settings
from app.services import media_storage


@pytest.fixture
def local_media(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "media_dir", str(tmp_path))
    for key in (
        "r2_account_id",
        "r2_bucket_name",
        "r2_access_key_id",
        "r2_secret_access_key",
        "r2_public_url",
    ):
        monkeypatch.setattr(settings, key, "")
    return tmp_path


def test_local_put_get_stream_delete(local_media: Path):
    url = media_storage.put_bytes("course/lesson/source.pdf", b"payload", "application/pdf")
    assert url == "/media/course/lesson/source.pdf"
    assert media_storage.get_bytes("course/lesson/source.pdf") == b"payload"
    assert list(media_storage.iter_bytes("course/lesson/source.pdf", 3)) == [
        b"pay",
        b"loa",
        b"d",
    ]
    media_storage.delete_key("course/lesson/source.pdf", backend="local")
    assert not (local_media / "course/lesson/source.pdf").exists()


def test_local_traversal_is_rejected(local_media: Path):
    with pytest.raises(media_storage.StorageError):
        media_storage.put_bytes("../escape.pdf", b"x", "application/pdf")
    with pytest.raises(media_storage.StorageError):
        media_storage.get_bytes("../../etc/passwd")


def test_delete_prefix_counts_only_files(local_media: Path):
    media_storage.put_bytes("courses/c1/a.pdf", b"a", "application/pdf")
    media_storage.put_bytes("courses/c1/deep/b.pdf", b"b", "application/pdf")
    (local_media / "courses/c1/empty").mkdir()
    assert media_storage.delete_prefix("courses/c1", backend="local") == 2
    assert not (local_media / "courses/c1").exists()


def test_delete_prefix_rejects_empty_prefix(local_media: Path):
    with pytest.raises(media_storage.StorageError):
        media_storage.delete_prefix("/", backend="local")


def test_missing_local_file_raises_storage_error(local_media: Path):
    with pytest.raises(media_storage.StorageError):
        media_storage.get_bytes("missing.pdf")
    with pytest.raises(media_storage.StorageError):
        list(media_storage.iter_bytes("missing.pdf"))


class _FakeBody:
    def __init__(self):
        self.closed = False

    def iter_chunks(self, _size):
        yield b"one"
        yield b"two"

    def close(self):
        self.closed = True


def test_r2_stream_closes_body(monkeypatch):
    body = _FakeBody()
    fake = type(
        "FakeClient",
        (),
        {"get_object": lambda self, **kwargs: {"Body": body}},
    )()
    monkeypatch.setattr(media_storage, "_r2_client", lambda: fake)
    monkeypatch.setattr(media_storage.settings, "r2_account_id", "acc")
    monkeypatch.setattr(media_storage.settings, "r2_bucket_name", "bucket")
    monkeypatch.setattr(media_storage.settings, "r2_access_key_id", "key")
    monkeypatch.setattr(media_storage.settings, "r2_secret_access_key", "secret")
    monkeypatch.setattr(media_storage.settings, "r2_public_url", "https://cdn")

    assert list(media_storage.iter_bytes("key.pdf")) == [b"one", b"two"]
    assert body.closed is True


def test_r2_delete_reports_partial_errors(monkeypatch):
    class FakeClient:
        def delete_objects(self, **_kwargs):
            return {"Errors": [{"Key": "x"}]}

    monkeypatch.setattr(media_storage, "_r2_client", lambda: FakeClient())
    monkeypatch.setattr(media_storage.settings, "r2_account_id", "acc")
    monkeypatch.setattr(media_storage.settings, "r2_bucket_name", "bucket")
    monkeypatch.setattr(media_storage.settings, "r2_access_key_id", "key")
    monkeypatch.setattr(media_storage.settings, "r2_secret_access_key", "secret")
    monkeypatch.setattr(media_storage.settings, "r2_public_url", "https://cdn")

    with pytest.raises(media_storage.StorageError):
        media_storage.delete_keys(["x"], backend="r2")


def test_r2_missing_object_returns_none(monkeypatch):
    class FakeClient:
        def get_object(self, **_kwargs):
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")

    monkeypatch.setattr(media_storage, "_r2_client", lambda: FakeClient())
    assert media_storage._get_r2_bytes("missing") is None
