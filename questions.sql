CREATE TABLE questions (
    id SERIAL PRIMARY KEY,
    question_text TEXT,
    yes_count default 0,
    no_count default 0
);
