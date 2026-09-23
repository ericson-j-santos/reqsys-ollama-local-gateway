from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

import reqsys_ollama_gateway.app as app_module

client = TestClient(app_module.app)


def _disable_auth(monkeypatch) -> None:
    monkeypatch.setenv("REQSYS_AUTH_REQUIRED", "false")
    monkeypatch.delenv("REQSYS_API_TOKEN", raising=False)


def test_models_success_maps_ollama_tags_and_preserves_correlation_id(monkeypatch) -> None:
    _disable_auth(monkeypatch)
    captured: dict[str, object] = {}

    def fake_get(url: str, **kwargs: object) -> httpx.Response:
        captured["url"] = url
        captured["kwargs"] = kwargs
        return httpx.Response(
            200,
            json={
                "models": [
                    {"name": "qwen2.5-coder:7b"},
                    {"name": "smollm2:135m"},
                    {"name": "qwen2.5-coder:7b"},
                ]
            },
        )

    monkeypatch.setattr(app_module.httpx, "get", fake_get)

    response = client.get(
        "/v1/models",
        headers={"X-Correlation-ID": "corr-models-001"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert response.headers["x-correlation-id"] == "corr-models-001"
    assert payload["correlation_id"] == "corr-models-001"
    assert payload["object"] == "list"
    assert payload["data"] == [
        {
            "id": "qwen2.5-coder:7b",
            "object": "model",
            "created": 0,
            "owned_by": "ollama",
        },
        {
            "id": "smollm2:135m",
            "object": "model",
            "created": 0,
            "owned_by": "ollama",
        },
    ]
    assert captured["url"] == "http://localhost:11434/api/tags"
    forwarded = captured["kwargs"]
    assert isinstance(forwarded, dict)
    assert forwarded["headers"] == {"X-Correlation-ID": "corr-models-001"}


def test_models_requires_valid_bearer_token(monkeypatch) -> None:
    monkeypatch.setenv("REQSYS_AUTH_REQUIRED", "true")
    monkeypatch.setenv("REQSYS_API_TOKEN", "expected-token")

    response = client.get(
        "/v1/models",
        headers={"Authorization": "Bearer wrong-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "unauthorized"
    assert response.headers["www-authenticate"] == "Bearer"


def test_models_normalizes_timeout(monkeypatch) -> None:
    _disable_auth(monkeypatch)

    def fake_get(*args: object, **kwargs: object) -> httpx.Response:
        raise httpx.ReadTimeout("upstream timeout")

    monkeypatch.setattr(app_module.httpx, "get", fake_get)

    response = client.get("/v1/models")

    assert response.status_code == 504
    assert response.json()["detail"]["code"] == "ollama_timeout"
    assert "upstream timeout" not in response.text


def test_models_hides_upstream_error_body(monkeypatch) -> None:
    _disable_auth(monkeypatch)

    def fake_get(*args: object, **kwargs: object) -> httpx.Response:
        return httpx.Response(500, text="secret-upstream-detail")

    monkeypatch.setattr(app_module.httpx, "get", fake_get)

    response = client.get("/v1/models")

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "ollama_upstream_error"
    assert "secret-upstream-detail" not in response.text


def test_models_rejects_invalid_upstream_shape(monkeypatch) -> None:
    _disable_auth(monkeypatch)

    def fake_get(*args: object, **kwargs: object) -> httpx.Response:
        return httpx.Response(200, json={"models": "invalid"})

    monkeypatch.setattr(app_module.httpx, "get", fake_get)

    response = client.get("/v1/models")

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "ollama_invalid_response"
