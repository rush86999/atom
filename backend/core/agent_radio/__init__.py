"""
Agent Radio — lateral (peer-to-peer) asynchronous coordination between agents.

Modeled on the AgentRadio protocol (arXiv:2607.28430): a fixed team of agents
shares one or more threads and exchanges directed @mentions in real time while
continuing their primary work. This package provides:

- ``radio_service``  — DB source of truth (AgentThread / LateralMessage).
- ``radio_server``   — async in-memory relay + bounded ``wait_for_mention``.
- ``radio_guard``    — attention + cost governance (mention-first, caps, budget).
- ``radio_breaker``  — responsibility-breakpoint detection (when to team up).
- ``radio_adapter``  — small Fleet adapter (thread auto-attach for breakpoint
  tasks only — a fixed multi-agent team is NOT the default).

See ``docs/architecture/AGENT_RADIO.md`` and ``docs/agents/lateral-messaging.md``.
"""