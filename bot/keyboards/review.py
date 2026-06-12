from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

NEXT_CARD = "review:next"
ANSWER_PREFIX = "review:answer"

OPTION_LABELS = ["A", "B", "C", "D"]


def multiple_choice_keyboard(card_id: int, options: list[str]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{OPTION_LABELS[i]}. {option}",
                callback_data=f"{ANSWER_PREFIX}:{card_id}:{i}",
            )
        ]
        for i, option in enumerate(options)
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def next_card_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Следующая →", callback_data=NEXT_CARD)]]
    )
