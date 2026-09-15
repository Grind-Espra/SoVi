from __future__ import annotations

import html
import json
import time

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from .. import db
from ..config import Settings
from ..game_manager import GameManager, registration_text
from ..keyboards import registration_keyboard
from ..modes import MODES, QUESTION_COUNTS_FREE, QUESTION_COUNTS_PREMIUM

router=Router()


def display_name(user)->str: return user.full_name or (f'@{user.username}' if user.username else str(user.id))
def safe_name(value): return html.escape(value or 'Игрок')

def format_voter(name,username):
    label=safe_name(name); return f'{label} (@{safe_name(username)})' if username else label

async def is_group_admin(bot,chat_id,user_id):
    try: return (await bot.get_chat_member(chat_id,user_id)).status in {'creator','administrator'}
    except Exception: return False

async def delete_command(message):
    try: await message.delete()
    except (TelegramBadRequest,TelegramForbiddenError): pass


def parse_count(args:str|None, default:int, premium:bool=False)->int:
    values = QUESTION_COUNTS_PREMIUM if premium else QUESTION_COUNTS_FREE
    if not args: return default if default in values else 10
    try: n=int(args.strip().split()[0])
    except ValueError: return default if default in values else 10
    return n if n in values else (default if default in values else 10)

async def effective_max_players(db_path:str, chat_id:int)->int:
    return 25 if await db.is_chat_premium(db_path, chat_id) else 12

async def create_game_for_mode(message:Message,settings:Settings,manager:GameManager,mode:str,count:int|None=None):
    if message.chat.type=='private': return await message.answer('👥 Игру нужно запускать в группе.')
    active=await db.get_active_game(settings.db_path,message.chat.id)
    if active: return await message.answer('⚠️ В этой группе уже есть активная игра.')
    cfg=await db.get_chat_settings(settings.db_path,message.chat.id)
    premium=await db.is_chat_premium(settings.db_path,message.chat.id)
    default_count = int(cfg['questions_per_game'])
    qcount=parse_count(message.text.split(maxsplit=1)[1] if message.text and ' ' in message.text else None, count or default_count, premium)
    max_players = await effective_max_players(settings.db_path, message.chat.id)
    if not premium and qcount > 50:
        qcount = 50
    try: question_ids=await db.pick_questions(settings.db_path,qcount,mode)
    except RuntimeError as exc: return await message.answer(f'❌ {safe_name(str(exc))}')
    await db.upsert_user(settings.db_path,message.from_user.id,message.from_user.username,display_name(message.from_user))
    end=time.time()+int(cfg['registration_seconds']); game_id=await db.create_game(settings.db_path,message.chat.id,message.from_user.id,end,question_ids,mode); await db.join_game(settings.db_path,game_id,message.from_user.id)
    msg=await message.answer(registration_text([display_name(message.from_user)],int(cfg['registration_seconds']),int(cfg['min_players']),mode,qcount),reply_markup=registration_keyboard(game_id,qcount,mode,True))
    await db.set_registration_message(settings.db_path,game_id,msg.message_id); manager.schedule_registration(game_id,int(cfg['registration_seconds']))


@router.message(Command('game','play','startgame'))
async def cmd_game(message,settings,manager):
    cfg=await db.get_chat_settings(settings.db_path,message.chat.id) if message.chat.type!='private' else None
    return await create_game_for_mode(message,settings,manager,str(cfg['default_mode']) if cfg else 'classic')

@router.message(Command('startclassic'))
async def startclassic(message,settings,manager): return await create_game_for_mode(message,settings,manager,'classic')
@router.message(Command('startdilemma'))
async def startdilemma(message,settings,manager): return await create_game_for_mode(message,settings,manager,'dilemma')
@router.message(Command('startchaos'))
async def startchaos(message,settings,manager): return await create_game_for_mode(message,settings,manager,'chaos')
@router.message(Command('startromance'))
async def startromance(message,settings,manager): return await create_game_for_mode(message,settings,manager,'romance')
@router.message(Command('startbook'))
async def startbook(message,settings,manager): return await create_game_for_mode(message,settings,manager,'booklover')
@router.message(Command('starthorror'))
async def starthorror(message,settings,manager): return await create_game_for_mode(message,settings,manager,'horror')

@router.message(Command('go'))
async def cmd_go(message,settings,manager):
    if message.chat.type=='private': return await message.answer('👥 /go работает в группе.')
    active=await db.get_active_game(settings.db_path,message.chat.id)
    if not active: return await message.answer('⚠️ Сейчас нет игры, ожидающей старта.')
    ids=await db.get_player_ids(settings.db_path,active['id'])
    if message.from_user.id not in ids: return await message.answer('Сначала присоединитесь к игре.')
    cfg=await db.get_chat_settings(settings.db_path,message.chat.id)
    if len(ids)<int(cfg['min_players']): return await message.answer(f'⚠️ Нужно ещё {int(cfg["min_players"])-len(ids)} игрок.')
    await manager.start_game(active['id'],'command')

