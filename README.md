# SoVi l Sueños o vida — Hostinger/GitHub build

This repository is prepared for deployment on a Hostinger VPS using Docker Compose.

## Run locally

    cp .env.example .env
    # put the real BOT_TOKEN into .env
    docker compose up -d --build

## Hostinger Web Console

See `HOSTINGER.md` for the exact Web Console commands.

## Important

- Keep `.env` out of GitHub.
- `data/bot.db` is ignored by Git and persisted on the VPS through `./data:/app/data`.
- The bot does not expose any host ports.
- Other bots can use their own Compose project and directory without sharing Python environments or containers.
