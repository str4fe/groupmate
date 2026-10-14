import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.db import async_session_factory
from app.models import Subject, User, UserRole


async def seed_file(path: Path) -> None:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    async with async_session_factory() as session:
        for item in data.get("subjects", []):
            name = item["name"].strip()
            subject = await session.scalar(select(Subject).where(Subject.name == name))
            if subject is None:
                session.add(Subject(name=name, teacher_name=item.get("teacher_name")))
            elif item.get("teacher_name") is not None:
                subject.teacher_name = item["teacher_name"]

        await session.flush()
        for item in data.get("students", []):
            telegram_id = int(item["telegram_id"])
            user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
            role = UserRole(item.get("role", UserRole.STUDENT))
            if user is None:
                session.add(
                    User(
                        telegram_id=telegram_id,
                        full_name=item["full_name"].strip(),
                        subgroup=item.get("subgroup", 1),
                        role=role,
                        is_active=item.get("is_active", True),
                    )
                )
            else:
                user.full_name = item["full_name"].strip()
                user.subgroup = item.get("subgroup", 1)
                user.role = role
                user.is_active = item.get("is_active", True)
        await session.commit()
    print(f"Seed imported from {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import subjects and students from JSON")
    parser.add_argument("path", nargs="?", type=Path, default=Path("group_seed.json"))
    args = parser.parse_args()
    asyncio.run(seed_file(args.path))


if __name__ == "__main__":
    main()
