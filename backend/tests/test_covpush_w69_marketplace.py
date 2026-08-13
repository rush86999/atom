# -*- coding: utf-8 -*-
"""Coverage wave 69 — core/workflow_marketplace (standalone, fully mocked,
zero LLM spend, no network, no real DB).

- Engine init: default/advanced/industry template materialization incl. the
  already-exists skip branch; dir scaffolding.
- list_templates: no-filter, category, template_type, tags filters; SaaS
  merge with dedup against local ids; SaaS exception tolerance.
- _load_legacy/_load_advanced/_load_industry templates: conversion to
  WorkflowTemplate (nodes/edges from steps, depends_on edges, industry
  passthrough), direct fallback, category/industry filters, corrupt-file
  tolerance.
- get_template: legacy/advanced/industry hit with download-count increment,
  corrupt legacy falls through, SaaS fallback (usage tracked), SaaS None and
  exception paths.
- import_workflow / export_workflow validation (missing nodes/edges → ValueError).
- create_advanced_template: duration summation, defaults, generated id,
  no-steps variant. create_workflow_from_advanced_template success + not-found.
- Router endpoints via TestClient with a patched module-level marketplace:
  templates list/types/featured (sort+limit), details 200/404,
  import 200/404/500 (404 must not degrade to 500), advanced create
  200/400, create-workflow 200/404/400, /import file upload
  (valid/JSONDecodeError/ValueError/500), /export (success/400/500),
  statistics (empty + populated aggregations).
"""
import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import core.workflow_marketplace as wm
from core.workflow_marketplace import (
    AdvancedWorkflowTemplate,
    MarketplaceEngine,
    TemplateType,
    WorkflowTemplate,
)


# ============================================================================
# Helpers / fixtures
# ============================================================================

def _legacy(id, category="Productivity", **over):
    data = {
        "id": id,
        "name": f"{id} name",
        "description": "desc",
        "category": category,
        "author": "a",
        "version": "1.0.0",
        "integrations": ["gmail"],
        "complexity": "Beginner",
        "workflow_data": {"nodes": [], "edges": []},
        "created_at": "2026-01-01T00:00:00",
        "tags": ["tag1"],
        "estimated_duration": 60,
    }
    data.update(over)
    return data


def _advanced(id, category="Data Processing", industry=None, with_steps=True):
    data = {
        "id": id,
        "name": f"{id} name",
        "description": "desc",
        "category": category,
        "author": "a",
        "version": "2.0.0",
        "integrations": ["api"],
        "complexity": "Advanced",
        "tags": ["etl"],
        "input_schema": [{"name": "x", "type": "string", "label": "X"}],
        "steps": [
            {"step_id": "s1", "name": "S1", "step_type": "t", "estimated_duration": 30},
            {"step_id": "s2", "name": "S2", "step_type": "t", "estimated_duration": 60, "depends_on": ["s1"]},
        ],
        "estimated_duration": 90,
        "prerequisites": ["p1"],
        "use_cases": ["uc"],
        "benefits": ["b1"],
        "downloads": 0,
        "rating": 5.0,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    }
    if not with_steps:
        data.pop("input_schema")
        data.pop("steps")
    if industry:
        data["industry"] = industry
    return data


def _saas_workflow(id, category="Sales"):
    return {
        "id": id,
        "name": "SaaS workflow",
        "description": "from saas",
        "category": category,
        "author": "saas",
        "version": "1.0.0",
        "integrations": [],
        "complexity": "Beginner",
        "workflow_data": {"nodes": [], "edges": []},
        "created_at": "2026-01-01T00:00:00",
        "template_type": "advanced",
        "tags": ["saas"],
    }


@pytest.fixture
def engine(tmp_path):
    saas = MagicMock()
    saas.get_workflow_template_sync.return_value = None
    saas.fetch_workflows_sync.return_value = {"workflows": []}
    eng = MarketplaceEngine(saas_client=saas)
    eng.templates_dir = str(tmp_path / "templates")
    eng.advanced_templates_dir = str(tmp_path / "templates" / "advanced")
    eng.industry_templates_dir = str(tmp_path / "templates" / "industry")
    os.makedirs(eng.templates_dir, exist_ok=True)
    os.makedirs(eng.advanced_templates_dir, exist_ok=True)
    os.makedirs(eng.industry_templates_dir, exist_ok=True)
    eng._initialize_default_templates()
    eng._initialize_advanced_templates()
    eng._initialize_industry_templates()
    return eng


