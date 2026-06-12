from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.decks import (
    CARD_DELETE_CONFIRM_PREFIX,
    CARD_DELETE_PREFIX,
    CARD_EDIT_A_PREFIX,
    CARD_EDIT_Q_PREFIX,
    CARD_VIEW_PREFIX,
    CARDS_LIST_PREFIX,
    CARDS_PAGE_SIZE,
    card_delete_confirm_keyboard,
    card_view_keyboard,
    cards_list_keyboard,
)
from bot.logger import get_logger
from bot.models import User
from bot.repositories.card_repo import (
    delete_card,
    get_card,
    get_cards_by_deck,
    update_card_answer,
    update_card_question,
)
from bot.repositories.deck_repo import get_deck
from bot.states import EditCard

logger = get_logger(__name__)

router = Router()


def _card_view_text(card) -> str:
    return f"❓ <b>Вопрос:</b>\n{card.question}\n\n💡 <b>Ответ:</b>\n{card.answer or '—'}"


def _list_text(deck_title: str, page: int, total: int, page_cards: list) -> str:
    if not page_cards:
        return f"📋 «{deck_title}» — карточек пока нет"
    start = page * CARDS_PAGE_SIZE
    return f"📋 «{deck_title}» — карточки {start + 1}-{start + len(page_cards)} из {total}"


@router.callback_query(F.data.startswith(f"{CARDS_LIST_PREFIX}:"))
async def show_cards_list(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    parts = callback.data.split(":")
    deck_id, page = int(parts[-2]), int(parts[-1])

    deck = await get_deck(session, deck_id, db_user.id)
    if deck is None:
        await callback.answer("Колода не найдена.")
        return

    cards = await get_cards_by_deck(session, deck_id)
    total = len(cards)
    start = page * CARDS_PAGE_SIZE
    page_cards = cards[start : start + CARDS_PAGE_SIZE]

    if not page_cards and page > 0:
        page = 0
        page_cards = cards[:CARDS_PAGE_SIZE]

    text = _list_text(deck.title, page, total, page_cards)
    await callback.message.edit_text(
        text, reply_markup=cards_list_keyboard(page_cards, deck_id, page, total)
    )
    await callback.answer()


@router.callback_query(F.data.startswith(f"{CARD_VIEW_PREFIX}:"))
async def show_card_view(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    parts = callback.data.split(":")
    card_id, page = int(parts[-2]), int(parts[-1])

    card = await get_card(session, card_id)
    if card is None:
        await callback.answer("Карточка не найдена.")
        return

    await callback.message.edit_text(
        _card_view_text(card), reply_markup=card_view_keyboard(card.id, card.deck_id, page)
    )
    await callback.answer()


@router.callback_query(F.data.startswith(f"{CARD_DELETE_PREFIX}:"))
async def confirm_delete_card(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    parts = callback.data.split(":")
    card_id, page = int(parts[-2]), int(parts[-1])

    card = await get_card(session, card_id)
    if card is None:
        await callback.answer("Карточка не найдена.")
        return

    text = f"Удалить карточку?\n\n❓ {card.question}"
    await callback.message.edit_text(
        text, reply_markup=card_delete_confirm_keyboard(card.id, card.deck_id, page)
    )
    await callback.answer()


@router.callback_query(F.data.startswith(f"{CARD_DELETE_CONFIRM_PREFIX}:"))
async def do_delete_card(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    parts = callback.data.split(":")
    card_id, page = int(parts[-2]), int(parts[-1])

    card = await get_card(session, card_id)
    if card is None:
        await callback.answer("Карточка не найдена.")
        return

    deck_id = card.deck_id
    await delete_card(session, card)

    cards = await get_cards_by_deck(session, deck_id)
    total = len(cards)
    if page * CARDS_PAGE_SIZE >= total and page > 0:
        page -= 1
    start = page * CARDS_PAGE_SIZE
    page_cards = cards[start : start + CARDS_PAGE_SIZE]

    deck = await get_deck(session, deck_id, db_user.id)
    text = "🗑 Карточка удалена.\n\n" + _list_text(deck.title, page, total, page_cards)
    await callback.message.edit_text(
        text, reply_markup=cards_list_keyboard(page_cards, deck_id, page, total)
    )
    await callback.answer()


@router.callback_query(F.data.startswith(f"{CARD_EDIT_Q_PREFIX}:"))
async def start_edit_question(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    parts = callback.data.split(":")
    card_id, page = int(parts[-2]), int(parts[-1])

    card = await get_card(session, card_id)
    if card is None:
        await callback.answer("Карточка не найдена.")
        return

    await state.set_state(EditCard.waiting_question)
    await state.update_data(card_id=card_id, page=page)
    await callback.message.answer(f"Текущий вопрос:\n{card.question}\n\nПришли новый текст вопроса:")
    await callback.answer()


@router.callback_query(F.data.startswith(f"{CARD_EDIT_A_PREFIX}:"))
async def start_edit_answer(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    parts = callback.data.split(":")
    card_id, page = int(parts[-2]), int(parts[-1])

    card = await get_card(session, card_id)
    if card is None:
        await callback.answer("Карточка не найдена.")
        return

    await state.set_state(EditCard.waiting_answer)
    await state.update_data(card_id=card_id, page=page)
    await callback.message.answer(
        f"Текущий ответ:\n{card.answer or '—'}\n\nПришли новый текст ответа:"
    )
    await callback.answer()


@router.message(EditCard.waiting_question)
async def process_edit_question(message: Message, state: FSMContext, session: AsyncSession) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст не может быть пустым. Пришли новый вопрос:")
        return

    data = await state.get_data()
    card = await get_card(session, data["card_id"])
    if card is None:
        await state.clear()
        await message.answer("Карточка не найдена.")
        return

    await update_card_question(session, card, text)
    page = data["page"]
    await state.clear()

    await message.answer("✅ Вопрос обновлён.")
    await message.answer(_card_view_text(card), reply_markup=card_view_keyboard(card.id, card.deck_id, page))


@router.message(EditCard.waiting_answer)
async def process_edit_answer(message: Message, state: FSMContext, session: AsyncSession) -> None:
    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст не может быть пустым. Пришли новый ответ:")
        return

    data = await state.get_data()
    card = await get_card(session, data["card_id"])
    if card is None:
        await state.clear()
        await message.answer("Карточка не найдена.")
        return

    await update_card_answer(session, card, text)
    page = data["page"]
    await state.clear()

    await message.answer("✅ Ответ обновлён.")
    await message.answer(_card_view_text(card), reply_markup=card_view_keyboard(card.id, card.deck_id, page))
