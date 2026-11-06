from fastapi import APIRouter, Depends
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.auth import User
from app.schemas.common import CamelModel
from app.schemas.course import ModuleCreateIn
from app.services import content

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
    course = await content.get_course_or_404(db, course_id)
    module = await content.create_module(db, course, user, body.title)
    await db.commit()
    await db.refresh(module)
    return ModuleOut(
        id=module.id,
        course_id=course.id,
        title=module.title,
        order_index=module.position,
    )


@router.patch("/teacher/modules/{module_id}", response_model=ModuleOut)
async def update_module(
    module_id: str,
    body: ModuleUpdateIn,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course, module = await content.course_of_module(db, module_id)
    if body.title is not None:
        module = await content.update_module(db, course, user, module_id, body.title)
    await db.commit()
    await db.refresh(module)
    return ModuleOut(
        id=module.id,
        course_id=course.id,
        title=module.title,
        order_index=module.position,
    )


@router.delete("/teacher/modules/{module_id}")
async def delete_module(
    module_id: str,
    user: User = Depends(require_roles("teacher", "admin")),
    db: AsyncSession = Depends(get_db),
):
    course, _ = await content.course_of_module(db, module_id)
    await content.delete_module(db, course, user, module_id)
    await db.commit()
    return {"ok": True}
