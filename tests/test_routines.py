from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.application.routines_service import create_routine
from app.infrastructure.database import Todo, TodoRoutine
from app.presentation.v1.todos.routines_controller import RoutineCreateRequest
from tests.conftest import auth_headers, make_category, make_user


async def setup_request(db):
    await make_user(db, 1)
    category = await make_category(db, 1)
    return {
        "requestId": str(uuid4()), "title": "운동", "categoryId": category.id,
        "startDate": "2026-09-01", "endDate": "2026-09-30",
    }


async def test_single_request_creates_month_with_independent_completion(client, db):
    payload = await setup_request(db)
    response = await client.post("/api/v1/todos/routines", json=payload, headers=auth_headers(1))
    assert response.status_code == 201
    result = response.json()
    assert result["createdCount"] == 30
    assert [item["dueDate"] for item in result["occurrences"]] == [f"2026-09-{day:02}" for day in range(1, 31)]
    assert len({item["todoId"] for item in result["occurrences"]}) == 30

    todo_id = result["occurrences"][0]["todoId"]
    assert (await client.patch(f"/api/v1/todos/{todo_id}/complete", headers=auth_headers(1))).status_code == 200
    listing = await client.get("/api/v1/todos", params={"date": "2026-09-02"}, headers=auth_headers(1))
    assert len(listing.json()) == 1
    assert listing.json()[0]["isRoutine"] is True
    assert listing.json()[0]["routineId"] == result["routineId"]
    assert listing.json()[0]["isCompleted"] is False
    calendar = await client.get("/api/v1/todos/daily-status", params={"month": "2026-09"}, headers=auth_headers(1))
    assert calendar.json()[0]["incompleteCount"] == 0
    assert calendar.json()[1]["incompleteCount"] == 1
    assert calendar.json()[0]["categoryStatuses"][0]["isCompleted"] is True


async def test_weekdays_and_retry_are_canonical_and_idempotent(client, db):
    payload = await setup_request(db)
    payload.update(startDate="2026-09-07", endDate="2026-09-13", weekdays=[5, 1, 3, 1])
    first = await client.post("/api/v1/todos/routines", json=payload, headers=auth_headers(1))
    assert first.status_code == 201
    assert [item["dueDate"] for item in first.json()["occurrences"]] == ["2026-09-07", "2026-09-09", "2026-09-11"]
    payload["weekdays"] = [1, 3, 5]
    retry = await client.post("/api/v1/todos/routines", json=payload, headers=auth_headers(1))
    assert retry.status_code == 201
    assert retry.json() == first.json()
    assert await db.scalar(select(func.count(Todo.id))) == 3
    assert await db.scalar(select(func.count(TodoRoutine.id))) == 1
    payload["title"] = "다른 할일"
    conflict = await client.post("/api/v1/todos/routines", json=payload, headers=auth_headers(1))
    assert conflict.status_code == 409
    assert await db.scalar(select(func.count(Todo.id))) == 3


async def test_cannot_use_other_users_category_or_change_their_occurrence(client, db):
    payload = await setup_request(db)
    await make_user(db, 2)
    denied = await client.post("/api/v1/todos/routines", json=payload, headers=auth_headers(2))
    assert denied.status_code == 404
    assert await db.scalar(select(func.count(TodoRoutine.id))) == 0
    created = await client.post("/api/v1/todos/routines", json=payload, headers=auth_headers(1))
    todo_id = created.json()["occurrences"][0]["todoId"]
    assert (await client.patch(f"/api/v1/todos/{todo_id}/complete", headers=auth_headers(2))).status_code == 404


@pytest.mark.parametrize("updates", [
    {"endDate": "2026-08-31"},
    {"endDate": "2027-09-02"},
    {"startDate": "2026-02-30"},
    {"weekdays": []},
    {"weekdays": [0]},
    {"weekdays": [8]},
    {"weekdays": [True]},
    {"startDate": "2026-09-07", "endDate": "2026-09-07", "weekdays": [2]},
    {"requestId": "not-a-uuid"},
])
async def test_invalid_routine_creates_nothing(client, db, updates):
    payload = await setup_request(db)
    payload.update(updates)
    response = await client.post("/api/v1/todos/routines", json=payload, headers=auth_headers(1))
    assert response.status_code == 422
    assert await db.scalar(select(func.count(Todo.id))) == 0
    assert await db.scalar(select(func.count(TodoRoutine.id))) == 0


@pytest.mark.parametrize("start,end,count", [
    ("2026-12-31", "2027-01-01", 2),
    ("2028-02-28", "2028-03-01", 3),
    ("2026-09-01", "2026-09-01", 1),
    ("2028-01-01", "2028-12-31", 366),
])
async def test_calendar_boundaries(client, db, start, end, count):
    payload = await setup_request(db)
    payload.update(startDate=start, endDate=end)
    result = await client.post("/api/v1/todos/routines", json=payload, headers=auth_headers(1))
    assert result.status_code == 201
    assert result.json()["createdCount"] == count
    assert result.json()["occurrences"][0]["dueDate"] == start
    assert result.json()["occurrences"][-1]["dueDate"] == end


async def test_failed_commit_rolls_back_entire_series(db, monkeypatch):
    payload = RoutineCreateRequest(**await setup_request(db))

    async def fail_commit():
        # Confirm failure happens after all occurrences have been inserted.
        assert await db.scalar(select(func.count(Todo.id))) == 30
        raise RuntimeError("simulated transaction failure")

    with monkeypatch.context() as patch:
        patch.setattr(db, "commit", fail_commit)
        with pytest.raises(RuntimeError, match="simulated transaction failure"):
            await create_routine(db, payload, 1)
    assert await db.scalar(select(func.count(Todo.id))) == 0
    assert await db.scalar(select(func.count(TodoRoutine.id))) == 0
    assert (await create_routine(db, payload, 1))["createdCount"] == 30


async def test_request_id_is_scoped_to_user(client, db):
    payload = await setup_request(db)
    first = await client.post("/api/v1/todos/routines", json=payload, headers=auth_headers(1))
    await make_user(db, 2)
    other_category = await make_category(db, 2)
    payload["categoryId"] = other_category.id
    second = await client.post("/api/v1/todos/routines", json=payload, headers=auth_headers(2))
    assert second.status_code == 201
    assert first.json()["routineId"] != second.json()["routineId"]