@router.message(Command('status'))
async def status(message,settings):
    if message.chat.type=='private': return await message.answer('📍 Статус игры смотрят в группе.')
    game=await db.get_active_game(settings.db_path,message.chat.id)
    if not game: return await message.answer('💤 Сейчас здесь нет активной игры. Напишите /game.')
    players=await db.get_player_rows(settings.db_path,game['id'])
    if game['status']=='registration':
        remain=max(0,int(float(game['registration_ends_at'])-time.time()+0.999)); return await message.answer(f'📝 <b>Регистрация</b>\n\n{MODES[game["mode"]]["title"]}\n👥 {len(players)} игрок(ов)\n⏳ {remain} сек.\n📝 Вопросов: {len(json.loads(game["questions_json"]))}')
    answered=await db.get_answered_count(settings.db_path,game['id'],int(game['current_question_id'])) if game['current_question_id'] else 0
    return await message.answer(f'🎮 <b>Игра идёт</b>\n\n{MODES[game["mode"]]["title"]}\n🧠 Вопрос {int(game["question_index"])+1}/{len(json.loads(game["questions_json"]))}\n👥 Игроков: {len(players)}\n✅ Ответили: {answered}/{len(players)}')

@router.message(Command('cancelgame'))
async def cancelgame(message,settings,manager):
    game=await db.get_active_game(settings.db_path,message.chat.id)
    if not game: return await message.answer('Сейчас нет активной игры.')
    if not await is_group_admin(message.bot,message.chat.id,message.from_user.id): return await message.answer('⛔ Отменить игру может только администратор.')
    if await db.finish_game(settings.db_path,game['id'],'cancelled'):
        manager.cancel(game['id']); await message.answer('🛑 Игра отменена администратором.')

@router.message(Command('anon'))
async def anon(message,settings):
    if message.chat.type=='private': return await message.answer('ℹ️ /anon меняет режим результатов конкретной группы. Используйте команду в нужной группе.')
    if not await is_group_admin(message.bot,message.chat.id,message.from_user.id): return await message.answer('⛔ Эта команда только для администратора группы.')
    p=(message.text or '').split(maxsplit=1); value=p[1].lower() if len(p)>1 else ''
    if value not in {'on','off'}: return await message.answer('Используйте <code>/anon on</code> или <code>/anon off</code>.')
    await db.update_chat_setting(settings.db_path,message.chat.id,'anonymous_results',1 if value=='on' else 0); await delete_command(message)

@router.callback_query(F.data.startswith('game:join:'))
async def join(callback,settings):
    gid=int(callback.data.rsplit(':',1)[1]); game=await db.get_game(settings.db_path,gid)
    if not game or game['status']!='registration' or time.time()>=float(game['registration_ends_at']): return await callback.answer('Регистрация уже закрыта.',show_alert=True)
    await db.upsert_user(settings.db_path,callback.from_user.id,callback.from_user.username,display_name(callback.from_user)); ids=await db.get_player_ids(settings.db_path,gid); cfg=await db.get_chat_settings(settings.db_path,game['chat_id'])
    max_players=await effective_max_players(settings.db_path,int(game['chat_id']))
    if len(ids)>=max_players and callback.from_user.id not in ids: return await callback.answer('Достигнут лимит игроков.',show_alert=True)
    added=await db.join_game(settings.db_path,gid,callback.from_user.id); await callback.answer('✅ Вы в игре!' if added else 'Вы уже в игре.'); await refresh_registration(callback,settings,gid)

@router.callback_query(F.data.startswith('game:leave:'))
async def leave(callback,settings):
    gid=int(callback.data.rsplit(':',1)[1]); game=await db.get_game(settings.db_path,gid)
    if not game or game['status']!='registration': return await callback.answer('Регистрация уже закрыта.',show_alert=True)
    removed=await db.leave_game(settings.db_path,gid,callback.from_user.id); await callback.answer('Вы вышли из игры.' if removed else 'Вы не были зарегистрированы.'); await refresh_registration(callback,settings,gid)

