import importlib.util
import json
import sqlite3
from pathlib import Path
import pytest

KIT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('lead_restore_fixture',KIT/'tests/test_release_restore.py');fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
rs=fixtures.restore_support

def test_restore_preserves_every_original_canvas_audit_byte(tmp_path):
    world,root,env,backup=fixtures._backup_world(tmp_path)
    with sqlite3.connect(backup/'atom.db') as db:
        original=db.execute('SELECT id,details_json FROM canvas_audit ORDER BY id').fetchall()
    assert original
    target=tmp_path/'restored'
    result=rs.restore_backup(backup_arg=str(backup),target_arg=str(target),env=env)
    assert result['status']=='verified',result
    with sqlite3.connect(target/'atom.db') as db:
        for identity,details in original:
            row=db.execute('SELECT details_json FROM canvas_audit WHERE id=?',(identity,)).fetchone()
            assert row is not None and row[0]==details,('restore rewrote original audit',identity,details,row)

def test_backup_database_swap_after_validation_refuses_before_publication(tmp_path,monkeypatch):
    world,root,env,backup=fixtures._backup_world(tmp_path)
    original=rs._copy_database
    reached=[]
    def peer_changes_before_copy(source,stage,counts,*args,**kwargs):
        reached.append(True)
        with sqlite3.connect(source) as db:
            db.execute("UPDATE users SET first_name='PEER-UNREVIEWED'");db.commit()
        return original(source,stage,counts,*args,**kwargs)
    monkeypatch.setattr(rs,'_copy_database',peer_changes_before_copy)
    target=tmp_path/'restored'
    try:
        result=rs.restore_backup(backup_arg=str(backup),target_arg=str(target),env=env)
    except rs.RestoreRefused as exc:
        assert reached == [True], "peer mutation never ran"
        assert "TypeError" not in str(exc), "signature mismatch is not tamper detection"
        assert not target.exists()
        return
    with sqlite3.connect(target/'atom.db') as db:observed=db.execute('SELECT first_name FROM users').fetchall()
    pytest.fail('unmanifested database published: '+repr((result['status'],observed)))

def test_exact_original_backup_positive_twin(tmp_path):
    world,root,env,backup=fixtures._backup_world(tmp_path)
    target=tmp_path/'restored'
    proc,result=fixtures._restore(backup,target,root=root,env=env)
    assert proc.returncode==0 and result['status']=='verified',(proc.returncode,result)
