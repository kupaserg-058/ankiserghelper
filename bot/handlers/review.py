from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.common import START_REVIEW
from bot.keyboards.decks import DECK_PREFIX, decks_list_keyboard
from bot.keyboards.main_menu import BTN_CARDS
from bot.keyboards.review import (
    GRADE_AGAIN,
    GRADE_KNEW,
    SHOW_ANSWER,
    grade_keyboard,
    show_answer_keyboard,
)
from bot.logger import get_logger
from bot.models import User
from bot.repositories.card_repo import get_card
from bot.repositories.deck_repo import list_decks_with_card_count
from bot.repositories.review_repo import apply_sm2_result, get_due_cards, get_review
from bot.repositories.session_repo import finish_session, record_answer, start_session
from bot.services.sm2 import sm2
from bot.states import Review

logger = get_logger(__name__)

router = Router()

GRADE_QUALITY = {
    GRADE_AGAIN: 2,
    GRADE_KNEW: 4,
}


@router.message(F.text == BTN_CARDS)
async def show_review_decks(message: Message, session: AsyncSession, db_user: User) -> None:
    decks = await list_decks_with_card_count(session, db_user.id)
    if not decks:
        await message.answer("У тебя пока нет колод. Создай первую в «📚 Мои колоды».")
        return

    await message.answer(
        "Выбери колоду для повторения:",
        reply_markup=decks_list_keyboard(decks, action_prefix=DECK_PREFIX),
    )


async def _start_review_session(
    message_target: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    deck_id: int | None,
) -> None:
    due = await get_due_cards(session, db_user.id, deck_id)
    if not due:
        await message_target.answer("🎉 На сегодня карточек для повторения нет!")
        return

    review_session = await start_session(session, db_user.id, deck_id)

    await state.update_data(
        queue=[card.id for _, card in due],
        review_session_id=review_session.id,
        deck_id=deck_id,
    )
    await state.set_state(Review.waiting_answer)

    await _show_next_card(message_target, state, session, db_user)


@router.callback_query(F.data.startswith(f"{DECK_PREFIX}:"))
async def callback_select_deck_for_review(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    deck_id = int(callback.data.split(":")[-1])
    await callback.message.edit_reply_markup(reply_markup=None)
    await _start_review_session(callback.message, state, session, db_user, deck_id)
    await callback.answer()


@router.callback_query(F.data.startswith(f"{START_REVIEW}:"))
async def callback_start_review(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    deck_id = int(callback.data.split(":")[-1])
    await callback.message.edit_reply_markup(reply_markup=None)
    await _start_review_session(callback.message, state, session, db_user, deck_id)
    await callback.answer()


async def _show_next_card(
    message_target: Message, state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    data = await state.get_data()
    queue: list[int] = data["queue"]

    if not queue:
        await _finish_review(message_target, state, session)
        return

    card_id = queue[0]
    card = await get_card(session, card_id)

    if card is None:
        queue.pop(0)
        await state.update_data(queue=queue)
        await _show_next_card(message_target, state, session, db_user)
        return

    text = f"🔁 <b>Вопрос:</b>\n{card.question}"
    await message_target.answer(text, reply_markup=show_answer_keyboard())


async def _finish_review(message_target: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    review_session_id = data.get("review_session_id")

    from bot.models import ReviewSession as ReviewSessionModel

    review_session = await session.get(ReviewSessionModel, review_session_id)
    if review_session is not None:
        await finish_session(session, review_session)
        total = review_session.cards_reviewed
        correct = review_session.correct_count
        await message_target.answer(
            f"🏁 Сессия завершена!\n\n"
            f"Знал: {correct}/{total}\n\n"
            f"Карточки, которые ты не знал, появятся снова раньше — "
            f"проверь «📊 Статистика» для общей информации."
        )

    await state.clear()


@router.callback_query(Review.waiting_answer, F.data == SHOW_ANSWER)
async def show_answer(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    data = await state.get_data()
    queue: list[int] = data["queue"]
    if not queue:
        await callback.answer()
        return

    card = await get_card(session, queue[0])
    if card is None:
        await callback.answer()
        return

    text = f"🔁 <b>Вопрос:</b>\n{card.question}\n\n💡 <b>Ответ:</b>\n{card.answer or '—'}"
    await callback.message.edit_text(text, reply_markup=grade_keyboard())
    await callback.answer()


@router.callback_query(Review.waiting_answer, F.data.in_(GRADE_QUALITY.keys()))
async def process_grade(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    data = await state.get_data()
    queue: list[int] = data["queue"]
    if not queue:
        await callback.answer()
        return

    card = await get_card(session, queue[0])
    if card is None:
        await callback.answer()
        return

    quality = GRADE_QUALITY[callback.data]

    review = await get_review(session, card.id, db_user.id)
    if review is not None:
        result = sm2(quality, review.ease_factor, review.interval, review.repetition)
        await apply_sm2_result(session, review, result)

    review_session_id = data.get("review_session_id")
    from bot.models import ReviewSession as ReviewSessionModel

    review_session = await session.get(ReviewSessionModel, review_session_id)
    if review_session is not None:
        await record_answer(session, review_session, correct=quality >= 3)

    await callback.message.edit_reply_markup(reply_markup=None)

    queue.pop(0)
    await state.update_data(queue=queue)

    await _show_next_card(callback.message, state, session, db_user)
    await callback.answer()
