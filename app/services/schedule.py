from datetime import date

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models import Lesson, Parity, ScheduleSlot


async def lessons_for_date(session: AsyncSession, target_date: date) -> list[Lesson]:
    query = (
        select(Lesson)
        .options(selectinload(Lesson.subject))
        .where(Lesson.date == target_date)
        .order_by(Lesson.slot_number, Lesson.subgroup, Lesson.id)
    )
    if session.bind and session.bind.dialect.name == "postgresql":
        # Serialize generation for this date, including the case with no template slots.
        await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": target_date.toordinal()})
    existing = (await session.scalars(query)).all()
    if existing:
        return list(existing)

    start = get_settings().semester_start_date
    week = (target_date - start).days // 7
    parity = Parity.EVEN if week % 2 == 0 else Parity.ODD
    slots = (await session.scalars(
        select(ScheduleSlot).where(
            ScheduleSlot.day_of_week == target_date.isoweekday(),
            ScheduleSlot.parity.in_((Parity.ALL, parity)),
        )
    )).all()
    # Identical template slots must not violate the lesson uniqueness constraint.
    unique = {(slot.slot_number, slot.subject_id, slot.subgroup) for slot in slots}
    if unique:
        session.add_all(
            Lesson(date=target_date, slot_number=number, subject_id=subject_id, subgroup=subgroup)
            for number, subject_id, subgroup in unique
        )
        await session.commit()
    return list((await session.scalars(query)).all())
