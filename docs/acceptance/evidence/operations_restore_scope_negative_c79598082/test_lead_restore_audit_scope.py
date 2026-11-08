import importlib.util,sqlite3,json
from pathlib import Path
import pytest
KIT=Path('/private/tmp/atom-oracle-refresh-20261107/scripts/deployment/assignment_successor_2026-10-30_fda4f2dc9')
s=importlib.util.spec_from_file_location('lead_restore_scope_fixture',KIT/'tests/test_release_restore.py');f=importlib.util.module_from_spec(s);s.loader.exec_module(f);rs=f.restore_support

def test_foreign_historical_audit_cannot_be_reissued_under_current_canvas_tenant(tmp_path):
    world=f._make_world(tmp_path)
    with sqlite3.connect(world['source']/'atom.db') as db:
        canvas=db.execute('SELECT tenant_id FROM canvases WHERE id=?',('canvas-1',)).fetchone()[0]
        assert canvas=='tenant-1'
        db.execute("UPDATE canvas_audit SET tenant_id='foreign-tenant' WHERE canvas_id='canvas-1'");db.commit()
    root,env,backup=f._backup_after_source_mutation(world,tmp_path,'foreign-history')
    target=tmp_path/'target'
    try:result=rs.restore_backup(backup_arg=str(backup),target_arg=str(target),env=env)
    except rs.RestoreRefused:
        assert not target.exists();return
    with sqlite3.connect(target/'atom.db') as db:
        reissued=db.execute("SELECT tenant_id,details_json FROM canvas_audit WHERE action_type='restore'").fetchall()
    pytest.fail('foreign audit content was recertified by a restore event: '+repr((result['status'],[(t,json.loads(d).get('restored_from')) for t,d in reissued])))
