from datetime import date

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import Card, CardReview, Deck, ReviewSession, User

router = Router()


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession, db_user: User) -> None:
    decks_count = await session.scalar(
        select(func.count(Deck.id)).where(Deck.user_id == db_user.id)
    )
    cards_count = await session.scalar(
        select(func.count(Card.id)).join(Deck, Deck.id == Card.deck_id).where(Deck.user_id == db_user.id)
    )
    due_count = await session.scalar(
        select(func.count(CardReview.id)).where(
            CardReview.user_id == db_user.id, CardReview.next_review_date <= date.today()
        )
    )
    sessions_count = await session.scalar(
        select(func.count(ReviewSession.id)).where(
            ReviewSession.user_id == db_user.id, ReviewSession.finished_at.is_not(None)
        )
    )

    totals = await session.execute(
        select(
            func.coalesce(func.sum(ReviewSession.cards_reviewed), 0),
            func.coalesce(func.sum(ReviewSession.correct_count), 0),
        ).where(ReviewSession.user_id == db_user.id, ReviewSession.finished_at.is_not(None))
    )
    total_reviewed, total_correct = totals.one()

    accuracy = f"{(total_correct / total_reviewed * 100):.1f}%" if total_reviewed else "—"

    text = (
        "📊 <b>Твоя статистика</b>\n\n"
        f"Колод: {decks_count}\n"
        f"Карточек: {cards_count}\n"
        f"К повторению сегодня: {due_count}\n"
        f"Завершённых сессий: {sessions_count}\n"
        f"Средняя точность: {accuracy}"
    )
    await message.answer(text)
