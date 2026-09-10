from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.infrastructure.database import Bet, Notification, Todo, TodoRoutine
from tests.conftest import auth_headers, make_category, make_user


@pytest.mark.parametrize("completed", [False, True])
async def test_delete_one_occurrence_preserves_other_dates_and_retries(client, db, completed):
    await make_user(db, 1)
    await make_user(db, 2)
    category = await make_category(db, 1)
    payload = {
        "requestId": str(uuid4()),
        "title": "운동",
        "categoryId": category.id,
        "startDate": "2026-09-08",
        "endDate": "2026-09-10",
    }
    created = await client.post("/api/v1/todos/routines", json=payload, headers=auth_headers(1))
    assert created.status_code == 201
    result = created.json()
    first, target, last = [item["todoId"] for item in result["occurrences"]]
    if completed:
        assert (await client.patch(f"/api/v1/todos/{target}/complete", headers=auth_headers(1))).status_code == 200
    # References and bets on the deleted occurrence are cleaned, not other dates'.
    assert (
        await client.put(
            f"/api/v1/todos/{last}/dependencies",
            json={"dependencyTodoIds": [first, target]},
            headers=auth_headers(1),
        )
    ).status_code == 200
    for todo_id in (first, target):
        bet = await client.post(f"/api/v1/todos/{todo_id}/bets", json={"content": "도전"}, headers=auth_headers(2))
        assert bet.status_code == 201
    assert (await client.delete(f"/api/v1/todos/{target}", headers=auth_headers(2))).status_code == 404
    assert await db.scalar(select(func.count(Todo.id))) == 3
    deleted = await client.delete(f"/api/v1/todos/{target}", headers=auth_headers(1))
    assert deleted.status_code == 200 and deleted.json()["success"] is True
    assert (await client.delete(f"/api/v1/todos/{target}", headers=auth_headers(1))).status_code == 404
    assert set(await db.scalars(select(Todo.id))) == {first, last}
    assert (await db.get(Todo, last)).dependencies == [first]
    assert list(await db.scalars(select(Bet.todo_id))) == [first]
    assert list(await db.scalars(select(Notification.todo_id))) == [first]
    assert (await db.get(TodoRoutine, result["routineId"])).deleted_at is None
    for day, expected in ((8, [first]), (9, []), (10, [last])):
        listing = await client.get("/api/v1/todos", params={"date": f"2026-09-{day:02}"}, headers=auth_headers(1))
        assert [item["todoId"] for item in listing.json()] == expected
    calendar = await client.get("/api/v1/todos/daily-status", params={"month": "2026-09"}, headers=auth_headers(1))
    assert [calendar.json()[day - 1]["incompleteCount"] for day in (8, 9, 10)] == [1, 0, 1]
    assert calendar.json()[8]["categoryStatuses"] == []
    retry = await client.post("/api/v1/todos/routines", json=payload, headers=auth_headers(1))
    assert retry.json() == result  # Immutable creation receipt, not the current list.
    assert set(await db.scalars(select(Todo.id))) == {first, last}
    assert (
        await client.get(f"/api/v1/todos/routines/{result['routineId']}", headers=auth_headers(1))
    ).status_code == 200
    whole = await client.delete(f"/api/v1/todos/routines/{result['routineId']}", headers=auth_headers(1))
    assert whole.json()["deletedCount"] == 2
    assert await db.scalar(select(func.count(Todo.id))) == 0
    assert (await client.post("/api/v1/todos/routines", json=payload, headers=auth_headers(1))).status_code == 410


async def test_last_occurrence_deletion_does_not_resurrect_on_creation_retry(client, db):
    await make_user(db, 1)
    category = await make_category(db, 1)
    payload = {
        "requestId": str(uuid4()),
        "title": "한 번",
        "categoryId": category.id,
        "startDate": "2026-09-09",
        "endDate": "2026-09-09",
    }
    created = await client.post("/api/v1/todos/routines", json=payload, headers=auth_headers(1))
    result = created.json()
    todo_id = result["occurrences"][0]["todoId"]
    assert (await client.delete(f"/api/v1/todos/{todo_id}", headers=auth_headers(1))).status_code == 200
    retry = await client.post("/api/v1/todos/routines", json=payload, headers=auth_headers(1))
    assert retry.status_code == 201 and retry.json() == result
    assert await db.scalar(select(func.count(Todo.id))) == 0
    whole = await client.delete(f"/api/v1/todos/routines/{result['routineId']}", headers=auth_headers(1))
    assert whole.json()["deletedCount"] == 0
