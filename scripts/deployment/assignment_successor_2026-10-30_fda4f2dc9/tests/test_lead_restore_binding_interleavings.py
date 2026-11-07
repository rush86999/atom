import importlib.util,json,os,sqlite3,shutil
from pathlib import Path
import pytest
KIT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('lead_restore_effective_fixture',KIT/'tests/test_release_restore.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f);rs=f.restore_support

@pytest.mark.parametrize('change',['content','inode','wal','shm'])
def test_real_postvalidation_peer_interleaving_occurs_and_is_refused(tmp_path,monkeypatch,change):
    world,root,env,backup=f._backup_world(tmp_path)
    original=rs._copy_database;reached=[]
    def peer(source,stage,counts,*args,**kwargs):
        reached.append(change)
        if change=='content':
            with sqlite3.connect(source) as db:db.execute("UPDATE users SET first_name='PEER-UNREVIEWED'");db.commit()
        elif change=='inode':
            peerfile=source.with_name('peer-replacement.db');shutil.copyfile(source,peerfile);os.replace(peerfile,source)
        else:source.with_name(source.name+'-'+change).write_bytes(b'unmanifested peer material')
        return original(source,stage,counts,*args,**kwargs)
    monkeypatch.setattr(rs,'_copy_database',peer)
    target=tmp_path/'target'
    with pytest.raises(rs.RestoreRefused) as exc:rs.restore_backup(backup_arg=str(backup),target_arg=str(target),env=env)
    assert reached==[change], 'negative never reached the actual peer interleaving'
    assert 'TypeError' not in str(exc.value), 'signature error is not tamper detection'
    assert not target.exists()

def test_original_audit_complete_rows_preserved_and_current_canvas_rebased(tmp_path):
    world,root,env,backup=f._backup_world(tmp_path)
    with sqlite3.connect(backup/'atom.db') as db:
        cols=[r[1] for r in db.execute('PRAGMA table_info(canvas_audit)')]
        before=db.execute('SELECT * FROM canvas_audit ORDER BY id').fetchall()
    assert before
    target=tmp_path/'target';result=rs.restore_backup(backup_arg=str(backup),target_arg=str(target),env=env)
    assert result['status']=='verified',result
    with sqlite3.connect(target/'atom.db') as db:
        after={r[cols.index('id')]:r for r in db.execute('SELECT * FROM canvas_audit')}
        for row in before:assert after[row[cols.index('id')]]==row
        assert len(after)>len(before),'restored current projection needs new truthful audit event'

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
