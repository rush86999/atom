"""Mini Apps — stateful, resumable canvas-UI apps on Firecracker microVMs.

Model (MVC): View = ``Canvas`` · Controller = ``CanvasLogic`` (sandboxed
one-shot per invocation in a Firecracker microVM; state round-tripped via
``CanvasState``; storage ops host-mediated) · Model = ``MiniApp`` manifest.

Locked decisions:
  * Firecracker microVM is the ONLY mini-app runtime — no Docker/E2B fallback.
    ``get_miniapp_runtime()`` fails closed.
  * Instance state lives in ``CanvasState`` (dedicated, versioned, latest-wins)
    — NOT the ``CanvasAudit`` trail.
  * Viewer-tier caps declared scopes (never widens).
  * Copy-on-install: publishing snapshots a blueprint; installing hydrates a
    fresh immutable instance; updates ship as new versions.
  * External deps are baked into a per-app ext4 rootfs by an OPERATOR script
    (``scripts/build_miniapp_rootfs.sh``); the API only scans fail-closed and
    verifies rootfs presence — it never auto-builds.
"""
from __future__ import annotations

import json
import logging
import os
import re
import textwrap
import uuid
from dataclasses import replace
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from core.mini_app_runtime import get_miniapp_runtime, get_miniapp_rootfs_dir

logger = logging.getLogger(__name__)

# Raw tools a mini app may declare (mirror the STUDENT tier floor + canvas
# helpers). Dotted action-registry names are validated against the registry.
_RAW_TOOL_SCOPES = (
    "canvas_render",
    "canvas_get_state",
    "memory_search",
    "memory_recall",
    "search_reasoning_steps_lexical",
)

_MINIAPP_STATE_MARKER = "__MINIAPP_STATE__:"

# Default max bytes per injected asset object (manifest storage config).
DEFAULT_ASSET_INJECTION_CAP = 5 * 1024 * 1024  # 5 MiB

# Valid storage backends for the manifest storage config.
_VALID_STORAGE_BACKENDS = {"local", "cloud", "auto"}

# Base canvas types a mini-app can build on (manifest["canvas_type"]).
# "mini_app" is the native default; ANY other app family is buildable — the
# type is a free slug ("crm", "accounting", "inventory", "sheets", …) that
# becomes the blueprint/instance Canvas.canvas_type, so the typed view
# applies. Unknown slugs self-register in canvas_type_registry with generic
# defaults (no hardcoded domain list).
NATIVE_BASE_CANVAS_TYPE = "mini_app"
_BASE_CANVAS_TYPE_RE = re.compile(r"[a-z][a-z0-9_-]{0,49}")


def _validate_base_canvas_type(canvas_type: str) -> str:
    """Normalize + validate a base canvas type; register unknown kinds.

    Raises ``ValueError`` when the slug is malformed — the string is the
    contract, so any app kind is expressible without backend changes.
    """
    normalized = (canvas_type or "").strip().lower()
    if not _BASE_CANVAS_TYPE_RE.fullmatch(normalized):
        raise ValueError(
            "Base canvas type must be a slug matching [a-z][a-z0-9_-]{0,49} "
            f"(e.g. 'crm', 'accounting', 'inventory', 'sheets'); got {canvas_type!r}"
        )
    from core.canvas_type_registry import canvas_type_registry

    canvas_type_registry.register_type(normalized)
    return normalized

# Host pre-fetched data-source types (read bridge). Extensible: a new entry
# only needs an injector in _inject_data_sources + a validate_manifest entry.
_VALID_DATA_SOURCE_TYPES = {"documents.search"}


# ===========================================================================
# Manifest validation
# ===========================================================================
def _known_scope_names() -> Tuple[str, ...]:
    """Known mini-app scope names: action-registry actions ∪ raw tools."""
    try:
        from core.action_registry import action_registry
        actions = tuple(action_registry.list_actions())
    except Exception:  # noqa: BLE001
        actions = ()
    return actions + _RAW_TOOL_SCOPES


def _base_image_allowlist() -> Tuple[str, ...]:
    raw = os.getenv(
        "MINIAPP_BASE_IMAGE_ALLOWLIST",
        "python:3.11-slim",
    )
    return tuple(p.strip() for p in raw.split(",") if p.strip())


def validate_manifest(manifest: Any) -> None:
    """Validate a mini-app manifest; raise ``ValueError`` on any violation."""
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")

    scopes = manifest.get("declared_scopes")
    if not isinstance(scopes, list) or not scopes:
        raise ValueError("manifest.declared_scopes must be a non-empty list")
    known = set(_known_scope_names())
    for s in scopes:
        if s == "*":
            continue
        if not isinstance(s, str) or s not in known:
            raise ValueError(
                f"unknown declared scope '{s}'. Allowed: '*' or one of {sorted(known)}"
            )

    deps = manifest.get("dependencies", [])
    if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
        raise ValueError("manifest.dependencies must be a list of strings")

    if manifest.get("canvas_type") is not None:
        if not isinstance(manifest.get("canvas_type"), str):
            raise ValueError("manifest.canvas_type must be a string")
        _validate_base_canvas_type(manifest["canvas_type"])

    base_image = manifest.get("base_image", "python:3.11-slim")
    if base_image not in _base_image_allowlist():
        raise ValueError(
            f"base_image '{base_image}' is not in MINIAPP_BASE_IMAGE_ALLOWLIST"
        )

    storage = manifest.get("storage") or {}
    if not isinstance(storage, dict):
        raise ValueError("manifest.storage must be an object")
    if "enabled" in storage and not isinstance(storage.get("enabled"), bool):
        raise ValueError("manifest.storage.enabled must be a boolean")
    if storage.get("backend") is not None and storage.get("backend") not in _VALID_STORAGE_BACKENDS:
        raise ValueError(
            f"manifest.storage.backend must be one of {sorted(_VALID_STORAGE_BACKENDS)}"
        )
    if storage.get("max_bytes_per_object") is not None:
        if not isinstance(storage.get("max_bytes_per_object"), int) or storage.get("max_bytes_per_object") <= 0:
            raise ValueError("manifest.storage.max_bytes_per_object must be an int > 0")

    # Records store + read-bridge config (mini-app data layer).
    db_cfg = manifest.get("db") or {}
    if not isinstance(db_cfg, dict):
        raise ValueError("manifest.db must be an object")
    if "enabled" in db_cfg and not isinstance(db_cfg.get("enabled"), bool):
        raise ValueError("manifest.db.enabled must be a boolean")
    if db_cfg.get("max_records_per_series") is not None:
        if not isinstance(db_cfg.get("max_records_per_series"), int) or db_cfg.get("max_records_per_series") <= 0:
            raise ValueError("manifest.db.max_records_per_series must be an int > 0")
    if db_cfg.get("max_record_bytes") is not None:
        if not isinstance(db_cfg.get("max_record_bytes"), int) or db_cfg.get("max_record_bytes") <= 0:
            raise ValueError("manifest.db.max_record_bytes must be an int > 0")
    record_queries = db_cfg.get("record_queries") or []
    if not isinstance(record_queries, list) or not all(isinstance(s, str) and s for s in record_queries):
        raise ValueError("manifest.db.record_queries must be a list of non-empty strings")
    from core.mini_app_db_service import SERIES_RE
    for s in record_queries:
        if SERIES_RE.fullmatch(s) is None:
            raise ValueError(f"manifest.db.record_queries entry '{s}' must match {SERIES_RE.pattern}")

    # Read bridge — existing system data (host pre-fetch).
    data_sources = manifest.get("data_sources") or []
    if not isinstance(data_sources, list):
        raise ValueError("manifest.data_sources must be a list")
    for ds in data_sources:
        if not isinstance(ds, dict):
            raise ValueError("each manifest.data_sources entry must be an object")
        if not isinstance(ds.get("type"), str) or ds["type"] not in _VALID_DATA_SOURCE_TYPES:
            raise ValueError(
                f"manifest.data_sources type must be one of {sorted(_VALID_DATA_SOURCE_TYPES)}"
            )

    # integrations — host-side pre-fetch of 3rd-party integration data (NOT
    # MCP protocol despite the legacy name; routes through
    # ExternalIntegrationService / the Node bridge). ``mcp_servers`` is a
    # deprecated alias kept for backward compatibility.
    if "mcp_servers" in manifest and "integrations" not in manifest:
        logger.warning(
            "manifest.mcp_servers is deprecated; rename to 'integrations'. "
            "The field routes through ExternalIntegrationService, not MCP."
        )
    integrations = manifest.get("integrations")
    if integrations is None:
        integrations = manifest.get("mcp_servers") or []
    if not isinstance(integrations, list):
        raise ValueError("manifest.integrations must be a list")
    for ms in integrations:
        if not isinstance(ms, dict):
            raise ValueError("each manifest.integrations entry must be an object")
        if not isinstance(ms.get("service"), str) or not ms.get("service"):
            raise ValueError("manifest.integrations[].service must be a non-empty string")
        if not isinstance(ms.get("action"), str) or not ms.get("action"):
            raise ValueError("manifest.integrations[].action must be a non-empty string")
        if ms.get("params") is not None and not isinstance(ms.get("params"), dict):
            raise ValueError("manifest.integrations[].params must be an object")

    assets = manifest.get("assets", [])
    if not isinstance(assets, list) or not all(isinstance(a, str) for a in assets):
        raise ValueError("manifest.assets must be a list of strings")

    if "tests" in manifest:
        validate_tests(manifest["tests"])


