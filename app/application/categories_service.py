from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import Category, category_to_response


async def list_categories(session: AsyncSession, user_id: int) -> list[dict]:
    categories = await session.scalars(select(Category).where(Category.user_id == user_id).order_by(Category.id))
    return [category_to_response(category) for category in categories]


async def create_category(session: AsyncSession, payload, user_id: int) -> dict:
    category_count = await session.scalar(select(func.count(Category.id)).where(Category.user_id == user_id))
    if category_count >= 5:
        raise HTTPException(status_code=400, detail={"message": "카테고리는 최대 5개까지만 생성할 수 있습니다."})
    category = Category(user_id=user_id, name=payload.name, color=payload.color, is_deletable=True)
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category_to_response(category)


async def update_category(session: AsyncSession, category_id: int, payload, user_id: int) -> dict:
    category = await session.scalar(select(Category).where(Category.id == category_id, Category.user_id == user_id))
    if category is None:
        raise HTTPException(status_code=404, detail={"message": "존재하지 않는 카테고리입니다."})
    category.name = payload.name
    category.color = payload.color
    await session.commit()
    return {"categoryId": category.id, "name": category.name, "color": category.color}


async def delete_category(session: AsyncSession, category_id: int, user_id: int) -> dict:
    category = await session.scalar(select(Category).where(Category.id == category_id, Category.user_id == user_id))
    if category is None:
        raise HTTPException(status_code=404, detail={"message": "삭제할 카테고리를 찾을 수 없습니다."})
    if not category.is_deletable:
        raise HTTPException(status_code=400, detail={"message": "취미 카테고리는 삭제할 수 없습니다."})
    await session.delete(category)
    await session.commit()
    return {"success": True, "message": "카테고리가 삭제되었습니다."}
