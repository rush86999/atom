# Results — employee-decided requested artifact

| Check | Result |
|---|---|
| `captured_exact_run` | PASS |
| `request_has_no_line_items` | PASS |
| `request_requests_document` | PASS |
| `assignment_completed` | PASS |
| `artifact_after_verified_quote` | PASS |
| `artifact_from_results` | PASS |
| `artifact_applied` | PASS |
| `artifact_criterion_met` | PASS |
| `ui_download_ok` | PASS |
| `api_download_ok` | PASS |
| `download_identity_matches` | PASS |
| `artifact_sha_matches` | PASS |
| `receipt_total_matches_independent_arithmetic` | PASS |
| `receipt_line_nets_match` | PASS |
| `artifact_has_exact_total` | PASS |
| `artifact_uses_receipt_expression` | PASS |
| `artifact_has_both_lines` | PASS |
| `artifact_shows_line_nets` | PASS |
| `artifact_has_source` | PASS |
| `artifact_has_human_labels` | PASS |
| `artifact_has_audit_section` | PASS |
| `ui_shows_exact_run` | PASS |

- Total checks: 22/22 passed.
- Receipt total: `370.00`; independent arithmetic: `370.00`.
- Receipt rows: `A 2 x 100.00 = 200.00`, `B 3 x 50.00 = 150.00`.
- Artifact SHA-256 (UI == API == recorded): `a6b8fffdb6d32dc6f2680310659db375ec71d3a7bd9ef0eef1996141ecee7583`.
- Model round: `[{"source": "model", "technical_fallback": false, "decision": "replan", "errors": [], "failure_stage": null, "attempt_id": "6fc7f4ff1e28433ca93e472217c507f3", "observation_ids": ["evidence-b1e4e29039defda2ac36"], "adoption_status": "applied", "work_request_operation": "quote_calculation", "execution_status": "completed"}]`.

Deterministic vs model: the model chose the operation and semantic column
mapping; the compiler resolved optional columns and generated all step ids,
dependencies, receipts, thresholds and artifact mechanics. No model output
was treated as proof.
