import logging

from aiogram import Bot, Dispatcher
from aiogram import types, executor
from aiogram.utils import markdown as md
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import KeyboardButton, ReplyKeyboardRemove

from db import Database
from config import settings


# Инициализация бота и диспетчера
bot = Bot(token=settings.tg_token)
dp = Dispatcher(bot)
db = Database()
logging.basicConfig(level=logging.INFO)
dp.middleware.setup(LoggingMiddleware())


def load_questions_from_file() -> list[str]:  # Лучше сразу приучивайся аннотациям :)
    """Функция для загрузки вопросов из файла"""
    questions_fp = 'YorN.txt'
    _questions = []  # Локальная переменная чаще всего не должна совпадать с именем глобальной
    with open(questions_fp, 'r') as file:
        for line in file:  # Это тоже можно прописать в генератор ))
            _questions.extend([question_text for question_text, _ in line.strip().split(' (Yes/No)')])

    return _questions


@dp.message_handler(commands=['start'])
async def register_player(message: types.Message):
    """Обработчик команды /start"""  # Хотя вообще это лишнее объяснение))))
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item = types.KeyboardButton('Регистрация в игру')
    markup.add(item)
    await message.answer("Для регистрации в игре нажмите кнопку ниже:", reply_markup=markup)


@dp.message_handler(lambda message: message.text == 'Регистрация в игру')
async def start_game_registration(message: types.Message):
    """Обработчик кнопки 'Регистрация в игре'"""  # Хотя вообще это лишнее объяснение))))
    await message.answer("Регистрация в игре открыта на 2 минуты.\n"
                         "Для запуска игры введите /go.")


@dp.message_handler(commands=['go'])
async def start_game(message: types.Message):
    """Обработчик для запуска игры"""
    user_data.clear()  # Очищаем предыдущие данные об игре
    await send_question(message.chat.id)  # Отправляем первый вопрос


async def send_question(user_id):
    question = db.get_next_question()
    if question:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton('Yes'), KeyboardButton('No'))
        user_data[user_id] = {'question_id': question[0]}
        await bot.send_message(user_id, question[1], reply_markup=markup)
    else:
        await bot.send_message(user_id, "Вопросы закончились. Игра завершена.", reply_markup=ReplyKeyboardRemove())


async def dp_question_answer(message: types.Message, question_type: bool):
    """Base-обработчик ответов"""
    user_id = message.chat.id
    question_id = user_data.get(user_id, {}).get('question_id')

    if question_id:
        db.save_answer(question_id, question_type)

    await send_question(user_id)


@dp.message_handler(lambda message: message.text.lower() == 'yes')
async def handle_yes(message: types.Message):
    """Обработчик, принимающий положительный ответ на вопрос"""
    await dp_question_answer(message, True)


@dp.message_handler(lambda message: message.text.lower() == 'no')
async def handle_no(message: types.Message):
    """Обработчик, принимающий отрицательный ответ на вопрос"""
    await dp_question_answer(message, False)


if __name__ == '__main__':
    user_data = {}
    questions = load_questions_from_file()
    # save_questions_to_db(questions)

    executor.start_polling(dp)
