"""Prova do Ollama local no E2E hermetico; nao instala nem despacha workers."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

import httpx

MODEL = "smollm2:135m"
BASE_URL = "http://127.0.0.1:11434"
PROOF_FILE = Path("artifacts/ollama-gateway-e2e-dev/local-proof.json")
EVIDENCE_FILE = Path("artifacts/ollama-gateway-e2e-dev/evidence.json")


class LocalProofError(RuntimeError):
    """Codigo fechado; nunca inclui corpo HTTP, ambiente ou stderr."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise LocalProofError(code)


def validate_cloud_environment(value: object) -> None:
    require(isinstance(value, list), "cloud_configuration_invalid")
    entries = [v for v in value if isinstance(v, str) and v.startswith("OLLAMA_NO_CLOUD=")]
    require(entries == ["OLLAMA_NO_CLOUD=1"], "cloud_not_explicitly_disabled")


def command_output(argv: list[str]) -> str:
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise LocalProofError("runtime_readback_unavailable") from None
    require(result.returncode == 0, "runtime_readback_failed")
    require(len(result.stdout) <= 1048576, "runtime_readback_too_large")
    return result.stdout.strip()


def cloud_readback() -> None:
    raw = command_output(
        ["docker", "inspect", "--format", "{{json .Config.Env}}", "ollama-e2e"]
    )
    try:
        environment = json.loads(raw)
    except (ValueError, TypeError):
        raise LocalProofError("cloud_configuration_invalid") from None
    validate_cloud_environment(environment)


def local_model(tags: object, show: object) -> str:
    require(isinstance(tags, dict), "model_inventory_invalid")
    models = tags.get("models")
    # O E2E legado escolhe o primeiro modelo: um unico candidato elimina ambiguidade.
    require(isinstance(models, list) and len(models) == 1, "model_inventory_ambiguous")
    item = models[0]
    require(isinstance(item, dict) and item.get("name") == MODEL, "unexpected_model")
    digest = item.get("digest")
    require(isinstance(digest, str) and bool(re.fullmatch(r"[0-9a-f]{64}", digest)),
            "model_digest_invalid")
    require(isinstance(show, dict), "model_metadata_invalid")
    for record in (item, show):
        require(not record.get("remote_host") and not record.get("remote_model"),
                "remote_model_blocked")
    details = show.get("details")
    require(isinstance(details, dict) and details.get("format") == "gguf",
            "local_weights_unproved")
    return digest


def running_model(payload: object, digest: str) -> None:
    require(isinstance(payload, dict) and isinstance(payload.get("models"), list),
            "local_process_inventory_invalid")
    for item in payload["models"]:
        if not isinstance(item, dict):
            continue
        if item.get("name") == MODEL and item.get("digest") == digest:
            size = item.get("size")
            require(type(size) is int and size > 0, "local_process_size_invalid")
            require(not item.get("remote_host") and not item.get("remote_model"),
                    "remote_process_blocked")
            return
    raise LocalProofError("local_process_not_found")


def request_json(client: httpx.Client, method: str, path: str, **kwargs) -> object:
    try:
        response = client.request(method, path, **kwargs)
        require(response.status_code == 200, "ollama_readback_http_error")
        require(len(response.content) <= 1048576, "ollama_readback_too_large")
        return response.json()
    except (httpx.HTTPError, ValueError):
        raise LocalProofError("ollama_readback_unavailable") from None


def validate_identity(record: object, sha: str, correlation: str, result: str) -> None:
    require(isinstance(record, dict), "evidence_invalid")
    require(record.get("expected_sha") == sha, "evidence_sha_mismatch")
    require(record.get("correlation_id") == correlation, "evidence_correlation_mismatch")
    require(record.get("result") == result, "evidence_result_invalid")


def read_json(path: Path) -> object:
    try:
        require(path.stat().st_size <= 1048576, "evidence_too_large")
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise LocalProofError("evidence_unavailable") from None


def write_json(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("preflight", "readback"))
    phase = parser.parse_args(argv).phase
    sha = os.environ.get("EXPECTED_SHA", "")
    correlation = os.environ.get("CORRELATION_ID", "")
    proof = {"result": "LOCAL_PROOF_BLOCKED", "expected_sha": sha,
             "correlation_id": correlation}
    try:
        require(bool(re.fullmatch(r"[0-9a-f]{40}", sha)), "expected_sha_invalid")
        require(bool(re.fullmatch(r"ollama-gateway-e2e-[0-9]+-[0-9]+", correlation)),
                "correlation_invalid")
        require(os.environ.get("GITHUB_ACTIONS") == "true", "hermetic_ci_required")
        require(os.environ.get("OLLAMA_MODEL") == MODEL, "unexpected_model")
        require(command_output(["git", "rev-parse", "HEAD"]) == sha, "checkout_sha_mismatch")
        cloud_readback()
        with httpx.Client(base_url=BASE_URL, timeout=10, trust_env=False,
                          follow_redirects=False) as client:
            if phase == "preflight":
                # Invalida prova residual antes de consultar o runtime.
                write_json(PROOF_FILE, proof)
                tags = request_json(client, "GET", "/api/tags")
                show = request_json(client, "POST", "/api/show", json={"model": MODEL})
                proof["model_digest"] = local_model(tags, show)
                proof["result"] = "LOCAL_PREFLIGHT_OK"
            else:
                previous = read_json(PROOF_FILE)
                require(isinstance(previous, dict), "evidence_invalid")
                require(previous.get("result") in {"LOCAL_PREFLIGHT_OK",
                                                   "LOCAL_INFERENCE_PROVED"},
                        "evidence_result_invalid")
                validate_identity(previous, sha, correlation, previous["result"])
                digest = previous.get("model_digest")
                require(isinstance(digest, str) and bool(re.fullmatch(r"[0-9a-f]{64}", digest)),
                        "model_digest_invalid")
                running_model(request_json(client, "GET", "/api/ps"), digest)
                evidence = read_json(EVIDENCE_FILE)
                validate_identity(evidence, sha, correlation, "E2E_PASSED")
                require(evidence.get("model") == MODEL, "evidence_model_mismatch")
                require(evidence.get("negative_auth_status") == 401
                        and evidence.get("positive_status") == 200,
                        "evidence_controls_missing")
                require(bool(re.fullmatch(r"[0-9a-f]{64}",
                                         str(evidence.get("response_content_sha256", "")))),
                        "response_hash_missing")
                evidence.update({"cloud_disabled_runtime_readback": True,
                                 "local_model_process_readback": True,
                                 "local_model_digest": digest})
                write_json(EVIDENCE_FILE, evidence)
                proof.update({"result": "LOCAL_INFERENCE_PROVED", "model_digest": digest})
        proof["cloud_disabled_runtime_readback"] = True
        write_json(PROOF_FILE, proof)
        print(proof["result"])
        return 0
    except LocalProofError as exc:
        # Reconstroi o registro para nao conservar sucesso anterior.
        write_json(PROOF_FILE, {"result": "LOCAL_PROOF_BLOCKED",
                               "expected_sha": sha if re.fullmatch(r"[0-9a-f]{40}", sha) else "",
                               "correlation_id": correlation if re.fullmatch(
                                   r"ollama-gateway-e2e-[0-9]+-[0-9]+", correlation) else "",
                               "reason_code": str(exc)})
        print("LOCAL_PROOF_BLOCKED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
