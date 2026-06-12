from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.keyboards.main_menu import main_menu_keyboard

router = Router()

WELCOME_TEXT = (
    "👋 Привет! Я помогу тебе превратить любой материал в флеш-карточки "
    "и выучить его с помощью интервального повторения.\n\n"
    "Используй кнопки внизу:\n"
    "📇 Карточки — повторение по расписанию (SM-2)\n"
    "📝 Тесты — проверка знаний по колоде\n"
    "📚 Мои колоды — список колод и создание новой\n"
    "📊 Статистика — твой прогресс"
)

HELP_TEXT = (
    "📚 <b>Как пользоваться ботом</b>\n\n"
    "1. «📚 Мои колоды» → «➕ Новая колода» — дай ей название и пришли материал "
    "(документ, голосовое сообщение, ссылку на статью/видео или просто текст).\n"
    "2. Выбери объём — сколько карточек создать.\n"
    "3. «📇 Карточки» — повторяй карточки по расписанию (алгоритм SM-2 сам подберёт интервалы).\n"
    "4. «📝 Тесты» — проверь себя тестом с вариантами ответов и открытыми вопросами.\n"
    "5. «📊 Статистика» — следи за прогрессом.\n"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(WELCOME_TEXT, reply_markup=main_menu_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)
