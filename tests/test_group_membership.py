import pytest
from fastapi import HTTPException

from app.application.groups_service import require_shared_group_membership
from tests.conftest import add_member, make_group, make_user


async def test_require_shared_group_membership_passes_when_both_are_members(db):
    await make_user(db, 1)
    await make_user(db, 2)
    await make_group(db, 10)
    await add_member(db, 10, 1)
    await add_member(db, 10, 2)

    await require_shared_group_membership(db, 10, requester_id=1, target_user_id=2)


async def test_require_shared_group_membership_raises_when_requester_missing(db):
    await make_user(db, 1)
    await make_user(db, 2)
    await make_group(db, 10)
    await add_member(db, 10, 2)

    with pytest.raises(HTTPException) as exc_info:
        await require_shared_group_membership(db, 10, requester_id=1, target_user_id=2)

    assert exc_info.value.status_code == 403


async def test_require_shared_group_membership_raises_when_target_missing(db):
    await make_user(db, 1)
    await make_user(db, 2)
    await make_group(db, 10)
    await add_member(db, 10, 1)

    with pytest.raises(HTTPException) as exc_info:
        await require_shared_group_membership(db, 10, requester_id=1, target_user_id=2)

    assert exc_info.value.status_code == 403


async def test_require_shared_group_membership_raises_when_neither_are_members(db):
    await make_user(db, 1)
    await make_user(db, 2)
    await make_group(db, 10)

    with pytest.raises(HTTPException) as exc_info:
        await require_shared_group_membership(db, 10, requester_id=1, target_user_id=2)

    assert exc_info.value.status_code == 403
