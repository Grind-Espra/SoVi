import logging

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

from config import settings
from db import Database

# Ініціалізація
bot = Bot(token=settings.tg_token)
dp = Dispatcher(bot)
db = Database()

logging.basicConfig(level=logging.INFO)
dp.middleware.setup(LoggingMiddleware())

# Реєстрація гравців
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton('Регистрация в игру'))
    await message.answer("Натисніть кнопку нижче, щоб зареєструватися в грі:", reply_markup=markup)


@dp.message_handler(lambda message: message.text == 'Регистрация в игру')
async def register_player(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    db.register_player(chat_id, user_id)
    await message.answer("✅ Ви зареєстровані в грі! Виберіть кількість питань через команду `/set 20`, `/set 30` і т.д.", parse_mode='Markdown')


# Встановлення кількості питань
@dp.message_handler(commands=['set'])
async def set_game_size(message: types.Message):
    chat_id = message.chat.id
    try:
        count = int(message.get_args())
        if count not in [20, 30, 40, 50, 100, 200, 500]:
            raise ValueError
        db.start_game_session(chat_id, count)
        await message.answer(f"🧩 Гру налаштовано на {count} питань. Щоб почати, введіть команду /go")
    except ValueError:
        await message.answer("⚠️ Використання: /set 20 або 30/50/100/200/500")


# Запуск гри
@dp.message_handler(commands=['go'])
async def go_game(message: types.Message):
    chat_id = message.chat.id
    await send_next_question(chat_id)


# Обробка Yes/No
@dp.message_handler(lambda message: message.text.lower() in ['yes', 'no'])
async def handle_answer(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    is_yes = message.text.lower() == 'yes'

    question = db.get_current_question(chat_id)
    if not question:
        await message.answer("❗ Питання не знайдено.")
        return

    question_id = question[0]
    db.record_user_answer(user_id, chat_id, question_id, is_yes)

    # Всі гравці відповіли?
    if db.have_all_players_answered(chat_id, question_id):
        db.advance_question(chat_id)
        await send_next_question(chat_id)


# Зупинка гри
@dp.message_handler(commands=['stop'])
async def stop_game(message: types.Message):
    chat_id = message.chat.id
    db.stop_game_session(chat_id)
    await message.answer("🛑 Гру зупинено.", reply_markup=ReplyKeyboardRemove())


# Відправка наступного питання
async def send_next_question(chat_id: int):
    if db.is_game_finished(chat_id):
        await send_results(chat_id)
        db.stop_game_session(chat_id)
        return

    question = db.get_current_question(chat_id)
    if question:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Yes", "No")
        await bot.send_message(chat_id, f"🧠 {question[1]}", reply_markup=markup)
    else:
        await bot.send_message(chat_id, "❗ Питання закінчились.", reply_markup=ReplyKeyboardRemove())


# Вивід статистики
async def send_results(chat_id: int):
    results = db.get_statistics(chat_id)
    if not results:
        await bot.send_message(chat_id, "Немає відповідей для статистики.")
        return

    text = "📊 *Результати гри:*\n\n"
    for i, (question, yes, no) in enumerate(results, 1):
        total = yes + no or 1
        yes_pct = round(yes * 100 / total)
        no_pct = 100 - yes_pct
        text += f"{i}. {question}\n✅ Так — {yes_pct}% | ❌ Ні — {no_pct}%\n\n"

    await bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=ReplyKeyboardRemove())


# Запуск
if __name__ == '__main__':
    executor.start_polling(dp)
