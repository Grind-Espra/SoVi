from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from .. import db
from ..achievements import ACHIEVEMENT_MAP
from ..config import Settings
from ..keyboards import (
    achievements_keyboard,
    mode_list_keyboard,
    settings_game_keyboard,
    settings_main_keyboard,
    settings_misc_keyboard,
    settings_mode_keyboard,
    settings_time_keyboard,
)
from ..modes import MODES, QUESTION_COUNTS_FREE, QUESTION_COUNTS_PREMIUM

router=Router()


def esc(value): return html.escape(value or 'Игрок')


async def is_admin(bot, chat_id:int, user_id:int)->bool:
    try: return (await bot.get_chat_member(chat_id,user_id)).status in {'creator','administrator'}
    except Exception: return False


async def send_settings_panel(target:Message|CallbackQuery, settings:Settings, chat_id:int):
    user=target.from_user; bot=target.bot
    if not await is_admin(bot,chat_id,user.id):
        text='⛔ У вас больше нет прав администратора этой группы.'
        return await target.answer(text,show_alert=True) if isinstance(target,CallbackQuery) else await target.answer(text)
    cfg=await db.get_chat_settings(settings.db_path,chat_id)
    try: title=(await bot.get_chat(chat_id)).title or str(chat_id)
    except Exception: title=str(chat_id)
    text=(f'⚙️ <b>Настройки SoVi l Sueños o vida</b>\n\n<b>{esc(title)}</b>\n\n'
          'Здесь можно спокойно покрутить настройки именно этой группы. Ничего соседнему чату не сломаем 😄')
    kb=settings_main_keyboard(chat_id,bool(cfg['anonymous_results']),str(cfg['default_mode']),await db.is_chat_premium(settings.db_path,chat_id))
    if isinstance(target,CallbackQuery):
        await target.message.edit_text(text,reply_markup=kb); return await target.answer()
    return await target.answer(text,reply_markup=kb)


@router.message(CommandStart())
async def start(message:Message,settings:Settings):
    payload=(message.text or '').split(maxsplit=1)[1] if ' ' in (message.text or '') else ''
    await db.upsert_user(settings.db_path,message.from_user.id,message.from_user.username,message.from_user.full_name)
    if payload.startswith('premium_') and message.chat.type=='private':
        try: chat_id=int(payload[len('premium_'):])
        except ValueError: return await message.answer('⚠️ Не удалось определить группу.')
        if not await is_admin(message.bot,chat_id,message.from_user.id):
            return await message.answer('⛔ Premium для группы может подключить только её администратор.')
        from .premium import premium_info
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
        text=await premium_info(message.bot,settings,chat_id)
        kb=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='💎 Подключить Premium',callback_data=f'premium:buy:{chat_id}')],
            [InlineKeyboardButton(text='🔄 Проверить статус',callback_data=f'premium:status:{chat_id}')],
        ])
        return await message.answer(text,reply_markup=kb)
    if payload.startswith('settings_') and message.chat.type=='private':
        try: chat_id=int(payload[len('settings_'):])
        except ValueError: return await message.answer('⚠️ Не удалось определить группу.')
        return await send_settings_panel(message,settings,chat_id)
    await message.answer(
        '🎭 <b>SoVi l Sueños o vida</b>\n\n'
        'Игра для компании, где один невинный вопрос способен вызвать спор на полчаса 😄\n\n'
        '<b>Основные команды</b>\n'
        '/game — создать игру\n'
        '/startgame — запустить классическую игру\n'
        '/go — начать набранную игру\n'
        '/settings — настройки группы (админ)\n'
        '/help — как играть\n'
        '/modes — режимы\n'
        '/myachv — мои достижения\n'
        '/missingachv — чего ещё не хватает\n'
        '/stats — моя статистика\n'
        '/top — рейтинг\n/premium — Premium для этой группы (админ)\n\n'
        '👥 Для теста достаточно <b>2 игроков</b>.\n'
        '🙈 По умолчанию результаты анонимные.',reply_markup=achievements_keyboard())


