"""Opt-in tests: local disposable PostgreSQL only; each test gets its own schema."""

import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text

from app.infrastructure import database
from app.infrastructure.database import Notification, Todo, TodoRoutine
from tests.conftest import (
    add_member,
    auth_headers,
    make_category,
    make_group,
    make_todo,
    make_user,
)

pytestmark = pytest.mark.skipif(
    not os.getenv("TLITODOS_TEST_DATABASE_URL"), reason="requires disposable local PostgreSQL"
)


@pytest.mark.parametrize("legacy_routines", [False, True])
async def test_startup_migrates_old_schema_twice_without_losing_rows(
    engine, session_factory, db, monkeypatch, legacy_routines
):
    await make_user(db, 41)
    await make_group(db, 10, "preserved-group")
    await add_member(db, 10, 41, "LEADER")
    category = await make_category(db, 41)
    todo = await make_todo(db, 41, category.id, group_id=10, title="기존 제목은 자르지 않음" * 5)
    todo.due_date = "2026-09-08T21:05:00+09:00"
    todo_id, category_id = todo.id, category.id
    if legacy_routines:
        routine = TodoRoutine(user_id=41, request_id=str(uuid4()), definition={}, creation_result={})
        db.add(routine)
        await db.flush()
        todo.routine_id = routine.id
    await db.commit()
    await db.close()
    async with engine.begin() as connection:
        await connection.execute(text("ALTER TABLE users DROP COLUMN time_format"))
        await connection.execute(text("ALTER TABLE todos ADD COLUMN visibility VARCHAR(20) NOT NULL DEFAULT 'PRIVATE'"))
        await connection.execute(text("DROP TABLE notifications"))
        for column in ("description", "start_date", "time", "timezone", "occurrence_date"):
            await connection.execute(text(f"ALTER TABLE todos DROP COLUMN {column}"))
        await connection.execute(text("ALTER TABLE diaries DROP COLUMN date"))
        if legacy_routines:
            await connection.execute(text("ALTER TABLE todo_routines DROP COLUMN deleted_at"))
        else:
            await connection.execute(text("ALTER TABLE todos DROP COLUMN routine_id"))
            await connection.execute(text("DROP TABLE todo_routines"))
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", session_factory)
    await database.init_db()
    async with engine.begin() as connection:
        assert await connection.scalar(text("SELECT time_format FROM users WHERE id=41")) == "12H"
        await connection.execute(text("UPDATE users SET time_format='24H' WHERE id=41"))
    await database.init_db()
    async with engine.connect() as connection:
        assert await connection.scalar(text("SELECT time_format FROM users WHERE id=41")) == "24H"
        columns = set(
            await connection.scalars(
                text(
                    "SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='todos'"
                )
            )
        )
        assert "visibility" not in columns
        assert "group_id" in columns
        assert await connection.scalar(text("SELECT count(*) FROM groups")) == 1
        assert await connection.scalar(text("SELECT count(*) FROM group_members WHERE user_id=1")) == 0
        assert await connection.scalar(text("SELECT name FROM groups WHERE id=10")) == "preserved-group"
        assert (
            await connection.scalar(text("SELECT role FROM group_members WHERE group_id=10 AND user_id=41")) == "LEADER"
        )
    async with session_factory() as fresh:
        restored = await fresh.get(Todo, todo_id)
        assert restored.title == "기존 제목은 자르지 않음" * 5
        assert restored.category_id == category_id
        assert restored.group_id == 10
        assert restored.start_date.isoformat() == restored.due_date == "2026-09-08"
        assert restored.time.hour == 21 and restored.time.minute == 5
        assert restored.description == ""
        assert (restored.occurrence_date is not None) == legacy_routines


async def test_concurrent_notification_read_all_counts_each_row_once(client, db):
    from tests.test_notification_unread_status import notification, setup

    await setup(db)
    rows = [await notification(db, "TODO_COMPLETED") for _ in range(20)]
    other = await notification(db, "DIARY_CREATED")
    responses = await asyncio.gather(
        *[client.patch("/api/v1/notifications/todo-completed/read-all", headers=auth_headers(2)) for _ in range(4)]
    )
    assert all(response.status_code == 200 for response in responses)
    assert sorted(response.json()["updatedCount"] for response in responses) == [0, 0, 0, 20]
    for row in rows:
        await db.refresh(row)
        assert row.read_at is not None
    await db.refresh(other)
    assert other.read_at is None


