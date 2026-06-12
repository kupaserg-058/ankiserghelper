from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.models import Card, Deck

NEW_DECK = "deck:new"
DECK_PREFIX = "deck:select"
DECK_INFO_PREFIX = "deck:info"
TEST_DECK_PREFIX = "test:deck"
SIZE_PREFIX = "deck:size"
DECK_DELETE_PREFIX = "deck:delete"
DECK_DELETE_CONFIRM_PREFIX = "deck:delete_confirm"
DECK_DELETE_CANCEL = "deck:delete_cancel"

CARDS_LIST_PREFIX = "cards:list"
CARD_VIEW_PREFIX = "cards:view"
CARD_EDIT_Q_PREFIX = "cards:edit_q"
CARD_EDIT_A_PREFIX = "cards:edit_a"
CARD_DELETE_PREFIX = "cards:delete"
CARD_DELETE_CONFIRM_PREFIX = "cards:delete_confirm"

CARDS_PAGE_SIZE = 8

SIZE_SMALL = f"{SIZE_PREFIX}:small"
SIZE_MEDIUM = f"{SIZE_PREFIX}:medium"
SIZE_LARGE = f"{SIZE_PREFIX}:large"

SIZE_LABELS = {
    SIZE_SMALL: "Малое (~20)",
    SIZE_MEDIUM: "Среднее (~40)",
    SIZE_LARGE: "Большое (~60+)",
}

SIZE_CARD_COUNTS = {
    SIZE_SMALL: 20,
    SIZE_MEDIUM: 40,
    SIZE_LARGE: 60,
}


def decks_list_keyboard(decks: list[tuple[Deck, int]], action_prefix: str) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{deck.title} ({count} карточек)",
                callback_data=f"{action_prefix}:{deck.id}",
            )
        ]
        for deck, count in decks
    ]
    rows.append([InlineKeyboardButton(text="➕ Новая колода", callback_data=NEW_DECK)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def deck_size_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=key)]
            for key, label in SIZE_LABELS.items()
        ]
    )


def deck_actions_keyboard(deck_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📇 Повторить", callback_data=f"{DECK_PREFIX}:{deck_id}")],
            [InlineKeyboardButton(text="📝 Тест", callback_data=f"{TEST_DECK_PREFIX}:{deck_id}")],
            [InlineKeyboardButton(text="📋 Список карточек", callback_data=f"{CARDS_LIST_PREFIX}:{deck_id}:0")],
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"{DECK_DELETE_PREFIX}:{deck_id}")],
        ]
    )


def cards_list_keyboard(
    cards: list[Card], deck_id: int, page: int, total: int
) -> InlineKeyboardMarkup:
    rows = []
    for card in cards:
        title = card.question.strip().replace("\n", " ")
        if len(title) > 40:
            title = title[:40] + "…"
        rows.append(
            [InlineKeyboardButton(text=title, callback_data=f"{CARD_VIEW_PREFIX}:{card.id}:{page}")]
        )

    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton(text="⬅️", callback_data=f"{CARDS_LIST_PREFIX}:{deck_id}:{page - 1}")
        )
    if (page + 1) * CARDS_PAGE_SIZE < total:
        nav.append(
            InlineKeyboardButton(text="➡️", callback_data=f"{CARDS_LIST_PREFIX}:{deck_id}:{page + 1}")
        )
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="⬅️ К колоде", callback_data=f"{DECK_INFO_PREFIX}:{deck_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def card_view_keyboard(card_id: int, deck_id: int, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Изменить вопрос", callback_data=f"{CARD_EDIT_Q_PREFIX}:{card_id}:{page}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Изменить ответ", callback_data=f"{CARD_EDIT_A_PREFIX}:{card_id}:{page}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Удалить карточку", callback_data=f"{CARD_DELETE_PREFIX}:{card_id}:{page}"
                )
            ],
            [InlineKeyboardButton(text="⬅️ К списку", callback_data=f"{CARDS_LIST_PREFIX}:{deck_id}:{page}")],
        ]
    )


def card_delete_confirm_keyboard(card_id: int, deck_id: int, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, удалить",
                    callback_data=f"{CARD_DELETE_CONFIRM_PREFIX}:{card_id}:{page}",
                ),
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"{CARD_VIEW_PREFIX}:{card_id}:{page}"),
            ]
        ]
    )


def deck_delete_confirm_keyboard(deck_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Да, удалить", callback_data=f"{DECK_DELETE_CONFIRM_PREFIX}:{deck_id}"
                ),
                InlineKeyboardButton(text="❌ Отмена", callback_data=DECK_DELETE_CANCEL),
            ]
        ]
    )
