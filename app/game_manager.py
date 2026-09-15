from __future__ import annotations

import asyncio
import html
import json
import logging
import time
from collections import defaultdict
from collections.abc import Awaitable

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from . import db
from .achievements import ACHIEVEMENT_MAP
from .config import Settings
from .keyboards import next_question_keyboard, registration_keyboard, vote_keyboard
from .modes import MODES

logger = logging.getLogger(__name__)


async def unlock_and_collect(db_path: str, uid: int, codes: list[str]) -> list[str]:
    out=[]
    for code in codes:
        if code in ACHIEVEMENT_MAP and await db.unlock_achievement(db_path, uid, code):
            out.append(code)
    return out


async def evaluate_user_achievements(db_path: str, uid: int) -> list[str]:
    st=await db.get_user_stats(db_path, uid)
    modes=await db.get_user_modes(db_path, uid)
    games=int(st['games_played']); answered=int(st['questions_answered']); hits=int(st['majority_hits']); minority=int(st['minority_hits']); streak=int(st['best_streak']); changed=int(st['changed_answers'])
    codes=[]
    if games>=1: codes += ['welcome']
    if answered>=1: codes += ['first_vote']
    if games>=10: codes += ['ten_games']
    if games>=50: codes += ['fifty_games']
    if games>=100: codes += ['hundred_games']
    if games>=1000: codes += ['thousand_games']
    if answered>=10: codes += ['ten_questions']
    if answered>=100: codes += ['hundred_questions']
    if answered>=500: codes += ['five_hundred_questions']
    if hits>=10: codes += ['majority_10']
    if hits>=50: codes += ['majority_50']
    if hits>=100: codes += ['majority_100']
    if streak>=5: codes += ['streak_5']
    if streak>=10: codes += ['streak_10']
    if streak>=20: codes += ['streak_20']
    if minority>=5: codes += ['minority_5']
    if minority>=25: codes += ['minority_25']
    if minority>=10: codes += ['minority_10']
    if changed>=1: codes += ['change_mind']
    if answered>=250: codes += ['answer_250']
    if answered>=1000: codes += ['answer_1000']
    if games>=250: codes += ['games_250']
    if st.get('ties',0)>=5: codes += ['tie_5']
    for mode, code in [('classic','classic_10'),('dilemma','dilemma_10'),('chaos','chaos_10'),('romance','romance_10'),('booklover','booklover_10'),('horror','horror_10')]:
        if modes.get(mode,0)>=10: codes.append(code)
    if modes.get('chaos',0)>=50: codes.append('chaos_50')
    if modes.get('dilemma',0)>=50: codes.append('dilemma_50')
    active_modes=sum(1 for k in MODES if modes.get(k,0)>=50)
    if active_modes>=3: codes.append('modes_50')
    if modes.get('horror',0)>=10: codes.append('night_owl')
    if all(modes.get(k,0)>=1 for k in MODES): codes.append('all_modes')
    return await unlock_and_collect(db_path,uid,codes)


