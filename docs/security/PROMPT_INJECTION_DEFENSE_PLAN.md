# Prompt Injection Defense — Engineering Plan

**Status**: ✅ Implemented (Rounds 43-47, June 30 2026)
**Last updated**: June 30, 2026
**Scope**: Add a deterministic sandbox layer to Atom's agent runtime, separate
from the existing probabilistic trust tier.
**Companion docs**:
- [`TRUST_VS_SANDBOX.md`](./TRUST_VS_SANDBOX.md) — why this layer is necessary.
- [`../architecture/SANDBOX_LAYER.md`](../architecture/SANDBOX_LAYER.md) — the shipped implementation (authoritative).

> All five phases (A through E) shipped in shadow mode — compute + audit
> always on, enforcement off by default. Operators flip
> `ATOM_SANDBOX_FORCE_ENFORCE=true` after observing violation distributions
> in staging. See `SANDBOX_LAYER.md` for the per-phase kill switches,
> audit table schema, and red-team verification protocol.

---

## 1. Problem statement

Atom graduates agents through a maturity system
(`STUDENT → INTERN → SUPERVISED → AUTONOMOUS`) and gates actions by complexity
level. This is a **routing** decision: it uses past clean executions to decide
how much rope to give the next call.

It is not a **security** decision. A single prompt-injected tool output, file
read, or memory retrieval can pivot any agent — at any tier — into executing
attacker-chosen actions within the full scope that tier permits. The trust
formula describes the past; the attack happens in the present call.

This plan defines the missing layer: a deterministic, per-run sandbox that
bounds blast radius regardless of who is steering the agent.

**Out of scope for this plan** (handled elsewhere or not at all):
- Detecting prompt-injection *content* via classifiers (unreliable, arms race;
  we use scope enforcement instead).
- Modifying the LLM providers or their training.
- Defending against a malicious *operator* (insider threat is a different
  model).
