"""Controlled-clock multi-day acceptance extension; not elapsed soak or restart proof."""
from datetime import datetime, timedelta
from typing import get_args

import pytest

pytestmark = pytest.mark.freeze_time(real_asyncio=True)

# ``tasks.create`` is a real registered action, but its handler lazily imports
# ``core.board_service`` / ``api.schemas.board_schemas`` on the dispatch path.
# Pydantic builds those schemas at class-creation time from the ``datetime``
# class in module globals.  If that first import happens while the marker above
# has frozen the clock, the schema captures ``freezegun.api.FakeDatetime`` and
# the real action fails before it touches the board.  Import the production
# module here -- collection runs before any test-level freeze -- so the
# acceptance path exercises the real action instead of an import-order
# artifact.  No expected task, receipt, or Oracle assertion is changed.
import core.board_service  # noqa: E402,F401

import tests.test_agent_generic_information_wait as original  # noqa: E402
from tests.test_agent_run_outcome_join_contract import real_env  # noqa: E402

_REAL_DATETIME = datetime


def _delay_answers(monkeypatch, freezer, days):
    answer = original._wait_answer
    observed = []
    def delayed(*args, **kwargs):
        freezer.tick(timedelta(days=days))
        observed.append(days)
        return answer(*args, **kwargs)
    monkeypatch.setattr(original, '_wait_answer', delayed)
    return observed


def test_action_schema_was_built_with_real_datetime():
    """Positive/negative isolation for the hosted import-order failure.

    The production ``TaskCreate`` schema must be built from the real
    ``datetime`` class while this module's clock is frozen.  Before the
    module-level preload above, the first ``tasks.create`` import happened
    inside the frozen resumed pass, so Pydantic rejected
    ``freezegun.api.FakeDatetime`` and the real action failed before writing.
    This control invokes no action, server, or model.
    """
    from api.schemas.board_schemas import TaskCreate

    annotation = TaskCreate.model_fields["due_at"].annotation
    assert _REAL_DATETIME in get_args(annotation)
    assert "FakeDatetime" not in repr(annotation)


@pytest.mark.parametrize('days', [3, 14])
def test_same_job_verified_result_after_multiday_wait(real_env, monkeypatch, freezer, days):
    observed = _delay_answers(monkeypatch, freezer, days)
    original.test_generic_info_wait_resumes_same_job_to_verified_result(real_env, monkeypatch)
    assert observed == [days]


def test_two_missing_facts_span_two_weeks_same_job(real_env, monkeypatch, freezer):
    observed = _delay_answers(monkeypatch, freezer, 7)
    original.test_second_missing_fact_waits_again_then_completes(real_env, monkeypatch)
    assert observed == [7, 7]


def test_late_multiday_answer_cannot_revive_cancelled_job(real_env, monkeypatch, freezer):
    observed = _delay_answers(monkeypatch, freezer, 14)
    original.test_answer_after_cancellation_cannot_revive_the_job(real_env, monkeypatch)
    assert observed == [14]
