from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.common import START_REVIEW
from bot.keyboards.review import (
    ANSWER_PREFIX,
    NEXT_CARD,
    multiple_choice_keyboard,
    next_card_keyboard,
)
from bot.logger import get_logger
from bot.models import Card, CardType, User
from bot.repositories.card_repo import get_card
from bot.repositories.deck_repo import get_deck
from bot.repositories.review_repo import apply_sm2_result, get_due_cards, get_review
from bot.repositories.session_repo import finish_session, record_answer, start_session
from bot.services import gemini
from bot.services.sm2 import sm2
from bot.states import Review

logger = get_logger(__name__)

router = Router()

CARD_TYPE_ICONS = {
    CardType.flashcard: "🔁",
    CardType.multiple_choice: "🔤",
    CardType.open_question: "💬",
}


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


@router.message(Command("review"))
async def cmd_review(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
) -> None:
    deck_id = None
    if command.args:
        try:
            deck_id = int(command.args.strip())
        except ValueError:
            await message.answer("Используй: /review или /review <id колоды>")
            return

        deck = await get_deck(session, deck_id, db_user.id)
        if deck is None:
            await message.answer("Колода с таким id не найдена.")
            return

    await _start_review_session(message, state, session, db_user, deck_id)


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

    icon = CARD_TYPE_ICONS[card.card_type]

    if card.card_type == CardType.multiple_choice:
        text = f"{icon} <b>Вопрос:</b>\n{card.question}"
        await message_target.answer(text, reply_markup=multiple_choice_keyboard(card.id, card.options))
    else:
        text = f"{icon} <b>Вопрос:</b>\n{card.question}\n\n✏️ Напиши свой ответ:"
        await message_target.answer(text)


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
            f"Правильных ответов: {correct}/{total}\n\n"
            f"Карточки, которые ты не знал, появятся снова раньше — "
            f"проверь /stats для общей статистики."
        )

    await state.clear()


async def _process_answer_result(
    message_target: Message,
    state: FSMContext,
    session: AsyncSession,
    db_user: User,
    card: Card,
    score: int,
    feedback: str,
) -> None:
    review = await get_review(session, card.id, db_user.id)
    if review is not None:
        result = sm2(score, review.ease_factor, review.interval, review.repetition)
        await apply_sm2_result(session, review, result)
        days = result.next_review_date
    else:
        days = None

    data = await state.get_data()
    review_session_id = data.get("review_session_id")
    from bot.models import ReviewSession as ReviewSessionModel

    review_session = await session.get(ReviewSessionModel, review_session_id)
    if review_session is not None:
        await record_answer(session, review_session, correct=score >= 3)

    next_review_text = f"\n\n📅 Следующее повторение: {days}" if days else ""
    await message_target.answer(f"{feedback}{next_review_text}", reply_markup=next_card_keyboard())

    queue: list[int] = data["queue"]
    if queue and queue[0] == card.id:
        queue.pop(0)
    await state.update_data(queue=queue)


@router.message(Review.waiting_answer, F.text)
async def process_text_answer(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    data = await state.get_data()
    queue: list[int] = data["queue"]
    if not queue:
        await _finish_review(message, state, session)
        return

    card = await get_card(session, queue[0])
    if card is None or card.card_type == CardType.multiple_choice:
        return

    user_answer = message.text or ""

    if card.card_type == CardType.flashcard:
        result = await gemini.check_flashcard(card.question, card.answer or "", user_answer)
        feedback = f"📊 Оценка: {result.score}/5 ({result.verdict})\n\n{result.explanation}"
        score = result.score
    else:
        oq_result = await gemini.check_open_question(card.question, card.answer or "", user_answer)
        missed = ""
        if oq_result.missed_points:
            missed = "\n\nУпущено:\n" + "\n".join(f"• {p}" for p in oq_result.missed_points)
        feedback = f"📊 Оценка: {oq_result.score}/5\n\n{oq_result.feedback}{missed}"
        score = oq_result.score

    await _process_answer_result(message, state, session, db_user, card, score, feedback)


@router.callback_query(Review.waiting_answer, F.data.startswith(f"{ANSWER_PREFIX}:"))
async def process_multiple_choice_answer(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    _, card_id_str, choice_str = callback.data.split(":")[1:]
    card_id = int(card_id_str)
    choice = int(choice_str)

    data = await state.get_data()
    queue: list[int] = data["queue"]
    if not queue or queue[0] != card_id:
        await callback.answer()
        return

    card = await get_card(session, card_id)
    if card is None:
        await callback.answer()
        return

    await callback.message.edit_reply_markup(reply_markup=None)

    if choice == card.correct_index:
        score = 5
        feedback = "✅ Верно!"
    else:
        score = 1
        correct_option = card.options[card.correct_index]
        feedback = f"❌ Неверно. Правильный ответ: {correct_option}"

    await _process_answer_result(callback.message, state, session, db_user, card, score, feedback)
    await callback.answer()


@router.callback_query(Review.waiting_answer, F.data == NEXT_CARD)
async def process_next_card(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    await callback.message.edit_reply_markup(reply_markup=None)
    await _show_next_card(callback.message, state, session, db_user)
    await callback.answer()
