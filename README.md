# SoVi l Sueños o vida — Hostinger/GitHub build

This repository is prepared for deployment on a Hostinger VPS using Docker Compose.

## Run locally

    cp .env.dist .env
    # put the real BOT_TOKEN into .env
    docker compose up -d --build

## Hostinger Web Console

See `HOSTINGER.md` for the exact Web Console commands.

## Important

- Keep `.env` out of GitHub.
- `data/bot.db` is ignored by Git and persisted on the VPS through `./data:/app/data`.
- The bot does not expose any host ports.
- Other bots can use their own Compose project and directory without sharing Python environments or containers.


## Question flow

The active game engine is `app/game_manager.py`. After a question is closed,
the database atomically increments `question_index` and clears the current
question. This prevents a stale timeout or callback from replaying the same
question.

`main.py` and `bot.py` both launch the same current implementation.