@pytest.fixture
def client(monkeypatch):
    fake = MagicMock()
    monkeypatch.setattr(wm, "marketplace", fake)
    app = FastAPI()
    app.include_router(wm.router)
    return TestClient(app), fake


def _write(directory, filename, payload):
    path = os.path.join(directory, filename)
    with open(path, "w") as f:
        json.dump(payload, f)
    return path


# ============================================================================
# Engine construction / template initialization
# ============================================================================

class TestEngineInit:
    def test_default_templates_materialized(self, engine):
        legacy_ids = {t.id for t in engine._load_legacy_templates()}
        assert {"tmpl_email_summarizer", "tmpl_lead_enrichment", "tmpl_followup_tasks"} <= legacy_ids

    def test_advanced_templates_materialized(self, engine):
        adv_ids = {t.id for t in engine._load_advanced_templates()}
        assert {"advanced_etl_pipeline", "advanced_approval_workflow"} <= adv_ids

    def test_industry_templates_materialized(self, engine):
        ind = engine._load_industry_templates()
        assert [t.id for t in ind] == ["healthcare_patient_onboarding"]
        assert ind[0].industry == "healthcare"
        assert ind[0].template_type == TemplateType.INDUSTRY

    def test_init_skips_existing_templates(self, engine, tmp_path):
        marker = os.path.join(engine.templates_dir, "tmpl_email_summarizer.json")
        data = json.load(open(marker))
        data["rating"] = 1.0
        with open(marker, "w") as f:
            json.dump(data, f)
        engine._initialize_default_templates()
        assert json.load(open(marker))["rating"] == 1.0

    def test_init_creates_directory_scaffolding(self, tmp_path):
        saas = MagicMock()
        with patch.object(
            wm.MarketplaceEngine,
            "_initialize_default_templates",
            lambda self: None,
        ), patch.object(
            wm.MarketplaceEngine,
            "_initialize_advanced_templates",
            lambda self: None,
        ), patch.object(
            wm.MarketplaceEngine,
            "_initialize_industry_templates",
            lambda self: None,
        ), patch.object(
            wm.os.path,
            "dirname",
            lambda p: str(tmp_path / "fake_pkg"),
        ):
            eng = MarketplaceEngine(saas_client=saas)
            assert os.path.isdir(eng.templates_dir)
            assert os.path.isdir(eng.advanced_templates_dir)
            assert os.path.isdir(eng.industry_templates_dir)


# ============================================================================
# list_templates + loaders
# ============================================================================

