# -*- coding: utf-8 -*-
"""Coverage wave 84 — core/package_feature_service (standalone, env/package
detection mocked via monkeypatch; zero DB, zero network).

- Edition/Feature enum values + FeatureInfo defaults (dependencies []).
- _detect_edition: ATOM_EDITION enterprise/full/personal; package extras
  detection (distribution present with/without postgresql requirement,
  PackageNotFoundError, distribution() raising); DATABASE_URL postgresql/
  postgres; default personal.
- _build_feature_set enterprise (all) vs personal (personal-only registry).
- edition/is_enterprise/is_personal properties.
- is_feature_enabled: personal feature, enterprise feature (missing),
  dependency-gated features (workspace_isolation/ssa/rbac → multi_user,
  advanced_analytics → monitoring, bi_dashboard → advanced_analytics),
  unknown feature.
- get_available_features copy semantics.
- get_enterprise_features / get_personal_features sets.
- require_feature raises PermissionError (with/without registry entry),
  passes when enabled.
- get_feature_info present/absent.
- list_features: availability flags, edition, dependency values, sort order.
- module-level API: get_package_feature_service singleton, is_enterprise_enabled,
  is_feature_enabled, require_enterprise raise/pass.
"""
import importlib.metadata
import pytest

from core.package_feature_service import (
    Edition,
    Feature,
    FeatureInfo,
    FEATURE_REGISTRY,
    PackageFeatureService,
    get_package_feature_service,
    is_enterprise_enabled,
    is_feature_enabled,
    require_enterprise,
)


