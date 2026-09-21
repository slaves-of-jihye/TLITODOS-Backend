import pytest

from tests.conftest import auth_headers
from tests.test_notification_unread_status import notification, setup

URL = "/api/v1/notifications/todo-completed/read-all"


async def test_bulk_read_is_recipient_and_type_scoped_across_all_pages(client, db):
    await setup(db)
    unread = [await notification(db, "TODO_COMPLETED") for _ in range(105)]
    # Also includes own old events hidden by the current shared-group filter.
    hidden = await notification(db, "TODO_COMPLETED", actor=3)
    already_read = await notification(db, "TODO_COMPLETED", read=True)
    original_read_at = already_read.read_at
    untouched = [
        await notification(db, "TODO_COMPLETED", recipient=3),
        await notification(db, "DIARY_CREATED"),
        await notification(db, "BET_REQUESTED"),
    ]
    response = await client.patch(URL, headers=auth_headers(2))
    assert response.status_code == 200
    assert response.json() == {"success": True, "updatedCount": 106}
    for row in [*unread, hidden]:
        await db.refresh(row)
        assert row.read_at is not None
    first_read_at = unread[0].read_at
    await db.refresh(already_read)
    assert already_read.read_at == original_read_at
    for row in untouched:
        await db.refresh(row)
        assert row.read_at is None
    assert (await client.get("/api/v1/notifications/unread-status", headers=auth_headers(2))).json() == {
        "TODO_COMPLETED": False,
        "DIARY_CREATED": True,
        "BET_REQUESTED": True,
    }
    assert (await client.patch(URL, headers=auth_headers(2))).json() == {"success": True, "updatedCount": 0}
    await db.refresh(unread[0])
    assert unread[0].read_at == first_read_at
    new = await notification(db, "TODO_COMPLETED")
    assert new.read_at is None
    assert (await client.patch(URL, headers=auth_headers(2))).json() == {"success": True, "updatedCount": 1}
    await db.refresh(new)
    assert new.read_at is not None
    # The existing per-notification endpoint still reads other types.
    assert (
        await client.patch(f"/api/v1/notifications/{untouched[1].id}/read", headers=auth_headers(2))
    ).status_code == 200


async def test_empty_read_all_succeeds(client, db):
    await setup(db)
    response = await client.patch(URL, headers=auth_headers(2))
    assert response.status_code == 200
    assert response.json() == {"success": True, "updatedCount": 0}


@pytest.mark.parametrize("authorization", [None, "Bearer invalid"])
async def test_requires_bearer_authentication(client, authorization):
    from app.main import app
    from app.shared.auth import require_access_token

    app.dependency_overrides.pop(require_access_token)
    headers = {"Authorization": authorization} if authorization else {}
    assert (await client.patch(URL, headers=headers)).status_code == 401
