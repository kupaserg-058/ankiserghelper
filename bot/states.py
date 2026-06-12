from aiogram.fsm.state import State, StatesGroup


class CreateDeck(StatesGroup):
    waiting_title = State()
    waiting_source = State()
    waiting_material = State()


class Review(StatesGroup):
    waiting_answer = State()
