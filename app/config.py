from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    api_football_key: str = ""
    league_ids: str = "71"
    timezone: str = "America/Sao_Paulo"
    days_ahead: int = Field(default=3, ge=0, le=7)
    refresh_minutes: int = Field(default=30, ge=5, le=1440)
    database_path: str = "data/football.sqlite3"
    max_requests_per_day: int = Field(default=90, ge=1)
    max_requests_per_refresh: int = Field(default=35, ge=1)
    max_fixtures: int = Field(default=12, ge=1, le=100)
    enable_odds: bool = False
    enable_injuries: bool = False
    enable_detailed_stats: bool = False
    odds_max_age_minutes: int = Field(default=60, ge=1, le=1440)
    admin_token: str = ""
    preferred_bookmaker_name: str = "83bets"
    preferred_bookmaker_id: int | None = Field(default=None, ge=1)

    @field_validator("preferred_bookmaker_id", mode="before")
    @classmethod
    def empty_bookmaker_id(cls, value):
        return None if value == "" else value

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        ZoneInfo(value)
        return value

    @field_validator("league_ids")
    @classmethod
    def valid_leagues(cls, value: str) -> str:
        ids = value.split(",")
        if not ids or any(not part.strip().isdigit() or int(part) < 1 for part in ids):
            raise ValueError("LEAGUE_IDS deve conter IDs positivos separados por vírgula")
        return value

    @property
    def leagues(self) -> list[int]:
        return list(dict.fromkeys(int(part.strip()) for part in self.league_ids.split(",")))


@lru_cache
def get_settings() -> Settings:
    return Settings()
