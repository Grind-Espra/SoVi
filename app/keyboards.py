from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .modes import MODES, QUESTION_COUNTS_FREE, QUESTION_COUNTS_PREMIUM


def registration_keyboard(game_id: int, question_count: int, mode: str, can_change_count: bool = True) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🎮 Присоединиться", callback_data=f"game:join:{game_id}"),
         InlineKeyboardButton(text="❌ Выйти", callback_data=f"game:leave:{game_id}")],
        [InlineKeyboardButton(text="🚀 Начать игру", callback_data=f"game:start:{game_id}")],
    ]
    if can_change_count:
        rows.append([InlineKeyboardButton(text=f"📝 Вопросов: {question_count}", callback_data=f"game:count:{game_id}")])
    rows.append([InlineKeyboardButton(text=f"{MODES[mode]['emoji']} {MODES[mode]['title'].replace(MODES[mode]['emoji']+' ', '')}", callback_data=f"game:about:{game_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def vote_keyboard(game_id: int, question_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да", callback_data=f"vote:1:{game_id}:{question_id}"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"vote:0:{game_id}:{question_id}"),
    ]])


def next_question_keyboard(game_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="➡️ Следующий вопрос", callback_data=f"game:next:{game_id}")
    ]])


def private_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Режимы", callback_data="private:modes")],
        [InlineKeyboardButton(text="🏆 Мои достижения", callback_data="private:achv")],
        [InlineKeyboardButton(text="📊 Моя статистика", callback_data="private:stats")],
        [InlineKeyboardButton(text="❓ Как играть", callback_data="private:help")],
    ])


def mode_list_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for key, info in MODES.items():
        rows.append([InlineKeyboardButton(text=info['title'], callback_data=f"modeinfo:{key}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_main_keyboard(chat_id: int, anonymous: bool, default_mode: str, premium: bool=False) -> InlineKeyboardMarkup:
    anon = "🙈 Анонимность: ВКЛ" if anonymous else "👀 Анонимность: ВЫКЛ"
    mode_title = MODES.get(default_mode, MODES['classic'])['title']
    premium_text = "💎 Premium активен" if premium else "💎 Premium"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎮 Игра", callback_data=f"setmenu:game:{chat_id}")],
        [InlineKeyboardButton(text="🕐 Тайминги", callback_data=f"setmenu:time:{chat_id}")],
        [InlineKeyboardButton(text=anon, callback_data=f"cfg:anon:{chat_id}")],
        [InlineKeyboardButton(text=f"🎭 Режим по умолчанию: {mode_title}", callback_data=f"setmenu:mode:{chat_id}")],
        [InlineKeyboardButton(text=premium_text, callback_data=f"setmenu:premium:{chat_id}")],
        [InlineKeyboardButton(text="🛠 Разное", callback_data=f"setmenu:misc:{chat_id}")],
        [InlineKeyboardButton(text="🔙 Выход", callback_data=f"setmenu:close:{chat_id}")],
    ])


def settings_game_keyboard(chat_id: int, questions: int, min_players: int, max_players: int, premium: bool=False) -> InlineKeyboardMarkup:
    max_cap = 25 if premium else 12
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📝 Вопросов по умолчанию: {questions}", callback_data=f"cfg:count:{chat_id}")],
        [InlineKeyboardButton(text=f"👥 Минимум игроков: {min_players}", callback_data=f"cfg:min:{chat_id}")],
        [InlineKeyboardButton(text=f"👤 Максимум игроков: {max_players}/{max_cap}", callback_data=f"cfg:max:{chat_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"setmenu:main:{chat_id}")],
    ])


def settings_time_keyboard(chat_id: int, vote_seconds: int, registration_seconds: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⏱ Вопрос: {vote_seconds} сек", callback_data=f"cfg:time:{chat_id}")],
        [InlineKeyboardButton(text=f"⏳ Регистрация: {registration_seconds} сек", callback_data=f"cfg:reg:{chat_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"setmenu:main:{chat_id}")],
    ])


def settings_mode_keyboard(chat_id: int, current_mode: str) -> InlineKeyboardMarkup:
    rows = []
    for key, info in MODES.items():
        mark = "✅ " if key == current_mode else ""
        rows.append([InlineKeyboardButton(text=f"{mark}{info['title']}", callback_data=f"cfg:mode:{chat_id}:{key}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"setmenu:main:{chat_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_misc_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Как играть", callback_data=f"setmenu:help:{chat_id}")],
        [InlineKeyboardButton(text="🔄 Сбросить настройки", callback_data=f"cfg:reset:{chat_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"setmenu:main:{chat_id}")],
    ])


def achievements_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏆 Полученные", callback_data="achv:mine"), InlineKeyboardButton(text="🔒 Осталось", callback_data="achv:missing")],
    ])
