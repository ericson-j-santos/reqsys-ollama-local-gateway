import pytest

from reqsys_ollama_gateway.config import load_settings


def test_load_settings_defaults(monkeypatch) -> None:
    monkeypatch.delenv("REQSYS_ENV", raising=False)
    monkeypatch.delenv("REQSYS_AUTH_REQUIRED", raising=False)
    monkeypatch.delenv("REQSYS_API_TOKEN", raising=False)
    monkeypatch.delenv("REQSYS_OLLAMA_BASE_URL", raising=False)
    monkeypatch.delenv("REQSYS_OLLAMA_TIMEOUT_SECONDS", raising=False)

    settings = load_settings()

    assert settings.env == "dev"
    assert settings.auth_required is True
    assert settings.api_token is None
    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.request_timeout_seconds == 30


def test_load_settings_rejects_invalid_timeout(monkeypatch) -> None:
    monkeypatch.setenv("REQSYS_OLLAMA_TIMEOUT_SECONDS", "0")

    with pytest.raises(RuntimeError, match="deve estar entre"):
        load_settings()
