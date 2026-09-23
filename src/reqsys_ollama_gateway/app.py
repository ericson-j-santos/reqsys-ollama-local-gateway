from __future__ import annotations

import hmac
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

import httpx
from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel, Field

from .config import Settings, load_settings

app = FastAPI(title="ReqSys Ollama Local Gateway", version="0.2.0")


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)


class ChatCompletionRequest(BaseModel):
    model: str = Field(min_length=1, max_length=128)
    messages: list[ChatMessage] = Field(min_length=1, max_length=100)
    stream: Literal[False] = False


def _correlation_id(value: str | None) -> str:
    return value or str(uuid4())


def _raise_gateway_error(
    *,
    status_code: int,
    code: str,
    correlation_id: str,
    authenticate: bool = False,
) -> None:
    headers = {"X-Correlation-ID": correlation_id}
    if authenticate:
        headers["WWW-Authenticate"] = "Bearer"
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "correlation_id": correlation_id},
        headers=headers,
    )


def _authorize(
    settings: Settings,
    authorization: str | None,
    correlation_id: str,
) -> None:
    if not settings.auth_required:
        return

    if not settings.api_token:
        _raise_gateway_error(
            status_code=503,
            code="gateway_auth_not_configured",
            correlation_id=correlation_id,
        )

    expected = f"Bearer {settings.api_token}"
    if authorization is None or not hmac.compare_digest(authorization, expected):
        _raise_gateway_error(
            status_code=401,
            code="unauthorized",
            correlation_id=correlation_id,
            authenticate=True,
        )


def _token_count(value: object) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


@app.get("/health")
def health(
    response: Response,
    x_correlation_id: str | None = Header(default=None),
) -> dict[str, object]:
    settings = load_settings()
    correlation_id = _correlation_id(x_correlation_id)
    response.headers["X-Correlation-ID"] = correlation_id
    return {
        "status": "ok",
        "service": "reqsys-ollama-local-gateway",
        "env": settings.env,
        "auth_required": settings.auth_required,
        "auth_configured": bool(settings.api_token),
        "correlation_id": correlation_id,
        "generated_at_utc": datetime.now(UTC).isoformat(),
    }


@app.post("/v1/chat/completions")
def chat_completions(
    request: ChatCompletionRequest,
    response: Response,
    x_correlation_id: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    settings = load_settings()
    correlation_id = _correlation_id(x_correlation_id)
    response.headers["X-Correlation-ID"] = correlation_id
    _authorize(settings, authorization, correlation_id)

    payload = {
        "model": request.model,
        "messages": [message.model_dump() for message in request.messages],
        "stream": False,
    }
    upstream_url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"

    try:
        upstream = httpx.post(
            upstream_url,
            json=payload,
            timeout=settings.request_timeout_seconds,
            headers={"X-Correlation-ID": correlation_id},
        )
    except httpx.TimeoutException:
        _raise_gateway_error(
            status_code=504,
            code="ollama_timeout",
            correlation_id=correlation_id,
        )
    except httpx.RequestError:
        _raise_gateway_error(
            status_code=502,
            code="ollama_unavailable",
            correlation_id=correlation_id,
        )

    if upstream.status_code >= 400:
        _raise_gateway_error(
            status_code=502,
            code="ollama_upstream_error",
            correlation_id=correlation_id,
        )

    try:
        upstream_payload = upstream.json()
    except ValueError:
        _raise_gateway_error(
            status_code=502,
            code="ollama_invalid_response",
            correlation_id=correlation_id,
        )

    if not isinstance(upstream_payload, dict):
        _raise_gateway_error(
            status_code=502,
            code="ollama_invalid_response",
            correlation_id=correlation_id,
        )

    upstream_message = upstream_payload.get("message")
    if (
        not isinstance(upstream_message, dict)
        or not isinstance(upstream_message.get("content"), str)
    ):
        _raise_gateway_error(
            status_code=502,
            code="ollama_invalid_response",
            correlation_id=correlation_id,
        )

    prompt_tokens = _token_count(upstream_payload.get("prompt_eval_count"))
    completion_tokens = _token_count(upstream_payload.get("eval_count"))
    model = upstream_payload.get("model")
    if not isinstance(model, str) or not model:
        model = request.model

    finish_reason = upstream_payload.get("done_reason")
    if not isinstance(finish_reason, str) or not finish_reason:
        finish_reason = "stop"

    return {
        "id": f"chatcmpl-{uuid4().hex}",
        "object": "chat.completion",
        "created": int(datetime.now(UTC).timestamp()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": upstream_message["content"],
                },
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
        "correlation_id": correlation_id,
    }