@router.message(Command('help'))
async def help_cmd(message:Message):
    await message.answer(
        '🎭 <b>SoVi — что тут вообще происходит?</b>\n\n'
        'Это игра для компании: бот задаёт вопрос, вы жмёте <b>Да</b> или <b>Нет</b>, а потом смотрите, насколько совпали с остальными. Всё просто — пока кто-нибудь не начнёт спорить из-за 51% 😄\n\n'
        '<b>🎮 Как сыграть</b>\n'
        '/game — открыть регистрацию\n'
        '/go — запустить набранную игру\n'
        'Или сразу выбрать режим командами ниже.\n\n'
        '<b>🎭 Режимы</b>\n'
        '/startclassic — Классика\n'
        '/startdilemma — Сложная дилемма\n'
        '/startchaos — Хаос\n'
        '/startromance — Романтика\n'
        '/startbook — Книголюб\n'
        '/starthorror — Ночная смена\n\n'
        '<b>🙈 Анонимность</b>\n'
        'Обычно результаты скрыты. Хочется устроить разбор полётов — <code>/anon off</code>. Вернуть обратно — <code>/anon on</code>.\n'
        'Настройка действует для этой группы.\n\n'
        '<b>🏆 Достижения и статистика</b>\n'
        '/myachv — что уже открыто\n'
        '/missingachv — что ещё осталось\n'
        '/stats — твои цифры\n'
        '/top — кто сейчас впереди\n\n'
        '<b>⚙️ Настройки</b>\n'
        '/settings — админская панель в личке. Команда после нажатия исчезает из группы.\n\n'
        'И маленький совет: не пытайтесь серьёзно объяснить выбор в «Хаосе». Иногда даже бот не знает, зачем он это спросил 😄'
    )

@router.message(Command('modes'))
async def modes_cmd(message:Message):
    text='🎮 <b>Режимы SoVi</b>\n\n'
    for key,info in MODES.items(): text += f'{info["title"]} — {info["description"]}\n<code>/{info["command"]} 20</code>\n\n'
    text += 'Число после команды — количество вопросов. Если его не указать, берётся значение по умолчанию для группы.'
    await message.answer(text,reply_markup=mode_list_keyboard())


async def achievements_text(uid:int, settings:Settings, missing:bool=False)->str:
    rows=await db.achievement_rows(settings.db_path,uid if missing else None)
    unlocked=await db.get_user_achievement_codes(settings.db_path,uid)
    total=len(await db.achievement_rows(settings.db_path,None))
    if not missing:
        if not unlocked: return f'🏆 <b>Ваши достижения</b> [0/{total}]\n\nПока пусто. Самое время получить первое 😄'
        items=[ACHIEVEMENT_MAP[c]['title'] for c in unlocked if c in ACHIEVEMENT_MAP]
        return f'🏆 <b>Ваши достижения</b> [{len(items)}/{total}]\n\n'+'\n'.join(f'• {x}' for x in items)
    if not rows: return f'🎉 <b>Невероятно.</b> Вы открыли все {total} достижений.'
    lines=[]
    for r in rows:
        lines.append(f'\n<b>[ {r["title"]} ]</b>\n{r["description"]}  <i>[{r["reward"]} ✨]</i>')
    return f'🔒 <b>Вам не хватает {len(rows)} достижений</b>\n'+'\n'.join(lines)


@router.message(Command('myachv','achievements'))
async def myachv(message:Message,settings:Settings):
    await db.upsert_user(settings.db_path,message.from_user.id,message.from_user.username,message.from_user.full_name)
    await message.answer(await achievements_text(message.from_user.id,settings,False),reply_markup=achievements_keyboard())


@router.message(Command('missingachv'))
async def missingachv(message:Message,settings:Settings):
    await db.upsert_user(settings.db_path,message.from_user.id,message.from_user.username,message.from_user.full_name)
    await message.answer(await achievements_text(message.from_user.id,settings,True))


@router.message(Command('stats','stat'))
async def stats_cmd(message:Message,settings:Settings):
    await db.upsert_user(settings.db_path,message.from_user.id,message.from_user.username,message.from_user.full_name)
    d=await db.get_user_stats(settings.db_path,message.from_user.id)
    answered=int(d['questions_answered'])
    hits=int(d['majority_hits'])
    rate=round(hits/answered*100) if answered else 0
    text=(
        '📊 <b>Твоя статистика</b>\n\n'
        f'🎮 Игр: <b>{d["games_played"]}</b>\n'
        f'🗳 Ответов: <b>{answered}</b>\n'
        f'🎯 В большинстве: <b>{hits}</b> ({rate}%)\n'
        f'😈 В меньшинстве: <b>{d["minority_hits"]}</b>\n'
        f'⚖️ Ничьих: <b>{d["ties"]}</b>\n'
        f'🔥 Текущая серия: <b>{d["current_streak"]}</b>\n'
        f'🏆 Лучшая серия: <b>{d["best_streak"]}</b>'
    )
    await message.answer(text)


