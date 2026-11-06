"""Test-only isolated provider catalogue for doubled cloud-route fixtures.

Production route eligibility is not relaxed. Tests that exercise a doubled
configured cloud route install a fresh, explicit discovery catalogue for the
models their fake clients serve, matching the current ``evaluate_route``
contract (unknown catalogue is not a licence to dispatch).
"""
from __future__ import annotations

from typing import Dict, Iterable

import core.llm.model_route_registry as mrr


def install_route_catalog(
    monkeypatch,
    tmp_path,
    models_by_provider: Dict[str, Iterable[str]],
):
    catalog = mrr.ProviderModelCatalog(
        path=str(tmp_path / "route-catalog.json"))
    for provider_id, models in models_by_provider.items():
        catalog.record_discovery(provider_id, list(models))
    monkeypatch.setattr(
        mrr, "get_provider_model_catalog", lambda: catalog)
    return catalog
