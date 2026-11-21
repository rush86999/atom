"""Chat → mini-app authoring bridge ("build it by chatting").

Gap this closes: the canvas co-editor chat could edit canvas CONTENT (the
deterministic canvas-editor leg) and run read-only integration lookups (the
tool planner), but the ``mini_app_*`` authoring loop was reachable only from
agent runs (GenericAgent MCP loop) and the RPC surface — so "build me a
mini-app inventory tracker" in chat dead-ended into a content edit or a
generic reply, and docs/architecture/MINI_APPS.md "Path A — ask an agent in
chat" overstated the wiring.

This leg runs BEFORE the canvas-edit leg in the chat flow and drives the SAME
service-layer handlers the agent tools use (``tools/mini_app_tool.py`` —
owner-attributed, fail-closed), so chat and agents share one vocabulary:

  build     scaffold → LLM-author the logic (syntax-gated, one repair retry)
            → dev-run (dry) → report. Never auto-publishes: shipping mints a
            distributed blueprint + instance canvases, so it waits for an
            explicit "publish it".
  publish   re-publish bumps the patch version (updates-as-new-versions).
  install   publishes first when the app is still a draft, then hydrates the
            instance canvas.
  status    constraint probe (syntax, scopes, deps, Firecracker availability).

Fail-closed and fault-isolated: the cheap keyword gate runs first (zero LLM
cost for normal turns); any handler failure becomes an honest chat message —
never an exception into the chat flow, never a fallback that mangles the
canvas content.
"""
from __future__ import annotations

import ast
import inspect
import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Conservative gate: only turns that actually say "mini app" engage this leg.
# Anything else must fall through to the canvas-edit / planner / conversational
# legs untouched.
_MINI_APP_RE = re.compile(r"mini[\s_-]?apps?\b", re.IGNORECASE)

# Deterministic action fallback for hosts without a working structured-LLM
# (BYOK absent). LLM extraction always runs first when a service is available.
_ACTION_HINTS = (
    ("install", re.compile(r"\binstall\b", re.IGNORECASE)),
    ("publish", re.compile(r"\bpublish\b|\bship it\b|\brelease\b", re.IGNORECASE)),
    ("status", re.compile(r"\bstatus\b|\bis it ready\b", re.IGNORECASE)),
    ("build", re.compile(r"\bbuild\b|\bcreate\b|\bmake\b|\bscaffold\b", re.IGNORECASE)),
)

_RUNTIME_DOC = "docs/deployment/FIRECRACKER_HOST_SETUP.md"


def _entry_text(entry: Any) -> str:
    """Text of one history entry. Session history stores
    ``{message, response(dict|str), intent, ...}`` — not chat roles."""
    if isinstance(entry, dict):
        turn = str(entry.get("message") or entry.get("content") or entry.get("text") or "")
        resp = entry.get("response")
        if isinstance(resp, dict):
            resp_text = str(resp.get("message") or "")
        elif resp is not None:
            resp_text = str(resp)
        else:
            resp_text = ""
        return f"{turn} {resp_text}"
    return str(entry or "")


def looks_like_mini_app_request(message: str, history: Any = None) -> bool:
    """Cheap deterministic gate — no LLM cost unless this matches.

    Matches when the message itself mentions a mini-app, OR the recent
    transcript does — follow-ups like "publish it" / "install it" must keep
    working while the conversation is about a mini-app, while a bare
    "publish it" in an unrelated chat must NOT hijack the turn.
    """
    if message and _MINI_APP_RE.search(message):
        return True
    for entry in list(history or [])[-6:]:
        if _MINI_APP_RE.search(_entry_text(entry)):
            return True
    return False


def _transcript(history: Any, last: int = 6) -> str:
    """Compact recent-transcript text for the extraction prompt."""
    lines = []
    for entry in list(history or [])[-last:]:
        text = _entry_text(entry)[:200]
        if text:
            lines.append(text)
    return "\n".join(lines) or "(no prior turns)"


