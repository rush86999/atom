"""Coverage wave 71 — core/custom_components_service.py (0% → 95%+).

Full service-level suite (Mock db): CRUD, versioning/rollback, usage
tracking, security sanitization (HTML/CSS/JS), dependency whitelist,
governance gates for JS (AUTONOMOUS only), ownership enforcement, slug
uniqueness, error paths.
"""
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.orm import Session

from core.custom_components_service import (
    ComponentSecurityError,
    CustomComponentsService,
)
from core.models import (
    AgentStatus,
    ComponentUsage,
    ComponentVersion,
    CustomComponent,
    User,
)


@pytest.fixture
def db():
    return Mock(spec=Session)


@pytest.fixture
def service(db):
    return CustomComponentsService(db)


@pytest.fixture
def user():
    u = Mock(spec=User)
    u.id = "user-1"
    return u


_MISSING = object()


def chain(db, first_values=_MISSING, all_values=_MISSING, first_returns=_MISSING):
    """Wire query()->filter()->...->first()/all() mock chain."""
    q = db.query.return_value
    f = q.filter.return_value
    f.filter.return_value = f
    f.order_by.return_value = f
    f.limit.return_value = f
    if first_values is not _MISSING:
        f.first.side_effect = list(first_values)
    if first_returns is not _MISSING:
        f.first.return_value = first_returns
    if all_values is not _MISSING:
        f.all.return_value = all_values
    return f


def make_component(**overrides):
    c = CustomComponent(
        id=overrides.get("id", "comp-1"),
        created_by=overrides.get("created_by", "user-1"),
        name=overrides.get("name", "chart"),
        display_name="chart",
        slug=overrides.get("slug", "chart"),
        component_type=overrides.get("component_type", "custom"),
        html_content=overrides.get("html_content", "<div>x</div>"),
        css_content=overrides.get("css_content", ".x {}"),
        js_content=overrides.get("js_content", None),
        props_schema=overrides.get("props_schema", None),
        default_props=overrides.get("default_props", {}),
        is_public=overrides.get("is_public", False),
        current_version=overrides.get("current_version", 1),
    )
    c.created_at = overrides.get("created_at", datetime.now())
    c.updated_at = overrides.get("updated_at", datetime.now())
    return c


def make_version(**overrides):
    v = ComponentVersion(
        id=overrides.get("id", "v1"),
        component_id=overrides.get("component_id", "comp-1"),
        version_number=overrides.get("version_number", 1),
        html_content=overrides.get("html_content", "<div>x</div>"),
        css_content=overrides.get("css_content", ".x {}"),
        js_content=overrides.get("js_content", None),
        change_summary=overrides.get("change_summary", "init"),
        created_by="user-1",
    )
    v.created_at = overrides.get("created_at", datetime.now())
    return v


def make_usage(**overrides):
    u = ComponentUsage(
        id=overrides.get("id", "u1"),
        component_id=overrides.get("component_id", "comp-1"),
        canvas_id=overrides.get("canvas_id", "canvas-1"),
        execution_context=overrides.get("execution_context", {}),
    )
    u.executed_at = overrides.get("executed_at", datetime.now())
    return u


class TestSecurityError:
    def test_str_components(self):
        err = ComponentSecurityError("bad", component_name="chart",
                                     validation_reason="xss")
        s = str(err)
        assert "Component: chart" in s
        assert "Reason: xss" in s

    def test_str_plain(self):
        assert str(ComponentSecurityError("bad")) == "bad"


