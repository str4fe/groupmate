from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.api.auth import router as auth_router
from app.api.deps import get_current_user, require_role
from app.db import get_session
from app.models import User, UserRole
from app.schemas.auth import UserProfile

settings = get_settings()
app = FastAPI(title=settings.app_name, debug=settings.debug)
api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)


@api_router.get("/health")
async def health(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


@api_router.get("/users/me", response_model=UserProfile)
async def get_me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user


@api_router.get("/admin/ping")
async def admin_ping(
    user: Annotated[User, Depends(require_role(UserRole.HEADMAN, UserRole.DEPUTY))],
) -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router)
