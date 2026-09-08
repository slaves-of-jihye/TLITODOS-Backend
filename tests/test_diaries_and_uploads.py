import base64

import pytest
from sqlalchemy import func, select

from app.infrastructure.database import Diary, Notification
from app.presentation.v1.uploads import uploads_controller
from app.shared import uploads
from tests.conftest import add_member, auth_headers, make_group, make_user

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j1ioAAAAASUVORK5CYII=")


@pytest.fixture(autouse=True)
def temporary_uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(uploads, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(uploads_controller, "UPLOAD_DIR", tmp_path)


async def setup(db):
    for user_id in (1, 2, 3):
        await make_user(db, user_id)
    await make_group(db, 10)
    await add_member(db, 10, 1, "LEADER")
    await add_member(db, 10, 2)


async def create_diary(client, visibility="PRIVATE", image=False):
    body = {"date": "2026-09-08", "content": "오늘 일기", "emotion": "행복", "visibility": visibility}
    if image:
        response = await client.post(
            "/api/v1/diaries", data=body, files={"image": ("test.png", PNG, "image/png")}, headers=auth_headers(1)
        )
    else:
        response = await client.post("/api/v1/diaries", json=body, headers=auth_headers(1))
    assert response.status_code == 201, response.text
    return response.json()


async def test_diary_date_visibility_and_notifications(client, db):
    await setup(db)
    public = await create_diary(client, "PUBLIC")
    private = await create_diary(client, "PRIVATE")
    partial = await create_diary(client, "GROUP")
    assert public["date"] == "2026-09-08"
    listing = await client.get("/api/v1/diaries", params={"date": "2026-09-08", "userId": 1}, headers=auth_headers(2))
    assert [item["diaryId"] for item in listing.json()] == [public["diaryId"]]
    assert (
        await client.get("/api/v1/diaries", params={"date": "2026-09-09", "userId": 1}, headers=auth_headers(2))
    ).json() == []
    for diary in (public, private, partial):
        url = f"/api/v1/diaries/{diary['diaryId']}"
        assert (await client.get(url, headers=auth_headers(1))).status_code == 200
        assert (await client.get(url, headers=auth_headers(3))).status_code == 404
    for diary in (private, partial):
        assert (await client.get(f"/api/v1/diaries/{diary['diaryId']}", headers=auth_headers(2))).status_code == 404
    assert await db.scalar(select(func.count(Notification.id))) == 1
    items = (await client.get("/api/v1/notifications", headers=auth_headers(2))).json()["items"]
    assert items[0]["type"] == "DIARY_CREATED" and items[0]["diaryId"] == public["diaryId"]


async def test_visibility_change_revokes_feed_and_leaving_group_revokes_access(client, db):
    await setup(db)
    diary = await create_diary(client, "PUBLIC")
    url = f"/api/v1/diaries/{diary['diaryId']}"
    for visibility in ("PRIVATE", "PUBLIC", "PRIVATE", "PUBLIC"):
        assert (await client.patch(url, json={"visibility": visibility}, headers=auth_headers(1))).status_code == 200
        count = len((await client.get("/api/v1/notifications", headers=auth_headers(2))).json()["items"])
        assert count == (1 if visibility == "PUBLIC" else 0)
    await client.post("/api/v1/groups/10/leave", headers=auth_headers(2))
    assert (await client.get(url, headers=auth_headers(2))).status_code == 404
    assert (await client.get("/api/v1/notifications", headers=auth_headers(2))).json()["items"] == []


async def test_diary_image_permissions_are_checked_on_direct_url(client, db):
    await setup(db)
    diary = await create_diary(client, "PRIVATE", image=True)
    image_url = diary["imageUrl"]
    owner = await client.get(image_url, headers=auth_headers(1))
    assert owner.status_code == 200 and owner.content == PNG
    assert owner.headers["cache-control"] == "private, no-store"
    assert (await client.get(image_url, headers=auth_headers(2))).status_code == 404
    assert (await client.get(image_url, headers=auth_headers(3))).status_code == 404
    assert (await client.get(image_url)).status_code in (401, 422)  # Test auth dependency needs a header.
    await client.patch(f"/api/v1/diaries/{diary['diaryId']}", json={"visibility": "PUBLIC"}, headers=auth_headers(1))
    assert (await client.get(image_url, headers=auth_headers(2))).status_code == 200
    assert (await client.get(image_url, headers=auth_headers(3))).status_code == 404
    await client.delete(f"/api/v1/diaries/{diary['diaryId']}", headers=auth_headers(1))
    assert (await client.get(image_url, headers=auth_headers(1))).status_code == 404


async def test_cannot_publish_someone_elses_private_image_by_linking_it(client, db):
    await setup(db)
    diary = await create_diary(client, image=True)
    for image_url in (
        diary["imageUrl"],
        "https://example.com/private-image.png",
        "/uploads/diaries/../profiles/file.png",
    ):
        response = await client.post(
            "/api/v1/diaries",
            json={"content": "도용", "imageUrl": image_url, "visibility": "PUBLIC"},
            headers=auth_headers(2),
        )
        assert response.status_code == 422


async def test_diary_multipart_update_replaces_image_and_edits_date(client, db):
    await setup(db)
    diary = await create_diary(client, image=True)
    response = await client.patch(
        f"/api/v1/diaries/{diary['diaryId']}",
        data={"date": "2026-09-09"},
        files={"image": ("new.png", PNG)},
        headers=auth_headers(1),
    )
    assert response.status_code == 200, response.text
    assert response.json()["imageUrl"] != diary["imageUrl"]
    assert response.json()["date"] == "2026-09-09"
    assert (await client.get(diary["imageUrl"], headers=auth_headers(1))).status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"date": "2026-02-30", "content": "일기"},
        {"content": ""},
        {"content": "일기", "visibility": "ANYONE"},
        {"content": "일기", "allowedUserIds": [2]},
    ],
)
async def test_diary_invalid_payload_returns_422_not_500(client, db, body):
    await setup(db)
    assert (await client.post("/api/v1/diaries", json=body, headers=auth_headers(1))).status_code == 422
    assert await db.scalar(select(func.count(Diary.id))) == 0