class TestCreateComponent:
    def test_create_success_no_js(self, service, db, user):
        chain(db, first_values=[None, None])
        db.refresh.side_effect = lambda c: setattr(c, "created_at", datetime.now())
        result = service.create_component(user.id, "my chart", "<div>hi</div>",
                                          ".x{}", None, "desc", category="chart")
        assert result["name"] == "my chart"
        assert result["slug"] == "my-chart"
        assert result["has_js"] is False
        assert result["version"] == 1
        assert db.add.call_count == 2
        assert db.commit.call_count == 2

    def test_create_with_js_autonomous_agent(self, service, db, user):
        agent = Mock(status=AgentStatus.AUTONOMOUS.value)
        agent.name = "A"
        chain(db, first_values=[agent, None, None])
        db.refresh.side_effect = lambda c: setattr(c, "created_at", datetime.now())
        result = service.create_component(user.id, "js chart", "<div>hi</div>",
                                          None, "console.log(1)", agent_id="ag-1")
        assert result["has_js"] is True
        assert result["version"] == 1

    def test_create_with_js_but_no_agent_raises(self, service, db, user):
        with pytest.raises(ComponentSecurityError) as e:
            service.create_component(user.id, "c", "<div>hi</div>", None,
                                     "console.log(1)")
        assert "No agent provided" in str(e.value)

    def test_create_with_js_unknown_agent_raises(self, service, db, user):
        chain(db, first_values=[None])
        with pytest.raises(ComponentSecurityError) as e:
            service.create_component(user.id, "c", "<div>hi</div>", None,
                                     "console.log(1)", agent_id="ghost")
        assert "not found" in str(e.value)

    def test_create_with_js_non_autonomous_agent_raises(self, service, db, user):
        agent = Mock(status=AgentStatus.SUPERVISED.value)
        agent.name = "S"
        chain(db, first_values=[agent])
        with pytest.raises(ComponentSecurityError) as e:
            service.create_component(user.id, "c", "<div>hi</div>", None,
                                     "console.log(1)", agent_id="ag-1")
        assert "AUTONOMOUS" in str(e.value)

    def test_create_duplicate_name_raises(self, service, db, user):
        existing = make_component(name="dup")
        chain(db, first_values=[existing])
        with pytest.raises(ValueError) as e:
            service.create_component(user.id, "dup", "<div>hi</div>")
        assert "already exists" in str(e.value)

    def test_create_unique_slug_generated(self, service, db, user):
        taken = make_component(id="other", name="other", slug="my-chart")
        chain(db, first_values=[None, taken, None])
        db.refresh.side_effect = lambda c: setattr(c, "created_at", datetime.now())
        result = service.create_component(user.id, "My Chart", "<div>hi</div>")
        assert result["slug"] == "my-chart-1"

    def test_create_dangerous_html_raises(self, service, db, user):
        chain(db, first_values=[None, None])
        with pytest.raises(ComponentSecurityError) as e:
            service.create_component(user.id, "c", "<script>alert(1)</script>")
        assert "script" in str(e.value).lower()

    def test_create_dangerous_html_javascript_uri_raises(self, service, db, user):
        chain(db, first_values=[None, None])
        with pytest.raises(ComponentSecurityError):
            service.create_component(user.id, "c", "<a href='javascript:alert(1)'>x</a>")

    def test_create_dangerous_html_event_handler_raises(self, service, db, user):
        chain(db, first_values=[None, None])
        with pytest.raises(ComponentSecurityError):
            service.create_component(user.id, "c", "<img onerror='x'>")

    def test_create_dangerous_css_raises(self, service, db, user):
        for css in ["expression(alert(1))", "behavior:url(x)", "-ms-binding", "javascript:void(0)"]:
            chain(db, first_values=[None, None])
            with pytest.raises(ComponentSecurityError):
                service.create_component(user.id, "c", "<div>x</div>", css)

    def test_create_dangerous_js_raises(self, service, db, user):
        agent = Mock(status=AgentStatus.AUTONOMOUS.value)
        agent.name = "A"
        bad_js = [
            "eval('x')", "Function('x')", "new Function('x')", "require('fs')",
            "document.write('x')", "document.cookie", "localStorage.getItem('k')",
            "window.location = 'x'", "fetch('/api')", "setTimeout('alert(1)')",
            "__proto__", "import('mod')",
        ]
        for js in bad_js:
            chain(db, first_values=[agent, None, None])
            with pytest.raises(ComponentSecurityError):
                service.create_component(user.id, "c", "<div>x</div>", None, js,
                                         agent_id="ag-1")

    def test_create_safe_js_allowed(self, service, db, user):
        agent = Mock(status=AgentStatus.AUTONOMOUS.value)
        agent.name = "A"
        chain(db, first_values=[agent, None, None])
        db.refresh.side_effect = lambda c: setattr(c, "created_at", datetime.now())
        result = service.create_component(user.id, "c", "<div>x</div>", None,
                                          "console.log('hello world')", agent_id="ag-1")
        assert result["has_js"] is True

    def test_create_allowed_dependency(self, service, db, user):
        chain(db, first_values=[None, None])
        db.refresh.side_effect = lambda c: setattr(c, "created_at", datetime.now())
        result = service.create_component(
            user.id, "c", "<div>x</div>", None, None, None, "custom", None, None,
            ["https://cdn.jsdelivr.net/npm/chart.js"])
        assert result["slug"] == "c"

    def test_create_blocked_dependency_raises(self, service, db, user):
        chain(db, first_values=[None, None])
        with pytest.raises(ComponentSecurityError) as e:
            service.create_component(user.id, "c", "<div>x</div>", None, None,
                                     None, "custom", None, None,
                                     ["https://evil.com/x.js"])
        assert "not in allowed list" in str(e.value)


