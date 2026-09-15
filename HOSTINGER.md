# SoVi on Hostinger VPS (Web Console)

## 1. Clone the repository

    mkdir -p /opt/bots
    cd /opt/bots
    git clone https://github.com/YOUR_GITHUB_USERNAME/YOUR_REPOSITORY.git sovi
    cd sovi

## 2. Create the environment file

    nano .env

Paste your real values. Minimum required:

    BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
    REGISTRATION_SECONDS=60
    VOTE_SECONDS=60
    QUESTIONS_PER_GAME=10
    MIN_PLAYERS=2
    MAX_PLAYERS=12
    RESULT_DELAY_SECONDS=2
    PREMIUM_STARS=150
    DB_PATH=data/bot.db

Save with Ctrl+O, Enter, then exit with Ctrl+X.

## 3. Build and start

    docker compose up -d --build

## 4. Check logs

    docker compose logs -f --tail=100

You should see the bot start polling Telegram.

## 5. Useful commands

    docker compose ps
    docker compose restart
    docker compose stop
    docker compose down
    docker compose logs -f

## 6. Update from GitHub

    git pull
    docker compose up -d --build

Do not run `docker compose down -v` for this project: the bot database is stored in `./data`, and deleting the volume is unnecessary.

## Isolation

This Compose project is named `sovi` and does not publish any host ports. Telegram long polling is used, so SoVi does not need ports such as 3000 or 8080. Other bots can run as separate Compose projects in their own directories.
