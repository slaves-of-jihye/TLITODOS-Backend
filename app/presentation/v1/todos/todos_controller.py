from datetime import date as CalendarDate
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import todos_service
from app.infrastructure.database import get_session
from app.presentation.v1.responses import BetResponse, DailyStatusResponse, TodoResponse
from app.shared.auth import require_access_token
from app.shared.scheduling import RequestModel, TimedRequest

router = APIRouter(prefix="/api/v1/todos", tags=["todos"])


class TodoCreateRequest(TimedRequest):
    title: str = Field(min_length=1, max_length=40, pattern=r"\S")
    description: str = Field(default="", max_length=100)
    category_id: int = Field(alias="categoryId")
    importance: Literal["NONE", "LOW", "HIGH"] = "NONE"
    hardship: int = Field(default=1, ge=1, le=5)
    start_date: CalendarDate | None = Field(default=None, alias="startDate")
    due_date: CalendarDate | None = Field(default=None, alias="dueDate")
    x: float = Field(default=0, allow_inf_nan=False)
    y: float = Field(default=0, allow_inf_nan=False)


class TodoPatchRequest(TimedRequest):
    title: str | None = Field(default=None, min_length=1, max_length=40, pattern=r"\S")
    description: str | None = Field(default=None, max_length=100)
    category_id: int | None = Field(default=None, alias="categoryId")
    importance: Literal["NONE", "LOW", "HIGH"] | None = None
    hardship: int | None = Field(default=None, ge=1, le=5)
    start_date: CalendarDate | None = Field(default=None, alias="startDate")
    due_date: CalendarDate | None = Field(default=None, alias="dueDate")
    x: float | None = Field(default=None, allow_inf_nan=False)
    y: float | None = Field(default=None, allow_inf_nan=False)

    @model_validator(mode="after")
    def no_null_values(self):
        for key in self.model_fields_set - {"due_date", "time"}:
            if getattr(self, key) is None:
                raise ValueError(f"{key}는 null일 수 없습니다.")
        return self


class SubtaskCreateRequest(BaseModel):
    content: str = Field(min_length=1)


class DependencyCreateRequest(BaseModel):
    dependency_todo_id: int = Field(alias="dependencyTodoId")


class BetCreateRequest(RequestModel):
    content: str = Field(min_length=1, max_length=1000, pattern=r"\S")


class DependenciesRequest(RequestModel):
    dependency_todo_ids: list[Annotated[int, Field(strict=True, gt=0)]] = Field(
        alias="dependencyTodoIds", max_length=100
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TodoResponse)
async def create_todo(
    payload: TodoCreateRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await todos_service.create_todo(session, payload, user_id)


@router.get("", response_model=list[TodoResponse])
async def list_todos(
    group_id: int | None = Query(default=None, alias="groupId"),
    date: CalendarDate | None = None,
    target_user_id: int | None = Query(default=None, alias="userId"),
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await todos_service.list_todos(session, user_id, target_user_id, group_id, date)


@router.get("/daily-status", response_model=list[DailyStatusResponse])
async def list_daily_todo_statuses(
    month: str = Query(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$"),
    target_user_id: int | None = Query(default=None, alias="userId"),
    group_id: int | None = Query(default=None, alias="groupId"),
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await todos_service.list_daily_todo_statuses(session, user_id, month, target_user_id, group_id)


@router.get("/{todoId}", response_model=TodoResponse)
async def get_todo(
    todoId: int, user_id: int = Depends(require_access_token), session: AsyncSession = Depends(get_session)
):
    return await todos_service.get_todo(session, todoId)


@router.put("/{todoId}/dependencies")
async def replace_dependencies(
    todoId: int,
    payload: DependenciesRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await todos_service.set_dependencies(session, todoId, payload.dependency_todo_ids, user_id)


@router.delete("/{todoId}/dependencies/{dependencyTodoId}")
async def remove_dependency(
    todoId: int,
    dependencyTodoId: int,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await todos_service.remove_dependency(session, todoId, dependencyTodoId, user_id)


@router.patch("/{todoId}", response_model=TodoResponse)
async def update_todo(
    todoId: int,
    payload: TodoPatchRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await todos_service.update_todo(session, todoId, payload, user_id)


@router.delete(
    "/{todoId}",
    summary="할 일 또는 루틴의 선택한 회차만 삭제",
    description="routineId가 있어도 지정한 todoId 하나만 삭제합니다. 전체 루틴 삭제는 DELETE /api/v1/todos/routines/{routineId}를 사용합니다.",
)
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


@router.patch("/{todoId}/uncomplete")
async def uncomplete_todo(
    todoId: int,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await todos_service.uncomplete_todo(session, todoId, user_id)


@router.post("/{todoId}/dependencies", status_code=status.HTTP_201_CREATED)
async def create_dependency(
    todoId: int,
    payload: DependencyCreateRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await todos_service.create_dependency(session, todoId, payload, user_id)


@router.post("/{todoId}/bets", status_code=status.HTTP_201_CREATED, response_model=BetResponse)
async def create_bet(
    todoId: int,
    payload: BetCreateRequest,
    user_id: int = Depends(require_access_token),
    session: AsyncSession = Depends(get_session),
):
    return await todos_service.create_bet_for_todo(session, todoId, payload, user_id)
