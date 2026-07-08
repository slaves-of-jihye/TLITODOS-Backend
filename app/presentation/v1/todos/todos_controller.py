from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import Bet, Category, Todo, bet_to_response, get_session, todo_to_response
from app.shared.auth import require_access_token


router = APIRouter(prefix="/api/v1/todos", tags=["todos"])


class TodoCreateRequest(BaseModel):
    title: str = Field(min_length=1)
    category_id: int = Field(alias="categoryId")
    importance: Literal["NONE", "LOW", "HIGH"] = "NONE"
    hardship: int = Field(default=1, ge=1, le=5)
    due_date: str | None = Field(default=None, alias="dueDate")
    visibility: Literal["PRIVATE", "GROUP", "PUBLIC"] = "PRIVATE"
    group_id: int | None = Field(default=None, alias="groupId")
    x: float = 0
    y: float = 0
    is_routine: bool = Field(default=False, alias="isRoutine")


class TodoPatchRequest(BaseModel):
    title: str | None = None
    category_id: int | None = Field(default=None, alias="categoryId")
    importance: Literal["NONE", "LOW", "HIGH"] | None = None
    hardship: int | None = Field(default=None, ge=1, le=5)
    due_date: str | None = Field(default=None, alias="dueDate")
    visibility: Literal["PRIVATE", "GROUP", "PUBLIC"] | None = None
    group_id: int | None = Field(default=None, alias="groupId")
    x: float | None = None
    y: float | None = None


class SubtaskCreateRequest(BaseModel):
    content: str = Field(min_length=1)


class DependencyCreateRequest(BaseModel):
    dependency_todo_id: int = Field(alias="dependencyTodoId")


class BetCreateRequest(BaseModel):
    content: str = Field(min_length=1)
    requester_id: int = Field(alias="requesterId")


async def _find_todo(session: AsyncSession, todoId: int, user_id: int) -> Todo:
    todo = await session.scalar(select(Todo).where(Todo.id == todoId, Todo.user_id == user_id))
    if todo is None:
        raise HTTPException(status_code=404, detail={"message": "존재하지 않는 할일입니다."})
    return todo


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_todo(
    payload: TodoCreateRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
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


@router.get("")
async def list_todos(
    group_id: int | None = Query(default=None, alias="groupId"),
    date: str | None = None,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    statement = select(Todo).where(Todo.user_id == user_id)
    if group_id is not None:
        statement = statement.where(Todo.group_id == group_id)
    if date is not None:
        statement = statement.where(or_(Todo.due_date == date, Todo.due_date.is_(None)))
    todos = await session.scalars(statement.order_by(Todo.id))
    return [todo_to_response(todo) for todo in todos]


@router.patch("/{todoId}")
async def update_todo(
    todoId: int,
    payload: TodoPatchRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    todo = await _find_todo(session, todoId, user_id)
    updates = payload.model_dump(by_alias=True, exclude_unset=True)
    field_map = {"categoryId": "category_id", "dueDate": "due_date", "groupId": "group_id"}
    for key, value in updates.items():
        setattr(todo, field_map.get(key, key), value)
    await session.commit()
    await session.refresh(todo)
    return todo_to_response(todo)


@router.delete("/{todoId}")
async def delete_todo(
    todoId: int,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    todo = await _find_todo(session, todoId, user_id)
    await session.delete(todo)
    await session.commit()
    return {
        "success": True,
        "message": "할일이 삭제되었습니다.",
    }


@router.post("/{todoId}/subtasks", status_code=status.HTTP_201_CREATED)
async def create_subtask(
    todoId: int,
    payload: SubtaskCreateRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    todo = await _find_todo(session, todoId, user_id)
    subtask = {
        "subtaskId": len(todo.subtasks) + 1,
        "content": payload.content,
        "isCompleted": False,
    }
    todo.subtasks = [*todo.subtasks, subtask]
    await session.commit()
    return subtask


@router.patch("/{todoId}/complete")
async def complete_todo(
    todoId: int,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    todo = await _find_todo(session, todoId, user_id)
    if any(not subtask["isCompleted"] for subtask in todo.subtasks):
        raise HTTPException(status_code=400, detail={"message": "완료되지 않은 하위 할일이 있습니다."})
    todo.is_completed = True
    await session.commit()
    return {
        "success": True,
        "todoId": todoId,
        "isCompleted": True,
    }


@router.post("/{todoId}/dependencies", status_code=status.HTTP_201_CREATED)
async def create_dependency(
    todoId: int,
    payload: DependencyCreateRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    todo = await _find_todo(session, todoId, user_id)
    dependency = await _find_todo(session, payload.dependency_todo_id, user_id)
    if todo.category_id == 1 or dependency.category_id == 1:
        raise HTTPException(status_code=400, detail={"message": "취미 카테고리 할일은 선행 할일로 연결할 수 없습니다."})
    if payload.dependency_todo_id not in todo.dependencies:
        todo.dependencies = [*todo.dependencies, payload.dependency_todo_id]
    await session.commit()
    return {
        "success": True,
        "todoId": todoId,
        "dependencyTodoId": payload.dependency_todo_id,
    }


@router.post("/{todoId}/bets", status_code=status.HTTP_201_CREATED)
async def create_bet(
    todoId: int,
    payload: BetCreateRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    await _find_todo(session, todoId, user_id)
    bet = Bet(todo_id=todoId, content=payload.content, requester_id=payload.requester_id)
    session.add(bet)
    await session.commit()
    await session.refresh(bet)
    return bet_to_response(bet)
