CREATE TABLE questions (
    id SERIAL PRIMARY KEY,
    question_text TEXT,
    yes_count INT,
    no_count INT
);