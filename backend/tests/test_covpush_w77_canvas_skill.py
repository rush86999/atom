"""Coverage wave 77 — core/canvas_skill_integration.py (0% -> 100%).

CanvasSkillIntegrationService: component<->skill pairing, marketplace
install with auto skill creation. Fully mocked DB (no real DB, no network).
"""
from unittest.mock import MagicMock

import pytest

from core.canvas_skill_integration import CanvasSkillIntegrationService
from core.models import CanvasComponent, ComponentInstallation, Skill, SkillVersion


def _fake_flush(db):
    """Mimic SQLAlchemy: apply PK defaults on flush() for pending objects."""
    def flush():
        for call in db.add.call_args_list:
            obj = call.args[0]
            if isinstance(obj, (Skill, SkillVersion, CanvasComponent, ComponentInstallation)) and not obj.id:
                obj.id = f"gen-{len(db.add.call_args_list)}-{obj.__class__.__name__}"
    db.flush.side_effect = flush


def _component(**overrides):
    defaults = {
        "id": "comp-1",
        "tenant_id": "t-src",
        "author_id": "u-author",
        "name": "Chart Widget",
        "description": "A chart",
        "category": "chart",
        "component_type": "html",
        "code": "<div/>",
        "config_schema": {},
        "tags": ["chart"],
        "dependencies": [],
        "version": "1.2.0",
        "is_public": True,
        "is_approved": True,
        "required_skill_id": None,
        "skill_version": None,
        "auto_install_skill": True,
    }
    defaults.update(overrides)
    return CanvasComponent(**defaults)


def _source_skill(**overrides):
    defaults = {
        "id": "skill-src",
        "tenant_id": "t-src",
        "author_tenant_id": "t-src",
        "name": "Data Fetch",
        "description": "Fetch data",
        "version": "1.0.0",
        "type": "api",
        "input_schema": {},
        "output_schema": {},
        "config": {},
        "code": "def run(): pass",
        "is_public": False,
        "is_approved": False,
    }
    defaults.update(overrides)
    return Skill(**defaults)


class TestCreateComponentWithSkill:
    @pytest.mark.asyncio
    async def test_creates_skill_then_component(self):
        db = MagicMock()
        _fake_flush(db)
        service = CanvasSkillIntegrationService(db)
        skill_data = {
            "name": "Data Fetch", "type": "api",
            "description": "Fetch", "input_schema": {"x": 1},
            "code": "pass", "version": "2.0.0",
        }
        component_data = {
            "name": "Chart", "category": "chart", "component_type": "html",
            "code": "<div/>", "auto_install_skill": False,
        }
        db.flush.side_effect = None
        result = await service.create_component_with_skill("t-1", "a-1", "u-1",
                                                           component_data, skill_data)
        assert result["status"] == "created"
        assert result["skill_name"] == "Data Fetch"
        added = [c.args[0] for c in db.add.call_args_list]
        assert any(isinstance(x, Skill) and x.name == "Data Fetch" for x in added)
        assert any(isinstance(x, SkillVersion) for x in added)
        component = [x for x in added if isinstance(x, CanvasComponent)][0]
        assert component.required_skill_id == result["skill_id"]
        assert component.auto_install_skill is False
        assert component.is_public is False
        assert component.is_approved is False
        db.commit.assert_called_once()
        db.refresh.assert_called()

    @pytest.mark.asyncio
    async def test_error_rolls_back_and_raises(self):
        db = MagicMock()
        db.add.side_effect = RuntimeError("constraint")
        service = CanvasSkillIntegrationService(db)
        with pytest.raises(RuntimeError, match="constraint"):
            await service.create_component_with_skill(
                "t-1", "a-1", "u-1",
                {"name": "C", "category": "chart", "component_type": "html", "code": "x"},
                {"name": "S", "type": "api"},
            )
        db.rollback.assert_called_once()


