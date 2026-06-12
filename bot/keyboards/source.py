from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

SOURCE_PDF = "source:pdf"
SOURCE_URL = "source:url"
SOURCE_VIDEO = "source:video"
SOURCE_VOICE = "source:voice"
SOURCE_TEXT = "source:text"


def source_selection_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📄 PDF", callback_data=SOURCE_PDF)],
            [InlineKeyboardButton(text="🔗 URL", callback_data=SOURCE_URL)],
            [InlineKeyboardButton(text="📺 Видео/YouTube", callback_data=SOURCE_VIDEO)],
            [InlineKeyboardButton(text="🎙 Голосовое", callback_data=SOURCE_VOICE)],
            [InlineKeyboardButton(text="✏️ Текст", callback_data=SOURCE_TEXT)],
        ]
    )