class TestGetComponent:
    def test_get_requires_identifier(self, service, db):
        assert service.get_component()["error"] == "Either component_id or slug required"

    def test_get_by_id_owner(self, service, db):
        comp = make_component()
        chain(db, first_returns=comp)
        result = service.get_component(component_id="comp-1", user_id="user-1")
        assert result["component_id"] == "comp-1"
        assert result["js_content"] is None

    def test_get_by_slug_public_other_user(self, service, db):
        comp = make_component(is_public=True)
        chain(db, first_returns=comp)
        result = service.get_component(slug="chart", user_id="someone-else")
        assert result["name"] == "chart"

    def test_get_private_other_user_denied(self, service, db):
        comp = make_component(is_public=False)
        chain(db, first_returns=comp)
        assert service.get_component(component_id="comp-1", user_id="intruder")["error"] == \
            "Access denied: Component is private"

    def test_get_not_found(self, service, db):
        chain(db, first_returns=None)
        assert service.get_component(component_id="ghost", user_id="u")["error"] == \
            "Component not found"

    def test_get_by_id_with_updated_at_none(self, service, db):
        comp = make_component(updated_at=None)
        chain(db, first_returns=comp)
        result = service.get_component(component_id="comp-1", user_id="user-1")
        assert result["updated_at"] is None


class TestListComponents:
    def _populate(self, db, comps):
        chain(db, all_values=comps)

    def test_list_public_only_no_user(self, service, db):
        comp = make_component(is_public=True)
        self._populate(db, [comp])
        result = service.list_components()
        assert result["total"] == 1
        assert result["components"][0]["is_owner"] is False

    def test_list_own_with_user(self, service, db):
        comp = make_component(created_by="user-1")
        self._populate(db, [comp])
        result = service.list_components(user_id="user-1", category="custom",
                                         is_public=False)
        assert result["components"][0]["is_owner"] is True

    def test_list_empty(self, service, db):
        self._populate(db, [])
        assert service.list_components()["total"] == 0


