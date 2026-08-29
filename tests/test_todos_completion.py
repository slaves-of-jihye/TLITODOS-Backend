from datetime import UTC, datetime

from tests.conftest import auth_headers, make_category, make_todo, make_user


async def test_uncomplete_todo_sets_completed_state_to_false(client, db):
    await make_user(db, 1, "owner")
    category = await make_category(db, 1)
    todo = await make_todo(db, 1, category.id)
    todo.is_completed = True
    todo.completed_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()

    response = await client.patch(f"/api/v1/todos/{todo.id}/uncomplete", headers=auth_headers(1))

    assert response.status_code == 200
    assert response.json() == {"success": True, "todoId": todo.id, "isCompleted": False}
    await db.refresh(todo)
    assert todo.is_completed is False
    assert todo.completed_at is None


async def test_uncomplete_todo_rejects_another_users_todo(client, db):
    await make_user(db, 1, "owner")
    await make_user(db, 2, "requester")
    category = await make_category(db, 1)
    todo = await make_todo(db, 1, category.id)
    todo.is_completed = True
    await db.commit()

    response = await client.patch(f"/api/v1/todos/{todo.id}/uncomplete", headers=auth_headers(2))

    assert response.status_code == 404
    await db.refresh(todo)
    assert todo.is_completed is True
