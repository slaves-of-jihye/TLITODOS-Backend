from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from app.application.notifications_service import NOTIFICATION_TYPES
from app.infrastructure.database import Diary, GroupMember, Notification
from app.shared.scheduling import utcnow
from tests.conftest import add_member, auth_headers, make_group, make_user

URL = "/api/v1/notifications/unread-status"
EMPTY = {kind: False for kind in NOTIFICATION_TYPES}


async def setup(db):
    for user_id in (1, 2, 3):
        await make_user(db, user_id)
    await make_group(db, 10)
    await add_member(db, 10, 1, "LEADER")
    await add_member(db, 10, 2)


async def notification(db, kind, recipient=2, actor=1, read=False, diary_id=None):
    row = Notification(
        recipient_id=recipient,
        actor_id=actor,
        type=kind,
        event_key=str(uuid4()),
        read_at=utcnow() if read else None,
        diary_id=diary_id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def test_empty_status_returns_all_types_as_booleans(client, db):
    await setup(db)
    response = await client.get(URL, headers=auth_headers(2))
    assert response.status_code == 200
    assert response.json() == EMPTY
    assert all(type(value) is bool for value in response.json().values())


@pytest.mark.parametrize("kind", NOTIFICATION_TYPES)
async def test_each_type_remains_true_until_last_unread_is_read(client, db, kind):
    await setup(db)
    first = await notification(db, kind)
    second = await notification(db, kind)
    await notification(db, kind, read=True)
    expected = {**EMPTY, kind: True}
    for _ in range(2):
        assert (await client.get(URL, headers=auth_headers(2))).json() == expected
    await db.refresh(first)
    assert first.read_at is None  # The status GET must not mark anything read.
    await client.patch(f"/api/v1/notifications/{first.id}/read", headers=auth_headers(2))
    assert (await client.get(URL, headers=auth_headers(2))).json() == expected
    await client.patch(f"/api/v1/notifications/{second.id}/read", headers=auth_headers(2))
    assert (await client.get(URL, headers=auth_headers(2))).json() == EMPTY


async def test_status_is_recipient_scoped_and_not_limited_to_first_page(client, db):
    await setup(db)
    await notification(db, "BET_REQUESTED", recipient=3)
    for kind in NOTIFICATION_TYPES:
        await notification(db, kind)
    # All unread notifications lie beyond the first 30 newest rows.
    for _ in range(31):
        await notification(db, "TODO_COMPLETED", read=True)
    page = (await client.get("/api/v1/notifications", headers=auth_headers(2))).json()
    assert len(page["items"]) == 30
    assert all(item["readAt"] is not None for item in page["items"])
    assert (await client.get(URL, headers=auth_headers(2))).json() == dict.fromkeys(NOTIFICATION_TYPES, True)
    assert (await client.get(URL, headers=auth_headers(1))).json() == EMPTY
    assert (await client.get(URL, headers=auth_headers(3))).json() == {**EMPTY, "BET_REQUESTED": True}


async def test_hidden_diaries_and_former_peers_match_list_visibility(client, db):
    await setup(db)
    diary = Diary(user_id=1, content="일기", visibility="PUBLIC")
    db.add(diary)
    await db.commit()
    await db.refresh(diary)
    await notification(db, "DIARY_CREATED", diary_id=diary.id)
    await notification(db, "TODO_COMPLETED")
    await notification(db, "BET_REQUESTED", actor=3)  # No shared group required for received bets.

    async def assert_matches_list(expected):
        response = await client.get(URL, headers=auth_headers(2))
        assert response.status_code == 200 and response.json() == expected
        items = (await client.get("/api/v1/notifications", headers=auth_headers(2))).json()["items"]
        kinds = {item["type"] for item in items if item["readAt"] is None}
        assert response.json() == {kind: kind in kinds for kind in NOTIFICATION_TYPES}

    await assert_matches_list(dict.fromkeys(NOTIFICATION_TYPES, True))
    for visibility in ("PRIVATE", "GROUP"):
        diary.visibility = visibility
        await db.commit()  # Leave the existing notification to exercise read-side protection.
        await assert_matches_list({**EMPTY, "TODO_COMPLETED": True, "BET_REQUESTED": True})
    diary.visibility = "PUBLIC"
    await db.commit()
    await db.execute(delete(GroupMember).where(GroupMember.group_id == 10, GroupMember.user_id == 2))
    await db.commit()
    await assert_matches_list({**EMPTY, "BET_REQUESTED": True})
    assert len(list(await db.scalars(select(Notification)))) == 3


async def test_status_requires_real_bearer_authentication(client):
    from app.main import app
    from app.shared.auth import require_access_token

    app.dependency_overrides.pop(require_access_token)
    assert (await client.get(URL)).status_code == 401
    assert (await client.get(URL, headers={"Authorization": "Bearer invalid"})).status_code == 401
