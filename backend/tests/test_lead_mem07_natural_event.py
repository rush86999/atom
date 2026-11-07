"""The actual episode event, not a hand-authored error/event bridge, triggers Memento."""
import asyncio
from tests.test_mem07_consolidated_chain import env, _failing_agent, _controlled_memento_llm, TASK
from core.auto_dev.models import SkillCandidate


def test_actual_episode_event_creates_pending_candidate_without_injected_segment(env, monkeypatch):
    from core.auto_dev.event_hooks import event_bus
    from core.auto_dev.reflection_engine import ReflectionEngine
    from core.episode_service import EpisodeService
    monkeypatch.setattr(event_bus, '_fail_handlers', [])
    ReflectionEngine(db=None, failure_threshold=1).register()
    calls = []
    _controlled_memento_llm(monkeypatch, calls)
    async def normal_chain():
        agent = _failing_agent(env)
        context = {'execution_id':env['execution_id'],'tenant_id':env['tenant'].id,'run_id':'lead-natural-event','operation_id':'lead-natural-event'}
        for _ in range(2):
            result = await agent._step_act('unknown.tool', {}, context)
            assert 'Error' in result
        env['db'].expire_all()
        episode = await EpisodeService(env['db']).create_episode_from_execution(env['execution_id'], TASK, outcome='success', success=True, metadata={})
        assert episode.success is False
        # No EpisodeSegment insertion or direct process_failure/TaskEvent call.
        for _ in range(200):
            await asyncio.sleep(0.01)
            with env['factory']() as fresh:
                rows = fresh.query(SkillCandidate).filter(SkillCandidate.agent_id == env['agent'].id).all()
                if rows:
                    assert len(rows) == 1
                    assert rows[0].validation_status == 'pending'
                    assert calls
                    return
        raise AssertionError('actual emitted failure event did not create a pending candidate')
    asyncio.run(normal_chain())
