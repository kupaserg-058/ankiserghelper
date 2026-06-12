from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.decks import TEST_DECK_PREFIX, decks_list_keyboard
from bot.keyboards.main_menu import BTN_TESTS
from bot.keyboards.test import (
    TEST_ANSWER_PREFIX,
    TEST_NEXT,
    test_multiple_choice_keyboard,
    test_next_keyboard,
)
from bot.logger import get_logger
from bot.models import User
from bot.repositories.card_repo import get_cards_by_deck
from bot.repositories.deck_repo import list_decks_with_card_count
from bot.services import gemini
from bot.states import Test

logger = get_logger(__name__)

router = Router()


@router.message(F.text == BTN_TESTS)
async def show_test_decks(message: Message, session: AsyncSession, db_user: User) -> None:
    decks = await list_decks_with_card_count(session, db_user.id)
    if not decks:
        await message.answer("У тебя пока нет колод. Создай первую в «📚 Мои колоды».")
        return

    await message.answer(
        "Выбери колоду для теста:",
        reply_markup=decks_list_keyboard(decks, action_prefix=TEST_DECK_PREFIX),
    )


@router.callback_query(F.data.startswith(f"{TEST_DECK_PREFIX}:"))
async def start_test(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    deck_id = int(callback.data.split(":")[-1])
    await callback.message.edit_text("⏳ Готовлю тест...")
    await callback.answer()

    cards = await get_cards_by_deck(session, deck_id)
    if not cards:
        await callback.message.edit_text("В этой колоде нет карточек.")
        return

    pairs = [(c.question, c.answer or "") for c in cards]

    try:
        questions = await gemini.generate_test_questions(pairs)
    except Exception:
        logger.exception("test_generation_failed", deck_id=deck_id)
        await callback.message.edit_text("❌ Не удалось создать тест. Попробуй ещё раз.")
        return

    if not questions:
        await callback.message.edit_text("❌ Не удалось создать тест по этой колоде.")
        return

    await state.update_data(
        questions=[q.model_dump() for q in questions],
        correct_count=0,
        total_count=len(questions),
    )
    await state.set_state(Test.waiting_answer)

    await callback.message.edit_text(f"📝 Тест из {len(questions)} вопросов. Начинаем!")
    await _show_next_question(callback.message, state)


async def _show_next_question(message_target: Message, state: FSMContext) -> None:
    data = await state.get_data()
    questions: list[dict] = data["questions"]

    if not questions:
        await _finish_test(message_target, state)
        return

    q = questions[0]

    if q["question_type"] == "multiple_choice":
        text = f"🔤 <b>Вопрос:</b>\n{q['question']}"
        await message_target.answer(text, reply_markup=test_multiple_choice_keyboard(q["options"]))
    else:
        text = f"💬 <b>Вопрос:</b>\n{q['question']}\n\n✏️ Напиши свой ответ:"
        await message_target.answer(text)


async def _finish_test(message_target: Message, state: FSMContext) -> None:
    data = await state.get_data()
    correct = data.get("correct_count", 0)
    total = data.get("total_count", 0)
    await message_target.answer(f"🏁 Тест завершён!\n\nПравильных ответов: {correct}/{total}")
    await state.clear()


@router.message(Test.waiting_answer, F.text)
async def process_open_answer(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    questions: list[dict] = data["questions"]
    if not questions:
        await _finish_test(message, state)
        return

    q = questions[0]
    if q["question_type"] != "open_question":
        return

    result = await gemini.check_open_question(q["question"], q.get("answer") or "", message.text or "")
    missed = ""
    if result.missed_points:
        missed = "\n\nУпущено:\n" + "\n".join(f"• {p}" for p in result.missed_points)
    feedback = f"📊 Оценка: {result.score}/5\n\n{result.feedback}{missed}"

    if result.score >= 3:
        await state.update_data(correct_count=data.get("correct_count", 0) + 1)

    questions.pop(0)
    await state.update_data(questions=questions)

    await message.answer(feedback, reply_markup=test_next_keyboard())


@router.callback_query(Test.waiting_answer, F.data.startswith(f"{TEST_ANSWER_PREFIX}:"))
async def process_choice_answer(callback: CallbackQuery, state: FSMContext) -> None:
    choice = int(callback.data.split(":")[-1])

    data = await state.get_data()
    questions: list[dict] = data["questions"]
    if not questions:
        await callback.answer()
        return

    q = questions[0]
    await callback.message.edit_reply_markup(reply_markup=None)

    if choice == q.get("correct_index"):
        await state.update_data(correct_count=data.get("correct_count", 0) + 1)
        feedback = "✅ Верно!"
    else:
        correct_option = q["options"][q["correct_index"]]
        feedback = f"❌ Неверно. Правильный ответ: {correct_option}"

    questions.pop(0)
    await state.update_data(questions=questions)

    await callback.message.answer(feedback, reply_markup=test_next_keyboard())
    await callback.answer()


@router.callback_query(Test.waiting_answer, F.data == TEST_NEXT)
async def process_next_question(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.edit_reply_markup(reply_markup=None)
    await _show_next_question(callback.message, state)
    await callback.answer()