@pytest.fixture(autouse=True)
def _reset_singleton(monkeypatch):
    import core.package_feature_service as mod
    PackageFeatureService._instance = None
    PackageFeatureService._edition = None
    PackageFeatureService._available_features = None
    mod._package_feature_service = None
    monkeypatch.delenv("ATOM_EDITION", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    yield
    PackageFeatureService._instance = None
    PackageFeatureService._edition = None
    PackageFeatureService._available_features = None
    mod._package_feature_service = None


# ============================================================================
# Enums + FeatureInfo
# ============================================================================

class TestEnumsAndMetadata:
    def test_edition_values(self):
        assert Edition.PERSONAL.value == "personal"
        assert Edition.ENTERPRISE.value == "enterprise"

    def test_feature_values(self):
        assert Feature.LOCAL_AGENT.value == "local_agent"
        assert Feature.RBAC.value == "rbac"

    def test_feature_info_defaults_dependencies(self):
        info = FeatureInfo("X", "desc", Edition.PERSONAL)
        assert info.dependencies == []

    def test_feature_info_with_dependencies(self):
        info = FeatureInfo("X", "desc", Edition.ENTERPRISE, dependencies=[Feature.MULTI_USER])
        assert info.dependencies == [Feature.MULTI_USER]

    def test_registry_has_all_features(self):
        assert set(FEATURE_REGISTRY) == set(Feature)


# ============================================================================
# _detect_edition
# ============================================================================

class TestDetectEdition:
    def test_env_enterprise(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "enterprise")
        assert PackageFeatureService().edition == Edition.ENTERPRISE

    def test_env_full(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "FULL")
        assert PackageFeatureService().edition == Edition.ENTERPRISE

    def test_env_personal(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "personal")
        assert PackageFeatureService().edition == Edition.PERSONAL

    def test_package_extras_postgresql(self, monkeypatch):
        dist = type("Dist", (), {"requires": ["requests", "psycopg2-binary>=2.9"]})
        monkeypatch.setattr(importlib.metadata, "distribution", lambda name: dist)
        assert PackageFeatureService().edition == Edition.ENTERPRISE

    def test_package_extras_without_postgresql(self, monkeypatch):
        dist = type("Dist", (), {"requires": ["requests"]})
        monkeypatch.setattr(importlib.metadata, "distribution", lambda name: dist)
        assert PackageFeatureService().edition == Edition.PERSONAL

    def test_package_not_found_falls_through(self, monkeypatch):
        def raise_not_found(name):
            raise importlib.metadata.PackageNotFoundError(name)
        monkeypatch.setattr(importlib.metadata, "distribution", raise_not_found)
        assert PackageFeatureService().edition == Edition.PERSONAL

    def test_distribution_raises_other(self, monkeypatch):
        def raise_other(name):
            raise RuntimeError("boom")
        monkeypatch.setattr(importlib.metadata, "distribution", raise_other)
        assert PackageFeatureService().edition == Edition.PERSONAL

    def test_db_url_postgresql(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db")
        assert PackageFeatureService().edition == Edition.ENTERPRISE

    def test_db_url_postgres(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgres://u:p@host/db")
        assert PackageFeatureService().edition == Edition.ENTERPRISE

    def test_db_url_sqlite_defaults_personal(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "sqlite:///./atom_dev.db")
        assert PackageFeatureService().edition == Edition.PERSONAL

    def test_default_personal(self):
        assert PackageFeatureService().edition == Edition.PERSONAL


# ============================================================================
# _build_feature_set
# ============================================================================

class TestBuildFeatureSet:
    def test_enterprise_has_all(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "enterprise")
        svc = PackageFeatureService()
        assert svc._available_features == set(Feature)

    def test_personal_has_only_personal(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "personal")
        svc = PackageFeatureService()
        expected = {f for f, info in FEATURE_REGISTRY.items() if info.edition == Edition.PERSONAL}
        assert svc._available_features == expected
        assert Feature.MULTI_USER not in expected


# ============================================================================
# Properties
# ============================================================================

class TestProperties:
    def test_edition_property(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "enterprise")
        assert PackageFeatureService().edition == Edition.ENTERPRISE

    def test_is_enterprise(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "enterprise")
        assert PackageFeatureService().is_enterprise is True
        assert PackageFeatureService().is_personal is False

    def test_is_personal(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "personal")
        assert PackageFeatureService().is_personal is True
        assert PackageFeatureService().is_enterprise is False


# ============================================================================
# is_feature_enabled
# ============================================================================

class TestIsFeatureEnabled:
    def test_personal_feature_enabled_in_personal(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "personal")
        svc = PackageFeatureService()
        assert svc.is_feature_enabled(Feature.CANVAS) is True
        assert svc.is_feature_enabled(Feature.LOCAL_AGENT) is True

    def test_enterprise_feature_disabled_in_personal(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "personal")
        svc = PackageFeatureService()
        assert svc.is_feature_enabled(Feature.MULTI_USER) is False
        assert svc.is_feature_enabled(Feature.SSO) is False

    def test_all_enabled_in_enterprise(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "enterprise")
        svc = PackageFeatureService()
        for feature in Feature:
            assert svc.is_feature_enabled(feature) is True

    def test_dependency_missing_in_personal(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "personal")
        svc = PackageFeatureService()
        assert svc.is_feature_enabled(Feature.WORKSPACE_ISOLATION) is False
        assert svc.is_feature_enabled(Feature.RBAC) is False

    def test_unknown_feature_false(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "personal")
        svc = PackageFeatureService()
        assert svc.is_feature_enabled("does_not_exist") is False


# ============================================================================
# Feature set accessors
# ============================================================================

class TestFeatureSets:
    def test_get_available_features_copy(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "enterprise")
        svc = PackageFeatureService()
        available = svc.get_available_features()
        assert available == set(Feature)
        available.add("junk")
        assert svc.get_available_features() != available

    def test_get_enterprise_features(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "personal")
        svc = PackageFeatureService()
        enterprise = svc.get_enterprise_features()
        assert Feature.MULTI_USER in enterprise
        assert Feature.LOCAL_AGENT not in enterprise
        assert all(FEATURE_REGISTRY[f].edition == Edition.ENTERPRISE for f in enterprise)

    def test_get_personal_features(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "enterprise")
        svc = PackageFeatureService()
        personal = svc.get_personal_features()
        assert Feature.LOCAL_AGENT in personal
        assert Feature.MULTI_USER not in personal
        assert all(FEATURE_REGISTRY[f].edition == Edition.PERSONAL for f in personal)


# ============================================================================
# require_feature / get_feature_info
# ============================================================================

class TestRequireFeature:
    def test_requires_available_feature_ok(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "enterprise")
        PackageFeatureService().require_feature(Feature.RBAC)

    def test_raises_for_enterprise_feature_in_personal(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "personal")
        with pytest.raises(PermissionError) as exc:
            PackageFeatureService().require_feature(Feature.MULTI_USER)
        assert "Multi-User" in str(exc.value)
        assert "atom enable enterprise" in str(exc.value)

    def test_raises_for_unknown_feature(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "personal")
        with pytest.raises(PermissionError) as exc:
            PackageFeatureService().require_feature("nope")
        assert "nope" in str(exc.value)

    def test_get_feature_info_present(self):
        info = PackageFeatureService().get_feature_info(Feature.CANVAS)
        assert info is not None
        assert info.name == "Canvas Presentations"

    def test_get_feature_info_absent(self):
        assert PackageFeatureService().get_feature_info("nope") is None


# ============================================================================
# list_features
# ============================================================================

class TestListFeatures:
    def test_structure_and_availability(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "personal")
        features = PackageFeatureService().list_features()
        by_id = {f["id"]: f for f in features}
        assert by_id["canvas"]["name"] == "Canvas Presentations"
        assert by_id["canvas"]["description"] == "Rich interactive presentations"
        assert by_id["canvas"]["available"] is True
        assert by_id["canvas"]["edition"] == "personal"
        assert by_id["multi_user"]["available"] is False
        assert by_id["multi_user"]["edition"] == "enterprise"

    def test_dependencies_values(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "enterprise")
        features = {f["id"]: f for f in PackageFeatureService().list_features()}
        assert features["bi_dashboard"]["dependencies"] == ["advanced_analytics"]
        assert features["sso"]["dependencies"] == ["multi_user"]
        assert features["canvas"]["dependencies"] == []

    def test_sorted_available_first_then_name(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "personal")
        features = PackageFeatureService().list_features()
        available = [f for f in features if f["available"]]
        unavailable = [f for f in features if not f["available"]]
        assert features == available + unavailable
        names = [f["name"] for f in available]
        assert names == sorted(names)

    def test_enterprise_all_available(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "enterprise")
        features = PackageFeatureService().list_features()
        assert all(f["available"] for f in features)
        assert len(features) == len(Feature)


# ============================================================================
# Module-level API
# ============================================================================

class TestModuleLevelApi:
    def test_get_service_singleton(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "personal")
        s1 = get_package_feature_service()
        s2 = get_package_feature_service()
        assert s1 is s2

    def test_is_enterprise_enabled_true(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "enterprise")
        assert is_enterprise_enabled() is True

    def test_is_enterprise_enabled_false(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "personal")
        assert is_enterprise_enabled() is False

    def test_module_is_feature_enabled(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "personal")
        assert is_feature_enabled(Feature.WORKFLOWS) is True
        assert is_feature_enabled(Feature.MULTI_USER) is False

    def test_require_enterprise_raises(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "personal")
        with pytest.raises(PermissionError, match="Enterprise Edition"):
            require_enterprise()

    def test_require_enterprise_passes(self, monkeypatch):
        monkeypatch.setenv("ATOM_EDITION", "enterprise")
        require_enterprise()
