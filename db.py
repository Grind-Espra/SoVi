import psycopg2

from psycopg2 import connection as _connection
from config import settings


class Database:

    @staticmethod
    def connect() -> _connection:
        return psycopg2.connect(dbname=settings.db_name,
                                user=settings.db_user,
                                password=settings.db_pass,
                                host='localhost')

    def save_answer(self, question_id: int, is_yes: bool) -> None:
        """Функция для сохранения ответа в базу данных"""
        with self.connect() as conn:
            with conn.cursor() as cursor:
                column = 'yes_count' if is_yes else 'no_count'
                cursor.execute(f"UPDATE questions SET {column} = {column} + 1 WHERE id = %s", (question_id,))
                conn.commit()

    def get_next_question(self):
        """Функция для получения следующего вопроса из базы данных"""
        with self.connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, question_text FROM questions WHERE id NOT IN (SELECT question_id FROM user_answers) LIMIT 1")
                return cursor.fetchone()
def start_game_session(self, chat_id: int, max_questions: int = 20):
    with self.connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO game_sessions (chat_id, current_question_index, max_questions, is_active)
                VALUES (%s, 0, %s, TRUE)
                ON CONFLICT (chat_id) DO UPDATE SET current_question_index = 0, max_questions = %s, is_active = TRUE;
            """, (chat_id, max_questions, max_questions))
            conn.commit()

def stop_game_session(self, chat_id: int):
    with self.connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE game_sessions SET is_active = FALSE WHERE chat_id = %s", (chat_id,))
            conn.commit()

def get_current_question(self, chat_id: int):
    with self.connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT q.id, q.question_text FROM questions q
                JOIN game_sessions s ON q.id = s.current_question_index + 1
                WHERE s.chat_id = %s AND s.is_active = TRUE
                LIMIT 1
            """, (chat_id,))
            return cursor.fetchone()

def record_user_answer(self, user_id: int, chat_id: int, question_id: int, is_yes: bool):
    with self.connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO user_answers (user_id, chat_id, question_id, is_yes)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING;
            """, (user_id, chat_id, question_id, is_yes))
            cursor.execute(f"UPDATE questions SET {'yes_count' if is_yes else 'no_count'} = {'yes_count' if is_yes else 'no_count'} + 1 WHERE id = %s", (question_id,))
            conn.commit()

def advance_question(self, chat_id: int):
    with self.connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE game_sessions SET current_question_index = current_question_index + 1 WHERE chat_id = %s", (chat_id,))
            conn.commit()

def is_game_finished(self, chat_id: int):
    with self.connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT current_question_index, max_questions
                FROM game_sessions
                WHERE chat_id = %s AND is_active = TRUE
            """, (chat_id,))
            result = cursor.fetchone()
            if result:
                return result[0] >= result[1]
            return True

def get_statistics(self, chat_id: int):
    with self.connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT q.question_text,
                       q.yes_count,
                       q.no_count
                FROM questions q
                JOIN user_answers ua ON ua.question_id = q.id
                WHERE ua.chat_id = %s
                GROUP BY q.id
            """, (chat_id,))
            return cursor.fetchall()
