from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import UserRole


class TelegramLoginRequest(BaseModel):
    init_data: str = Field(min_length=1)


class DevLoginRequest(BaseModel):
    telegram_id: int = Field(gt=0)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


class AccessToken(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: int
    full_name: str
    role: UserRole
    subgroup: int
