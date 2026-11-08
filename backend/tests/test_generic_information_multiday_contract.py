"""Controlled-clock multi-day acceptance extension; not elapsed soak or restart proof."""
from datetime import timedelta
import pytest
pytestmark = pytest.mark.freeze_time(real_asyncio=True)

import tests.test_agent_generic_information_wait as original
from tests.test_agent_run_outcome_join_contract import real_env


def _delay_answers(monkeypatch, freezer, days):
    answer = original._wait_answer
    observed = []
    def delayed(*args, **kwargs):
        freezer.tick(timedelta(days=days))
        observed.append(days)
        return answer(*args, **kwargs)
    monkeypatch.setattr(original, '_wait_answer', delayed)
    return observed


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