def validate_tests(tests: Any) -> None:
    """Validate an acceptance-test list; raise ``ValueError`` on any violation.

    Each case is a dict: ``{name?, initial_state?, inputs?, expect_state?,
    expect_ops?}``. At least one of ``expect_state``/``expect_ops`` is required
    (an assertion-less case would always pass and teach the agent nothing).
    ``expect_state`` is a subset match (every key must be present with an equal
    value); ``expect_ops`` is a subset of ``{op, key}`` pairs the run must
    propose. See ``run_tests``.
    """
    if not isinstance(tests, list):
        raise ValueError("tests must be a list")
    for case in tests:
        if not isinstance(case, dict):
            raise ValueError("each test case must be an object")
        for field in ("initial_state", "inputs", "expect_state"):
            if field in case and not isinstance(case[field], dict):
                raise ValueError(f"test.{field} must be an object")
        if "expect_ops" in case and not isinstance(case["expect_ops"], list):
            raise ValueError("test.expect_ops must be a list")
        if "name" in case and not isinstance(case["name"], str):
            raise ValueError("test.name must be a string")
        if "expect_state" not in case and "expect_ops" not in case:
            raise ValueError(
                "each test case must declare expect_state and/or expect_ops"
            )


# ===========================================================================
# Runtime preparation — fail-closed dependency scan + rootfs verification
# ===========================================================================
def prepare_runtime(app: Any, db: Session) -> Optional[str]:
    """Resolve/verify the per-app rootfs for ``app``; return its path or None.

    * No dependencies → ``runtime_image=None`` (base template rootfs; guest
      agent pre-baked).
    * With dependencies → fail-closed pip-audit/Safety scan; if unsafe → raise.
      The operator-built rootfs ``MINIAPP_ROOTFS_DIR/miniapp-{app.id}.ext4``
      MUST exist (raise ``RuntimeError`` pointing at the build script — never
      auto-build). Persists ``runtime_image`` and bumps ``runtime_version``.
    """
    from core.models import MiniApp
    from core.package_dependency_scanner import PackageDependencyScanner

    manifest = app.manifest or {}
    deps = manifest.get("dependencies") or []
    if not deps:
        if app.runtime_image is not None:
            app.runtime_image = None
            db.commit()
        return None

    scan = PackageDependencyScanner().scan_packages(list(deps))
    if not scan.get("safe"):
        vulns = scan.get("vulnerabilities") or []
        conflicts = scan.get("conflicts") or []
        raise ValueError(
            f"Dependency scan failed (fail-closed) for app '{app.name}': "
            f"{len(vulns)} vulnerability(s), {len(conflicts)} conflict(s). "
            "Fix dependencies and re-run."
        )

    rootfs_path = os.path.join(get_miniapp_rootfs_dir(), f"miniapp-{app.id}.ext4")
    if not os.path.isfile(rootfs_path):
        raise RuntimeError(
            f"Rootfs for app '{app.id}' not found at {rootfs_path}. Run "
            f"scripts/build_miniapp_rootfs.sh {app.id} to bake dependencies "
            "into the per-app ext4 rootfs (operator step)."
        )

    if app.runtime_image != rootfs_path:
        app.runtime_image = rootfs_path
        app.runtime_version = (app.runtime_version or 0) + 1
        db.commit()
    return rootfs_path


# ===========================================================================
# Effective scopes — viewer tier ∩ declared scopes (never widens)
# ===========================================================================
def resolve_effective_scopes(
    manifest: Dict[str, Any],
    viewer: Any = None,
    tier: Optional[str] = None,
) -> Tuple[str, ...]:
    """Intersect a mini app's declared scopes with the viewer's tier floor.

    **Never-widens guarantee (verified against ``capability_resolver``):**
      * Declared ``["*"]`` → ``capabilities=None`` → ``_normalize_capabilities``
        returns ``UNRESTRICTED``. For any non-AUTONOMOUS tier the resolver then
        returns the tier ``floor`` (the declared ``["*"]`` grants nothing beyond
        it); only AUTONOMOUS (whose floor IS ``("*",)``) yields ``("*",)``.
      * Declared specific scopes → intersected with the tier floor, so a viewer
        can never receive a scope their tier floor excludes.

    Viewer ``None`` → ``"student"`` (read-only floor). The result is therefore
    always ``⊆ tier floor`` — scopes never widen the viewer's tier.
    """
    from core.capability_resolver import resolve_allowed_tools

    declared = manifest.get("declared_scopes") or ["*"]
    if declared == ["*"]:
        proxy = SimpleNamespace(capabilities=None)
    else:
        proxy = SimpleNamespace(capabilities=[str(s) for s in declared])

    if tier is None:
        tier = getattr(viewer, "tier", None) or "student"
    return resolve_allowed_tools(proxy, tier=tier)


# ===========================================================================
# Syntax gate
# ===========================================================================
def syntax_check(source: str) -> None:
    """Parse ``source``; raise ``SyntaxError`` when invalid (harness lint gate)."""
    import ast

    if not source or not source.strip():
        raise SyntaxError("Empty logic source")
    ast.parse(source)


# ===========================================================================
# Scaffold — coding harness entry
# ===========================================================================
_STARTER_LOGIC = '''# Mini-app starter logic
# `state` (dict) and `assets` (dict of bytes/str) are injected as globals.
# To persist new state, assign `state = {...}`.
# To read/write an asset, use the `storage_ops` list, e.g.:
#   storage_ops.append({"op": "put", "key": "data.xlsx", "data": <bytes>, "content_type": "..."})
# To CRUD structured rows, use the `record_ops` list, e.g.:
#   record_ops.append({"op": "append", "series": "chart_data", "data": {"label": "Jan", "value": 12}})
# `records` (dict of pre-fetched own-history series) and `data_sources`
# (documents.search + integration results) are injected when the manifest
# declares record_queries / data_sources / integrations.
# To make a CONDITIONAL integration call mid-run (host-mediated, scope-gated),
# call fetch_integration(service, action, params) — it blocks until the host
# resolves the call and returns the result payload (raises RuntimeError on error):
#   pages = fetch_integration("notion", "search", {"query": state.get("topic", "")})
result = {}
if isinstance(state, dict):
    result = dict(state)
result["runs"] = result.get("runs", 0) + 1
state = result
'''


def _build_starter_manifest(
    name: str,
    declared_scopes: List[str],
    dependencies: List[str],
    base_image: str,
) -> Dict[str, Any]:
    return {
        "declared_scopes": declared_scopes or ["canvas_render", "canvas_get_state"],
        "skills": [],
        "integrations": [],
        "entrypoint": "logic",
        "dependencies": dependencies or [],
        "base_image": base_image or "python:3.11-slim",
        "assets": [],
        "storage": {
            "enabled": True,
            "backend": "local",
            "max_bytes_per_object": DEFAULT_ASSET_INJECTION_CAP,
        },
        "db": {
            "enabled": True,
            "max_records_per_series": 10000,
            "max_record_bytes": 100 * 1024,
            "record_queries": [],
        },
        "initial_state": {},
        "blueprint": {},
    }


