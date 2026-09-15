from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats

from .config import Settings
from .db import init_db
from .game_manager import GameManager
from .handlers import game, start, premium

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')


async def main():
    settings=Settings.from_env()
    root=Path(__file__).resolve().parent.parent
    qpath=root/'data'/'questions.json'
    await init_db(settings.db_path,str(qpath))
    bot=Bot(token=settings.bot_token,default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp=Dispatcher(); manager=GameManager(bot,settings)
    dp['settings']=settings; dp['manager']=manager
    dp.include_router(start.router); dp.include_router(game.router); dp.include_router(premium.router)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await manager.restore_active_games()
        try:
            await bot.set_my_name(name='SoVi l Sueños o vida')
            await bot.set_my_short_description(short_description='SoVi l Sueños o vida — вопросы для компании, где мнение иногда интереснее ответа.')
            await bot.set_my_description(description='SoVi l Sueños o vida — социальная игра для компаний. Вы отвечаете «Да» или «Нет», а затем узнаёте мнение всей компании.')
            private=[
                BotCommand(command='start',description='Главное меню'),
                BotCommand(command='help',description='Как играть'),
                BotCommand(command='modes',description='Режимы игры'),
                BotCommand(command='settings',description='Настройки группы'),
                BotCommand(command='myachv',description='Мои достижения'),
                BotCommand(command='missingachv',description='Неоткрытые достижения'),
                BotCommand(command='stats',description='Моя статистика'),
                BotCommand(command='top',description='Рейтинг'),
                BotCommand(command='premium',description='Premium для группы'),
            ]
            group=[
                BotCommand(command='game',description='Начать игру'),
                BotCommand(command='startgame',description='Запустить классическую игру'),
                BotCommand(command='startclassic',description='Классический режим'),
                BotCommand(command='startdilemma',description='Сложная дилемма'),
                BotCommand(command='startchaos',description='Хаос'),
                BotCommand(command='startromance',description='Романтика'),
                BotCommand(command='startbook',description='Книголюб'),
                BotCommand(command='starthorror',description='Ночная смена'),
                BotCommand(command='go',description='Запустить набранную игру'),
                BotCommand(command='status',description='Статус игры'),
                BotCommand(command='settings',description='Настройки группы'),
                BotCommand(command='help',description='Как играть'),
                BotCommand(command='modes',description='Режимы игры'),
                BotCommand(command='myachv',description='Мои достижения'),
                BotCommand(command='missingachv',description='Неоткрытые достижения'),
                BotCommand(command='stats',description='Моя статистика'),
                BotCommand(command='top',description='Рейтинг'),
                BotCommand(command='cancelgame',description='Отменить игру'),
                BotCommand(command='premium',description='Premium для группы'),
            ]
            await bot.set_my_commands(private,scope=BotCommandScopeAllPrivateChats())
            await bot.set_my_commands(group,scope=BotCommandScopeAllGroupChats())
        except Exception:
            logging.getLogger(__name__).exception('Failed to update profile/commands')
        me=await bot.get_me(); logging.getLogger(__name__).info('SoVi l Sueños o vida started: @%s',me.username)
        await dp.start_polling(bot)
    finally:
        for task in list(manager.tasks.values()): task.cancel()
        await bot.session.close()
