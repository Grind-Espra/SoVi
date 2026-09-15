from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

import aiosqlite

from .achievements import ACHIEVEMENTS

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users (
 telegram_id INTEGER PRIMARY KEY, username TEXT, display_name TEXT NOT NULL,
 games_played INTEGER NOT NULL DEFAULT 0, questions_answered INTEGER NOT NULL DEFAULT 0,
 majority_hits INTEGER NOT NULL DEFAULT 0, minority_hits INTEGER NOT NULL DEFAULT 0,
 ties INTEGER NOT NULL DEFAULT 0, current_streak INTEGER NOT NULL DEFAULT 0,
 best_streak INTEGER NOT NULL DEFAULT 0, changed_answers INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS questions (
 id INTEGER PRIMARY KEY, text TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'Разное',
 difficulty TEXT NOT NULL DEFAULT 'medium', mode TEXT NOT NULL DEFAULT 'classic',
 active INTEGER NOT NULL DEFAULT 1, source TEXT NOT NULL DEFAULT 'curated'
);
CREATE TABLE IF NOT EXISTS games (
 id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL, status TEXT NOT NULL,
 created_by INTEGER NOT NULL, mode TEXT NOT NULL DEFAULT 'classic',
 registration_ends_at REAL, registration_message_id INTEGER,
 question_index INTEGER NOT NULL DEFAULT 0, current_question_id INTEGER,
 current_question_started_at REAL, current_question_message_id INTEGER,
 questions_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, finished_at TEXT
);
CREATE TABLE IF NOT EXISTS game_players (
 game_id INTEGER NOT NULL, telegram_id INTEGER NOT NULL, score INTEGER NOT NULL DEFAULT 0,
 joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(game_id,telegram_id), FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE,
 FOREIGN KEY(telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS votes (
 game_id INTEGER NOT NULL, question_id INTEGER NOT NULL, telegram_id INTEGER NOT NULL,
 answer INTEGER NOT NULL CHECK(answer IN (0,1)), created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(game_id,question_id,telegram_id), FOREIGN KEY(game_id) REFERENCES games(id) ON DELETE CASCADE,
 FOREIGN KEY(telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS chat_settings (
 chat_id INTEGER PRIMARY KEY, anonymous_results INTEGER NOT NULL DEFAULT 1,
 vote_seconds INTEGER NOT NULL DEFAULT 60, registration_seconds INTEGER NOT NULL DEFAULT 60,
 questions_per_game INTEGER NOT NULL DEFAULT 10, min_players INTEGER NOT NULL DEFAULT 2,
 max_players INTEGER NOT NULL DEFAULT 12, default_mode TEXT NOT NULL DEFAULT 'classic', premium_until REAL, premium_customer_id INTEGER, premium_charge_id TEXT
);
CREATE TABLE IF NOT EXISTS achievements (
 code TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL, reward INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS user_achievements (
 telegram_id INTEGER NOT NULL, code TEXT NOT NULL, unlocked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(telegram_id,code), FOREIGN KEY(telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE,
 FOREIGN KEY(code) REFERENCES achievements(code) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_games_chat_status ON games(chat_id,status);
CREATE INDEX IF NOT EXISTS idx_votes_game_question ON votes(game_id,question_id);
CREATE INDEX IF NOT EXISTS idx_games_mode ON games(mode);
"""

DEFAULTS = {
    'anonymous_results': 1,
    'vote_seconds': 60,
    'registration_seconds': 60,
    'questions_per_game': 10,
    'min_players': 2,
    'max_players': 12,
    'default_mode': 'classic',
}


def _cols(row):
    return {r[1] for r in row}


async def init_db(db_path: str, questions_path: str) -> None:
    async with aiosqlite.connect(db_path) as c:
        await c.executescript(SCHEMA)
        migrations = {
            'users': [
                ('minority_hits', 'INTEGER NOT NULL DEFAULT 0'), ('ties', 'INTEGER NOT NULL DEFAULT 0'),
                ('changed_answers', 'INTEGER NOT NULL DEFAULT 0'), ('updated_at', 'TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP'),
                ('games_played', 'INTEGER NOT NULL DEFAULT 0'), ('questions_answered', 'INTEGER NOT NULL DEFAULT 0'),
                ('majority_hits', 'INTEGER NOT NULL DEFAULT 0'), ('current_streak', 'INTEGER NOT NULL DEFAULT 0'),
                ('best_streak', 'INTEGER NOT NULL DEFAULT 0'),
            ],
            'questions': [('mode', "TEXT NOT NULL DEFAULT 'classic'"), ('difficulty', "TEXT NOT NULL DEFAULT 'medium'"), ('source', "TEXT NOT NULL DEFAULT 'curated'")],
            'games': [('mode', "TEXT NOT NULL DEFAULT 'classic'"), ('current_question_started_at', 'REAL'), ('current_question_message_id', 'INTEGER'), ('finished_at', 'TEXT')],
            'chat_settings': [
                ('default_mode', "TEXT NOT NULL DEFAULT 'classic'"),
                ('premium_until', 'REAL'),
                ('premium_customer_id', 'INTEGER'),
                ('premium_charge_id', 'TEXT'),
            ],
        }
        for table, cols in migrations.items():
            existing = _cols(await (await c.execute(f'PRAGMA table_info({table})')).fetchall())
            for name, ddl in cols:
                if name not in existing:
                    await c.execute(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}')
        await c.executemany(
            'INSERT INTO achievements(code,title,description,reward) VALUES(?,?,?,?) ON CONFLICT(code) DO UPDATE SET title=excluded.title,description=excluded.description,reward=excluded.reward',
            ACHIEVEMENTS,
        )
        data = json.loads(Path(questions_path).read_text(encoding='utf-8'))
        await c.executemany(
            '''INSERT INTO questions(id,text,category,difficulty,mode,source) VALUES(?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET text=excluded.text,category=excluded.category,
               difficulty=excluded.difficulty,mode=excluded.mode,source=excluded.source,active=1''',
            [(x['id'], x['text'], x.get('category','Разное'), x.get('difficulty','medium'), x.get('mode','classic'), x.get('source','curated')) for x in data],
        )
        await c.commit()


async def get_chat_settings(db_path: str, chat_id: int) -> dict[str, Any]:
    async with aiosqlite.connect(db_path) as c:
        c.row_factory = aiosqlite.Row
        r = await (await c.execute('SELECT * FROM chat_settings WHERE chat_id=?', (chat_id,))).fetchone()
        if r:
            return dict(r)
        await c.execute('INSERT OR IGNORE INTO chat_settings(chat_id) VALUES(?)', (chat_id,))
        await c.commit()
        r = await (await c.execute('SELECT * FROM chat_settings WHERE chat_id=?', (chat_id,))).fetchone()
        return dict(r)


async def update_chat_setting(db_path: str, chat_id: int, field: str, value: int | str) -> None:
    allowed = set(DEFAULTS)
    if field not in allowed:
        raise ValueError(field)
    async with aiosqlite.connect(db_path) as c:
        await c.execute(
            f'INSERT INTO chat_settings(chat_id,{field}) VALUES(?,?) ON CONFLICT(chat_id) DO UPDATE SET {field}=excluded.{field}',
            (chat_id, value),
        )
        await c.commit()


async def reset_chat_settings(db_path: str, chat_id: int) -> None:
    async with aiosqlite.connect(db_path) as c:
        await c.execute("INSERT INTO chat_settings(chat_id) VALUES(?) ON CONFLICT(chat_id) DO UPDATE SET anonymous_results=1,vote_seconds=60,registration_seconds=60,questions_per_game=10,min_players=2,max_players=12,default_mode='classic'", (chat_id,))
        await c.commit()

async def is_chat_premium(db_path: str, chat_id: int) -> bool:
    import time
    async with aiosqlite.connect(db_path) as c:
        r=await (await c.execute('SELECT premium_until FROM chat_settings WHERE chat_id=?',(chat_id,))).fetchone()
        return bool(r and r[0] and float(r[0]) > time.time())

async def get_premium_until(db_path: str, chat_id: int):
    async with aiosqlite.connect(db_path) as c:
        r=await (await c.execute('SELECT premium_until FROM chat_settings WHERE chat_id=?',(chat_id,))).fetchone()
        return float(r[0]) if r and r[0] else None

async def set_chat_premium(db_path: str, chat_id: int, until_ts: float, customer_id=None, charge_id=None) -> None:
    async with aiosqlite.connect(db_path) as c:
        await c.execute("INSERT INTO chat_settings(chat_id,premium_until,premium_customer_id,premium_charge_id) VALUES(?,?,?,?) ON CONFLICT(chat_id) DO UPDATE SET premium_until=excluded.premium_until,premium_customer_id=excluded.premium_customer_id,premium_charge_id=excluded.premium_charge_id", (chat_id,until_ts,customer_id,charge_id))
        await c.commit()


async def upsert_user(db_path, telegram_id, username, display_name):
    async with aiosqlite.connect(db_path) as c:
        await c.execute(
            'INSERT INTO users(telegram_id,username,display_name) VALUES(?,?,?) ON CONFLICT(telegram_id) DO UPDATE SET username=excluded.username,display_name=excluded.display_name,updated_at=CURRENT_TIMESTAMP',
            (telegram_id, username, display_name),
        )
        await c.commit()


async def create_game(db_path, chat_id, created_by, registration_ends_at, question_ids, mode):
    async with aiosqlite.connect(db_path) as c:
        cur = await c.execute(
            "INSERT INTO games(chat_id,status,created_by,mode,registration_ends_at,questions_json) VALUES(?, 'registration', ?, ?, ?, ?)",
            (chat_id, created_by, mode, registration_ends_at, json.dumps(question_ids)),
        )
        await c.commit()
        return int(cur.lastrowid)


async def set_registration_message(db_path, game_id, message_id):
    async with aiosqlite.connect(db_path) as c:
        await c.execute('UPDATE games SET registration_message_id=? WHERE id=?', (message_id, game_id))
        await c.commit()


async def get_game(db_path, game_id):
    async with aiosqlite.connect(db_path) as c:
        c.row_factory = aiosqlite.Row
        r = await (await c.execute('SELECT * FROM games WHERE id=?', (game_id,))).fetchone()
        return dict(r) if r else None


async def get_active_game(db_path, chat_id):
    async with aiosqlite.connect(db_path) as c:
        c.row_factory = aiosqlite.Row
        r = await (await c.execute("SELECT * FROM games WHERE chat_id=? AND status IN('registration','running') ORDER BY id DESC LIMIT 1", (chat_id,))).fetchone()
        return dict(r) if r else None


async def get_active_games(db_path):
    async with aiosqlite.connect(db_path) as c:
        c.row_factory = aiosqlite.Row
        rows = await (await c.execute("SELECT * FROM games WHERE status IN('registration','running') ORDER BY id")).fetchall()
        return [dict(x) for x in rows]


async def join_game(db_path, game_id, uid):
    async with aiosqlite.connect(db_path) as c:
        cur = await c.execute('INSERT OR IGNORE INTO game_players(game_id,telegram_id) VALUES(?,?)', (game_id, uid))
        await c.commit()
        return cur.rowcount == 1


async def leave_game(db_path, game_id, uid):
    async with aiosqlite.connect(db_path) as c:
        cur = await c.execute('DELETE FROM game_players WHERE game_id=? AND telegram_id=?', (game_id, uid))
        await c.commit()
        return cur.rowcount == 1


async def get_player_count(db_path, game_id):
    async with aiosqlite.connect(db_path) as c:
        return int((await (await c.execute('SELECT COUNT(*) FROM game_players WHERE game_id=?', (game_id,))).fetchone())[0])


async def get_player_ids(db_path, game_id):
    async with aiosqlite.connect(db_path) as c:
        return [int(r[0]) for r in await (await c.execute('SELECT telegram_id FROM game_players WHERE game_id=?', (game_id,))).fetchall()]


async def get_player_rows(db_path, game_id):
    async with aiosqlite.connect(db_path) as c:
        c.row_factory = aiosqlite.Row
        rows = await (await c.execute('SELECT gp.telegram_id,gp.score,gp.joined_at,u.display_name,u.username FROM game_players gp JOIN users u ON u.telegram_id=gp.telegram_id WHERE gp.game_id=? ORDER BY gp.score DESC,gp.joined_at ASC', (game_id,))).fetchall()
        return [dict(x) for x in rows]


async def set_game_running(db_path, game_id):
    async with aiosqlite.connect(db_path) as c:
        cur = await c.execute("UPDATE games SET status='running',question_index=0 WHERE id=? AND status='registration'", (game_id,))
        await c.commit()
        return cur.rowcount == 1


async def set_current_question(db_path, game_id, qid, index, started, message_id):
    async with aiosqlite.connect(db_path) as c:
        await c.execute('UPDATE games SET current_question_id=?,question_index=?,current_question_started_at=?,current_question_message_id=? WHERE id=?', (qid, index, started, message_id, game_id))
        await c.commit()


async def clear_current_question(db_path, game_id):
    async with aiosqlite.connect(db_path) as c:
        await c.execute('UPDATE games SET current_question_id=NULL,current_question_started_at=NULL,current_question_message_id=NULL WHERE id=?', (game_id,))
        await c.commit()


async def replace_game_questions(db_path, game_id, question_ids):
    async with aiosqlite.connect(db_path) as c:
        await c.execute('UPDATE games SET questions_json=? WHERE id=? AND status="registration"', (json.dumps(question_ids), game_id))
        await c.commit()


async def finish_game(db_path, game_id, status='finished'):
    async with aiosqlite.connect(db_path) as c:
        cur = await c.execute("UPDATE games SET status=?,finished_at=CURRENT_TIMESTAMP WHERE id=? AND status IN ('registration','running')", (status, game_id))
        if cur.rowcount != 1:
            await c.rollback(); return False
        ids = [r[0] for r in await (await c.execute('SELECT telegram_id FROM game_players WHERE game_id=?', (game_id,))).fetchall()]
        for uid in ids:
            await c.execute('UPDATE users SET games_played=games_played+1,updated_at=CURRENT_TIMESTAMP WHERE telegram_id=?', (uid,))
        await c.commit(); return True


async def pick_questions(db_path, count, mode='classic'):
    async with aiosqlite.connect(db_path) as c:
        c.row_factory = aiosqlite.Row
        rows = await (await c.execute('SELECT id,category FROM questions WHERE active=1 AND mode=?', (mode,))).fetchall()
        if len(rows) < count:
            rows = await (await c.execute('SELECT id,category FROM questions WHERE active=1')).fetchall()
    by = defaultdict(list)
    for r in rows:
        by[r['category']].append(int(r['id']))
    for ids in by.values(): random.shuffle(ids)
    cats = list(by); random.shuffle(cats); selected=[]
    while len(selected) < count:
        progressed = False
        for cat in cats:
            if by[cat]: selected.append(by[cat].pop()); progressed = True
            if len(selected) >= count: break
        if not progressed: break
    if len(selected) < count:
        raise RuntimeError(f'Недостаточно вопросов для режима {mode}: нужно {count}, доступно {len(selected)}.')
    return selected


async def get_question(db_path, qid):
    async with aiosqlite.connect(db_path) as c:
        c.row_factory = aiosqlite.Row
        r = await (await c.execute('SELECT * FROM questions WHERE id=?', (qid,))).fetchone()
        if not r: raise KeyError(qid)
        return dict(r)


async def cast_vote(db_path, game_id, qid, uid, answer):
    async with aiosqlite.connect(db_path) as c:
        row = await (await c.execute('SELECT answer FROM votes WHERE game_id=? AND question_id=? AND telegram_id=?', (game_id, qid, uid))).fetchone()
        if row is None:
            await c.execute('INSERT INTO votes(game_id,question_id,telegram_id,answer) VALUES(?,?,?,?)', (game_id,qid,uid,answer)); await c.commit(); return 'created'
        old=int(row[0])
        if old == answer: return 'same'
        await c.execute('UPDATE votes SET answer=?,created_at=CURRENT_TIMESTAMP WHERE game_id=? AND question_id=? AND telegram_id=?', (answer,game_id,qid,uid));
        await c.execute('UPDATE users SET changed_answers=changed_answers+1 WHERE telegram_id=?', (uid,));
        await c.commit(); return 'changed'


async def get_answered_count(db_path, game_id, qid):
    async with aiosqlite.connect(db_path) as c:
        return int((await (await c.execute('SELECT COUNT(*) FROM votes WHERE game_id=? AND question_id=?', (game_id,qid))).fetchone())[0])


async def get_vote_counts(db_path, game_id, qid):
    async with aiosqlite.connect(db_path) as c:
        rows=await (await c.execute('SELECT answer,COUNT(*) FROM votes WHERE game_id=? AND question_id=? GROUP BY answer', (game_id,qid))).fetchall()
        m={int(a):int(n) for a,n in rows}; y=m.get(1,0); n=m.get(0,0); return y,n,y+n


async def get_votes_with_users(db_path, game_id, qid):
    async with aiosqlite.connect(db_path) as c:
        rows=await (await c.execute('SELECT v.telegram_id,v.answer,u.display_name,u.username FROM votes v JOIN users u ON u.telegram_id=v.telegram_id WHERE v.game_id=? AND v.question_id=? ORDER BY v.answer DESC,u.display_name COLLATE NOCASE', (game_id,qid))).fetchall()
        return [(int(uid),int(a),name,username) for uid,a,name,username in rows]


async def award_question_points(db_path, game_id, qid):
    votes = await get_votes_with_users(db_path, game_id, qid)
    if not votes: return {}, None, 0
    yes=sum(a==1 for _,a,_,_ in votes); no=len(votes)-yes
    if yes == no:
        majority=None; awards={uid:1 for uid,_,_,_ in votes}; tie=1
    else:
        majority=1 if yes>no else 0; awards={uid:1 for uid,a,_,_ in votes if a==majority}; tie=0
    async with aiosqlite.connect(db_path) as c:
        for uid,a,_,_ in votes:
            is_award = uid in awards
            if is_award:
                await c.execute('UPDATE game_players SET score=score+1 WHERE game_id=? AND telegram_id=?', (game_id,uid))
                if majority is not None:
                    await c.execute('UPDATE users SET majority_hits=majority_hits+1,questions_answered=questions_answered+1,current_streak=current_streak+1,best_streak=MAX(best_streak,current_streak+1),updated_at=CURRENT_TIMESTAMP WHERE telegram_id=?', (uid,))
                else:
                    await c.execute('UPDATE users SET ties=ties+1,questions_answered=questions_answered+1,current_streak=current_streak+1,best_streak=MAX(best_streak,current_streak+1),updated_at=CURRENT_TIMESTAMP WHERE telegram_id=?', (uid,))
            else:
                await c.execute('UPDATE users SET minority_hits=minority_hits+1,questions_answered=questions_answered+1,current_streak=0,updated_at=CURRENT_TIMESTAMP WHERE telegram_id=?', (uid,))
        await c.commit()
    return awards, majority, tie


async def get_user_stats(db_path, uid):
    async with aiosqlite.connect(db_path) as c:
        c.row_factory=aiosqlite.Row
        r=await (await c.execute('SELECT * FROM users WHERE telegram_id=?', (uid,))).fetchone()
        return dict(r) if r else {'games_played':0,'questions_answered':0,'majority_hits':0,'minority_hits':0,'ties':0,'current_streak':0,'best_streak':0,'changed_answers':0}


async def get_top_users(db_path, limit=10):
    async with aiosqlite.connect(db_path) as c:
        c.row_factory=aiosqlite.Row
        rows=await (await c.execute('SELECT display_name,username,games_played,questions_answered,majority_hits,best_streak FROM users WHERE questions_answered>0 ORDER BY majority_hits DESC,best_streak DESC,questions_answered DESC LIMIT ?', (limit,))).fetchall()
        return [dict(x) for x in rows]


async def get_user_modes(db_path, uid):
    async with aiosqlite.connect(db_path) as c:
        rows=await (await c.execute('SELECT mode,COUNT(*) FROM games g JOIN game_players gp ON gp.game_id=g.id WHERE gp.telegram_id=? AND g.status="finished" GROUP BY mode', (uid,))).fetchall()
        return {str(mode): int(n) for mode,n in rows}


async def get_user_achievement_codes(db_path, uid):
    async with aiosqlite.connect(db_path) as c:
        rows=await (await c.execute('SELECT code FROM user_achievements WHERE telegram_id=? ORDER BY unlocked_at ASC', (uid,))).fetchall()
        return [r[0] for r in rows]


async def unlock_achievement(db_path, uid, code) -> bool:
    async with aiosqlite.connect(db_path) as c:
        cur=await c.execute('INSERT OR IGNORE INTO user_achievements(telegram_id,code) VALUES(?,?)', (uid,code)); await c.commit(); return cur.rowcount==1


async def achievement_rows(db_path, missing_for_uid=None):
    async with aiosqlite.connect(db_path) as c:
        c.row_factory=aiosqlite.Row
        if missing_for_uid is None:
            rows=await (await c.execute('SELECT * FROM achievements ORDER BY rowid')).fetchall()
        else:
            rows=await (await c.execute('SELECT a.* FROM achievements a LEFT JOIN user_achievements ua ON ua.code=a.code AND ua.telegram_id=? WHERE ua.code IS NULL ORDER BY a.rowid', (missing_for_uid,))).fetchall()
        return [dict(x) for x in rows]


async def get_game_mode_stats(db_path, uid, mode) -> int:
    async with aiosqlite.connect(db_path) as c:
        return int((await (await c.execute('SELECT COUNT(*) FROM games g JOIN game_players gp ON gp.game_id=g.id WHERE gp.telegram_id=? AND g.mode=? AND g.status="finished"', (uid,mode))).fetchone())[0])


async def get_game_question_count(db_path, game_id) -> int:
    async with aiosqlite.connect(db_path) as c:
        r=await (await c.execute('SELECT questions_json FROM games WHERE id=?', (game_id,))).fetchone(); return len(json.loads(r[0])) if r else 0


async def get_game_player_count(db_path, game_id) -> int:
    return await get_player_count(db_path, game_id)


async def get_player_game_score(db_path, game_id, uid) -> int:
    async with aiosqlite.connect(db_path) as c:
        r=await (await c.execute('SELECT score FROM game_players WHERE game_id=? AND telegram_id=?', (game_id,uid))).fetchone(); return int(r[0]) if r else 0


async def get_max_game_score(db_path, game_id) -> int:
    async with aiosqlite.connect(db_path) as c:
        r=await (await c.execute('SELECT MAX(score) FROM game_players WHERE game_id=?', (game_id,))).fetchone(); return int(r[0] or 0)


async def user_answered_all(db_path, game_id, uid) -> bool:
    async with aiosqlite.connect(db_path) as c:
        q=await (await c.execute('SELECT questions_json FROM games WHERE id=?', (game_id,))).fetchone()
        if not q: return False
        total=len(json.loads(q[0])); answered=int((await (await c.execute('SELECT COUNT(*) FROM votes WHERE game_id=? AND telegram_id=?', (game_id,uid))).fetchone())[0]); return answered>=total
