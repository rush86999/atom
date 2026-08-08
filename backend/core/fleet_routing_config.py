"""Fleet routing feature flags (env-driven, fail-safe defaults).

P1a (W4) wires the previously-dead ``route_with_governance`` path into the
live ``AtomMetaAgent.execute()`` dispatch so TASK intents can recruit a
specialist fleet. This is a behavioral change to a hot path, so the master
switch ``ATOM_FLEET_ROUTING_ENABLED`` defaults to **OFF** — flipping it to
``false`` (the default) restores the exact pre-P1a Queen→ReAct behavior
(kill-switch parity is covered by ``test_fleet_routing_wire.py``).

Mirrors the ``agent_radio/radio_config.py`` convention.
"""

import os

# Canonical env-var name for the master switch (exposed for flag-sanity
# checks and docs cross-reference; the live value is read via
# fleet_routing_enabled()).
ATOM_FLEET_ROUTING_ENABLED = "ATOM_FLEET_ROUTING_ENABLED"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def fleet_routing_enabled() -> bool:
    """Master switch for routing TASK intents through the governed fleet path.

    Defaults to False: live execute() keeps the Queen→ReAct path until this
    is explicitly turned on. Kill-switch parity — ``false`` == pre-P1a behavior.
    """
    return _env_bool(ATOM_FLEET_ROUTING_ENABLED, False)


def fleet_routing_force_enforce() -> bool:
    """Shadow-mode control.

    When False (the default during rollout), the governed branch is chosen
    and its recruitment summary is computed/audited, but the request still
    falls through to the Queen→ReAct path for the actual response — so the
    new path's telemetry can be observed without changing user-visible
    behavior. When True, the fleet-recruitment result is returned directly.
    """
    return _env_bool("ATOM_FLEET_ROUTING_FORCE_ENFORCE", False)