async def test_concurrent_creation_and_deletion_do_not_duplicate_or_resurrect(client, db):
    await make_user(db, 1)
    category = await make_category(db, 1)
    payload = {
        "requestId": str(uuid4()),
        "title": "운동",
        "categoryId": category.id,
        "startDate": "2026-09-01",
        "endDate": "2026-09-30",
    }
    results = await asyncio.gather(
        *[client.post("/api/v1/todos/routines", json=payload, headers=auth_headers(1)) for _ in range(10)]
    )
    assert all(result.status_code == 201 for result in results)
    assert all(result.json() == results[0].json() for result in results)
    assert await db.scalar(select(func.count(Todo.id))) == 30
    assert await db.scalar(select(func.count(TodoRoutine.id))) == 1
    routine_id = results[0].json()["routineId"]
    deleted = await asyncio.gather(
        *[client.delete(f"/api/v1/todos/routines/{routine_id}", headers=auth_headers(1)) for _ in range(3)]
    )
    assert sorted(result.json()["deletedCount"] for result in deleted) == [0, 0, 30]
    assert (await client.post("/api/v1/todos/routines", json=payload, headers=auth_headers(1))).status_code == 410
    assert await db.scalar(select(func.count(Todo.id))) == 0


async def test_concurrent_conflicting_requests_and_dependency_cycles(client, db):
    await make_user(db, 1)
    category = await make_category(db, 1)
    payload = {
        "requestId": str(uuid4()),
        "title": "운동",
        "categoryId": category.id,
        "startDate": "2026-09-01",
        "endDate": "2026-09-01",
    }
    results = await asyncio.gather(
        *[
            client.post("/api/v1/todos/routines", json={**payload, "title": title}, headers=auth_headers(1))
            for title in ("운동", "독서")
        ]
    )
    assert sorted(result.status_code for result in results) == [201, 409]
    first = await make_todo(db, 1, category.id)
    second = await make_todo(db, 1, category.id)
    results = await asyncio.gather(
        *[
            client.put(f"/api/v1/todos/{a}/dependencies", json={"dependencyTodoIds": [b]}, headers=auth_headers(1))
            for a, b in ((first.id, second.id), (second.id, first.id))
        ]
    )
    assert sorted(result.status_code for result in results) == [200, 422]


async def test_concurrent_diary_publish_creates_one_notification(client, db):
    await make_user(db, 1)
    await make_user(db, 2)
    await make_group(db, 10)
    await add_member(db, 10, 1)
    await add_member(db, 10, 2)
    response = await client.post(
        "/api/v1/diaries", json={"content": "일기", "visibility": "PRIVATE"}, headers=auth_headers(1)
    )
    diary_id = response.json()["diaryId"]
    results = await asyncio.gather(
        *[
            client.patch(f"/api/v1/diaries/{diary_id}", json={"visibility": "PUBLIC"}, headers=auth_headers(1))
            for _ in range(4)
        ]
    )
    assert all(result.status_code == 200 for result in results)
    assert await db.scalar(select(func.count(Notification.id))) == 1


async def test_owner_graph_lock_allows_completion_notification_fk_checks(session_factory, db):
    from app.application import todos_service
    from app.infrastructure.database import User

    await make_user(db, 1)
    await make_user(db, 2)
    await make_group(db, 10)
    await add_member(db, 10, 1)
    await add_member(db, 10, 2)
    category = await make_category(db, 1)
    todo = await make_todo(db, 1, category.id)
    # A pending routine delete holds the owner's graph lock. Completion must be
    # able to finish its FK inserts before that deletion acquires the Todo lock.
    async with session_factory() as deletion, session_factory() as completion:
        await deletion.scalar(select(User.id).where(User.id == 1).with_for_update(key_share=True))
        result = await asyncio.wait_for(todos_service.complete_todo(completion, todo.id, 1), timeout=3)
        assert result["isCompleted"] is True
        await deletion.rollback()


async def test_invalid_legacy_date_aborts_additive_migration(engine, db):
    from app.infrastructure.migrations import migrate_design_schema

    await make_user(db, 1)
    category = await make_category(db, 1)
    todo = await make_todo(db, 1, category.id)
    todo.due_date = "not-a-date"
    await db.commit()
    await db.close()
    async with engine.begin() as connection:
        await connection.execute(text("ALTER TABLE todos DROP COLUMN description"))
    with pytest.raises(ValueError, match="invalid legacy due_date"):
        async with engine.begin() as connection:
            await migrate_design_schema(connection)
    async with engine.connect() as connection:
        exists = await connection.scalar(
            text(
                "SELECT count(*) FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='todos' AND column_name='description'"
            )
        )
        assert exists == 0  # DDL performed before validation was rolled back too.
