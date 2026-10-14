from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = Field(default="", validation_alias="BOT_TOKEN")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/app.db", validation_alias="DATABASE_URL"
    )
    timezone: str = Field(default="UTC", validation_alias="TIMEZONE")
    app_secret_key: str = Field(
        default="change-me-in-your-env", validation_alias="APP_SECRET_KEY"
    )
    app_name: str = Field(default="University Attendance", validation_alias="APP_NAME")
    debug: bool = Field(default=False, validation_alias="DEBUG")

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
