"""Annotation names on module-level functions must RESOLVE at def time.

R5 (review 2026-09-17): core/session_sources.py annotated
``List[Dict[str, Any]]`` without importing ``Dict``. Local dev runs Python
3.14, which defers annotation evaluation, so every import and test passed —
while CI and Docker (python:3.11-slim, per pyproject ``requires-python``)
raise NameError AT DEF TIME. The 3.11 pytest run failed at collection; the
green 3.14 runs were cited as coverage anyway.

This test statically does what the 3.11 interpreter does when it defines a
module-level function: every name used in that function's annotations must
be bound at module level (import / assignment / def / class, including
``if TYPE_CHECKING:`` and top-level ``try:`` import arms) or be a builtin.
No module is imported, so the check has no import side effects and runs on
any interpreter version.

The embedded self-check pins the detector on the exact R5 defect shape, so
a refactor that blinds the scan fails here instead of silently passing.
"""
import ast
import builtins
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
#: The two packages where the RCA modules and their consumers live. AST-only:
#: no file is executed, so scanning is safe regardless of import-time behavior.
SCAN_PACKAGES = ("core", "integrations")

_BUILTIN_NAMES = set(dir(builtins))


def _bindings(tree: ast.Module) -> set:
    """Names bound at MODULE level — direct body children, plus imports
    nested one level inside ``if``/``try`` (TYPE_CHECKING and conditional
    import arms still bind module globals when the branch runs). A
    function-local import does NOT bind module scope and must not satisfy
    an annotation: on 3.11 the def-time evaluation happens before any
    function body runs."""
    names: set = set()

    def _collect_imports(nodes) -> None:
        for node in nodes:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.add((alias.asname or alias.name).split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name != "*":
                        names.add(alias.asname or alias.name)

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            _collect_imports([node])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(
                node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.If, ast.Try)):
            _collect_imports(ast.walk(node))
    return names


def _annotation_names(func: ast.FunctionDef) -> set:
    """Every bare Name used in a module-level function's annotations
    (arguments, defaults excluded, return). Quoted forward references are
    constants the interpreter would resolve lazily via get_type_hints —
    out of scope here; Attribute roots (``typing.List``) ARE in scope,
    because an unevaluated ``typing`` import breaks 3.11 exactly the same
    way an unimported ``Dict`` does."""
    out: set = set()

    def _walk(node) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Name):
                out.add(child.id)
            elif not isinstance(child, ast.Constant):
                _walk(child)

    a = func.args
    arg_annotations = [x.annotation for x in (
        [*a.posonlyargs, *a.args, *a.kwonlyargs]
        + [x for x in (a.vararg, a.kwarg) if x])]
    for annotation in [*arg_annotations, func.returns]:
        if annotation is not None:
            _walk(annotation)
    return out


def _unresolved_annotation_names(source: str) -> "dict[str, set]":
    """``{function: {unresolved, ...}}`` for one module's source."""
    tree = ast.parse(source)
    bound = _bindings(tree)
    problems: "dict[str, set]" = {}
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        missing = {n for n in _annotation_names(node)
                   if n not in bound and n not in _BUILTIN_NAMES}
        if missing:
            problems[node.name] = missing
    return problems


def test_core_and_integration_annotations_resolve():
    failures = []
    for package in SCAN_PACKAGES:
        package_dir = BACKEND_DIR / package
        if not package_dir.is_dir():
            continue
        for path in sorted(package_dir.glob("*.py")):
            problems = _unresolved_annotation_names(path.read_text(
                encoding="utf-8"))
            for func, missing in problems.items():
                failures.append(
                    f"{package}/{path.name}:{func} — annotation name(s) "
                    f"{sorted(missing)} not importable at module level "
                    "(NameError on python3.11 at def time)")
    assert not failures, (
        "modules whose annotations break on the deployed 3.11 runtime:\n"
        + "\n".join(failures))


def test_detector_catches_the_r5_shape():
    """Self-check: the scan must flag the exact defect that shipped — a
    module-level function annotated with an unimported typing name."""
    buggy = (
        "from typing import Any, Iterable, List\n"
        "\n"
        "def conversation_source_names(history: List[Dict[str, Any]],\n"
        "                              window: int = 12) -> List[str]:\n"
        "    return []\n"
    )
    problems = _unresolved_annotation_names(buggy)
    assert problems.get("conversation_source_names") == {"Dict"}


def test_detector_accepts_type_checking_and_conditional_imports():
    ok = (
        "from typing import TYPE_CHECKING\n"
        "\n"
        "if TYPE_CHECKING:\n"
        "    from decimal import Decimal\n"
        "\n"
        "try:\n"
        "    from typing import Dict\n"
        "except ImportError:\n"
        "    Dict = dict\n"
        "\n"
        "def f(x: Dict[str, int]) -> 'Decimal':\n"  # quoted: lazily resolved
        "    return x\n"
    )
    assert _unresolved_annotation_names(ok) == {}
