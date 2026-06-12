from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.common import LATER, start_review_keyboard
from bot.keyboards.decks import (
    DECK_DELETE_CANCEL,
    DECK_DELETE_CONFIRM_PREFIX,
    DECK_DELETE_PREFIX,
    DECK_INFO_PREFIX,
    NEW_DECK,
    SIZE_CARD_COUNTS,
    SIZE_PREFIX,
    deck_actions_keyboard,
    deck_delete_confirm_keyboard,
    deck_size_keyboard,
    decks_list_keyboard,
)
from bot.keyboards.main_menu import BTN_DECKS
from bot.logger import get_logger
from bot.models import SourceType, User
from bot.repositories.card_repo import bulk_create_cards, count_cards, init_reviews_for_cards
from bot.repositories.deck_repo import create_deck, delete_deck, get_deck, list_decks_with_card_count
from bot.services import gemini, parser
from bot.states import CreateDeck

logger = get_logger(__name__)

router = Router()


@router.message(F.text == BTN_DECKS)
async def show_decks(message: Message, session: AsyncSession, db_user: User) -> None:
    decks = await list_decks_with_card_count(session, db_user.id)
    if not decks:
        await message.answer(
            "У тебя пока нет колод. Создай первую:",
            reply_markup=decks_list_keyboard([], action_prefix=DECK_INFO_PREFIX),
        )
        return

    lines = ["📚 <b>Твои колоды:</b>"]
    for deck, count in decks:
        lines.append(f"• {deck.title} ({count} карточек)")

    await message.answer(
        "\n".join(lines), reply_markup=decks_list_keyboard(decks, action_prefix=DECK_INFO_PREFIX)
    )


