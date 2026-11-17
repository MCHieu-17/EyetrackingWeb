"""Cấu hình runtime công khai cho frontend (không chứa bí mật)."""

from fastapi import APIRouter, Response

from app.core.config import settings

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
async def get_runtime_config(response: Response) -> dict[str, int]:
    # Không cache: đổi GAZE_FPS + restart backend phải có hiệu lực ngay.
    response.headers["Cache-Control"] = "no-store"
    return {"gazeFps": settings.gaze_fps}
