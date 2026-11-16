import logging
import re
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import TimeoutError as SATimeoutError

from app.api.routes import (
    admin,
    admin_db,
    analytics,
    aoi,
    auth,
    calibration,
    chat,
    chat_internal,
    course_visits,
    courses,
    enrollments,
    gaze_ingest,
    internal_metrics,
    learning_sessions,
    lessons,
    media,
    module_items,
    modules,
    proxy,
    quiz_attempts,
    quiz_editor,
    users,
)
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.redis import close_redis, init_redis
from app.db.session import SessionLocal
from app.models.metadata import AppMetadata
from app.services.embedding import close_ingest_client
from app.services.study_chat import close_chatbot_client

EXPECTED_SCHEMA_GENERATION = "13"

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if "*" in settings.cors_origin_list:
        raise RuntimeError("CORS_ORIGINS không được chứa '*' khi allow_credentials=True — hãy liệt kê origin cụ thể")
    _ = settings.r2_enabled  # validate partial R2 configuration at startup
    settings.media_path.mkdir(parents=True, exist_ok=True)

    # Fail-fast nếu DB không phải baseline đã nghiệm thu. Không cho backend cũ
    # chạy trên schema mới hoặc ngược lại.
    try:
        async with SessionLocal() as session:
            metadata = dict(
                (
                    await session.execute(
                        select(AppMetadata.key, AppMetadata.value).where(
                            AppMetadata.key.in_(
                                ("schema_generation", "db_instance_id")
                            )
                        )
                    )
                ).all()
            )
            generation = metadata.get("schema_generation")
            instance_id = metadata.get("db_instance_id")
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Database chưa có baseline mới (app_metadata). "
            "Chạy scripts/reset_db.sh có guard trước khi khởi động backend."
        ) from exc
    if generation != EXPECTED_SCHEMA_GENERATION:
        raise RuntimeError(
            f"Schema generation không khớp: DB={generation!r}, "
            f"backend={EXPECTED_SCHEMA_GENERATION!r}. Cần reset/migrate có guard."
        )
    if instance_id:
        settings.app_instance_id = instance_id
    app.state.schema_generation = generation
    app.state.db_instance_id = instance_id

    await init_redis()
    yield
    await close_chatbot_client()
    await close_ingest_client()
    await close_redis()


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)
performance_logger = logging.getLogger("app.performance")


@app.exception_handler(SATimeoutError)
async def db_pool_timeout_handler(request: Request, exc: SATimeoutError):
    """Pool cạn -> 503 + Retry-After thay vì treo/500."""
    performance_logger.warning(
        "db pool timeout path=%s detail=%s", request.url.path, exc
    )
    return JSONResponse(
        status_code=503,
        content={"detail": "Hệ thống đang quá tải, vui lòng thử lại."},
        headers={"Retry-After": "2"},
    )


REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


@app.middleware("http")
async def request_timing(request, call_next):
    incoming_id = request.headers.get("x-request-id", "")
    request_id = incoming_id if REQUEST_ID_PATTERN.fullmatch(incoming_id) else secrets.token_hex(8)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        performance_logger.exception(
            "request id=%s method=%s path=%s status=500 duration_ms=%.1f",
            request_id,
            request.method,
            request.url.path,
            (time.perf_counter() - started) * 1000,
        )
        raise

    duration_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    existing_timing = response.headers.get("Server-Timing")
    app_timing = f"app;dur={duration_ms:.1f}"
    response.headers["Server-Timing"] = f"{existing_timing}, {app_timing}" if existing_timing else app_timing
    if duration_ms >= 250 or request.url.path.startswith("/api/auth/"):
        performance_logger.info(
            "request id=%s method=%s path=%s status=%s duration_ms=%.1f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Server-Timing", "X-Request-ID", "Retry-After"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(courses.router)
app.include_router(admin.router)
app.include_router(admin_db.router)
app.include_router(modules.router)
app.include_router(module_items.router)
app.include_router(lessons.router)
app.include_router(enrollments.router)
app.include_router(proxy.router)
app.include_router(media.router)
app.include_router(quiz_editor.router)
app.include_router(quiz_attempts.router)
app.include_router(calibration.router)
app.include_router(course_visits.router)
app.include_router(learning_sessions.router)
app.include_router(gaze_ingest.router)
app.include_router(aoi.router)
app.include_router(analytics.router)
app.include_router(chat.router)
app.include_router(chat_internal.router)
app.include_router(internal_metrics.router)


@app.get("/health", tags=["system"])
async def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "schemaGeneration": getattr(app.state, "schema_generation", None),
        "dbInstanceId": getattr(app.state, "db_instance_id", None),
    }


# PDF nguồn của slide (đường dẫn trong slide.pdf_url bắt đầu /media).
# Tạo thư mục tránh lỗi khi không có file nào. /media qua router có auth (media.py).
settings.media_path.mkdir(parents=True, exist_ok=True)
