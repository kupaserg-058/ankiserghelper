from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import Card, CardReview, CardType
from bot.services.gemini import GeneratedCard


async def bulk_create_cards(session: AsyncSession, deck_id: int, cards: list[GeneratedCard]) -> list[Card]:
    db_cards = []
    for c in cards:
        db_cards.append(
            Card(
                deck_id=deck_id,
                question=c.question,
                answer=c.answer,
                card_type=CardType(c.card_type),
                options=c.options,
                correct_index=c.correct_index,
            )
        )
    session.add_all(db_cards)
    await session.commit()
    for db_card in db_cards:
        await session.refresh(db_card)
    return db_cards


async def init_reviews_for_cards(
    session: AsyncSession, user_id: int, cards: list[Card], today: date | None = None
) -> None:
    today = today or date.today()
    reviews = [
        CardReview(card_id=card.id, user_id=user_id, next_review_date=today)
        for card in cards
    ]
    session.add_all(reviews)
    await session.commit()


async def count_cards(session: AsyncSession, deck_id: int) -> int:
    result = await session.execute(select(func.count(Card.id)).where(Card.deck_id == deck_id))
    return result.scalar_one()


async def get_card(session: AsyncSession, card_id: int) -> Card | None:
    result = await session.execute(select(Card).where(Card.id == card_id))
    return result.scalar_one_or_none()