class TestInstallComponentToTenant:
    def _install_service(self, db, source_component, source_skill=None, existing_skill=None):
        db.query.return_value.filter.return_value.first.side_effect = [
            source_component,  # component lookup
            source_skill,      # skill lookup
            existing_skill,    # tenant skill lookup
        ]
        return CanvasSkillIntegrationService(db)

    @pytest.mark.asyncio
    async def test_component_not_available(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        service = CanvasSkillIntegrationService(db)
        with pytest.raises(ValueError, match="not found or not available"):
            await service.install_component_to_tenant("t-1", "u-1", "comp-x")

    @pytest.mark.asyncio
    async def test_installs_without_skill(self):
        db = MagicMock()
        comp = _component()  # no required_skill_id
        service = self._install_service(db, comp)
        result = await service.install_component_to_tenant("t-1", "u-1", "comp-1")
        assert result["status"] == "installed"
        assert result["skill_id"] is None
        added = [c.args[0] for c in db.add.call_args_list]
        assert any(isinstance(x, CanvasComponent) and x.tenant_id == "t-1" for x in added)

    @pytest.mark.asyncio
    async def test_required_skill_missing_raises(self):
        db = MagicMock()
        comp = _component(required_skill_id="skill-gone", auto_install_skill=True)
        service = self._install_service(db, comp, source_skill=None)
        with pytest.raises(ValueError, match="skill not found"):
            await service.install_component_to_tenant("t-1", "u-1", "comp-1")

    @pytest.mark.asyncio
    async def test_installs_skill_and_component_with_canvas(self):
        db = MagicMock()
        _fake_flush(db)
        comp = _component(required_skill_id="skill-src")
        src_skill = _source_skill()
        service = self._install_service(db, comp, source_skill=src_skill, existing_skill=None)
        result = await service.install_component_to_tenant(
            "t-1", "u-1", "comp-1", canvas_id="canvas-9", config={"theme": "dark"})
        assert result["status"] == "installed"
        assert result["skill_id"]
        added = [c.args[0] for c in db.add.call_args_list]
        installed_skill = [x for x in added if isinstance(x, Skill) and x.tenant_id == "t-1"][0]
        assert installed_skill.name == "Data Fetch"
        assert installed_skill.author_tenant_id == "t-src"
        assert any(isinstance(x, SkillVersion) for x in added)
        versions = [x for x in added if isinstance(x, SkillVersion)]
        assert versions[0].changelog == "Installed from component Chart Widget"
        new_component = [x for x in added if isinstance(x, CanvasComponent)][-1]
        assert new_component.required_skill_id == result["skill_id"]
        assert new_component.is_public is False
        from core.models import ComponentInstallation
        installations = [x for x in added if isinstance(x, ComponentInstallation)]
        assert len(installations) == 1
        assert installations[0].canvas_id == "canvas-9"
        assert installations[0].config == {"theme": "dark"}
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_reuses_existing_tenant_skill(self):
        db = MagicMock()
        comp = _component(required_skill_id="skill-src")
        src_skill = _source_skill()
        existing = _source_skill(id="skill-local", tenant_id="t-1")
        service = self._install_service(db, comp, source_skill=src_skill, existing_skill=existing)
        result = await service.install_component_to_tenant("t-1", "u-1", "comp-1")
        assert result["skill_id"] == "skill-local"
        # no new Skill rows created for the reuse path
        from core.models import Skill
        assert not any(
            isinstance(c.args[0], Skill) and c.args[0].tenant_id == "t-1"
            for c in db.add.call_args_list
        )

    @pytest.mark.asyncio
    async def test_error_rolls_back_and_raises(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            _component(required_skill_id="skill-src"), _source_skill(), None,
        ]
        db.flush.side_effect = RuntimeError("flush fail")
        service = CanvasSkillIntegrationService(db)
        with pytest.raises(RuntimeError, match="flush fail"):
            await service.install_component_to_tenant("t-1", "u-1", "comp-1")
        db.rollback.assert_called_once()
