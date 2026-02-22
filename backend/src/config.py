"""Configuration management for the agent orchestrator platform."""

from functools import lru_cache
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "Agent Orchestrator"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/orchestrator.db"

    # JWT Authentication
    jwt_secret_key: str = Field(default="change-me-in-production-use-secrets")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24  # 24 hours
    jwt_refresh_token_expire_days: int = 7

    # LLM Configuration
    default_llm_model: str = "claude-sonnet-4-20250514"
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    crusoe_api_key: Optional[str] = None
    crusoe_api_base: str = "https://hackeurope.crusoecloud.com/v1"

    # MCP Configuration
    mcp_connection_timeout: int = 30  # seconds
    mcp_request_timeout: int = 120  # seconds

    # Event Bus
    event_bus_max_queue_size: int = 1000

    # GitHub Integration
    github_token: str | None = None
    github_api_base_url: str = "https://api.github.com"

    # Marketplace & Billing
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_seat: str = ""
    paid_api_key: str = ""
    paid_product_id: str = ""
    paid_webhook_secret: str = ""
    platform_commission_rate: float = 0.20
    free_tier_daily_limit: int = 10

    # Token pricing (cost per million tokens, USD)
    anthropic_input_cost_per_m: float = 3.0  # Sonnet input
    anthropic_output_cost_per_m: float = 15.0  # Sonnet output


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def calculate_token_cost(input_tokens: int, output_tokens: int) -> float:
    """Calculate USD cost from token counts using configured rates."""
    settings = get_settings()
    return (
        input_tokens * settings.anthropic_input_cost_per_m
        + output_tokens * settings.anthropic_output_cost_per_m
    ) / 1_000_000
