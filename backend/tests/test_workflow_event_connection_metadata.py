"""Observe the real SQL metadata boundary used for event binding."""
from sqlalchemy import event
from sqlalchemy.orm import Session
from core.connection_service import ConnectionService
from tests.test_workflow_event_registration import world


def test_connection_binding_reads_metadata_only_without_writes(world):
    client, catalog, actor, db_engine, sub, payload = world
    statements = []
    def capture(conn, cursor, statement, parameters, context, many):
        statements.append(statement.lower())
    event.listen(db_engine, 'before_cursor_execute', capture)
    try:
        with Session(db_engine) as db:
            metadata = ConnectionService.get_scoped_connection_metadata(
                db, user_id=actor.id, tenant_id=actor.tenant_id, workspace_id=actor.workspace_id,
                connection_id=sub['connection_id'], integration_id=sub['source'])
        assert set(metadata) == {'id', 'user_id', 'tenant_id', 'workspace_id', 'integration_id', 'status'}
        assert statements and all(s.lstrip().startswith('select') for s in statements)
        assert all('credentials' not in s for s in statements)
    finally:
        event.remove(db_engine, 'before_cursor_execute', capture)
