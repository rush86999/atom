# Chat session fork — test results

Executed source: `371cb197b9f5b69e6b1ef3b75580b501b1f7f575`  
Base main: `d860072a787e6460d83260e9cb629cfa5d5ea14b`  
Prepared provenance: branch `codex/oracle01-chat-20261105`, tip `eede11a8f`

Every command ran from `backend/` with:

```sh
export PYTHONDONTWRITEBYTECODE=1
export TESTING=1
export PYTHONPATH=$PWD
PY314=/Users/rushiparikh/projects/atom/backend/venv314/bin/python
PY311=python3.11
```

## Focused chat-fork gate

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_chat_fork_decision_contract.py \
  tests/test_chat_store_session_fork.py \
  tests/test_chat_session_fork.py \
  -q --tb=short
```

| Version | Result | Log |
|---|---|---|
| Python 3.14 | **38 passed** | `focused-314.log` |
| Python 3.11 | **38 passed** | `focused-311.log` |

`test_chat_fork_decision_contract.py` contributes 24 new controls:
owner full/prefix forks, foreign owner, empty/unknown source, replay and
changed prefix, stale source, stale message content, authority change,
audit rollback, post-commit readback, lost confirmation, tampered receipt and
anonymous refusal.

## Affected chat selection

```sh
$PY314 -B -m pytest -p no:randomly \
  tests/test_chat_fork_decision_contract.py \
  tests/test_chat_store_session_fork.py \
  tests/test_chat_session_fork.py \
  tests/test_chat_session_delete.py \
  tests/test_chat_session_ownership_regression.py \
  tests/test_chat_history_retrieval.py \
  tests/test_chat_idor_security.py \
  tests/test_covpush_w92_chat_routes.py \
  tests/api/test_chat_assistant_and_teaching.py \
  tests/test_chat_integration.py \
  tests/test_chat_transport.py \
  tests/test_chat_orchestrator.py \
  tests/test_covpush_w109_chat_orchestrator.py \
  tests/test_covpush_w115_chat_orchestrator.py \
  -q --tb=line
```

| Tree | Python | Passed | Failed | Log |
|---|---|---|---|---|
| Candidate `371cb197b` | 3.14 | **314** | 7 | `affected-314.log` |
| Candidate `371cb197b` | 3.11 | **314** | 7 | `affected-311.log` |
| Main `d860072a7` | 3.14 | 290 | 7 | `baseline-main-314.log` |
| Main `d860072a7` | 3.11 | 289 | 8 | `baseline-main-311.log` |

The baseline selection excludes only the new candidate contract file, so the
shared tests are identical. Candidate delta: **+24 passing controls, zero new
failures**.

### Shared baseline failures (7)

- `tests/test_chat_transport.py::test_blank_reply_is_reported_as_unavailable_not_silently_empty`
- `tests/test_covpush_w109_chat_orchestrator.py::TestProcessMessageEdgePaths::test_lkgp_sticky_hint_exception_swallowed`
- `tests/test_covpush_w92_chat_routes.py::TestGetChatHistory::test_db_fallback`
- `tests/test_covpush_w92_chat_routes.py::TestRoutingStats::test_disabled`
- `tests/test_covpush_w92_chat_routes.py::TestRoutingStats::test_enabled_no_router`
- `tests/test_covpush_w92_chat_routes.py::TestRoutingStats::test_stats_error`
- `tests/test_covpush_w92_chat_routes.py::TestRoutingStats::test_stats_success`

### Additional main-3.11 failure not reproduced

- `tests/test_covpush_w115_chat_orchestrator.py::TestGetQwenResponse::test_success_with_history`

It is unrelated to the fork route and passes on the candidate. It is recorded
as a main-side flake, not claimed as a repair.

## Added repair during the port

The prepared service claimed the session row but did not re-read message rows
after the claim. A concurrent in-place message edit could therefore be forked
as stale content. The candidate re-reads the ordered snapshot after the claim
and refuses 409 `STALE_SOURCE` on any digest change. The failing twin
`test_stale_message_content_before_claim_refuses` asserts no fork, no copied
messages and no audit.

## Notes

- Logs use `-p no:randomly` for deterministic identity comparison.
- Candidate and baseline ran on the same host and declared environment.
- No live model/provider/credential/spend/send/download/deployment operation.
