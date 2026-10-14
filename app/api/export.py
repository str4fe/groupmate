from datetime import date, timedelta
from io import BytesIO
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.config import get_settings
from app.db import get_session
from app.models import AttendanceRecord, AttendanceStatus, Lesson, LessonStatus, User, UserRole
from app.services.schedule import lessons_for_date

router = APIRouter(tags=["attendance"])
Session = Annotated[AsyncSession, Depends(get_session)]
Admin = Annotated[User, Depends(require_role(UserRole.HEADMAN, UserRole.DEPUTY))]


def _safe_cell(value: str) -> str:
    # Avoid treating names imported from external sources as spreadsheet formulas.
    return "'" + value if value.startswith(("=", "+", "-", "@")) else value


@router.get("/admin/attendance/export/excel")
async def export_excel(
    date_from: date, date_to: date, session: Session, admin: Admin,
) -> StreamingResponse:
    if date_to < date_from or (date_to - date_from).days > 366:
        raise HTTPException(422, "Date range must be ordered and at most 366 days")

    lessons: list[Lesson] = []
    day = date_from
    while day <= date_to:
        lessons.extend(
            lesson for lesson in await lessons_for_date(session, day)
            if lesson.status != LessonStatus.CANCELLED
        )
        day += timedelta(days=1)
    users = (await session.scalars(
        select(User).where(User.is_active.is_(True)).order_by(User.full_name, User.id)
    )).all()
    lesson_ids = [lesson.id for lesson in lessons]
    records = (await session.scalars(
        select(AttendanceRecord).where(AttendanceRecord.lesson_id.in_(lesson_ids))
    )).all() if lesson_ids else []
    by_pair = {(record.lesson_id, record.user_id): record for record in records}

    book = Workbook()
    sheet = book.active
    sheet.title = "Ведомость"
    sheet.append([_safe_cell(
        f"{get_settings().group_name}: {date_from.isoformat()} - {date_to.isoformat()}"
    )])
    sheet.append([
        "№ п/п", "ФИО", "Подгруппа",
        *(f"{lesson.date:%d.%m.%Y} · {lesson.slot_number} · {_safe_cell(lesson.subject.name)}"
          for lesson in lessons),
        "Всего часов", "Пропущено (уваж.)", "Пропущено (неуваж.)",
    ])
    for number, user in enumerate(users, 1):
        total = valid = invalid = 0
        marks: list[str] = []
        for lesson in lessons:
            if lesson.subgroup not in (0, user.subgroup):
                marks.append("")
                continue
            total += 2
            record = by_pair.get((lesson.id, user.id))
            if record is None:
                marks.append("")
            elif record.status == AttendanceStatus.PRESENT:
                marks.append("+")
            elif record.status == AttendanceStatus.ABSENT_VALID:
                marks.append("У")
                valid += 2
            else:
                marks.append("Н")
                invalid += 2
        sheet.append([number, _safe_cell(user.full_name), user.subgroup, *marks, total, valid, invalid])

    sheet.freeze_panes = "D3"
    sheet.column_dimensions["B"].width = 35
    for cell in sheet[2]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(wrap_text=True)
    sheet.row_dimensions[2].height = 45
    stream = BytesIO()
    book.save(stream)
    stream.seek(0)
    filename = f"attendance_{date_from.isoformat()}_{date_to.isoformat()}.xlsx"
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
