from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import User
from app.schemas.auth import AccessToken, DevLoginRequest, RefreshRequest, TelegramLoginRequest, TokenPair
from app.services.auth import AuthenticationError, create_token, create_token_pair, decode_token, validate_init_data

router = APIRouter(prefix="/auth", tags=["auth"])
Session = Annotated[AsyncSession, Depends(get_session)]


async def _find_active_user(session: AsyncSession, telegram_id: int) -> User:
    user = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользователь не зарегистрирован в группе. Обратитесь к старосте.",
        )
    return user


@router.post("/telegram", response_model=TokenPair)
async def telegram_login(body: TelegramLoginRequest, session: Session) -> TokenPair:
    try:
        telegram_user = validate_init_data(body.init_data)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return create_token_pair(await _find_active_user(session, telegram_user.id))


@router.post("/refresh", response_model=AccessToken)
async def refresh(body: RefreshRequest, session: Session) -> AccessToken:
    try:
        claims = decode_token(body.refresh_token, "refresh")
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    user = await session.get(User, claims.user_id)
    if user is None or not user.is_active or user.telegram_id != claims.telegram_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    return AccessToken(access_token=create_token(user, "access"))


@router.post("/dev-login", response_model=TokenPair)
async def dev_login(body: DevLoginRequest, session: Session) -> TokenPair:
    if not get_settings().debug_auth:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    return create_token_pair(await _find_active_user(session, body.telegram_id))
