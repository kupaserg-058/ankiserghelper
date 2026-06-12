from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

TEST_ANSWER_PREFIX = "test:answer"
TEST_NEXT = "test:next"

OPTION_LABELS = ["A", "B", "C", "D"]


def test_multiple_choice_keyboard(options: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{OPTION_LABELS[i]}. {option}",
                callback_data=f"{TEST_ANSWER_PREFIX}:{i}",
            )
        ]
        for i, option in enumerate(options)
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def test_next_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Следующий →", callback_data=TEST_NEXT)]]
    )
