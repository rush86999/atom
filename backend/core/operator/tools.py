"""Agent-facing operator tools + the in-memory run registry.

Surface (registered in tools/registry.py, dispatched through
mcp_service.call_tool like every other agent tool):

- operator_start_task(task, start_url?) — open a governed browser session
  and run the observe→decide→act loop in the background; returns a run
  handle immediately.
- operator_get_status(run_id) — steps, progress, result summary (no
  screenshot payload).
- operator_get_screenshot(run_id) — the last observation's screenshot
  (base64 JPEG).
- operator_stop_task(run_id) — halt between steps and close the session.

Governance mirrors browser_create_session: the entry gate checks
browser permissions (INTERN+) when governance enforcement is on; inside
the loop, every action re-runs the same permission check as a governance
callback (a denial is the hard stop session.py:244 implements) and is
audited (BrowserAudit). Both open their own short-lived DB session when
the caller supplies none — MCP dispatch never puts a db in the tool
context. Maturity gating also applies at the MCP dispatch layer via the
tier floors (core/sandbox_policy.py) and the registered tool metadata.

Goal-run wiring: a run started with goal_run_id pushes an
``operator_task_done`` event through goal_run_events.ingest_event when it
finishes — the wait spec set by the computer_use_work executor step
matches on operator_run_id (same consumed-once pattern as
human_checkpoint).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.feature_flags import FeatureFlags

logger = logging.getLogger(__name__)

# Keep spawned loop tasks referenced so the GC never reaps a live run.
_BACKGROUND_TASKS: set = set()

# Registry bounds: finished runs keep summary/result (small), but their
# ~1568px JPEG screenshots are dropped after the TTL and whole runs are
# evicted beyond the cap — goal runs otherwise pin every screenshot in
# memory forever. BrowserAudit rows remain the durable trail.
_MAX_TRACKED_RUNS = 20
_SCREENSHOT_TTL_SECONDS = 900  # 15 minutes after the run goes terminal


@dataclass
class OperatorRunState:
    run_id: str
    task: str
    user_id: str
    agent_id: Optional[str] = None
    workspace_id: str = "default"
    tenant_id: str = "default"
    goal_run_id: Optional[str] = None
    goal_run_step_id: Optional[str] = None
    status: str = "running"     # running|done|failed|stopped|blocked
    result: Dict[str, Any] = field(default_factory=dict)
    steps: List[Dict[str, Any]] = field(default_factory=list)
    last_screenshot: str = ""
    last_url: str = ""
    last_title: str = ""
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    terminal_at: Optional[datetime] = None
    screenshot_dropped: bool = False
    _task: Optional[asyncio.Task] = None

    def touch(self):
        self.updated_at = datetime.now()
        if self.status != "running" and self.terminal_at is None:
            self.terminal_at = datetime.now()


class OperatorRunRegistry:
    """In-memory registry of live/finished operator runs (mirrors
    BrowserSessionManager's process-local lifecycle model; BrowserAudit
    rows are the durable trail). Bounded: at most ``max_runs`` most-recent
    runs are tracked (running runs are never evicted), and a terminal
    run's screenshot bytes are dropped ``screenshot_ttl_seconds`` after it
    finished — the summary/result stay."""

    def __init__(self, max_runs: int = _MAX_TRACKED_RUNS,
                 screenshot_ttl_seconds: int = _SCREENSHOT_TTL_SECONDS):
        self._runs: Dict[str, OperatorRunState] = {}
        self.max_runs = max_runs
        self.screenshot_ttl_seconds = screenshot_ttl_seconds

    def create(self, **kwargs) -> OperatorRunState:
        run_id = f"operator-{uuid.uuid4().hex[:12]}"
        state = OperatorRunState(run_id=run_id, **kwargs)
        self._runs[run_id] = state
        self._evict_beyond_capacity()
        return state

    def get(self, run_id: str) -> Optional[OperatorRunState]:
        state = self._runs.get(run_id)
        if state is not None:
            self._expire_screenshot_if_due(state)
        return state

    def list_runs(self, agent_id: Optional[str] = None) -> List[OperatorRunState]:
        runs = list(self._runs.values())
        if agent_id:
            runs = [r for r in runs if r.agent_id == agent_id]
        return sorted(runs, key=lambda r: r.created_at, reverse=True)

    def _evict_beyond_capacity(self) -> None:
        if len(self._runs) <= self.max_runs:
            return
        evictable = sorted(
            (r for r in self._runs.values() if r.status != "running"),
            key=lambda r: r.created_at)
        for state in evictable:
            if len(self._runs) <= self.max_runs:
                break
            self._runs.pop(state.run_id, None)

    def _expire_screenshot_if_due(self, state: OperatorRunState) -> None:
        if (state.screenshot_dropped or state.terminal_at is None
                or not state.last_screenshot):
            return
        age = (datetime.now() - state.terminal_at).total_seconds()
        if age > self.screenshot_ttl_seconds:
            state.last_screenshot = ""
            state.screenshot_dropped = True


_operator_run_registry = OperatorRunRegistry()


def get_operator_run_registry() -> OperatorRunRegistry:
    return _operator_run_registry


async def _browser_governance_permits(user_id: str,
                                      agent_id: Optional[str],
                                      db=None) -> bool:
    """THE browser-permission check for the operator — used by the entry
    gate (operator_start_task) AND, per action, by the governance callback
    wired in _run_operator_task, so the loop re-verifies what the entry
    gate admitted (same check, not a second policy).

    Opens its own short-lived DB session when none is supplied (the
    goal_run_events idiom) — the MCP dispatch path never forwards a db,
    and the goal-run executor closes its session right after start.
    """
    if not (FeatureFlags.should_enforce_governance("browser") and agent_id):
        return True

    async def _check(session) -> bool:
        from core.agent_context_resolver import AgentContextResolver
        from core.service_factory import ServiceFactory
        resolver = AgentContextResolver(session)
        governance = ServiceFactory.get_governance_service(session)
        agent, _ = await resolver.resolve_agent_for_request(
            user_id=user_id, requested_agent_id=agent_id,
            action_type="browser_navigate")
        if not agent:
            return True
        check = governance.can_perform_action(
            agent_id=agent.id, action_type="browser_navigate")
        return bool(check.get("allowed"))

    try:
        if db is not None:
            return await _check(db)
        from core.database import get_db_session
        with get_db_session() as session:
            return await _check(session)
    except Exception as exc:
        logger.error(f"operator governance gate failed (denying): {exc}")
        return False


async def _governance_allows(db, user_id: str,
                             agent_id: Optional[str]) -> bool:
    """Entry gate seam (kept for tests) — same check the per-action
    governance callback runs."""
    return await _browser_governance_permits(user_id, agent_id, db=db)


def _spawn(coro) -> Optional[asyncio.Task]:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    task = loop.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return task


async def _run_operator_task(state: OperatorRunState,
                             start_url: Optional[str],
                             max_steps: Optional[int]) -> None:
    """Background body: session → loop → status → goal-run wake."""
    from core.operator.loop import OperatorLoop, JsonVisionDecider
    from core.operator.session import OperatorSession

    async def _governance_callback(action_type, details) -> bool:
        # Per-action re-run of the entry gate's browser-permission check
        # (opens its own short-lived DB session). A denial is the hard
        # stop session.py implements as blocked_by_governance.
        return await _browser_governance_permits(state.user_id,
                                                 state.agent_id)

    def _publish(progress: Dict[str, Any]) -> None:
        # Mid-run observability (P2-6): the loop and this runner share the
        # event loop and the callback is synchronous, so plain assignment
        # is safe — no lock needed.
        state.steps = progress["steps"]
        state.last_url = progress["last_url"]
        state.last_title = progress["last_title"]
        if progress["last_screenshot_b64"]:
            state.last_screenshot = progress["last_screenshot_b64"]
        state.touch()

    backend = None
    try:
        backend = OperatorSession(user_id=state.user_id,
                                  agent_id=state.agent_id,
                                  governance_callback=_governance_callback)
        started = await backend.start(start_url=start_url)
        start_nav = started.get("navigate") or {}
        if start_nav.get("blocked_by_governance"):
            # Egress policy denied the start_url — same hard stop the loop
            # applies to in-run navigations.
            state.status = "blocked"
            state.result = {"success": False,
                            "error": start_nav.get("error"),
                            "task": state.task}
        else:
            loop = OperatorLoop(backend=backend,
                                decider=JsonVisionDecider(tenant_id=state.tenant_id),
                                max_steps=max_steps,
                                stop_event=state.stop_event,
                                progress_callback=_publish)
            result = await loop.run(state.task)

            state.result = result
            state.steps = list(result.get("actions") or [])
            state.last_url = result.get("final_url") or ""
            state.last_title = result.get("final_title") or ""

            if result.get("stopped"):
                state.status = "stopped"
            elif result.get("budget_exhausted"):
                # Budget exhaustion is a bounded, honest end — NOT a
                # failure. Distinguishable via result.budget_exhausted.
                state.status = "stopped"
                state.result = {**result,
                                "stop_reason": "step budget exhausted"}
            elif result.get("blocked"):
                state.status = "blocked"
            elif result.get("done"):
                state.status = "done"
            else:
                state.status = "failed"
    except Exception as exc:
        logger.error(f"operator run {state.run_id} crashed: {exc}")
        state.status = "failed"
        state.result = {"success": False, "error": str(exc),
                        "task": state.task}
    finally:
        if backend is not None:
            try:
                last = await backend.observe()
                if last.screenshot_b64:
                    state.last_screenshot = last.screenshot_b64
            except Exception:
                pass
            await backend.close()
        state.touch()
        await _notify_goal_run(state)


async def _notify_goal_run(state: OperatorRunState) -> None:
    """Wake the owning goal run (consumed-once, fault-isolated)."""
    if not state.goal_run_id:
        return
    try:
        from core.goals.goal_run_events import ingest_event
        result = state.result or {}
        await ingest_event(
            {
                "event": "operator_task_done",
                "operator_run_id": state.run_id,
                "success": bool(result.get("done") and result.get("success")),
                "summary": (result.get("summary") or result.get("error")
                            or "")[:300],
            },
            workspace_id=state.workspace_id or "default",
            tenant_id=state.tenant_id or "default",
        )
    except Exception as exc:
        logger.warning(f"operator run {state.run_id}: goal-run wake "
                       f"failed: {exc}")


# ---------------------------------------------------------------------------
# Tool functions (agent-callable)
# ---------------------------------------------------------------------------

async def operator_start_task(
    task: str,
    start_url: Optional[str] = None,
    max_steps: Optional[int] = None,
    user_id: str = "system",
    agent_id: Optional[str] = None,
    db=None,
    workspace_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    goal_run_id: Optional[str] = None,
    goal_run_step_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Start a computer-use operator task: a governed browser session runs
    the observe→decide→act loop in the background. Returns a run handle
    immediately; poll with operator_get_status."""
    task = (task or "").strip()
    if not task:
        return {"success": False, "error": "task is required"}

    if not await _governance_allows(db, user_id, agent_id):
        return {"success": False,
                "error": "agent not permitted to use the browser operator"}

    state = get_operator_run_registry().create(
        task=task, user_id=user_id, agent_id=agent_id,
        workspace_id=workspace_id or "default",
        tenant_id=tenant_id or "default",
        goal_run_id=goal_run_id, goal_run_step_id=goal_run_step_id)

    spawned = _spawn(_run_operator_task(state, start_url, max_steps))
    if spawned is None:
        get_operator_run_registry()._runs.pop(state.run_id, None)
        return {"success": False,
                "error": "no running event loop — call from an async context"}

    return {
        "success": True,
        "operator_run_id": state.run_id,
        "status": state.status,
        "max_steps": max_steps,
    }


