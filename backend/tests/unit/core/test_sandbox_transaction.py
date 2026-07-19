import os
import pytest
import shutil
from pathlib import Path
from core.sandbox_transaction import SandboxTransaction

@pytest.fixture
def temp_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "file1.txt").write_text("hello")
    (workspace / "dir1").mkdir()
    (workspace / "dir1/file2.txt").write_text("world")
    return workspace

def test_sandbox_transaction_commit(temp_workspace):
    with SandboxTransaction(temp_workspace) as tx:
        (temp_workspace / "file1.txt").write_text("modified")
        (temp_workspace / "new_file.txt").write_text("added")
        shutil.rmtree(temp_workspace / "dir1")
        
    assert (temp_workspace / "file1.txt").read_text() == "modified"
    assert (temp_workspace / "new_file.txt").read_text() == "added"
    assert not (temp_workspace / "dir1").exists()
    
def test_sandbox_transaction_rollback(temp_workspace):
    try:
        with SandboxTransaction(temp_workspace) as tx:
            (temp_workspace / "file1.txt").write_text("modified")
            (temp_workspace / "new_file.txt").write_text("added")
            raise ValueError("abort transaction")
    except ValueError:
        pass
        
    assert (temp_workspace / "file1.txt").read_text() == "hello"
    assert not (temp_workspace / "new_file.txt").exists()
    assert (temp_workspace / "dir1/file2.txt").read_text() == "world"
