from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    admin_token: str = Field(alias="ADMIN_TOKEN")

    db_path: str = Field(default="/data/app.db", alias="DB_PATH")

    fetch_at_utc: str = Field(default="02:00", alias="FETCH_AT_UTC")

    max_items_per_feed: int = Field(default=50, alias="MAX_ITEMS_PER_FEED")
    request_timeout_seconds: int = Field(default=20, alias="REQUEST_TIMEOUT_SECONDS")
    user_agent: str = Field(default="LandingBot/1.0", alias="USER_AGENT")

    min_words: int = Field(default=300, alias="MIN_WORDS")
    preview_words: int = Field(default=200, alias="PREVIEW_WORDS")

settings = Settings()
