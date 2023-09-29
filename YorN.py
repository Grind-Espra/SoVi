import asyncio
import aiogram.utils.markdown as md
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ParseMode, KeyboardButton, ReplyKeyboardRemove
import logging
import psycopg2

# Подключение к базе данных PostgreSQL
conn = psycopg2.connect(dbname='your_db_name', user='R', password='your_db_password', host='your_db_host')
cursor = conn.cursor()

API_TOKEN = 'YOUR_API_TOKEN'

# Инициализация бота и диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)
dp.middleware.setup(LoggingMiddleware())

# Функция для загрузки вопросов из файла
def load_questions_from_file(file_path):
    questions = []
    with open(file_path, 'r') as file:
        for line in file:
            question_text, _ = line.strip().split(' (Yes/No)')
            questions.append(question_text)
    return questions

# Функция для сохранения ответа в базу данных
def save_answer(question_id, is_yes):
    cursor.execute("UPDATE questions SET {} = {} + 1 WHERE id = %s".format('yes_count' if is_yes else 'no_count'), (question_id,))
    conn.commit()

# Функция для получения следующего вопроса из базы данных
def get_next_question():
    cursor.execute("SELECT id, question_text FROM questions WHERE id NOT IN (SELECT question_id FROM user_answers) LIMIT 1")
    return cursor.fetchone()

# Обработчик команды "/start"
@dp.message_handler(commands=['start'])
async def register_player(message: types.Message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    item = types.KeyboardButton('Регистрация в игру')
    markup.add(item)
    await message.answer("Для регистрации в игре нажмите кнопку ниже:", reply_markup=markup)

# Обработчик кнопки "Регистрация в игре"
@dp.message_handler(lambda message: message.text == 'Регистрация в игру')
async def start_game_registration(message: types.Message):
    await message.answer("Регистрация в игре открыта на 2 минуты.\n"
                         "Для запуска игры введите /go.")

# Обработчик команды "/go" для запуска игры
@dp.message_handler(commands=['go'])
async def start_game(message: types.Message):
    # Очищаем предыдущие данные об игре
    user_data.clear()
    # Отправляем первый вопрос
    await send_question(message.chat.id)

async def send_question(user_id):
    question = get_next_question()
    if question:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton('Yes'), KeyboardButton('No'))
        user_data[user_id] = {'question_id': question[0]}
        await bot.send_message(user_id, question[1], reply_markup=markup)
    else:
        await bot.send_message(user_id, "Вопросы закончились. Игра завершена.", reply_markup=ReplyKeyboardRemove())

# Обработчик ответа "Yes"
@dp.message_handler(lambda message: message.text.lower() == 'yes')
async def handle_yes(message: types.Message):
    user_id = message.chat.id
    question_id = user_data.get(user_id, {}).get('question_id')

    if question_id:
        save_answer(question_id, True)

    await send_question(user_id)

# Обработчик ответа "No"
@dp.message_handler(lambda message: message.text.lower() == 'no')
async def handle_no(message: types.Message):
    user_id = message.chat.id
    question_id = user_data.get(user_id, {}).get('question_id')

    if question_id:
        save_answer(question_id, False)

    await send_question(user_id)

if __name__ == '__main__':
    user_data = {}
    questions_file_path = 'YorN.txt'
    questions = load_questions_from_file(questions_file_path)
    save_questions_to_db(questions)

    loop = asyncio.get_event_loop()
    loop.create_task(dp.start_polling())
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.stop()
        loop.run_until_complete(dp.storage.close())
        loop.run_until_complete(dp.storage.wait_closed())