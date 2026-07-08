from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import Bet, Category, Todo, bet_to_response, todo_to_response


async def find_todo(session: AsyncSession, todo_id: int, user_id: int) -> Todo:
    todo = await session.scalar(select(Todo).where(Todo.id == todo_id, Todo.user_id == user_id))
    if todo is None:
        raise HTTPException(status_code=404, detail={"message": "존재하지 않는 할일입니다."})
    return todo


async def create_todo(session: AsyncSession, payload, user_id: int) -> dict:
    category = await session.scalar(select(Category).where(Category.id == payload.category_id, Category.user_id == user_id))
    if category is None:
        raise HTTPException(status_code=404, detail={"message": "존재하지 않는 카테고리입니다."})
    todo = Todo(
        user_id=user_id,
        title=payload.title,
        category_id=payload.category_id,
        importance=payload.importance,
        hardship=payload.hardship,
        due_date=payload.due_date,
        visibility=payload.visibility,
        group_id=payload.group_id,
        x=payload.x,
        y=payload.y,
        is_routine=payload.is_routine,
        subtasks=[],
        dependencies=[],
    )
    session.add(todo)
    await session.commit()
    await session.refresh(todo)
    return todo_to_response(todo)


async def list_todos(session: AsyncSession, user_id: int, group_id: int | None, date: str | None) -> list[dict]:
    statement = select(Todo).where(Todo.user_id == user_id)
    if group_id is not None:
        statement = statement.where(Todo.group_id == group_id)
    if date is not None:
        statement = statement.where(or_(Todo.due_date == date, Todo.due_date.is_(None)))
    todos = await session.scalars(statement.order_by(Todo.id))
    return [todo_to_response(todo) for todo in todos]


async def update_todo(session: AsyncSession, todo_id: int, payload, user_id: int) -> dict:
    todo = await find_todo(session, todo_id, user_id)
    updates = payload.model_dump(by_alias=True, exclude_unset=True)
    field_map = {"categoryId": "category_id", "dueDate": "due_date", "groupId": "group_id"}
    for key, value in updates.items():
        setattr(todo, field_map.get(key, key), value)
    await session.commit()
    await session.refresh(todo)
    return todo_to_response(todo)


async def delete_todo(session: AsyncSession, todo_id: int, user_id: int) -> dict:
    todo = await find_todo(session, todo_id, user_id)
    await session.delete(todo)
    await session.commit()
    return {"success": True, "message": "할일이 삭제되었습니다."}


async def create_subtask(session: AsyncSession, todo_id: int, payload, user_id: int) -> dict:
    todo = await find_todo(session, todo_id, user_id)
    subtask = {"subtaskId": len(todo.subtasks) + 1, "content": payload.content, "isCompleted": False}
    todo.subtasks = [*todo.subtasks, subtask]
    await session.commit()
    return subtask


async def complete_todo(session: AsyncSession, todo_id: int, user_id: int) -> dict:
    todo = await find_todo(session, todo_id, user_id)
    if any(not subtask["isCompleted"] for subtask in todo.subtasks):
        raise HTTPException(status_code=400, detail={"message": "완료되지 않은 하위 할일이 있습니다."})
    todo.is_completed = True
    await session.commit()
    return {"success": True, "todoId": todo_id, "isCompleted": True}


async def create_dependency(session: AsyncSession, todo_id: int, payload, user_id: int) -> dict:
    todo = await find_todo(session, todo_id, user_id)
    dependency = await find_todo(session, payload.dependency_todo_id, user_id)
    if todo.category_id == 1 or dependency.category_id == 1:
        raise HTTPException(status_code=400, detail={"message": "취미 카테고리 할일은 선행 할일로 연결할 수 없습니다."})
    if payload.dependency_todo_id not in todo.dependencies:
        todo.dependencies = [*todo.dependencies, payload.dependency_todo_id]
    await session.commit()
    return {"success": True, "todoId": todo_id, "dependencyTodoId": payload.dependency_todo_id}


async def create_bet_for_todo(session: AsyncSession, todo_id: int, payload, user_id: int) -> dict:
    await find_todo(session, todo_id, user_id)
    bet = Bet(todo_id=todo_id, content=payload.content, requester_id=payload.requester_id)
    session.add(bet)
    await session.commit()
    await session.refresh(bet)
    return bet_to_response(bet)
