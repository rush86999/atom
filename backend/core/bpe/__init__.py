"""BPE runtime workspace (Belief / Progress / Experience).

Research-grounded adaptation of EvoHarness-RL's policy-facing harness state
(arXiv:2608.05446) — see ``docs/architecture/BPE_WORKSPACE_PLAN.md``.

Modules:
- ``workspace``  — the (B, P, E) container, meta-action application, rendering
- ``adapter``    — domain-specific grounding behind a functional interface
- ``telemetry``  — span emission for every workspace read/write
- ``actions``    — ``workspace.track/commit/recall/note`` action registration
"""
