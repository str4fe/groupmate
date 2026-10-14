from contextlib import aclosing
from html import escape
import logging

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.types import MenuButtonWebApp, Message
from sqlalchemy import select

from app.bot.keyboards.inline import get_main_keyboard, get_web_app_info
from app.db import get_session
from app.models import User, UserRole


router = Router()
logger = logging.getLogger(__name__)

ROLE_NAMES = {
    UserRole.STUDENT: "Студент",
    UserRole.HEADMAN: "Староста",
    UserRole.DEPUTY: "Зам. старосты",
}


async def _find_user(telegram_id: int) -> User | None:
    async with aclosing(get_session()) as sessions:
        session = await anext(sessions)
        return await session.scalar(select(User).where(User.telegram_id == telegram_id))


@router.message(CommandStart())
async def start(message: Message) -> None:
    if message.from_user is None:
        return

    user = await _find_user(message.from_user.id)
    if user is None:
        await message.answer(
            "Здравствуйте! Вас нет в списках группы ББ-607.\n"
            f"Ваш Telegram ID: <code>{message.from_user.id}</code>.\n"
            "Пожалуйста, обратитесь к старосте, чтобы вас добавили."
        )
        return

    bot = message.bot
    if bot is None:
        return
    web_app = get_web_app_info()
    keyboard = get_main_keyboard()
    webapp_note = ""
    if web_app is None:
        webapp_note = (
            "\nДля запуска Mini App нужен HTTPS-адрес. "
            "В локальной разработке настройте HTTPS-туннель и укажите его в WEBAPP_URL."
        )
    else:
        try:
            await bot.set_chat_menu_button(
                chat_id=message.chat.id,
                menu_button=MenuButtonWebApp(text="Открыть приложение", web_app=web_app),
            )
        except TelegramBadRequest:
            logger.exception("Telegram rejected the Mini App menu button")

    await message.answer(
        f"Здравствуйте, {escape(user.full_name)}!\n"
        f"Роль: {ROLE_NAMES[user.role]}\n"
        f"Подгруппа: {user.subgroup}{webapp_note}",
        reply_markup=keyboard,
    )


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        "Доступные команды:\n"
        "/start - информация о вашем аккаунте\n"
        "/help - список команд\n"
        "/my_id - ваш Telegram ID и username"
    )


@router.message(Command("my_id"))
async def my_id(message: Message) -> None:
    if message.from_user is None:
        return

    username = f"@{message.from_user.username}" if message.from_user.username else "не указан"
    await message.answer(
        f"Ваш Telegram ID: <code>{message.from_user.id}</code>\n"
        f"Username: {escape(username)}"
    )
