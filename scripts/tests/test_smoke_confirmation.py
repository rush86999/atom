"""No-network confirmation-branch tests for the deployment smoke.

The tests load both the development smoke and the packaged release smoke, mock
the HTTP/session seams, capture every outgoing confirmation, and check the
captured strings against the frozen candidate's actual classifier.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

DEV_SMOKE = Path(__file__).resolve().parents[1] / "smoke_release_candidate_ae0c2fda3.py"
PACKAGED_SMOKE = Path(os.environ.get(
    "ATOM_RELEASE_SMOKE_PATH",
    "/Users/rushiparikh/projects/atom-releases/c072b62e9/scripts/"
    "smoke_release_candidate_ae0c2fda3.py",
))
CANDIDATE_BACKEND = Path(os.environ.get(
    "ATOM_CANDIDATE_BACKEND",
    "/Users/rushiparikh/projects/atom-releases/c072b62e9/backend",
))
VERBOSE_CONFIRMATIONS = (
    "Yes, go ahead. This is the confirmation — run the saved workbook lookup "
    "now and return the requested result with the source rows.",
    "Yes, go ahead. This is the confirmation — run the saved workbook lookup "
    "now.",
)


def load_smoke(path: Path):
    if not path.is_file():
        pytest.skip(f"smoke script not present: {path}")
    spec = importlib.util.spec_from_file_location(
        f"smoke_under_test_{uuid.uuid4().hex}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AskRecorder:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, base, token, user_id, agent_id, message,
                 session_id=None):
        self.calls.append({
            "base": base,
            "token": token,
            "user_id": user_id,
            "agent_id": agent_id,
            "message": message,
            "session_id": session_id,
        })
        response = self.responses.pop(0)
        result = {
            "http": 200,
            "session_id": session_id or "session-1",
            "execution_id": "exec-1",
            "success": True,
            "outcome": "completed",
            "error_code": None,
            "message": "ok",
        }
        result.update(response)
        return result


def pending_session(db_path, session_id):
    return {"_pending_file_task": {"status": "pending"}}


def no_pending_session(db_path, session_id):
    return {}


@pytest.mark.parametrize(
    "smoke_path", (DEV_SMOKE, PACKAGED_SMOKE),
    ids=("development", "packaged"),
)
def test_confirmation_and_retry_use_go_ahead_in_same_session(
        smoke_path, monkeypatch):
    module = load_smoke(smoke_path)
    assert module.CONFIRM_PENDING_READ == "go ahead"

    recorder = AskRecorder([
        {"session_id": "session-42", "success": True, "outcome": "partial",
         "message": "The workbook lookup hasn't run yet — confirm to proceed."},
        {"session_id": "session-42", "error_code": "turn_budget_exceeded"},
        {"session_id": "session-42"},
    ])
    monkeypatch.setattr(module, "ask", recorder)
    monkeypatch.setattr(module, "session_meta", pending_session)

    record = module.ask_confirmed(
        "/tmp/does-not-matter.db", "http://candidate", "token-abc",
        "user-abc", "agent-abc", "original ask")

    assert [call["message"] for call in recorder.calls] == [
        "original ask", "go ahead", "go ahead"]
    assert [call["session_id"] for call in recorder.calls] == [
        None, "session-42", "session-42"]
    assert all(call["token"] == "token-abc" for call in recorder.calls)
    assert all(call["user_id"] == "user-abc" for call in recorder.calls)
    assert all(call["agent_id"] == "agent-abc" for call in recorder.calls)
    assert record["confirmation_sent"] is True
    assert record["final"] is record["budget_retry"]


@pytest.mark.parametrize(
    "smoke_path", (DEV_SMOKE, PACKAGED_SMOKE),
    ids=("development", "packaged"),
)
def test_confirmation_without_retry_stays_in_session(smoke_path, monkeypatch):
    module = load_smoke(smoke_path)
    recorder = AskRecorder([
        {"session_id": "session-7", "success": True, "outcome": "partial",
         "message": "The workbook lookup hasn't run yet — confirm to proceed."},
        {"session_id": "session-7"},
    ])
    monkeypatch.setattr(module, "ask", recorder)
    monkeypatch.setattr(module, "session_meta", pending_session)

    record = module.ask_confirmed(
        "/tmp/does-not-matter.db", "http://candidate", "token-xyz",
        "user-xyz", "agent-xyz", "original ask")

    assert [call["message"] for call in recorder.calls] == [
        "original ask", "go ahead"]
    assert [call["session_id"] for call in recorder.calls] == [
        None, "session-7"]
    assert record["confirmation_sent"] is True
    assert record["final"] is record["second"]


@pytest.mark.parametrize(
    "smoke_path", (DEV_SMOKE, PACKAGED_SMOKE),
    ids=("development", "packaged"),
)
def test_no_confirmation_branch_makes_one_request(smoke_path, monkeypatch):
    module = load_smoke(smoke_path)
    recorder = AskRecorder([{"session_id": "session-plain"}])
    monkeypatch.setattr(module, "ask", recorder)
    monkeypatch.setattr(module, "session_meta", no_pending_session)

    record = module.ask_confirmed(
        "/tmp/does-not-matter.db", "http://candidate", "token", "user",
        "agent", "just answer the question")

    assert [call["message"] for call in recorder.calls] == [
        "just answer the question"]
    assert record["confirmation_sent"] is False
    assert record["final"] is record["first"]


@pytest.mark.parametrize("smoke_path", (DEV_SMOKE, PACKAGED_SMOKE),
                         ids=("development", "packaged"))
def test_stale_pending_after_valid_answer_does_not_confirm(
        smoke_path, monkeypatch):
    module = load_smoke(smoke_path)
    recorder = AskRecorder([
        {"session_id": "session-valid", "success": True, "outcome": None,
         "message": "Workbook: `sheet.xlsx`; known subtotal -700.00 CAD; "
                    "gap 0055 at C5; grand total withheld."},
    ])
    monkeypatch.setattr(module, "ask", recorder)
    monkeypatch.setattr(module, "session_meta", pending_session)

    record = module.ask_confirmed(
        "/tmp/does-not-matter.db", "http://candidate", "token", "user",
        "agent", "original ask")

    assert [call["message"] for call in recorder.calls] == ["original ask"]
    assert record["confirmation_sent"] is False
    assert record["final"] is record["first"]


def _candidate_classifier(message: str) -> bool:
    if not CANDIDATE_BACKEND.is_dir():
        pytest.fail(f"candidate backend not present: {CANDIDATE_BACKEND}")
    code = (
        "import sys; sys.path.insert(0, '.'); "
        "from core.pending_file_task import is_filename_confirmation; "
        "print(is_filename_confirmation(sys.argv[1]))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, message],
        cwd=str(CANDIDATE_BACKEND),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip() == "True"


@pytest.mark.parametrize("smoke_path", (DEV_SMOKE, PACKAGED_SMOKE),
                         ids=("development", "packaged"))
def test_captured_confirmations_match_candidate_classifier(
        smoke_path, monkeypatch):
    module = load_smoke(smoke_path)
    recorder = AskRecorder([
        {"session_id": "session-99", "success": True, "outcome": "partial",
         "message": "The workbook lookup hasn't run yet — confirm to proceed."},
        {"session_id": "session-99", "error_code": "turn_budget_exceeded"},
        {"session_id": "session-99"},
    ])
    monkeypatch.setattr(module, "ask", recorder)
    monkeypatch.setattr(module, "session_meta", pending_session)
    module.ask_confirmed(
        "/tmp/does-not-matter.db", "http://candidate", "token", "user",
        "agent", "original ask")

    confirmations = [call["message"] for call in recorder.calls[1:]]
    assert confirmations == ["go ahead", "go ahead"]
    for message in confirmations:
        assert _candidate_classifier(message) is True, message


def test_candidate_classifier_rejects_old_verbose_confirmations():
    assert _candidate_classifier("go ahead") is True
    for message in VERBOSE_CONFIRMATIONS:
        assert _candidate_classifier(message) is False, message
