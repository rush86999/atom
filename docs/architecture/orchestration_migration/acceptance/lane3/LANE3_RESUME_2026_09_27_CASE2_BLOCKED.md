# Lane 3 resume - case 2 blocked on a background-path defect

Case 1 (synchronous controlled mutation) PASSES 15/15, all five boundaries green.
Case 2 (background success) reaches the product's OWN async fork and the write lands,
but the continuation never records or announces a verified terminal success.

Machine-readable detail, hashes, live-world identity and next command:
`c16_controlled/CHECKPOINT.json`. Case 1 evidence is preserved untouched in
`c16_controlled/RESUME.md` and `c16_controlled/c16_controlled_planner.json`.

This document is additive; no other stream's resume file was overwritten.

```json
{
  "schema": "lane3-c16-checkpoint-v1",
  "overall": "ACCEPTANCE INCOMPLETE - C16 still FAILED. Case 1 sync PASS; case 2 background blocked on a real product defect.",
  "next_command": "backend/venv314/bin/python docs/architecture/orchestration_migration/acceptance/lane3/controlled_planner_c16.py --world c16_d0 --out docs/architecture/orchestration_migration/acceptance/lane3/c16_controlled --port 8074 --relaunch --mode bg-success",
  "expected_next_assertion": "durable AgentExecution.status in (success, completed) AND >=1 `chat_continuation` WS event on channel user:{uid} whose continuation_id matches the durable row AND history contains the continuation record",
  "next_root_cause_step": "In core/async_turn_continuation.py the attempt branch treats the edit as unconfirmed when readback_ok is False. The write demonstrably lands, so determine WHICH is false: (a) response['data']['canvas_edit']['updated'] is not True (D0 postcondition verification failing only on the background path), (b) _operation_landed(cont) is False, or (c) tools.canvas_crud_tool.read_canvas returns no audit_id. Log the branch decision at INFO once, then re-run. Do NOT weaken verification to make the test pass.",
  "not_done": [
    "case 2 completion",
    "case 3 background failure",
    "D5 completion UX",
    "real-planner evaluation on API-created canvases",
    "canvas creation/read consistency (step 5)",
    "final combined candidate freeze",
    "public/browser acceptance",
    "handoff publication",
    "artifact editing promotion (correctly still excluded)"
  ]
}
```
