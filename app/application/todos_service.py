import heapq
from calendar import monthrange
from datetime import date

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.groups_service import require_shared_group_membership
from app.infrastructure.database import (
    Bet,
    Category,
    Todo,
    User,
    todo_to_response,
)
from app.shared.scheduling import today, todo_dates, utcnow


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
    todo = await session.scalar(select(Todo).where(Todo.id == todo_id, Todo.user_id == user_id).with_for_update())
    if todo is None:
        raise HTTPException(status_code=404, detail={"message": "존재하지 않는 할일입니다."})
    return todo


async def create_todo(session: AsyncSession, payload, user_id: int) -> dict:
    category = await session.scalar(
        select(Category).where(Category.id == payload.category_id, Category.user_id == user_id)
    )
    if category is None:
        raise HTTPException(status_code=404, detail={"message": "존재하지 않는 카테고리입니다."})
    start = payload.start_date or payload.due_date or today()
    if payload.due_date and payload.due_date < start:
        raise HTTPException(422, detail={"message": "마감일은 시작일보다 빠를 수 없습니다."})
    todo = Todo(
        user_id=user_id,
        title=payload.title,
        description=payload.description,
        start_date=start,
        time=payload.time,
        timezone=payload.timezone,
        category_id=payload.category_id,
        importance=payload.importance,
        hardship=payload.hardship,
        due_date=payload.due_date.isoformat() if payload.due_date else None,
        x=payload.x,
        y=payload.y,
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
    date: date | None,
) -> list[dict]:
    owner_id = target_user_id if target_user_id is not None else requester_id

    if owner_id != requester_id and group_id is not None:
        await require_shared_group_membership(session, group_id, requester_id, owner_id)

    statement = select(Todo).where(Todo.user_id == owner_id)
    if date is not None:
        statement = statement.where(*overlaps(date, date))
    todos = list((await session.scalars(statement.order_by(Todo.id))).all())
    if date is not None:
        todos = [todo for todo in todos if todo_dates(todo)[0] <= date <= todo_dates(todo)[1]]
    return [todo_to_response(todo) for todo in sort_todos_by_dependencies(todos)]


async def list_daily_todo_statuses(
    session: AsyncSession, user_id: int, month: str, target_user_id: int | None = None, group_id: int | None = None
) -> list[dict]:
    owner_id = target_user_id if target_user_id is not None else user_id
    if owner_id != user_id and group_id is not None:
        await require_shared_group_membership(session, group_id, user_id, owner_id)
    try:
        first_day = date.fromisoformat(f"{month}-01")
    except ValueError as error:
        raise HTTPException(status_code=422, detail={"message": "month는 YYYY-MM 형식이어야 합니다."}) from error

    last_day = monthrange(first_day.year, first_day.month)[1]
    dates = [date(first_day.year, first_day.month, day).isoformat() for day in range(1, last_day + 1)]
    statuses_by_date = {due_date: {"incompleteCount": 0, "categoryStatuses": {}} for due_date in dates}

    todos = await session.scalars(
        select(Todo)
        .where(Todo.user_id == owner_id, *overlaps(first_day, date(first_day.year, first_day.month, last_day)))
        .order_by(Todo.id)
    )
    for todo in todos:
        start, end = todo_dates(todo)
        for day in dates:
            if not start.isoformat() <= day <= end.isoformat():
                continue
            daily_status = statuses_by_date[day]
            if not todo.is_completed:
                daily_status["incompleteCount"] += 1
            category_statuses = daily_status["categoryStatuses"]
            category_statuses[todo.category_id] = category_statuses.get(todo.category_id, False) or todo.is_completed

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
    updates = payload.model_dump(exclude_unset=True)
    if "category_id" in updates:
        category = await session.scalar(
            select(Category.id).where(Category.id == updates["category_id"], Category.user_id == user_id)
        )
        if category is None:
            raise HTTPException(404, detail={"message": "존재하지 않는 카테고리입니다."})
    start = updates.get("start_date", todo_dates(todo)[0])
    end = updates.get("due_date", date.fromisoformat(todo.due_date) if todo.due_date else None)
    if end and end < start:
        raise HTTPException(422, detail={"message": "마감일은 시작일보다 빠를 수 없습니다."})
    if "due_date" in updates:
        updates["due_date"] = end.isoformat() if end else None
    # Freeze the original selected date when changing the deadline of a legacy row.
    updates.setdefault("start_date", start)
    for key, value in updates.items():
        setattr(todo, key, value)
    await session.commit()
    await session.refresh(todo)
    return todo_to_response(todo)


async def delete_todo(session: AsyncSession, todo_id: int, user_id: int) -> dict:
    await session.scalar(select(User.id).where(User.id == user_id).with_for_update(key_share=True))
    todo = await find_todo(session, todo_id, user_id)
    await clean_dependencies(session, user_id, {todo_id})
    await session.delete(todo)
    await session.commit()
    return {"success": True, "message": "할일이 삭제되었습니다."}


