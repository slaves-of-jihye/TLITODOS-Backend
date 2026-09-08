from fastapi import APIRouter, Depends, Query, status
from pydantic import Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import categories_service
from app.infrastructure.database import get_session
from app.shared.auth import require_access_token
from app.shared.scheduling import RequestModel

router = APIRouter(prefix="/api/v1/categories", tags=["categories"])


class CategoryRequest(RequestModel):
    name: str = Field(min_length=1, max_length=80, pattern=r"\S")
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")


class CategoryPatchRequest(RequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=80, pattern=r"\S")
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")

    @model_validator(mode="after")
    def no_null(self):
        if any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("이름과 색상은 null일 수 없습니다.")
        return self


@router.get("")
async def list_categories(
    group_id: int | None = Query(default=None, alias="groupId"),
    target_user_id: int | None = Query(default=None, alias="userId"),
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await categories_service.list_categories(session, user_id, target_user_id, group_id)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await categories_service.create_category(session, payload, user_id)


@router.patch("/{categoryId}")
async def update_category(
    categoryId: int,
    payload: CategoryPatchRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await categories_service.update_category(session, categoryId, payload, user_id)


@router.delete("/{categoryId}")
async def delete_category(
    categoryId: int,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await categories_service.delete_category(session, categoryId, user_id)