@router.callback_query(F.data.startswith('game:start:'))
async def start_btn(callback,settings,manager):
    gid=int(callback.data.rsplit(':',1)[1]); game=await db.get_game(settings.db_path,gid)
    if not game or game['status']!='registration': return await callback.answer('Игра уже запущена или закрыта.',show_alert=True)
    ids=await db.get_player_ids(settings.db_path,gid); cfg=await db.get_chat_settings(settings.db_path,game['chat_id'])
    if callback.from_user.id not in ids: return await callback.answer('Сначала присоединитесь к игре.',show_alert=True)
    if len(ids)<int(cfg['min_players']): return await callback.answer(f'Нужно минимум {cfg["min_players"]} игрока.',show_alert=True)
    max_players=await effective_max_players(settings.db_path,game['chat_id'])
    if len(ids)>max_players: return await callback.answer(f'Для этой группы максимум {max_players} игроков.',show_alert=True)
    await callback.answer('🚀 Поехали!'); await manager.start_game(gid,'button')

@router.callback_query(F.data.startswith('game:count:'))
async def game_count(callback,settings):
    gid=int(callback.data.rsplit(':',1)[1]); game=await db.get_game(settings.db_path,gid)
    if not game or game['status']!='registration': return await callback.answer('Регистрация уже закрыта.',show_alert=True)
    if callback.from_user.id!=int(game['created_by']) and not await is_group_admin(callback.bot,int(game['chat_id']),callback.from_user.id): return await callback.answer('Менять количество вопросов может создатель игры или админ.',show_alert=True)
    cfg=await db.get_chat_settings(settings.db_path,int(game['chat_id'])); cur=len(json.loads(game['questions_json'])); vals=QUESTION_COUNTS_PREMIUM if await db.is_chat_premium(settings.db_path,int(game['chat_id'])) else QUESTION_COUNTS_FREE; new=vals[(vals.index(cur)+1)%len(vals)] if cur in vals else 10
    ids=await db.pick_questions(settings.db_path,new,game['mode']); await db.replace_game_questions(settings.db_path,gid,ids)
    await callback.answer(f'📝 Теперь {new} вопросов'); await refresh_registration(callback,settings,gid)

@router.callback_query(F.data.startswith('game:about:'))
async def game_about(callback,settings):
    gid=int(callback.data.rsplit(':',1)[1]); game=await db.get_game(settings.db_path,gid)
    if not game: return await callback.answer('Игра не найдена.',show_alert=True)
    await callback.answer(); await callback.message.answer(f'{MODES[game["mode"]]["title"]}\n\n{MODES[game["mode"]]["description"]}')

@router.callback_query(F.data.startswith('game:next:'))
async def next_btn(callback,settings,manager):
    gid=int(callback.data.rsplit(':',1)[1]); game=await db.get_game(settings.db_path,gid)
    if not game or game['status']!='running': return await callback.answer('Игра уже завершена.',show_alert=True)
    if callback.from_user.id not in await db.get_player_ids(settings.db_path,gid): return await callback.answer('Вы не участвуете.',show_alert=True)
    ok=await manager.next_question_now(gid); await callback.answer('➡️ Следующий вопрос' if ok else 'Следующий вопрос уже запущен.')

@router.callback_query(F.data.startswith('vote:'))
async def vote(callback,settings,manager):
    p=callback.data.split(':');
    if len(p)!=4: return await callback.answer()
    answer=1 if p[1]=='1' else 0; gid,qid=int(p[2]),int(p[3]); game=await db.get_game(settings.db_path,gid)
    if not game or game['status']!='running' or int(game['current_question_id'] or 0)!=qid: return await callback.answer('⏰ Этот вопрос уже закрыт.',show_alert=True)
    if callback.from_user.id not in await db.get_player_ids(settings.db_path,gid): return await callback.answer('Вы не участвуете.',show_alert=True)
    started=float(game['current_question_started_at'] or 0); duration=await manager.question_duration(gid)
    if time.time()>=started+duration: return await callback.answer('⏰ Время вышло.',show_alert=True)
    result=await db.cast_vote(settings.db_path,gid,qid,callback.from_user.id,answer); await callback.answer({'created':'✅ Ответ принят.','changed':'🔄 Ответ изменён.','same':'Вы уже выбрали этот ответ.'}[result])
    if await db.get_answered_count(settings.db_path,gid,qid)>=await db.get_player_count(settings.db_path,gid): await manager.close_question_and_continue(gid,True)

async def refresh_registration(callback,settings,gid):
    game=await db.get_game(settings.db_path,gid)
    if not game or not callback.message: return
    names=[p['display_name'] for p in await db.get_player_rows(settings.db_path,gid)]; left=max(0,int(float(game['registration_ends_at'])-time.time()+0.999)); qcount=len(json.loads(game['questions_json']))
    cfg=await db.get_chat_settings(settings.db_path,game['chat_id'])
    try: await callback.message.edit_text(registration_text(names,left,int(cfg['min_players']),game['mode'],qcount,await effective_max_players(settings.db_path,game['chat_id'])),reply_markup=registration_keyboard(gid,qcount,game['mode'],True))
    except TelegramBadRequest: pass
