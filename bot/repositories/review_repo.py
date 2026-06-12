from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import Card, CardReview, Deck
from bot.services.sm2 import SM2Result


async def get_due_cards(
    session: AsyncSession, user_id: int, deck_id: int | None = None, today: date | None = None
) -> list[tuple[CardReview, Card]]:
    today = today or date.today()

    stmt = (
        select(CardReview, Card)
        .join(Card, Card.id == CardReview.card_id)
        .where(CardReview.user_id == user_id, CardReview.next_review_date <= today)
    )
    if deck_id is not None:
        stmt = stmt.join(Deck, Deck.id == Card.deck_id).where(Deck.id == deck_id)

    result = await session.execute(stmt)
    return [(review, card) for review, card in result.all()]


async def get_review(session: AsyncSession, card_id: int, user_id: int) -> CardReview | None:
    result = await session.execute(
        select(CardReview).where(CardReview.card_id == card_id, CardReview.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def apply_sm2_result(session: AsyncSession, review: CardReview, result: SM2Result) -> None:
    review.ease_factor = result.ease_factor
    review.interval = result.interval
    review.repetition = result.repetition
    review.next_review_date = result.next_review_date
    review.last_reviewed_at = datetime.now(timezone.utc)
    await session.commit()
