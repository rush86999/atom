"""Static Alembic revision ABI check; not a PostgreSQL runtime qualification.

Re-run of the root's independent probe against the corrected source:
* the installed Alembic ``alembic_version`` column is ``String(32)``;
* the selected revision fits that column;
* the parent revision exists at the executed source;
* the revision is unique and is a head.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SOURCE = "4dfc3402b3d232ce1fda993f2c2362331600ef6f"
FILE = "backend/alembic/versions/20261107_task_operation_result_json.py"

import alembic  # noqa: E402 - import after path setup for the installed package

installed = Path(alembic.__file__).resolve().parent / "ddl" / "impl.py"
installed_text = installed.read_text()
assert 'Column("version_num", String(32), nullable=False)' in installed_text, (
    f"installed alembic no longer declares String(32): {installed}"
)

text = subprocess.check_output(
    ["git", "show", f"{SOURCE}:{FILE}"], cwd=ROOT, text=True)
assignments = {
    node.targets[0].id: ast.literal_eval(node.value)
    for node in ast.parse(text).body
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
}
revision = assignments["revision"]
parent = assignments["down_revision"]
assert len(revision) <= 32, (revision, len(revision))
print(f"revision {revision!r} = {len(revision)} chars (<= 32)")

files = subprocess.check_output(
    ["git", "ls-tree", "-r", "--name-only", SOURCE,
     "backend/alembic/versions"],
    cwd=ROOT, text=True,
).splitlines()
revisions = {}
for file in files:
    if not file.endswith(".py"):
        continue
    body = subprocess.check_output(
        ["git", "show", f"{SOURCE}:{file}"], cwd=ROOT, text=True)
    try:
        tree = ast.parse(body)
    except SyntaxError:
        continue
    values = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"revision", "down_revision"}
    }
    for key, value in values.items():
        if key == "revision":
            assert value not in revisions, f"duplicate revision {value}"
            revisions[value] = (file, values.get("down_revision"))

assert parent in revisions, f"parent {parent} not found"
print(f"parent {parent!r} resolves to {revisions[parent][0]}")

children = {}
for child, (_file, down) in revisions.items():
    parents = down if isinstance(down, (tuple, list)) else [down]
    for name in parents:
        if name is not None:
            children.setdefault(name, []).append(child)
assert revision not in children, children.get(revision)
print(f"revision {revision!r} is a head")
print("revision contract verified (static ABI only; no PostgreSQL runtime)")
