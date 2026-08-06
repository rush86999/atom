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

_VALID_STORAGE_BACKENDS = {"local", "cloud", "auto"}


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

    base_image = manifest.get("base_image", "python:3.11-slim")
    if base_image not in _base_image_allowlist():
        raise ValueError(
            f"base_image '{base_image}' is not in MINIAPP_BASE_IMAGE_ALLOWLIST"
        )

    storage = manifest.get("storage") or {}
    if "enabled" in storage and not isinstance(storage.get("enabled"), bool):
        raise ValueError("manifest.storage.enabled must be a boolean")
    if storage.get("backend") is not None and storage.get("backend") not in _VALID_STORAGE_BACKENDS:
        raise ValueError(
            f"manifest.storage.backend must be one of {sorted(_VALID_STORAGE_BACKENDS)}"
        )
    if storage.get("max_bytes_per_object") is not None:
        if not isinstance(storage.get("max_bytes_per_object"), int) or storage.get("max_bytes_per_object") <= 0:
            raise ValueError("manifest.storage.max_bytes_per_object must be an int > 0")

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
        "mcp_servers": [],
        "entrypoint": "logic",
        "dependencies": dependencies or [],
        "base_image": base_image or "python:3.11-slim",
        "assets": [],
        "storage": {
            "enabled": True,
            "backend": "local",
            "max_bytes_per_object": DEFAULT_ASSET_INJECTION_CAP,
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
    from core.models import Canvas, CanvasLogic, MiniApp

    tenant_id = getattr(viewer, "tenant_id", None) or "default"
    workspace_id = getattr(viewer, "workspace_id", None)
    base_image = spec.get("base_image", "python:3.11-slim")
    description = spec.get("description")

    canvas_id = str(uuid.uuid4())
    app_id = str(uuid.uuid4())
    source_canvas = Canvas(
        id=canvas_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        created_by=str(viewer.id),
        name=name,
        description=description,
        canvas_type="mini_app",
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

    manifest = _build_starter_manifest(name, declared_scopes, dependencies, base_image)
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


def _llm_scaffold(name: str, spec: Dict[str, Any]) -> Optional[str]:
    """Optional LLM-assisted starter body. Deterministic template is the default."""
    try:
        from core.llm_service import llm_service  # type: ignore[import-not-found]
        prompt = (
            "Write short Python for a canvas mini-app that reads a `state` dict "
            f"(name '{name}') and returns an updated `state`. Only pure Python, "
            "no imports beyond stdlib. Return only code."
        )
        resp = llm_service.complete(prompt)
        code = (resp or "").strip()
        if code:
            syntax_check(code)
            return code
    except Exception as e:  # noqa: BLE001
        logger.warning("LLM scaffold failed, using template: %s", e)
    return None


# ===========================================================================
# Publish — snapshot the blueprint (copy-on-install)
# ===========================================================================
def publish(app: Any, db: Session) -> Dict[str, Any]:
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
    app.status = "published"
    db.commit()

    return {"success": True, "app_id": app.id, "version": app.version}


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

    new_id = str(uuid.uuid4())
    canvas = Canvas(
        id=new_id,
        tenant_id=app.tenant_id,
        workspace_id=app.workspace_id,
        created_by=str(viewer.id),
        name=app.name,
        description=app.description,
        canvas_type="mini_app",
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
            tenant_id=app.tenant_id,
            canvas_id=new_id,
            component_id=inst.get("component_id"),
            config=strip_credentials(inst.get("config")) if inst.get("config") else inst.get("config"),
            position=inst.get("position"),
            z_index=inst.get("z_index", 0),
        ))

    # State store: version 1.
    db.add(CanvasState(
        canvas_id=new_id,
        tenant_id=app.tenant_id,
        created_by=str(viewer.id),
        state=initial_state,
        version=1,
    ))

    # Exactly one audit row.
    db.add(CanvasAudit(
        canvas_id=new_id,
        tenant_id=app.tenant_id,
        action_type="mini_app_install",
        user_id=str(viewer.id),
        canvas_type="mini_app",
        details_json={"app_id": app.id},
    ))

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
        '"storage_ops": globals().get("storage_ops", [])}))',
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
        if isinstance(data, str):
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
    from core.mini_app_storage import get_mini_app_storage
    from core.models import Canvas, CanvasState, MiniApp, MiniAppAsset
    from core.sandbox_policy import PolicyIssuer

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

            run_inputs: Dict[str, Any] = dict(inputs or {})
            run_inputs["state"] = current_state
            run_inputs["assets"] = asset_inputs
            run_inputs["storage_ops"] = []
            run_inputs["mini_app_id"] = app.id

            namespace = f"{app.id}-{canvas_id}"[:80]
            fs_root = os.path.join(get_miniapp_rootfs_dir(), "policy", namespace)
            os.makedirs(fs_root, exist_ok=True)
            policy = PolicyIssuer().issue(
                run_id=f"miniapp-{namespace}",
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
            result = await runtime.execute_python(
                wrapped,
                policy=policy,
                inputs=run_inputs,
                image=app.runtime_image,  # None → base template rootfs
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
            if envelope is not None:
                new_state = envelope.get("state") or {}
                max_bytes = (manifest.get("storage") or {}).get(
                    "max_bytes_per_object", DEFAULT_ASSET_INJECTION_CAP
                )
                storage = get_mini_app_storage(canvas.tenant_id, canvas_id)
                for raw_op in envelope.get("storage_ops") or []:
                    valid = _validate_storage_op(raw_op, max_bytes)
                    if valid is None:
                        logger.warning("Invalid storage_op skipped: %s", raw_op)
                        continue
                    if persist:
                        op_results.append(_execute_storage_op(valid, storage, db, canvas, app))
                    else:
                        # Harness dry-run: propose the op, never execute it (no
                        # backend store, no MiniAppAsset rows, no commit).
                        op_results.append({
                            "op": valid["op"],
                            "key": valid["key"],
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
            }
    except RuntimeError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:  # noqa: BLE001
        logger.error("MiniApp run_stateful failed for %s: %s", canvas_id, e)
        return {"success": False, "error": "Mini-app run failed"}


def _execute_storage_op(
    valid_op: Dict[str, Any],
    storage: Any,
    db: Session,
    canvas: Any,
    app: Any,
) -> Dict[str, Any]:
    """Execute a validated storage op against the backend + rows."""
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
                    created_by=app.created_by,
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
            return {"op": "get", "key": key, "ok": True, "data": data.decode("utf-8", errors="replace")}
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
    from core.models import CanvasAudit

    version = _logic_version_number(db, canvas_id)
    db.add(CanvasAudit(
        canvas_id=canvas_id,
        tenant_id=tenant_id,
        action_type="mini_app_logic",
        user_id=actor_id,
        canvas_type="mini_app",
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
    record_logic_snapshot(
        db,
        canvas_id=app.blueprint_canvas_id,
        tenant_id=app.tenant_id,
        app_id=app.id,
        source=source,
        actor_id=actor_id,
    )
    return {"success": True, "app_id": app.id, "version": version, "source": source}


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
    }
