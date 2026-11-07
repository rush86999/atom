"""Finite startup boundary and truthful counters over real scratch job rows.

Only the per-wait continuation leaf is controlled by the existing recovery
fixture. These controls qualify selection/accounting, not model or UI quality.
"""
from tests.test_generic_information_wait_recovery import world, _wait, _drain
from core.models import AgentJob


def test_drain_counts_unanswered_rows_and_all_accepted_batches(world, monkeypatch):
    for _ in range(10):
        _wait(world, status="pending", feedback=None)
    accepted = [_wait(world) for _ in range(21)]
    result, calls = _drain(world, monkeypatch, batch_size=7)
    assert result["complete"] is True, result
    assert result["scanned_jobs"] == 31, result
    assert result["resumed"] == 21, result
    assert set(calls) == {item.action_id for item in accepted}
    second, calls = _drain(world, monkeypatch, batch_size=7)
    assert second["scanned_jobs"] == 10, second
    assert second["resumed"] == 0 and calls == [], second


def test_startup_drain_does_not_extend_to_later_admitted_jobs(world, monkeypatch):
    import core.information_wait as waits
    _wait(world, status="pending", feedback=None)
    original_page = waits._eligible_accepted_page
    visited = []

    def page(*args, **kwargs):
        result = original_page(*args, **kwargs)
        visited.append(result[1])
        if len(visited) == 1:
            with world.SessionLocal() as db:
                db.add(AgentJob(id="zzzz-admitted-after-boot", agent_id="a1",
                                status="waiting", result_summary="{}"))
                db.commit()
        return result

    monkeypatch.setattr(waits, "_eligible_accepted_page", page)
    result, calls = _drain(world, monkeypatch, batch_size=1)
    assert "zzzz-admitted-after-boot" not in visited, visited
    assert result["complete"] is True and calls == [], result
    assert result["scanned_jobs"] == 1, result
