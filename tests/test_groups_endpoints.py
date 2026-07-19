from sqlalchemy import select

from app.infrastructure.database import GroupMember
from tests.conftest import add_member, auth_headers, make_group, make_user


async def test_get_group_includes_member_bio(client, db):
    await make_user(db, 1, "leader", bio="안녕하세요, 반갑습니다.")
    await make_group(db, 10, "shared")
    await add_member(db, 10, 1, role="LEADER")

    response = await client.get("/api/v1/groups/10", headers=auth_headers(1))

    assert response.status_code == 200
    members = response.json()["members"]
    assert members[0]["bio"] == "안녕하세요, 반갑습니다."


async def test_leave_group_removes_member(client, db):
    await make_user(db, 1, "leader")
    await make_user(db, 2, "member")
    await make_group(db, 10, "shared")
    await add_member(db, 10, 1, role="LEADER")
    await add_member(db, 10, 2, role="MEMBER")

    response = await client.post("/api/v1/groups/10/leave", headers=auth_headers(2))

    assert response.status_code == 200
    remaining = (await db.scalars(select(GroupMember).where(GroupMember.group_id == 10))).all()
    assert {member.user_id for member in remaining} == {1}


async def test_leave_group_rejects_leader(client, db):
    await make_user(db, 1, "leader")
    await make_group(db, 10, "shared")
    await add_member(db, 10, 1, role="LEADER")

    response = await client.post("/api/v1/groups/10/leave", headers=auth_headers(1))

    assert response.status_code == 400


async def test_leave_group_rejects_non_member(client, db):
    await make_user(db, 1, "leader")
    await make_user(db, 2, "outsider")
    await make_group(db, 10, "shared")
    await add_member(db, 10, 1, role="LEADER")

    response = await client.post("/api/v1/groups/10/leave", headers=auth_headers(2))

    assert response.status_code == 404


async def test_leave_group_missing_group_returns_404(client, db):
    await make_user(db, 1, "requester")

    response = await client.post("/api/v1/groups/999/leave", headers=auth_headers(1))

    assert response.status_code == 404


async def test_delete_group_by_leader_succeeds(client, db):
    await make_user(db, 1, "leader")
    await make_user(db, 2, "member")
    await make_group(db, 10, "shared")
    await add_member(db, 10, 1, role="LEADER")
    await add_member(db, 10, 2, role="MEMBER")

    response = await client.delete("/api/v1/groups/10", headers=auth_headers(1))

    assert response.status_code == 200
    remaining = (await db.scalars(select(GroupMember).where(GroupMember.group_id == 10))).all()
    assert remaining == []


async def test_delete_group_by_member_returns_403(client, db):
    await make_user(db, 1, "leader")
    await make_user(db, 2, "member")
    await make_group(db, 10, "shared")
    await add_member(db, 10, 1, role="LEADER")
    await add_member(db, 10, 2, role="MEMBER")

    response = await client.delete("/api/v1/groups/10", headers=auth_headers(2))

    assert response.status_code == 403


async def test_delete_group_missing_group_returns_404(client, db):
    await make_user(db, 1, "requester")

    response = await client.delete("/api/v1/groups/999", headers=auth_headers(1))

    assert response.status_code == 404
