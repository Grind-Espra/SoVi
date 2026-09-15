from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    bot_token: str
    registration_seconds: int = 60
    vote_seconds: int = 60
    questions_per_game: int = 10
    min_players: int = 2
    max_players: int = 12
    premium_stars: int = 150
    result_delay_seconds: int = 2
    db_path: str = "data/bot.db"

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("BOT_TOKEN", "").strip()
        if not token or token == "PUT_YOUR_BOT_TOKEN_HERE":
            raise RuntimeError("BOT_TOKEN is not set. Add it to .env or hosting environment variables.")
        db_path = os.getenv("DB_PATH", "data/bot.db").strip() or "data/bot.db"
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        return cls(
            bot_token=token,
            registration_seconds=max(10, int(os.getenv("REGISTRATION_SECONDS", "60"))),
            vote_seconds=max(10, int(os.getenv("VOTE_SECONDS", "60"))),
            questions_per_game=max(1, min(100, int(os.getenv("QUESTIONS_PER_GAME", "10")))),
            min_players=max(2, min(100, int(os.getenv("MIN_PLAYERS", "2")))),
            max_players=12,
            premium_stars=max(1, int(os.getenv("PREMIUM_STARS", "150"))),
            result_delay_seconds=max(1, min(10, int(os.getenv("RESULT_DELAY_SECONDS", "2")))),
            db_path=db_path,
        )
