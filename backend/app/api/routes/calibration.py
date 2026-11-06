import base64
import binascii
import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.auth import User
from app.models.calibration import Calibration, CalibrationSettings, Device
from app.schemas.calibration import (
    CalibrationActiveOut,
    CalibrationCreateIn,
    CalibrationModelOut,
    CalibrationOut,
    CalibrationSettingsOut,
)

router = APIRouter(prefix="/api/calibrations", tags=["calibrations"])

MAPPING_MODEL_VERSION = "ubj-linreg-v2-b16"
MAX_MODEL_UBJ_BYTES = 256 * 1024


def _decode_model(model_ubj_base64: str) -> bytes:
    try:
        raw = base64.b64decode(model_ubj_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="modelUbjBase64 không phải base64 hợp lệ",
        ) from exc
    if not raw:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail="model .ubj rỗng"
        )
    if len(raw) > MAX_MODEL_UBJ_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="model .ubj quá lớn",
        )
    return raw


async def _find_device(
    db: AsyncSession, user_id: str, fingerprint: str
) -> Device | None:
    stmt = select(Device).where(
        Device.owner_id == user_id,
        Device.fingerprint == fingerprint,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _current_calibration(
    db: AsyncSession, device: Device
) -> Calibration | None:
    if not device.current_calibration_id:
        return None
    return await db.get(Calibration, device.current_calibration_id)


@router.post("", response_model=CalibrationOut, status_code=201)
async def save_calibration_params(
    body: CalibrationCreateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    model_ubj = _decode_model(body.model_ubj_base64)
    device = await _find_device(db, user.id, body.device_fingerprint)
    if device is None:
        device = Device(owner_id=user.id, fingerprint=body.device_fingerprint)
        db.add(device)
        await db.flush()

    calibration = Calibration(
        device_id=device.id,
        model_ubj=model_ubj,
        model_hash=hashlib.sha256(model_ubj).hexdigest(),
        model_version=MAPPING_MODEL_VERSION,
        mae_px=body.mae_px,
        viewport_width_px=body.viewport_width_px or body.screen_width_px or 1,
        viewport_height_px=body.viewport_height_px or body.screen_height_px or 1,
        device_pixel_ratio=body.device_pixel_ratio or 1.0,
        config={"num_points": body.num_points},
    )
    db.add(calibration)
    await db.flush()
    device.current_calibration_id = calibration.id
    await db.commit()
    await db.refresh(calibration)
    return CalibrationOut(
        id=calibration.id,
        mae_px=calibration.mae_px,
        num_points=body.num_points,
        device_fingerprint=device.fingerprint,
        valid_from=calibration.created_at,
        viewport_width_px=calibration.viewport_width_px,
        viewport_height_px=calibration.viewport_height_px,
        device_pixel_ratio=calibration.device_pixel_ratio,
        model_version=calibration.model_version,
    )


@router.get("/active", response_model=CalibrationActiveOut)
async def get_active_calibration(
    device_fingerprint: str = Query(alias="deviceFingerprint"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    device = await _find_device(db, user.id, device_fingerprint)
    if device is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Chưa có calibration cho thiết bị này"
        )
    calibration = await _current_calibration(db, device)
    if calibration is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Chưa có calibration cho thiết bị này"
        )
    return CalibrationActiveOut(
        calibrated=calibration.model_version == MAPPING_MODEL_VERSION,
        mae_px=calibration.mae_px,
        calibrated_at=calibration.created_at,
        calibration_id=calibration.id,
        viewport_width_px=calibration.viewport_width_px,
        viewport_height_px=calibration.viewport_height_px,
        device_pixel_ratio=calibration.device_pixel_ratio,
        model_version=calibration.model_version,
    )


@router.get("/active/model", response_model=CalibrationModelOut)
async def get_active_calibration_model(
    device_fingerprint: str = Query(alias="deviceFingerprint"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    device = await _find_device(db, user.id, device_fingerprint)
    if device is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Chưa có calibration cho thiết bị này"
        )
    calibration = await _current_calibration(db, device)
    if calibration is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="Chưa có model calibration cho thiết bị này",
        )
    if calibration.model_version != MAPPING_MODEL_VERSION:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Model hiệu chỉnh đã lỗi thời — hãy hiệu chỉnh lại",
        )
    return CalibrationModelOut(
        model_ubj_base64=base64.b64encode(calibration.model_ubj).decode("ascii"),
        mae_px=calibration.mae_px,
        model_version=calibration.model_version,
        model_hash=calibration.model_hash,
    )


@router.get("/config", response_model=CalibrationSettingsOut)
async def get_calibration_config(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(CalibrationSettings, 1)
    if row is None:
        return CalibrationSettingsOut(enabled=True, threshold=0.12, updated_at=None)
    return CalibrationSettingsOut(
        enabled=row.enabled,
        threshold=float(row.threshold),
        updated_at=row.updated_at,
    )