class TestListTemplates:
    def test_lists_all_local_types(self, engine):
        result = engine.list_templates()
        assert len(result) == 6
        assert {t.template_type for t in result} == {
            TemplateType.LEGACY,
            TemplateType.ADVANCED,
            TemplateType.INDUSTRY,
        }

    def test_category_filter(self, engine):
        result = engine.list_templates(category="Sales")
        assert [t.id for t in result] == ["tmpl_lead_enrichment"]

    def test_template_type_filter(self, engine):
        result = engine.list_templates(template_type=TemplateType.INDUSTRY)
        assert [t.id for t in result] == ["healthcare_patient_onboarding"]

    def test_tags_filter(self, engine):
        result = engine.list_templates(tags=["etl"])
        assert result and all("etl" in t.tags for t in result)

    def test_saas_merge_dedup(self, engine):
        engine.saas_client.fetch_workflows_sync.return_value = {
            "workflows": [
                _saas_workflow("saas_new_1"),
                _saas_workflow("tmpl_email_summarizer"),
            ]
        }
        result = engine.list_templates()
        ids = [t.id for t in result]
        assert "saas_new_1" in ids
        assert ids.count("tmpl_email_summarizer") == 1

    def test_saas_exception_tolerated(self, engine):
        engine.saas_client.fetch_workflows_sync.side_effect = RuntimeError("boom")
        result = engine.list_templates()
        assert len(result) == 6

    def test_legacy_loader_tolerates_corrupt_and_non_json(self, engine, tmp_path):
        bad = tmp_path / "templates"
        with open(os.path.join(bad, "broken.json"), "w") as f:
            f.write("{not json")
        with open(os.path.join(bad, "notes.txt"), "w") as f:
            f.write("hello")
        result = engine._load_legacy_templates()
        assert len(result) == 3

    def test_legacy_loader_category_filter(self, engine):
        assert engine._load_legacy_templates(category="Nope") == []

    def test_advanced_loader_conversion_and_filters(self, engine, tmp_path):
        _write(engine.advanced_templates_dir, "custom_adv.json", _advanced("custom_adv"))
        loaded = engine._load_advanced_templates()
        custom = [t for t in loaded if t.id == "custom_adv"][0]
        assert custom.template_type == TemplateType.ADVANCED
        assert len(custom.workflow_data["nodes"]) == 2
        assert {"source": "s1", "target": "s2"} in custom.workflow_data["edges"]
        assert custom.estimated_duration == 90
        assert custom.prerequisites == ["p1"]

    def test_advanced_loader_fallback_direct(self, engine, tmp_path):
        legacy_shaped = _legacy("adv_fallback", category="Data Processing")
        legacy_shaped["tags"] = ["etl"]
        legacy_shaped["template_type"] = "advanced"
        _write(engine.advanced_templates_dir, "adv_fallback.json", legacy_shaped)
        loaded = engine._load_advanced_templates()
        fb = [t for t in loaded if t.id == "adv_fallback"][0]
        assert fb.template_type == TemplateType.ADVANCED

    def test_advanced_loader_category_filter(self, engine):
        assert engine._load_advanced_templates(category="Nope") == []

    def test_advanced_loader_corrupt_tolerated(self, engine, tmp_path):
        with open(os.path.join(engine.advanced_templates_dir, "corrupt_adv.json"), "w") as f:
            f.write("{oops")
        assert engine._load_advanced_templates()  # no raise

    def test_industry_loader_conversion_and_filters(self, engine, tmp_path):
        _write(
            engine.industry_templates_dir,
            "custom_ind.json",
            _advanced("custom_ind", category="Finance", industry="finance"),
        )
        loaded = engine._load_industry_templates()
        custom = [t for t in loaded if t.id == "custom_ind"][0]
        assert custom.industry == "finance"
        assert custom.template_type == TemplateType.INDUSTRY
        assert [t for t in loaded if t.id == "custom_ind" and t.industry == "other"] == []
        assert engine._load_industry_templates(category="Nope") == []
        assert engine._load_industry_templates(industry="finance") == [custom]
        assert engine._load_industry_templates(industry="other") == []

    def test_industry_loader_fallback_and_corrupt(self, engine, tmp_path):
        legacy_shaped = _legacy("ind_fallback", category="Retail")
        legacy_shaped["industry"] = "retail"
        legacy_shaped["template_type"] = "industry"
        _write(
            engine.industry_templates_dir,
            "ind_fallback.json",
            legacy_shaped,
        )
        with open(os.path.join(engine.industry_templates_dir, "corrupt_ind.json"), "w") as f:
            f.write("{broken")
        loaded = engine._load_industry_templates()
        fb = [t for t in loaded if t.id == "ind_fallback"][0]
        assert fb.template_type == TemplateType.INDUSTRY
        assert fb.industry == "retail"


# ============================================================================
# get_template
# ============================================================================

