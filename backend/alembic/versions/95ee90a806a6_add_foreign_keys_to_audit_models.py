"""add foreign keys to audit models

Revision ID: 95ee90a806a6
Revises: a04bed1462ee
Create Date: 2026-02-06 19:29:12.808194

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '95ee90a806a6'
down_revision: Union[str, Sequence[str], None] = 'a04bed1462ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - add foreign keys to audit models."""
    # CanvasAudit foreign keys
    with op.batch_alter_table('canvas_audit', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_canvas_audit_agent', 'agent_registry', ['agent_id'], ['id'])
        batch_op.create_foreign_key('fk_canvas_audit_user', 'users', ['user_id'], ['id'])
        batch_op.create_foreign_key('fk_canvas_audit_execution', 'agent_executions', ['agent_execution_id'], ['id'])

    # DeviceAudit foreign keys
    with op.batch_alter_table('device_audit', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_device_audit_user', 'users', ['user_id'], ['id'])
        batch_op.create_foreign_key('fk_device_audit_agent', 'agent_registry', ['agent_id'], ['id'])
        batch_op.create_foreign_key('fk_device_audit_execution', 'agent_executions', ['agent_execution_id'], ['id'])
        batch_op.create_foreign_key('fk_device_audit_device', 'device_nodes', ['device_node_id'], ['device_id'])

    # BrowserAudit foreign keys
    with op.batch_alter_table('browser_audit', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_browser_audit_user', 'users', ['user_id'], ['id'])
        batch_op.create_foreign_key('fk_browser_audit_agent', 'agent_registry', ['agent_id'], ['id'])
        batch_op.create_foreign_key('fk_browser_audit_execution', 'agent_executions', ['agent_execution_id'], ['id'])

    # DeepLinkAudit foreign key
    with op.batch_alter_table('deep_link_audit', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_deep_link_audit_user', 'users', ['user_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema - remove foreign keys from audit models."""
    # CanvasAudit foreign keys
    with op.batch_alter_table('canvas_audit', schema=None) as batch_op:
        batch_op.drop_constraint('fk_canvas_audit_agent', type_='foreignkey')
        batch_op.drop_constraint('fk_canvas_audit_user', type_='foreignkey')
        batch_op.drop_constraint('fk_canvas_audit_execution', type_='foreignkey')

    # DeviceAudit foreign keys
    with op.batch_alter_table('device_audit', schema=None) as batch_op:
        batch_op.drop_constraint('fk_device_audit_user', type_='foreignkey')
        batch_op.drop_constraint('fk_device_audit_agent', type_='foreignkey')
        batch_op.drop_constraint('fk_device_audit_execution', type_='foreignkey')
        batch_op.drop_constraint('fk_device_audit_device', type_='foreignkey')

    # BrowserAudit foreign keys
    with op.batch_alter_table('browser_audit', schema=None) as batch_op:
        batch_op.drop_constraint('fk_browser_audit_user', type_='foreignkey')
        batch_op.drop_constraint('fk_browser_audit_agent', type_='foreignkey')
        batch_op.drop_constraint('fk_browser_audit_execution', type_='foreignkey')

    # DeepLinkAudit foreign key
    with op.batch_alter_table('deep_link_audit', schema=None) as batch_op:
        batch_op.drop_constraint('fk_deep_link_audit_user', type_='foreignkey')
