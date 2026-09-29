# -*- coding: utf-8 -*-
"""Defect 1: the launchers and the storage policy agree, and a broken policy
stops the launcher instead of quietly becoming a different module.

Scope and safety
----------------
Purely static + import-time assertions plus ONE subprocess that imports the
launcher against a deliberately broken *copy* of the policy. Nothing here
builds a world, seeds a run, opens a port, or reads ``backend/data/atom.db``.
The broken-policy fixture lives in ``tmp_path`` and shadows the real module
only inside that subprocess.

What is actually pinned
-----------------------
* every ``SP.<symbol>`` reference in ``run_isolated.py`` and
  ``preview_stack.py`` resolves on the imported policy module;
* every ``SP.<fn>(...)`` CALL binds against the real signature (arity +
  keyword names), so a renamed parameter fails here rather than mid-build;
* the launcher's own import-time guard (``_REQUIRED_POLICY_SYMBOLS``) is a
  SUPERSET of the references the AST finds, so the guard cannot drift into
  covering less than the code needs;
* there is exactly ONE policy module object. A second copy means two copies of
  every constant, which is the drift this repo keeps paying for;
* the dead policy surface is gone (``MIN_FREE_DISK_BYTES``,
  ``SMALL_FIXTURE_MAX_BYTES``) and the constants that are still declared are
  each referenced somewhere;
* a policy module that raises ``ImportError`` from INSIDE itself produces a
  loud, named failure at import time — never a second import path, never a
  launcher that imports cleanly against a policy that is missing symbols.
"""
from __future__ import annotations

import ast
import inspect
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from scripts.orchestration_acceptance import storage_policy as SP  # noqa: E402

ACC = BACKEND / "scripts" / "orchestration_acceptance"
LAUNCHERS = ("run_isolated.py", "preview_stack.py")

PY = str(BACKEND / "venv" / "bin" / "python")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _references(name: str):
    """``(attributes, calls)`` for one launcher: every ``SP.<x>`` touched.

    AST rather than a regex: a docstring that mentions ``SP.foo`` is
    documentation, an ``ast.Attribute`` on a ``Name('SP')`` is a reference.
    """
    tree = ast.parse((ACC / name).read_text())
    attrs, calls = {}, {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "SP"):
            continue
        attrs.setdefault(node.attr, node.lineno)
        if isinstance(node.ctx, ast.Load) and isinstance(getattr(node, "_call", None), ast.Call):
            pass
    # second pass for call sites (ast.Call wraps the Attribute)
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "SP"):
            npos = len(node.args)
            kwargs = {k.arg for k in node.keywords if k.arg is not None}
            calls.setdefault(node.func.attr, []).append((node.lineno, npos, kwargs))
    return attrs, calls


def _all_references():
    out = {}
    for name in LAUNCHERS:
        attrs, calls = _references(name)
        for sym, line in attrs.items():
            out.setdefault(sym, []).append(f"{name}:{line}")
    return out


# ---------------------------------------------------------------------------
# 1. every referenced symbol exists
# ---------------------------------------------------------------------------
def test_every_policy_symbol_the_launchers_reference_exists():
    refs = _all_references()
    assert refs, "the AST found no SP.<symbol> references at all — the audit is broken"
    missing = {sym: where for sym, where in refs.items() if not hasattr(SP, sym)}
    assert not missing, (
        "storage_policy does not define: "
        + json.dumps(missing, indent=2)
        + f"\n  (policy module: {SP.__file__})")


@pytest.mark.parametrize("symbol", sorted(_all_references()))
def test_each_referenced_symbol_resolves_on_the_imported_module(symbol):
    """One node id per referenced symbol, so a failure names the culprit."""
    assert hasattr(SP, symbol), (
        f"storage_policy is missing {symbol!r}; the launcher would raise "
        f"AttributeError mid-build instead of failing here")