class TestGetTemplate:
    def test_legacy_hit_increments_downloads(self, engine):
        tmpl = engine.get_template("tmpl_email_summarizer")
        assert tmpl.id == "tmpl_email_summarizer"
        assert tmpl.template_type == TemplateType.LEGACY
        saved = json.load(open(os.path.join(engine.templates_dir, "tmpl_email_summarizer.json")))
        assert saved["downloads"] == 1

    def test_corrupt_legacy_falls_through_to_advanced(self, engine, tmp_path):
        with open(os.path.join(engine.templates_dir, "bad_legacy.json"), "w") as f:
            f.write("{nope")
        _write(engine.advanced_templates_dir, "advanced_etl_pipeline.json",
               _advanced("advanced_etl_pipeline"))
        tmpl = engine.get_template("bad_legacy")
        assert tmpl is None  # corrupt legacy ignored, advanced dir has no bad_legacy
        adv = engine.get_template("advanced_etl_pipeline")
        assert adv.template_type == TemplateType.ADVANCED

    def test_industry_hit(self, engine):
        tmpl = engine.get_template("healthcare_patient_onboarding")
        assert tmpl.template_type == TemplateType.INDUSTRY

    def test_get_template_advanced_fallback_direct(self, engine, tmp_path):
        legacy_shaped = _legacy("adv_direct", category="Data Processing", downloads=2)
        _write(engine.advanced_templates_dir, "adv_direct.json", legacy_shaped)
        tmpl = engine.get_template("adv_direct")
        assert tmpl.template_type == TemplateType.ADVANCED
        assert tmpl.downloads == 3

    def test_get_template_industry_fallback_direct(self, engine, tmp_path):
        legacy_shaped = _legacy("ind_direct", category="Retail", downloads=0)
        legacy_shaped["industry"] = "retail"
        _write(engine.industry_templates_dir, "ind_direct.json", legacy_shaped)
        tmpl = engine.get_template("ind_direct")
        assert tmpl.template_type == TemplateType.INDUSTRY
        assert tmpl.industry == "retail"

    def test_get_template_corrupt_advanced_and_industry(self, engine, tmp_path):
        with open(os.path.join(engine.advanced_templates_dir, "bad_adv.json"), "w") as f:
            f.write("{oops")
        with open(os.path.join(engine.industry_templates_dir, "bad_ind.json"), "w") as f:
            f.write("{oops")
        assert engine.get_template("bad_adv") is None
        assert engine.get_template("bad_ind") is None

    def test_saas_fallback_hit(self, engine):
        engine.saas_client.get_workflow_template_sync.return_value = _saas_workflow("remote_1")
        with patch("core.workflow_marketplace.MarketplaceUsageTracker.track_usage") as track:
            tmpl = engine.get_template("remote_1")
        assert tmpl.id == "remote_1"
        track.assert_called_once_with(item_type="workflow", item_id="remote_1", success=True)

    def test_saas_returns_none(self, engine):
        engine.saas_client.get_workflow_template_sync.return_value = None
        assert engine.get_template("missing_1") is None

    def test_saas_raises(self, engine):
        engine.saas_client.get_workflow_template_sync.side_effect = RuntimeError("down")
        assert engine.get_template("missing_1") is None


# ============================================================================
# import / export / advanced creation
# ============================================================================

class TestWorkflowImportExport:
    def test_import_workflow_valid(self):
        eng = MarketplaceEngine(saas_client=MagicMock())
        result = eng.import_workflow(
            {"name": "My Flow", "nodes": [{"id": "1"}], "edges": []}
        )
        assert result["name"] == "Imported: My Flow"
        assert result["nodes"] == [{"id": "1"}]

    def test_import_workflow_missing_structure(self):
        eng = MarketplaceEngine(saas_client=MagicMock())
        with pytest.raises(ValueError, match="nodes or edges"):
            eng.import_workflow({"nodes": []})

    def test_export_workflow_valid(self):
        eng = MarketplaceEngine(saas_client=MagicMock())
        result = eng.export_workflow(
            {"name": "Flow", "description": "d", "nodes": [{"id": "1"}], "edges": []}
        )
        assert result["name"] == "Flow"
        assert result["metadata"]["version"] == "1.0.0"
        assert "exported_at" in result["metadata"]

    def test_export_workflow_missing_structure(self):
        eng = MarketplaceEngine(saas_client=MagicMock())
        with pytest.raises(ValueError, match="nodes or edges"):
            eng.export_workflow({"name": "x"})


class TestAdvancedTemplateCreation:
    def test_create_advanced_template_with_steps(self, engine):
        data = _advanced("new_adv_1")
        result = engine.create_advanced_template(data)
        assert isinstance(result, AdvancedWorkflowTemplate)
        assert result.id == "new_adv_1"
        assert result.estimated_duration == 90
        assert result.multi_input_support is True
        assert result.downloads == 0
        assert result.rating == 5.0
        assert os.path.exists(os.path.join(engine.advanced_templates_dir, "new_adv_1.json"))

    def test_create_advanced_template_generated_id_no_steps(self, engine):
        data = {
            "name": "n", "description": "d", "category": "c", "author": "a",
            "version": "1.0", "integrations": [], "complexity": "Beginner",
            "input_schema": [], "steps": [],
        }
        result = engine.create_advanced_template(data)
        assert result.id.startswith("advanced_")
        assert result.estimated_duration == 0

    def test_create_workflow_from_advanced_template(self, engine):
        workflow = engine.create_workflow_from_advanced_template(
            "advanced_etl_pipeline", "My ETL", {"data_source_type": "database"}
        )
        assert workflow["name"] == "My ETL"
        assert workflow["created_from_advanced_template"] is True
        assert workflow["user_inputs"] == {"data_source_type": "database"}
        assert workflow["estimated_duration"] == 690
        saved = json.load(open(os.path.join(engine.advanced_templates_dir, "advanced_etl_pipeline.json")))
        assert saved["downloads"] == 1

    def test_create_workflow_missing_template(self, engine):
        with pytest.raises(ValueError, match="not found"):
            engine.create_workflow_from_advanced_template("nope_1", "w", {})


