from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

router = Router()

WELCOME_TEXT = (
    "👋 Привет! Я помогу тебе превратить любой материал в флеш-карточки "
    "и выучить его с помощью интервального повторения.\n\n"
    "Команды:\n"
    "/new — создать новую колоду карточек\n"
    "/decks — список твоих колод\n"
    "/review — повторить карточки, которые пора повторить\n"
    "/stats — статистика\n"
    "/help — справка"
)

HELP_TEXT = (
    "📚 <b>Как пользоваться ботом</b>\n\n"
    "1. /new — создай новую колоду: дай ей название и пришли материал "
    "(PDF, ссылку на статью/видео, голосовое сообщение или просто текст).\n"
    "2. Я проанализирую материал через ИИ и создам набор карточек трёх типов:\n"
    "   🔁 flashcard — вопрос/ответ\n"
    "   🔤 multiple_choice — выбор из 4 вариантов\n"
    "   💬 open_question — развёрнутый ответ с проверкой ИИ\n"
    "3. /review — повторяй карточки, которые подошли по расписанию "
    "(алгоритм SM-2 сам подберёт интервалы).\n"
    "4. /decks и /stats — следи за своими колодами и прогрессом.\n"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(WELCOME_TEXT)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)
