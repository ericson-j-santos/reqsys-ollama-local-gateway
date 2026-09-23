from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    env: str
    ollama_base_url: str
    auth_required: bool
    api_token: str | None
    allowed_origins: tuple[str, ...]
    request_timeout_seconds: float

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "prod"


def _load_timeout_seconds() -> float:
    raw_value = os.getenv("REQSYS_OLLAMA_TIMEOUT_SECONDS", "30")
    try:
        timeout = float(raw_value)
    except ValueError as exc:
        raise RuntimeError("REQSYS_OLLAMA_TIMEOUT_SECONDS invalido") from exc

    if timeout <= 0 or timeout > 120:
        raise RuntimeError("REQSYS_OLLAMA_TIMEOUT_SECONDS deve estar entre 0 e 120")
    return timeout


def load_settings() -> Settings:
    env = os.getenv("REQSYS_ENV", "dev")
    origins = tuple(
        origin.strip()
        for origin in os.getenv("REQSYS_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
        if origin.strip()
    )
    api_token = os.getenv("REQSYS_API_TOKEN") or None
    settings = Settings(
        env=env,
        ollama_base_url=os.getenv("REQSYS_OLLAMA_BASE_URL", "http://localhost:11434"),
        auth_required=os.getenv("REQSYS_AUTH_REQUIRED", "true").lower() == "true",
        api_token=api_token,
        allowed_origins=origins,
        request_timeout_seconds=_load_timeout_seconds(),
    )
    if settings.is_production and not settings.auth_required:
        raise RuntimeError("Auth obrigatoria em producao")
    if settings.is_production and "*" in settings.allowed_origins:
        raise RuntimeError("CORS wildcard bloqueado em producao")
    return settings
