# ORACLE_VERIFICATION.md — Postcondition Oracle & Two-Tier Confidence (W2, P3)

> **Status**: implemented (shadow-first). Master switch `ATOM_ORACLE_VERIFIER_ENABLED` (default **false**).
> **Scope**: W2 upgrade items P3a (oracle), P3b (verify-before-retry), P3c (two-tier confidence), P3d (fact versioning).

## TL;DR

The oracle closes the **self-attestation gap**: `tool_outcome_verifier` grades a tool's *own* return
(`{verified: true, …}`), but the entity being checked must never grade its own work (Postcept principle).
The oracle **re-derives** success against the system of record (DB read-back) — independent of the tool's
claim — and the two-tier confidence layer makes that distinction explicit in audit: only
`EXTERNAL_VERIFIED` is credible; `INTERNAL_HIGH` (including an LLM tiebreak) is not.

## 1. Postcondition oracle (P3a)

`backend/core/oracle/__init__.py` (service) + `backend/core/oracle/postcondition_verifiers.py`
(per-action checks):

- `OracleResult(action, verified, evidence, claim_verified)` — frozen dataclass.
- `register_postcondition(action)` — decorator registry; add new high-risk mutating actions here.
- `validate(action, ctx)` — async, never raises (errors → `verified=False` with evidence). Returns
  `None` for unregistered actions (self-report stands).
- Pattern: **verify-before-retry** (arXiv 2608.02645) — on an ambiguous timeout, call
  `verify_before_retry(action, ctx)` BEFORE retrying. If the postcondition is already met the action
  succeeded despite the timeout — retrying would duplicate the side effect.

Verifiers (system of record, NOT tool claim):

| Action | Verifier | Reads |
|---|---|---|
| `trigger_workflow` | workflow row exists + status active/running/enabled | `Workflow` |
| `tasks.create` | Kanban task persists | `BoardTask` (`core.models_board`) |

> **Deviation from plan**: the plan named `core/oracle/oracle_service.py`; the implementation lives in
> `core/oracle/__init__.py` (single small module, avoids a one-function file). Verifier set is the
> minimal high-risk mutating pair the plan scoped; more actions = one `@register_postcondition` each.

## 2. Verify-before-retry wiring (P3b)

- `generic_agent._step_act` timeout branch: when a tool call raises "timeout", the oracle is consulted
  (flag-gated, lazy import, DB session opened fresh). Postcondition met ⇒ the LLM is told
  *"verified as succeeded — do NOT retry"* instead of *"you may try once more if critical"* (the old
  message that produced duplicate side effects).
- Kill-switch parity: flag off (or unregistered action, or genuinely unmet) ⇒ behavior is byte-for-byte
  the pre-P3 path.

## 3. Two-tier confidence (P3c)

`backend/core/selector_confidence_service.py`:

| Tier | Meaning | Auto-proceed? |
|---|---|---|
| `high` / `partial` / `ambiguous` | internal self-assessment (cheap, gameable) | no |
| `needs_external_validation` | bridge — internal says plausible, oracle pending | **no** (routes to review) |
| `external_verified` | oracle re-derived the effect | **yes** (only credible tier) |
| `external_refuted` | oracle disproved the tool's claim | no |

Critical rules (plan H5 — credibility laundering):

1. `INTERNAL_HIGH` is **not** auto-proceed-trusted: `_maybe_gate_with_proposal` (browser_tool) bypasses
   only when `level == HIGH and provenance != "internal"`. With `MATCH_CONFIDENCE_FORCE_PROPOSAL=true`
   an internal HIGH routes to ProposalService like partial/ambiguous; in shadow mode (default) it
   proceeds with annotation — no behavior change until enforcement flips.
2. `attach_tiebreak` (LLM tiebreak on PARTIAL) promotes to **`NEEDS_EXTERNAL_VALIDATION`**, never
   `HIGH` — an LLM pick is still internal self-assessment. `requires_review` includes the bridge tier.
3. `coerce_match_level_for_storage` (RN3): invalid input defaults to `AMBIGUOUS` (route-to-human), and
   the external tiers pass through unchanged (`_VALID_LEVELS` extended).

Provenance is denormalized into audit: `browser_audit` + `agent_reasoning_steps` gain indexed
`match_level` / `match_confidence_provenance` / `match_confidence_score` / `external_validated_at`
(migration `20260808_add_confidence_provenance.py`). `audit_service._create_browser_audit_record`
writes them from the `match_confidence` metadata envelope.

## 4. Fact versioning (P3d)

`turn_facts` gains git-like columns (migration `20260808_add_turn_fact_versioning.py`):
`parent_id` (superseded predecessor), `commit_message`, `author_type` (`extractor|tool|user|oracle`),
`branch_name`, `diff_summary`. `TurnFactExtractor._persist_one` writes the initial commit on create
(`parent_id=None, commit_message="created", author_type="extractor", branch_name="main"`) and, on a
stronger-fact supersede, marks the old row's `commit_message`/`diff_summary` and links the new row via
`parent_id`. An oracle confirmation of a fact is a commit authored by the oracle
(`author_type='oracle'`) — the wiring point for the future oracle→memory confirmation hook.

## 5. Flags

| Env var | Default | Effect |
|---|---|---|
| `ATOM_ORACLE_VERIFIER_ENABLED` | `false` (shadow) | oracle checks computed; kill switch for verify-before-retry |
| `MATCH_CONFIDENCE_FORCE_PROPOSAL` | `false` (shadow) | gate routes non-credible levels to ProposalService when true |
| `SELECTOR_CONFIDENCE_LLM_TIEBREAKER_ENABLED` | env | fires LLM tiebreak on PARTIAL (promotes to bridge) |

## 6. Verification

- `tests/core/test_oracle_and_two_tier_confidence.py` — 15 tests (lying-tool refutation, confirm,
  unregistered None, tiebreak bridge stop, bridge routing, verify_before_retry ×4 kill-switch parity,
  audit provenance denormalization).
- `tests/test_match_confidence_proposal_gating.py` — `TestTwoTierCredibilityGate` ×3 + updated
  INTERNAL_HIGH gating test.
- Migration smoke: scratch SQLite `create_all` → `stamp 20260808_add_lateral_messaging` →
  `upgrade head` = `20260808_add_turn_fact_versioning`; all 9 columns + indexes present.