class TestUpdateComponent:
    def test_update_not_found(self, service, db):
        chain(db, first_returns=None)
        assert service.update_component("ghost", "user-1")["error"] == "Component not found"

    def test_update_not_owner_denied(self, service, db):
        comp = make_component(created_by="other")
        chain(db, first_returns=comp)
        assert service.update_component("comp-1", "user-1")["error"] == \
            "Access denied: Not component owner"

    def test_update_all_fields_new_version(self, service, db):
        comp = make_component(current_version=1)
        agent = Mock(status=AgentStatus.AUTONOMOUS.value)
        agent.name = "A"
        chain(db, first_values=[comp, None, agent])
        db.refresh.side_effect = lambda c: setattr(c, "updated_at", datetime.now())
        result = service.update_component(
            "comp-1", "user-1", name="new name", html_content="<div>new</div>",
            css_content=".y{}", js_content="console.log(2)", description="d2",
            props_schema={"type": "object"}, default_props={"a": 1},
            dependencies=["https://unpkg.com/x"], is_public=True,
            change_description="big change", agent_id="ag-1")
        assert result["version"] == 2
        assert comp.name == "new name"
        assert comp.is_public is True

    def test_update_rename_to_existing_name_raises(self, service, db):
        comp = make_component()
        existing = make_component(id="comp-2", name="taken", slug="taken")
        chain(db, first_values=[comp, existing])
        with pytest.raises(ValueError) as e:
            service.update_component("comp-1", "user-1", name="taken")
        assert "already exists" in str(e.value)

    def test_update_js_change_requires_autonomous(self, service, db):
        comp = make_component()
        supervised = Mock(status=AgentStatus.SUPERVISED.value)
        supervised.name = "S"
        chain(db, first_values=[comp, supervised])
        with pytest.raises(ComponentSecurityError) as e:
            service.update_component("comp-1", "user-1", js_content="console.log(2)",
                                     agent_id="student-agent")
        assert "AUTONOMOUS" in str(e.value)

    def test_update_js_unchanged_skips_governance(self, service, db):
        comp = make_component(js_content="console.log(1)")
        chain(db, first_values=[comp, None])
        db.refresh.side_effect = lambda c: setattr(c, "updated_at", datetime.now())
        result = service.update_component("comp-1", "user-1", js_content="console.log(1)")
        assert result["version"] == 2

    def test_update_dangerous_js_raises(self, service, db):
        comp = make_component()
        agent = Mock(status=AgentStatus.AUTONOMOUS.value)
        agent.name = "A"
        chain(db, first_values=[comp, agent])
        with pytest.raises(ComponentSecurityError):
            service.update_component("comp-1", "user-1", js_content="eval('x')",
                                     agent_id="ag-1")

    def test_update_bad_dependency_raises(self, service, db):
        comp = make_component()
        chain(db, first_values=[comp])
        with pytest.raises(ComponentSecurityError):
            service.update_component("comp-1", "user-1",
                                     dependencies=["https://evil.com/x"])

    def test_update_no_changes_still_bumps_version(self, service, db):
        comp = make_component()
        chain(db, first_values=[comp])
        db.refresh.side_effect = lambda c: setattr(c, "updated_at", datetime.now())
        result = service.update_component("comp-1", "user-1")
        assert result["version"] == 2


class TestDeleteComponent:
    def test_delete_not_found(self, service, db):
        chain(db, first_returns=None)
        assert service.delete_component("ghost", "u")["error"] == "Component not found"

    def test_delete_not_owner_denied(self, service, db):
        comp = make_component(created_by="other")
        chain(db, first_returns=comp)
        assert service.delete_component("comp-1", "u")["error"] == \
            "Access denied: Not component owner"

    def test_delete_success_soft_delete(self, service, db):
        comp = make_component()
        chain(db, first_returns=comp)
        result = service.delete_component("comp-1", "user-1")
        assert comp.is_active is False
        assert result["status"] == "deleted"


