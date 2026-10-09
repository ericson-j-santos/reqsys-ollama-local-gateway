from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("local_ollama_proof",
                                            ROOT / "scripts/local_ollama_proof.py")
proof = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proof)
DIGEST = "a" * 64
SHA = "b" * 40
CORRELATION = "ollama-gateway-e2e-123-1"


def tags():
    return {"models": [{"name": proof.MODEL, "digest": DIGEST}]}


def show():
    return {"details": {"format": "gguf"}}


def process():
    return {"models": [{"name": proof.MODEL, "digest": DIGEST, "size": 1000000}]}


@pytest.mark.parametrize("environment", [
    None, {}, [], ["OLLAMA_NO_CLOUD=0"], ["OLLAMA_NO_CLOUD=true"],
    ["OLLAMA_NO_CLOUD=1", "OLLAMA_NO_CLOUD=0"], ["OLLAMA_NO_CLOUD=1"] * 2,
])
def test_cloud_unknown_or_enabled_is_blocked(environment):
    with pytest.raises(proof.LocalProofError):
        proof.validate_cloud_environment(environment)


def test_cloud_disabled_readback():
    proof.validate_cloud_environment(["PATH=/bin", "OLLAMA_NO_CLOUD=1"])


@pytest.mark.parametrize("change", [
    "empty", "multiple", "wrong_model", "digest_missing", "digest_invalid", "remote_tag",
    "remote_show", "remote_model", "metadata_missing", "weights_unproved",
])
def test_model_preflight_fail_closed(change):
    inventory, metadata = tags(), show()
    if change == "empty":
        inventory["models"] = []
    elif change == "multiple":
        inventory["models"] *= 2
    elif change == "wrong_model":
        inventory["models"][0]["name"] = "not-the-approved-model:cloud"
    elif change == "digest_missing":
        inventory["models"][0].pop("digest")
    elif change == "digest_invalid":
        inventory["models"][0]["digest"] = "invalid"
    elif change == "remote_tag":
        inventory["models"][0]["remote_host"] = "https://example.invalid"
    elif change == "remote_show":
        metadata["remote_host"] = "https://example.invalid"
    elif change == "remote_model":
        metadata["remote_model"] = "cloud-model"
    elif change == "metadata_missing":
        metadata = None
    else:
        metadata["details"]["format"] = "unknown"
    with pytest.raises(proof.LocalProofError):
        proof.local_model(inventory, metadata)


def test_expected_local_model_and_replay():
    assert proof.local_model(tags(), show()) == DIGEST
    assert proof.local_model(tags(), show()) == DIGEST
    proof.running_model(process(), DIGEST)


@pytest.mark.parametrize("change", ["empty", "digest", "name", "size", "boolean", "remote"])
def test_process_requires_matching_loaded_model(change):
    inventory = process()
    if change == "empty":
        inventory["models"] = []
    elif change == "digest":
        inventory["models"][0]["digest"] = "c" * 64
    elif change == "name":
        inventory["models"][0]["name"] = "other:latest"
    elif change == "size":
        inventory["models"][0]["size"] = 0
    elif change == "boolean":
        inventory["models"][0]["size"] = True
    else:
        inventory["models"][0]["remote_host"] = "https://example.invalid"
    with pytest.raises(proof.LocalProofError):
        proof.running_model(inventory, DIGEST)


@pytest.mark.parametrize("status", [301, 401, 404, 500])
def test_http_errors_and_redirects_fail_closed(status):
    with httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(status, json={"error": "PRIVATE_VALUE"})
    ), base_url=proof.BASE_URL) as client, pytest.raises(proof.LocalProofError) as error:
        proof.request_json(client, "GET", "/api/tags")
    assert "PRIVATE_VALUE" not in str(error.value)


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("EXPECTED_SHA", SHA)
    monkeypatch.setenv("CORRELATION_ID", CORRELATION)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("OLLAMA_MODEL", proof.MODEL)
    monkeypatch.setattr(proof, "PROOF_FILE", tmp_path / "local-proof.json")
    monkeypatch.setattr(proof, "EVIDENCE_FILE", tmp_path / "evidence.json")
    state = {"cloud": ["OLLAMA_NO_CLOUD=1"], "process": process(), "calls": []}

    def command(argv, **kwargs):
        assert kwargs["timeout"] == 10 and kwargs["check"] is False
        if argv == ["git", "rev-parse", "HEAD"]:
            return SimpleNamespace(returncode=0, stdout=SHA + "\n")
        assert argv == ["docker", "inspect", "--format", "{{json .Config.Env}}", "ollama-e2e"]
        return SimpleNamespace(returncode=0, stdout=json.dumps(state["cloud"]))
    monkeypatch.setattr(proof.subprocess, "run", command)

    def transport(request):
        assert request.url.host == "127.0.0.1"
        state["calls"].append((request.method, request.url.path))
        data = {"/api/tags": tags(), "/api/show": show(), "/api/ps": state["process"]}
        assert request.url.path in data, "the verifier must never generate or pull a model"
        return httpx.Response(200, json=data[request.url.path])
    real_client = httpx.Client

    def client(**kwargs):
        assert kwargs["trust_env"] is False and kwargs["follow_redirects"] is False
        return real_client(transport=httpx.MockTransport(transport), **kwargs)
    monkeypatch.setattr(proof.httpx, "Client", client)
    return state


