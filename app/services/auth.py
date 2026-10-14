import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import parse_qsl

import jwt
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import get_settings
from app.models import User
from app.schemas.auth import TokenPair


class AuthenticationError(ValueError):
    pass


class TelegramUser(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int = Field(gt=0)
    first_name: str = Field(min_length=1)
    username: str | None = None


class TokenClaims(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: int = Field(gt=0)
    telegram_id: int = Field(gt=0)
    role: str
    subgroup: int = Field(ge=1, le=2)
    type: Literal["access", "refresh"]
    exp: int
    iat: int


def validate_init_data(init_data: str) -> TelegramUser:
    settings = get_settings()
    if not settings.bot_token:
        raise AuthenticationError("Telegram authentication is not configured")
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True, errors="strict")
        data = dict(pairs)
        if len(data) != len(pairs) or len(init_data) > 16_384:
            raise ValueError("Duplicate or oversized data")
        received_hash = data.pop("hash")
        if len(received_hash) != 64:
            raise ValueError("Invalid hash")
        bytes.fromhex(received_hash)
        check_string = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
        secret_key = hmac.new(b"WebAppData", settings.bot_token.encode(), hashlib.sha256).digest()
        expected_hash = hmac.new(secret_key, check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_hash, received_hash.lower()):
            raise ValueError("Signature mismatch")
        auth_date = int(data["auth_date"])
        now = int(datetime.now(timezone.utc).timestamp())
        if auth_date > now or now - auth_date > 24 * 60 * 60:
            raise ValueError("Expired or future auth_date")
        return TelegramUser.model_validate(json.loads(data["user"]))
    except (KeyError, ValueError, TypeError, ValidationError) as exc:
        raise AuthenticationError("Invalid Telegram initData") from exc


def _jwt_secret() -> str:
    secret = get_settings().app_secret_key
    if not secret or secret == "change-me-in-your-env":
        raise RuntimeError("Set a secure APP_SECRET_KEY before issuing tokens")
    return secret


def create_token(user: User, token_type: Literal["access", "refresh"]) -> str:
    now = datetime.now(timezone.utc)
    expires = now + (timedelta(minutes=60) if token_type == "access" else timedelta(days=30))
    payload = {
        "user_id": user.id,
        "telegram_id": user.telegram_id,
        "role": user.role.value,
        "subgroup": user.subgroup,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm="HS256")


def create_token_pair(user: User) -> TokenPair:
    return TokenPair(access_token=create_token(user, "access"), refresh_token=create_token(user, "refresh"))


def decode_token(token: str, expected_type: Literal["access", "refresh"]) -> TokenClaims:
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=["HS256"], options={"require": ["exp", "iat"]})
        claims = TokenClaims.model_validate(payload)
        if claims.type != expected_type:
            raise AuthenticationError("Wrong token type")
        return claims
    except (jwt.PyJWTError, ValidationError, ValueError) as exc:
        raise AuthenticationError("Invalid or expired token") from exc
