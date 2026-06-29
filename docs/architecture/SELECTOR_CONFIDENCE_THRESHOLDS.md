# Selector Confidence Thresholds — Tuning Guide

> **One-pager** on tuning the pre-action match-confidence layer.
> See `docs/architecture/MATCH_CONFIDENCE.md` for the full design.

## Environment Variables

| Flag | Default | Range | Effect |
|---|---|---|---|
| `SELECTOR_CONFIDENCE_ENABLED` | `true` | bool | Master switch for scorer + annotation |
| `BROWSER_LOCATOR_API_ENABLED` | `true` | bool | Use `page.locator()` (true) or legacy `query_selector*` (false) |
| `MATCH_CONFIDENCE_HIGH_THRESHOLD` | `0.85` | float 0–1 | `>=` this score → `level=high` |
| `MATCH_CONFIDENCE_PARTIAL_THRESHOLD` | `0.50` | float 0–1 | `>=` this score → `level=partial`; below → `ambiguous` |
| `MATCH_CONFIDENCE_FORCE_PROPOSAL` | `false` | bool | Gate partial/ambiguous through ProposalService (shadow default) |
| `SELECTOR_CONFIDENCE_LLM_TIEBREAKER_ENABLED` | `true` | bool | LLM tiebreaker for partial band |
| `SELECTOR_CONFIDENCE_LLM_TIMEOUT_SECONDS` | `2.0` | float | Hard timeout on tiebreaker LLM call |
| `SELECTOR_CONFIDENCE_LLM_CACHE_ENABLED` | `true` | bool | Cache tiebreaker results per selector+hostname |

## Score Curve

```
score = max(0.0,
  1.0
  - 0.30 * (match_count - 1)
  - 0.15 * is_text_only
  - 0.10 * (appeared_after_ms > 1000)
)
```

| Matches | Text-only? | Late? | Score | Default Level |
|--------:|:----------:|:-----:|------:|:--------------|
| 1       | no         | no    | 1.00  | high          |
| 1       | yes        | no    | 0.85  | high          |
| 1       | yes        | yes   | 0.75  | partial       |
| 2       | no         | no    | 0.70  | partial       |
| 2       | yes        | yes   | 0.45  | ambiguous     |
| 3       | no         | no    | 0.40  | ambiguous     |
| 5+      | any        | any   | 0.00  | ambiguous (floor) |

## Tuning Scenarios

### "Too many proposals" (over-gating)

Lower `MATCH_CONFIDENCE_HIGH_THRESHOLD` from 0.85 → 0.75. This promotes
2-match cases (0.70 → still partial) but promotes single-text-only-late
(0.75 → high) to direct execution. Watch Prometheus for proposal volume
vs baseline.

### "Wrong element clicked on 2-match cases"

Either (a) lower `MATCH_CONFIDENCE_PARTIAL_THRESHOLD` from 0.50 → 0.40
so 3-match cases still execute (if you trust the LLM tiebreaker), or
(b) verify the tiebreaker is firing (`SELECTOR_CONFIDENCE_LLM_TIEBREAKER_ENABLED=true`)
and check its cache hit rate. The tiebreaker should resolve most
2-match partials to a single candidate.

### "Tiebreaker too slow / too expensive"

1. Verify cache: `SELECTOR_CONFIDENCE_LLM_CACHE_ENABLED=true`. Repeat
   selectors on the same hostname amortize to zero LLM cost.
2. Lower timeout: `SELECTOR_CONFIDENCE_LLM_TIMEOUT_SECONDS=1.0`.
3. As last resort, disable: `SELECTOR_CONFIDENCE_LLM_TIEBREAKER_ENABLED=false`.
   Partials will route directly to ProposalService.

### "Circuit breaker keeps tripping"

The breaker opens after 5 consecutive failures (LLM errors or timeouts)
and stays open for 120s. Check:
- LLM provider health (`/health/ready`)
- API key validity
- Network latency to provider

Breaker state is in-memory per-process; restarting the service resets it.

## Per-Agent Opt-Out

```sql
-- Disable gating for one misbehaving agent (overrides global flag):
UPDATE agent_registry
   SET match_confidence_gating_enabled = false
 WHERE id = '<agent-id>';

-- Force gating for one agent (regardless of global shadow mode):
UPDATE agent_registry
   SET match_confidence_gating_enabled = true
 WHERE id = '<agent-id>';
```

`NULL` (default) → falls through to `MATCH_CONFIDENCE_FORCE_PROPOSAL`.

## Verifying Current Behavior

```bash
# Check effective flags:
curl -s http://localhost:8000/health/ready | jq .details.match_confidence

# Tail audit rows to see what level real actions are getting:
sqlite3 ./atom_dev.db \
  "SELECT action, json_extract(metadata_json, '$.match_confidence.level') AS level,
          json_extract(metadata_json, '$.match_confidence.score') AS score
     FROM browser_audit
    WHERE created_at > datetime('now', '-1 hour')
    ORDER BY created_at DESC LIMIT 20;"
```
