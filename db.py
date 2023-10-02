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
