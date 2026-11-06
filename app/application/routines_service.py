from copy import deepcopy
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import IntegrityError

from app.infrastructure.database import Category, Todo, TodoRoutine, User
from app.shared.scheduling import utcnow

MAX_OCCURRENCES = 1000


def occurrence_dates(payload):
    start, end, rule = payload.start_date, payload.end_date, payload.recurrence
    dates = []
    if rule.frequency in {"DAILY", "WEEKLY"}:
        # Monday starts the ISO week containing the start date, not the next week.
        anchor = start - timedelta(days=start.weekday())
        for offset in range((end - start).days + 1):
            day = start + timedelta(days=offset)
            if rule.frequency == "WEEKLY" and (
                day.isoweekday() not in rule.weekdays or ((day - anchor).days // 7) % rule.interval
            ):
                continue
            dates.append(day)
            if len(dates) > MAX_OCCURRENCES:
                break
    elif rule.frequency == "MONTHLY":
        for month_index in range(start.year * 12 + start.month - 1, end.year * 12 + end.month):
            year, month = divmod(month_index, 12)
            try:
                day = date(year, month + 1, start.day)
            except ValueError:
                continue
            if start <= day <= end:
                dates.append(day)
    else:
        for year in range(start.year, end.year + 1):
            try:
                day = date(year, start.month, start.day)
            except ValueError:
                continue
            if start <= day <= end:
                dates.append(day)
    if not dates or len(dates) > MAX_OCCURRENCES:
        raise HTTPException(422, detail={"message": "기간 내 실제 반복 횟수는 1~1,000회여야 합니다."})
    return dates


def canonical_definition(payload, source_todo_id=None):
    result = payload.model_dump(mode="json", by_alias=True, exclude={"request_id", "weekdays"})
    # Preserve replay compatibility with definitions written before dependencies
    # were accepted. For conversion, [] explicitly clears inherited references.
    if "dependency_todo_ids" not in payload.model_fields_set or (
        source_todo_id is None and not payload.dependency_todo_ids
    ):
        result.pop("dependencyTodoIds", None)
    if source_todo_id is not None:
        result["sourceTodoId"] = source_todo_id
    return result


def replay_creation(routine, definition):
    if routine.deleted_at:
        raise HTTPException(410, detail={"message": "삭제한 루틴입니다. 같은 요청으로 재생성하지 않습니다."})
    stored = routine.definition
    if "recurrence" not in stored:
        from app.presentation.v1.todos.routines_controller import RoutineCreateRequest

        stored = canonical_definition(RoutineCreateRequest(requestId=routine.request_id, **stored))
    if stored != definition:
        raise HTTPException(409, detail={"message": "다른 내용에 사용된 requestId입니다."})
    return routine.creation_result


async def dependencies_by_date(session, dependency_ids, dates, user_id, source=None):
    if not dependency_ids:
        return {day: [] for day in dates}
    # Read the owner's graph once: resolve all selected series in memory rather
    # than querying for every generated occurrence. The caller holds the owner lock.
    nodes = {todo.id: todo for todo in await session.scalars(select(Todo).where(Todo.user_id == user_id))}
    if any(todo_id not in nodes for todo_id in dependency_ids):
        raise HTTPException(404, detail={"message": "존재하지 않는 선행 할일입니다."})
    if source and source.id in dependency_ids:
        raise HTTPException(422, detail={"message": "자기 자신이나 순환 관계를 연결할 수 없습니다."})
    selected = [nodes[todo_id] for todo_id in dependency_ids]
    routine_ids = {todo.routine_id for todo in selected if todo.routine_id is not None}
    occurrences = {
        (todo.routine_id, todo.occurrence_date): todo.id
        for todo in nodes.values()
        if todo.routine_id in routine_ids and todo.occurrence_date is not None
    }
    result = {}
    for day in dates:
        ids = {occurrences.get((todo.routine_id, day)) if todo.routine_id is not None else todo.id for todo in selected}
        result[day] = sorted(ids - {None})
    if source:
        # Only the first occurrence reuses an existing ID, so only it can close
        # a cycle through the existing graph. Later occurrences have new IDs.
        stack, visited = list(result[dates[0]]), set()
        while stack:
            current = stack.pop()
            if current == source.id:
                raise HTTPException(422, detail={"message": "자기 자신이나 순환 관계를 연결할 수 없습니다."})
            if current not in visited and current in nodes:
                visited.add(current)
                stack.extend(nodes[current].dependencies)
    return result


async def create_routine(session, payload, user_id, source_todo_id=None):
    definition = canonical_definition(payload, source_todo_id)
    lookup = select(TodoRoutine).where(
        TodoRoutine.user_id == user_id, TodoRoutine.request_id == str(payload.request_id)
    )
    # FOR NO KEY UPDATE serializes this owner's graph/series operations while
    # allowing FK checks from concurrent completion notifications (no deadlock).
    await session.scalar(select(User.id).where(User.id == user_id).with_for_update(key_share=True))
    existing = await session.scalar(lookup)
    if existing:
        return replay_creation(existing, definition)
    source = None
    if source_todo_id is not None:
        from app.application.todos_service import find_todo

        source = await find_todo(session, source_todo_id, user_id)
        if source.routine_id or source.is_routine:
            raise HTTPException(409, detail={"message": "이미 루틴에 속한 할일입니다."})
        fields = {
            key: getattr(source, key)
            for key in ("title", "description", "category_id", "importance", "hardship", "x", "y")
        }
    else:
        fields = {
            key: getattr(payload, key)
            for key in ("title", "description", "category_id", "importance", "hardship", "x", "y")
        }
    if (
        await session.scalar(
            select(Category.id).where(Category.id == fields["category_id"], Category.user_id == user_id)
        )
        is None
    ):
        raise HTTPException(404, detail={"message": "존재하지 않는 카테고리입니다."})
    if len(fields["title"]) > 40 or len(fields["description"]) > 100:
        raise HTTPException(422, detail={"message": "기존 할일을 제목 40자, 설명 100자 이내로 수정한 뒤 전환하세요."})
    dates = occurrence_dates(payload)
    dependency_ids = payload.dependency_todo_ids
    if "dependency_todo_ids" not in payload.model_fields_set:
        dependency_ids = list(source.dependencies) if source else []
    planned_dependencies = await dependencies_by_date(session, dependency_ids, dates, user_id, source)
    routine = TodoRoutine(user_id=user_id, request_id=str(payload.request_id), definition=definition)
    try:
        session.add(routine)
        await session.flush()
        occurrences, values = [], []
        for day in dates:
            if source is not None and day == dates[0]:
                source.routine_id = routine.id
                source.is_routine = True
                source.occurrence_date = source.start_date = day
                source.due_date = day.isoformat()
                source.time, source.timezone = payload.time, payload.timezone
                source.dependencies = planned_dependencies[day]
                occurrences.append({"todoId": source.id, "dueDate": day.isoformat()})
                continue
            subtasks = deepcopy(source.subtasks) if source else []
            for subtask in subtasks:
                subtask["isCompleted"] = False
            values.append(
                {
                    **fields,
                    "user_id": user_id,
                    "routine_id": routine.id,
                    "start_date": day,
                    "due_date": day.isoformat(),
                    "occurrence_date": day,
                    "time": payload.time,
                    "timezone": payload.timezone,
                    "is_routine": True,
                    "is_completed": False,
                    "subtasks": subtasks,
                    "dependencies": planned_dependencies[day],
                }
            )
        if values:
            rows = (await session.execute(insert(Todo).returning(Todo.id, Todo.due_date), values)).all()
            occurrences.extend({"todoId": row.id, "dueDate": row.due_date} for row in rows)
        result = {
            "routineId": routine.id,
            "createdCount": len(dates),
            "occurrences": sorted(occurrences, key=lambda row: row["dueDate"]),
        }
        routine.creation_result = result
        await session.commit()
        return result
    except IntegrityError:
        await session.rollback()
        existing = await session.scalar(lookup)
        if existing:
            return replay_creation(existing, definition)
        raise
    except Exception:
        await session.rollback()
        raise


async def owned_routine(session, routine_id, user_id):
    routine = await session.scalar(
        select(TodoRoutine).where(TodoRoutine.id == routine_id, TodoRoutine.user_id == user_id).with_for_update()
    )
    if routine is None:
        raise HTTPException(404, detail={"message": "존재하지 않는 루틴입니다."})
    return routine


async def get_routine(session, routine_id, user_id):
    routine = await owned_routine(session, routine_id, user_id)
    if routine.deleted_at:
        raise HTTPException(410, detail={"message": "삭제한 루틴입니다."})
    return {"routineId": routine.id, "definition": routine.definition}


async def delete_routine(session, routine_id, user_id):
    from app.application.todos_service import clean_dependencies

    await session.scalar(select(User.id).where(User.id == user_id).with_for_update(key_share=True))
    routine = await owned_routine(session, routine_id, user_id)
    ids = set(await session.scalars(select(Todo.id).where(Todo.routine_id == routine_id, Todo.user_id == user_id)))
    await clean_dependencies(session, user_id, ids)
    await session.flush()
    await session.execute(delete(Todo).where(Todo.id.in_(ids)))
    # A tombstone prevents delayed creation requests from resurrecting tasks.
    routine.deleted_at = routine.deleted_at or utcnow()
    await session.commit()
    return {"success": True, "routineId": routine_id, "deletedCount": len(ids)}
