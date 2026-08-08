# Lateral Messaging (Agent Radio)

> Peer-to-peer coordination for working agents. A plain-English guide to the
> protocol, the primitives, the governance, and the knobs. Deep-dive:
> [`docs/architecture/AGENT_RADIO.md`](../architecture/AGENT_RADIO.md).

## What it is

Modeled on the AgentRadio protocol (Coral AI Labs, arXiv:2607.28430): a team
of agents doing interdependent subtasks shares a **thread** and exchanges
directed **@mentions** while each goes on working. The core idea: *an agent
that is working can also be listening* — discoveries propagate in real time
before their operational value expires (the MinIO-log case in the paper: a
0→16/16 score flip from one mid-execution broadcast).

Atom's implementation is **mention-first, thread-scoped, cost-governed, and
opt-in by task type** — a fixed team is never the default.

## The three primitives (plus a read)

All four are exposed as `radio.*` registry actions (i.e. also
`POST /api/rpc/radio.*`), maturity-gated per tool:

| Primitive | What the agent sees | Tier |
|---|---|---|
| `radio.create_thread(name, member_agent_ids)` | Opens a shared thread; creator is added automatically | INTERN+ |
| `radio.send_message(thread_id, content, mention_agent_ids)` | Directed @mention. **No broadcast** — a recipient is required | INTERN+ |
| `radio.wait_for_mention(thread_id, timeout≤30s)` | Bounded block — only when the current step truly depends on a peer's answer | STUDENT+ |
| `radio.read_inbox(thread_id?)` | Non-blocking snapshot (instant context, like a worklog) | STUDENT+ |

**Passive awareness is automatic**: whenever the agent's context carries a
`radio_thread_id`, the ReAct loop drains pending mentions at the top of every
step and injects them as `[RADIO INBOX]` history lines. The agent never has
to poll; the system never forces a block.

## When a team forms

Fleet recruitment (`_recruit_fleet`) auto-creates ONE thread per
DelegationChain — but only when the task crosses a **responsibility
breakpoint** (`core/agent_radio/radio_breaker.py`): legacy/unfamiliar
systems, cross-service incidents, security analysis, migrations,
multi-module refactors, dependency coordination (≥2 signals). Bounded local
work (single-file change, boilerplate, rename) always stays single-agent.
Gate: `ATOM_RADIO_BREAKPOINT_GATE`.

The thread id is stamped onto the chain executions
(`AgentExecution.thread_id`) and flows to members via
`context["radio_thread_id"]`, so each member's loop picks mentions up.

## Governance (paper bottleneck #1)

- **Mention-first**: a send without ≥1 explicit recipient is rejected.
- **Per-drain cap**: max pending mentions surfaced per drain
  (`ATOM_RADIO_INBOX_CAP`).
- **Staleness**: mentions older than `ATOM_RADIO_BACKLOG_TTL_MIN` min are
  not surfaced.
- **Budget**: per-thread cumulative message cost ceiling
  (`ATOM_RADIO_TEAM_BUDGET_USD`); sending past it raises `RadioBudgetExceeded`.
- **Delivery bookkeeping**: per-recipient read state (`metadata_json.read_by`);
  a message counts delivered only once every mentioned agent has read it.
  Surfaced mentions are marked read so an inbox message appears exactly once.

## Data model

- `agent_threads` — shared channel (chain-scoped: `chain_id` FK).
- `lateral_messages` — directed messages (mentions JSON, `delivered`).
- **Distinct from `agent_messages`**, which is live board-comment storage
  (do not reuse).

## Kill switch & docs

- `ATOM_RADIO_ENABLED=false` restores the pre-radio behavior everywhere
  (tools reply "disabled"; drains yield nothing).
- HTTP surface: `POST /api/rpc/radio.create_thread|send_message|
  wait_for_mention|read_inbox` — passes through the Unified Action Registry
  (capability + sandbox gates apply automatically).
- Cost math notes: a radio team multiplies API spend (paper: ~$2.96 → ~$19.45
  per task) but is structural, not brute-force — compute-matched 6 runs scored
  37.9% vs the team's 62.1%. Keep teams for breakpoint tasks only.