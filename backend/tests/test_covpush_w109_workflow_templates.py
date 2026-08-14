# -*- coding: utf-8 -*-
"""Coverage wave 109 — core/workflow_template_system.py (untracked module,
63% baseline via legacy suites -> target 100%; temp-dir filesystem, no LLM,
no network).

W109-2 BUG (TDD RED->GREEN): `update_template` was defined TWICE — the
feature-rich first definition (dict->TemplateStep conversion, alias handling)
was silently shadowed by the second, so the LIVE version assigned raw dicts
to `template.steps`. `create_workflow_from_template` then crashed with
`KeyError: 'parameters'` while iterating dict steps. Fix: remove the dead
duplicate; the surviving method now converts dict steps (incl. "id" alias)
to TemplateStep objects. RED: test_update_with_dict_steps_then_generate.

Also covers every remaining uncovered line: create/update/delete/rate/export/
import CRUD, statistics, parameter validation (number/boolean/array/object
incl. JSON-decode errors), workflow-definition generation, index removal,
template-file load error paths, built-in load error path, model validators.
"""
import json
import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from core.workflow_template_system import (
    TemplateCategory,
    TemplateComplexity,
    TemplateParameter,
    TemplateStep,
    WorkflowTemplate,
    WorkflowTemplateManager,
)

SAMPLE_TEMPLATE = {
    "name": "Test ETL",
    "description": "A test pipeline",
    "category": "data_processing",
    "complexity": "intermediate",
    "tags": ["etl", "test"],
    "author": "tester",
    "inputs": [
        {"name": "source", "label": "Source", "type": "string", "required": True},
        {"name": "limit", "label": "Limit", "type": "number", "required": False, "default_value": 10},
        {"name": "flag", "label": "Flag", "type": "boolean", "required": False},
        {"name": "items", "label": "Items", "type": "array", "required": False},
        {"name": "cfg", "label": "Cfg", "type": "object", "required": False},
    ],
    "steps": [
        {"step_id": "extract", "name": "Extract", "estimated_duration": 30},
        {"step_id": "load", "name": "Load", "estimated_duration": 20, "depends_on": ["extract"]},
    ],
    "is_public": True,
}


@pytest.fixture
def manager(tmp_path):
    return WorkflowTemplateManager(template_dir=str(tmp_path / "templates"))


class TestModelValidators:
    def test_parameter_label_default(self):
        p = TemplateParameter(name="x", label="", description=None)
        assert p.label == "Parameter"
        assert p.description == "Parameter"

    def test_step_alias_id(self):
        step = TemplateStep(**{"id": "s1", "name": "N"})
        assert step.step_id == "s1"

    def test_step_dependency_validator_passthrough(self):
        step = TemplateStep(**{"id": "s1", "name": "N", "depends_on": ["a", "b"]})
        assert step.depends_on == ["a", "b"]

    def test_validate_step_connections_ok(self):
        tpl = WorkflowTemplate(**{
            "name": "N", "description": "D", "category": "automation",
            "complexity": "beginner",
            "steps": [{"id": "a", "name": "A"}, {"id": "b", "name": "B", "depends_on": ["a"]}],
        })
        assert len(tpl.steps) == 2

    def test_validate_step_connections_bad_dep(self):
        with pytest.raises(ValidationError):
            WorkflowTemplate(**{
                "name": "N", "description": "D", "category": "automation",
                "complexity": "beginner",
                "steps": [{"id": "a", "name": "A", "depends_on": ["ghost"]}],
            })

    def test_template_id_generated(self):
        tpl = WorkflowTemplate(name="N", description="D", category="automation", complexity="beginner")
        assert tpl.template_id.startswith("template_")

    def test_calculate_estimated_duration_mixed(self):
        tpl = WorkflowTemplate(name="N", description="D", category="automation", complexity="beginner",
                               steps=[TemplateStep(id="a", name="A", estimated_duration=10),
                                      {"id": "b", "name": "B"}])
        assert tpl.calculate_estimated_duration() == 70

    def test_add_usage(self):
        tpl = WorkflowTemplate(name="N", description="D", category="automation", complexity="beginner")
        tpl.add_usage()
        assert tpl.usage_count == 1

    def test_update_rating_first_and_subsequent(self):
        tpl = WorkflowTemplate(name="N", description="D", category="automation", complexity="beginner")
        tpl.update_rating(4.0)
        assert tpl.rating == 4.0
        assert tpl.review_count == 1
        tpl.update_rating(2.0)
        assert tpl.rating == 3.0
        assert tpl.review_count == 2


