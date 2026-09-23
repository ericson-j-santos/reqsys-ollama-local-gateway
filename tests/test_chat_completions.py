from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

import reqsys_ollama_gateway.app as app_module

client = TestClient(app_module.app)


def _disable_auth(monkeypatch) -> None:
    monkeypatch.setenv("REQSYS_AUTH_REQUIRED", "false")
    monkeypatch.delenv("REQSYS_API_TOKEN", raising=False)


def test_chat_completion_success_preserves_correlation_id(monkeypatch) -> None:
    _disable_auth(monkeypatch)
    captured: dict[str, object] = {}

    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        captured["url"] = url
        captured["kwargs"] = kwargs
        return httpx.Response(
            200,
            json={
                "model": "qwen2.5-coder:7b",
                "message": {"role": "assistant", "content": "resposta local"},
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 12,
                "eval_count": 8,
            },
        )

    monkeypatch.setattr(app_module.httpx, "post", fake_post)

    response = client.post(
        "/v1/chat/completions",
        headers={"X-Correlation-ID": "corr-test-001"},
        json={
            "model": "qwen2.5-coder:7b",
            "messages": [{"role": "user", "content": "teste"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert response.headers["x-correlation-id"] == "corr-test-001"
    assert payload["correlation_id"] == "corr-test-001"
    assert payload["choices"][0]["message"]["content"] == "resposta local"
    assert payload["usage"] == {
        "prompt_tokens": 12,
        "completion_tokens": 8,
        "total_tokens": 20,
    }
    assert captured["url"] == "http://localhost:11434/api/chat"
    forwarded = captured["kwargs"]
    assert isinstance(forwarded, dict)
    assert forwarded["headers"] == {"X-Correlation-ID": "corr-test-001"}


def test_chat_completion_requires_valid_bearer_token(monkeypatch) -> None:
    monkeypatch.setenv("REQSYS_AUTH_REQUIRED", "true")
    monkeypatch.setenv("REQSYS_API_TOKEN", "expected-token")

    response = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer wrong-token"},
        json={
            "model": "qwen2.5-coder:7b",
            "messages": [{"role": "user", "content": "teste"}],
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "unauthorized"
    assert response.headers["www-authenticate"] == "Bearer"


def test_chat_completion_fails_closed_when_auth_not_configured(monkeypatch) -> None:
    monkeypatch.setenv("REQSYS_AUTH_REQUIRED", "true")
    monkeypatch.delenv("REQSYS_API_TOKEN", raising=False)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "qwen2.5-coder:7b",
            "messages": [{"role": "user", "content": "teste"}],
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "gateway_auth_not_configured"


def test_chat_completion_normalizes_timeout(monkeypatch) -> None:
    _disable_auth(monkeypatch)

    def fake_post(*args: object, **kwargs: object) -> httpx.Response:
        raise httpx.ReadTimeout("upstream timeout")

    monkeypatch.setattr(app_module.httpx, "post", fake_post)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "qwen2.5-coder:7b",
            "messages": [{"role": "user", "content": "teste"}],
        },
    )

    assert response.status_code == 504
    assert response.json()["detail"]["code"] == "ollama_timeout"
    assert "upstream timeout" not in response.text


def test_chat_completion_hides_upstream_error_body(monkeypatch) -> None:
    _disable_auth(monkeypatch)

    def fake_post(*args: object, **kwargs: object) -> httpx.Response:
        return httpx.Response(500, text="secret-upstream-detail")

    monkeypatch.setattr(app_module.httpx, "post", fake_post)

    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "qwen2.5-coder:7b",
            "messages": [{"role": "user", "content": "teste"}],
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "ollama_upstream_error"
    assert "secret-upstream-detail" not in response.text


def test_chat_completion_rejects_streaming() -> None:
    response = client.post(
        "/v1/chat/completions",
        json={
            "model": "qwen2.5-coder:7b",
            "messages": [{"role": "user", "content": "teste"}],
            "stream": True,
        },
    )

    assert response.status_code == 422
