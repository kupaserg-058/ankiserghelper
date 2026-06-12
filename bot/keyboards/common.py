from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

START_REVIEW = "deck:start_review"
LATER = "deck:later"


def start_review_keyboard(deck_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data=f"{START_REVIEW}:{deck_id}"),
                InlineKeyboardButton(text="⏰ Позже", callback_data=LATER),
            ]
        ]
    )