# ---------------------------------------------------------------------------
# 2. every CALL binds against the real signature
# ---------------------------------------------------------------------------
def test_every_policy_call_binds_against_the_real_signature():
    """A renamed parameter must fail at audit time, not mid-build.

    ``sig.bind`` is the real check: it enforces arity, keyword names and
    positional-only/keyword-only markers exactly as a call would.
    """
    problems = []
    checked = 0
    for name in LAUNCHERS:
        _, calls = _references(name)
        for sym, sites in calls.items():
            fn = getattr(SP, sym, None)
            if not callable(fn):
                problems.append(f"{name}: {sym} is called but is not callable")
                continue
            sig = inspect.signature(fn)
            for line, npos, kwargs in sites:
                checked += 1
                try:
                    sig.bind(*([None] * npos), **dict.fromkeys(kwargs, None))
                except TypeError as exc:
                    problems.append(
                        f"{name}:{line} SP.{sym}({npos} positional, "
                        f"kwargs={sorted(kwargs)}) does not bind: {exc}")
    assert checked >= 10, f"only {checked} call sites audited — audit is too narrow"
    assert not problems, "signature mismatches:\n  " + "\n  ".join(problems)


def test_call_audit_actually_catches_a_broken_signature():
    """Negative control: the audit above must be capable of failing."""
    def good(a, *, b=1):
        return a, b

    sig = inspect.signature(good)
    sig.bind(None, b=None)                     # fine
    with pytest.raises(TypeError):
        sig.bind(None, c=None)                 # unknown keyword
    with pytest.raises(TypeError):
        sig.bind(None, None)                   # too many positionals


# ---------------------------------------------------------------------------
# 3. the import-time guard covers at least what the code references
# ---------------------------------------------------------------------------
def test_import_time_guard_covers_every_reference():
    import scripts.orchestration_acceptance.run_isolated as R  # noqa: E402

    declared = set(R._REQUIRED_POLICY_SYMBOLS)
    referenced = set(_all_references())
    assert referenced <= declared, (
        "the launcher's import-time policy guard does not cover: "
        + ", ".join(sorted(referenced - declared))
        + " — a rename of any of these would not be caught at import time")
    for name in declared:
        assert hasattr(SP, name), f"guard names {name}, which the policy does not define"


def test_the_verifier_names_every_missing_symbol(monkeypatch):
    """It must fail with a LIST, not with the first one it trips over."""
    import scripts.orchestration_acceptance.run_isolated as R  # noqa: E402

    missing = ("human", "check_space")

    class Fake:
        __file__ = "<fake policy>"
        # everything EXCEPT the two above
        def __getattr__(self, item):
            if item in missing:
                raise AttributeError(item)
            return object()

    monkeypatch.setattr(R, "SP", Fake())
    with pytest.raises(ImportError) as excinfo:
        R._verify_policy_surface()
    msg = str(excinfo.value)
    for name in missing:
        assert name in msg, f"{name} was not named in the failure message: {msg}"
    assert "Refusing to start" in msg


# ---------------------------------------------------------------------------
# 4. ONE policy module object
# ---------------------------------------------------------------------------
def test_both_launchers_share_one_policy_module_object():
    import scripts.orchestration_acceptance.run_isolated as R  # noqa: E402
    import scripts.orchestration_acceptance.preview_stack as P  # noqa: E402

    assert R.SP is SP, "run_isolated bound a different policy module"
    assert P.SP is SP, "preview_stack bound a different policy module"
    assert R.SP is P.SP


def test_no_sibling_copy_of_the_policy_is_imported_by_the_launchers():
    """``tests/core/test_storage_policy.py`` imports a SIBLING copy under the
    bare name ``storage_policy``; the launchers must not, or the constants
    diverge again."""
    import scripts.orchestration_acceptance.run_isolated as R  # noqa: E402

    assert "storage_policy" not in sys.modules or \
        sys.modules["storage_policy"] is sys.modules[SP.__name__], (
        "a bare `storage_policy` module object exists alongside the package "
        "one; two module objects means two copies of every constant")


