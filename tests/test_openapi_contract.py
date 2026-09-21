import json
from pathlib import Path

from app.main import app


def test_generated_openapi_matches_application():
    checked_in = json.loads((Path(__file__).resolve().parents[1] / "docs/openapi.json").read_text())
    assert checked_in == app.openapi()


def test_frontend_contract_contains_new_request_and_response_fields():
    spec = app.openapi()
    schemas = spec["components"]["schemas"]
    assert {"startDate", "description", "time", "timezone"} <= schemas["TodoResponse"]["properties"].keys()
    assert "visibility" not in schemas["TodoCreateRequest"]["properties"]
    assert "visibility" not in schemas["TodoPatchRequest"]["properties"]
    assert "visibility" not in schemas["TodoResponse"]["properties"]
    for path in ("/api/v1/todos", "/api/v1/todos/daily-status", "/api/v1/categories"):
        assert "groupId" in {parameter["name"] for parameter in spec["paths"][path]["get"]["parameters"]}
    assert "/api/v1/groups" in spec["paths"]
    assert "requesterId" not in schemas["BetCreateRequest"]["properties"]
    assert schemas["Recurrence"]["properties"]["frequency"]["enum"] == ["DAILY", "WEEKLY", "MONTHLY", "YEARLY"]
    assert "/api/v1/notifications" in spec["paths"]
    unread = spec["paths"]["/api/v1/notifications/unread-status"]["get"]
    assert unread["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/NotificationUnreadStatusResponse"
    )
    unread_schema = schemas["NotificationUnreadStatusResponse"]
    assert set(unread_schema["required"]) == {"TODO_COMPLETED", "DIARY_CREATED", "BET_REQUESTED"}
    assert all(field["type"] == "boolean" for field in unread_schema["properties"].values())
    for path, method in (("/api/v1/diaries", "post"), ("/api/v1/diaries/{diaryId}", "patch")):
        assert (
            "image"
            in spec["paths"][path][method]["requestBody"]["content"]["multipart/form-data"]["schema"]["properties"]
        )


def test_settings_and_bulk_notification_read_contract():
    spec = app.openapi()
    schemas = spec["components"]["schemas"]
    request = schemas["TimeFormatSettingRequest"]
    assert request["required"] == ["timeFormat"]
    assert request["properties"]["timeFormat"]["enum"] == ["12H", "24H"]
    assert request["additionalProperties"] is False
    for path, response_name in (
        ("/api/v1/users/me/time-format", "TimeFormatSettingResponse"),
        ("/api/v1/notifications/todo-completed/read-all", "NotificationsReadAllResponse"),
    ):
        operation = spec["paths"][path]["patch"]
        assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
            "/" + response_name
        )
    assert schemas["TimeFormatSettingResponse"]["properties"]["timeFormat"]["enum"] == ["12H", "24H"]
    assert schemas["NotificationsReadAllResponse"]["properties"]["updatedCount"]["type"] == "integer"


def test_profile_settings_and_notification_navigation_are_in_openapi():
    spec = app.openapi()
    schemas = spec["components"]["schemas"]
    for method in ("get", "patch"):
        response = spec["paths"]["/api/v1/users/me"][method]["responses"]["200"]
        assert response["content"]["application/json"]["schema"]["$ref"].endswith("/UserResponse")
    assert {"font", "timeFormat"} <= set(schemas["UserResponse"]["required"])
    assert schemas["UserResponse"]["properties"]["timeFormat"]["enum"] == ["12H", "24H"]
    assert "groupId" in schemas["NotificationResponse"]["required"]
    assert {"userId", "startDate", "dueDate"} <= set(schemas["TodoPreviewResponse"]["required"])
