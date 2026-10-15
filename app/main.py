from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.attendance import router as attendance_router
from app.api.auth import router as auth_router
from app.api.deps import get_current_user, require_role
from app.api.export import router as export_router
from app.api.lessons import router as lessons_router
from app.config import get_settings
from app.db import get_session
from app.models import User, UserRole
from app.schemas.auth import UserProfile

settings = get_settings()
app = FastAPI(title=settings.app_name, debug=settings.debug)


@app.exception_handler(404)
async def not_found(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": exc.detail})


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(lessons_router)
api_router.include_router(attendance_router)
api_router.include_router(export_router)


@api_router.get("/health")
async def health(session: Annotated[AsyncSession, Depends(get_session)]) -> dict[str, str]:
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


@app.api_route("/api/v1/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"], include_in_schema=False)
async def unknown_api(path: str) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "Not Found"})

# Resolve from the project root so the app behaves consistently from any cwd.
frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.is_dir():
    @app.get("/", include_in_schema=False)
    async def frontend_index() -> FileResponse:
        return FileResponse(frontend_dist / "index.html")

    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
