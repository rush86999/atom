# -*- coding: utf-8 -*-
"""Round 80 — zero-coverage gap: core/entity_skill_service.py.

CRUD coverage for skill↔entity-type bindings with tenant isolation:
attach (global skill + tenant installation), detach, listing, permission
checks and the not-found / duplicate / inaccessible paths.
"""
import pytest

from core.entity_skill_service import EntitySkillService, get_entity_skill_service


@pytest.fixture()
def db(monkeypatch):
    """Function-scoped in-memory SQLite with only the needed tables, and
    SessionLocal patched so the service's get_db_session() hits it."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from core.database import Base
    from core.models import EntityTypeDefinition, Skill, SkillInstallation, Tenant

    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        bind=engine,
        tables=[Tenant.__table__, Skill.__table__, SkillInstallation.__table__,
                EntityTypeDefinition.__table__],
    )
    session_factory = sessionmaker(bind=engine)
    monkeypatch.setattr("core.database.SessionLocal", session_factory)
    session = session_factory()
    yield session
    session.close()
    engine.dispose()


def _tenant(session, tid="tenant-1"):
    from core.models import Tenant

    tenant = Tenant(id=tid, name="Acme", subdomain=f"acme-{tid}")
    session.add(tenant)
    return tenant


def _entity_type(session, eid="et-1", tid="tenant-1", slug="invoice", skills=None):
    from core.models import EntityTypeDefinition

    et = EntityTypeDefinition(
        id=eid, tenant_id=tid, slug=slug, display_name="Invoice",
        json_schema={"type": "object"}, available_skills=skills or [],
    )
    session.add(et)
    return et


def _skill(session, sid="skill-1", tenant_id=None):
    from core.models import Skill

    skill = Skill(id=sid, name=f"skill {sid}", type="api",
                  tenant_id=tenant_id, input_schema={}, config={})
    session.add(skill)
    return skill


def _installation(session, sid="skill-2", tid="tenant-1"):
    from core.models import SkillInstallation

    inst = SkillInstallation(id=f"inst-{sid}", tenant_id=tid, skill_id=sid,
                             installed_version="1.0.0")
    session.add(inst)
    return inst


class TestAttachSkill:
    def test_attach_global_skill(self, db):
        _tenant(db)
        et = _entity_type(db)
        _skill(db, "skill-1")
        db.commit()

        result = EntitySkillService().attach_skill("tenant-1", "et-1", "skill-1")
        assert "skill-1" in result.available_skills

    def test_attach_skill_via_tenant_installation(self, db):
        _tenant(db)
        et = _entity_type(db)
        _installation(db, "skill-2", "tenant-1")  # installed but no global Skill row
        db.commit()

        result = EntitySkillService().attach_skill("tenant-1", "et-1", "skill-2")
        assert "skill-2" in result.available_skills

    def test_attach_is_idempotent(self, db):
        _tenant(db)
        _entity_type(db, skills=["skill-1"])
        _skill(db, "skill-1")
        db.commit()

        result = EntitySkillService().attach_skill("tenant-1", "et-1", "skill-1")
        assert result.available_skills == ["skill-1"]

    def test_attach_unknown_entity_type_raises(self, db):
        _tenant(db)
        _skill(db, "skill-1")
        db.commit()

        with pytest.raises(ValueError, match="not found"):
            EntitySkillService().attach_skill("tenant-1", "et-ghost", "skill-1")

    def test_attach_unknown_skill_raises(self, db):
        _tenant(db)
        _entity_type(db)
        db.commit()

        with pytest.raises(ValueError, match="not found or not accessible"):
            EntitySkillService().attach_skill("tenant-1", "et-1", "skill-ghost")

    def test_attach_respects_tenant_isolation(self, db):
        _tenant(db, "tenant-1")
        _tenant(db, "tenant-2")
        _entity_type(db, eid="et-1", tid="tenant-1")
        _skill(db, "skill-1")
        db.commit()

        with pytest.raises(ValueError, match="not found"):
            EntitySkillService().attach_skill("tenant-2", "et-1", "skill-1")

    def test_attach_installation_isolation(self, db):
        """Tenant 2's installation of a skill must not make it attachable for
        tenant 1 when the global Skill row is missing."""
        _tenant(db, "tenant-1")
        _tenant(db, "tenant-2")
        _entity_type(db, eid="et-1", tid="tenant-1")
        _installation(db, "skill-2", "tenant-2")
        db.commit()

        with pytest.raises(ValueError, match="not found or not accessible"):
            EntitySkillService().attach_skill("tenant-1", "et-1", "skill-2")


class TestDetachSkill:
    def test_detach_removes_skill(self, db):
        _tenant(db)
        _entity_type(db, skills=["skill-1", "skill-2"])
        db.commit()

        result = EntitySkillService().detach_skill("tenant-1", "et-1", "skill-1")
        assert result.available_skills == ["skill-2"]

    def test_detach_non_attached_returns_unchanged(self, db):
        _tenant(db)
        _entity_type(db, skills=["skill-1"])
        db.commit()

        result = EntitySkillService().detach_skill("tenant-1", "et-1", "skill-9")
        assert result.available_skills == ["skill-1"]

    def test_detach_unknown_entity_type_raises(self, db):
        _tenant(db)
        db.commit()

        with pytest.raises(ValueError, match="not found"):
            EntitySkillService().detach_skill("tenant-1", "et-ghost", "skill-1")

    def test_detach_tenant_isolation(self, db):
        _tenant(db, "tenant-1")
        _tenant(db, "tenant-2")
        _entity_type(db, eid="et-1", tid="tenant-1", skills=["skill-1"])
        db.commit()

        with pytest.raises(ValueError, match="not found"):
            EntitySkillService().detach_skill("tenant-2", "et-1", "skill-1")


class TestGetEntitySkills:
    def test_lists_attached_skills(self, db):
        _tenant(db)
        _entity_type(db, skills=["skill-1", "skill-2"])
        _skill(db, "skill-1")
        _skill(db, "skill-2")
        db.commit()

        result = EntitySkillService().get_entity_skills("tenant-1", "et-1")
        assert {s["id"] for s in result} == {"skill-1", "skill-2"}
        assert all({"id", "name", "description", "type"} <= set(s) for s in result)

    def test_empty_when_no_skills_attached(self, db):
        _tenant(db)
        _entity_type(db, skills=[])
        db.commit()

        assert EntitySkillService().get_entity_skills("tenant-1", "et-1") == []

    def test_unknown_entity_type_raises(self, db):
        _tenant(db)
        db.commit()

        with pytest.raises(ValueError, match="not found"):
            EntitySkillService().get_entity_skills("tenant-1", "et-ghost")


class TestCheckSkillPermission:
    def test_allowed_when_attached(self, db):
        _tenant(db)
        _entity_type(db, slug="invoice", skills=["skill-1"])
        db.commit()

        result = EntitySkillService().check_skill_permission("tenant-1", "invoice", "skill-1")
        assert result == {"allowed": True, "reason": "Skill allowed"}

    def test_denied_when_not_attached(self, db):
        _tenant(db)
        _entity_type(db, slug="invoice", skills=["skill-1"])
        db.commit()

        result = EntitySkillService().check_skill_permission("tenant-1", "invoice", "skill-9")
        assert result["allowed"] is False
        assert result["reason"] == "Skill not attached"

    def test_denied_when_entity_type_unknown(self, db):
        _tenant(db)
        db.commit()

        result = EntitySkillService().check_skill_permission("tenant-1", "ghost", "skill-1")
        assert result == {"allowed": False, "reason": "Entity type not found"}


class TestServiceFactory:
    def test_factory_returns_singleton(self, monkeypatch):
        from core.entity_skill_service import _default_service

        monkeypatch.setattr("core.entity_skill_service._default_service", None)
        a = get_entity_skill_service()
        b = get_entity_skill_service()
        assert a is b
        assert isinstance(a, EntitySkillService)

    def test_factory_with_db_returns_new_instance(self, db):
        svc = get_entity_skill_service(db=db)
        assert svc.db is db