async def create_subtask(session: AsyncSession, todo_id: int, payload, user_id: int) -> dict:
    todo = await find_todo(session, todo_id, user_id)
    subtask = {
        "subtaskId": max((task["subtaskId"] for task in todo.subtasks), default=0) + 1,
        "content": payload.content,
        "isCompleted": False,
    }
    todo.subtasks = [*todo.subtasks, subtask]
    await session.commit()
    return subtask


async def complete_todo(session: AsyncSession, todo_id: int, user_id: int) -> dict:
    todo = await find_todo(session, todo_id, user_id)
    if any(not subtask["isCompleted"] for subtask in todo.subtasks):
        raise HTTPException(status_code=400, detail={"message": "완료되지 않은 하위 할일이 있습니다."})
    if not todo.is_completed:
        from app.application.notifications_service import notify_peers

        todo.is_completed = True
        todo.completed_at = utcnow()
        await notify_peers(
            session, user_id, "TODO_COMPLETED", f"todo:{todo.id}:{todo.completed_at.isoformat()}", todo_id=todo.id
        )
    await session.commit()
    return {"success": True, "todoId": todo_id, "isCompleted": True}


async def uncomplete_todo(session: AsyncSession, todo_id: int, user_id: int) -> dict:
    todo = await find_todo(session, todo_id, user_id)
    todo.is_completed = False
    todo.completed_at = None
    await session.commit()
    return {"success": True, "todoId": todo_id, "isCompleted": False}


async def create_dependency(session: AsyncSession, todo_id: int, payload, user_id: int) -> dict:
    await session.scalar(select(User.id).where(User.id == user_id).with_for_update(key_share=True))
    todo = await find_todo(session, todo_id, user_id)
    await set_dependencies(session, todo_id, [*todo.dependencies, payload.dependency_todo_id], user_id)
    return {"success": True, "todoId": todo_id, "dependencyTodoId": payload.dependency_todo_id}


async def create_bet_for_todo(session: AsyncSession, todo_id: int, payload, user_id: int) -> dict:
    todo = await session.get(Todo, todo_id)
    if todo is None:
        raise HTTPException(404, detail={"message": "존재하지 않는 할일입니다."})
    if todo.user_id == user_id:
        raise HTTPException(400, detail={"message": "자신의 할일에는 내기를 요청할 수 없습니다."})
    bet = Bet(todo_id=todo_id, content=payload.content, requester_id=user_id)
    session.add(bet)
    await session.flush()
    from app.infrastructure.database import Notification

    session.add(
        Notification(
            recipient_id=todo.user_id,
            actor_id=user_id,
            type="BET_REQUESTED",
            event_key=f"bet:{bet.id}",
            todo_id=todo.id,
            bet_id=bet.id,
        )
    )
    await session.commit()
    await session.refresh(bet)
    from app.application.bets_service import get_bet

    return await get_bet(session, bet.id, user_id)


async def get_todo(session, todo_id):
    todo = await session.get(Todo, todo_id)
    if todo is None:
        raise HTTPException(404, detail={"message": "존재하지 않는 할일입니다."})
    return todo_to_response(todo)


async def clean_dependencies(session, user_id, deleted_ids):
    for todo in await session.scalars(select(Todo).where(Todo.user_id == user_id)):
        if set(todo.dependencies) & deleted_ids:
            todo.dependencies = [value for value in todo.dependencies if value not in deleted_ids]


async def set_dependencies(session, todo_id, dependency_ids, user_id):
    # Hobby/seeded categories are allowed in both directions, regardless of ID.
    # Serialize graph mutations per user so concurrent edits cannot create a cycle.
    await session.scalar(select(User.id).where(User.id == user_id).with_for_update(key_share=True))
    todo = await find_todo(session, todo_id, user_id)
    ids = sorted(set(dependency_ids))
    nodes = {node.id: node for node in await session.scalars(select(Todo).where(Todo.user_id == user_id))}
    if any(value not in nodes for value in ids):
        raise HTTPException(404, detail={"message": "존재하지 않는 선행 할일입니다."})
    graph = {node.id: node.dependencies for node in nodes.values()}
    graph[todo_id] = ids
    stack, visited = list(ids), set()
    while stack:
        current = stack.pop()
        if current == todo_id:
            raise HTTPException(422, detail={"message": "자기 자신이나 순환 관계를 연결할 수 없습니다."})
        if current not in visited:
            visited.add(current)
            stack.extend(graph.get(current, []))
    todo.dependencies = ids
    await session.commit()
    return {"success": True, "todoId": todo_id, "dependencies": ids}


async def remove_dependency(session, todo_id, dependency_id, user_id):
    await session.scalar(select(User.id).where(User.id == user_id).with_for_update(key_share=True))
    todo = await find_todo(session, todo_id, user_id)
    return await set_dependencies(
        session, todo_id, [value for value in todo.dependencies if value != dependency_id], user_id
    )


def overlaps(start, end):
    # SQL bounds reduce the candidate set; todo_dates performs the exact legacy
    # fallback consistently in both the list and the monthly aggregation.
    return (
        or_(Todo.start_date <= end, Todo.start_date.is_(None)),
        or_(Todo.due_date >= start.isoformat(), Todo.due_date.is_(None)),
    )
