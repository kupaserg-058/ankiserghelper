from aiogram.fsm.state import State, StatesGroup


class CreateDeck(StatesGroup):
    waiting_title = State()
    waiting_material = State()
    waiting_size = State()


class Review(StatesGroup):
    waiting_answer = State()


class Test(StatesGroup):
    waiting_answer = State()


class EditCard(StatesGroup):
    waiting_question = State()
    waiting_answer = State()
