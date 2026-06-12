from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.db import async_session_maker
from bot.repositories.user_repo import get_or_create_user


class DbSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with async_session_maker() as session:
            data["session"] = session

            tg_user = data.get("event_from_user")
            if tg_user is not None:
                data["db_user"] = await get_or_create_user(session, tg_user.id, tg_user.username)

            return await handler(event, data)
