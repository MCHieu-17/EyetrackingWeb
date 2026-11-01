from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.access import get_module_owned, get_owned_course
from app.api.deps import require_roles
from app.db.session import get_db
from app.models.auth import User
from app.models.course import Module
from app.schemas.common import CamelModel
from app.schemas.course import ModuleCreateIn

router = APIRouter(tags=["modules"])


class ModuleOut(CamelModel):
    id: str
    course_id: str
    title: str
    order_index: int


class ModuleUpdateIn(CamelModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)


@router.post("/teacher/courses/{course_id}/modules", response_model=ModuleOut, status_code=201)
async def create_module(
    course_id: str,
    body: ModuleCreateIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    await get_owned_course(db, course_id, user)
    next_index = (
        await db.execute(
            select(func.coalesce(func.max(Module.order_index), 0) + 1).where(
                Module.course_id == course_id
            )
        )
    ).scalar_one()
    module = Module(course_id=course_id, title=body.title, order_index=next_index)
    db.add(module)
    await db.commit()
    await db.refresh(module)
    return ModuleOut(
        id=module.id,
        course_id=module.course_id,
        title=module.title,
        order_index=module.order_index,
    )


@router.patch("/teacher/modules/{module_id}", response_model=ModuleOut)
async def update_module(
    module_id: str,
    body: ModuleUpdateIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    module = await get_module_owned(db, module_id, user)
    if body.title is not None:
        module.title = body.title
    await db.commit()
    await db.refresh(module)
    return ModuleOut(
        id=module.id,
        course_id=module.course_id,
        title=module.title,
        order_index=module.order_index,
    )


@router.delete("/teacher/modules/{module_id}")
async def delete_module(
    module_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    module = await get_module_owned(db, module_id, user)
    await db.delete(module)
    await db.commit()
    return {"ok": True}
