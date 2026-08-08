"""
P0a — Reconciliation of the two competing IntegrationService base classes.

Hazard H4 (STANFORD_VIRTUAL_BIOTECH_PAPERCLIP.md): the codebase has TWO
incompatible ``IntegrationService`` ABCs — ``core/integration_service.py``
(62 adopters, dict return, ``get_capabilities``/``health_check``) and
``core/integration_base.py`` (4 adapters, pydantic ``OperationResult``,
``get_supported_operations``). Notion is wrapped under both. This suite
verifies the collapse: Base B is deleted, its ``OperationResult`` +
``IntegrationErrorCode`` move into Base A (preserving the typed envelope),
the 4 adapters inherit Base A, and the registry repoints its import.

Run: ``cd backend && venv/bin/python -m pytest tests/core/test_integration_base_reconciliation.py -v``
"""
import importlib
import sys

import pytest


# ---------------------------------------------------------------------------
# 1. OperationResult + IntegrationErrorCode now live in Base A.
# ---------------------------------------------------------------------------
def test_operation_result_importable_from_integration_service():
    """OperationResult was moved from integration_base into integration_service."""
    from core.integration_service import OperationResult  # noqa: F401


def test_integration_error_code_importable_from_integration_service():
    from core.integration_service import IntegrationErrorCode

    # B-only members must survive the merge so adapters don't NameError.
    for member in (
        "INVALID_PARAMETERS",
        "AUTH_EXPIRED",
        "NOT_FOUND",
        "API_ERROR",
        "TIMEOUT",
        "EXECUTION_EXCEPTION",
        "LICENSE_RESTRICTED",
    ):
        assert hasattr(IntegrationErrorCode, member), (
            f"IntegrationErrorCode.{member} missing after merge — adapter code would NameError"
        )


# ---------------------------------------------------------------------------
# 2. integration_base.py is gone.
# ---------------------------------------------------------------------------
def test_integration_base_module_removed():
    """The competing base module must be deleted once all importers repointed."""
    # Purge any cached import so importlib reflects the filesystem.
    sys.modules.pop("core.integration_base", None)
    with pytest.raises(ImportError):
        importlib.import_module("core.integration_base")


# ---------------------------------------------------------------------------
# 3. Each of the 4 adapters inherits Base A and satisfies its abstract
#    surface (get_capabilities + health_check), while still returning the
#    OperationResult envelope the registry expects.
# ---------------------------------------------------------------------------
ADAPTER_CASES = [
    ("integrations.adapters.notion_adapter", "NotionAdapter", "notion"),
    ("integrations.adapters.asana_adapter", "AsanaAdapter", "asana"),
    ("integrations.adapters.slack_adapter", "SlackAdapter", "slack"),
    ("integrations.adapters.hubspot_adapter", "HubSpotAdapter", "hubspot"),
]


@pytest.mark.parametrize("module_path,class_name,connector_id", ADAPTER_CASES)
def test_adapter_inherits_base_a(module_path, class_name, connector_id):
    from core.integration_service import IntegrationService as BaseA

    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    assert issubclass(cls, BaseA), (
        f"{class_name} must inherit core.integration_service.IntegrationService after reconciliation"
    )


@pytest.mark.parametrize("module_path,class_name,connector_id", ADAPTER_CASES)
def test_adapter_satisfies_base_a_abstracts(module_path, class_name, connector_id):
    """Base A requires get_capabilities + health_check; Base B only required get_supported_operations."""
    from core.integration_service import IntegrationService as BaseA

    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    # If these were left abstract, instantiation would raise TypeError.
    instance = cls(tenant_id="default", config={})
    caps = instance.get_capabilities()
    assert isinstance(caps, dict) and "operations" in caps, (
        f"{class_name}.get_capabilities() must return a dict with an 'operations' key (Base A contract)"
    )
    health = instance.health_check()
    assert isinstance(health, dict) and "healthy" in health, (
        f"{class_name}.health_check() must return a dict with a 'healthy' key (Base A contract)"
    )


# ---------------------------------------------------------------------------
# 4. The registry imports from Base A and constructs adapters with tenant_id=.
# ---------------------------------------------------------------------------
def test_registry_imports_from_base_a():
    """integration_registry_v2 must no longer import from integration_base."""
    import core.integration_registry_v2 as reg

    assert reg.OperationResult.__module__.startswith("core.integration_service"), (
        "registry's OperationResult must come from core.integration_service, not integration_base"
    )
    assert reg.IntegrationErrorCode.__module__.startswith("core.integration_service"), (
        "registry's IntegrationErrorCode must come from core.integration_service"
    )


def test_registry_constructs_adapter_via_tenant_id(monkeypatch):
    """get_service must construct adapters with tenant_id= (Base A ctor), not workspace_id=."""
    import core.integration_registry_v2 as reg_mod

    registry = reg_mod.IntegrationRegistryV2(workspace_id="ws-test")
    # Force a clean cache so construction runs.
    registry._service_cache.clear()
    service = registry.get_service("notion", config={"access_token": "fake-token"})
    assert service is not None, "notion adapter failed to construct — ctor signature mismatch?"
    # Base A stores tenant_id; the registry passes workspace_id as the tenant scope.
    assert getattr(service, "tenant_id", None) == "ws-test", (
        "adapter must expose tenant_id (Base A identity), set from the registry's workspace_id"
    )
