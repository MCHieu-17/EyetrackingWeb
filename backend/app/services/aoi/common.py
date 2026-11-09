"""Shared constants and HTTP helpers for AOI services."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status

NO_LABEL_CODE = "no_label"
NO_LABEL_NAME = "Chưa đánh dấu"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _not_found(message: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail=message)


def _bad_request(message: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail=message)


def _conflict(message: str) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        detail={"code": "aoi_revision_conflict", "message": message},
    )