- Defending against the user themselves (the user is trusted by definition;
  the agents reading untrusted data on the user's behalf are not).

---

## 2. Threat model

### 2.1 Attacker goals (in roughly decreasing severity)

| Goal | Example |
|---|---|
| Credential/session exfiltration | Read `~/.aws/credentials`, browser cookies, `.env`, JWTs; POST to attacker host |
| Destructive state changes | Drop production DB tables, delete user data, revoke own access keys |
| Lateral persistence | Install a cron job, backdoor a skill, add a new admin account |
| Cost denial-of-service | Spin up compute, call expensive APIs in a loop, mine crypto |
| Reputation / spam | Post on behalf of user, email contacts, send social DMs |
| Subtle data poisoning | Write subtly-wrong facts to `agent_world_model` or episodic memory |

### 2.2 Injection vectors (where attacker-controlled text enters context)

| Vector | Status in Atom today |
|---|---|
| Tool outputs (browser, device, canvas scrape) | Tool returns are concatenated into context unfiltered |
| File reads (any path the agent can reach) | No path-provenance tagging |
| Web pages fetched by browser tool | Rendered text becomes agent context |
| Email/message ingestion (integrations) | Body text becomes agent context |
| Third-party API responses | JSON/text bodies become context |
| Retrieved episodic memory | Past episodes (possibly poisoned) re-injected |
| Retrieved facts (`turn_fact_*`, world model) | Facts are trusted; a poisoned fact becomes a trusted instruction |
| Federation messages (`X-Federation-Key` peers) | Remote agent text becomes context |
| Skill package code itself | A malicious skill is arbitrary Python — out of scope here, covered by package governance |

### 2.3 What the attacker can and cannot rely on

- **Can rely on**: the agent will read their text, the agent has *some* tool
  access, and the maturity system will not detect the pivot (by design — it's
  not what tier checks for).
- **Cannot rely on**: a specific provider being vulnerable, the agent
  executing every instruction perfectly, or any single attack landing. Defense
  must assume *some* attacks land and bound the consequence.

---

## 3. Defense principles

Five principles drive the design. None is novel; all are standard for
untrusted-input systems and restated here so reviewers can hold us to them.

### P1 — Tier gates permission, sandbox gates capability

These are different questions answered by different code paths. Maturity tier
remains the routing decision; the sandbox runs alongside it and answers the
blast-radius question. Neither is allowed to substitute for the other.

### P2 — Default-deny at the sandbox, not the tier

A new agent run starts with no capabilities. Each capability (filesystem path,
tool, host, resource budget) must be *added* by the orchestrator for that run,
based on the task. Tier can *cap* the maximum scope a run may request; it
cannot *grant* scope implicitly.

### P3 — Provenance is mandatory, not optional

Every byte that enters agent context is tagged with its source trust level.
Instructions may only come from trusted channels (system prompt, the user's
session). Everything else is data. Data is never allowed to invoke tools
directly — it can only be reported on.

### P4 — Caps are hard and tripwired, not soft and advisory

Approaching a cap → kill the run, alert, write an audit row. No demotion, no
"are you sure" prompt. Demotion is a tier concern and moves at the speed of
statistics; tripwires move at the speed of a syscall.

### P5 — Sandbox enforcement is independent of agent cooperation

The agent cannot see, request changes to, or veto the sandbox. Tools that
refuse to enforce sandbox scope (e.g. raw shell exec) are either wrapped,
proxied, or disallowed — never trusted to police themselves.

---

## 4. Architecture

```
                          ┌────────────────────────────────┐
   Task request ─────────►│   Task Orchestrator            │
                          │   (issues SandboxPolicy token) │
                          └───────────────┬────────────────┘
                                          │ SandboxPolicy
                                          ▼
            ┌─────────────────────────────────────────────┐
            │  Agent runtime (LLM + tools)                │
            │  ┌───────────────────────────────────────┐  │
            │  │ Provenance-tagged context assembly    │  │
            │  │ (system / user = trusted;             │  │
            │  │  tools / memory / federation = data)  │  │
            │  └───────────────────────────────────────┘  │
            └────────────────┬────────────────────────────┘
                             │ tool call args
                             ▼
            ┌─────────────────────────────────────────────┐
            │  SandboxPolicy.check(tool, args)            │
            │   - filesystem path in scope?               │
            │   - tool on whitelist?                      │
            │   - egress host on allowlist?               │
            │   - within byte/time/$ budget?              │
            │  ── NO ─► kill + audit + alert              │
            │  ── YES ─► delegate to tool                 │
            └────────────────┬────────────────────────────┘
                             │
                             ▼
            ┌─────────────────────────────────────────────┐
            │  Existing tools (browser, device, canvas,   │
            │  file, memory, federation)                  │
            │  ← wrapped so they cannot bypass policy     │
            └─────────────────────────────────────────────┘
```

### 4.1 New components

#### `SandboxPolicy` service (`core/sandbox_policy.py`)

The deterministic gate. Per-run, in-memory, immutable after issuance.

```python
@dataclass(frozen=True)
class SandboxPolicy:
    run_id: str
    agent_id: str
    tier_at_issuance: AgentStatus           # captured for audit; not consulted
    fs_roots: tuple[str, ...]               # absolute paths the run may read
    fs_write_roots: tuple[str, ...]         # subset the run may write
    tool_whitelist: tuple[str, ...]         # tool names this run may call
    egress_hosts: tuple[str, ...]           # hostnames the run may contact
    max_bytes_written: int                  # across all fs writes this run
    max_exec_seconds: int                   # wall clock for the run
    max_tool_calls: int                     # total calls permitted
    max_cost_usd: float                     # LLM + tool spend
    tripwire_actions: tuple[str, ...]       # hard-kill on sight, no budget check
```

Issued by the task orchestrator at run start. The orchestrator derives the
policy from (a) the task's declared needs, (b) the agent's tier (tier caps
the *maximum* a task may request — e.g. a STUDENT-tier task cannot request
write access even if the task declares it), and (c) tenant/workspace policy.

Stored in a `RunSandbox` table alongside `AgentExecution` for audit. Cached
in-process for the run's lifetime.

#### `ProvenanceTagger` (`core/provenance.py`)

Wraps context assembly so every chunk is tagged with one of:

| Tag | Examples | May invoke tools? |
|---|---|---|
| `SYSTEM` | System prompt, constitutional rules | (defines tools, doesn't invoke) |
| `USER` | This session's user messages | Yes |
| `TOOL_OUTPUT` | Browser scrape, API response | No |
| `FILE` | Read from disk | No |
| `MEMORY` | Episode retrieval, fact recall | No |
| `FEDERATION` | Peer-agent messages | No |

The runtime layer that turns the LLM's tool-call requests into actual calls
refuses to honor any tool call whose *justification* in the LLM's reasoning
chain traces only to non-`USER`/non-`SYSTEM` tags. Implementation note: this
is the hardest part and the lowest-confidence defense; it is a *deterrent*,
not a *guarantee*. The deterministic parts (SandboxPolicy) carry the weight.

#### Egress proxy (`core/sandbox_egress.py` + an HTTP CONNECT proxy)

All outbound HTTP from `browser_tool`, `device_tool`, integration clients,
and skill packages is forced through a local proxy that consults the run's
`egress_hosts` allowlist. Connections to non-allowlisted hosts are dropped
and logged. No tool is permitted to bypass the proxy (enforced at process
boundary for skills via Docker network mode; enforced at HTTP client config
for built-in tools).

#### Action tripwires (`core/sandbox_tripwire.py`)

Pattern-matching on (tool, args) pairs that warrant instant kill regardless
of budget:

- Read of any path matching `**/.aws/credentials`, `**/.env*`,
  `**/*.pem`, `**/id_rsa*`, `**/cookies.db`, `**/Google Passwords*`
- Write outside `fs_write_roots`
- Egress to any host matched against a denylist of known exfil endpoints
- Creation of cron jobs, systemd units, launch agents, scheduled tasks
- Granting admin/owner role to a newly-created principal
- DB writes that match destructive patterns (`DROP TABLE`, `TRUNCATE`,
  `DELETE FROM <table> WHERE true`, bulk `UPDATE` without `WHERE`)

Tripwire match → `KillRun(reason, evidence)` → audit row + alert. No
"are you sure", no demotion.

#### `KillRun` and run-state machine (`core/run_lifecycle.py`)

Hard kill capability. Once killed, the run cannot make further tool calls and
its final output is replaced with a canned "this run was killed by the
sandbox" message. The agent's tier may be reviewed by a separate, slower
investigation process — but that is decoupled from the kill itself.

### 4.2 Modified components

#### `AgentGovernanceService.can_perform_action`

Unchanged signature, but now the **second** check, not the only check. The
orchestrator calls `SandboxPolicy.check(...)` *before*
`can_perform_action(...)` and treats a sandbox denial as final.

#### Tools (`tools/*.py`)

Every tool gains a wrapper that:

1. Receives the run's `SandboxPolicy` from the runtime context.
2. Calls `policy.check(tool_name=self.name, args=args)` before doing work.
3. On `Denied(reason)`: raises `SandboxKill` → runtime kills the run.
4. On `Allowed(usage)`: proceeds and reports usage back (for budget
   decrement).

Tools that cannot be wrapped (raw shell exec, arbitrary code eval) are
disallowed at STUDENT/INTERN/SUPERVISED tiers and gated behind a separate
`ShellSandbox` capability at AUTONOMOUS tier that runs in a Docker container
with no network, no volume mounts, and a CPU/wall budget.

#### Memory retrieval (`episode_retrieval_service`, `turn_fact_*`)

Memory items and facts gain a `provenance` field. Items injected into context
keep their tag. Items with `provenance != TRUSTED` are marked as data, not
instructions — same constraint as tool outputs.

New writes to durable memory (episodes, facts, world model) go through the
same sandbox as any other write: in-scope path, within write budget, no
tripwire match.

#### Context assembly (`core/llm/byok_handler.py`)

`truncate_to_context` and related functions preserve provenance tags through
compression. The system prompt is always prepended *after* compression, never
inside it, so compression cannot be tricked into "summarizing away" the
actual system instructions.

---

## 5. Phasing

Five phases. Each is independently shippable and reverts cleanly.

### Phase A — Foundation (no enforcement yet)

**Goal**: get the data model and policy object in place; no behavior change.

- Add `SandboxPolicy` dataclass and `IssuePolicy` orchestrator hook.
- Add `RunSandbox` table and migration (`20260627_run_sandbox`).
- Add `provenance` column to `AgentReasoningStep`,
  `Episode`, `TurnFact`.
- Emit policy on every run; log it; don't enforce yet.
- Tests: policy issuance is well-formed; provenance tags survive a round
  trip through the DB.

**Verification**: every run has a policy row in `RunSandbox`; every retrieved
memory item carries a `provenance` value. No tool behavior change.

### Phase B — Filesystem scope (highest-value, lowest-risk)

**Goal**: cap what paths a run may touch.

- Implement `SandboxPolicy.check_fs(path, mode)`.
- Wrap `canvas_tool`, `document_ingestion`, file-reading tools.
- Default `fs_roots` = workspace dir + a per-run scratch dir.
- Default `fs_write_roots` = per-run scratch dir only; writes to workspace
  require the task to declare them.
- Tripwire on credential/key paths (P4 above).

**Verification**: integration test — agent run that attempts to read
`/etc/passwd` or `~/.aws/credentials` is killed and audit row exists.

### Phase C — Tool whitelist + resource caps

**Goal**: cap which tools and how much.

- `SandboxPolicy.check_tool(name)` and `check_budget(usage)`.
- Orchestrator issues whitelist per task type (declared in task schema).
- Budgets: bytes written, tool calls, wall time, LLM cost (already tracked
  by `cognitive_tier_system`; integrate).
- Tripwire on destructive DB patterns.

**Verification**: a run that tries to call a tool not in its whitelist is
killed. A run that exceeds `max_bytes_written` is killed.

### Phase D — Egress proxy

**Goal**: cap network blast radius.

- Stand up the local HTTP CONNECT proxy.
- Reconfigure `httpx` clients in `browser_tool`, `device_tool`,
  integration clients to use it.
- Skills in Docker: `--network=none` unless task declares egress needs,
  in which case `--network=sandbox_proxy`.
- Default `egress_hosts` = empty; task declares what it needs (e.g.
  `api.github.com` for a GitHub task).

**Verification**: a hijacked run attempting to POST to
`https://attacker.example/` is killed at the proxy.

### Phase E — Provenance-aware context (hardest; lowest confidence)

**Goal**: make it harder for injected instructions to drive tool calls.

- `ProvenanceTagger` wraps context assembly.
- Runtime refuses to honor a tool call whose stated justification in the
  LLM reasoning trace references only non-`USER`/non-`SYSTEM` chunks.
- This is a *deterrent layer*. It will miss attacks and may flag legitimate
  tool calls. Tunable per workspace; default = advisory (log only) for the
  first release, promoting to enforcement once false-positive rate is
  characterized.

**Verification**: red-team suite of known injection patterns; characterize
detection and false-positive rates; document them.

---

## 6. What success looks like

End state, all five phases shipped:

1. Every agent run has a `SandboxPolicy` row visible in the admin UI.
2. A red-team injection suite (we will need to build this) demonstrates:
   - Credential-exfil attempt killed at file-tripwire.
   - Destructive DB write killed at tripwire.
   - Exfil-to-attacker-host killed at egress proxy.
   - Subtle memory-poisoning write killed at fs_write_root cap.
3. The maturity system docs are accurate: tier is described as routing, not
   safety, with a link to `TRUST_VS_SANDBOX.md`.
4. Pre-commit hook + CI run the red-team suite against any change to
   sandbox-related code.

---

## 7. Risks and open questions

- **Provenance enforcement (Phase E) is the soft layer.** LLMs don't
  reliably expose their reasoning, and "did this tool call trace to
  USER-tagged context?" is a best-effort inference. Phases B–D carry the
  actual security weight; E is depth-defense.
- **Sandbox vs. legitimate agent capability.** Real workflows need agents
  that *can* write to the workspace, *can* make network calls, *can* do
  destructive things on request. The sandbox must be ergonomic enough that
  legitimate tasks aren't blocked. This is a UX design problem as much as a
  security problem; expect iteration.
- **Skill packages remain a hole.** A malicious skill is arbitrary Python.
  Existing Docker isolation helps but doesn't fully close this. Out of
  scope for this plan; tracked by package governance.
- **Federation peers.** A peer agent under a different operator can inject
  into our runs via federation messages. Provenance tagging handles this
  (federation = data, not instructions), but trust boundaries between
  federated operators need separate threat modeling.
- **Cost.** Forcing all egress through a proxy and tagging all context
  adds latency and complexity. Phase A's instrumentation should measure
  this before Phase D enforces it.

---

## 8. References

- [`TRUST_VS_SANDBOX.md`](./TRUST_VS_SANDBOX.md) — the scope-clarification
  doc this plan implements.
- `core/agent_governance_service.py` — current trust-tier implementation
  (unchanged in role; becomes the second check, not the only check).
- `docs/agents/governance.md` — describes the existing maturity system.
- OWASP LLM Top 10 (LLM01: Prompt Injection) — vector taxonomy.
- Anthropic, *Constitutional AI* and *Many-shot Jailbreaking* papers —
  defense-in-depth philosophy, not direct applicability.
