from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# sherpa/config.py -> repo root (works for editable install; wheel falls back to cwd)
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_ENV = _REPO_ROOT / ".env"


def _default_data_dir() -> Path:
    """Stable data/ location even when the process cwd is not the repo root."""
    if (_REPO_ROOT / "pyproject.toml").is_file():
        return _REPO_ROOT / "data"
    return Path.cwd() / "data"


def _env_file_path() -> Path | str:
    if _DEFAULT_ENV.is_file():
        return _DEFAULT_ENV
    return ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_file_path(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Optional paid / broker tiers
    news_api_key: str | None = Field(default=None, validation_alias="NEWS_API_KEY")
    alpaca_api_key: str | None = Field(default=None, validation_alias="ALPACA_API_KEY")
    alpaca_secret_key: str | None = Field(default=None, validation_alias="ALPACA_SECRET_KEY")
    alpaca_base_url: str = Field(
        default="https://paper-api.alpaca.markets",
        validation_alias="ALPACA_BASE_URL",
    )

    data_dir: Path = Field(default_factory=_default_data_dir)
    # Paper simulation sandbox: separate files under data/simulations/<profile>/
    simulation_profile: str = Field(default="default", validation_alias="SIMULATION_PROFILE")
    max_position_pct_nav: float = Field(default=0.05, ge=0, le=1)
    max_daily_loss_pct: float = Field(default=0.02, ge=0, le=1)
    default_slippage_bps: float = Field(default=5.0, ge=0)


def get_settings() -> Settings:
    return Settings()
