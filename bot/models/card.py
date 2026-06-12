import enum

from sqlalchemy import ForeignKey, Integer, JSON, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from bot.models.base import Base


class CardType(str, enum.Enum):
    flashcard = "flashcard"
    multiple_choice = "multiple_choice"
    open_question = "open_question"


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    deck_id: Mapped[int] = mapped_column(ForeignKey("decks.id", ondelete="CASCADE"))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    card_type: Mapped[CardType] = mapped_column(SAEnum(CardType, name="card_type"))
    options: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    correct_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
