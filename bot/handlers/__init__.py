from aiogram import Router

from bot.handlers import decks, review, start, stats


def get_main_router() -> Router:
    router = Router()
    router.include_router(start.router)
    router.include_router(decks.router)
    router.include_router(review.router)
    router.include_router(stats.router)
    return router
