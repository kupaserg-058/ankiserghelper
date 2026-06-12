from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.common import LATER, start_review_keyboard
from bot.keyboards.source import (
    SOURCE_PDF,
    SOURCE_TEXT,
    SOURCE_URL,
    SOURCE_VIDEO,
    SOURCE_VOICE,
    source_selection_keyboard,
)
from bot.logger import get_logger
from bot.models import SourceType, User
from bot.repositories.card_repo import bulk_create_cards, init_reviews_for_cards
from bot.repositories.deck_repo import create_deck, list_decks_with_card_count
from bot.services import gemini, parser
from bot.states import CreateDeck

logger = get_logger(__name__)

router = Router()

SOURCE_TYPE_MAP = {
    SOURCE_PDF: SourceType.pdf,
    SOURCE_URL: SourceType.url,
    SOURCE_VIDEO: SourceType.video,
    SOURCE_VOICE: SourceType.audio,
    SOURCE_TEXT: SourceType.text,
}

SOURCE_PROMPTS = {
    SOURCE_PDF: "📄 Пришли PDF-файл с материалом.",
    SOURCE_URL: "🔗 Пришли ссылку на статью или видео.",
    SOURCE_VIDEO: "📺 Пришли ссылку на видео (YouTube и др.) — я скачаю и расшифрую аудио.",
    SOURCE_VOICE: "🎙 Пришли голосовое сообщение.",
    SOURCE_TEXT: "✏️ Пришли текст материала.",
}


@router.message(Command("new"))
async def cmd_new(message: Message, state: FSMContext) -> None:
    await state.set_state(CreateDeck.waiting_title)
    await message.answer("Как назовём новую колоду?")


@router.message(CreateDeck.waiting_title)
async def process_title(message: Message, state: FSMContext) -> None:
    title = (message.text or "").strip()
    if not title:
        await message.answer("Название не может быть пустым. Введи название колоды:")
        return

    await state.update_data(title=title)
    await state.set_state(CreateDeck.waiting_source)
    await message.answer("Откуда возьмём материал?", reply_markup=source_selection_keyboard())


@router.callback_query(CreateDeck.waiting_source, F.data.in_(SOURCE_TYPE_MAP.keys()))
async def process_source_choice(callback: CallbackQuery, state: FSMContext) -> None:
    source_key = callback.data
    await state.update_data(source_key=source_key)
    await state.set_state(CreateDeck.waiting_material)
    await callback.message.edit_text(SOURCE_PROMPTS[source_key])
    await callback.answer()


@router.message(CreateDeck.waiting_material)
async def process_material(
    message: Message, state: FSMContext, session: AsyncSession, db_user: User
) -> None:
    data = await state.get_data()
    source_key = data.get("source_key")
    title = data["title"]

    if source_key not in SOURCE_TYPE_MAP:
        await message.answer("Сначала выбери источник материала.")
        return

    status_message = await message.answer("⏳ Анализирую материал и создаю карточки...")

    try:
        cards = await _generate_cards_for_source(message, source_key)
    except Exception:
        logger.exception("card_generation_failed", source_key=source_key)
        await status_message.edit_text(
            "❌ Не удалось обработать материал. Попробуй ещё раз с /new."
        )
        await state.clear()
        return

    if not cards:
        await status_message.edit_text(
            "❌ Не удалось создать карточки из этого материала. Попробуй другой источник."
        )
        await state.clear()
        return

    deck = await create_deck(session, db_user.id, title, SOURCE_TYPE_MAP[source_key])
    db_cards = await bulk_create_cards(session, deck.id, cards)
    await init_reviews_for_cards(session, db_user.id, db_cards)

    await status_message.edit_text(
        f"✅ Создано {len(db_cards)} карточек в колоде «{title}»!\n\nНачать повторение?",
        reply_markup=start_review_keyboard(deck.id),
    )
    await state.clear()


async def _generate_cards_for_source(message: Message, source_key: str) -> list[gemini.GeneratedCard]:
    if source_key == SOURCE_TEXT:
        text = message.text or message.caption or ""
        if not text.strip():
            raise ValueError("empty text material")
        return await gemini.generate_cards(text=text)

    if source_key == SOURCE_URL:
        url = (message.text or "").strip()
        text = await parser.fetch_url_text(url)
        if not text.strip():
            raise ValueError("empty url content")
        return await gemini.generate_cards(text=text)

    if source_key == SOURCE_PDF:
        return await _generate_from_pdf(message)

    if source_key == SOURCE_VIDEO:
        return await _generate_from_video_url(message)

    if source_key == SOURCE_VOICE:
        return await _generate_from_voice(message)

    raise ValueError(f"unknown source key: {source_key}")


async def _generate_from_pdf(message: Message) -> list[gemini.GeneratedCard]:
    if message.document is None:
        raise ValueError("expected a document")

    local_path = parser.temp_path(".pdf")
    await message.bot.download(message.document, destination=local_path)

    gemini_file = None
    try:
        if parser.is_pdf_within_inline_limit(local_path):
            gemini_file = await gemini.upload_file(local_path, "application/pdf")
            return await gemini.generate_cards(file=gemini_file)

        text = parser.extract_pdf_text(local_path)
        if not text.strip():
            raise ValueError("empty pdf text")
        return await gemini.generate_cards(text=text)
    finally:
        parser.cleanup(local_path)
        if gemini_file is not None:
            await gemini.delete_file(gemini_file.name)


async def _generate_from_video_url(message: Message) -> list[gemini.GeneratedCard]:
    url = (message.text or "").strip()
    audio_path = await parser.download_audio(url)

    gemini_file = None
    try:
        gemini_file = await gemini.upload_file(audio_path, "audio/mp3")
        return await gemini.generate_cards(file=gemini_file)
    finally:
        parser.cleanup(audio_path)
        if gemini_file is not None:
            await gemini.delete_file(gemini_file.name)


async def _generate_from_voice(message: Message) -> list[gemini.GeneratedCard]:
    if message.voice is None:
        raise ValueError("expected a voice message")

    local_path = parser.temp_path(".ogg")
    await message.bot.download(message.voice, destination=local_path)

    gemini_file = None
    try:
        gemini_file = await gemini.upload_file(local_path, "audio/ogg")
        return await gemini.generate_cards(file=gemini_file)
    finally:
        parser.cleanup(local_path)
        if gemini_file is not None:
            await gemini.delete_file(gemini_file.name)


@router.callback_query(F.data == LATER)
async def process_later(callback: CallbackQuery) -> None:
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Хорошо, когда будешь готов — используй /review")


@router.message(Command("decks"))
async def cmd_decks(message: Message, session: AsyncSession, db_user: User) -> None:
    decks = await list_decks_with_card_count(session, db_user.id)
    if not decks:
        await message.answer("У тебя пока нет колод. Создай первую с помощью /new")
        return

    lines = ["📚 <b>Твои колоды:</b>\n"]
    for deck, count in decks:
        lines.append(f"#{deck.id} — {deck.title} ({count} карточек)")

    lines.append("\nПовторить конкретную колоду: /review <id>")
    await message.answer("\n".join(lines))
