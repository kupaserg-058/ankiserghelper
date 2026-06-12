import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from bot.config import settings
from bot.handlers import get_main_router
from bot.logger import configure_logging, get_logger
from bot.middlewares.auth import AuthMiddleware
from bot.middlewares.db import DbSessionMiddleware
from bot.middlewares.throttle import GenerationThrottleMiddleware

logger = get_logger(__name__)


async def main() -> None:
    configure_logging()

    redis = Redis.from_url(settings.redis_url)
    storage = RedisStorage(redis=redis)

    bot = Bot(
        token=settings.telegram_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=storage)

    dp.update.middleware(AuthMiddleware())
    dp.update.middleware(DbSessionMiddleware())
    dp.message.middleware(GenerationThrottleMiddleware(redis=redis))

    dp.include_router(get_main_router())

    logger.info("bot_starting")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