def scaffold(
    spec: Dict[str, Any],
    name: str,
    declared_scopes: List[str],
    dependencies: List[str],
    viewer: Any,
    db: Session,
) -> Tuple[Any, str]:
    """Create a source canvas + starter logic + draft MiniApp. Returns (app, canvas_id)."""
    from core.canvas_logic_service import CanvasLogicService
    from core.models import Canvas, CanvasAudit, CanvasLogic, MiniApp

    tenant_id = getattr(viewer, "tenant_id", None) or "default"
    workspace_id = getattr(viewer, "workspace_id", None)
    base_image = spec.get("base_image", "python:3.11-slim")
    description = spec.get("description")
    # The base canvas type is the View the app builds ON: the blueprint (and
    # every installed instance) renders with that type's view. Default keeps
    # the native mini_app type.
    canvas_type = _validate_base_canvas_type(str(spec.get("canvas_type") or NATIVE_BASE_CANVAS_TYPE))

    canvas_id = str(uuid.uuid4())
    app_id = str(uuid.uuid4())
    source_canvas = Canvas(
        id=canvas_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        created_by=str(viewer.id),
        name=name,
        description=description,
        canvas_type=canvas_type,
        content={"blocks": []},
        style={},
        is_collaborative=True,
        share_token=None,
        status="active",
        # The source canvas is the app's own dev instance — run_stateful()
        # (used by the harness dev-run route) resolves the app via this.
        mini_app_id=app_id,
    )
    db.add(source_canvas)
    db.flush()

    # Starter logic passes ast.parse by construction.
    logic_source = _STARTER_LOGIC
    if os.getenv("ATOM_MINIAAP_LLM_SCAFFOLD", "false").strip().lower() in {"1", "true", "yes", "on"}:
        logic_source = _llm_scaffold(name, spec) or logic_source
    CanvasLogicService(db).save_logic(
        canvas_id=canvas_id,
        source=logic_source,
        language="python",
        created_by=str(viewer.id),
    )

    # First audit row. read_canvas (GET /api/canvas/{id}, the canvas page's
    # load path) serves FROM the audit trail — without a row a freshly
    # scaffolded blueprint 404s on open ("Canvas not found"). The row also
    # stamps the base canvas type so the page renders the typed view.
    db.add(CanvasAudit(
        canvas_id=canvas_id,
        tenant_id=tenant_id,
        action_type="mini_app_scaffold",
        user_id=str(viewer.id),
        canvas_type=canvas_type,
        details_json={"app_id": app_id, "title": name, "content": {"blocks": []}},
    ))
    db.flush()

    manifest = _build_starter_manifest(name, declared_scopes, dependencies, base_image)
    manifest["canvas_type"] = canvas_type
    validate_manifest(manifest)

    app = MiniApp(
        id=app_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        created_by=str(viewer.id),
        name=name,
        description=description,
        version=spec.get("version", "1.0.0"),
        manifest=manifest,
        blueprint_canvas_id=canvas_id,
        status="draft",
        is_public=False,
        share_token=None,
        runtime_image=None,
        runtime_version=0,
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return app, canvas_id


def _run_async(coro: Any) -> Any:
    """Run a coroutine on a fresh event loop in a worker thread.

    ``scaffold`` stays sync but is invoked from async handlers (a running
    loop), where ``asyncio.run``/``run_until_complete`` would raise. A
    dedicated thread with its own loop works in both sync and async contexts.
    """
    import asyncio
    import threading

    box: Dict[str, Any] = {}

    def _worker() -> None:
        loop = asyncio.new_event_loop()
        try:
            box["result"] = loop.run_until_complete(coro)
        except BaseException as e:  # noqa: BLE001
            box["error"] = e
        finally:
            loop.close()

    thread = threading.Thread(target=_worker)
    thread.start()
    thread.join()
    if "error" in box:
        raise box["error"]
    return box.get("result")


def _llm_scaffold(name: str, spec: Dict[str, Any]) -> Optional[str]:
    """Optional LLM-assisted starter body. Deterministic template is the default."""
    try:
        from core.llm_service import LLMService

        async def _generate() -> str:
            svc = LLMService()
            resp = await svc.generate_completion([
                {"role": "user", "content": (
                    "Write short Python for a canvas mini-app that reads a `state` dict "
                    f"(name '{name}') and returns an updated `state`. Only pure Python, "
                    "no imports beyond stdlib. Return only code."
                )},
            ])
            return (resp or {}).get("content") or ""

        code = _run_async(_generate()).strip()
        if code:
            syntax_check(code)
            return code
    except Exception as e:  # noqa: BLE001
        logger.warning("LLM scaffold failed, using template: %s", e)
    return None


# ===========================================================================
# Publish — snapshot the blueprint (copy-on-install)
# ===========================================================================
def _bump_patch_version(version: str) -> str:
    """Semver patch bump ("1.0.0" → "1.0.1"); unparsable strings get ".1"."""
    parts = str(version or "1.0.0").split(".")
    try:
        parts[-1] = str(int(parts[-1]) + 1)
        return ".".join(parts)
    except ValueError:
        return f"{version}.1"


def publish(app: Any, db: Session, public: bool = False) -> Dict[str, Any]:
    """Scan deps + verify rootfs, snapshot source canvas into the blueprint.

    Captures the latest ``CanvasState.state`` (or latest audit details_json) as
    ``initial_state`` and the canvas content/style/logic/component configs as
    ``blueprint``. Credentials are stripped from manifest + blueprint before
    the app is marked ``published``.

    **``initial_state`` is scrubbed too**: ``strip_credentials`` is applied to
    the entire manifest (including ``initial_state`` and ``blueprint.content`` /
    component configs). Any credential-shaped key is removed/zeroed; keys that
    survive are treated as intentional author-provided seed data — never as
    live credentials.
    """
    from core.blueprint_sanitizer import strip_credentials
    from core.canvas_logic_service import CanvasLogicService
    from core.models import Canvas, CanvasLogic, CanvasState, ComponentInstallation
    from sqlalchemy import desc

    prepare_runtime(app, db)  # fail-closed: deps scan + rootfs must exist

    source_canvas_id = app.blueprint_canvas_id
    canvas = db.query(Canvas).filter(Canvas.id == source_canvas_id).first()
    if canvas is None:
        raise ValueError(f"Blueprint canvas {source_canvas_id} not found")

    # initial_state: latest CanvasState, falling back to the latest audit row.
    state_row = (
        db.query(CanvasState)
        .filter(CanvasState.canvas_id == source_canvas_id)
        .order_by(desc(CanvasState.updated_at))
        .first()
    )
    if state_row is not None:
        initial_state = state_row.state
    else:
        from core.models import CanvasAudit

        latest_audit = (
            db.query(CanvasAudit)
            .filter(CanvasAudit.canvas_id == source_canvas_id)
            .order_by(desc(CanvasAudit.created_at))
            .first()
        )
        initial_state = (latest_audit.details_json or {}).get("content", {}) if latest_audit else {}

    logic = CanvasLogicService(db).load_logic(source_canvas_id) or {}
    component_installations = [
        {
            "component_id": inst.component_id,
            "config": inst.config,
            "position": inst.position,
            "z_index": inst.z_index,
        }
        for inst in db.query(ComponentInstallation)
        .filter(ComponentInstallation.canvas_id == source_canvas_id)
        .all()
    ]

    blueprint = {
        "content": canvas.content,
        "style": canvas.style,
        "logic_source": logic.get("source", ""),
        "logic_language": logic.get("language", "python"),
        "component_installations": component_installations,
    }

    manifest = dict(app.manifest or {})
    manifest["initial_state"] = initial_state
    manifest["blueprint"] = blueprint
    # ``strip_credentials`` recursively scrubs api_key/access_token/refresh_token/
    # secret/password keys from the ENTIRE manifest — including initial_state and
    # blueprint.content/component configs. This is load-bearing: a dev who ran
    # ``state["api_key"] = os.getenv(...)`` during authoring would otherwise ship
    # their key into every install. Survivors (keys not matching the credential
    # regex) are treated as intentional author-provided seed data.
    cleaned = strip_credentials(manifest)
    # Belt-and-suspenders: never let a known-credential key through initial_state.
    if isinstance(cleaned.get("initial_state"), dict):
        cleaned["initial_state"] = strip_credentials(cleaned["initial_state"])
    app.manifest = cleaned
    # Updates ship as new versions: the FIRST publish keeps the scaffold
    # version (1.0.0); every re-publish bumps the patch so the
    # MiniAppInstallation.installed_version comparison can signal
    # update-available. Without the bump a re-published app is invisible to
    # every installed instance forever (installed_version never differs).
    if app.status == "published":
        app.version = _bump_patch_version(app.version)
    app.status = "published"
    # Gap C: optionally activate public/share. Publishing publicly mints a
    # share_token for the by-token install path. is_approved stays False until
    # an admin approves (Gap D); public install requires both flags.
    if public:
        import secrets

        app.is_public = True
        if not app.share_token:
            app.share_token = secrets.token_urlsafe(32)
    db.commit()

    return {"success": True, "app_id": app.id, "version": app.version,
            "is_public": bool(app.is_public), "share_token": app.share_token}


# ===========================================================================
# Install — hydrate a fresh instance canvas (copy-on-install)
# ===========================================================================
def install(app: Any, viewer: Any, db: Session) -> str:
    """Hydrate a fresh instance Canvas from ``manifest["blueprint"]``.

    Returns the new ``canvas_id``. Identity/state fields are reset; component
    configs are credential-stripped; exactly one ``mini_app_install`` audit row
    is written. Assets are NOT copied (instance data — uploaded after install).
    """
    from datetime import datetime, timezone

    from core.blueprint_sanitizer import strip_credentials
    from core.canvas_logic_service import CanvasLogicService
    from core.models import Canvas, CanvasAudit, CanvasState, ComponentInstallation

    if app.status != "published":
        raise ValueError(f"App '{app.id}' is not published")

    blueprint = (app.manifest or {}).get("blueprint") or {}
    initial_state = (app.manifest or {}).get("initial_state") or {}

    # Gap B fix: the instance lands in the INSTALLER's tenant/workspace, not the
    # author's. Previously this hardcoded app.tenant_id/app.workspace_id, which
    # meant a cross-tenant install created the instance (+ all its records/
    # assets/state) in the author's namespace — a data-ownership break.
    instance_tenant = getattr(viewer, "tenant_id", None) or app.tenant_id
    instance_workspace = getattr(viewer, "workspace_id", None)
    if instance_workspace is None:
        instance_workspace = app.workspace_id if str(viewer.id) == str(app.created_by) else None

    new_id = str(uuid.uuid4())
    # Instances render as the app's base canvas type (manifest["canvas_type"],
    # e.g. "sheets" for an inventory tracker); apps authored before typed
    # scaffolding have no manifest entry and keep the native "mini_app" type.
    instance_canvas_type = (app.manifest or {}).get("canvas_type") or NATIVE_BASE_CANVAS_TYPE
    canvas = Canvas(
        id=new_id,
        tenant_id=instance_tenant,
        workspace_id=instance_workspace,
        created_by=str(viewer.id),
        name=app.name,
        description=app.description,
        canvas_type=instance_canvas_type,
        content=blueprint.get("content"),
        style=blueprint.get("style"),
        is_collaborative=True,
        share_token=None,  # never inherit a share token
        status="active",
        mini_app_id=app.id,
        last_edited_by=str(viewer.id),
        last_edited_at=datetime.now(timezone.utc),
    )
    db.add(canvas)
    db.flush()

    # Controller: copy the source CanvasLogic.
    logic_source = blueprint.get("logic_source") or ""
    logic_language = blueprint.get("logic_language") or "python"
    if logic_source:
        CanvasLogicService(db).save_logic(
            canvas_id=new_id,
            source=logic_source,
            language=logic_language,
            created_by=str(viewer.id),
        )

    # Re-create component installations with credentials stripped.
    for inst in blueprint.get("component_installations") or []:
        db.add(ComponentInstallation(
            tenant_id=instance_tenant,
            canvas_id=new_id,
            component_id=inst.get("component_id"),
            config=strip_credentials(inst.get("config")) if inst.get("config") else inst.get("config"),
            position=inst.get("position"),
            z_index=inst.get("z_index", 0),
        ))

    # State store: version 1.
    db.add(CanvasState(
        canvas_id=new_id,
        tenant_id=instance_tenant,
        created_by=str(viewer.id),
        state=initial_state,
        version=1,
    ))

    # Exactly one audit row.
    db.add(CanvasAudit(
        canvas_id=new_id,
        tenant_id=instance_tenant,
        action_type="mini_app_install",
        user_id=str(viewer.id),
        # The audit row IS what read_canvas serves to the canvas page — stamp
        # the instance's real type so a typed app (inventory, crm, …) renders
        # as that type on first open, not the native mini_app fallback.
        canvas_type=instance_canvas_type,
        details_json={"app_id": app.id},
    ))

    # Gap F: record which version was installed so update-check can signal.
    try:
        from core.models import MiniAppInstallation

        db.add(MiniAppInstallation(
            app_id=app.id,
            canvas_id=new_id,
            tenant_id=instance_tenant,
            installed_by=str(viewer.id),
            installed_version=app.version,
            installed_runtime_version=app.runtime_version or 0,
            source="owned" if str(viewer.id) == str(app.created_by) else "marketplace",
        ))
    except Exception as e:  # noqa: BLE001
        logger.debug("MiniAppInstallation write skipped: %s", e)

    db.commit()
    return new_id


# ===========================================================================
# Stateful run — the controller execution loop
# ===========================================================================
def _read_state(db: Session, canvas_id: str) -> Tuple[Dict[str, Any], int]:
    from core.models import CanvasState

    row = db.query(CanvasState).filter(CanvasState.canvas_id == canvas_id).first()
    if row is None:
        return {}, 0
    return dict(row.state or {}), int(row.version or 0)


def _wrap_source(source: str) -> str:
    """Wrap app source so it runs in a ``try:`` block.

    The wrapper indents the source into a ``try:`` (a column-0 body would be a
    SyntaxError). ``state`` and ``storage_ops`` are injected as exec globals
    via ``inputs``; the guest agent reads the (possibly updated) ``state``
    global after exec and returns it over the vsock reply channel as
    ``state_envelope`` — immune to the host's 64 KiB stdout cap.

    A fallback ``__MINIAPP_STATE__:`` stdout print is kept in ``finally`` so
    older guest agents (without the structured channel) still round-trip state.
    For truncation safety, the host treats a partial stdout marker as a hard
    failure (see ``run_stateful``) rather than silently dropping state.
    """
    header = "try:\n"
    body = textwrap.indent(source or "", "    ")
    epilogue = textwrap.indent(
        "import json\n"
        f'print("{_MINIAPP_STATE_MARKER}" + json.dumps({{"state": state, '
        '"storage_ops": globals().get("storage_ops", []), '
        '"record_ops": globals().get("record_ops", [])}))',
        "    ",
    )
    return header + body + "\n" + epilogue + "\n"


def _parse_envelope(output: str) -> Optional[Dict[str, Any]]:
    """Extract the last ``__MINIAPP_STATE__:`` envelope from stdout/stderr."""
    if not output:
        return None
    idx = output.rfind(_MINIAPP_STATE_MARKER)
    if idx < 0:
        return None
    rest = output[idx + len(_MINIAPP_STATE_MARKER):].split("\n", 1)[0].strip()
    try:
        return json.loads(rest)
    except (json.JSONDecodeError, ValueError):
        return None


def _validate_storage_op(op: Any, max_bytes: int) -> Optional[Dict[str, Any]]:
    if not isinstance(op, dict):
        return None
    op_type = op.get("op")
    if op_type not in {"put", "get", "delete"}:
        return None
    key = op.get("key")
    if not isinstance(key, str) or not key:
        return None
    if len(key) > 500:
        return None
    if op_type == "put":
        data = op.get("data")
        if data is None:
            return None
        encoding = op.get("encoding")
        if encoding == "base64":
            # Binary-safe channel: the JSON envelope carries strings only, so
            # binary bytes arrive base64-encoded. Decode here so the stored
            # bytes match what the guest intended (symmetric with get, which
            # returns base64). Invalid base64 → reject the op.
            import base64

            if not isinstance(data, str):
                return None
            try:
                data = base64.b64decode(data, validate=True)
            except (ValueError, Exception):  # noqa: BLE001
                return None
        elif isinstance(data, str):
            data = data.encode("utf-8")
        elif not isinstance(data, (bytes, bytearray)):
            return None
        if len(data) > max_bytes:
            return None
        return {"op": "put", "key": key, "data": bytes(data), "content_type": op.get("content_type")}
    return {"op": op_type, "key": key}


def _inject_assets(
    manifest: Dict[str, Any],
    tenant_id: str,
    canvas_id: str,
) -> Dict[str, Any]:
    """Retrieve manifest-declared assets into ``inputs["assets"]`` (size-capped)."""
    from core.mini_app_storage import get_mini_app_storage

    storage_cfg = manifest.get("storage") or {}
    cap = storage_cfg.get("max_bytes_per_object", DEFAULT_ASSET_INJECTION_CAP)
    storage = get_mini_app_storage(tenant_id, canvas_id)
    out: Dict[str, Any] = {}
    for key in manifest.get("assets") or []:
        try:
            data = storage.retrieve(key)
            if data is None:
                continue
            if len(data) > cap:
                logger.warning("Asset %s exceeds injection cap %d — skipped", key, cap)
                continue
            out[key] = data.decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            logger.debug("Asset injection %s skipped: %s", key, e)
    return out


# ---------------------------------------------------------------------------
# Read bridge — own-history + documents + integration pre-fetch (host-side).
# The microVM has no network/DB; the host fetches declared sources and injects
# the results as run inputs BEFORE execute_python. Skip-on-failure + size caps
# guarantee a failed source never crashes the run.
# ---------------------------------------------------------------------------
_DEFAULT_DATA_SOURCE_CAP = 5 * 1024 * 1024  # 5 MiB serialized per source


def _inject_record_queries(
    manifest: Dict[str, Any],
    db: Session,
    canvas_id: str,
) -> Dict[str, Any]:
    """Pre-fetch own-history series into ``inputs["records"]`` (read bridge).

    For each series in ``manifest.db.record_queries``, inject the latest
    ``limit`` rows (default 100, desc) as ``{series: [rows]}`` so the app can
    compute over its own accumulated history without cramming it into state.
    """
    from core.mini_app_db_service import query_records

    db_cfg = manifest.get("db") or {}
    limit = db_cfg.get("record_query_limit", 100)
    out: Dict[str, Any] = {}
    for series in db_cfg.get("record_queries") or []:
        try:
            out[series] = query_records(db, canvas_id, series, limit=limit, order="desc")
        except Exception as e:  # noqa: BLE001
            logger.debug("record_queries pre-fetch '%s' skipped: %s", series, e)
    return out


async def _inject_data_sources(
    manifest: Dict[str, Any],
    tenant_id: str,
    workspace_id: Optional[str],
    agent_id: Optional[str],
) -> Dict[str, Any]:
    """Pre-fetch existing-system data into ``inputs["data_sources"]``.

    Currently supports ``documents.search`` (over IngestedDocument /
    KnowledgeDocument). Unknown or failing sources are logged + skipped —
    never crash the run. Results are size-capped (5 MiB serialized).
    """
    out: Dict[str, Any] = {}
    for ds in manifest.get("data_sources") or []:
        ds_type = ds.get("type")
        try:
            if ds_type == "documents.search":
                from core.action_registry import action_registry

                query = (ds.get("query") or "").strip()
                if not query:
                    continue
                res = await _safe_action_call(
                    action_registry, "documents.search",
                    {"query": query, "limit": int(ds.get("limit", 10))},
                    {"user_id": agent_id, "workspace_id": workspace_id},
                )
                payload = res.get("data") if isinstance(res, dict) else None
                if isinstance(payload, dict) and _json_bytes(payload) <= _DEFAULT_DATA_SOURCE_CAP:
                    out.setdefault("documents", []).extend(payload.get("results") or [])
        except Exception as e:  # noqa: BLE001
            logger.debug("data_source %s skipped: %s", ds_type, e)
    return out


async def _inject_integration_sources(
    manifest: Dict[str, Any],
    tenant_id: str,
    workspace_id: Optional[str],
    agent_id: Optional[str],
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Pre-fetch integration data into ``inputs["data_sources"]``.

    ``manifest.integrations`` entries ``{service, action, params}`` are host
    pre-fetches (NOT live guest calls — the microVM has no network). Each
    resolves through the unified dispatcher: native (IntegrationRegistry) →
    Activepieces piece → MCP server. Credentials are resolved host-side
    (tokens never reach the guest). Failures/unknown services are logged +
    skipped; results are size-capped.

    ``mcp_servers`` is a deprecated alias read as a fallback.
    """
    from core.mini_app_integration_dispatch import dispatch

    integrations = manifest.get("integrations")
    if integrations is None:
        integrations = manifest.get("mcp_servers") or []
    out: Dict[str, Any] = {}
    for ms in integrations:
        service = ms.get("service")
        action = ms.get("action")
        if not service or not action:
            continue
        try:
            result = await dispatch(
                service, action, ms.get("params") or {},
                tenant_id=tenant_id, db=db,
            )
            if not result.get("ok"):
                continue
            payload = result.get("data")
            if isinstance(payload, (dict, list)) and _json_bytes(payload) <= _DEFAULT_DATA_SOURCE_CAP:
                out[service] = payload
        except Exception as e:  # noqa: BLE001
            logger.debug("mcp source %s/%s skipped: %s", service, action, e)
    return out


def _json_bytes(value: Any) -> int:
    import json as _json

    try:
        return len(_json.dumps(value).encode("utf-8"))
    except (TypeError, ValueError):
        return _DEFAULT_DATA_SOURCE_CAP + 1


async def _safe_action_call(
    registry: Any,
    name: str,
    args: Dict[str, Any],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute a registry action with a bounded timeout (read-bridge safety)."""
    import asyncio

    try:
        return await asyncio.wait_for(
            registry.execute_action(name, args, context), timeout=10
        )
    except Exception as e:  # noqa: BLE001
        logger.debug("action %s call failed: %s", name, e)
        return {}


def _resolve_integration_credentials(
    tenant_id: str, service: str, db: Optional[Session]
) -> Dict[str, Any]:
    """Resolve credentials for an integration pre-fetch (host-side only).

    Looks up ``IntegrationToken`` by (tenant_id, provider=service); at-rest
    values are decrypted via the P0 token-encryption layer
    (``decrypt_token`` — transparent plaintext fallback for legacy rows).
    Returns ``{}`` when unconfigured (caller skips the source). The guest
    NEVER receives this dict — only the action result.
    """
    try:
        from core.models import IntegrationToken
        from core.privsec.token_encryption import decrypt_token

        def _lookup(sess: Session) -> Optional[Dict[str, Any]]:
            row = (
                sess.query(IntegrationToken)
                .filter(
                    IntegrationToken.tenant_id == tenant_id,
                    IntegrationToken.provider == service,
                )
                .order_by(IntegrationToken.updated_at.desc())
                .first()
            )
            if row is None:
                return None
            return {
                "access_token": decrypt_token(row.access_token or ""),
                "refresh_token": decrypt_token(row.refresh_token or "") if row.refresh_token else None,
                "token_type": row.token_type,
                "instance_url": row.instance_url,
            }

        if db is not None:
            return _lookup(db) or {}
        from core.database import get_db_session

        with get_db_session() as sess:
            return _lookup(sess) or {}
    except Exception as e:  # noqa: BLE001
        logger.debug("IntegrationToken resolution for %s skipped: %s", service, e)
    return {}


def _make_callback_handler(
    db: Any,
    tenant_id: str,
    scopes: Tuple[str, ...],
    workspace_id: Optional[str],
    agent_id: Optional[str],
) -> Any:
    """Build the async callback handler passed to ``execute_python``.

    Services guest ``fetch_integration`` callbacks: scope-gated, credential-
    resolved host-side (tokens never reach the guest), size-capped, skip-on-
    failure. Only ``integrations.<service>`` (or ``*``) in the resolved scopes
    permits a call; otherwise the guest sees ``scope_denied`` so user code can
    react gracefully.
    """

    async def handler(request: Dict[str, Any]) -> Dict[str, Any]:
        kind = request.get("kind")
        if kind != "fetch_integration":
            return {"ok": False, "error": f"unknown callback kind: {kind}"}
        service = str(request.get("service") or "")
        action = str(request.get("action") or "")
        params = request.get("params") or {}
        # Resolve the backend FIRST (needed for the scope gate — MCP uses a
        # different scope namespace than native/piece).
        from core.mini_app_integration_dispatch import resolve_backend, dispatch

        backend, server_id = await resolve_backend(service, action)
        # Scope gate: '*' permits everything. native+piece need
        # 'integrations.<service>'; mcp needs 'mcp.<server_id>'.
        if "*" in scopes:
            allowed = True
        elif backend == "mcp" and server_id:
            allowed = f"mcp.{server_id}" in scopes
        else:
            allowed = f"integrations.{service}" in scopes
        if not allowed:
            needed = f"mcp.{server_id}" if backend == "mcp" else f"integrations.{service}"
            logger.warning("callback %s denied by scope gate (need %s)", service, needed)
            return {"ok": False, "error": "scope_denied"}
        try:
            result = await dispatch(service, action, params, tenant_id=tenant_id, db=db)
            payload = result.get("data")
            if _json_bytes(payload) > _DEFAULT_DATA_SOURCE_CAP:
                return {"ok": False, "error": "result_too_large"}
            return {"ok": result.get("ok", True), "data": payload,
                    "backend": result.get("backend")}
        except Exception as e:  # noqa: BLE001
            logger.warning("callback fetch_integration %s.%s failed: %s", service, action, e)
            return {"ok": False, "error": "failed"}

    return handler


async def run_stateful(
    canvas_id: str,
    inputs: Optional[Dict[str, Any]] = None,
    agent_id: Optional[str] = None,
    user_id: Optional[str] = None,
    scopes: Optional[Tuple[str, ...]] = None,
    persist: bool = True,
    viewer: Any = None,
    viewer_tier: Optional[str] = None,
    initial_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run the mini-app logic once (stateful controller run).

    Reads state from ``CanvasState``, injects it (plus assets) into the
    microVM, parses the ``__MINIAPP_STATE__`` envelope, executes host-mediated
    ``storage_ops``, upserts ``CanvasState``, and broadcasts on
    ``user:{user_id}``. ``persist=False`` (harness dry-run) returns the parsed
    state + proposed ops WITHOUT committing or broadcasting.

    ``initial_state`` (optional) overrides the ``CanvasState`` read — used by
    the acceptance-test harness so each test case is self-contained
    (given-state → expected-state) instead of depending on run order. Only
    meaningful with ``persist=False``.
    """
    from core.canvas_logic_service import CanvasLogicService
    from core.mini_app_storage import get_max_object_bytes, get_mini_app_storage
    from core.models import Canvas, CanvasState, MiniApp, MiniAppAsset
    from core.sandbox_policy import PolicyIssuer

    run_id: Optional[str] = None

    try:
        from core.database import get_db_session
        with get_db_session() as db:
            canvas = db.query(Canvas).filter(Canvas.id == canvas_id).first()
            if canvas is None:
                return {"success": False, "error": f"Canvas {canvas_id} not found"}
            if not canvas.mini_app_id:
                return {"success": False, "error": f"Canvas {canvas_id} is not a mini-app instance"}

            app = db.query(MiniApp).filter(MiniApp.id == canvas.mini_app_id).first()
            if app is None:
                return {"success": False, "error": f"MiniApp {canvas.mini_app_id} not found"}

            manifest = app.manifest or {}
            if initial_state is not None:
                current_state, version = dict(initial_state), 0
            else:
                current_state, version = _read_state(db, canvas_id)

            if scopes is None:
                scopes = resolve_effective_scopes(manifest, viewer=viewer, tier=viewer_tier)

            asset_inputs = _inject_assets(manifest, canvas.tenant_id, canvas_id)
            record_inputs = _inject_record_queries(manifest, db, canvas_id)
            data_source_inputs = await _inject_data_sources(
                manifest, canvas.tenant_id, getattr(canvas, "workspace_id", None), agent_id
            )
            mcp_inputs = await _inject_integration_sources(
                manifest, canvas.tenant_id, getattr(canvas, "workspace_id", None), agent_id,
                db=db,
            )
            data_source_inputs.update(mcp_inputs)

            run_inputs: Dict[str, Any] = dict(inputs or {})
            run_inputs["state"] = current_state
            run_inputs["assets"] = asset_inputs
            run_inputs["storage_ops"] = []
            run_inputs["record_ops"] = []
            run_inputs["records"] = record_inputs
            run_inputs["data_sources"] = data_source_inputs
            run_inputs["mini_app_id"] = app.id

            namespace = f"{app.id}-{canvas_id}"[:80]
            fs_root = os.path.join(get_miniapp_rootfs_dir(), "policy", namespace)
            os.makedirs(fs_root, exist_ok=True)
            # Per-run run_id (uuid): caps/KillRun counters keyed on run_id must
            # NOT persist across runs of the same instance — a long-lived
            # mini-app would otherwise permanently burn its budget. Per-canvas
            # identity lives in the run_id prefix and fs_root.
            run_id = f"miniapp-{namespace}-{uuid.uuid4().hex}"
            policy = PolicyIssuer().issue(
                run_id=run_id,
                agent_id=agent_id or "system",
                tier_at_issuance=(viewer_tier or "student").lower(),
                workspace_data_root=fs_root,
            )
            policy = replace(policy, tool_whitelist=tuple(scopes))

            source = CanvasLogicService(db).load_logic(canvas_id)
            if source is None:
                return {"success": False, "error": f"No logic saved for canvas {canvas_id}"}
            wrapped = _wrap_source(source.get("source", ""))

            runtime = get_miniapp_runtime()  # raises RuntimeError when FC unavailable
            callback_handler = _make_callback_handler(
                db, canvas.tenant_id, scopes, getattr(canvas, "workspace_id", None), agent_id
            )
            result = await runtime.execute_python(
                wrapped,
                policy=policy,
                inputs=run_inputs,
                image=app.runtime_image,  # None → base template rootfs
                callback_handler=callback_handler,
            )

            stdout = getattr(result, "stdout", "") or ""
            stderr = getattr(result, "stderr", "") or ""
            exit_code = getattr(result, "exit_code", 0)

            # Prefer the structured state envelope returned over the vsock reply
            # channel (stored in result.metadata["state_envelope"] by the guest
            # agent). This is immune to the 64 KiB stdout cap that would
            # otherwise corrupt large state objects. Fall back to the legacy
            # __MINIAPP_STATE__: stdout marker only when the structured channel
            # is absent (older guest agent / non-FC runtime).
            meta = getattr(result, "metadata", {}) or {}
            envelope = meta.get("state_envelope")
            if not isinstance(envelope, dict):
                envelope = _parse_envelope(stdout) or _parse_envelope(stderr)

            # If stdout was truncated and no structured envelope was found, we
            # cannot trust a partial __MINIAPP_STATE__ line — fail loudly rather
            # than silently no-op (a stateful app would otherwise lose state).
            if (
                envelope is None
                and getattr(result, "truncated", False)
                and _MINIAPP_STATE_MARKER in stdout
            ):
                return {
                    "success": False,
                    "error": (
                        "Mini-app output was truncated before the state envelope "
                        "could be parsed; state unchanged. Reduce state size or "
                        "use the vsock state channel."
                    ),
                    "stdout": stdout,
                    "stderr": stderr,
                    "exit_code": exit_code,
                }

            new_state = current_state
            op_results: List[Dict[str, Any]] = []
            # Bug fix: storage_ops now respects the manifest storage.enabled
            # gate (parity with record_ops' db.enabled gate) AND uses the same
            # per-object cap as the REST upload path so an asset written via the
            # API isn't silently dropped when written back via storage_ops.
            storage_cfg = manifest.get("storage") or {}
            storage_enabled = bool(storage_cfg.get("enabled", True))
            if envelope is not None:
                new_state = envelope.get("state") or {}
                # Per-object cap: manifest override → global upload cap (50 MiB).
                # Previously defaulted to DEFAULT_ASSET_INJECTION_CAP (5 MiB),
                # which silently dropped assets the REST path accepted.
                max_bytes = storage_cfg.get(
                    "max_bytes_per_object", get_max_object_bytes()
                )
                storage = get_mini_app_storage(canvas.tenant_id, canvas_id)
                for raw_op in envelope.get("storage_ops") or []:
                    if not storage_enabled:
                        op_results.append({
                            "op": raw_op.get("op") if isinstance(raw_op, dict) else "?",
                            "key": raw_op.get("key") if isinstance(raw_op, dict) else None,
                            "ok": False,
                            "error": "storage_disabled",
                        })
                        continue
                    valid = _validate_storage_op(raw_op, max_bytes)
                    if valid is None:
                        logger.warning("Invalid storage_op skipped: %s", raw_op)
                        continue
                    if persist:
                        op_results.append(_execute_storage_op(
                            valid, storage, db, canvas, app, created_by=user_id
                        ))
                    else:
                        # Harness dry-run: propose the op, never execute it (no
                        # backend store, no MiniAppAsset rows, no commit).
                        op_results.append({
                            "op": valid["op"],
                            "key": valid["key"],
                            "ok": True,
                            "proposed": True,
                        })

            # Host-mediated record store (mini-app data layer): the guest
            # proposes record_ops; the host validates and executes them against
            # CanvasRecord rows. Disabled store / disabled manifest → every op
            # rejected with db_disabled (fail-closed, never silently dropped).
            record_results: List[Dict[str, Any]] = []
            if envelope is not None:
                from core.mini_app_db_service import (
                    DEFAULT_MAX_RECORD_BYTES, DEFAULT_MAX_RECORDS_PER_SERIES,
                    db_store_enabled,
                )

                db_cfg = manifest.get("db") or {}
                store_ok = db_store_enabled() and bool(db_cfg.get("enabled", True))
                max_record_bytes = db_cfg.get("max_record_bytes", DEFAULT_MAX_RECORD_BYTES)
                max_records = db_cfg.get(
                    "max_records_per_series", DEFAULT_MAX_RECORDS_PER_SERIES
                )
                for raw_op in envelope.get("record_ops") or []:
                    if not store_ok:
                        record_results.append({
                            "op": raw_op.get("op") if isinstance(raw_op, dict) else "?",
                            "ok": False,
                            "error": "db_disabled",
                        })
                        continue
                    valid = _validate_record_op(raw_op, max_record_bytes)
                    if valid is None:
                        logger.warning("Invalid record_op skipped: %s", raw_op)
                        continue
                    if persist:
                        record_results.append(_execute_record_op(
                            valid, db, canvas, app, created_by=user_id,
                            max_records=max_records,
                            max_record_bytes=max_record_bytes,
                        ))
                    else:
                        record_results.append({
                            "op": valid["op"],
                            "series": valid.get("series"),
                            "ok": True,
                            "proposed": True,
                        })

            state_changed = new_state != current_state
            new_version = version

            if persist and (state_changed or envelope is not None):
                new_version = version + 1 if version > 0 else 1
                row = db.query(CanvasState).filter(CanvasState.canvas_id == canvas_id).first()
                if row is None:
                    db.add(CanvasState(
                        canvas_id=canvas_id,
                        tenant_id=canvas.tenant_id,
                        created_by=user_id,
                        state=new_state,
                        version=new_version,
                    ))
                else:
                    row.state = new_state
                    row.version = new_version
                db.commit()

            if persist and user_id:
                await _broadcast_state(user_id, canvas_id, new_version, new_state)
                if record_results:
                    await _broadcast_db(user_id, canvas_id, record_results)

            return {
                "success": True,
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
                "state_changed": state_changed,
                "version": new_version if persist else version,
                "state": new_state,
                "op_results": op_results,
                "proposed_ops": op_results if not persist else [],
                "record_results": record_results,
                "proposed_record_ops": record_results if not persist else [],
                "callbacks": meta.get("callbacks", []),
            }
    except RuntimeError as e:
        # Keep runtime failures generic in the response — the raised message
        # can carry env var names/values and FS paths (e.g. Firecracker
        # provisioning details) that must not reach the agent/API surface.
        # The pointer stays actionable without secrets: mini_app_status
        # surfaces the sanitized reason + the operator setup doc.
        logger.error("MiniApp run_stateful runtime error for %s: %s", canvas_id, e)
        return {
            "success": False,
            "error": (
                "Mini-app runtime unavailable on this host. Probe "
                "mini_app_status for the reason; host setup: "
                "docs/deployment/FIRECRACKER_HOST_SETUP.md"
            ),
        }
    except Exception as e:  # noqa: BLE001
        logger.error("MiniApp run_stateful failed for %s: %s", canvas_id, e)
        return {"success": False, "error": "Mini-app run failed"}
    finally:
        # Per-run counter semantics: release this run's caps/KillRun counters
        # so the next run of the same instance starts fresh.
        try:
            if run_id:
                from core import sandbox_caps
                sandbox_caps.release_run(run_id)
        except Exception as rel_e:  # noqa: BLE001
            logger.debug("mini-app counter release failed: %s", rel_e)


def _execute_storage_op(
    valid_op: Dict[str, Any],
    storage: Any,
    db: Session,
    canvas: Any,
    app: Any,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a validated storage op against the backend + rows.

    ``created_by`` is the acting user of the run (attribution parity with
    ``_execute_record_op``); falls back to the app author for legacy callers.
    """
    from core.models import MiniAppAsset

    op = valid_op["op"]
    key = valid_op["key"]
    try:
        if op == "put":
            uri = storage.store(key, valid_op["data"], content_type=valid_op.get("content_type"))
            row = db.query(MiniAppAsset).filter(
                MiniAppAsset.canvas_id == canvas.id,
                MiniAppAsset.key == key,
            ).first()
            if row is None:
                db.add(MiniAppAsset(
                    canvas_id=canvas.id,
                    tenant_id=canvas.tenant_id,
                    key=key,
                    uri=uri,
                    content_type=valid_op.get("content_type"),
                    size=len(valid_op["data"]),
                    created_by=created_by or app.created_by,
                ))
            else:
                row.uri = uri
                row.content_type = valid_op.get("content_type")
                row.size = len(valid_op["data"])
            db.commit()
            return {"op": "put", "key": key, "ok": True, "uri": uri}
        if op == "get":
            data = storage.retrieve(key)
            if data is None:
                return {"op": "get", "key": key, "ok": False, "error": "not_found"}
            # Base64 so binary assets (xlsx/images/pdf) round-trip losslessly
            # through the JSON envelope. The previous utf-8 decode corrupted
            # non-text assets via errors="replace".
            import base64

            return {
                "op": "get", "key": key, "ok": True,
                "data": base64.b64encode(data).decode("ascii"),
                "encoding": "base64",
                "size": len(data),
            }
        if op == "delete":
            ok = storage.delete(key)
            if ok:
                row = db.query(MiniAppAsset).filter(
                    MiniAppAsset.canvas_id == canvas.id,
                    MiniAppAsset.key == key,
                ).first()
                if row is not None:
                    db.delete(row)
                    db.commit()
            return {"op": "delete", "key": key, "ok": ok}
    except Exception as e:  # noqa: BLE001
        logger.warning("storage_op %s %s failed: %s", op, key, e)
        return {"op": op, "key": key, "ok": False, "error": "failed"}
    return {"op": op, "key": key, "ok": False, "error": "unknown_op"}


def _validate_record_op(op: Any, max_record_bytes: int) -> Optional[Dict[str, Any]]:
    """Validate one ``record_ops`` envelope entry; return None when invalid.

    Mirrors ``_validate_storage_op``: unknown ops are skipped with a warning
    (never executed, never crash the run). Series names must match the
    ``^[a-z0-9_]{1,64}$`` allowlist; record payloads must be JSON-serializable
    dicts within ``max_record_bytes``; filters are equality dicts of scalars.
    """
    from core.mini_app_db_service import validate_filter, validate_record_data, validate_series

    if not isinstance(op, dict):
        return None
    op_type = op.get("op")
    if op_type not in {
        "append", "get", "query", "count", "update", "update_many",
        "delete", "delete_series", "clear", "list_series",
    }:
        return None

    if op_type not in {"clear", "list_series"}:
        series = validate_series(op.get("series"))
        if series is None:
            return None
    else:
        series = None

    valid: Dict[str, Any] = {"op": op_type, "series": series}

    if op_type in {"append", "update", "update_many"}:
        data = op.get("data")
        if not validate_record_data(data, max_record_bytes):
            return None
        valid["data"] = data
    if op_type == "append":
        rid = op.get("id")
        if rid is not None and (not isinstance(rid, str) or not rid):
            return None
        valid["id"] = rid
    if op_type in {"get", "update", "delete"}:
        rid = op.get("id")
        if not isinstance(rid, str) or not rid:
            return None
        valid["id"] = rid
    if op_type in {"query", "count"}:
        f = op.get("filter") or {}
        if not validate_filter(f):
            return None
        valid["filter"] = f
    if op_type == "query":
        limit = op.get("limit", 100)
        if not isinstance(limit, int) or not (1 <= limit <= 10000):
            return None
        order = op.get("order", "desc")
        if order not in {"asc", "desc"}:
            return None
        valid["limit"] = limit
        valid["order"] = order
    if op_type == "update_many":
        f = op.get("filter") or {}
        if not validate_filter(f):
            return None
        valid["filter"] = f
    return valid


def _execute_record_op(
    valid_op: Dict[str, Any],
    db: Session,
    canvas: Any,
    app: Any,
    created_by: Optional[str],
    *,
    max_records: Optional[int] = None,
    max_record_bytes: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute a validated record op against the mini-app DB store.

    ``max_records`` / ``max_record_bytes`` carry the manifest-declared caps so
    the store's limits (rows/series, per-record size after merge) hold on this
    path too.
    """
    from core.mini_app_db_service import (
        DEFAULT_MAX_RECORD_BYTES, append_record, clear_records, count_records,
        delete_record, delete_series, get_record, list_series, query_records,
        update_many_records, update_record,
    )

    op = valid_op["op"]
    series = valid_op.get("series")
    base: Dict[str, Any] = {"op": op}
    if series is not None:
        base["series"] = series
    try:
        if op == "append":
            row = append_record(
                db, canvas.id, canvas.tenant_id, app.id,
                series, valid_op["data"], record_id=valid_op.get("id"),
                created_by=created_by,
                max_records=max_records,
            )
            return {**base, "ok": True, "id": row["id"], "seq": row["seq"]}
        if op == "get":
            row = get_record(db, canvas.id, series, valid_op["id"])
            if row is None:
                return {**base, "ok": False, "error": "not_found"}
            return {**base, "ok": True, "record": row}
        if op == "query":
            rows = query_records(
                db, canvas.id, series,
                f=valid_op.get("filter"), limit=valid_op.get("limit", 100),
                order=valid_op.get("order", "desc"),
            )
            return {**base, "ok": True, "records": rows, "count": len(rows)}
        if op == "count":
            n = count_records(db, canvas.id, series=series, f=valid_op.get("filter"))
            return {**base, "ok": True, "count": n}
        if op == "update":
            row = update_record(
                db, canvas.id, series, valid_op["id"], valid_op["data"],
                max_bytes=max_record_bytes or DEFAULT_MAX_RECORD_BYTES,
            )
            if row is None:
                return {**base, "ok": False, "error": "not_found"}
            return {**base, "ok": True, "record": row}
        if op == "update_many":
            n = update_many_records(
                db, canvas.id, series, valid_op.get("filter") or {}, valid_op["data"],
                max_bytes=max_record_bytes or DEFAULT_MAX_RECORD_BYTES,
            )
            return {**base, "ok": True, "updated": n}
        if op == "delete":
            ok = delete_record(db, canvas.id, series, valid_op["id"])
            return {**base, "ok": ok, "id": valid_op["id"], "error": None if ok else "not_found"}
        if op == "delete_series":
            n = delete_series(db, canvas.id, series)
            return {**base, "ok": True, "deleted": n}
        if op == "clear":
            n = clear_records(db, canvas.id)
            return {**base, "ok": True, "deleted": n}
        if op == "list_series":
            return {**base, "ok": True, "series": list_series(db, canvas.id)}
    except ValueError as e:
        # Store-cap enforcement (rows/series, post-merge size) — fail closed
        # with a structured error, never a generic 500.
        logger.warning("record_op %s cap hit for %s: %s", op, canvas.id, e)
        return {
            **base,
            "ok": False,
            "error": "series_cap" if op == "append" else "size_cap",
        }
    except Exception as e:  # noqa: BLE001
        logger.warning("record_op %s failed for %s: %s", op, canvas.id, e)
        return {**base, "ok": False, "error": "failed"}
    return {**base, "ok": False, "error": "unknown_op"}


async def _broadcast_db(user_id: str, canvas_id: str, results: List[Dict[str, Any]]) -> None:
    """Fire-and-forget WS broadcast of committed record mutations (live charts)."""
    try:
        from core.websockets import manager as ws_manager

        await ws_manager.broadcast(f"user:{user_id}", {
            "type": "canvas:update",
            "data": {
                "action": "mini_app_db",
                "canvas_id": canvas_id,
                "ops": results,
            },
        })
    except Exception as e:  # noqa: BLE001
        logger.debug("MiniApp db WS broadcast skipped: %s", e)


async def _broadcast_state(user_id: str, canvas_id: str, version: int, state: Any) -> None:
    try:
        from core.websockets import manager as ws_manager

        await ws_manager.broadcast(f"user:{user_id}", {
            "type": "canvas:update",
            "data": {
                "action": "mini_app_state",
                "canvas_id": canvas_id,
                "version": version,
                "data": state,
            },
        })
    except Exception as e:  # noqa: BLE001
        logger.debug("MiniApp state WS broadcast skipped: %s", e)


# ===========================================================================
# Agent harness — acceptance tests, logic checkpoints, constraint probe
# ---------------------------------------------------------------------------
# Research-backed additions to the coding harness (generator-evaluator loop,
# clean-state recovery, constraint observability):
#   * ``mini_app_set_tests`` / ``mini_app_run_tests`` — the agent declares
#     given-state→expected-state cases; the harness runs each in the microVM
#     and reports per-case pass/fail + diffs, so the agent self-corrects
#     without a human in the loop (the "feedback loop" / "lint as prompt").
#   * ``mini_app_logic_history`` / ``mini_app_revert_logic`` — every
#     write_logic is checkpointed to the audit trail; the agent can list
#     versions and revert to a known-good source ("leave the environment in a
#     clean state").
#   * ``mini_app_status`` — a constraint probe surfacing syntax validity,
#     effective scopes (viewer tier ∩ declared), dep-scan state, rootfs
#     presence, and Firecracker availability before the agent iterates.
# ===========================================================================


# ---------------------------------------------------------------------------
# Logic checkpoints (versioned snapshots in the audit trail)
# ---------------------------------------------------------------------------
def _logic_version_number(db: Session, canvas_id: str) -> int:
    """1-based next version for a canvas's ``mini_app_logic`` snapshots."""
    from sqlalchemy import func

    from core.models import CanvasAudit

    n = (
        db.query(func.count(CanvasAudit.id))
        .filter(
            CanvasAudit.canvas_id == canvas_id,
            CanvasAudit.action_type == "mini_app_logic",
        )
        .scalar()
    )
    return int(n or 0) + 1


def record_logic_snapshot(
    db: Session,
    canvas_id: str,
    tenant_id: str,
    app_id: str,
    source: str,
    actor_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Append a versioned checkpoint of the app logic to the audit trail."""
    from core.models import Canvas, CanvasAudit

    # Stamp the canvas's real type — the audit trail is what read_canvas
    # serves, so a typed blueprint must not read back as native mini_app.
    canvas_row = db.query(Canvas).filter(Canvas.id == canvas_id).first()
    canvas_type = canvas_row.canvas_type if canvas_row is not None else NATIVE_BASE_CANVAS_TYPE
    version = _logic_version_number(db, canvas_id)
    db.add(CanvasAudit(
        canvas_id=canvas_id,
        tenant_id=tenant_id,
        action_type="mini_app_logic",
        user_id=actor_id,
        canvas_type=canvas_type,
        details_json={"app_id": app_id, "version": version, "source": source},
    ))
    db.commit()
    return {"version": version}


def list_logic_history(app: Any, db: Session) -> List[Dict[str, Any]]:
    """Return the app's logic checkpoint versions, oldest → newest."""
    from core.models import CanvasAudit

    rows = (
        db.query(CanvasAudit)
        .filter(
            CanvasAudit.canvas_id == app.blueprint_canvas_id,
            CanvasAudit.action_type == "mini_app_logic",
        )
        .order_by(CanvasAudit.created_at.asc())
        .all()
    )
    out: List[Dict[str, Any]] = []
    for r in rows:
        details = r.details_json or {}
        source = details.get("source") or ""
        out.append({
            "version": details.get("version"),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "created_by": r.user_id,
            "preview": source[:200],
        })
    return out


def revert_logic(
    app: Any,
    db: Session,
    version: int,
    actor_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Restore a previously checkpointed logic version onto the blueprint canvas.

    Writes a fresh checkpoint for the reverted source so the revert itself is
    visible in history (never silently loses the reverted-from state).
    """
    from core.canvas_logic_service import CanvasLogicService
    from core.models import CanvasAudit

    rows = (
        db.query(CanvasAudit)
        .filter(
            CanvasAudit.canvas_id == app.blueprint_canvas_id,
            CanvasAudit.action_type == "mini_app_logic",
        )
        .order_by(CanvasAudit.created_at.asc())
        .all()
    )
    target = None
    for r in rows:
        if (r.details_json or {}).get("version") == version:
            target = r
            break
    if target is None:
        raise ValueError(f"Logic version {version} not found for app '{app.id}'")

    source = (target.details_json or {}).get("source") or ""
    CanvasLogicService(db).save_logic(
        canvas_id=app.blueprint_canvas_id,
        source=source,
        created_by=actor_id,
    )
    snapshot = record_logic_snapshot(
        db,
        canvas_id=app.blueprint_canvas_id,
        tenant_id=app.tenant_id,
        app_id=app.id,
        source=source,
        actor_id=actor_id,
    )
    # ``version`` is the NEW checkpoint just written (the current head),
    # not the reverted-to target — otherwise callers report a stale version
    # after a revert (the newest checkpoint is what counts as "current").
    return {
        "success": True,
        "app_id": app.id,
        "version": snapshot["version"],
        "reverted_to": version,
        "source": source,
    }


# ---------------------------------------------------------------------------
# Acceptance tests — the generator-evaluator feedback loop
# ---------------------------------------------------------------------------
async def run_tests(
    app_id: str,
    blueprint_canvas_id: str,
    tests: List[Dict[str, Any]],
    viewer: Any = None,
    viewer_tier: Optional[str] = None,
) -> Dict[str, Any]:
    """Run each acceptance case in the microVM (dry) and grade it.

    Each case runs ``run_stateful(..., persist=False, initial_state=case
    ["initial_state"])`` so it is self-contained. ``expect_state`` is a subset
    match; ``expect_ops`` is a subset of proposed ``{op, key}`` pairs. Every
    case is reported (never short-circuited) so the agent sees the full diff
    and can self-correct across all failures at once.
    """
    results: List[Dict[str, Any]] = []
    passed = 0
    for i, case in enumerate(tests):
        name = case.get("name") or f"case-{i}"
        try:
            res = await run_stateful(
                blueprint_canvas_id,
                inputs=case.get("inputs") or {},
                user_id=getattr(viewer, "id", None),
                persist=False,
                viewer=viewer,
                viewer_tier=viewer_tier,
                initial_state=case.get("initial_state"),
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Acceptance case %s raised: %s", name, e)
            results.append({"name": name, "passed": False, "error": "test run raised"})
            continue

        if not res.get("success"):
            results.append({
                "name": name,
                "passed": False,
                "error": res.get("error", "run failed"),
            })
            continue

        actual = res.get("state") or {}
        expect = case.get("expect_state") or {}
        diff = {
            k: {"expected": v, "actual": actual.get(k)}
            for k, v in expect.items()
            if actual.get(k) != v
        }
        state_ok = not diff

        proposed = res.get("proposed_ops") or []
        exp_ops = case.get("expect_ops") or []
        ops_ok = all(
            any(
                (o.get("op") == eo.get("op") and o.get("key") == eo.get("key"))
                for o in proposed
            )
            for eo in exp_ops
        )

        ok = bool(res.get("success")) and state_ok and ops_ok
        if ok:
            passed += 1
        results.append({
            "name": name,
            "passed": ok,
            "state": actual,
            "diff": diff,
            "ops_ok": ops_ok,
            "stdout_tail": (res.get("stdout") or "")[-200:],
        })
    return {"passed": passed, "total": len(results), "results": results}


# ---------------------------------------------------------------------------
# Constraint probe — what the agent can rely on before iterating
# ---------------------------------------------------------------------------
def status_probe(app: Any, db: Session, viewer: Any = None) -> Dict[str, Any]:
    """Return the app's authoring constraints: syntax, scopes, deps, rootfs, FC."""
    import os

    from core.canvas_logic_service import CanvasLogicService
    from core.mini_app_db_service import db_store_enabled
    from core.mini_app_runtime import get_miniapp_rootfs_dir, get_miniapp_runtime
    from core.package_dependency_scanner import PackageDependencyScanner

    manifest = app.manifest or {}
    logic = CanvasLogicService(db).load_logic(app.blueprint_canvas_id) or {}
    source = logic.get("source", "")

    syntax_ok, syntax_error = True, None
    try:
        syntax_check(source)
    except SyntaxError as e:
        syntax_ok, syntax_error = False, str(e)

    deps = manifest.get("dependencies") or []
    scan: Optional[Dict[str, Any]] = None
    if deps:
        try:
            scan = PackageDependencyScanner().scan_packages(list(deps))
        except Exception as e:  # noqa: BLE001
            scan = {"safe": False, "error": "scan failed"}

    rootfs: Optional[Dict[str, Any]] = None
    if deps:
        path = os.path.join(get_miniapp_rootfs_dir(), f"miniapp-{app.id}.ext4")
        rootfs = {"path": path, "present": os.path.isfile(path)}

    runtime_available, runtime_reason = True, None
    try:
        get_miniapp_runtime()
    except RuntimeError as e:
        runtime_available, runtime_reason = False, str(e)
    except Exception as e:  # noqa: BLE001
        runtime_available, runtime_reason = False, "runtime init failed"

    return {
        "app_id": app.id,
        "name": app.name,
        "status": app.status,
        "version": app.version,
        "runtime_image": app.runtime_image,
        "logic": {
            "present": bool(source),
            "syntax_ok": syntax_ok,
            "syntax_error": syntax_error,
        },
        "scopes": {
            "declared": manifest.get("declared_scopes") or ["*"],
            "effective": list(resolve_effective_scopes(manifest, viewer=viewer)),
        },
        "dependencies": {
            "count": len(deps),
            "scan_safe": bool((scan or {}).get("safe", True)),
            "scan": scan,
        },
        "rootfs": rootfs,
        "runtime": {"available": runtime_available, "reason": runtime_reason},
        "tests": {"count": len(manifest.get("tests") or [])},
        "db": {
            "enabled": db_store_enabled() and bool((manifest.get("db") or {}).get("enabled", True)),
            "config": manifest.get("db") or {},
            "record_queries": ((manifest.get("db") or {}).get("record_queries")) or [],
            "data_sources": manifest.get("data_sources") or [],
            "integrations": (manifest.get("integrations")
                              if manifest.get("integrations") is not None
                              else manifest.get("mcp_servers")) or [],
        },
    }
