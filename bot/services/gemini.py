import asyncio
import time
from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from bot.config import settings
from bot.logger import get_logger

logger = get_logger(__name__)

client = genai.Client(api_key=settings.google_api_key)


class GeneratedCard(BaseModel):
    question: str
    answer: str | None


class GeneratedTestQuestion(BaseModel):
    question_type: Literal["multiple_choice", "open_question"]
    question: str
    answer: str | None
    options: list[str] | None
    correct_index: int | None


class FlashcardCheckResult(BaseModel):
    score: int
    verdict: Literal["correct", "partial", "incorrect"]
    explanation: str


class OpenQuestionCheckResult(BaseModel):
    score: int
    feedback: str
    missed_points: list[str]


GENERATE_CARDS_PROMPT = """\
Ты — ассистент для создания обучающих флеш-карточек по материалу.

Проанализируй приложенный материал и создай набор флеш-карточек для изучения.

Правила:
- Создай примерно {target_count} флеш-карточек по материалу.
- Язык карточек должен совпадать с языком исходного материала.
- Фокусируйся на ключевых концепциях и идеях, а не на второстепенных деталях.
- question — вопрос/термин, answer — краткий эталонный ответ.

Верни результат строго в виде JSON-массива карточек согласно схеме.
"""

GENERATE_TEST_PROMPT = """\
Ты — ассистент для создания проверочных тестов на основе флеш-карточек.

Вот список флеш-карточек (вопрос/ответ) из колоды:

{cards_text}

Создай на их основе набор тестовых вопросов:
- Распредели вопросы по типам примерно так: 60% multiple_choice, 40% open_question.
- Язык вопросов должен совпадать с языком исходных карточек.
- Для multiple_choice: question — вопрос, options — ровно 4 варианта ответа,
  correct_index — индекс (0-3) правильного варианта, остальные три варианта
  должны быть правдоподобными, но неверными. Поле answer оставь пустым.
- Для open_question: question — вопрос, требующий развёрнутого ответа,
  answer — эталонный развёрнутый ответ для последующей проверки.

Верни результат строго в виде JSON-массива вопросов согласно схеме.
"""

CHECK_FLASHCARD_PROMPT = """\
Ты проверяешь ответ пользователя на флеш-карточку.

Вопрос: {question}
Эталонный ответ: {reference}
Ответ пользователя: {user_answer}

Оцени ответ пользователя по шкале 0-5, где:
5 — полностью верный ответ
3-4 — в целом верный, но неполный
1-2 — частично верный, есть существенные ошибки
0 — неверный или отсутствует

Верни JSON со score (0-5), verdict ("correct"|"partial"|"incorrect")
и кратким explanation на языке вопроса.
"""

CHECK_OPEN_QUESTION_PROMPT = """\
Ты проверяешь развёрнутый ответ пользователя на открытый вопрос.

Вопрос: {question}
Эталонный ответ: {reference}
Ответ пользователя: {user_answer}

Оцени ответ пользователя по шкале 0-5, где:
5 — полный и точный ответ, раскрывающий все ключевые аспекты
3-4 — в целом верный ответ, но упущены некоторые аспекты
1-2 — частично верный ответ с существенными пробелами
0 — неверный или отсутствующий ответ

Верни JSON со score (0-5), feedback (краткий комментарий на языке вопроса)
и missed_points (список упущенных ключевых моментов, может быть пустым).
"""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def _generate_content(contents: list, response_schema) -> str:
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
        ),
    )
    return response.text


async def generate_cards(
    text: str | None = None,
    file: types.File | None = None,
    target_count: int = 20,
) -> list[GeneratedCard]:
    """Generate flashcards either from raw text or an uploaded Gemini file."""
    contents: list = [GENERATE_CARDS_PROMPT.format(target_count=target_count)]
    if file is not None:
        contents.append(file)
    if text is not None:
        contents.append(text)

    raw = await asyncio.to_thread(_generate_content, contents, list[GeneratedCard])
    return _parse_list(raw, GeneratedCard)


async def generate_test_questions(cards: list[tuple[str, str]]) -> list[GeneratedTestQuestion]:
    """Generate multiple_choice/open_question test items from a deck's flashcards."""
    cards_text = "\n".join(f"- Вопрос: {q}\n  Ответ: {a}" for q, a in cards)
    prompt = GENERATE_TEST_PROMPT.format(cards_text=cards_text)
    raw = await asyncio.to_thread(_generate_content, [prompt], list[GeneratedTestQuestion])
    return _parse_list(raw, GeneratedTestQuestion)


async def check_flashcard(question: str, reference: str, user_answer: str) -> FlashcardCheckResult:
    prompt = CHECK_FLASHCARD_PROMPT.format(
        question=question, reference=reference, user_answer=user_answer
    )
    raw = await asyncio.to_thread(_generate_content, [prompt], FlashcardCheckResult)
    return FlashcardCheckResult.model_validate_json(raw)


async def check_open_question(
    question: str, reference: str, user_answer: str
) -> OpenQuestionCheckResult:
    prompt = CHECK_OPEN_QUESTION_PROMPT.format(
        question=question, reference=reference, user_answer=user_answer
    )
    raw = await asyncio.to_thread(_generate_content, [prompt], OpenQuestionCheckResult)
    return OpenQuestionCheckResult.model_validate_json(raw)


def _parse_list[T: BaseModel](raw: str, model: type[T]) -> list[T]:
    import json

    data = json.loads(raw)
    return [model.model_validate(item) for item in data]


def _upload_file_sync(path: str, mime_type: str) -> types.File:
    file = client.files.upload(file=path, config={"mime_type": mime_type})
    while file.state == types.FileState.PROCESSING:
        time.sleep(2)
        file = client.files.get(name=file.name)
    if file.state == types.FileState.FAILED:
        raise RuntimeError(f"Gemini file upload failed: {file.name}")
    return file


def _delete_file_sync(name: str) -> None:
    client.files.delete(name=name)


async def upload_file(path: str, mime_type: str) -> types.File:
    return await asyncio.to_thread(_upload_file_sync, path, mime_type)


async def delete_file(name: str) -> None:
    try:
        await asyncio.to_thread(_delete_file_sync, name)
    except Exception:
        logger.warning("gemini_file_delete_failed", name=name)
