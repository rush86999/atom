"""Dispatch parity — every service the chat tool planner advertises must
route its search to methods that ACTUALLY EXIST on the service layer.

Live 2026-09-03: the planner catalog advertised zoho_workdrive as "file
storage — search files" while UniversalIntegrationService dispatched the
search to ZohoWorkDriveService.search_files — a method that did not exist.
Every WorkDrive search AttributeError'd into "returned nothing usable" and
the agent declared a file missing while it sat on the drive. OneDrive had a
real search_files that dispatch never called (root-list + client-side
filter instead), and box/onedrive searches fell through _search_storage to
a silent [] — the MCP no-platform search_files fan-out never saw them.

This test mechanically walks the WHOLE advertised catalog (plus the
storage search() entry the MCP fan-out uses) against a recording stand-in
service, so the next integration added with a broken dispatch fails HERE
instead of in a live conversation. Two bug classes are pinned per service:
  1. dispatch reaches for a method the service class does not have
     (AttributeError class — WorkDrive);
  2. dispatch reaches for NOTHING and silently returns empty
     (fall-through class — box/onedrive in _search_storage).
A third, manual rule rides the same file: adding a service to the planner
catalog (_SERVICE_DESCRIPTIONS) requires either a passing entry here or an
explicit skip with a reason.
"""
import ast
import asyncio
import importlib
import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.chat_tool_planner import _SERVICE_DESCRIPTIONS
from integrations.universal_integration_service import UniversalIntegrationService

# Pseudo-services: no integration dispatch behind them.
PLATFORM_SERVICES = {"web_search", "web_fetch", "memory"}

# Services whose search() entry routes through _search_storage (the MCP
# no-platform search_files fan-out path).
STORAGE_FAMILY = ("google_drive", "dropbox", "onedrive", "box", "notion",
                  "zoho_workdrive")

# Recorded names that are instance attributes, not methods — allowed to be
# absent from the class object.
_ATTR_OK = {"access_token"}

# Services whose live search is honest-empty by design: the dispatch reaches
# its _search_* helper but no provider search implementation exists (discord
# has no search API wrapper in this codebase). The planner's memory fallback
# covers them. Anything added here needs a reason in the comment.
_EMPTY_OK = {
    # discord: no search API wrapper exists; helper returns [] cleanly.
    "discord",
}


# ── recording stand-in ──────────────────────────────────────────────────


class _Blank(dict):
    """Awaited-result shape: mapping-AND-empty. Branches treat results as
    mappings (res.get("status")) or as lists (for item in results) — a plain
    dict would iterate its KEYS and explode branch-side .get chains."""

    def __iter__(self):
        return iter([])


_BLANK = _Blank(status="success", data={}, results=[], issues=[],
                entries=[], value=[], tickets=[], conversations=[],
                messages=[], events=[], orders=[], customers=[],
                products=[], invoices=[], payments=[], repos=[],
                projects=[], cards=[])


class Tape:
    """Universal stand-in for an integration service.

    Records every attribute name touched (shared root), is callable and
    awaitable, and behaves as an empty mapping/iterable so dispatch branch
    code runs to completion without network or credentials."""

    access_token = "parity-token"  # truthy: token-guard early returns must not fire

    def __init__(self, root=None):
        object.__setattr__(self, "_root", root if root is not None else self)
        if root is None:
            object.__setattr__(self, "accessed", set())

    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        root = object.__getattribute__(self, "_root")
        root.accessed.add(name)
        return Tape(root)

    def __call__(self, *args, **kwargs):
        return Tape(object.__getattribute__(self, "_root"))

    def __await__(self):
        async def _result():
            return _BLANK
        return _result().__await__()

    # dict-protocol enough for branch-side result handling
    def get(self, key, default=None):
        return default
    def keys(self):
        return []
    def values(self):
        return []
    def items(self):
        return []
    def __iter__(self):
        return iter([])
    def __len__(self):
        return 0
    def __bool__(self):
        # `if service_inst:` guards must treat the stand-in as PRESENT —
        # __len__=0 would otherwise make every Tape falsy and flip the
        # dispatch's own existence checks.
        return True
    def __getitem__(self, key):
        raise KeyError(key)
    def __contains__(self, key):
        return False
    def __str__(self):
        return ""
    def __int__(self):
        return 0


# ── harness ─────────────────────────────────────────────────────────────


