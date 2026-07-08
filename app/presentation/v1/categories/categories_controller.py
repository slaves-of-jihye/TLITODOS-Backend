from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import categories_service
from app.infrastructure.database import get_session
from app.shared.auth import require_access_token


router = APIRouter(prefix="/api/v1/categories", tags=["categories"])


class CategoryRequest(BaseModel):
    name: str = Field(min_length=1)
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")


@router.get("")
async def list_categories(
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await categories_service.list_categories(session, user_id)


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
    payload: CategoryRequest,
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
