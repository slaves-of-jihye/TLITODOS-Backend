from fastapi import HTTPException
from sqlalchemy import func, or_, select, update

from app.infrastructure.database import (
    Bet,
    Diary,
    GroupMember,
    Notification,
    Todo,
    User,
    bet_to_response,
)
from app.shared.scheduling import todo_dates, utcnow

NOTIFICATION_TYPES = ("TODO_COMPLETED", "DIARY_CREATED", "BET_REQUESTED")


def peer_ids(user_id):
    groups = select(GroupMember.group_id).where(GroupMember.user_id == user_id)
    return (
        select(GroupMember.user_id).where(GroupMember.group_id.in_(groups), GroupMember.user_id != user_id).distinct()
    )


async def notify_peers(session, actor_id, notification_type, event_key, **references):
    for recipient in await session.scalars(peer_ids(actor_id)):
        session.add(
            Notification(
                recipient_id=recipient, actor_id=actor_id, type=notification_type, event_key=event_key, **references
            )
        )


def visible_notification_conditions(user_id):
    # Both list and unread status must apply the same visibility rules.
    # Queries using these conditions must outer-join Diary.
    return (
        Notification.recipient_id == user_id,
        or_(Notification.type == "BET_REQUESTED", Notification.actor_id.in_(peer_ids(user_id))),
        or_(Notification.diary_id.is_(None), Diary.visibility == "PUBLIC"),
    )


async def unread_status(session, user_id):
    kinds = await session.scalars(
        select(Notification.type)
        .outerjoin(Diary, Notification.diary_id == Diary.id)
        .where(
            *visible_notification_conditions(user_id),
            Notification.read_at.is_(None),
            Notification.type.in_(NOTIFICATION_TYPES),
        )
        .distinct()
    )
    unread_types = set(kinds)
    return {kind: kind in unread_types for kind in NOTIFICATION_TYPES}


async def list_notifications(session, user_id, kind=None, cursor=None, limit=30):
    # Navigation hint, not a notification's originating group: events are
    # deduplicated across shared groups. Aggregate before joining to avoid
    # duplicate notifications and keep pagination stable.
    own_groups = select(GroupMember.group_id).where(GroupMember.user_id == user_id)
    shared_groups = (
        select(GroupMember.user_id, func.min(GroupMember.group_id).label("group_id"))
        .where(GroupMember.group_id.in_(own_groups), GroupMember.user_id != user_id)
        .group_by(GroupMember.user_id)
        .subquery()
    )
    statement = (
        select(Notification, User, Todo, Diary, Bet, shared_groups.c.group_id)
        .join(User, Notification.actor_id == User.id)
        .outerjoin(Todo, Notification.todo_id == Todo.id)
        .outerjoin(Diary, Notification.diary_id == Diary.id)
        .outerjoin(Bet, Notification.bet_id == Bet.id)
        .outerjoin(shared_groups, shared_groups.c.user_id == Notification.actor_id)
        .where(*visible_notification_conditions(user_id))
    )
    if kind:
        statement = statement.where(Notification.type == kind)
    if cursor is not None:
        statement = statement.where(Notification.id < cursor)
    rows = (await session.execute(statement.order_by(Notification.id.desc()).limit(limit + 1))).all()
    items = []
    for notification, actor, todo, diary, bet, group_id in rows[:limit]:
        items.append(
            {
                "notificationId": notification.id,
                "groupId": group_id,
                "type": notification.type,
                "actor": {"userId": actor.id, "name": actor.name, "profileImageUrl": actor.profile_image_url},
                "todo": {
                    "todoId": todo.id,
                    "userId": todo.user_id,
                    "title": todo.title,
                    "description": todo.description,
                    "startDate": todo_dates(todo)[0].isoformat(),
                    "dueDate": todo.due_date,
                }
                if todo
                else None,
                "diaryId": diary.id if diary else None,
                "bet": bet_to_response(bet) if bet else None,
                "createdAt": notification.created_at.isoformat(),
                "readAt": notification.read_at.isoformat() if notification.read_at else None,
            }
        )
    return {"items": items, "nextCursor": items[-1]["notificationId"] if len(rows) > limit else None}


async def read_all_todo_completed(session, user_id):
    # Recipient-scoped bulk update, including older events no longer in the feed.
    # Repeated/concurrent calls preserve existing read timestamps.
    result = await session.execute(
        update(Notification)
        .where(
            Notification.recipient_id == user_id,
            Notification.type == "TODO_COMPLETED",
            Notification.read_at.is_(None),
        )
        .values(read_at=utcnow())
        .execution_options(synchronize_session=False)
    )
    await session.commit()
    return {"success": True, "updatedCount": result.rowcount}


async def read_notification(session, notification_id, user_id):
    notification = await session.scalar(
        select(Notification)
        .where(Notification.id == notification_id, Notification.recipient_id == user_id)
        .with_for_update()
    )
    if notification is None:
        raise HTTPException(404, detail={"message": "존재하지 않는 알림입니다."})
    notification.read_at = notification.read_at or utcnow()
    await session.commit()
    return {"success": True, "notificationId": notification.id, "readAt": notification.read_at.isoformat()}
