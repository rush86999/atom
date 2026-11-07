Invalid baseline capture, preserved honestly and NOT used for
classification. `PYTHONPATH=.baseline_api python -m pytest ...` from
backend did not load the shim (cwd/backend won sys.path[0]); the run
therefore exercised the candidate source. Root's actual Git baseline
at /private/tmp/atom-agent-job-baseline (source 335fd77fa) is the
authoritative comparison: ../root-actual-baseline-findings.json.