# ---------------------------------------------------------------------------
# 5. the import is single and unconditional
# ---------------------------------------------------------------------------
def test_launcher_has_no_fallback_policy_import():
    src = (ACC / "run_isolated.py").read_text()
    tree = ast.parse(src)
    # The precise check: a bare `import storage_policy` statement. A substring
    # test would also match the legitimate
    # `from scripts.orchestration_acceptance import storage_policy as SP`.
    bare = [n for n in ast.walk(tree)
            if isinstance(n, ast.Import)
            and any(a.name == "storage_policy" and a.asname == "SP"
                    for a in n.names)]
    assert not bare, (
        "a bare `import storage_policy` is still present: an ImportError from "
        "inside the policy can rebind SP to a second module object")
    imports = [n for n in ast.walk(tree)
               if isinstance(n, ast.ImportFrom) and n.module ==
               "scripts.orchestration_acceptance"]
    assert any(any(a.name == "storage_policy" for a in imp.names)
               for imp in imports), \
        "the launcher no longer imports the policy as a package module"
    # ... and there is no try/except around it.
    guarded = [n for n in ast.walk(tree)
               if isinstance(n, ast.Try)
               and any(isinstance(x, ast.ImportFrom) and x.module ==
                       "scripts.orchestration_acceptance" and
                       any(a.name == "storage_policy" for a in x.names)
                       for x in ast.walk(n))]
    assert not guarded, "the policy import is still inside a try/except"


def test_backend_is_on_sys_path_before_the_policy_import():
    """The removed fallback existed for this; the guarantee is now explicit."""
    src = (ACC / "run_isolated.py").read_text()
    assert 'sys.path.insert(0, str(BACKEND))' in src
    assert src.index('sys.path.insert(0, str(BACKEND))') < \
        src.index("from scripts.orchestration_acceptance import storage_policy as SP")


# ---------------------------------------------------------------------------
# 6. dead policy surface
# ---------------------------------------------------------------------------
def test_removed_legacy_constants_are_gone():
    import scripts.orchestration_acceptance.run_isolated as R  # noqa: E402

    for name in ("MIN_FREE_DISK_BYTES", "SMALL_FIXTURE_MAX_BYTES"):
        assert not hasattr(R, name), (
            f"{name} is still declared in run_isolated.py: nothing reads it, and a "
            f"headroom/fixture ceiling that nothing enforces is exactly the dead "
            f"policy surface this repair removes")
    assert hasattr(SP, "SMALL_FIXTURE_MAX_BYTES"), \
        "the ceiling must still exist — in the policy, where it is enforced"


def test_every_constant_still_declared_by_the_launcher_is_referenced():
    """No other dead policy surface, checked mechanically rather than by eye."""
    import scripts.orchestration_acceptance.run_isolated as R  # noqa: E402

    tree = ast.parse((ACC / "run_isolated.py").read_text())
    declared = {t.id for n in tree.body if isinstance(n, ast.Assign)
                for t in n.targets if isinstance(t, ast.Name)}
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    used |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    dead = sorted(n for n in declared - used
                  if not n.startswith("_") and n.isupper())
    assert not dead, f"module constants declared but never referenced: {dead}"
    assert "MAX_RETAINED_RUNS" in declared, "the retention cap must survive"