async def _extract_ask(llm_service: Any, message: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """One structured LLM pass over the ask; deterministic fallback without LLM."""
    action, name, kind, description = None, None, None, None
    if llm_service is not None:
        try:
            from pydantic import BaseModel

            class MiniAppAsk(BaseModel):
                """What the user wants done to a mini-app (see module docstring)."""
                action: str  # none | build | publish | install | status
                name: Optional[str] = None
                canvas_type: Optional[str] = None  # crm, accounting, inventory, sheets, …
                description: Optional[str] = None

            from core.chat_tool_planner import _structured_with_fallback

            ask = await _structured_with_fallback(
                llm_service,
                prompt=(
                    "The user is chatting inside a canvas workspace. Extract what they "
                    "want regarding a MINI-APP.\n"
                    "action: 'build' (create a new mini-app), 'publish' (ship/snapshot a "
                    "draft so it can be installed), 'install' (create a usable instance), "
                    "'status' (probe/inspect), or 'none' (not a mini-app action — e.g. a "
                    "question ABOUT mini-apps, or an unrelated edit).\n"
                    "name: a short app name if the user gave one. "
                    "canvas_type: the app family the user named (crm, accounting, "
                    "inventory, sheets, docs, email, …) if any. "
                    "description: one sentence of what the app should do.\n"
                    "Short follow-ups like \"publish it\" refer to the mini-app in the "
                    "recent conversation — resolve them from that context.\n\n"
                    f"Recent conversation:\n{_transcript(history)}\n\n"
                    f"Message: {message}"
                ),
                response_model=MiniAppAsk,
                system_instruction="You return only the requested JSON object.",
            )
            if ask is not None:
                action = (getattr(ask, "action", "") or "").strip().lower() or None
                name = getattr(ask, "name", None)
                kind = getattr(ask, "canvas_type", None)
                description = getattr(ask, "description", None)
        except Exception as e:  # noqa: BLE001 — extraction is best-effort
            logger.debug("mini-app ask extraction failed: %s", e)
    if action is None:
        # No LLM (or it failed): verb hints, build as the default mini-app ask.
        for hint_action, hint_re in _ACTION_HINTS:
            if hint_re.search(message):
                action = hint_action
                break
        else:
            action = "build" if looks_like_mini_app_request(message) else "none"
        # Kind scan for the no-LLM path only — the LLM pass extracts this from
        # context; these are just the common families users type first.
        if kind is None:
            m = re.search(
                r"\b(crms?|accounting|inventor(y|ies)|sheets?|docs?|email|coding|terminal|orchestration|generic)\b",
                message, re.IGNORECASE,
            )
            if m:
                singular = {"crms": "crm", "sheet": "sheets", "doc": "docs"}
                kind = m.group(1).lower()
                kind = singular.get(kind, kind)
    return {"action": action, "name": name, "canvas_type": kind, "description": description}


def _ctx(user_id: str) -> Dict[str, Any]:
    """Dispatch context for the agent-tool handlers — identity from the
    authenticated chat user only (never client-supplied actor ids)."""
    return {"user_id": user_id}


def _scoped_canvas_lessons(user_id: str, canvas_id: str, query: str) -> str:
    """Return scoped lesson block for a canvas, or "" on any failure."""
    try:
        from core.request_scope import current_request_scope
        from core.database import get_db_session
        from core.models import AgentRegistry, User
        from services.canvas_context_service import CanvasContextService
        from core.student_learning_service import format_lessons_block, get_agent_lessons

        scope = current_request_scope()
        tenant_id = scope.get("tenant_id")
        workspace_id = scope.get("workspace_id")
        if not tenant_id or not workspace_id:
            return ""

        with get_db_session() as db:
            user = db.get(User, user_id)
            if user is None:
                return ""
            if user.tenant_id != tenant_id or user.workspace_id != workspace_id:
                return ""

            context = CanvasContextService(db, tenant_id).get_context(canvas_id, user_id)
            if context is None or not getattr(context, "agent_id", None):
                return ""

            agent = db.get(AgentRegistry, context.agent_id)
            if agent is None:
                return ""
            if agent.tenant_id != tenant_id or agent.workspace_id != workspace_id:
                return ""

            lessons = get_agent_lessons(
                db,
                agent.id,
                query=query,
                include_workspace=False,
                task_context={"canvas_type": context.canvas_type},
                workspace_id=workspace_id,
                limit=5,
            )

            accepted = []
            for lesson in lessons or []:
                if not isinstance(lesson, dict):
                    continue

                # Explicit scope on the lesson must match when stated.
                lesson_tenant = lesson.get("tenant_id")
                if lesson_tenant is not None and lesson_tenant != tenant_id:
                    continue
                lesson_workspace = lesson.get("workspace_id")
                if lesson_workspace is not None and lesson_workspace != workspace_id:
                    continue

                source = lesson.get("source")
                if source == "teacher":
                    pass
                elif source == "observation":
                    if lesson.get("observation_type") != "human_correction":
                        continue
                    details = lesson.get("details")
                    if not isinstance(details, dict):
                        continue
                    if details.get("distilled") is not True:
                        continue
                else:
                    continue

                # Project only rule text/topic; never pass raw canvas or correction payloads.
                accepted.append(
                    {
                        "lesson": lesson.get("lesson") or lesson.get("summary") or "",
                        "topic": lesson.get("topic"),
                    }
                )

            return format_lessons_block(accepted)
    except Exception:
        return ""


# Words that carry no request intent on their own ("build it", "make an app").
# Used only to decide whether a lesson lookup has a meaningful query.
_QUERY_STOPWORDS = frozenset({
    "a", "an", "the", "it", "me", "my", "please", "can", "you", "could",
    "would", "build", "create", "make", "scaffold", "new", "one", "app",
    "apps", "mini", "mini-app", "mini_app", "for", "of", "and", "with",
    "to", "this", "that", "some",
})


def _meaningful_query(text: Optional[str]) -> str:
    """Normalized request text when it says something beyond a bare
    imperative; ``""`` when blank or when only action/filler words remain."""
    query = re.sub(r"\s+", " ", str(text or "")).strip()
    if not query:
        return ""
    words = re.findall(r"[a-z0-9][a-z0-9_-]*", query.lower())
    if not any(w not in _QUERY_STOPWORDS and len(w) >= 2 for w in words):
        return ""
    return query


def _build_logic_prompt(name: str, kind: Optional[str], description: Optional[str],
                        lessons: Optional[str] = None) -> str:
    what = description or (
        f"{name}: track items and counts in state, bumping a counter each "
        "run, and exposing everything through state keys."
    )
    prompt = (
        "Write the Python controller for an Atom canvas mini-app.\n"
        "Write executable top-level statements. The runtime supplies the state "
        "dict and each per-run input field as a separate global. To persist "
        "results, update or assign the global state dict using JSON-serializable "
        "values. No function is called automatically. There is no inputs "
        "dictionary. Controllers run unattended: every per-run input field is "
        "already a global, so never call input() or wait for interactive input — "
        "an interactive call makes grading wait until the runtime stops. For "
        "example, if the run provides a field named rows, read it directly as "
        "rows and save a count with state['count'] = len(rows). Stdlib only.\n"
        f"App name: {name}. App family/kind: {kind or 'general'}. "
        f"What it should do: {what}\n"
    )
    lessons_text = (lessons or "").strip()
    if lessons_text:
        prompt += (
            "Lessons from this canvas (background only — follow them where they "
            "help, but the runtime contract above always wins):\n"
            f"{lessons_text}\n"
        )
    return prompt + "Keep it under 40 lines. Return ONLY the code."


_FENCE_RE = re.compile(r"```[a-z]*\s*\n(.*?)```", re.DOTALL)


def _strip_code_fences(text: str) -> str:
    """LLMs habitually wrap code in ```python fences — the syntax gate (and
    ast.parse) reject them. Extract the fenced body when present."""
    m = _FENCE_RE.search(text or "")
    return (m.group(1) if m else (text or "")).strip()


def _valid_controller_error(value: Any) -> Optional[str]:
    """Mirror the runtime's exact typed-controller error allowlist."""
    from core.mini_app_service import valid_controller_error

    return valid_controller_error(value)


def _repair_failure_diagnostics(failures: Any) -> Any:
    """Project repair feedback without leaking runtime output or inputs.

    Typed deterministic controller failures are reduced to their case name and
    exact error type. Ordinary assertion mismatches keep their existing shape
    (diff/state/etc.) so repair behavior for them is unchanged.
    """
    if not isinstance(failures, (list, tuple)):
        return failures
    diagnostics: List[Any] = []
    for row in failures:
        if not isinstance(row, dict):
            diagnostics.append(row)
            continue
        controller_error = _valid_controller_error(row.get("controller_error"))
        if controller_error is None:
            diagnostics.append(row)
            continue
        diagnostic = {"controller_error": controller_error}
        if "name" in row:
            diagnostic["name"] = row.get("name")
        diagnostics.append(diagnostic)
    return diagnostics


async def _author_logic(llm_service: Any, app_id: str, name: str, kind: Optional[str],
                        description: Optional[str], user_id: str,
                        lessons: Optional[str] = None,
                        acceptance_cases: Any = None,
                        acceptance_failures: Any = None,
                        expected_source_sha256: Optional[str] = None) -> Dict[str, Any]:
    """Generate the logic body, syntax-gate it through write_logic, one repair
    retry on SyntaxError (the gate returns the line/offset)."""
    from tools.mini_app_tool import mini_app_write_logic

    async def save_candidate(code: str) -> Dict[str, Any]:
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return {"success": False, "error": f"SyntaxError: {exc}"}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            target = node.func
            name = target.id if isinstance(target, ast.Name) else (
                target.attr if isinstance(target, ast.Attribute) else None
            )
            if name in {"exec", "eval", "system"}:
                return {
                    "success": False,
                    "error": f"SyntaxError: generated code cannot call {name}()",
                }
            # Unattended runs supply input fields as globals; input() would
            # block waiting on stdin. Only reject the builtin called directly,
            # not an attribute method such as Reader().input(rows).
            if isinstance(target, ast.Name) and target.id == "input":
                return {
                    "success": False,
                    "error": (
                        "SyntaxError: generated code cannot call input(); input "
                        "fields are supplied as globals (read rows directly)"
                    ),
                }
        args = {"app_id": app_id, "source": code}
        if expected_source_sha256 is not None:
            args["expected_source_sha256"] = expected_source_sha256
        return await mini_app_write_logic(args, _ctx(user_id))

    prompt = _build_logic_prompt(name, kind, description, lessons)
    if acceptance_cases:
        prompt += "\nFixed acceptance cases: " + json.dumps(acceptance_cases, sort_keys=True)
    if acceptance_failures:
        diagnostics = _repair_failure_diagnostics(acceptance_failures)
        prompt += "\nPrevious draft failed: " + json.dumps(diagnostics, sort_keys=True)

    source = ""
    if llm_service is not None:
        try:
            resp = await llm_service.generate_completion([
                {"role": "system", "content": "You write small, correct Python. Return only code."},
                {"role": "user", "content": prompt},
            ])
            source = _strip_code_fences((resp or {}).get("content") or "")
        except Exception as e:  # noqa: BLE001
            logger.debug("mini-app logic generation failed: %s", e)
    if not source and acceptance_failures:
        return {"success": False, "error": "No repair generated"}
    used_starter = not source
    if used_starter:
        # Deterministic starter body (same contract the scaffold template uses).
        source = (
            "state['items'] = int(state.get('items', 0)) + 1\n"
        )
    res = await save_candidate(source)
    if not res.get("success") and "SyntaxError" in str(res.get("error", "")) and llm_service is not None:
        retry = await llm_service.generate_completion([
            {"role": "system", "content": "You fix Python code. Return only the corrected code."},
            {"role": "user", "content": f"{prompt}\n\nYour previous attempt failed:\n{res['error']}\nReturn the fixed code only."},
        ])
        fixed = _strip_code_fences((retry or {}).get("content") or "")
        if fixed:
            res = await save_candidate(fixed)
    return {**res, "used_starter": used_starter}


async def _resolve_app(user_id: str, message: str, canvas_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Find the app a publish/install/status ask refers to: explicit app_id in
    the message, else the app whose blueprint hosts this canvas, else the
    user's most recent app."""
    import re as _re

    from tools.mini_app_tool import mini_app_list

    listing = await mini_app_list({}, _ctx(user_id))
    apps = listing.get("apps") or []
    if not apps:
        return None
    m = _re.search(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", message or "")
    if m:
        for a in apps:
            if str(a.get("id", "")).startswith(m.group(0)[:8]):
                return a
    if canvas_id:
        for a in apps:
            if a.get("blueprint_canvas_id") == canvas_id:
                return a
    return apps[0]


async def try_handle(
    message: str,
    history: List[Dict[str, Any]],
    user_id: str,
    llm_service: Any,
    canvas: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    *,
    acceptance_cases: Any = None,
) -> Optional[Dict[str, Any]]:
    """Entry point from the chat flow. Returns the chat response dict when the
    turn IS a mini-app request (handled here), or None to fall through.

    ``session_id`` rides back on the response: chat_routes takes the session
    id from the response body, and a handled turn that drops it breaks every
    follow-up ("publish it") into a fresh, context-free session (observed
    live — follow-ups answered by the generic assistant).
    """
    if not user_id or not looks_like_mini_app_request(message, history):
        return None

    canvas_id = (canvas or {}).get("canvas_id")
    host_canvas_type = (canvas or {}).get("canvas_type")

    try:
        ask = await _extract_ask(llm_service, message, history)
        action = ask["action"]

        if action in ("none", "", None):
            # Safety net: the gate passed via HISTORY (the message itself never
            # says "mini app") and the message is a bare imperative ("publish
            # it"). The verb IS the ask — falling through hands the turn to the
            # generic assistant, which can't see the app and hallucinates a
            # publication (observed live). A bare imperative with NO history
            # never reaches here (the gate rejects it).
            if not looks_like_mini_app_request(message, None):
                for hint_action, hint_re in _ACTION_HINTS:
                    if hint_re.search(message):
                        action = hint_action
                        break
        if action in ("none", "", None):
            return None  # a question ABOUT mini-apps → normal conversational path

        if action == "build":
            res = await _handle_build(
                ask, user_id, llm_service, host_canvas_type, canvas_id, message,
                acceptance_cases=acceptance_cases,
            )
        else:
            res = await _route_app_action(action, ask, message, user_id, canvas_id)
        if res is not None:
            res.setdefault("session_id", session_id)
        return res
    except Exception as e:  # noqa: BLE001 — never break the chat flow
        logger.error("mini-app chat leg failed: %s", e)
        return {
            "success": True,
            "message": ("The mini-app request hit an unexpected error — try again, "
                        "or use the Mini-App Harness panel on the canvas."),
            "data": {"mini_app_authoring": True},
            "session_id": session_id,
        }


async def _route_app_action(action: str, ask: Dict[str, Any], message: str,
                            user_id: str, canvas_id: Optional[str]) -> Optional[Dict[str, Any]]:
    app = await _resolve_app(user_id, message, canvas_id)
    if action == "status":
        if app is None:
            return _say("No mini-app found yet — ask me to build one first (e.g. "
                        "\"build a mini-app inventory tracker\").")
        from tools.mini_app_tool import mini_app_status

        probe = await mini_app_status({"app_id": app["id"]}, _ctx(user_id))
        st = probe.get("status") or {}
        return _say(
            f"App '{app.get('name')}' — status: {app.get('status')}, v{app.get('version')}. "
            f"Syntax OK: {bool((st.get('logic') or {}).get('syntax_ok'))}. "
            f"Runtime available: {bool((st.get('runtime') or {}).get('available'))}."
        )
    if action == "publish":
        if app is None:
            return _say("No mini-app found to publish — build one first (e.g. "
                        "\"build a mini-app CRM follow-up tracker\").")
        from tools.mini_app_tool import mini_app_publish

        res = await mini_app_publish({"app_id": app["id"]}, _ctx(user_id))
        if not res.get("success"):
            return _say(f"Publish failed: {res.get('error')} "
                        f"(dependency scans and the Firecracker rootfs gate are fail-closed.)")
        return _say(
            f"Published '{app.get('name')}' v{res.get('version')}. The snapshot is "
            "credential-stripped. Say \"install it\" and I'll hydrate a fresh "
            "instance canvas."
        )
    if action == "install":
        if app is None:
            return _say("No mini-app found to install — build one first.")
        if app.get("status") != "published":
            from tools.mini_app_tool import mini_app_publish

            pub = await mini_app_publish({"app_id": app["id"]}, _ctx(user_id))
            if not pub.get("success"):
                return _say(f"Couldn't publish before install: {pub.get('error')}")
        from tools.mini_app_tool import mini_app_install

        res = await mini_app_install({"app_id": app["id"]}, _ctx(user_id))
        if not res.get("success"):
            return _say(f"Install failed: {res.get('error')}")
        return _say(
            f"Installed '{app.get('name')}' → instance canvas {res.get('canvas_id')}. "
            "Open it from your canvases; runs broadcast live state to the "
            "Mini-App Harness panel."
        )
    return None


async def _verify_build(
    app_id, context, cases, tests_sha256, source_sha256,
    save_cases, run_cases, repair,
):
    if not cases:
        return {"status": "not_run"}
    saved = await save_cases({"app_id": app_id, "tests": cases}, context)
    if not saved.get("success"):
        return {"status": "unverified", "reason": "tests_not_saved"}
    if not source_sha256:
        return {"status": "unverified", "reason": "logic_not_saved"}

    args = {
        "app_id": app_id,
        "expected_tests_sha256": tests_sha256,
        "expected_source_sha256": source_sha256,
    }
    report = await run_cases(args, context)
    for attempt in range(2):
        if (not report.get("success")
                or report.get("tests_sha256") != tests_sha256
                or report.get("total") != len(cases)):
            return {"status": "unverified", "reason": "test_run_incomplete"}
        if report.get("all_passed") is True and report.get("passed") == len(cases):
            return {"status": "passed", "report": report,
                    "source_sha256": args["expected_source_sha256"]}
        failures = [row for row in report.get("results", []) if row.get("passed") is False]
        # A mismatched (error-free) assertion is repairable, as before. An
        # error-bearing row is repairable ONLY when it carries a validated,
        # typed deterministic controller failure; timeout/stale/unavailable/
        # unknown/legacy errors stay unrepairable.
        unrepairable_error = any(
            isinstance(row, dict)
            and row.get("error")
            and _valid_controller_error(row.get("controller_error")) is None
            for row in failures
        )
        if attempt or not failures or unrepairable_error:
            break
        repaired_sha256 = await repair(_repair_failure_diagnostics(failures))
        if not repaired_sha256:
            break
        args = {**args, "expected_source_sha256": repaired_sha256}
        report = await run_cases(args, context)
    return {"status": "failed", "report": report,
            "source_sha256": args["expected_source_sha256"]}


async def _handle_build(ask: Dict[str, Any], user_id: str, llm_service: Any,
                        host_canvas_type: Optional[str],
                        canvas_id: Optional[str] = None,
                        request_query: str = "",
                        acceptance_cases: Any = None) -> Dict[str, Any]:
    from core.mini_app_service import validate_tests
    from tools.mini_app_tool import mini_app_dev_run, mini_app_scaffold

    if acceptance_cases is not None:
        try:
            validate_tests(acceptance_cases)
        except ValueError as exc:
            result = _say(f"Check the supplied acceptance cases before building. {exc}")
            result["data"]["acceptance_status"] = "invalid_cases"
            return result

    kind = (ask.get("canvas_type") or host_canvas_type or "").strip().lower() or None
    name = (ask.get("name") or "").strip() or f"{(kind or 'Chat').title()} Mini-App"

    # Canvas lessons are build-only context: never used for intent parsing or
    # for publish/install/status, and skipped when there is no canvas or the
    # ask is too thin to search with. A lookup failure degrades to no lessons.
    lessons = ""
    query = _meaningful_query(" ".join(
        str(part).strip()
        for part in (ask.get("description"), request_query)
        if str(part or "").strip()
    ))
    if canvas_id and query:
        try:
            lessons = _scoped_canvas_lessons(user_id, canvas_id, query)
            if inspect.isawaitable(lessons):
                lessons = await lessons
            lessons = str(lessons or "").strip()
        except Exception as e:  # noqa: BLE001 — lessons are optional context
            logger.debug("scoped canvas lesson lookup failed: %s", e)
            lessons = ""

    spec: Dict[str, Any] = {}
    if kind and kind != "mini_app":
        spec["canvas_type"] = kind
    if ask.get("description"):
        spec["description"] = ask["description"]

    scaffold = await mini_app_scaffold(
        {"name": name, "declared_scopes": ["canvas_render", "canvas_get_state"],
         "dependencies": [], "spec": spec},
        _ctx(user_id),
    )
    if not scaffold.get("success"):
        return _say(f"Couldn't scaffold the mini-app: {scaffold.get('error')}")
    app_id = scaffold["app_id"]

    write = await _author_logic(
        llm_service, app_id, name, kind, ask.get("description"), user_id,
        lessons=lessons, acceptance_cases=acceptance_cases,
    )
    logic_note = (
        f"logic saved (checkpoint v{write.get('version')})" if write.get("success")
        else f"logic save failed: {write.get('error')} — fix it in the Mini-App Harness editor"
    )

    if acceptance_cases:
        from core.task_lifecycle import _approval_payload_hash
        from tools.mini_app_tool import mini_app_run_tests, mini_app_set_tests

        async def repair(failures):
            if llm_service is None:
                return None
            fixed = await _author_logic(
                llm_service, app_id, name, kind, ask.get("description"), user_id,
                lessons=lessons, acceptance_cases=acceptance_cases,
                acceptance_failures=failures,
                expected_source_sha256=write["source_sha256"],
            )
            return fixed.get("source_sha256") if fixed.get("success") else None

        outcome = await _verify_build(
            app_id, _ctx(user_id), acceptance_cases,
            _approval_payload_hash(acceptance_cases),
            write.get("source_sha256") if write.get("success") and not write.get("used_starter") else None,
            mini_app_set_tests, mini_app_run_tests, repair,
        )
        report = outcome.get("report") or {}
        result = _say(
            f"Saved draft '{name}' — app {app_id}, blueprint canvas {scaffold.get('canvas_id')}. "
            + (f"{report['passed']}/{report['total']} supplied acceptance cases passed."
               if report else "The supplied acceptance cases could not be verified.")
        )
        result["data"]["acceptance"] = outcome
        return result

    run = await mini_app_dev_run({"app_id": app_id, "inputs": {}}, _ctx(user_id))
    if run.get("success"):
        run_note = f"dev-run passed (dry): state={run.get('state')}"
    elif "runtime unavailable" in str(run.get("error", "")).lower():
        run_note = ("dev-run couldn't execute: this host has no Firecracker runtime "
                    f"(fail-closed by design — see {_RUNTIME_DOC}); the logic is "
                    "syntax-checked and will run on a provisioned host")
    else:
        run_note = f"dev-run failed: {run.get('error')}"

    if write.get("used_starter") and write.get("success"):
        result = _say(
            f"Saved starter draft '{name}'"
            + (f" on a {kind} canvas" if kind and kind != "mini_app" else "")
            + f" — app {app_id}, blueprint canvas {scaffold.get('canvas_id')}. "
            + "The requested logic was not generated. "
            + f"Starter smoke test: {run_note}. Requested behavior is unverified. "
            "Review or edit the draft in the Mini-App Harness."
        )
        result["data"].update({
            "authoring_status": "starter_saved",
            "requested_logic_generated": False,
            "requested_behavior_verified": False,
        })
        return result

    return _say(
        f"Built mini-app '{name}'"
        + (f" on a {kind} canvas" if kind and kind != "mini_app" else "")
        + f" — app {app_id}, blueprint canvas {scaffold.get('canvas_id')}. "
        + logic_note + ". " + run_note + ". "
        + "Review it in the Mini-App Harness panel; say \"publish it\" when it looks right."
    )


def _say(message: str) -> Dict[str, Any]:
    return {"success": True, "message": message, "data": {"mini_app_authoring": True}}
