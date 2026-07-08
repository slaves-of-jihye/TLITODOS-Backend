from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import todos_service
from app.infrastructure.database import get_session
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


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_todo(
    payload: TodoCreateRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await todos_service.create_todo(session, payload, user_id)


@router.get("")
async def list_todos(
    group_id: int | None = Query(default=None, alias="groupId"),
    date: str | None = None,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await todos_service.list_todos(session, user_id, group_id, date)


@router.patch("/{todoId}")
async def update_todo(
    todoId: int,
    payload: TodoPatchRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await todos_service.update_todo(session, todoId, payload, user_id)


@router.delete("/{todoId}")
async def delete_todo(
    todoId: int,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await todos_service.delete_todo(session, todoId, user_id)


@router.post("/{todoId}/subtasks", status_code=status.HTTP_201_CREATED)
async def create_subtask(
    todoId: int,
    payload: SubtaskCreateRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await todos_service.create_subtask(session, todoId, payload, user_id)


@router.patch("/{todoId}/complete")
async def complete_todo(
    todoId: int,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await todos_service.complete_todo(session, todoId, user_id)


@router.post("/{todoId}/dependencies", status_code=status.HTTP_201_CREATED)
async def create_dependency(
    todoId: int,
    payload: DependencyCreateRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await todos_service.create_dependency(session, todoId, payload, user_id)


@router.post("/{todoId}/bets", status_code=status.HTTP_201_CREATED)
async def create_bet(
    todoId: int,
    payload: BetCreateRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await todos_service.create_bet_for_todo(session, todoId, payload, user_id)