class TestCRUD:
    def test_create_template(self, manager):
        tpl = manager.create_template(dict(SAMPLE_TEMPLATE))
        assert tpl.template_id in manager.templates
        assert tpl.estimated_total_duration == 50
        assert tpl.template_id in manager.marketplace.templates
        assert tpl.template_id in manager.marketplace.categories["data_processing"]
        assert tpl.template_id in manager.marketplace.tags_index["etl"]
        assert manager.template_files[tpl.template_id].exists()

    def test_create_template_invalid_raises(self, manager):
        with pytest.raises(ValidationError):
            manager.create_template({"name": "N", "description": "D"})  # missing category/complexity

    def test_get_template(self, manager):
        tpl = manager.create_template(dict(SAMPLE_TEMPLATE))
        assert manager.get_template(tpl.template_id) is tpl
        assert manager.get_template("nope") is None

    def test_update_template_name_tags(self, manager):
        tpl = manager.create_template(dict(SAMPLE_TEMPLATE))
        updated = manager.update_template(tpl.template_id, {"name": "Renamed", "tags": ["x"]})
        assert updated.name == "Renamed"
        assert updated.tags == ["x"]
        assert "x" in manager.marketplace.tags_index

    def test_update_template_missing_raises(self, manager):
        with pytest.raises(ValueError):
            manager.update_template("nope", {"name": "X"})

    def test_update_with_dict_steps_then_generate(self, manager):
        """RED (W109-2): dict steps were assigned raw -> generate crashed
        with KeyError; now converted to TemplateStep objects."""
        tpl = manager.create_template(dict(SAMPLE_TEMPLATE))
        manager.update_template(tpl.template_id, {
            "steps": [
                {"id": "s1", "name": "One", "estimated_duration": 5},
                {"id": "s2", "name": "Two", "estimated_duration": 7, "depends_on": ["s1"]},
            ]
        })
        result = manager.create_workflow_from_template(tpl.template_id, "My Flow", {"source": "api"})
        assert result["workflow_definition"]["steps"][0]["step_id"] == "s1"
        assert result["workflow_definition"]["steps"][0]["timeout_seconds"] == 5

    def test_update_with_template_step_objects(self, manager):
        tpl = manager.create_template(dict(SAMPLE_TEMPLATE))
        steps = [TemplateStep(id="x", name="X", estimated_duration=3)]
        manager.update_template(tpl.template_id, {"steps": steps})
        assert tpl.steps[0].name == "X"

    def test_list_filters(self, manager):
        tpl = manager.create_template(dict(SAMPLE_TEMPLATE))
        assert manager.list_templates()  # non-empty
        assert manager.list_templates(category=TemplateCategory.AUTOMATION)  # built-ins
        by_cat = manager.list_templates(category=TemplateCategory.DATA_PROCESSING)
        assert tpl.template_id in [t.template_id for t in by_cat]
        assert manager.list_templates(complexity=TemplateComplexity.BEGINNER)  # built-ins
        by_comp = manager.list_templates(complexity=TemplateComplexity.INTERMEDIATE)
        assert tpl.template_id in [t.template_id for t in by_comp]
        by_tag = manager.list_templates(tags=["etl"])
        assert tpl.template_id in [t.template_id for t in by_tag]
        assert manager.list_templates(tags=["nope"]) == []
        by_author = manager.list_templates(author="tester")
        assert tpl.template_id in [t.template_id for t in by_author]
        assert manager.list_templates(author="other") == []
        by_public = manager.list_templates(is_public=True)
        assert tpl.template_id in [t.template_id for t in by_public]
        by_private = manager.list_templates(is_public=False)
        assert tpl.template_id not in [t.template_id for t in by_private]
        assert by_private  # some built-ins are private
        assert len(manager.list_templates(limit=1)) == 1

    def test_search_templates_ordering(self, manager):
        tpl = manager.create_template(dict(SAMPLE_TEMPLATE))
        by_name = manager.search_templates("test etl")  # exact name match first
        assert by_name[0].template_id == tpl.template_id
        by_desc = manager.search_templates("pipeline")
        assert by_desc  # partial match
        assert manager.search_templates("zzz-no-match") == []

    def test_create_workflow_from_template_success(self, manager):
        tpl = manager.create_template(dict(SAMPLE_TEMPLATE))
        before = tpl.usage_count
        result = manager.create_workflow_from_template(
            tpl.template_id, "Flow", {"source": "db", "limit": 5, "flag": "yes",
                                      "items": '["a","b"]', "cfg": '{"k": 1}'}
        )
        assert result["workflow_id"].startswith("workflow_")
        assert result["template_used"] == tpl.template_id
        assert result["parameters_applied"]["source"] == "db"
        assert result["parameters_applied"]["limit"] == 5.0
        assert result["parameters_applied"]["flag"] is True
        assert result["parameters_applied"]["items"] == ["a", "b"]
        assert result["parameters_applied"]["cfg"] == {"k": 1}
        assert tpl.usage_count == before + 1

    def test_create_workflow_from_template_missing(self, manager):
        with pytest.raises(ValueError):
            manager.create_workflow_from_template("nope", "Flow", {})

    def test_create_workflow_missing_required_param(self, manager):
        tpl = manager.create_template(dict(SAMPLE_TEMPLATE))
        with pytest.raises(ValueError):
            manager.create_workflow_from_template(tpl.template_id, "Flow", {})

    def test_create_workflow_bad_json_param(self, manager):
        tpl = manager.create_template(dict(SAMPLE_TEMPLATE))
        with pytest.raises(ValueError):
            manager.create_workflow_from_template(tpl.template_id, "Flow", {"source": "db", "items": "not-json"})

    def test_create_workflow_required_param_with_default(self, manager):
        data = dict(SAMPLE_TEMPLATE)
        data["inputs"] = [
            {"name": "mode", "label": "Mode", "type": "string", "required": True,
             "default_value": "safe"},
            {"name": "flag", "label": "Flag", "type": "boolean", "required": False},
        ]
        tpl = manager.create_template(data)
        result = manager.create_workflow_from_template(tpl.template_id, "Flow", {})
        assert result["parameters_applied"]["mode"] == "safe"
        # Boolean coercion of a non-string value (int 1 -> True).
        result2 = manager.create_workflow_from_template(
            tpl.template_id, "Flow", {"mode": "x", "flag": 1}
        )
        assert result2["parameters_applied"]["flag"] is True

    def test_load_templates_dir_removed_early_return(self, manager, tmp_path):
        import shutil
        shutil.rmtree(manager.template_dir)
        assert manager.load_templates() is None

    def test_create_workflow_default_filled(self, manager):
        tpl = manager.create_template(dict(SAMPLE_TEMPLATE))
        result = manager.create_workflow_from_template(tpl.template_id, "Flow", {"source": "db"})
        assert result["parameters_applied"]["limit"] == 10.0
        assert result["parameters_applied"]["flag"] is None
        assert result["parameters_applied"]["items"] is None
        assert result["workflow_definition"]["name"] == "Flow"
        assert result["workflow_definition"]["user_inputs"]["source"] == "db"
        assert result["workflow_definition"]["customizations"] == {}
        assert result["workflow_definition"]["steps"][0]["depends_on"] == []
        assert result["workflow_definition"]["steps"][1]["depends_on"] == ["extract"]

    def test_create_workflow_with_customizations(self, manager):
        tpl = manager.create_template(dict(SAMPLE_TEMPLATE))
        result = manager.create_workflow_from_template(
            tpl.template_id, "Flow", {"source": "db"}, {"steps": [1]}
        )
        assert result["workflow_definition"]["customizations"] == {"steps": [1]}

    def test_delete_template(self, manager):
        tpl = manager.create_template(dict(SAMPLE_TEMPLATE))
        tpl_file = manager.template_files[tpl.template_id]
        assert manager.delete_template(tpl.template_id) is True
        assert tpl.template_id not in manager.templates
        assert tpl.template_id not in manager.marketplace.templates
        assert not tpl_file.exists()
        assert tpl.template_id not in manager.template_files
        assert manager.delete_template(tpl.template_id) is False

    def test_delete_template_index_cleanup(self, manager):
        tpl = manager.create_template(dict(SAMPLE_TEMPLATE))
        manager.delete_template(tpl.template_id)
        assert tpl.template_id not in manager.marketplace.categories["data_processing"]
        assert tpl.template_id not in manager.marketplace.tags_index["etl"]

    def test_rate_template(self, manager):
        tpl = manager.create_template(dict(SAMPLE_TEMPLATE))
        assert manager.rate_template(tpl.template_id, 4.5) is True
        assert tpl.rating == 4.5
        assert tpl.review_count == 1
        assert manager.rate_template("nope", 3.0) is False
        with pytest.raises(ValueError):
            manager.rate_template(tpl.template_id, 5.5)

    def test_export_template(self, manager):
        tpl = manager.create_template(dict(SAMPLE_TEMPLATE))
        exported = manager.export_template(tpl.template_id)
        assert exported["template_id"] == tpl.template_id
        assert exported["name"] == "Test ETL"
        with pytest.raises(ValueError):
            manager.export_template("nope")

    def test_import_template_new(self, manager):
        data = dict(SAMPLE_TEMPLATE)
        data["template_id"] = "imported_tpl"
        tpl = manager.import_template(data)
        assert tpl.template_id == "imported_tpl"

    def test_import_template_no_overwrite(self, manager):
        data = dict(SAMPLE_TEMPLATE)
        data["template_id"] = "imported_tpl"
        manager.import_template(data)
        with pytest.raises(ValueError):
            manager.import_template(dict(data))

    def test_import_template_overwrite_new_id(self, manager):
        data = dict(SAMPLE_TEMPLATE)
        data["template_id"] = "imported_tpl"
        manager.import_template(data)
        tpl2 = manager.import_template(dict(data), overwrite=True)
        assert tpl2.template_id != "imported_tpl"
        assert tpl2.template_id in manager.templates

    def test_template_statistics(self, manager):
        tpl = manager.create_template(dict(SAMPLE_TEMPLATE))
        tpl.add_usage()
        tpl.update_rating(5.0)
        stats = manager.get_template_statistics()
        assert stats["total_templates"] > 0
        assert stats["total_usage"] > 0
        assert stats["average_rating"] > 0
        assert stats["category_breakdown"]["data_processing"]["count"] >= 1
        assert stats["most_used_templates"][0].template_id == tpl.template_id
        assert stats["highest_rated_templates"][0].template_id == tpl.template_id


