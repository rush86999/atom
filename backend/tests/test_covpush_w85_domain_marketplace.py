# -*- coding: utf-8 -*-
"""Coverage wave 85 — core/domain_marketplace_service (never-wave-tested).

Covers the marketplace upstream client service:
- browse_domains: success passthrough (params forwarded) + SaaS failure -> error envelope.
- install_domain: template-not-found; success with/without custom_name (slug
  derivation, private flag, parent_domain_id, usage tracking, SaaS notify,
  commit); failure mid-install -> rollback + error dict (template fetch raise,
  install notify raise).
- uninstall_domain: success (delete + commit + message); not found (incl.
  public/foreign-tenant rows excluded); failure -> rollback + error dict.

Fully mocked SaaS client + usage tracker; real in-memory SQLite for the
SpecialistDomain rows (no network, zero LLM spend).
"""
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import SpecialistDomain  # noqa: F401 (register models)

import core.domain_marketplace_service as mdms
from core.domain_marketplace_service import DomainMarketplaceService


@pytest.fixture()
def db():
    """In-memory SQLite session with the full schema."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _make_domain(db, domain_id="dom-1", tenant_id="t1", name="CRM Pipeline",
                 slug="crm_pipeline_t1", parent="tmpl-1", is_public=False):
    domain = SpecialistDomain(
        id=domain_id,
        tenant_id=tenant_id,
        domain_name=name,
        domain_slug=slug,
        parent_domain_id=parent,
        description="desc",
        is_public=is_public,
    )
    db.add(domain)
    db.commit()
    return domain


class _Template:
    @staticmethod
    def fetch_domains_sync(*a, **k):
        return {"domains": [{"id": "1"}], "total": 1}

    @staticmethod
    def get_domain_template_sync(domain_id):
        return None

    @staticmethod
    def install_domain_sync(*a, **k):
        return {"ok": True}


class TestBrowseDomains:
    def test_success_passthrough(self, db):
        client = MagicMock()
        client.fetch_domains_sync.return_value = {"domains": [{"id": "d1"}], "total": 1}
        svc = DomainMarketplaceService(db, saas_client=client)
        result = svc.browse_domains(query="crm", category="sales", page=2, page_size=50)
        assert result == {"domains": [{"id": "d1"}], "total": 1}
        client.fetch_domains_sync.assert_called_once_with(
            query="crm", category="sales", page=2, page_size=50
        )

    def test_saas_failure_returns_error_envelope(self, db):
        client = MagicMock()
        client.fetch_domains_sync.side_effect = RuntimeError("saas down")
        svc = DomainMarketplaceService(db, saas_client=client)
        result = svc.browse_domains()
        assert result["domains"] == []
        assert result["total"] == 0
        assert result["error"] == "saas down"

    def test_default_constructor_builds_real_client(self, db):
        with patch.object(mdms, "AtomAgentOSMarketplaceClient") as client_cls:
            svc = DomainMarketplaceService(db)
            assert svc.saas_client is client_cls.return_value


class TestInstallDomain:
    def _svc(self, db, template=None, install_exc=None):
        client = MagicMock()
        client.get_domain_template_sync.return_value = template
        if install_exc is not None:
            client.install_domain_sync.side_effect = install_exc
        else:
            client.install_domain_sync.return_value = {"ok": True}
        svc = DomainMarketplaceService(db, saas_client=client)
        return svc, client

    def test_template_not_found(self, db):
        svc, client = self._svc(db, template=None)
        result = svc.install_domain("tmpl-missing", "t1")
        assert result == {"success": False, "error": "Domain template not found in marketplace"}
        assert db.query(SpecialistDomain).count() == 0
        client.install_domain_sync.assert_not_called()

    def test_success_default_name(self, db):
        svc, client = self._svc(db, template={
            "domain_name": "CRM Pipeline",
            "description": "Pipeline mgmt",
        })
        result = svc.install_domain("tmpl-1", "tenant-12345678")
        assert result["success"] is True
        assert result["domain_name"] == "CRM Pipeline"
        assert result["domain_id"]
        domain = db.query(SpecialistDomain).filter(SpecialistDomain.id == result["domain_id"]).first()
        assert domain.domain_slug == "crm_pipeline_tenant-1"
        assert domain.is_public is False
        assert domain.parent_domain_id == "tmpl-1"
        assert domain.description == "Pipeline mgmt"
        client.install_domain_sync.assert_called_once_with("tmpl-1", "tenant-12345678")

    def test_success_custom_name(self, db):
        svc, client = self._svc(db, template={
            "domain_name": "CRM Pipeline",
            "description": "Pipeline mgmt",
        })
        result = svc.install_domain("tmpl-1", "tenant-12345678", custom_name="Custom CRM")
        assert result["success"] is True
        assert result["domain_name"] == "Custom CRM"
        domain = db.query(SpecialistDomain).first()
        assert domain.domain_slug == "custom_crm_tenant-1"
        assert domain.domain_name == "Custom CRM"

    def test_success_tracks_usage_locally(self, db):
        svc, _ = self._svc(db, template={"domain_name": "CRM Pipeline"})
        with patch.object(mdms.MarketplaceUsageTracker, "track_usage") as track:
            svc.install_domain("tmpl-1", "t1")
        track.assert_called_once_with(item_type="domain", item_id="tmpl-1", success=True)

    def test_failure_notifies_saas_rolls_back(self, db):
        svc, client = self._svc(db, template={"domain_name": "CRM Pipeline"},
                                install_exc=RuntimeError("saas 500"))
        with patch.object(mdms.MarketplaceUsageTracker, "track_usage"):
            result = svc.install_domain("tmpl-1", "t1")
        assert result == {"success": False, "error": "saas 500"}
        assert db.query(SpecialistDomain).count() == 0

    def test_template_fetch_raise_rolls_back(self, db):
        client = MagicMock()
        client.get_domain_template_sync.side_effect = RuntimeError("saas down")
        svc = DomainMarketplaceService(db, saas_client=client)
        result = svc.install_domain("tmpl-1", "t1")
        assert result["success"] is False
        assert result["error"] == "saas down"
        assert db.query(SpecialistDomain).count() == 0


class TestUninstallDomain:
    def test_success(self, db):
        _make_domain(db)
        svc = DomainMarketplaceService(db, saas_client=MagicMock())
        result = svc.uninstall_domain("dom-1", "t1")
        assert result == {"success": True, "message": "Domain uninstalled successfully"}
        assert db.query(SpecialistDomain).count() == 0

    def test_not_found(self, db):
        svc = DomainMarketplaceService(db, saas_client=MagicMock())
        result = svc.uninstall_domain("dom-missing", "t1")
        assert result == {"success": False, "error": "Installed domain not found"}

    def test_public_domain_excluded(self, db):
        _make_domain(db, is_public=True)
        svc = DomainMarketplaceService(db, saas_client=MagicMock())
        result = svc.uninstall_domain("dom-1", "t1")
        assert result["success"] is False
        assert db.query(SpecialistDomain).count() == 1

    def test_other_tenant_excluded(self, db):
        _make_domain(db)
        svc = DomainMarketplaceService(db, saas_client=MagicMock())
        result = svc.uninstall_domain("dom-1", "other-tenant")
        assert result["success"] is False
        assert db.query(SpecialistDomain).count() == 1

    def test_error_rolls_back(self, db):
        _make_domain(db)
        svc = DomainMarketplaceService(db, saas_client=MagicMock())
        svc.db.commit = MagicMock(side_effect=RuntimeError("db down"))
        svc.db.rollback = MagicMock()
        result = svc.uninstall_domain("dom-1", "t1")
        assert result == {"success": False, "error": "db down"}
        assert svc.db.rollback.call_count >= 1
