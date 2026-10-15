from datetime import date as Date
from datetime import datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_role
from app.config import get_settings
from app.db import get_session
from app.models import Lesson, LessonStatus, Parity, ScheduleSlot, Subject, User, UserRole
from app.services.schedule import lessons_for_date

router = APIRouter(tags=["lessons"])
Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]
Admin = Annotated[User, Depends(require_role(UserRole.HEADMAN, UserRole.DEPUTY))]


class LessonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: Date
    slot_number: int
    time_start: str | None
    time_end: str | None
    lesson_type: str | None
    subject_id: int
    subject_name: str
    subgroup: int
    status: LessonStatus


def lesson_out(lesson: Lesson, schedule_slot: ScheduleSlot | None = None) -> LessonOut:
    times = get_settings().schedule_slot_times.get(str(lesson.slot_number), [])
    return LessonOut(
        id=lesson.id, date=lesson.date, slot_number=lesson.slot_number,
        subject_id=lesson.subject_id, subject_name=lesson.subject.name,
        subgroup=lesson.subgroup, status=lesson.status,
        time_start=times[0] if len(times) > 0 else None,
        time_end=times[1] if len(times) > 1 else None,
        lesson_type=schedule_slot.lesson_type.value if schedule_slot is not None else None,
    )


async def _get_lessons(target_date: Date, session: AsyncSession, user: User) -> list[LessonOut]:
    lessons = await lessons_for_date(session, target_date)
    start = get_settings().semester_start_date
    parity = Parity.EVEN if ((target_date - start).days // 7) % 2 == 0 else Parity.ODD
    slots = (await session.scalars(select(ScheduleSlot).where(
        ScheduleSlot.day_of_week == target_date.isoweekday(),
        ScheduleSlot.parity.in_((Parity.ALL, parity)),
    ))).all()
    slot_by_key = {(slot.slot_number, slot.subject_id, slot.subgroup): slot for slot in slots}
    return [
        lesson_out(lesson, slot_by_key.get((lesson.slot_number, lesson.subject_id, lesson.subgroup)))
        for lesson in lessons
        if user.role != UserRole.STUDENT or lesson.subgroup in (0, user.subgroup)
    ]


@router.get("/lessons/today", response_model=list[LessonOut])
async def today(session: Session, user: CurrentUser) -> list[LessonOut]:
    return await _get_lessons(datetime.now(ZoneInfo(get_settings().timezone)).date(), session, user)


@router.get("/lessons", response_model=list[LessonOut])
async def by_date(date: Date, session: Session, user: CurrentUser) -> list[LessonOut]:
    return await _get_lessons(date, session, user)


class LessonEdit(BaseModel):
    lesson_id: int | None = None
    date: Date | None = None
    slot_number: int | None = Field(default=None, ge=1, le=6)
    subject_id: int | None = None
    subgroup: int = Field(default=0, ge=0, le=2)
    status: Literal[LessonStatus.SCHEDULED, LessonStatus.CANCELLED] = LessonStatus.SCHEDULED


@router.post("/admin/lessons", response_model=LessonOut)
async def edit_lesson(body: LessonEdit, session: Session, admin: Admin) -> LessonOut:
    if body.lesson_id is not None:
        if body.status != LessonStatus.CANCELLED:
            raise HTTPException(422, "An existing lesson can only be cancelled")
        lesson = await session.scalar(
            select(Lesson).options(selectinload(Lesson.subject)).where(Lesson.id == body.lesson_id)
        )
        if lesson is None:
            raise HTTPException(404, "Lesson not found")
        lesson.status = LessonStatus.CANCELLED
    else:
        if body.date is None or body.slot_number is None or body.subject_id is None:
            raise HTTPException(422, "date, slot_number and subject_id are required")
        if await session.get(Subject, body.subject_id) is None:
            raise HTTPException(404, "Subject not found")
        lesson = Lesson(
            date=body.date, slot_number=body.slot_number, subject_id=body.subject_id,
            subgroup=body.subgroup, status=body.status,
        )
        session.add(lesson)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(409, "Lesson already exists") from exc
    lesson = await session.scalar(
        select(Lesson).options(selectinload(Lesson.subject)).where(Lesson.id == lesson.id)
    )
    start = get_settings().semester_start_date
    parity = Parity.EVEN if ((lesson.date - start).days // 7) % 2 == 0 else Parity.ODD
    schedule_slot = await session.scalar(select(ScheduleSlot).where(
        ScheduleSlot.day_of_week == lesson.date.isoweekday(), ScheduleSlot.parity.in_((Parity.ALL, parity)),
        ScheduleSlot.slot_number == lesson.slot_number, ScheduleSlot.subject_id == lesson.subject_id,
        ScheduleSlot.subgroup == lesson.subgroup,
    ))
    return lesson_out(lesson, schedule_slot)
