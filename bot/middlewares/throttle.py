from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from redis.asyncio import Redis

THROTTLE_KEY_PREFIX = "throttle:generate"
THROTTLE_SECONDS = 1


class GenerationThrottleMiddleware(BaseMiddleware):
    """Limits flashcard-generation requests to 1 per second per user."""

    def __init__(self, redis: Redis):
        self.redis = redis

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is None:
            return await handler(event, data)

        key = f"{THROTTLE_KEY_PREFIX}:{tg_user.id}"
        is_set = await self.redis.set(key, "1", nx=True, ex=THROTTLE_SECONDS)
        if not is_set:
            return None

        return await handler(event, data)
