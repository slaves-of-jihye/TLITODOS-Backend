from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import Category, Todo, TodoRoutine


def replay_creation(routine: TodoRoutine, definition: dict) -> dict:
    if routine.definition != definition:
        raise HTTPException(status_code=409, detail={"message": "다른 내용에 사용된 requestId입니다."})
    return routine.creation_result


async def create_routine(session: AsyncSession, payload, user_id: int) -> dict:
    definition = payload.model_dump(mode="json", by_alias=True, exclude={"request_id"})
    lookup = select(TodoRoutine).where(
        TodoRoutine.user_id == user_id, TodoRoutine.request_id == str(payload.request_id)
    )
    existing = await session.scalar(lookup)
    if existing is not None:
        return replay_creation(existing, definition)

    category = await session.scalar(
        select(Category.id).where(Category.id == payload.category_id, Category.user_id == user_id)
    )
    if category is None:
        raise HTTPException(status_code=404, detail={"message": "존재하지 않는 카테고리입니다."})

    dates = [
        payload.start_date + timedelta(days=offset)
        for offset in range((payload.end_date - payload.start_date).days + 1)
        if (payload.start_date + timedelta(days=offset)).isoweekday() in payload.weekdays
    ]
    if not dates:
        raise HTTPException(status_code=422, detail={"message": "기간 내 선택한 요일에 해당하는 날짜가 없습니다."})

    routine = TodoRoutine(user_id=user_id, request_id=str(payload.request_id), definition=definition)
    try:
        session.add(routine)
        await session.flush()
        # One bulk insert and one commit for the entire series; no per-day requests or commits.
        rows = (await session.execute(
            insert(Todo).returning(Todo.id, Todo.due_date),
            [
                {
                    "user_id": user_id,
                    "routine_id": routine.id,
                    "category_id": payload.category_id,
                    "title": payload.title,
                    "importance": payload.importance,
                    "hardship": payload.hardship,
                    "x": payload.x,
                    "y": payload.y,
                    "due_date": day.isoformat(),
                    "is_routine": True,
                    "is_completed": False,
                    "subtasks": [],
                    "dependencies": [],
                }
                for day in dates
            ],
        )).all()
        result = {
            "routineId": routine.id,
            "createdCount": len(rows),
            "occurrences": [
                {"todoId": row.id, "dueDate": row.due_date}
                for row in sorted(rows, key=lambda row: row.due_date)
            ],
        }
        routine.creation_result = result
        await session.commit()
        return result
    except IntegrityError:
        await session.rollback()
        # The unique constraint serializes concurrent retries with the same request ID.
        existing = await session.scalar(lookup)
        if existing is not None:
            return replay_creation(existing, definition)
        raise
    except Exception:
        await session.rollback()
        raise