# ============================================================================
# Router endpoints
# ============================================================================

class TestMarketplaceRouter:
    def test_get_templates_passthrough(self, client):
        _, fake = client
        fake.list_templates.return_value = [WorkflowTemplate(**_legacy("tmpl_x"))]
        resp = client[0].get("/api/marketplace/templates?category=Sales&tags=saas")
        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["id"] == "tmpl_x"
        assert fake.list_templates.called

    def test_get_template_types(self, client):
        resp = client[0].get("/api/marketplace/templates/types")
        assert resp.status_code == 200
        types = resp.json()["template_types"]
        assert [t["value"] for t in types] == ["legacy", "advanced", "industry"]

    def test_get_featured_empty(self, client):
        _, fake = client
        fake.list_templates.return_value = [WorkflowTemplate(**_legacy("plain"))]
        resp = client[0].get("/api/marketplace/templates/featured")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_featured_sorted_and_limited(self, client):
        _, fake = client
        fake.list_templates.return_value = [
            SimpleNamespace(is_featured=True, rating=4.0, downloads=10),
            SimpleNamespace(is_featured=True, rating=5.0, downloads=3),
            SimpleNamespace(is_featured=False, rating=5.0, downloads=99),
        ]
        resp = client[0].get("/api/marketplace/templates/featured?limit=1")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["rating"] == 5.0

    def test_get_template_details_found(self, client):
        _, fake = client
        fake.get_template.return_value = WorkflowTemplate(**_legacy("tmpl_y"))
        resp = client[0].get("/api/marketplace/templates/tmpl_y")
        assert resp.status_code == 200
        assert resp.json()["id"] == "tmpl_y"

    def test_get_template_details_404(self, client):
        _, fake = client
        fake.get_template.return_value = None
        resp = client[0].get("/api/marketplace/templates/nope")
        assert resp.status_code == 404

    def test_import_template_success(self, client):
        _, fake = client
        fake.get_template.return_value = WorkflowTemplate(**_legacy("tmpl_z"))
        fake.import_workflow.return_value = {"id": "w1", "name": "Imported"}
        resp = client[0].post("/api/marketplace/templates/tmpl_z/import")
        assert resp.status_code == 200
        assert resp.json()["id"] == "w1"

    def test_import_template_not_found_is_404_not_500(self, client):
        """TDD bug: HTTPException(404) raised inside the try block was
        swallowed by `except Exception` and re-raised as a 500."""
        _, fake = client
        fake.get_template.return_value = None
        resp = client[0].post("/api/marketplace/templates/missing/import")
        assert resp.status_code == 404

    def test_import_template_engine_error_is_500(self, client):
        _, fake = client
        fake.get_template.side_effect = RuntimeError("boom")
        resp = client[0].post("/api/marketplace/templates/tmpl_z/import")
        assert resp.status_code == 500

    def test_create_advanced_template_endpoint(self, client):
        _, fake = client
        fake.create_advanced_template.return_value = AdvancedWorkflowTemplate(
            **_advanced("endpoint_adv")
        )
        resp = client[0].post("/api/marketplace/templates/advanced", json=_advanced("endpoint_adv"))
        assert resp.status_code == 200
        assert resp.json()["id"] == "endpoint_adv"

    def test_create_advanced_template_error_400(self, client):
        _, fake = client
        fake.create_advanced_template.side_effect = ValueError("bad")
        resp = client[0].post("/api/marketplace/templates/advanced", json={})
        assert resp.status_code == 400

    def test_create_workflow_endpoint_success(self, client):
        _, fake = client
        fake.create_workflow_from_advanced_template.return_value = {"workflow_id": "w9"}
        resp = client[0].post(
            "/api/marketplace/templates/advanced_etl_pipeline/create-workflow",
            params={"workflow_name": "My ETL"},
            json={"data_source_type": "database"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert resp.json()["workflow_definition"] == {"workflow_id": "w9"}

    def test_create_workflow_endpoint_404(self, client):
        _, fake = client
        fake.create_workflow_from_advanced_template.side_effect = ValueError("not found")
        resp = client[0].post(
            "/api/marketplace/templates/missing/create-workflow",
            params={"workflow_name": "w"},
        )
        assert resp.status_code == 404

    def test_create_workflow_endpoint_400(self, client):
        _, fake = client
        fake.create_workflow_from_advanced_template.side_effect = RuntimeError("bad")
        resp = client[0].post(
            "/api/marketplace/templates/advanced_x/create-workflow",
            params={"workflow_name": "w"},
        )
        assert resp.status_code == 400

    def test_upload_import_valid_json(self, client):
        _, fake = client
        fake.import_workflow.return_value = {"id": "w2", "name": "Imported: up"}
        resp = client[0].post(
            "/api/marketplace/import",
            files={"file": ("flow.json", json.dumps({"nodes": [], "edges": []}), "application/json")},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Imported: up"

    def test_upload_import_invalid_json(self, client):
        resp = client[0].post(
            "/api/marketplace/import",
            files={"file": ("flow.json", "{not json", "application/json")},
        )
        assert resp.status_code == 400

    def test_upload_import_value_error_400(self, client):
        _, fake = client
        fake.import_workflow.side_effect = ValueError("missing nodes")
        resp = client[0].post(
            "/api/marketplace/import",
            files={"file": ("flow.json", '{"nodes": []}', "application/json")},
        )
        assert resp.status_code == 400

    def test_upload_import_other_error_500(self, client):
        _, fake = client
        fake.import_workflow.side_effect = RuntimeError("boom")
        resp = client[0].post(
            "/api/marketplace/import",
            files={"file": ("flow.json", '{"nodes": []}', "application/json")},
        )
        assert resp.status_code == 500

    def test_export_success(self, client):
        _, fake = client
        fake.export_workflow.return_value = {"name": "Exported"}
        resp = client[0].post("/api/marketplace/export", json={"nodes": [], "edges": []})
        assert resp.status_code == 200
        assert resp.json() == {"name": "Exported"}

    def test_export_value_error_400(self, client):
        _, fake = client
        fake.export_workflow.side_effect = ValueError("invalid")
        resp = client[0].post("/api/marketplace/export", json={})
        assert resp.status_code == 400

    def test_export_other_error_500(self, client):
        _, fake = client
        fake.export_workflow.side_effect = RuntimeError("boom")
        resp = client[0].post("/api/marketplace/export", json={})
        assert resp.status_code == 500

    def test_statistics_empty(self, client):
        _, fake = client
        fake.list_templates.return_value = []
        resp = client[0].get("/api/marketplace/templates/statistics")
        assert resp.status_code == 200
        assert resp.json()["total_templates"] == 0
        assert resp.json()["average_rating"] == 0.0

    def test_statistics_populated(self, client):
        _, fake = client
        a = _legacy("s1", category="Sales", downloads=5, rating=4.0)
        b = _legacy("s2", category="Sales", downloads=10, rating=5.0)
        c = _legacy("s3", category="Ops", downloads=1, rating=3.0)
        c["template_type"] = "advanced"
        c["complexity"] = "Advanced"
        fake.list_templates.return_value = [
            WorkflowTemplate(**a),
            WorkflowTemplate(**b),
            WorkflowTemplate(**c),
        ]
        resp = client[0].get("/api/marketplace/templates/statistics")
        stats = resp.json()
        assert stats["total_templates"] == 3
        assert stats["total_downloads"] == 16
        assert stats["average_rating"] == pytest.approx(4.0)
        assert stats["categories"]["Sales"]["count"] == 2
        assert stats["categories"]["Sales"]["downloads"] == 15
        assert stats["complexity_levels"]["Advanced"]["count"] == 1


# ============================================================================
# Models
# ============================================================================

class TestModels:
    def test_workflow_template_defaults(self):
        minimal = {
            "id": "d1",
            "name": "n",
            "description": "d",
            "category": "c",
            "author": "a",
            "version": "1.0.0",
            "integrations": [],
            "complexity": "Beginner",
            "workflow_data": {"nodes": [], "edges": []},
            "created_at": "2026-01-01T00:00:00",
        }
        tmpl = WorkflowTemplate(**minimal)
        assert tmpl.template_type == TemplateType.LEGACY
        assert tmpl.tags == []
        assert tmpl.estimated_duration is None
        assert tmpl.multi_input_support is False
        assert tmpl.prerequisites == []
        assert tmpl.industry is None

    def test_advanced_template_defaults(self):
        data = _advanced("adv_d1")
        tmpl = AdvancedWorkflowTemplate(**data)
        assert tmpl.output_config is None
        assert tmpl.pause_resume_support is True
        assert tmpl.use_cases == ["uc"]
        assert tmpl.downloads == 0