# ---------------------------------------------------------------------------
# 7. a broken policy must fail LOUDLY
# ---------------------------------------------------------------------------
_BROKEN_POLICY = textwrap.dedent('''
    """Stand-in for storage_policy that fails the way the real defect did.

    FIRST import raises ImportError from INSIDE the module (a nested import
    blowing up is indistinguishable, to the caller, from the module being
    missing). LATER imports succeed — and return a module that is missing
    half the API.

    That is precisely the shape the old dual import could not see: attempt one
    raises, the `except ImportError` branch imports a second module object,
    the launcher imports "successfully", and the missing symbols only surface
    as an AttributeError thousands of lines into a 400 MB build.
    """
    import json as _json
    import os as _os
    from pathlib import Path as _P

    _counter = _P(__file__).with_suffix(".attempts")
    _n = int(_counter.read_text()) + 1 if _counter.exists() else 1
    _counter.write_text(str(_n))

    if _n == 1:
        try:
            import a_module_that_does_not_exist_anywhere  # noqa: F401
        except ImportError as _exc:
            raise ImportError(
                "storage_policy failed to initialise: a nested import inside "
                "the policy module blew up") from _exc

    # Second and later attempts: a DIFFERENT module object, and incomplete.
    IDENTITY = f"copy-{_n}"
    MB = 1024 * 1024
    FULL_DEV_DB_FLAG = "--full-dev-db-snapshot"
    CLASS_DROPPABLE = "droppable"
    DEFAULT_RUN_CAP = 5
    SpaceEstimate = None
    SpaceReport = None
    InsufficientStorage = RuntimeError
    human = str
    real_free_bytes = lambda p: 0
    check_space = lambda *a, **k: None
    estimate_world_build = lambda *a, **k: None
    estimate_new_run = lambda *a, **k: None
    # NOTE: build_inventory, world_storage_report, render_report,
    # provision_api_seeded_fixture, resolve_fixture_source,
    # link_shared_export, assert_writable_state_separate,
    # assert_not_hardlinked_writable are ALL absent on purpose.
''')


def _shim_dir(tmp_path: Path) -> Path:
    """A shadowing copy of the package with a broken policy inside it."""
    pkg = tmp_path / "scripts" / "orchestration_acceptance"
    pkg.mkdir(parents=True)
    (tmp_path / "scripts" / "__init__.py").write_text("")
    (pkg / "__init__.py").write_text("")
    (pkg / "storage_policy.py").write_text(_BROKEN_POLICY)
    (pkg / "run_isolated.py").write_text(
        (ACC / "run_isolated.py").read_text())
    return tmp_path


_DRIVER = textwrap.dedent('''
    """No try/except: exactly how production imports the launcher."""
    import sys
    sys.path.insert(0, {shim!r})     # the broken policy wins
    sys.path.insert(1, {backend!r})  # the real backend, for core.*
    from scripts.orchestration_acceptance import run_isolated as R
    print("IMPORTED", getattr(R.SP, "__file__", "?"))
''')


_CATCHING_DRIVER = textwrap.dedent('''
    """Same import, but reporting what happened as JSON instead of dying."""
    import json, sys
    sys.path.insert(0, {shim!r})
    sys.path.insert(1, {backend!r})
    try:
        from scripts.orchestration_acceptance import run_isolated as R
    except ImportError as exc:
        print(json.dumps({{"imported": False, "error_type": type(exc).__name__,
                           "error": str(exc)}}))
        raise SystemExit(0)
    print(json.dumps({{"imported": True,
                      "sp_file": getattr(R.SP, "__file__", "?"),
                      "sp_identity": getattr(R.SP, "IDENTITY", "n/a")}}))
''')


def _run_driver(tmp_path: Path, source: str) -> subprocess.CompletedProcess:
    path = tmp_path / "driver.py"
    path.write_text(source.format(shim=str(tmp_path), backend=str(BACKEND)))
    return subprocess.run([PY, str(path)], capture_output=True, text=True,
                          cwd=str(BACKEND), timeout=300)


