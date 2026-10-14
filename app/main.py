from fastapi import APIRouter, Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session

settings = get_settings()
app = FastAPI(title=settings.app_name, debug=settings.debug)
api_router = APIRouter(prefix="/api/v1")


@api_router.get("/health")
async def health(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


app.include_router(api_router)