async def test_profile_upload_is_public_but_rejects_svg_and_large_files(client, db):
    await setup(db)
    response = await client.patch("/api/v1/users/me", files={"image": ("avatar.png", PNG)}, headers=auth_headers(1))
    assert response.status_code == 200
    assert (await client.get(response.json()["profileImageUrl"])).content == PNG
    assert (
        await client.patch("/api/v1/users/me", files={"image": ("bad.svg", b"<svg></svg>")}, headers=auth_headers(1))
    ).status_code == 422
    oversized = PNG + b"0" * (10 * 1024 * 1024)
    assert (
        await client.patch("/api/v1/users/me", files={"image": ("large.png", oversized)}, headers=auth_headers(1))
    ).status_code == 413


async def test_bet_proof_participant_permissions(client, db):
    from tests.conftest import make_category, make_todo

    await setup(db)
    category = await make_category(db, 1)
    todo = await make_todo(db, 1, category.id)
    bet = (await client.post(f"/api/v1/todos/{todo.id}/bets", json={"content": "내기"}, headers=auth_headers(2))).json()
    base = f"/api/v1/bets/{bet['betId']}"
    assert (
        await client.post(base + "/proof", files={"image": ("proof.png", PNG)}, headers=auth_headers(1))
    ).status_code == 409
    await client.patch(base + "/status", json={"status": "ACCEPTED"}, headers=auth_headers(1))
    assert (
        await client.post(base + "/proof", files={"image": ("proof.png", PNG)}, headers=auth_headers(2))
    ).status_code == 404
    proof = await client.post(base + "/proof", files={"image": ("proof.png", PNG)}, headers=auth_headers(1))
    assert proof.status_code == 200
    for user_id, status in ((1, 200), (2, 200), (3, 404)):
        assert (await client.get(proof.json()["proofImageUrl"], headers=auth_headers(user_id))).status_code == status
    assert (await client.patch(base + "/verify", json={"approved": True}, headers=auth_headers(1))).status_code == 404
    assert (await client.patch(base + "/verify", json={"approved": True}, headers=auth_headers(2))).json()[
        "status"
    ] == "VERIFIED"


async def test_private_image_and_api_reject_missing_real_bearer_token(client, db):
    from app.main import app
    from app.shared.auth import require_access_token

    await setup(db)
    diary = await create_diary(client, image=True)
    app.dependency_overrides.pop(require_access_token)
    for path in (diary["imageUrl"], "/api/v1/todos", "/api/v1/notifications", "/api/v1/diaries"):
        assert (await client.get(path)).status_code == 401


@pytest.mark.parametrize("method,path", [("post", "/api/v1/diaries"), ("patch", "/api/v1/users/me")])
async def test_invalid_json_is_a_client_error(client, db, method, path):
    await setup(db)
    response = await client.request(
        method, path, content="{invalid", headers={**auth_headers(1), "Content-Type": "application/json"}
    )
    assert response.status_code == 422
