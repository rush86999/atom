import pytest
from core import sandbox_tripwire
from core.sandbox_policy import ALLOWED, BLOCKED, VT_TRIPWIRE

def test_ast_tripwires_allow_safe_code():
    code = """
def add(a, b):
    return a + b

result = add(5, 10)
print(f"Result is {result}")
"""
    d = sandbox_tripwire.check(tool_name="t", args={"code": code})
    assert d.decision == ALLOWED

def test_ast_tripwires_block_forbidden_import():
    code = """
import os
print(os.listdir("."))
"""
    d = sandbox_tripwire.check(tool_name="t", args={"code": code})
    assert d.decision == BLOCKED
    assert "AST violation: Forbidden import of module 'os'" in d.violation_detail

def test_ast_tripwires_block_forbidden_call():
    code = """
exec("import os; os.system('ls')")
"""
    d = sandbox_tripwire.check(tool_name="t", args={"code": code})
    assert d.decision == BLOCKED
    assert "AST violation: Forbidden built-in call 'exec()'" in d.violation_detail

def test_ast_tripwires_block_env_secret_access():
    code = """
key = os.environ["AWS_SECRET_ACCESS_KEY"]
print(key)
"""
    d = sandbox_tripwire.check(tool_name="t", args={"code": code})
    assert d.decision == BLOCKED
    assert "AST violation: Access to secret-bearing environment variable" in d.violation_detail