def test_broken_policy_fails_loudly_at_import_time(tmp_path):
    """The launcher must STOP on a policy that raises from inside itself.

    Run in a subprocess: the shadowing copy has to win the import, and a
    half-imported launcher must not be left in this process. The driver does
    NOT catch, so "loud" means a non-zero exit and a traceback naming the
    policy — the opposite of importing cleanly against half a policy.
    """
    shim = _shim_dir(tmp_path)
    proc = _run_driver(tmp_path, _DRIVER)
    assert proc.returncode != 0, (
        "the launcher imported SUCCESSFULLY against a policy whose first "
        f"import raised ImportError — the silent-fallback defect is back.\n"
        f"stdout: {proc.stdout}")
    assert "Traceback (most recent call last)" in proc.stderr, (
        f"the failure must be loud; stderr was:\n{proc.stderr}")
    assert "storage_policy" in proc.stderr, (
        f"the failure must NAME the module that broke:\n{proc.stderr}")
    assert "IMPORTED" not in proc.stdout


def test_broken_policy_reports_a_named_import_error(tmp_path):
    """Same event, reported as data: imported=False and a message that says
    the policy is what failed."""
    _shim_dir(tmp_path)
    proc = _run_driver(tmp_path, _CATCHING_DRIVER)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert payload["imported"] is False
    assert payload["error_type"] in ("ImportError", "ModuleNotFoundError")
    assert "storage_policy" in payload["error"]


def test_the_old_dual_import_pattern_reproduces_the_silent_fallback(tmp_path):
    """Negative control: the pattern that was removed, run in isolation.

    This is a REPLICA of the removed code, labelled as such. It exists to show
    the defect was real and is not hypothetical: with the same broken policy,
    the dual import succeeds and hands back a module missing half the API.
    """
    shim = _shim_dir(tmp_path)
    replica = tmp_path / "replica.py"
    replica.write_text(textwrap.dedent('''
        import json, sys
        sys.path.insert(0, {shim!r})
        sys.path.insert(1, {backend!r})
        sys.path.insert(0, {pkgdir!r})      # what the fallback did
        try:
            from scripts.orchestration_acceptance import storage_policy as SP
        except ImportError:
            import storage_policy as SP
        print(json.dumps({{
            "imported": True,
            "identity": getattr(SP, "IDENTITY", "n/a"),
            "is_package_module": SP.__name__ == "scripts.orchestration_acceptance.storage_policy",
            "has_world_storage_report": hasattr(SP, "world_storage_report"),
        }}))
    ''').format(shim=str(shim), backend=str(BACKEND),
               pkgdir=str(shim / "scripts" / "orchestration_acceptance")))
    proc = subprocess.run([PY, str(replica)], capture_output=True, text=True,
                          cwd=str(BACKEND), timeout=300)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    assert payload["imported"] is True, \
        "the replica did not reproduce the defect; the negative control is void"
    assert payload["is_package_module"] is False, (
        "the fallback rebound SP to a module under a different name — two "
        "module objects, two copies of every constant")
    assert payload["has_world_storage_report"] is False, (
        "and the rebound module is missing symbols the launcher calls")


# ---------------------------------------------------------------------------
# 8. the flag surface the launchers expose
# ---------------------------------------------------------------------------
def test_full_dev_db_flag_is_named_in_both_launchers_help():
    import scripts.orchestration_acceptance.run_isolated as R  # noqa: E402
    src = (ACC / "run_isolated.py").read_text()
    assert SP.FULL_DEV_DB_FLAG in src
    # the help must say it copies the ENTIRE live database, in bytes measured
    assert "COPY THE ENTIRE LIVE DEV DATABASE" in src
    assert "413,360,128" in src, \
        "the help must carry the measured size, not a vague 'large'"
    assert SP.FULL_DEV_DB_FLAG.startswith("--full-dev-db")


def test_cli_help_for_the_opt_in_says_it_copies_the_whole_database(capsys):
    with pytest.raises(SystemExit):
        SP.main(["space", "--help"])
    text = capsys.readouterr().out
    assert SP.FULL_DEV_DB_FLAG in text
    assert "ENTIRE live dev database" in text
    assert "413,360,128" in text
