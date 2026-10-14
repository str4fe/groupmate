from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from app.config import get_settings


def get_web_app_info() -> WebAppInfo | None:
    url = get_settings().webapp_url.strip()
    if not url.lower().startswith("https://"):
        return None
    return WebAppInfo(url=url)


def get_main_keyboard() -> InlineKeyboardMarkup | None:
    web_app = get_web_app_info()
    if web_app is None:
        return None

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть приложение", web_app=web_app)]
        ]
    )
