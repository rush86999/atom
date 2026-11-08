"""Root independent behavior probe; no dependency on proposed receipt layout."""
from tests.test_assignment_routes import route_env  # noqa:F401
from tests.test_assignment_external_reply_identity import _open_wait, _reply, _wait


def test_same_reply_identity_cannot_change_into_a_resolving_answer(route_env, tmp_path, monkeypatch):
    run_id, correlation, artifact_root = _open_wait(route_env, tmp_path, monkeypatch, requested_output="document")
    first = _reply(route_env, run_id, correlation, reply_id="root-reply-1", value="5", response="received 5 units")
    assert first.status_code == 200 and first.json()["status"] == "conflict", first.text
    changed = _reply(route_env, run_id, correlation, reply_id="root-reply-1", value="2", response="received 2 units")
    state = route_env["lifecycle"].get_assignment(run_id)
    capture = {"http": changed.status_code, "reply_status": changed.json().get("status"), "assignment_status": state["status"], "wait_status": _wait(route_env, run_id)["status"], "artifact_files": sum(p.is_file() for p in artifact_root.rglob("*"))}
    assert changed.status_code == 409 or capture["reply_status"] in ("conflict", "refused", "reply_conflict"), capture
    assert capture["wait_status"] == "waiting", capture
    assert capture["artifact_files"] == 0, capture
