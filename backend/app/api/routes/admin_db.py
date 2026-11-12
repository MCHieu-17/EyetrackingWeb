import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import require_roles, user_rate_limit
from app.models.auth import User
from app.schemas.admin_db import (
    AdminDbQueryIn,
    AdminDbQueryOut,
    AdminDbSchemaOut,
    AdminDbTableRowsIn,
    AdminDbTableRowsOut,
)
from app.services import admin_db as admin_db_service

logger = logging.getLogger("app.admin_db")

router = APIRouter(prefix="/admin/db", tags=["admin-db"])


@router.get("/schema", response_model=AdminDbSchemaOut)
async def get_schema(
    refresh: bool = Query(default=False),
    _: User = Depends(require_roles("admin")),
):
    """Danh sách bảng/view mà role truy vấn hiện tại được phép đọc."""
    try:
        return await admin_db_service.get_schema(force_refresh=refresh)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("admin_db_schema_failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Không tải được schema CSDL.",
        ) from exc


@router.post(
    "/query",
    response_model=AdminDbQueryOut,
    dependencies=[Depends(user_rate_limit(30, 60, "admin_db_query"))],
)
async def run_query(
    body: AdminDbQueryIn,
    user: User = Depends(require_roles("admin")),
):
    """Chạy một câu lệnh SELECT/WITH trong transaction chỉ đọc."""
    try:
        return await admin_db_service.run_query(body.sql, body.max_rows, user_id=user.id)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("admin_db_query_failed user_id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không chạy được truy vấn.",
        ) from exc


@router.post(
    "/tables/{table_name}/rows",
    response_model=AdminDbTableRowsOut,
    dependencies=[Depends(user_rate_limit(60, 60, "admin_db_browse"))],
)
async def browse_table(
    table_name: str,
    body: AdminDbTableRowsIn,
    user: User = Depends(require_roles("admin")),
):
    """Duyệt dữ liệu bảng/view bằng tham số có cấu trúc (không nhận raw SQL)."""
    try:
        return await admin_db_service.browse_table(
            table_name,
            schema_name=body.schema_name,
            columns=body.columns,
            limit=body.limit,
            offset=body.offset,
            order_by=body.order_by,
            order_dir=body.order_dir,
            filters=body.filters,
            user_id=user.id,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("admin_db_browse_failed user_id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không tải được dữ liệu bảng.",
        ) from exc
