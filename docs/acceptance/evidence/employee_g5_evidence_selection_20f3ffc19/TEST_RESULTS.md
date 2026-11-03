# Results — current-source evidence selection `20f3ffc19`

| Scope | Result |
|---|---|
| Evidence selection, industrial quote | model source; required sources selected |
| Evidence selection, procurement | **negative**; parsed proposal mixed `source_id` and `action`, omitted `invoice-v1`; deterministic fallback selected `purchase-order` only |
| Backend affected suite | **777 passed**, 8 known WebSocket tests deselected |
| Independent verifier probes | **20 passed** |
| Frontend | **54 passed** |
| Typed quote/invoice work requests | passed separately at 370.00 / 270.00 (`employee_two_domain_work_smoke_20f3ffc19`) |

The remaining G5 gap is upstream procurement source selection, not typed-work
compilation. The full two-domain journey is not established.
