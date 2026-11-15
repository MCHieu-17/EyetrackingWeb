from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.auth import User
from app.services import media_storage
from app.services.media_access import get_asset_for_user

router = APIRouter(tags=["media"])


def _ensure_media_in_root(path: Path) -> Path:
    try:
        path.resolve().relative_to(settings.media_path.resolve())
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy file")
    return path


@router.get("/media/assets/{asset_id}/file")
async def get_asset_file(
    asset_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Proxy PDF same-origin cho PDF.js (tránh CORS và presigned URL hết hạn)."""
    asset = await get_asset_for_user(db, asset_id, user)
    headers = {
        "Cache-Control": "private, max-age=3600",
        "Accept-Ranges": "none",
    }

    if asset.storage_backend == "r2" and settings.r2_enabled:
        headers["Content-Length"] = str(asset.byte_size)
        return StreamingResponse(
            media_storage.iter_bytes(asset.object_key),
            media_type=asset.mime_type,
            headers=headers,
        )

    file_path = _ensure_media_in_root(settings.media_path / asset.object_key)
    if not file_path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy file")

    # Đã kiểm tra quyền xong; để nginx phục vụ file bằng sendfile + Range,
    # không giữ worker Python trong suốt thời gian tải PDF.
    headers.update(
        {
            "X-Accel-Redirect": (
                f"/_protected_media/{quote(asset.object_key, safe='/')}"
            ),
            "Content-Type": asset.mime_type,
            "Content-Length": str(asset.byte_size),
            "Accept-Ranges": "bytes",
        }
    )
    return Response(status_code=status.HTTP_200_OK, headers=headers)
