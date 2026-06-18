"""Configuration management via Pydantic Settings.

Single source of truth for all configuration. Loads from .env file.
Use get_settings() for a cached singleton instance.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """TAP Framework configuration. All values loaded from environment / .env file."""

    # === Twitter API v2 — OAuth 2.0 Bearer Token (App-only auth, for search/read) ===
    twitter_bearer_token: str = Field(
        default="",
        description="OAuth 2.0 Bearer Token for search/read endpoints",
    )

    # === Twitter API v2 — OAuth 1.0a (User Context, required for POSTING) ===
    twitter_consumer_key: str = Field(
        default="",
        description="API Key / Consumer key",
    )
    twitter_consumer_secret: str = Field(
        default="",
        description="API Key Secret / Consumer key secret",
    )
    twitter_access_token: str = Field(
        default="",
        description="Access Token (under Authentication Tokens)",
    )
    twitter_access_token_secret: str = Field(
        default="",
        description="Access Token Secret",
    )

    # === Twitter API v2 — OAuth 2.0 User Context ===
    twitter_oauth2_client_id: str = Field(default="")
    twitter_oauth2_client_secret: str = Field(default="")
    twitter_oauth2_access_token: str = Field(default="")
    twitter_oauth2_refresh_token: str = Field(default="")

    # === OpenRouter (single API key for ALL LLMs including Grok) ===
    openrouter_api_key: str = Field(default="")
    openrouter_model_primary: str = Field(
        default="anthropic/claude-sonnet-4",
        description="Primary model for routine tasks",
    )
    openrouter_model_hard: str = Field(
        default="x-ai/grok-4.3",
        description="Hard model for complex reasoning (engine, followup)",
    )
    openrouter_model_grok: str = Field(
        default="x-ai/grok-4",
        description="Grok model for response analysis",
    )

    # === Target Configuration ===
    target_handle: str = Field(
        default="HackingA0",
        description="Target Twitter handle (without @)",
    )
    our_bot_handle: str = Field(
        default="",
        description="Our bot's Twitter handle (without @)",
    )

    # === Operational Parameters ===
    poll_interval_seconds: int = Field(
        default=30,
        description="How often to check for new tweets (seconds)",
    )
    post_cooldown_seconds: int = Field(
        default=60,
        description="Minimum time between our posts (seconds)",
    )
    max_tweets_per_hour: int = Field(
        default=50,
        description="Rate limit safety margin",
    )
    reply_timeout_seconds: int = Field(
        default=3600,
        description="How long to wait for bot reply (seconds)",
    )
    tap_width: int = Field(
        default=10,
        description="TAP tree width (top-w pruning)",
    )
    tap_depth: int = Field(
        default=10,
        description="TAP tree depth levels",
    )
    tap_branching: int = Field(
        default=4,
        description="Variants per leaf node",
    )

    # === Paths ===
    db_path: str = Field(
        default="data/tap.db",
        description="SQLite database file path",
    )
    ssot_path: str = Field(
        default="data/hackinga0_analysis.md",
        description="SSOT living markdown document path",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings singleton.

    Loads from .env file on first call, then returns cached instance.
    Call with no arguments — all configuration comes from environment.
    """
    return Settings()