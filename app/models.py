from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Enum, ForeignKey, Integer, JSON, SmallInteger
from sqlalchemy import String, Text, UniqueConstraint, CheckConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserRole(StrEnum):
    STUDENT = "student"
    DEPUTY = "deputy"
    HEADMAN = "headman"


class Parity(StrEnum):
    ALL = "all"
    EVEN = "even"
    ODD = "odd"


class LessonType(StrEnum):
    LECTURE = "lecture"
    PRACTICE = "practice"
    LAB = "lab"


class LessonStatus(StrEnum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AttendanceStatus(StrEnum):
    PRESENT = "present"
    ABSENT_VALID = "absent_valid"
    ABSENT_INVALID = "absent_invalid"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("subgroup IN (1, 2)", name="ck_users_subgroup"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    subgroup: Mapped[int] = mapped_column(SmallInteger, default=1, server_default="1")
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, values_callable=lambda enum: [item.value for item in enum]),
        default=UserRole.STUDENT,
        server_default="student",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(back_populates="user")


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    teacher_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    schedule_slots: Mapped[list["ScheduleSlot"]] = relationship(back_populates="subject")
    lessons: Mapped[list["Lesson"]] = relationship(back_populates="subject")
    homeworks: Mapped[list["Homework"]] = relationship(back_populates="subject")


class ScheduleSlot(Base):
    __tablename__ = "schedule_slots"
    __table_args__ = (
        CheckConstraint("day_of_week BETWEEN 1 AND 7", name="ck_schedule_day"),
        CheckConstraint("slot_number BETWEEN 1 AND 6", name="ck_schedule_slot"),
        CheckConstraint("subgroup BETWEEN 0 AND 2", name="ck_schedule_subgroup"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    day_of_week: Mapped[int] = mapped_column(SmallInteger)
    slot_number: Mapped[int] = mapped_column(SmallInteger)
    parity: Mapped[Parity] = mapped_column(
        Enum(Parity, native_enum=False, values_callable=lambda enum: [item.value for item in enum]),
        default=Parity.ALL,
        server_default="all",
    )
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    subgroup: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    lesson_type: Mapped[LessonType] = mapped_column(
        Enum(LessonType, native_enum=False, values_callable=lambda enum: [item.value for item in enum])
    )
    subject: Mapped[Subject] = relationship(back_populates="schedule_slots")


class Lesson(Base):
    __tablename__ = "lessons"
    __table_args__ = (
        CheckConstraint("slot_number BETWEEN 1 AND 6", name="ck_lessons_slot"),
        CheckConstraint("subgroup BETWEEN 0 AND 2", name="ck_lessons_subgroup"),
        UniqueConstraint("date", "slot_number", "subject_id", "subgroup", name="uq_lesson_instance"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date)
    slot_number: Mapped[int] = mapped_column(SmallInteger)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    subgroup: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    status: Mapped[LessonStatus] = mapped_column(
        Enum(LessonStatus, native_enum=False, values_callable=lambda enum: [item.value for item in enum]),
        default=LessonStatus.SCHEDULED,
        server_default="scheduled",
    )
    subject: Mapped[Subject] = relationship(back_populates="lessons")
    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan"
    )


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    __table_args__ = (UniqueConstraint("lesson_id", "user_id", name="uq_attendance_lesson_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus, native_enum=False, values_callable=lambda enum: [item.value for item in enum])
    )
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    check_in_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lesson: Mapped[Lesson] = relationship(back_populates="attendance_records")
    user: Mapped[User] = relationship(back_populates="attendance_records")


class Homework(Base):
    __tablename__ = "homeworks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    subgroup: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    description: Mapped[str] = mapped_column(Text)
    links: Mapped[Any] = mapped_column(JSON, default=list, server_default=text("'[]'"))
    subject: Mapped[Subject] = relationship(back_populates="homeworks")
