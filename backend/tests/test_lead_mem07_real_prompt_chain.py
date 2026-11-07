"""The same naturally generated/reviewed candidate reaches a fresh agent's final model request."""
import asyncio
from tests.test_mem07_consolidated_chain import env, _pending_candidate_from_tool_error, _approve_and_apply, TASK


def test_natural_error_reviewed_skill_reaches_fresh_agent_actual_request(env, monkeypatch):
    from core.generic_agent import GenericAgent
    from core.models import AgentRegistry
    from core.react_models import ReActStep
    candidate, calls = _pending_candidate_from_tool_error(env)
    original_config = dict(env['agent'].configuration)
    generated = candidate.generated_code
    description = candidate.skill_description
    client, headers, approved, applied = _approve_and_apply(env, candidate)
    assert applied['status'] == 'promoted'
    assert applied['generated_code_applied'] is False
    captured = {}
    with env['factory']() as fresh:
        row = fresh.get(AgentRegistry, env['agent'].id)
        agent = GenericAgent(row, workspace_id=env['workspace'].id)
        agent.tenant_id = env['tenant'].id
        async def capture(**kwargs):
            captured.update(kwargs)
            return ReActStep(thought='controlled request capture', final_answer='Reviewed guidance received')
        monkeypatch.setattr(agent.llm, 'generate_structured', capture)
        result = asyncio.run(agent._react_step(TASK, memory={}, history='', context={}))
        assert result.final_answer == 'Reviewed guidance received'
        assert row.configuration == original_config
    system = str(captured.get('system_instruction') or '')
    prompt = str(captured.get('prompt') or '')
    assert calls
    assert candidate.skill_name in system
    assert description in system
    assert TASK in prompt
    assert generated not in system and generated not in prompt
    client.close()
