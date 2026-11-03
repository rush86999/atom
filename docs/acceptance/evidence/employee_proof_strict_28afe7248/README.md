# Employee strict proof-profile repair

Status: **submitted for independent verification; adaptive G5 remains
unqualified.**

This successor completes the typed proof-profile contract after the two
minimum-schema failures on c6ac292f3.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Worktree | `/private/tmp/atom-full-app` |
| Executed source | `28afe7248` (full SHA in `MANIFEST.json`) |
| Tree at integrated run | clean |
| Transport | controlled local service/DB; no live provider |

## Supported proof profiles

- **Source read:** observed resource identity, version/hash, explicit
  `verified` status, complete observed coverage. Every explicit
  `complete`/`known`/`truncated` flag must be a real boolean; counts must be
  finite, integral, nonnegative and paired. Missing, malformed, contradictory
  or incomplete proof is unknown/refuted.
- **External mutation:** observed operation identity plus observed remote/
  message identity; account/provider/message expectations are compared in
  their own namespaces. Provider acceptance is not Sent Items or delivery.
- **Sent Items:** presence observation + governed operation/request
  correlation + observed stable message identity. Missing either category is
  unknown; any known mismatch is false. Boolean/self-asserted shortcuts are
  ignored.
- **Artifact:** persisted artifact revision and sha256.
- **Local calculation:** durable value or calculation receipt.
- **Fact qualification:** stable source identity resolved against accepted
  assignment scope, or explicit authored authority.

## Results

| Scope | Result |
|---|---|
| Integrated backend | **742 passed**, 8 known WebSocket tests deselected |
| Frontend assignment/goal/approvals | **54 passed** |
| Independent evidence/G0/binding/minima probes | **16 passed** |
| Patch invariants | **8 passed** |
| Deterministic two-domain campaign | **4 passed** |
| Proof schema matrix (all sources) | **53 passed** |
| Focused affected suites | **270 passed** |

The generated matrix covers omission/None/wrong-type for each required field,
one-wrong/all-other-right identities, namespace swaps, malformed/contradictory
coverage flags, non-finite/negative/unpaired counts, boolean shortcuts and
valid complete twins through the real executor/objective path.

## Boundaries

- No served adaptive model choice or held-out two-domain campaign.
- No live provider action/credential/consent/send/spend/reseed/deployment.
- Planner 5/5, goal router 1/2, alignment gap 3.0 and historical 111/123
  remain unchanged.