def _patch_integrations(root):
    """Patch EVERY `from integrations.X import Y` that
    universal_integration_service performs (top-level or in-branch) with a
    Tape sharing `root`, in both the source module's namespace and the
    universal module's. Derived from the AST, so new branch imports are
    covered automatically."""
    source = Path(inspect.getfile(UniversalIntegrationService))
    tree = ast.parse(source.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("integrations.") or node.module == "integrations":
                for alias in node.names:
                    names.add((node.module, alias.name))
    patchers = []
    for module_name, name in sorted(names):
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue
        patchers.append(patch.object(module, name, Tape(root), create=True))
        universal = importlib.import_module(
            "integrations.universal_integration_service")
        if hasattr(universal, name):
            patchers.append(
                patch.object(universal, name, Tape(root), create=True))
    return patchers


def _run(search_fn, service, *args):
    """Run one dispatch entry under the tape harness.
    Returns (accessed_names, exception_or_None, result)."""
    tape = Tape()

    async def _get_instance(service_name, tenant):
        return tape

    registry = SimpleNamespace(get_service_instance=_get_instance)
    context = {
        "user_id": "parity-user",
        "tenant_id": "default",
        "workspace_id": "default",
        "registry": registry,
        # Satisfies token-guard early returns so the tape actually sees the
        # service calls the dispatch is supposed to make.
        "access_token": "parity-token",
        "shop": "parity-shop.myshopify.com",
        "params": {},
    }
    patchers = _patch_integrations(tape)
    for p in patchers:
        p.start()
    try:
        result = asyncio.run(search_fn(service, *args, context))
        return tape.accessed, None, result
    except Exception as e:  # noqa: BLE001 — the assertion IS the finding
        return tape.accessed, e, None
    finally:
        for p in patchers:
            p.stop()


def _dispatch_search(service):
    """The planner path: execute(service, 'search') → _dispatch_execution."""
    svc = UniversalIntegrationService(workspace_id="default")
    return _run(
        lambda s, context: svc._dispatch_execution(
            s, "search", {"query": "parity probe", "limit": 5}, context),
        service,
    )


def _search_storage_entry(service):
    """The MCP fan-out path: search() → _search_storage."""
    svc = UniversalIntegrationService(workspace_id="default")
    return _run(lambda s, context: svc._search_storage(s, "parity probe", context), service)


def _real_class(service):
    """The real service class behind a catalog name, via the static
    registry map — None when the service has no registry entry."""
    from core.integration_registry import DEFAULT_SERVICE_REGISTRY

    path = DEFAULT_SERVICE_REGISTRY.get(service)
    if not path:
        return None
    module_name, class_name = path.split(":")
    try:
        return getattr(importlib.import_module(module_name), class_name)
    except Exception:
        return None


def _advertised():
    return sorted(
        s for s in _SERVICE_DESCRIPTIONS if s not in PLATFORM_SERVICES
    )


# ── the parity assertions ───────────────────────────────────────────────


@pytest.mark.parametrize("service", _advertised())
def test_planner_search_dispatch_reaches_a_real_method(service):
    accessed, error, _ = _dispatch_search(service)
    assert error is None, (
        f"{service}.search raised {type(error).__name__}: {error} — the "
        "planner catalog advertises this service but its dispatch is "
        "broken (the live-2026-09-03 WorkDrive AttributeError class). "
        "Fix the dispatch or remove the service from _SERVICE_DESCRIPTIONS."
    )
    if service in _EMPTY_OK:
        return
    assert accessed, (
        f"{service}.search dispatched to NOTHING — silent fall-through "
        "with empty data (the box/_search_storage bug class). The planner "
        "catalog advertises this service; wire its search."
    )
    real = _real_class(service)
    if real is not None:
        missing = {n for n in accessed
                   if not hasattr(real, n) and n not in _ATTR_OK}
        assert not missing, (
            f"{service}: dispatch calls {sorted(missing)} which do not "
            f"exist on {real.__name__} — AttributeError class."
        )


@pytest.mark.parametrize("service", sorted(STORAGE_FAMILY))
def test_storage_search_entry_reaches_a_real_method(service):
    accessed, error, _ = _search_storage_entry(service)
    assert error is None, (
        f"_search_storage({service}) raised {type(error).__name__}: {error}"
    )
    assert accessed, (
        f"_search_storage({service}) fell through to [] without touching "
        "the service — the MCP no-platform search_files fan-out silently "
        "returns nothing for it."
    )
    real = _real_class(service)
    if real is not None:
        missing = {n for n in accessed
                   if not hasattr(real, n) and n not in _ATTR_OK}
        assert not missing, (
            f"{service}: _search_storage calls {sorted(missing)} which do "
            f"not exist on {real.__name__}."
        )


def test_catalog_services_all_have_dispatch_targets():
    """Every advertised integration name must resolve somewhere — a name
    the planner offers but nothing knows about is a guaranteed dead end."""
    from core.integration_registry import DEFAULT_SERVICE_REGISTRY

    unresolvable = []
    for service in _advertised():
        if _real_class(service) is None and service not in (
            # resolved by direct service imports, not the static registry map:
            "outlook", "gmail", "zoho_mail", "discord", "telegram",
            "whatsapp", "slack", "teams",
            # quickbooks executes through the finance family with a
            # registry-resolved adapter; zendesk through ZendeskService —
            # neither is keyed in DEFAULT_SERVICE_REGISTRY.
            "quickbooks", "zendesk",
        ):
            unresolvable.append(service)
    assert not unresolvable, (
        f"planner advertises {unresolvable} but the registry has no "
        "service class for them"
    )
