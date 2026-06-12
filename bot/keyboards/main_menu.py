from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

BTN_CARDS = "📇 Карточки"
BTN_TESTS = "📝 Тесты"
BTN_DECKS = "📚 Мои колоды"
BTN_STATS = "📊 Статистика"


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_CARDS), KeyboardButton(text=BTN_TESTS)],
            [KeyboardButton(text=BTN_DECKS), KeyboardButton(text=BTN_STATS)],
        ],
        resize_keyboard=True,
    )
