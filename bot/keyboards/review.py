from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

SHOW_ANSWER = "review:show_answer"
GRADE_AGAIN = "review:grade:again"
GRADE_KNEW = "review:grade:knew"


def show_answer_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="👁 Показать ответ", callback_data=SHOW_ANSWER)]]
    )


def grade_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="❌ Не знал", callback_data=GRADE_AGAIN),
                InlineKeyboardButton(text="✅ Знал", callback_data=GRADE_KNEW),
            ]
        ]
    )