@router.message(Command('top','rating','leaderboard'))
async def top_cmd(message:Message,settings:Settings):
    rows=await db.get_top_users(settings.db_path,10)
    if not rows:
        return await message.answer('🏆 <b>Рейтинг пока пуст.</b>\n\nСыграйте первую игру — и можно начинать охоту за первым местом 😄')
    lines=[]
    medals=['🥇','🥈','🥉']
    for i,row in enumerate(rows,1):
        name=html.escape(row['display_name'] or row['username'] or 'Игрок')
        prefix=medals[i-1] if i<=3 else f'{i}.'
        lines.append(f'{prefix} <b>{name}</b> — {int(row["majority_hits"])} попаданий')
    await message.answer('🏆 <b>Рейтинг SoVi</b>\n\n'+'\n'.join(lines))


@router.callback_query(F.data=='private:help')
async def private_help(callback:CallbackQuery):
    await callback.answer(); await callback.message.answer('💡 /help уже всё рассказал. А если совсем просто: вошли в игру → нажали Да или Нет → подождали остальных → посмотрели, насколько вы совпадаете с толпой 😄')


@router.callback_query(F.data=='private:stats')
async def private_stats(callback:CallbackQuery,settings:Settings):
    await callback.answer(); await db.upsert_user(settings.db_path,callback.from_user.id,callback.from_user.username,callback.from_user.full_name)
    d=await db.get_user_stats(settings.db_path,callback.from_user.id); answered=int(d['questions_answered']); hits=int(d['majority_hits']); rate=round(hits/answered*100) if answered else 0
    await callback.message.answer(f'📊 <b>Статистика</b>\n\n🎮 Игр: <b>{d["games_played"]}</b>\n🧠 Ответов: <b>{answered}</b>\n🎯 Большинство: <b>{hits}</b> ({rate}%)\n😈 Меньшинство: <b>{d["minority_hits"]}</b>\n⚖️ Ничьих: <b>{d["ties"]}</b>\n🔥 Серия: <b>{d["current_streak"]}</b>\n🏆 Лучшая серия: <b>{d["best_streak"]}</b>')


@router.callback_query(F.data=='private:achv')
async def private_achv(callback:CallbackQuery,settings:Settings):
    await callback.answer(); await callback.message.answer(await achievements_text(callback.from_user.id,settings,False),reply_markup=achievements_keyboard())


@router.callback_query(F.data=='private:modes')
async def private_modes(callback:CallbackQuery):
    await callback.answer(); await callback.message.answer('🎮 <b>Режимы</b>\n\n'+ '\n'.join(f'{v["title"]} — {v["description"]}\n/{v["command"]} 20' for v in MODES.values()),reply_markup=mode_list_keyboard())


@router.callback_query(F.data=='achv:mine')
async def achv_mine(callback:CallbackQuery,settings:Settings):
    await callback.answer(); await callback.message.edit_text(await achievements_text(callback.from_user.id,settings,False),reply_markup=achievements_keyboard())


@router.callback_query(F.data=='achv:missing')
async def achv_missing(callback:CallbackQuery,settings:Settings):
    await callback.answer(); await callback.message.edit_text(await achievements_text(callback.from_user.id,settings,True),reply_markup=achievements_keyboard())


@router.callback_query(F.data.startswith('modeinfo:'))
async def mode_info(callback:CallbackQuery):
    key=callback.data.split(':',1)[1]; info=MODES.get(key)
    if not info: return await callback.answer('Режим не найден.',show_alert=True)
    await callback.answer(); await callback.message.answer(f'{info["title"]}\n\n{info["description"]}\n\nКоманда: <code>/{info["command"]} 20</code>')


