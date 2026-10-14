from datetime import datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_role
from app.config import get_settings
from app.db import get_session
from app.models import AttendanceRecord, AttendanceStatus, Lesson, LessonStatus, User, UserRole

router = APIRouter(tags=["attendance"])
Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]
Admin = Annotated[User, Depends(require_role(UserRole.HEADMAN, UserRole.DEPUTY))]


class CheckIn(BaseModel):
    lesson_id: int
    status: AttendanceStatus


class AttendanceOut(BaseModel):
    lesson_id: int
    user_id: int
    status: AttendanceStatus
    check_in_time: datetime | None
    is_confirmed: bool


class StudentAttendance(BaseModel):
    user_id: int
    full_name: str
    subgroup: int
    status: AttendanceStatus | Literal["unmarked"]
    check_in_time: datetime | None
    is_confirmed: bool


async def _lesson(session: AsyncSession, lesson_id: int) -> Lesson:
    lesson = await session.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, "Lesson not found")
    return lesson


def _eligible(lesson: Lesson, user: User) -> None:
    if lesson.status == LessonStatus.CANCELLED:
        raise HTTPException(400, "Cancelled lesson")
    if lesson.subgroup not in (0, user.subgroup):
        raise HTTPException(403, "Lesson belongs to another subgroup")


def _out(record: AttendanceRecord) -> AttendanceOut:
    return AttendanceOut(
        lesson_id=record.lesson_id, user_id=record.user_id, status=record.status,
        check_in_time=record.check_in_time, is_confirmed=record.is_confirmed,
    )


@router.post("/attendance/check-in", response_model=AttendanceOut)
async def check_in(body: CheckIn, session: Session, user: CurrentUser) -> AttendanceOut:
    lesson = await _lesson(session, body.lesson_id)
    _eligible(lesson, user)
    now = datetime.now(ZoneInfo(get_settings().timezone))
    if lesson.date != now.date():
        raise HTTPException(400, "Check-in is allowed only on the lesson date")
    values = {
        "lesson_id": lesson.id, "user_id": user.id, "status": body.status,
        "check_in_time": now, "is_confirmed": False,
    }
    dialect = session.bind.dialect.name if session.bind else ""
    if dialect in ("postgresql", "sqlite"):
        insert = pg_insert(AttendanceRecord) if dialect == "postgresql" else sqlite_insert(AttendanceRecord)
        stmt = insert.values(**values).on_conflict_do_update(
            index_elements=[AttendanceRecord.lesson_id, AttendanceRecord.user_id],
            set_={"status": body.status, "check_in_time": now, "is_confirmed": False},
        )
        await session.execute(stmt)
    else:
        record = await session.scalar(select(AttendanceRecord).where(
            AttendanceRecord.lesson_id == lesson.id, AttendanceRecord.user_id == user.id,
        ))
        if record is None:
            session.add(AttendanceRecord(**values))
        else:
            record.status = body.status
            record.check_in_time = now
            record.is_confirmed = False
    await session.commit()
    record = await session.scalar(select(AttendanceRecord).where(
        AttendanceRecord.lesson_id == lesson.id, AttendanceRecord.user_id == user.id,
    ))
    return _out(record)


@router.get("/admin/attendance/lesson/{lesson_id}", response_model=list[StudentAttendance])
async def lesson_attendance(lesson_id: int, session: Session, admin: Admin) -> list[StudentAttendance]:
    await _lesson(session, lesson_id)
    rows = (await session.execute(
        select(User, AttendanceRecord).outerjoin(
            AttendanceRecord,
            (AttendanceRecord.user_id == User.id) & (AttendanceRecord.lesson_id == lesson_id),
        ).where(User.is_active.is_(True)).order_by(User.full_name, User.id)
    )).all()
    return [StudentAttendance(
        user_id=user.id, full_name=user.full_name, subgroup=user.subgroup,
        status=record.status if record else "unmarked",
        check_in_time=record.check_in_time if record else None,
        is_confirmed=record.is_confirmed if record else False,
    ) for user, record in rows]


class ConfirmRequest(BaseModel):
    lesson_id: int
    user_ids: list[int] | None = None
    confirm_all: bool = False

    @model_validator(mode="after")
    def check_selection(self) -> "ConfirmRequest":
        if self.confirm_all == (self.user_ids is not None) or self.user_ids == []:
            raise ValueError("Specify either non-empty user_ids or confirm_all=true")
        return self


@router.post("/admin/attendance/confirm")
async def confirm(body: ConfirmRequest, session: Session, admin: Admin) -> dict[str, int]:
    lesson = await _lesson(session, body.lesson_id)
    if lesson.status == LessonStatus.CANCELLED:
        raise HTTPException(400, "Cancelled lesson")
    ids = set(body.user_ids or [])
    if not body.confirm_all:
        users = (await session.scalars(select(User).where(User.id.in_(ids), User.is_active.is_(True)))).all()
        if len(users) != len(ids) or any(lesson.subgroup not in (0, user.subgroup) for user in users):
            raise HTTPException(400, "Unknown or ineligible user")
        existing = set((await session.scalars(select(AttendanceRecord.user_id).where(
            AttendanceRecord.lesson_id == lesson.id, AttendanceRecord.user_id.in_(ids),
        ))).all())
        if existing != ids:
            raise HTTPException(400, "Some users have no check-in")
    stmt = update(AttendanceRecord).where(AttendanceRecord.lesson_id == lesson.id)
    if body.confirm_all:
        stmt = stmt.where(AttendanceRecord.user_id.in_(
            select(User.id).where(User.is_active.is_(True), User.subgroup.in_((1, 2)) if lesson.subgroup == 0 else User.subgroup == lesson.subgroup)
        ))
    else:
        stmt = stmt.where(AttendanceRecord.user_id.in_(ids))
    result = await session.execute(stmt.values(is_confirmed=True))
    await session.commit()
    return {"confirmed": result.rowcount}


class ManualAttendance(BaseModel):
    lesson_id: int
    user_id: int
    status: AttendanceStatus


@router.put("/admin/attendance/manual", response_model=AttendanceOut)
async def manual(body: ManualAttendance, session: Session, admin: Admin) -> AttendanceOut:
    lesson = await _lesson(session, body.lesson_id)
    user = await session.get(User, body.user_id)
    if user is None or not user.is_active:
        raise HTTPException(404, "User not found")
    _eligible(lesson, user)
    record = await session.scalar(select(AttendanceRecord).where(
        AttendanceRecord.lesson_id == lesson.id, AttendanceRecord.user_id == user.id,
    ))
    if record is None:
        record = AttendanceRecord(lesson_id=lesson.id, user_id=user.id, status=body.status)
        session.add(record)
    record.status = body.status
    record.is_confirmed = True
    await session.commit()
    return _out(record)
