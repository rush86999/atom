"""Independent forced-interleaving probe; real scratch SQLite only."""
from sqlalchemy import event
from core.models import AgentRegistry
from core.capability_graduation_service import CapabilityGraduationService
from tests.test_autonomy_revocation import store


def test_stale_success_cannot_erase_committed_regression(store):
    Session, weak = store
    engine = weak.get_bind()
    armed = [True]
    observed = []
    def interleave(conn, cursor, statement, parameters, context, executemany):
        if armed[0] and statement.lstrip().upper().startswith('UPDATE AGENT_REGISTRY'):
            armed[0] = False
            with Session() as peer:
                CapabilityGraduationService(peer).record_usage(
                    'agent-revocation-1', 'canvas_edit', False, 'failed_verification')
                row = peer.query(AgentRegistry).filter_by(id='agent-revocation-1').one()
                observed.append(row.configuration['capability_stats']['canvas_edit']['failures_verified'])
    event.listen(engine, 'before_cursor_execute', interleave)
    try:
        CapabilityGraduationService(weak).record_usage(
            'agent-revocation-1', 'canvas_edit', True, 'verified')
    finally:
        event.remove(engine, 'before_cursor_execute', interleave)
    assert observed == [1], 'peer must commit a real regression before weak DML'
    with Session() as fresh:
        row = fresh.query(AgentRegistry).filter_by(id='agent-revocation-1').one()
        cfg = row.configuration
        assert cfg['capability_stats']['canvas_edit'].get('failures_verified', 0) == 1
        assert cfg['capability_maturities']['canvas_edit'] == 'student'
        assert cfg.get('autonomy_revocations', {}).get('canvas_edit'), 'revocation must survive'