class GameManager:
    def __init__(self, bot: Bot, settings: Settings):
        self.bot=bot; self.settings=settings
        self.tasks:dict[int,asyncio.Task]={}; self.locks=defaultdict(asyncio.Lock)

    def cancel(self, game_id:int)->None:
        task=self.tasks.pop(game_id,None); current=asyncio.current_task()
        if task and task is not current and not task.done(): task.cancel()

    def _replace_task(self, game_id:int, coro:Awaitable[None])->None:
        self.cancel(game_id); self.tasks[game_id]=asyncio.create_task(coro)

    def schedule_registration(self, game_id:int, delay:float|None=None)->None:
        self._replace_task(game_id,self._registration_worker(game_id,delay))

    def schedule_question_close(self, game_id:int, delay:float|None=None)->None:
        self._replace_task(game_id,self._question_worker(game_id,delay))

    async def restore_active_games(self)->None:
        for game in await db.get_active_games(self.settings.db_path):
            try:
                if game['status']=='registration':
                    delay=max(0,float(game['registration_ends_at'] or time.time())-time.time()); self.schedule_registration(game['id'],delay)
                elif game['status']=='running':
                    if not game['current_question_id']: await self.send_next_question(game['id'])
                    else:
                        started=float(game['current_question_started_at'] or time.time()); duration=await self.question_duration(game['id'])
                        self.schedule_question_close(game['id'],max(0,started+duration-time.time()))
            except Exception: logger.exception('Failed to restore game %s',game['id'])

    async def question_duration(self,game_id:int)->int:
        game=await db.get_game(self.settings.db_path,game_id); cfg=await db.get_chat_settings(self.settings.db_path,game['chat_id']); return int(cfg['vote_seconds'])

    async def _registration_worker(self,game_id:int,delay:float|None)->None:
        try:
            await asyncio.sleep(0 if delay is None else delay)
            while True:
                game=await db.get_game(self.settings.db_path,game_id)
                if not game or game['status']!='registration': return
                names=[p['display_name'] for p in await db.get_player_rows(self.settings.db_path,game_id)]
                cfg=await db.get_chat_settings(self.settings.db_path,game['chat_id'])
                remain=max(0,int(float(game['registration_ends_at'])-time.time()+0.999))
                if game['registration_message_id']:
                    try:
                        await self.bot.edit_message_text(chat_id=game['chat_id'],message_id=game['registration_message_id'],text=registration_text(names,remain,int(cfg['min_players']),game['mode'],len(json.loads(game['questions_json'])),25 if await db.is_chat_premium(self.settings.db_path,game['chat_id']) else 12),reply_markup=registration_keyboard(game_id,len(json.loads(game['questions_json'])),game['mode'],True))
                    except (TelegramBadRequest,TelegramForbiddenError): pass
                if remain<=0: break
                await asyncio.sleep(min(5,remain))
            await self.start_game(game_id,'timer')
        except asyncio.CancelledError: raise
        except Exception: logger.exception('Registration worker failed for game %s',game_id)

    async def start_game(self,game_id:int,reason:str='manual')->bool:
        async with self.locks[game_id]:
            game=await db.get_game(self.settings.db_path,game_id)
            if not game or game['status']!='registration': return False
            count=await db.get_player_count(self.settings.db_path,game_id); cfg=await db.get_chat_settings(self.settings.db_path,game['chat_id'])
            if count<int(cfg['min_players']): return False
            max_players = 25 if await db.is_chat_premium(self.settings.db_path,game['chat_id']) else 12
            if count > max_players: return False
            if not await db.set_game_running(self.settings.db_path,game_id): return False
            ids=json.loads(game['questions_json']); duration=int(cfg['vote_seconds'])
            try:
                if game['registration_message_id']:
                    await self.bot.edit_message_text(chat_id=game['chat_id'],message_id=game['registration_message_id'],text=(f'🚀 <b>ИГРА НАЧИНАЕТСЯ</b>\n\n{MODES[game["mode"]]["title"]}\n👥 Игроков: <b>{count}</b>\n📝 Вопросов: <b>{len(ids)}</b>\n⏱ На вопрос: <b>{duration} сек.</b>'),reply_markup=None)
            except (TelegramBadRequest,TelegramForbiddenError): pass
            await self.bot.send_message(game['chat_id'],f'🎭 <b>SoVi l Sueños o vida</b>\n\n🚀 Игра началась!\n{MODES[game["mode"]]["title"]}\n👥 Игроков: <b>{count}</b>\n📝 Вопросов: <b>{len(ids)}</b>\n⏱ До <b>{duration} сек.</b> на вопрос.\n\n⚡ Ответили все — идём дальше сразу.')
        await asyncio.sleep(0.7); await self.send_next_question(game_id); return True

    async def _question_worker(self,game_id:int,delay:float|None)->None:
        try:
            await asyncio.sleep(0 if delay is None else delay); await self.close_question_and_continue(game_id)
        except asyncio.CancelledError: raise
        except Exception: logger.exception('Question worker failed for game %s',game_id)

    async def send_next_question(self,game_id:int)->None:
        async with self.locks[game_id]:
            game=await db.get_game(self.settings.db_path,game_id)
            if not game or game['status']!='running' or game['current_question_id']: return
            ids=json.loads(game['questions_json']); idx=int(game['question_index'])
            if idx>=len(ids): return await self.finish(game_id)
            q=await db.get_question(self.settings.db_path,ids[idx]); cfg=await db.get_chat_settings(self.settings.db_path,game['chat_id']); duration=int(cfg['vote_seconds'])
            text=(f'🧠 <b>ВОПРОС {idx+1}/{len(ids)}</b>  •  {MODES[game["mode"]]["title"]}\n'
                  f'🏷 <i>{html.escape(q["category"])}</i>\n\n{html.escape(q["text"])}\n\n'
                  f'⏱ <b>{duration} сек.</b> на ответ\n🔒 Результаты откроются после завершения.')
            msg=await self.bot.send_message(chat_id=game['chat_id'],text=text,reply_markup=vote_keyboard(game_id,q['id']))
            started=time.time(); await db.set_current_question(self.settings.db_path,game_id,q['id'],idx,started,msg.message_id); self.schedule_question_close(game_id,duration)

    async def close_question_and_continue(self,game_id:int,forced:bool=False)->None:
        async with self.locks[game_id]:
            game=await db.get_game(self.settings.db_path,game_id)
            if not game or game['status']!='running' or not game['current_question_id']: return
            qid=int(game['current_question_id']); players=await db.get_player_rows(self.settings.db_path,game_id); player_count=len(players); answered=await db.get_answered_count(self.settings.db_path,game_id,qid); started=float(game['current_question_started_at'] or 0); duration=await self.question_duration(game_id)
            if not forced and answered<player_count and time.time()<started+duration:
                self.schedule_question_close(game_id,max(0.1,started+duration-time.time())); return
            yes,no,total=await db.get_vote_counts(self.settings.db_path,game_id,qid); votes=await db.get_votes_with_users(self.settings.db_path,game_id,qid); _,majority,tie=await db.award_question_points(self.settings.db_path,game_id,qid); cfg=await db.get_chat_settings(self.settings.db_path,game['chat_id'])
            try:
                if game['current_question_message_id']:
                    await self.bot.edit_message_reply_markup(chat_id=game['chat_id'],message_id=game['current_question_message_id'],reply_markup=None)
            except (TelegramBadRequest,TelegramForbiddenError): pass
            if total==0:
                body='🤷 <b>Никто не ответил.</b>\n\nПохоже, вопрос победил всех сразу 😄'
            else:
                yes_pct=npct(yes,total); no_pct=npct(no,total); head='⚔️ <b>Ничья!</b>' if yes==no else f'🏆 Большинство: <b>{"Да" if yes>no else "Нет"}</b>'
                body=('📊 <b>РЕЗУЛЬТАТЫ</b>\n\n✅ За «Да» — <b>'+str(yes_pct)+'%</b> ('+str(yes)+')\n'
                      '❌ За «Нет» — <b>'+str(no_pct)+'%</b> ('+str(no)+')\n\n'+head+'\n'
                      f'👥 Ответили: <b>{total}/{player_count}</b>\n\n')
                if tie: body+='⚖️ На этот раз победила ничья. Ответившие получили по <b>+1</b>.\n'
                elif majority is not None: body+='🎯 Игроки, выбравшие большинство, получают <b>+1</b>.\n'
                if not int(cfg['anonymous_results']):
                    yes_names=[format_voter(n,u) for _,a,n,u in votes if a==1]; no_names=[format_voter(n,u) for _,a,n,u in votes if a==0]; voted={uid for uid,_,_,_ in votes}; pending=[format_voter(p['display_name'],p['username']) for p in players if p['telegram_id'] not in voted]
                    body+='\n👥 <b>Кто голосовал:</b>\n✅ <b>«Да» ('+str(len(yes_names))+')</b>\n'+(''.join('• '+n+'\n' for n in yes_names) if yes_names else '• —\n')
                    body+='❌ <b>«Нет» ('+str(len(no_names))+')</b>\n'+(''.join('• '+n+'\n' for n in no_names) if no_names else '• —\n')
                    if pending: body+='⏳ <b>Не ответили ('+str(len(pending))+')</b>\n'+'\n'.join('• '+n for n in pending)+'\n'
            await self.bot.send_message(chat_id=game['chat_id'],text=body,reply_markup=next_question_keyboard(game_id))
            await db.clear_current_question(self.settings.db_path,game_id); await db.increment_question_index(self.settings.db_path,game_id)
            # Unlock lightweight achievements per voter.
            for uid,_,_,_ in votes:
                codes=['tie_breaker'] if tie else []
                if int(cfg['anonymous_results']): codes.append('anon_respect')
                await unlock_and_collect(self.settings.db_path,uid,codes)
                await evaluate_user_achievements(self.settings.db_path,uid)
        self.cancel(game_id); await asyncio.sleep(2); await self.send_next_question(game_id)

    async def next_question_now(self,game_id:int)->bool:
        async with self.locks[game_id]:
            game=await db.get_game(self.settings.db_path,game_id)
            if not game or game['status']!='running' or game['current_question_id']: return False
        self.cancel(game_id); await self.send_next_question(game_id); return True

    async def finish(self,game_id:int)->None:
        game=await db.get_game(self.settings.db_path,game_id)
        if not game: return
        changed=await db.finish_game(self.settings.db_path,game_id,'finished'); self.cancel(game_id)
        if not changed: return
        players=await db.get_player_rows(self.settings.db_path,game_id)
        if not players: text='🏁 <b>ИГРА ЗАВЕРШЕНА</b>\n\nРезультатов нет.'
        else:
            lines=[f'<b>{i}.</b> {html.escape(p["display_name"])} — <b>{p["score"]}</b>' for i,p in enumerate(players[:10],1)]
            max_score=max(int(p['score']) for p in players); winners=[p for p in players if int(p['score'])==max_score]
            text=('🏁 <b>SÓVI — ИГРА ОКОНЧЕНА</b>\n\n'+MODES[game['mode']]['title']+'\n\n🏆 <b>Итог</b>\n\n'+'\n'.join(lines)+f'\n\n🥇 Победил: <b>{len(winners)} игрок(а)</b> с {max_score} очк.\n\n🏆 /myachv — достижения\n📊 /stats — статистика')
        await self.bot.send_message(game['chat_id'],text)
        for p in players:
            codes=[]
            st=await db.get_user_stats(self.settings.db_path,int(p['telegram_id']))
            gp=len(players); qcount=len(json.loads(game['questions_json']))
            if gp==2: codes.append('two_players')
            if gp>=10: codes.append('big_room_10')
            if gp>=20: codes.append('big_room_20')
            if gp>=25: codes.append('big_room_25')
            if qcount>=10 and await db.user_answered_all(self.settings.db_path,game_id,int(p['telegram_id'])): codes.append('perfect_10')
            if qcount>=20: codes.append('marathon_20')
            if qcount>=50: codes.append('marathon_50')
            if qcount>=100: codes.append('marathon_100')
            if int(p['score'])==max_score: codes.append('best_of_game')
            if int((await db.get_chat_settings(self.settings.db_path,game['chat_id']))['anonymous_results']): codes.append('anon_respect')
            mode=game['mode']; codes += {'chaos':['chaos_survivor'],'dilemma':['dilemma_survivor'],'romance':['romantic_survivor'],'horror':['first_horror'],'booklover':['open_book']}.get(mode,[])
            await unlock_and_collect(self.settings.db_path,int(p['telegram_id']),codes); await evaluate_user_achievements(self.settings.db_path,int(p['telegram_id']))


