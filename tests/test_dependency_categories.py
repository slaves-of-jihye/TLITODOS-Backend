import pytest
from sqlalchemy import select

from app.infrastructure.database import Category, ensure_user_defaults
from tests.conftest import auth_headers, make_todo, make_user


async def seeded_categories(db):
    for user_id in (1, 2):
        await make_user(db, user_id)
        await ensure_user_defaults(db, user_id)
        await db.commit()
    return {(category.user_id, category.name): category for category in await db.scalars(select(Category))}


@pytest.mark.parametrize("method", ["POST", "PUT"])
@pytest.mark.parametrize("user_id", [1, 2])
async def test_seeded_hobby_is_allowed_as_both_dependency_and_dependent(client, db, method, user_id):
    categories = await seeded_categories(db)
    assert categories[1, "취미"].id == 1
    assert categories[2, "취미"].id != 1
    hobby = categories[user_id, "취미"]
    ordinary = categories[user_id, "할일"]
    for source, target in ((ordinary, hobby), (hobby, ordinary)):
        dependent = await make_todo(db, user_id, source.id)
        predecessor = await make_todo(db, user_id, target.id)
        payload = {"dependencyTodoId": predecessor.id} if method == "POST" else {"dependencyTodoIds": [predecessor.id]}
        response = await client.request(
            method, f"/api/v1/todos/{dependent.id}/dependencies", json=payload, headers=auth_headers(user_id)
        )
        assert response.status_code == (201 if method == "POST" else 200), response.text
        if method == "POST":
            assert response.json()["dependencyTodoId"] == predecessor.id
        else:
            assert response.json()["dependencies"] == [predecessor.id]
        await db.refresh(dependent)
        assert dependent.dependencies == [predecessor.id]


@pytest.mark.parametrize("method", ["POST", "PUT"])
async def test_hobby_still_enforces_ownership_and_prevents_cycles(client, db, method):
    categories = await seeded_categories(db)
    a, b = [await make_todo(db, 1, categories[1, "취미"].id) for _ in range(2)]
    other = await make_todo(db, 2, categories[2, "취미"].id)

    async def link(todo_id, dependency_id):
        payload = {"dependencyTodoId": dependency_id} if method == "POST" else {"dependencyTodoIds": [dependency_id]}
        return await client.request(
            method, f"/api/v1/todos/{todo_id}/dependencies", json=payload, headers=auth_headers(1)
        )

    assert (await link(a.id, other.id)).status_code == 404
    assert (await link(other.id, a.id)).status_code == 404
    assert (await link(a.id, a.id)).status_code == 422
    assert (await link(a.id, b.id)).status_code == (201 if method == "POST" else 200)
    assert (await link(b.id, a.id)).status_code == 422