def _owned_run_or_denial(run_id: str,
                         user_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Fetch a run enforcing ownership: identity comes from the dispatch
    CONTEXT only (mcp_service strips argument-supplied user_id/agent_id
    for operator_* tools), and an unknown/no-context caller is denied
    rather than served — otherwise a model-supplied identity could read
    or stop another user's run. Returns the denial dict, or None when the
    caller may proceed."""
    state = get_operator_run_registry().get(run_id)
    if not state:
        return {"success": False, "error": f"operator run {run_id} not found"}
    if not user_id:
        return {"success": False,
                "error": "user identity required — operator runs are only "
                         "readable from an authenticated dispatch context"}
    if state.user_id != user_id:
        return {"success": False, "error": "run belongs to different user"}
    return None


def operator_get_status(run_id: str,
                        user_id: Optional[str] = None) -> Dict[str, Any]:
    """Status of an operator run: step log and result summary (no
    screenshot payload — use operator_get_screenshot)."""
    denial = _owned_run_or_denial(run_id, user_id)
    if denial:
        return denial
    state = get_operator_run_registry().get(run_id)
    result = dict(state.result or {})
    result.pop("actions", None)  # steps carry the log; avoid duplication
    return {
        "success": True,
        "operator_run_id": state.run_id,
        "status": state.status,
        "task": state.task,
        "steps": state.steps,
        "final_url": state.last_url,
        "final_title": state.last_title,
        "has_screenshot": bool(state.last_screenshot),
        "result": result,
    }


def operator_get_screenshot(run_id: str,
                            user_id: Optional[str] = None) -> Dict[str, Any]:
    """The run's last observation screenshot (base64 JPEG, model-sized)."""
    denial = _owned_run_or_denial(run_id, user_id)
    if denial:
        return denial
    state = get_operator_run_registry().get(run_id)
    if state.screenshot_dropped:
        return {"success": False,
                "error": f"screenshot for operator run {run_id} expired "
                         f"(dropped {_SCREENSHOT_TTL_SECONDS}s after "
                         f"completion); summary/result remain via "
                         f"operator_get_status"}
    return {
        "success": True,
        "operator_run_id": state.run_id,
        "screenshot_b64": state.last_screenshot,
        "url": state.last_url,
        "format": "jpeg",
    }


async def operator_stop_task(run_id: str,
                             user_id: Optional[str] = None) -> Dict[str, Any]:
    """Halt an operator run between steps (the current action finishes;
    the loop stops before the next decision) and close its session."""
    denial = _owned_run_or_denial(run_id, user_id)
    if denial:
        return denial
    state = get_operator_run_registry().get(run_id)
    state.stop_event.set()
    return {"success": True, "operator_run_id": state.run_id,
            "status": "stopping"}


# ---------------------------------------------------------------------------
# ToolRegistry registration (tools/registry.py calls this)
# ---------------------------------------------------------------------------

def register_operator_tools(tool_registry=None):
    """Register the operator surface with the tool registry.

    Maturity ladder mirrors blast radius: start/stop drive a live browser
    under the agent's name (3/SUPERVISED — an INTERN that reaches them
    proposes, a human confirms); status/screenshot are reads (1/STUDENT).
    """
    from tools.registry import get_tool_registry

    if tool_registry is None:
        tool_registry = get_tool_registry()

    tool_registry.register(
        name="operator_start_task",
        function=operator_start_task,
        version="1.0.0",
        description=(
            "Start a computer-use operator task: a governed Chromium "
            "session runs the observe→decide→act loop (one model-decided "
            "action per fresh screenshot, step-bounded, audited) in the "
            "background. Returns an operator_run_id; poll with "
            "operator_get_status. Money/checkout actions are hard-stopped "
            "by the operator guardrails."
        ),
        category="browser",
        complexity=3,
        maturity_required="SUPERVISED",
        dependencies=["playwright"],
        parameters={
            "task": "string (required) — what to accomplish on the web",
            "start_url": "string (optional) — opening page",
            "max_steps": "int (optional) — step budget (default from "
                         "ATOM_COMPUTER_USE_MAX_STEPS)",
        },
        tags=["operator", "computer_use", "browser", "automation", "agent"],
        cacheable=False,
    )

    tool_registry.register(
        name="operator_get_status",
        function=operator_get_status,
        version="1.0.0",
        description=(
            "Get status, step log, and result summary of an operator task "
            "run (no screenshot payload — use operator_get_screenshot)."
        ),
        category="browser",
        complexity=1,
        maturity_required="STUDENT",
        dependencies=[],
        parameters={"run_id": "string (required) — operator run id"},
        tags=["operator", "computer_use", "status"],
        cacheable=False,
    )

    tool_registry.register(
        name="operator_get_screenshot",
        function=operator_get_screenshot,
        version="1.0.0",
        description=(
            "Get the last screenshot captured by an operator task run "
            "(base64 JPEG, model-sized)."
        ),
        category="browser",
        complexity=1,
        maturity_required="STUDENT",
        dependencies=[],
        parameters={"run_id": "string (required) — operator run id"},
        tags=["operator", "computer_use", "screenshot"],
        cacheable=False,
    )

    tool_registry.register(
        name="operator_stop_task",
        function=operator_stop_task,
        version="1.0.0",
        description=(
            "Stop an operator task run between steps and close its browser "
            "session."
        ),
        category="browser",
        complexity=3,
        maturity_required="SUPERVISED",
        dependencies=[],
        parameters={"run_id": "string (required) — operator run id"},
        tags=["operator", "computer_use", "stop"],
        cacheable=False,
    )