class TestPersistenceAndErrors:
    def test_load_templates_from_dir(self, tmp_path):
        d = tmp_path / "templates"
        m1 = WorkflowTemplateManager(template_dir=str(d))
        tpl = m1.create_template(dict(SAMPLE_TEMPLATE))
        m2 = WorkflowTemplateManager(template_dir=str(d))
        assert tpl.template_id in m2.templates

    def test_load_templates_missing_dir(self, tmp_path):
        m = WorkflowTemplateManager(template_dir=str(tmp_path / "missing" / "deep"))
        assert m.load_templates() is None  # early return

    def test_load_templates_corrupt_json_logs_and_skips(self, tmp_path):
        d = tmp_path / "templates"
        m1 = WorkflowTemplateManager(template_dir=str(d))
        tpl = m1.create_template(dict(SAMPLE_TEMPLATE))
        (d / "corrupt.json").write_text("{ not json")
        m2 = WorkflowTemplateManager(template_dir=str(d))
        assert m2.templates.get("corrupt") is None
        assert tpl.template_id in m2.templates

    def test_load_templates_invalid_schema_skipped(self, tmp_path):
        d = tmp_path / "templates"
        d.mkdir(parents=True, exist_ok=True)
        (d / "bad.json").write_text(json.dumps({"template_id": "bad1", "name": "x"}))
        m = WorkflowTemplateManager(template_dir=str(d))
        assert "bad1" not in m.templates

    def test_load_built_in_error_path(self, tmp_path, monkeypatch):
        import core.workflow_template_system as wts
        def boom(*args, **kwargs):
            raise ValueError("template source broke")
        monkeypatch.setattr(wts.WorkflowTemplateManager, "_create_data_processing_template", boom)
        m = WorkflowTemplateManager(template_dir=str(tmp_path / "t"))
        # Other built-ins still loaded; the broken one just logged.
        assert m.templates
