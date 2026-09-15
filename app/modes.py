from __future__ import annotations

MODES = {
    'classic': {
        'title': '🎮 Классика',
        'description': 'Обычные вопросы без лишней суеты. Выбирай «Да» или «Нет».',
        'command': 'startclassic',
        'emoji': '🎮',
    },
    'dilemma': {
        'title': '🧠 Сложная дилемма',
        'description': 'Непростые решения, где оба ответа могут быть неудобными.',
        'command': 'startdilemma',
        'emoji': '🧠',
    },
    'chaos': {
        'title': '😂 Хаос',
        'description': 'Абсурд, странные условия и вопросы, после которых хочется спросить «почему?»',
        'command': 'startchaos',
        'emoji': '😂',
    },
    'romance': {
        'title': '💘 Романтика',
        'description': 'Симпатия, отношения, свидания, дружба и немного неловких вопросов.',
        'command': 'startromance',
        'emoji': '💘',
    },
    'booklover': {
        'title': '📚 Книголюб',
        'description': 'Книги, герои, авторы, библиотеки и жизнь внутри историй.',
        'command': 'startbook',
        'emoji': '📚',
    },
    'horror': {
        'title': '👻 Ночная смена',
        'description': 'Мистика, хоррор и ситуации, в которых лучше не выключать свет.',
        'command': 'starthorror',
        'emoji': '👻',
    },
}

QUESTION_COUNTS_FREE = [10, 20, 25, 30, 35, 50]
QUESTION_COUNTS_PREMIUM = QUESTION_COUNTS_FREE + [75, 100]
QUESTION_COUNTS = QUESTION_COUNTS_FREE
FREE_MAX_PLAYERS = 12
PREMIUM_MAX_PLAYERS = 25
