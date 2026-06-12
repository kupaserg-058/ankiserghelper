from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import Card, Deck, SourceType


async def create_deck(
    session: AsyncSession, user_id: int, title: str, source_type: SourceType
) -> Deck:
    deck = Deck(user_id=user_id, title=title, source_type=source_type)
    session.add(deck)
    await session.commit()
    await session.refresh(deck)
    return deck


async def get_deck(session: AsyncSession, deck_id: int, user_id: int) -> Deck | None:
    result = await session.execute(
        select(Deck).where(Deck.id == deck_id, Deck.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def list_decks_with_card_count(session: AsyncSession, user_id: int) -> list[tuple[Deck, int]]:
    result = await session.execute(
        select(Deck, func.count(Card.id))
        .outerjoin(Card, Card.deck_id == Deck.id)
        .where(Deck.user_id == user_id)
        .group_by(Deck.id)
        .order_by(Deck.created_at.desc())
    )
    return [(deck, count) for deck, count in result.all()]


async def count_decks(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(select(func.count(Deck.id)).where(Deck.user_id == user_id))
    return result.scalar_one()