@router.message(Command('settings'))
async def cmd_settings(message:Message,settings:Settings):
    if message.chat.type == 'private':
        return await message.answer('⚙️ Настройки меняются для конкретной группы. Откройте /settings из нужной группы, а панель придёт сюда, в личку.')
    if not await is_admin(message.bot,message.chat.id,message.from_user.id):
        try: await message.delete()
        except Exception: pass
        return
    chat_id=message.chat.id
    try: await message.delete()
    except Exception: pass
    me=await message.bot.get_me()
    link=f'https://t.me/{me.username}?start=settings_{chat_id}'
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    await message.bot.send_message(
        chat_id=message.from_user.id,
        text=(
            '⚙️ <b>Настройки SoVi</b>\n\n'
            f'Для группы <b>{html.escape(message.chat.title or str(chat_id))}</b> всё готово.\n'
            'Нажмите кнопку ниже — панель откроется прямо здесь, в личке.\n\n'
            'В группе ничего лишнего оставлять не будем 🙂'
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='⚙️ Открыть настройки',url=link)]])
    )

@router.callback_query(F.data.startswith('setmenu:'))
async def settings_menu(callback:CallbackQuery,settings:Settings):
    parts=callback.data.split(':'); action=parts[1]; chat_id=int(parts[2])
    if action=='close':
        await callback.answer()
        try: await callback.message.delete()
        except Exception: pass
        return
    if not await is_admin(callback.bot,chat_id,callback.from_user.id): return await callback.answer('⛔ Только администратор этой группы.',show_alert=True)
    cfg=await db.get_chat_settings(settings.db_path,chat_id)
    if action=='main':
        text='⚙️ <b>Настройки группы</b>\n\nВыберите, что хотите поменять.'; kb=settings_main_keyboard(chat_id,bool(cfg['anonymous_results']),str(cfg['default_mode']),await db.is_chat_premium(settings.db_path,chat_id))
    elif action=='game': text='🎮 <b>Игра</b>\n\nНажмите нужную строку, чтобы переключить значение.'; kb=settings_game_keyboard(chat_id,int(cfg['questions_per_game']),int(cfg['min_players']),int(cfg['max_players']),await db.is_chat_premium(settings.db_path,chat_id))
    elif action=='time': text='🕐 <b>Тайминги</b>\n\nВопрос живёт до 60 секунд по умолчанию, но когда ответили все — закрывается сразу.'; kb=settings_time_keyboard(chat_id,int(cfg['vote_seconds']),int(cfg['registration_seconds']))
    elif action=='mode': text='🎭 <b>Режим по умолчанию для /game</b>'; kb=settings_mode_keyboard(chat_id,str(cfg['default_mode']))
    elif action=='premium':
        active=await db.is_chat_premium(settings.db_path,chat_id)
        if active:
            until=await db.get_premium_until(settings.db_path,chat_id)
            text=f'💎 <b>Premium активен</b>\n\nДо <b>{__import__("time").strftime("%d.%m.%Y",__import__("time").localtime(until))}</b>\n\n👥 Лимит: <b>25 игроков</b>\n📝 Размер игры: до <b>100 вопросов</b>.'
            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
            kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🔄 Обновить статус',callback_data=f'setmenu:premium:{chat_id}')],[InlineKeyboardButton(text='🔙 Назад',callback_data=f'setmenu:main:{chat_id}')]])
        else:
            text='💎 <b>Premium</b>\n\nУвеличивает лимит группы до <b>25 игроков</b> и открывает длинные игры до <b>100 вопросов</b>.\n\nПокупка проходит в личном чате с ботом.'
            me=await callback.bot.get_me()
            from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
            kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='💎 Открыть Premium',url=f'https://t.me/{me.username}?start=premium_{chat_id}')],[InlineKeyboardButton(text='🔙 Назад',callback_data=f'setmenu:main:{chat_id}')]])
    elif action=='misc': text='🛠 <b>Разное</b>\n\nЗдесь спрятаны спокойные служебные настройки.'; kb=settings_misc_keyboard(chat_id)
    elif action=='help': return await callback.message.edit_text('📖 <b>Подсказка</b>\n\nАдминская панель работает только в личке. Настройки меняются для этой группы и больше ни для какой.')
    else: return await callback.answer('Неизвестный раздел.',show_alert=True)
    await callback.answer(); await callback.message.edit_text(text,reply_markup=kb)


