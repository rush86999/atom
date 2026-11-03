# Results — capability/eligibility batch 7df7ad08d

| Scope | Result |
|---|---|
| API-level normal-product campaign | **18/18 checks passed** |
| Quote unfamiliar headers | **370.00**, then **485.00** after change |
| Restart while completed | **485.00** survives |
| Cancellation | terminal `cancelled` |
| Invoice | **270.00** |
| Missing invoice | targeted question naming `invoice` + `PO-8` |
| Source answer | resolved obligation, no duplicate step |
| Recovery | **270.00** |
| Focused suite | **167 passed** |
| Eligibility probe | **2 passed** |

`campaign.json` holds the scenario records and check details;
`attempts.jsonl` holds model dispatch/parsed/raw traces; `focused-tests.log`
and `eligibility-probe.log` are the deterministic controls; `world-guard.log`
shows the existing unmarked world refusal with sentinel preservation.
