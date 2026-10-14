"""Initial application schema.

Revision ID: 0001_initial
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subjects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False, unique=True),
        sa.Column("teacher_name", sa.String(length=255), nullable=True),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("subgroup", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("role", sa.String(length=20), server_default="student", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint("subgroup IN (1, 2)", name="ck_users_subgroup"),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=False)
    op.create_table(
        "schedule_slots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("day_of_week", sa.SmallInteger(), nullable=False),
        sa.Column("slot_number", sa.SmallInteger(), nullable=False),
        sa.Column("parity", sa.String(length=10), server_default="all", nullable=False),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("subgroup", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("lesson_type", sa.String(length=20), nullable=False),
        sa.CheckConstraint("day_of_week BETWEEN 1 AND 7", name="ck_schedule_day"),
        sa.CheckConstraint("slot_number BETWEEN 1 AND 6", name="ck_schedule_slot"),
        sa.CheckConstraint("subgroup BETWEEN 0 AND 2", name="ck_schedule_subgroup"),
    )
    op.create_table(
        "lessons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("slot_number", sa.SmallInteger(), nullable=False),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("subgroup", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="scheduled", nullable=False),
        sa.CheckConstraint("slot_number BETWEEN 1 AND 6", name="ck_lessons_slot"),
        sa.CheckConstraint("subgroup BETWEEN 0 AND 2", name="ck_lessons_subgroup"),
        sa.UniqueConstraint("date", "slot_number", "subject_id", "subgroup", name="uq_lesson_instance"),
    )
    op.create_table(
        "homeworks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id"), nullable=False),
        sa.Column("subgroup", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("links", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
    )
    op.create_table(
        "attendance_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lesson_id", sa.Integer(), sa.ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("is_confirmed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("check_in_time", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("lesson_id", "user_id", name="uq_attendance_lesson_user"),
    )


def downgrade() -> None:
    op.drop_table("attendance_records")
    op.drop_table("homeworks")
    op.drop_table("lessons")
    op.drop_table("schedule_slots")
    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_table("users")
    op.drop_table("subjects")