def gateway_evidence():
    return {"result": "E2E_PASSED", "expected_sha": SHA, "correlation_id": CORRELATION,
            "model": proof.MODEL, "negative_auth_status": 401, "positive_status": 200,
            "response_content_sha256": "d" * 64}


def test_full_proof_replay_and_independent_readback(runtime):
    assert proof.main(["preflight"]) == 0
    first = proof.PROOF_FILE.read_bytes()
    assert proof.main(["preflight"]) == 0
    assert proof.PROOF_FILE.read_bytes() == first
    proof.write_json(proof.EVIDENCE_FILE, gateway_evidence())
    assert proof.main(["readback"]) == 0
    terminal = proof.PROOF_FILE.read_bytes()
    assert proof.main(["readback"]) == 0
    assert proof.PROOF_FILE.read_bytes() == terminal
    evidence = json.loads(proof.EVIDENCE_FILE.read_text())
    assert evidence["local_model_digest"] == DIGEST
    assert evidence["local_model_process_readback"] is True
    assert runtime["calls"].count(("GET", "/api/ps")) == 2


def test_cloud_control_stops_before_http_and_clears_old_proof(runtime):
    proof.write_json(proof.PROOF_FILE, {"result": "LOCAL_INFERENCE_PROVED"})
    runtime["cloud"] = ["OLLAMA_NO_CLOUD=0"]
    assert proof.main(["preflight"]) == 1
    assert runtime["calls"] == []
    assert proof.read_json(proof.PROOF_FILE)["result"] == "LOCAL_PROOF_BLOCKED"


@pytest.mark.parametrize("field", ["expected_sha", "correlation_id", "model",
                                   "negative_auth_status", "response_content_sha256"])
def test_stale_or_invalid_gateway_evidence_is_blocked(runtime, field):
    assert proof.main(["preflight"]) == 0
    evidence = gateway_evidence()
    evidence[field] = "invalid"
    proof.write_json(proof.EVIDENCE_FILE, evidence)
    assert proof.main(["readback"]) == 1
    assert proof.read_json(proof.PROOF_FILE)["result"] == "LOCAL_PROOF_BLOCKED"
    assert "local_model_process_readback" not in proof.read_json(proof.EVIDENCE_FILE)


def test_empty_process_cannot_reuse_previous_success(runtime):
    assert proof.main(["preflight"]) == 0
    proof.write_json(proof.EVIDENCE_FILE, gateway_evidence())
    assert proof.main(["readback"]) == 0
    runtime["process"] = {"models": []}
    assert proof.main(["readback"]) == 1
    assert proof.read_json(proof.PROOF_FILE)["result"] == "LOCAL_PROOF_BLOCKED"


def test_workflow_requires_no_cloud_and_local_readback():
    content = (ROOT / ".github/workflows/e2e-ollama-dev.yml").read_text()
    assert "-e OLLAMA_NO_CLOUD=1" in content
    assert "-p 127.0.0.1:11434:11434" in content
    assert content.index("local_ollama_proof.py preflight") < content.index("e2e_ollama_dev.py")
    assert content.index("e2e_ollama_dev.py") < content.index("local_ollama_proof.py readback")
    assert 'proof["result"] == "LOCAL_INFERENCE_PROVED"' in content
    assert "cloud_disabled_runtime_readback" in content
    assert "local_model_process_readback" in content
