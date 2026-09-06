import heapq
from calendar import monthrange
from datetime import date

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.groups_service import require_shared_group_membership
from app.infrastructure.database import Bet, Category, Todo, bet_to_response, todo_to_response


def sort_todos_by_dependencies(todos: list[Todo]) -> list[Todo]:
    todos_by_id = {todo.id: todo for todo in todos}
    indegree = {todo.id: 0 for todo in todos}
    dependents = {todo.id: [] for todo in todos}

    for todo in todos:
        dependency_ids = {
            dependency_id
            for dependency_id in todo.dependencies
            if dependency_id in todos_by_id and dependency_id != todo.id
        }
        indegree[todo.id] = len(dependency_ids)
        for dependency_id in dependency_ids:
            dependents[dependency_id].append(todo.id)

    ready = [todo_id for todo_id, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)
    sorted_ids = []

    while ready:
        todo_id = heapq.heappop(ready)
        sorted_ids.append(todo_id)
        for dependent_id in dependents[todo_id]:
            indegree[dependent_id] -= 1
            if indegree[dependent_id] == 0:
                heapq.heappush(ready, dependent_id)

    if len(sorted_ids) != len(todos):
        sorted_id_set = set(sorted_ids)
        sorted_ids.extend(todo.id for todo in todos if todo.id not in sorted_id_set)

    return [todos_by_id[todo_id] for todo_id in sorted_ids]


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


async def list_todos(
    session: AsyncSession,
    requester_id: int,
    target_user_id: int | None,
    group_id: int | None,
    date: str | None,
) -> list[dict]:
    owner_id = target_user_id if target_user_id is not None else requester_id

    if owner_id != requester_id:
        if group_id is None:
            raise HTTPException(status_code=400, detail={"message": "다른 사용자의 할일을 조회하려면 groupId가 필요합니다."})
        await require_shared_group_membership(session, group_id, requester_id, owner_id)

    statement = select(Todo).where(Todo.user_id == owner_id)
    if owner_id != requester_id:
        statement = statement.where(Todo.visibility.in_(["GROUP", "PUBLIC"]))
    if group_id is not None:
        statement = statement.where(Todo.group_id == group_id)
    if date is not None:
        statement = statement.where(or_(Todo.due_date == date, Todo.due_date.is_(None)))
    todos = list((await session.scalars(statement.order_by(Todo.id))).all())
    return [todo_to_response(todo) for todo in sort_todos_by_dependencies(todos)]


async def list_daily_todo_statuses(session: AsyncSession, user_id: int, month: str) -> list[dict]:
    try:
        first_day = date.fromisoformat(f"{month}-01")
    except ValueError as error:
        raise HTTPException(status_code=422, detail={"message": "month는 YYYY-MM 형식이어야 합니다."}) from error

    last_day = monthrange(first_day.year, first_day.month)[1]
    dates = [date(first_day.year, first_day.month, day).isoformat() for day in range(1, last_day + 1)]
    statuses_by_date = {
        due_date: {"incompleteCount": 0, "categoryStatuses": {}}
        for due_date in dates
    }

    todos = await session.scalars(
        select(Todo)
        .where(Todo.user_id == user_id, Todo.due_date.like(f"{month}-%"))
        .order_by(Todo.id)
    )
    for todo in todos:
        if todo.due_date not in statuses_by_date:
            continue
        daily_status = statuses_by_date[todo.due_date]
        if not todo.is_completed:
            daily_status["incompleteCount"] += 1
        category_statuses = daily_status["categoryStatuses"]
        category_statuses[todo.category_id] = category_statuses.get(todo.category_id, True) and todo.is_completed

    return [
        {
            "date": due_date,
            "incompleteCount": statuses_by_date[due_date]["incompleteCount"],
            "categoryStatuses": [
                {"categoryId": category_id, "isCompleted": is_completed}
                for category_id, is_completed in sorted(statuses_by_date[due_date]["categoryStatuses"].items())
            ],
        }
        for due_date in dates
    ]


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


async def uncomplete_todo(session: AsyncSession, todo_id: int, user_id: int) -> dict:
    todo = await find_todo(session, todo_id, user_id)
    todo.is_completed = False
    todo.completed_at = None
    await session.commit()
    return {"success": True, "todoId": todo_id, "isCompleted": False}


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
