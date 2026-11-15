"""Shared constants and HTTP helpers for AOI services."""

from __future__ import annotations

from fastapi import HTTPException, status

NO_LABEL_CODE = "no_label"
NO_LABEL_NAME = "Chưa đánh dấu"

# Nhãn gaze một sample. Slide dùng tiền tố SLIDE_; UI dùng trực tiếp tên AOI.
SLIDE_LABEL_PREFIX = "SLIDE_"
SLIDE_NO_LABEL = "SLIDE_NO_LABEL"
UI_NO_LABEL = "UI_NO_LABEL"


def _not_found(message: str) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail=message)


def _bad_request(message: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail=message)
