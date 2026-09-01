from tests.conftest import auth_headers, make_category, make_todo, make_user


async def test_list_todos_places_dependency_before_dependent(client, db):
    await make_user(db, 1, "owner")
    category = await make_category(db, 1)
    dependent = await make_todo(db, 1, category.id, title="dependent")
    dependency = await make_todo(db, 1, category.id, title="dependency")
    dependent.dependencies = [dependency.id]
    await db.commit()

    response = await client.get("/api/v1/todos", headers=auth_headers(1))

    assert response.status_code == 200
    assert [todo["title"] for todo in response.json()] == ["dependency", "dependent"]


async def test_list_todos_topologically_sorts_transitive_dependencies(client, db):
    await make_user(db, 1, "owner")
    category = await make_category(db, 1)
    last = await make_todo(db, 1, category.id, title="last")
    middle = await make_todo(db, 1, category.id, title="middle")
    first = await make_todo(db, 1, category.id, title="first")
    last.dependencies = [middle.id]
    middle.dependencies = [first.id]
    await db.commit()

    response = await client.get("/api/v1/todos", headers=auth_headers(1))

    assert response.status_code == 200
    assert [todo["title"] for todo in response.json()] == ["first", "middle", "last"]


async def test_list_todos_returns_every_todo_when_dependencies_contain_cycle(client, db):
    await make_user(db, 1, "owner")
    category = await make_category(db, 1)
    first = await make_todo(db, 1, category.id, title="first")
    second = await make_todo(db, 1, category.id, title="second")
    first.dependencies = [second.id]
    second.dependencies = [first.id]
    await db.commit()

    response = await client.get("/api/v1/todos", headers=auth_headers(1))

    assert response.status_code == 200
    assert [todo["title"] for todo in response.json()] == ["first", "second"]
