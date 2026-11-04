# Results — integrated artifact + source-version change

| Check | Result |
|---|---|
| `phase1_completed` | PASS |
| `phase1_quote_370` | PASS |
| `phase1_artifact_has_370` | PASS |
| `phase1_no_line_items_supplied` | PASS |
| `revised_version_authorized` | PASS |
| `revised_version_identity_persisted` | PASS |
| `model_chose_next_work` | PASS |
| `model_chose_quote_work` | PASS |
| `phase2_completed` | PASS |
| `affected_quote_changed` | PASS |
| `prior_quote_result_retained` | PASS |
| `prior_quote_operation_retained` | PASS |
| `unrelated_note_operation_retained` | PASS |
| `unrelated_note_result_retained` | PASS |
| `artifact_revision_changed` | PASS |
| `artifact_has_new_total` | PASS |
| `artifact_excludes_superseded_total` | PASS |
| `artifact_criterion_still_met` | PASS |

- Total: 18/18 passed.
- Phase 1 quote/artifact: 370.00 / `4486b1274c0a9855e6fd4e972eb428e5a4879fb08f20a519daa67ca44e8dfe5f`.
- Phase 2 quote/artifact: 425.00 / `5d26049c83641f4d155f9c20c0ce7d9f1f6b1294b53fa618ddd4cfadbe419cd2`.
- Model rounds: phase 1 + phase 2 both `quote_calculation`, source `model`, no technical fallback.
