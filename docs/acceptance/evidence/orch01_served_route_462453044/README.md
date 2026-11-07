# ORCH01 authenticated served-route control

Executed source `462453044`, runtime base `248a23296`. Test-only change.

A separate Python/uvicorn process serves the production workflow router over an inherited localhost socket. The test checks the server PID differs from the parent. Each test owns explicit temporary SQLite/data/LanceDB locations. Importing the test does not change global DB environment. Real JWT validation and permission dependencies are exercised without dependency overrides; JWTs are issued using the production helper, not ordinary login. Structured-model transport and classification are doubled. An observing orchestrator double records registration/execution attempts: this is an additional seam, not only a model double.

Checks: unauthenticated401, typed persisted design/digest with HITL gates, correctly non-executable unbound design, no registration/execution/trigger activation, exact HTTP and fresh-session DB readback, scope compatibility refusals, empty422, invalid422 and no-suitable503 without extra persistence. Single-tenant user/workspace behavior remains the product target.

Python3.14 results: new served control1passed; combined existing-blueprint neighborhood18passed. Disclosed logs retain test messages/results and replace only the two explicit local path prefixes listed in verification.json; raw originals remain private and were not regenerated. Inspection found no JWT, Bearer credential, credential query or known test secret. Artifact identities describe the sanitized disclosure bytes.

ZCodeStart-plan GLMFlash loweffort generated the initial unexecuted harness. It used a thread while claiming process coverage and changed DB environment at import. Lead review corrected both, added no-suitable coverage and executed the retained runs. A first lead invocation used a wrong relative path and collected no tests; it is not counted.

Boundary: minimal mounted-router process, not full production bootstrap, ordinary login, live-model quality, process-restart recovery, PostgreSQL or multi-worker qualification. No production runtime changes or live DB/provider actions. Prior accepted evidence is preserved. Full ORCH01/whole-app acceptance is not claimed.
