from datetime import datetime

import pytest
from sqlalchemy import event

from app.infrastructure.database import Bet, User
from tests.conftest import auth_headers, make_todo
from tests.test_figma_contract import new_todo, setup_users


def assert_preview(bet, todo, name="요청자"):
    assert bet["requesterName"] == name
    assert bet["todoId"] == todo["todoId"]
    assert bet["todo"] == {
        key: todo[key] for key in ("todoId", "userId", "title", "description", "startDate", "dueDate")
    }


async def test_preview_on_create_detail_status_verify_and_notifications(client, db):
    category = await setup_users(db)
    requester = await db.get(User, 2)
    requester.name = "요청자"
    await db.commit()
    todo = await new_todo(client, category.id)
    created = await client.post(
        f"/api/v1/todos/{todo['todoId']}/bets", json={"content": "내기"}, headers=auth_headers(2)
    )
    assert created.status_code == 201
    bet = created.json()
    assert_preview(bet, todo)
    url = f"/api/v1/bets/{bet['betId']}"
    for user_id in (1, 2):
        response = await client.get(url, headers=auth_headers(user_id))
        assert response.status_code == 200
        assert_preview(response.json(), todo)
    assert (await client.get(url, headers=auth_headers(3))).status_code == 404
    assert (await client.get("/api/v1/bets", headers=auth_headers(3))).json() == []
    accepted = await client.patch(url + "/status", json={"status": "ACCEPTED"}, headers=auth_headers(1))
    assert accepted.status_code == 200
    assert_preview(accepted.json(), todo)
    # Model an existing uploaded proof; upload permissions are covered separately.
    row = await db.get(Bet, bet["betId"])
    row.proof_image_url = "/uploads/bet-proofs/test.png"
    await db.commit()
    verified = await client.patch(url + "/verify", json={"approved": True}, headers=auth_headers(2))
    assert verified.status_code == 200
    assert_preview(verified.json(), todo)
    items = (await client.get("/api/v1/notifications", headers=auth_headers(1))).json()["items"]
    assert_preview(items[0]["bet"], todo)
    assert items[0]["todo"] == items[0]["bet"]["todo"]
    # Names and dates are live metadata, not event-time snapshots.
    requester.name = "바뀐 이름"
    await db.commit()
    changed = await client.patch(
        f"/api/v1/todos/{todo['todoId']}", json={"title": "새 제목", "dueDate": None}, headers=auth_headers(1)
    )
    assert changed.status_code == 200
    assert_preview((await client.get(url, headers=auth_headers(1))).json(), changed.json(), "바뀐 이름")
    assert_preview((await client.get("/api/v1/bets", headers=auth_headers(2))).json()[0], changed.json(), "바뀐 이름")
    assert_preview(
        (await client.get("/api/v1/notifications", headers=auth_headers(1))).json()["items"][0]["bet"],
        changed.json(),
        "바뀐 이름",
    )


@pytest.mark.parametrize("count", [1, 20])
async def test_list_joins_preview_in_one_query_independent_of_row_count(client, db, engine, count):
    category = await setup_users(db)
    todo = await new_todo(client, category.id)
    for _ in range(count):
        db.add(Bet(todo_id=todo["todoId"], requester_id=2, content="내기"))
    await db.commit()
    queries = []

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany):
        queries.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", capture)
    try:
        response = await client.get("/api/v1/bets", headers=auth_headers(1))
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture)
    assert response.status_code == 200
    assert len(queries) == 1
    items = response.json()
    assert len(items) == count
    assert [item["betId"] for item in items] == sorted([item["betId"] for item in items], reverse=True)
    for item in items:
        assert_preview(item, todo, "user")


@pytest.mark.parametrize("due_date", [None, "2026-09-08"])
async def test_legacy_bet_without_requester_stays_visible_and_uses_todo_date_fallback(client, db, due_date):
    category = await setup_users(db)
    todo = await make_todo(db, 1, category.id)
    todo.created_at = datetime(2026, 9, 1, 12)
    todo.due_date = due_date
    db.add(Bet(todo_id=todo.id, requester_id=999, content="이전 내기"))
    await db.commit()
    response = await client.get("/api/v1/bets", headers=auth_headers(1))
    assert response.status_code == 200
    assert len(response.json()) == 1
    item = response.json()[0]
    assert item["requesterName"] is None
    assert item["todo"]["startDate"] == (due_date or "2026-09-01")
    assert item["todo"]["dueDate"] == due_date


async def test_routine_bet_preview_uses_occurrence_not_series_range(client, db):
    from uuid import uuid4

    category = await setup_users(db)
    created = await client.post(
        "/api/v1/todos/routines",
        headers=auth_headers(1),
        json={
            "requestId": str(uuid4()),
            "title": "운동",
            "categoryId": category.id,
            "startDate": "2026-09-08",
            "endDate": "2026-09-10",
        },
    )
    assert created.status_code == 201
    todo = (await client.get("/api/v1/todos", params={"date": "2026-09-09"}, headers=auth_headers(1))).json()[0]
    response = await client.post(
        f"/api/v1/todos/{todo['todoId']}/bets", json={"content": "내기"}, headers=auth_headers(2)
    )
    assert response.status_code == 201
    assert response.json()["todo"]["startDate"] == response.json()["todo"]["dueDate"] == "2026-09-09"
