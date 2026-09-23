from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

import httpx


OLLAMA_URL = "http://127.0.0.1:11434"
GATEWAY_URL = "http://127.0.0.1:18008"


def fail(message: str) -> None:
    raise RuntimeError(message)


def wait_for_gateway(timeout_seconds: float = 20.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{GATEWAY_URL}/health", timeout=2.0)
            if response.status_code == 200:
                return
        except httpx.RequestError:
            pass
        time.sleep(0.5)
    fail("gateway_health_timeout")


def choose_model() -> str:
    response = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=10.0)
    response.raise_for_status()
    payload = response.json()
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list) or not models:
        fail("ollama_has_no_models")
    for item in models:
        if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"]:
            return item["name"]
    fail("ollama_model_name_missing")


def main() -> int:
    expected_sha = os.environ["EXPECTED_SHA"]
    correlation_id = os.environ["CORRELATION_ID"]
    evidence_file = Path(os.environ["EVIDENCE_FILE"])
    host = os.environ.get("COMPUTERNAME", "unknown")

    model = choose_model()
    token = secrets.token_urlsafe(32)

    env = os.environ.copy()
    env.update(
        {
            "REQSYS_ENV": "dev",
            "REQSYS_OLLAMA_BASE_URL": OLLAMA_URL,
            "REQSYS_AUTH_REQUIRED": "true",
            "REQSYS_API_TOKEN": token,
            "REQSYS_OLLAMA_TIMEOUT_SECONDS": "60",
        }
    )

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "reqsys_ollama_gateway.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            "18008",
            "--log-level",
            "warning",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    evidence: dict[str, object] = {
        "result": "E2E_BLOCKED",
        "expected_sha": expected_sha,
        "host": host,
        "correlation_id": correlation_id,
        "ollama_url": OLLAMA_URL,
        "gateway_url": GATEWAY_URL,
        "model": model,
        "ollama_tags_readback": True,
        "negative_auth_status": None,
        "positive_status": None,
        "response_content_sha256": None,
        "production_touched": False,
        "deploy_executed": False,
    }

    try:
        wait_for_gateway()

        request_payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": "Responda somente com uma confirmação curta de que recebeu esta mensagem.",
                }
            ],
            "stream": False,
        }

        negative = httpx.post(
            f"{GATEWAY_URL}/v1/chat/completions",
            headers={
                "Authorization": "Bearer invalid-e2e-token",
                "X-Correlation-ID": f"{correlation_id}-negative",
            },
            json=request_payload,
            timeout=10.0,
        )
        evidence["negative_auth_status"] = negative.status_code
        if negative.status_code != 401:
            fail(f"negative_auth_expected_401_got_{negative.status_code}")

        positive = httpx.post(
            f"{GATEWAY_URL}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Correlation-ID": correlation_id,
            },
            json=request_payload,
            timeout=90.0,
        )
        evidence["positive_status"] = positive.status_code
        if positive.status_code != 200:
            fail(f"positive_expected_200_got_{positive.status_code}")

        payload = positive.json()
        if payload.get("correlation_id") != correlation_id:
            fail("correlation_id_mismatch")
        if payload.get("model") != model:
            fail("model_mismatch")

        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            fail("choices_missing")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            fail("assistant_content_missing")

        evidence["response_content_sha256"] = hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest()
        evidence["result"] = "E2E_PASSED"
        return 0
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        evidence_file.parent.mkdir(parents=True, exist_ok=True)
        evidence_file.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


if __name__ == "__main__":
    raise SystemExit(main())