class TestVersions:
    def test_versions_not_found(self, service, db):
        chain(db, first_returns=None)
        assert service.get_component_versions("ghost", "u")["error"] == "Component not found"

    def test_versions_not_owner_denied(self, service, db):
        comp = make_component(created_by="other")
        chain(db, first_returns=comp)
        assert service.get_component_versions("comp-1", "u")["error"] == \
            "Access denied: Not component owner"

    def test_versions_listed(self, service, db):
        comp = make_component(current_version=2)
        v1 = make_version(version_number=1, change_summary="init")
        v2 = make_version(id="v2", version_number=2, change_summary="update")
        chain(db, first_returns=comp, all_values=[v2, v1])
        result = service.get_component_versions("comp-1", "user-1")
        assert result["total_versions"] == 2
        assert result["versions"][0]["change_summary"] == "update"

    def test_rollback_not_found(self, service, db):
        chain(db, first_returns=None)
        assert service.rollback_component("ghost", 1, "u")["error"] == "Component not found"

    def test_rollback_not_owner_denied(self, service, db):
        comp = make_component(created_by="other")
        chain(db, first_returns=comp)
        assert service.rollback_component("comp-1", 1, "u")["error"] == \
            "Access denied: Not component owner"

    def test_rollback_target_missing(self, service, db):
        comp = make_component(current_version=2)
        chain(db, first_values=[comp, None])
        assert service.rollback_component("comp-1", 3, "user-1")["error"] == \
            "Target version not found"

    def test_rollback_success(self, service, db):
        comp = make_component(current_version=2)
        target = make_version(version_number=1, html_content="<div>old</div>",
                              css_content=".old{}", js_content="oldJs")
        chain(db, first_values=[comp, target])
        db.refresh.side_effect = lambda c: setattr(c, "updated_at", datetime.now())
        result = service.rollback_component("comp-1", 1, "user-1")
        assert result["previous_version"] == 1
        assert result["new_version"] == 3
        assert comp.html_content == "<div>old</div>"
        assert comp.js_content == "oldJs"


class TestUsage:
    def test_record_usage(self, service, db):
        result = service.record_component_usage(
            "comp-1", "canvas-1", "user-1", session_id="s1", agent_id="ag-1",
            props_passed={"x": 1}, rendering_time_ms=42, error_message=None,
            governance_check_passed=True, agent_maturity_level="AUTONOMOUS")
        assert result["status"] == "recorded"
        usage = db.add.call_args[0][0]
        assert usage.execution_context["rendering_time_ms"] == 42

    def test_usage_stats_not_found(self, service, db):
        chain(db, first_returns=None)
        assert service.get_component_usage_stats("ghost", "u")["error"] == "Component not found"

    def test_usage_stats_not_owner_denied(self, service, db):
        comp = make_component(created_by="other")
        chain(db, first_returns=comp)
        assert service.get_component_usage_stats("comp-1", "u")["error"] == \
            "Access denied: Not component owner"

    def test_usage_stats_computed(self, service, db):
        comp = make_component()
        usages = [
            make_usage(canvas_id="c1", execution_context={
                "error_message": None, "rendering_time_ms": 100}),
            make_usage(id="u2", canvas_id="c1", execution_context={
                "error_message": "render failed", "rendering_time_ms": 200}),
            make_usage(id="u3", canvas_id="c2", execution_context={
                "error_message": None, "rendering_time_ms": None}),
            make_usage(id="u4", canvas_id="c2", execution_context=None),
        ]
        chain(db, first_returns=comp, all_values=usages)
        result = service.get_component_usage_stats("comp-1", "user-1")
        assert result["total_renders"] == 4
        assert result["successful_renders"] == 3
        assert result["failed_renders"] == 1
        assert result["success_rate"] == 0.75
        assert result["avg_rendering_time_ms"] == 150.0
        assert result["top_canvases"][0] == {"canvas_id": "c1", "render_count": 2}

    def test_usage_stats_no_records(self, service, db):
        comp = make_component()
        chain(db, first_returns=comp, all_values=[])
        result = service.get_component_usage_stats("comp-1", "user-1")
        assert result["success_rate"] == 0
        assert result["avg_rendering_time_ms"] == 0


class TestHelpers:
    def test_slugify(self, service):
        assert service._slugify("  Hello, World!  ") == "hello-world"
        assert service._slugify("already-kebab") == "already-kebab"
        assert service._slugify("UPPER Case") == "upper-case"