@router.callback_query(F.data.startswith(f"{DECK_INFO_PREFIX}:"))
async def show_deck_info(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    deck_id = int(callback.data.split(":")[-1])
    deck = await get_deck(session, deck_id, db_user.id)
    if deck is None:
        await callback.answer("Колода не найдена.")
        return

    count = await count_cards(session, deck.id)
    await callback.message.answer(
        f"📚 «{deck.title}» — {count} карточек",
        reply_markup=deck_actions_keyboard(deck.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(f"{DECK_DELETE_PREFIX}:"))
async def confirm_delete_deck(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    deck_id = int(callback.data.split(":")[-1])
    deck = await get_deck(session, deck_id, db_user.id)
    if deck is None:
        await callback.answer("Колода не найдена.")
        return

    await callback.message.edit_text(
        f"Удалить колоду «{deck.title}» вместе со всеми карточками и прогрессом?",
        reply_markup=deck_delete_confirm_keyboard(deck.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith(f"{DECK_DELETE_CONFIRM_PREFIX}:"))
async def do_delete_deck(callback: CallbackQuery, session: AsyncSession, db_user: User) -> None:
    deck_id = int(callback.data.split(":")[-1])
    deck = await get_deck(session, deck_id, db_user.id)
    if deck is None:
        await callback.answer("Колода не найдена.")
        return

    title = deck.title
    await delete_deck(session, deck)
    await callback.message.edit_text(f"🗑 Колода «{title}» удалена.")
    await callback.answer()


@router.callback_query(F.data == DECK_DELETE_CANCEL)
async def cancel_delete_deck(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Отменено.")
    await callback.answer()


@router.callback_query(F.data == NEW_DECK)
async def start_new_deck(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CreateDeck.waiting_title)
    await callback.message.answer("Как назовём новую колоду?")
    await callback.answer()


@router.message(CreateDeck.waiting_title)
async def process_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title:
        await message.answer("Название не может быть пустым. Введи название колоды:")
        return

    await state.update_data(title=title)
    await state.set_state(CreateDeck.waiting_material)
    await message.answer(
        "Пришлите материал: документ, голосовое сообщение, видео/ссылку или просто текст."
    )


@router.message(CreateDeck.waiting_material)
async def process_material(message: Message, state: FSMContext) -> None:
    try:
        material = await _extract_material(message)
    except Exception:
        logger.exception("material_extraction_failed")
        await message.answer(
            "❌ Не удалось распознать материал. Пришлите документ, голосовое, ссылку или текст."
        )
        return

    await state.update_data(material=material)
    await state.set_state(CreateDeck.waiting_size)
    await message.answer("Сколько карточек создать?", reply_markup=deck_size_keyboard())


@router.callback_query(CreateDeck.waiting_size, F.data.startswith(f"{SIZE_PREFIX}:"))
async def process_size_choice(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    size_key = callback.data
    target_count = SIZE_CARD_COUNTS[size_key]

    data = await state.get_data()
    title = data["title"]
    material = data["material"]

    await callback.message.edit_text("⏳ Анализирую материал и создаю карточки...")
    await callback.answer()

    try:
        cards = await _generate_cards(material, target_count)
    except Exception:
        logger.exception("card_generation_failed")
        await callback.message.edit_text(
            "❌ Не удалось обработать материал. Попробуй ещё раз через «📚 Мои колоды»."
        )
        await state.clear()
        return
    finally:
        await _cleanup_material(material)

    if not cards:
        await callback.message.edit_text(
            "❌ Не удалось создать карточки из этого материала. Попробуй другой материал."
        )
        await state.clear()
        return

    deck = await create_deck(session, db_user.id, title, material["source_type"])
    db_cards = await bulk_create_cards(session, deck.id, cards)
    await init_reviews_for_cards(session, db_user.id, db_cards)

    await callback.message.edit_text(
        f"✅ Создано {len(db_cards)} карточек в колоде «{title}»!\n\nНачать повторение?",
        reply_markup=start_review_keyboard(deck.id),
    )
    await state.clear()


async def _extract_material(message: Message) -> dict:
    """Detect the attachment type and prepare a material descriptor for generation."""
    if message.document is not None:
        if message.document.mime_type != "application/pdf" and not (
            message.document.file_name or ""
        ).lower().endswith(".pdf"):
            raise ValueError(f"unsupported document type: {message.document.mime_type}")

        local_path = parser.temp_path(".pdf")
        await message.bot.download(message.document, destination=local_path)
        return {"kind": "pdf", "path": local_path, "source_type": SourceType.pdf}

    if message.voice is not None:
        local_path = parser.temp_path(".ogg")
        await message.bot.download(message.voice, destination=local_path)
        return {"kind": "audio", "path": local_path, "source_type": SourceType.audio}

    text = (message.text or message.caption or "").strip()
    if not text:
        raise ValueError("empty message")

    url = parser.extract_url(text)
    if url:
        if parser.is_video_url(url):
            audio_path = await parser.download_audio(url)
            return {"kind": "audio", "path": audio_path, "source_type": SourceType.video}

        page_text = await parser.fetch_url_text(url)
        if not page_text.strip():
            raise ValueError("empty url content")
        return {"kind": "text", "text": page_text, "source_type": SourceType.url}

    return {"kind": "text", "text": text, "source_type": SourceType.text}


async def _generate_cards(material: dict, target_count: int) -> list[gemini.GeneratedCard]:
    if material["kind"] == "text":
        return await gemini.generate_cards(text=material["text"], target_count=target_count)

    if material["kind"] == "pdf":
        local_path = material["path"]
        if parser.is_pdf_within_inline_limit(local_path):
            gemini_file = await gemini.upload_file(local_path, "application/pdf")
            material["gemini_file"] = gemini_file
            return await gemini.generate_cards(file=gemini_file, target_count=target_count)

        text = parser.extract_pdf_text(local_path)
        if not text.strip():
            raise ValueError("empty pdf text")
        return await gemini.generate_cards(text=text, target_count=target_count)

    if material["kind"] == "audio":
        mime_type = "audio/ogg" if material["source_type"] == SourceType.audio else "audio/mp3"
        gemini_file = await gemini.upload_file(material["path"], mime_type)
        material["gemini_file"] = gemini_file
        return await gemini.generate_cards(file=gemini_file, target_count=target_count)

    raise ValueError(f"unknown material kind: {material['kind']}")


async def _cleanup_material(material: dict) -> None:
    local_path = material.get("path")
    if local_path:
        parser.cleanup(local_path)

    gemini_file = material.get("gemini_file")
    if gemini_file is not None:
        await gemini.delete_file(gemini_file.name)


@router.callback_query(F.data == LATER)
async def process_later(callback: CallbackQuery) -> None:
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Хорошо, когда будешь готов — нажми «📇 Карточки»")
