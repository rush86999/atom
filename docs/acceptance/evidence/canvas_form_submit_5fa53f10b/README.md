# Durable form presentation and verified submission

Runtime: 5fa53f10b. Executed test/CI successor: 3644c792a (runtime bytes unchanged). The dedicated 54-control gate passes on Python 3.14 and 3.11. CI includes this gate.

Normal form presentation now persists the actor-scoped Canvas schema/title and present audit before independent verification and broadcast. Exact actor/operation retries reuse that surface and audit without another broadcast; changed material conflicts. Explicit missing/foreign/disabled agents cannot become fallback authority. User scope is authoritative; actor claims and final agent checks protect the mutation transaction. Presentation is not credited as satisfied business work.

POST /api/canvas/submit uses the existing CanvasAudit ledger and oracle. Same-scope shared form submissions remain legal; submit is an event and does not grant authorship. Current actor, target scope, optional agent/execution, request material and operation bind the receipt. No failed, missing, stale, disabled or contradictory proof becomes verified success. Lost confirmation retains original opaque identities and do_not_repeat.

The three older form integration cases used an unseeded hardcoded user. Their old baseline passed, while the new authority contract correctly refused. Their fixture now provides real scoped records; original success assertions remain and durable schema/scope assertions were added. No test was skipped or removed. Python 3.11 disables an automatic-retry plugin that cannot bind a local socket in this environment; tests are not retried.

The predecessor bundles retain failure-first evidence. The broader predecessor selection had 167 passes and four exact WebSocket failures on each runtime; those four reproduce on exact base b550 on both versions. They remain open baseline defects, not green coverage.

Two isolated DeepSeek Flash CLI proposals were step bounded and independently adjudicated. Both exited zero at the cap; neither was accepted as complete solely from that exit. The second proposal was incomplete and failed the three original retry/selection negatives until root integration. No application inference, browser journey, real account action, deployment, PostgreSQL or multi-worker qualification is claimed. Hosted checks and independent review are pending.
