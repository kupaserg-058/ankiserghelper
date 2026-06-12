from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from bot.models import ReviewSession


async def start_session(session: AsyncSession, user_id: int, deck_id: int | None) -> ReviewSession:
    review_session = ReviewSession(user_id=user_id, deck_id=deck_id)
    session.add(review_session)
    await session.commit()
    await session.refresh(review_session)
    return review_session


async def record_answer(session: AsyncSession, review_session: ReviewSession, correct: bool) -> None:
    review_session.cards_reviewed += 1
    if correct:
        review_session.correct_count += 1
    await session.commit()


async def finish_session(session: AsyncSession, review_session: ReviewSession) -> None:
    review_session.finished_at = datetime.now(timezone.utc)
    await session.commit()
