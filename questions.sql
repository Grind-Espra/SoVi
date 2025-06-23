CREATE TABLE questions (
    id SERIAL PRIMARY KEY,
    question_text TEXT NOT NULL,
    yes_count INTEGER DEFAULT 0,
    no_count INTEGER DEFAULT 0
);

CREATE TABLE user_answers (
    user_id BIGINT,
    chat_id BIGINT,
    question_id INT,
    is_yes BOOLEAN,
    PRIMARY KEY (user_id, question_id)
);

CREATE TABLE game_sessions (
    chat_id BIGINT PRIMARY KEY,
    current_question_index INT DEFAULT 0,
    max_questions INT DEFAULT 20,
    is_active BOOLEAN DEFAULT FALSE
);

CREATE TABLE game_participants (
    chat_id BIGINT,
    user_id BIGINT,
    PRIMARY KEY (chat_id, user_id)
);
