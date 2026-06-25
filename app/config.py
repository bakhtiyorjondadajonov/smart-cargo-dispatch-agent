"""Application settings loaded from environment / .env."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "sqlite:///./dev.db"

    # Gemini (the agent brain)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    # 0 disables "thinking" on gemini-2.5-flash -> much lower latency for this
    # pick-nearest task. Raise it only if ranking quality needs deliberation.
    gemini_thinking_budget: int = 0
    gemini_max_retries: int = 2  # transient-error retries before falling back

    # Matching concurrency (threadpool size for matching a batch of requests)
    match_concurrency: int = 4

    # Matching / location
    location_mode: str = "mixed"  # named | gps | mixed
    candidate_top_n: int = 10
    max_radius_km: float = 600.0

    # Request generator
    enable_scheduler: bool = True
    generator_min_minutes: float = 1.0
    generator_max_minutes: float = 10.0
    generator_batch_size: int = 2
    auto_seed: bool = True


settings = Settings()
