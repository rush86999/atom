"""Computer-use operator — one governed observe→decide→act loop over pluggable
actuation backends (browser today, desktop later).

Architecture (docs: plan 2026-09-12, "Computer Use Operator"):

- session.py  — OperatorSession: the browser actuation backend. Wraps the
  production Playwright sessions from tools/browser_tool.py (SSRF guard,
  BrowserAudit rows, selector-confidence where selectors are used) and adds
  coordinate/keyboard actions, a unified Observation (downscaled screenshot
  + URL/title/text), risky-action guardrails, and per-action audit.
- loop.py     — OperatorLoop: the decide loop (one action per fresh
  observation, step budget, governance hard-stop, three-failure abort —
  the same rails LuxModel.run_task established). The decide-step protocol
  is pluggable: v1 is the JSON-vision protocol any vision+tools model can
  serve through LLMService(task_type="computer_use", image_payload=...).
- models.py   — the researched computer-use model pool for the BPC router
  (capability data, not call-site branches).
- tools.py    — the agent-facing surface: operator_start_task /
  get_status / get_screenshot / stop_task plus the in-memory run registry.
- legacy_bridge.py — retires the old mcp_service dual-mode browser dispatch
  (dead cloud_browser_service import + desktop-bridge simulation) by
  delegating legacy names to the real governed browser tools.

Model-research summary (2026-09, sources in the plan):
- Claude 4.6 + computer_20250124 tool: top OSWorld-Verified (~72.5–72.7%).
- gpt-6-astra: top GUI grounding (ScreenSpot-Pro ~92.7%) — repo default.
- OpenAI CUA computer-use-preview: top browser-only (WebArena ~87%),
  $3/$12 per MTok.
- Native CUA protocols (Anthropic computer-use tool, OpenAI Responses
  computer_use_preview) are phase 2 — they hang off the same backends.
"""