def npct(value:int,total:int)->int: return round(value/total*100) if total else 0

def format_voter(name:str|None,username:str|None)->str:
    label=html.escape(name or 'Игрок'); return f'{label} (@{html.escape(username)})' if username else label

def registration_text(names:list[str],left:int,min_players:int,mode:str='classic',question_count:int=10,max_players:int=12)->str:
    listed='\n'.join(f'{i}. {html.escape(name)}' for i,name in enumerate(names[:30],1)) or 'Пока никого нет'
    if len(names)>30: listed+=f'\n… и ещё {len(names)-30}'
    ready='✅ Минимум набран — можно начинать сразу.' if len(names)>=min_players else f'⚠️ Нужно ещё <b>{min_players-len(names)}</b> игрока.'
    return (f'🎭 <b>SoVi l Sueños o vida</b>\n\n<b>Регистрация открыта</b>\n\n{MODES.get(mode,MODES["classic"])["title"]}\n'
            f'👥 <b>Игроки:</b>\n{listed}\n\n👥 Всего: <b>{len(names)}</b> / {max_players}\n📝 Вопросов: <b>{question_count}</b>\n⏳ Автостарт через: <b>{left} сек.</b>\n\n{ready}\n\n'
            '🙈 Результаты по умолчанию анонимны.\n🚀 Можно начать раньше, когда набрали минимум.')
