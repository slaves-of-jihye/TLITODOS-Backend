"""Transactional startup migration; never connects to a second DB.

Legacy dates are validated in Python before any data is changed. A malformed date
aborts startup with its Todo ID instead of silently moving or deleting the task.
"""

from datetime import date, datetime

from sqlalchemy import text


async def migrate_design_schema(connection):
    await connection.execute(text("SELECT pg_advisory_xact_lock(74102918)"))
    for sql in (
        "ALTER TABLE todos ADD COLUMN IF NOT EXISTS description VARCHAR(100) NOT NULL DEFAULT ''",
        "ALTER TABLE todos ADD COLUMN IF NOT EXISTS start_date DATE",
        "ALTER TABLE todos ADD COLUMN IF NOT EXISTS time TIME",
        "ALTER TABLE todos ADD COLUMN IF NOT EXISTS timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Seoul'",
        "ALTER TABLE todos ADD COLUMN IF NOT EXISTS occurrence_date DATE",
        "ALTER TABLE todo_routines ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP",
        "ALTER TABLE diaries ADD COLUMN IF NOT EXISTS date DATE",
        "CREATE INDEX IF NOT EXISTS ix_todos_start_date ON todos(start_date)",
        "CREATE INDEX IF NOT EXISTS ix_diaries_date ON diaries(date)",
    ):
        await connection.execute(text(sql))
    rows = (
        (
            await connection.execute(
                text("SELECT id, due_date, created_at, routine_id FROM todos WHERE start_date IS NULL")
            )
        )
        .mappings()
        .all()
    )
    updates = []
    for row in rows:
        raw = row["due_date"]
        local_time = None
        try:
            if raw and len(raw) != 10:
                parsed = datetime.fromisoformat(raw)
                if parsed.tzinfo:
                    from zoneinfo import ZoneInfo

                    parsed = parsed.astimezone(ZoneInfo("Asia/Seoul"))
                day, local_time = parsed.date(), parsed.time().replace(tzinfo=None)
            else:
                day = date.fromisoformat(raw) if raw else row["created_at"].date()
        except ValueError as exc:
            raise ValueError(f"Todo {row['id']}: invalid legacy due_date; correct before deployment") from exc
        updates.append(
            {
                "id": row["id"],
                "start": day,
                "due": day.isoformat() if raw else None,
                "time": local_time,
                "occurrence": day if row["routine_id"] else None,
            }
        )
    if updates:
        await connection.execute(
            text(
                "UPDATE todos SET start_date=:start, due_date=:due, time=COALESCE(time,:time), "
                "occurrence_date=:occurrence WHERE id=:id"
            ),
            updates,
        )
    await connection.execute(text("UPDATE diaries SET date=created_at::date WHERE date IS NULL"))
    await connection.execute(
        text("CREATE UNIQUE INDEX IF NOT EXISTS uq_routine_occurrence ON todos(routine_id, occurrence_date)")
    )
    # Todos are always public. Group data stays intact; restoring the retired
    # privacy values requires a backup.
    await connection.execute(text("ALTER TABLE todos DROP COLUMN IF EXISTS visibility"))
