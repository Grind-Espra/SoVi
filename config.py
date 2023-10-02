from pydantic_settings import BaseSettings, SettingsConfigDict


class _Settings(BaseSettings):
    tg_token: str = 1
    db_name: str
    db_user: str
    db_pass: str

    model_config = SettingsConfigDict(env_file=".env.dist", env_file_encoding="utf-8", extra="ignore")


settings = _Settings()
