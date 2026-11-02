# Final model request — test results

| # | Control | Detail | Result |
|---|---|---|---|
| 1 | `_react_step` final request | reviewed skill in `system_instruction`; generated code absent | PASS |
| 2 | Request payload | `system_instruction` 4,392 chars + `prompt` 138 chars written | PASS |
| 3 | GenericAgent prompt injection | skill present | PASS |
| 4 | Workspace block | skill named | PASS |
| 5 | Fresh session | skill still injected | PASS |
| 6 | Meta-agent | skill consumed | PASS |
| 7 | Workspace isolation | non-owning workspace empty | PASS |

Suites: 492 backend passed, 5 focused controls passed, 7 frontend passed.
Local serving of the captured request timed out/500 under load; recorded, not
claimed as model behavior.
