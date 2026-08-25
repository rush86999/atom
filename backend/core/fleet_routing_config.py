"""Fleet routing feature flags (env-driven, fail-safe defaults).

P1a (W4) wires the previously-dead ``route_with_governance`` path into the
live ``AtomMetaAgent.execute()`` dispatch so TASK intents can recruit a
specialist fleet. Since 2026-08-21 the master switch
``ATOM_FLEET_ROUTING_ENABLED`` defaults to **ON (shadow)**: eligible TASK
intents get governed recruitment computed + audited, while responses still
come from Queen→ReAct unless ``ATOM_FLEET_ROUTING_FORCE_ENFORCE=true``.
``ATOM_FLEET_ROUTING_ENABLED=false`` is the full kill switch, restoring the
exact pre-P1a behavior (parity covered by ``tests/unit/test_fleet_routing_wire.py``).

Mirrors the ``agent_radio/radio_config.py`` convention.
"""

from core.runtime_settings import get_bool_setting

# Canonical env-var name for the master switch (exposed for flag-sanity
# checks and docs cross-reference; the live value is read via
# fleet_routing_enabled()).
ATOM_FLEET_ROUTING_ENABLED = "ATOM_FLEET_ROUTING_ENABLED"


def _env_bool(name: str, default: bool) -> bool:
    # Raw env parse FIRST (legacy contract incl. uncataloged keys), then
    # runtime_settings DB row (UI admin), then default.
    import os

    raw = os.getenv(name)
    if raw is not None:
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return get_bool_setting(name, default)


def fleet_routing_enabled() -> bool:
    """Master switch for routing TASK intents through the governed fleet path.

    Defaults to **True** since 2026-08-21: eligible TASK intents get governed
    recruitment computed and audited on every execute(). With
    ``fleet_routing_force_enforce()`` False (the default) this is SHADOW mode —
    responses still come from Queen→ReAct; only telemetry changes. Set
    ``ATOM_FLEET_ROUTING_ENABLED=false`` for full kill-switch parity with
    pre-P1a behavior.
    """
    return _env_bool(ATOM_FLEET_ROUTING_ENABLED, True)


def fleet_routing_force_enforce() -> bool:
    """Shadow-mode control.

    When False (the default), the governed branch is chosen and its
    recruitment summary is computed/audited, but the request still falls
    through to the Queen→ReAct path for the actual response — so the new
    path's telemetry can be observed without changing user-visible behavior.
    When True, the fleet-recruitment result is returned directly.
    """
    return _env_bool("ATOM_FLEET_ROUTING_FORCE_ENFORCE", False)