@router.callback_query(F.data.startswith('cfg:'))
async def settings_change(callback:CallbackQuery,settings:Settings):
    parts=callback.data.split(':'); action=parts[1]; chat_id=int(parts[2])
    if not await is_admin(callback.bot,chat_id,callback.from_user.id): return await callback.answer('⛔ Только администратор этой группы.',show_alert=True)
    cfg=await db.get_chat_settings(settings.db_path,chat_id)
    if action=='anon':
        await db.update_chat_setting(settings.db_path,chat_id,'anonymous_results',0 if int(cfg['anonymous_results']) else 1)
    elif action=='time':
        vals=[30,45,60]; cur=int(cfg['vote_seconds']); await db.update_chat_setting(settings.db_path,chat_id,'vote_seconds',vals[(vals.index(cur)+1)%len(vals)] if cur in vals else 60)
    elif action=='reg':
        vals=[30,60,90,120]; cur=int(cfg['registration_seconds']); await db.update_chat_setting(settings.db_path,chat_id,'registration_seconds',vals[(vals.index(cur)+1)%len(vals)] if cur in vals else 60)
    elif action=='count':
        premium=await db.is_chat_premium(settings.db_path,chat_id)
        vals=QUESTION_COUNTS_PREMIUM if premium else QUESTION_COUNTS_FREE; cur=int(cfg['questions_per_game']); await db.update_chat_setting(settings.db_path,chat_id,'questions_per_game',vals[(vals.index(cur)+1)%len(vals)] if cur in vals else 10)
    elif action=='min':
        vals=[2,3,4,5]; cur=int(cfg['min_players']); await db.update_chat_setting(settings.db_path,chat_id,'min_players',vals[(vals.index(cur)+1)%len(vals)] if cur in vals else 2)
    elif action=='max':
        premium=await db.is_chat_premium(settings.db_path,chat_id)
        vals=[6,8,10,12,20,25] if premium else [6,8,10,12]
        cur=int(cfg['max_players'])
        new=vals[(vals.index(cur)+1)%len(vals)] if cur in vals else (25 if premium else 12)
        await db.update_chat_setting(settings.db_path,chat_id,'max_players',new)
    elif action=='reset':
        await db.reset_chat_settings(settings.db_path,chat_id)
    elif action=='mode':
        if len(parts)<4 or parts[3] not in MODES: return await callback.answer('Режим не найден.',show_alert=True)
        await db.update_chat_setting(settings.db_path,chat_id,'default_mode',parts[3])
    else: return await callback.answer('Неизвестная настройка.',show_alert=True)
    await callback.answer('✅ Сохранено.')
    cfg=await db.get_chat_settings(settings.db_path,chat_id)
    await settings_menu(CallbackQuery.model_construct(data=f'setmenu:main:{chat_id}',message=callback.message,from_user=callback.from_user,bot=callback.bot),settings) if False else None
    # Refresh current section without manufacturing CallbackQuery.
    if action in {'time','reg'}:
        await callback.message.edit_text('🕐 <b>Тайминги</b>\n\nИзменения действуют для следующей игры.',reply_markup=settings_time_keyboard(chat_id,int(cfg['vote_seconds']),int(cfg['registration_seconds'])))
    elif action in {'count','min','max'}:
        await callback.message.edit_text('🎮 <b>Игра</b>\n\nКоличество вопросов и лимиты игроков.',reply_markup=settings_game_keyboard(chat_id,int(cfg['questions_per_game']),int(cfg['min_players']),min(int(cfg['max_players']),25 if await db.is_chat_premium(settings.db_path,chat_id) else 12),await db.is_chat_premium(settings.db_path,chat_id)))
    elif action=='mode':
        await callback.message.edit_text('🎭 <b>Режим по умолчанию</b>',reply_markup=settings_mode_keyboard(chat_id,str(cfg['default_mode'])))
    elif action=='anon':
        await callback.message.edit_text('⚙️ <b>Настройки группы</b>\n\nАнонимность сейчас: <b>'+('ВКЛ' if cfg['anonymous_results'] else 'ВЫКЛ')+'</b>',reply_markup=settings_main_keyboard(chat_id,bool(cfg['anonymous_results']),str(cfg['default_mode']),await db.is_chat_premium(settings.db_path,chat_id)))
    elif action=='reset':
        await callback.message.edit_text('⚙️ <b>Настройки группы</b>\n\nВернули стандартные значения.',reply_markup=settings_main_keyboard(chat_id,True,'classic',await db.is_chat_premium(settings.db_path,chat_id)))
