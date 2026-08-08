# -*- coding: utf-8 -*-
"""
Coverage + bug-hunt tests for core/custom_components_service.py.

Unlike the pre-existing mock-based test_custom_components_service.py (which
exercises almost no real branches and has 2 broken tests due to enum-value
mismatches), this file drives the service against a real in-memory SQLite DB
so every ownership check, not-found path, and sanitization branch is hit for
real. Bug-hunt tests are marked with the ``BUG:`` docstring convention and
were written to FAIL before the source fix.
"""

import pytest
from sqlalchemy.orm import sessionmaker

from core.custom_components_service import (
    ComponentSecurityError,
    CustomComponentsService,
)
from core.models import (
    AgentRegistry,
    AgentStatus,
    CustomComponent,
    ComponentVersion,
    ComponentUsage,
)


# ---------------------------------------------------------------------------
# Real-DB fixture (in-memory SQLite, all tables, FKs off).
# ---------------------------------------------------------------------------
@pytest.fixture
def db():
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool
    from core.models_registration import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def service(db):
    return CustomComponentsService(db)


def _autonomous_agent(db, agent_id="ag-auto", status=AgentStatus.AUTONOMOUS.value):
    """Insert an AgentRegistry row with all NOT NULL fields populated."""
    ag = AgentRegistry(
        id=agent_id,
        name="Auto Agent",
        display_name="Auto Agent",
        category="test",
        module_path="test.module",
        class_name="TestClass",
        status=status,
        confidence_score=0.95,
    )
    db.add(ag)
    db.commit()
    return ag


# ===========================================================================
# create_component
# ===========================================================================
class TestCreateComponent:
    def test_create_no_js_succeeds(self, service, db):
        """No-JS component: no governance check, min maturity SUPERVISED."""
        result = service.create_component(
            "u1", "Chart1", "<div>hi</div>",
            css_content=".x { color: red; }",
            description="desc",
            category="chart",
        )
        assert result["name"] == "Chart1"
        assert result["has_js"] is False
        assert result["version"] == 1
        comp = db.query(CustomComponent).filter(CustomComponent.name == "Chart1").one()
        assert comp.min_maturity_level == "SUPERVISED"
        assert comp.is_active is True
        # initial version row written
        versions = db.query(ComponentVersion).filter(
            ComponentVersion.component_id == comp.id
        ).all()
        assert len(versions) == 1
        assert versions[0].version_number == 1

    def test_create_with_dependencies(self, service, db):
        """Whitelisted CDN dependency URLs are accepted."""
        result = service.create_component(
            "u1", "WithDeps", "<div>x</div>",
            dependencies=["https://unpkg.com/react@18/umd/react.js"],
        )
        assert result["component_id"]

    def test_create_generates_unique_slug(self, service, db):
        """Slug is derived from name and lowercased."""
        result = service.create_component("u1", "My Cool Chart", "<div>x</div>")
        assert result["slug"] == "my-cool-chart"

    def test_create_duplicate_name_raises(self, service, db):
        service.create_component("u1", "Dup", "<div>a</div>")
        with pytest.raises(ValueError, match="already exists"):
            service.create_component("u2", "Dup", "<div>b</div>")

    def test_create_js_without_agent_raises(self, service, db):
        with pytest.raises(ComponentSecurityError, match="AUTONOMOUS agent"):
            service.create_component("u1", "J1", "<div>x</div>", js_content="var a=1;")

    def test_create_js_with_non_autonomous_agent_raises(self, service, db):
        _autonomous_agent(db, status=AgentStatus.SUPERVISED.value)
        with pytest.raises(ComponentSecurityError, match="AUTONOMOUS maturity"):
            service.create_component(
                "u1", "J2", "<div>x</div>", js_content="var a=1;", agent_id="ag-auto"
            )

    def test_create_js_with_unknown_agent_raises(self, service, db):
        with pytest.raises(ComponentSecurityError, match="not found"):
            service.create_component(
                "u1", "J3", "<div>x</div>", js_content="var a=1;", agent_id="ghost"
            )

    def test_create_js_with_autonomous_agent_succeeds(self, service, db):
        _autonomous_agent(db)
        result = service.create_component(
            "u1", "J4", "<div>x</div>", js_content="var a=1;", agent_id="ag-auto"
        )
        assert result["has_js"] is True
        comp = db.query(CustomComponent).filter(CustomComponent.name == "J4").one()
        assert comp.min_maturity_level == "AUTONOMOUS"

    def test_create_with_dangerous_html_raises(self, service, db):
        with pytest.raises(ComponentSecurityError, match="dangerous pattern"):
            service.create_component("u1", "Bad", "<script>alert(1)</script>")

    def test_create_with_onerror_html_raises(self, service, db):
        with pytest.raises(ComponentSecurityError):
            service.create_component("u1", "Bad2", '<img src=x onerror="x()">')

    def test_create_with_dangerous_css_raises(self, service, db):
        with pytest.raises(ComponentSecurityError, match="CSS contains dangerous"):
            service.create_component(
                "u1", "BadCss", "<div>x</div>", css_content="x { behavior:url(evil); }"
            )

    def test_create_with_js_injection_blocked(self, service, db):
        _autonomous_agent(db)
        with pytest.raises(ComponentSecurityError, match="blocked pattern"):
            service.create_component(
                "u1", "BadJs", "<div>x</div>",
                js_content="eval('evil')", agent_id="ag-auto",
            )

    def test_create_with_disallowed_dependency_raises(self, service, db):
        with pytest.raises(ComponentSecurityError, match="not in allowed list"):
            service.create_component(
                "u1", "BadDep", "<div>x</div>",
                dependencies=["https://evil.example.com/lib.js"],
            )

    def test_create_with_props_and_public_flag(self, service, db):
        result = service.create_component(
            "u1", "PropComp", "<div>x</div>",
            props_schema={"type": "object"},
            default_props={"color": "red"},
            is_public=True,
        )
        assert result["is_public"] is True
        comp = db.query(CustomComponent).filter(CustomComponent.name == "PropComp").one()
        assert comp.props_schema == {"type": "object"}
        assert comp.default_props == {"color": "red"}


# ===========================================================================
# get_component
# ===========================================================================
class TestGetComponent:
    def test_get_by_id_owner(self, service, db):
        created = service.create_component("u1", "G1", "<div>x</div>", is_public=False)
        got = service.get_component(component_id=created["component_id"], user_id="u1")
        assert got["name"] == "G1"
        assert got["js_content"] is None  # no JS
        assert "error" not in got

    def test_get_by_slug(self, service, db):
        created = service.create_component("u1", "Slug Comp", "<div>x</div>", is_public=True)
        got = service.get_component(slug="slug-comp", user_id="u2")
        assert got["name"] == "Slug Comp"

    def test_get_without_id_or_slug(self, service, db):
        got = service.get_component()
        assert got["error"] == "Either component_id or slug required"

    def test_get_not_found(self, service, db):
        got = service.get_component(component_id="nope", user_id="u1")
        assert got["error"] == "Component not found"

    def test_get_private_as_non_owner_denied(self, service, db):
        created = service.create_component("u1", "Priv", "<div>x</div>", is_public=False)
        got = service.get_component(component_id=created["component_id"], user_id="u2")
        assert got["error"] == "Access denied: Component is private"

    def test_get_public_as_non_owner_ok_js_hidden(self, service, db):
        _autonomous_agent(db)
        created = service.create_component(
            "u1", "Pub", "<div>x</div>", js_content="var a=1;",
            is_public=True, agent_id="ag-auto",
        )
        # Non-owner fetches public component: JS content is hidden.
        got = service.get_component(component_id=created["component_id"], user_id="u2")
        assert got["name"] == "Pub"
        assert got["js_content"] is None
        assert got["has_js"] is True

    def test_get_owner_sees_js(self, service, db):
        _autonomous_agent(db)
        created = service.create_component(
            "u1", "Own", "<div>x</div>", js_content="var a=1;", agent_id="ag-auto",
        )
        got = service.get_component(component_id=created["component_id"], user_id="u1")
        assert got["js_content"] == "var a=1;"


# ===========================================================================
# list_components
# ===========================================================================
class TestListComponents:
    def test_list_filters_to_public_when_no_user(self, service, db):
        service.create_component("u1", "PrivA", "<div>x</div>", is_public=False)
        service.create_component("u1", "PubA", "<div>y</div>", is_public=True)
        result = service.list_components(user_id=None)
        names = [c["name"] for c in result["components"]]
        assert names == ["PubA"]
        assert result["total"] == 1

    def test_list_includes_own_and_public(self, service, db):
        service.create_component("u1", "Mine", "<div>x</div>", is_public=False)
        service.create_component("u2", "TheirsPub", "<div>y</div>", is_public=True)
        service.create_component("u2", "TheirsPriv", "<div>z</div>", is_public=False)
        result = service.list_components(user_id="u1")
        names = sorted(c["name"] for c in result["components"])
        assert names == ["Mine", "TheirsPub"]

    def test_list_category_and_public_filter(self, service, db):
        service.create_component("u1", "A", "<div>x</div>", category="chart", is_public=True)
        service.create_component("u1", "B", "<div>x</div>", category="form", is_public=True)
        result = service.list_components(category="chart")
        assert [c["name"] for c in result["components"]] == ["A"]

    def test_list_is_public_true_filter(self, service, db):
        service.create_component("u1", "A", "<div>x</div>", is_public=True)
        service.create_component("u1", "B", "<div>x</div>", is_public=False)
        result = service.list_components(user_id="u1", is_public=True)
        assert all(c["is_public"] is True for c in result["components"])

    def test_list_limit(self, service, db):
        for i in range(5):
            service.create_component("u1", f"L{i}", "<div>x</div>", is_public=True)
        result = service.list_components(limit=2)
        assert result["total"] == 2

    def test_list_is_owner_flag(self, service, db):
        service.create_component("u1", "Own", "<div>x</div>", is_public=True)
        result = service.list_components(user_id="u1")
        assert result["components"][0]["is_owner"] is True


# ===========================================================================
# update_component
# ===========================================================================
class TestUpdateComponent:
    def test_update_not_found(self, service, db):
        got = service.update_component("nope", "u1", description="x")
        assert got["error"] == "Component not found"

    def test_update_not_owner(self, service, db):
        created = service.create_component("u1", "Up1", "<div>x</div>")
        got = service.update_component(created["component_id"], "u2", description="x")
        assert got["error"] == "Access denied: Not component owner"

    def test_update_html_css_description(self, service, db):
        created = service.create_component("u1", "Up2", "<div>old</div>")
        result = service.update_component(
            created["component_id"], "u1",
            html_content="<div>new</div>",
            css_content=".a { color: blue; }",
            description="updated",
            change_description="tweaked",
        )
        assert result["version"] == 2
        comp = db.query(CustomComponent).filter(CustomComponent.name == "Up2").one()
        assert comp.html_content == "<div>new</div>"
        assert comp.css_content == ".a { color: blue; }"
        assert comp.description == "updated"

    def test_update_name(self, service, db):
        created = service.create_component("u1", "Rename", "<div>x</div>")
        service.update_component(created["component_id"], "u1", name="Renamed")
        comp = db.query(CustomComponent).filter(
            CustomComponent.id == created["component_id"]
        ).one()
        assert comp.name == "Renamed"

    def test_update_js_requires_governance(self, service, db):
        created = service.create_component("u1", "NoJs", "<div>x</div>")
        # JS change without autonomous agent -> blocked.
        with pytest.raises(ComponentSecurityError):
            service.update_component(
                created["component_id"], "u1", js_content="var a=1;"
            )

    def test_update_js_with_autonomous_agent(self, service, db):
        _autonomous_agent(db)
        created = service.create_component("u1", "AddJs", "<div>x</div>")
        result = service.update_component(
            created["component_id"], "u1", js_content="var a=1;", agent_id="ag-auto"
        )
        assert result["version"] == 2
        comp = db.query(CustomComponent).filter(CustomComponent.name == "AddJs").one()
        assert comp.js_content == "var a=1;"
        assert comp.min_maturity_level == "SUPERVISED"  # unchanged on update

    def test_update_props_and_public(self, service, db):
        created = service.create_component("u1", "PropUp", "<div>x</div>")
        service.update_component(
            created["component_id"], "u1",
            props_schema={"k": "v"}, default_props={"a": 1}, is_public=True,
        )
        comp = db.query(CustomComponent).filter(CustomComponent.name == "PropUp").one()
        assert comp.props_schema == {"k": "v"}
        assert comp.default_props == {"a": 1}
        assert comp.is_public is True

    def test_update_validates_dependencies(self, service, db):
        created = service.create_component("u1", "DepUp", "<div>x</div>")
        with pytest.raises(ComponentSecurityError):
            service.update_component(
                created["component_id"], "u1",
                dependencies=["https://evil.example.com/x.js"],
            )

    def test_update_unchanged_js_skips_governance(self, service, db):
        """If js_content equals existing js_content, no governance re-check."""
        _autonomous_agent(db)
        created = service.create_component(
            "u1", "SameJs", "<div>x</div>", js_content="var a=1;", agent_id="ag-auto"
        )
        # Passing the SAME js content must not trigger governance (no agent).
        result = service.update_component(
            created["component_id"], "u1", js_content="var a=1;"
        )
        assert result["version"] == 2


# ===========================================================================
# delete_component
# ===========================================================================
class TestDeleteComponent:
    def test_delete_not_found(self, service, db):
        got = service.delete_component("nope", "u1")
        assert got["error"] == "Component not found"

    def test_delete_not_owner(self, service, db):
        created = service.create_component("u1", "Del1", "<div>x</div>")
        got = service.delete_component(created["component_id"], "u2")
        assert got["error"] == "Access denied: Not component owner"

    def test_delete_success_soft_delete(self, service, db):
        created = service.create_component("u1", "Del2", "<div>x</div>")
        result = service.delete_component(created["component_id"], "u1")
        assert result["status"] == "deleted"
        comp = db.query(CustomComponent).filter(
            CustomComponent.id == created["component_id"]
        ).one()
        assert comp.is_active is False


# ===========================================================================
# Version control
# ===========================================================================
class TestVersionControl:
    def test_get_versions_not_found(self, service, db):
        assert service.get_component_versions("nope", "u1")["error"] == "Component not found"

    def test_get_versions_not_owner(self, service, db):
        created = service.create_component("u1", "V1", "<div>x</div>")
        assert service.get_component_versions(created["component_id"], "u2")[
            "error"
        ] == "Access denied: Not component owner"

    def test_get_versions_lists_all(self, service, db):
        created = service.create_component("u1", "V2", "<div>a</div>")
        service.update_component(created["component_id"], "u1", html_content="<div>b</div>")
        result = service.get_component_versions(created["component_id"], "u1")
        assert result["total_versions"] == 2
        assert result["current_version"] == 2
        numbers = [v["version_number"] for v in result["versions"]]
        assert numbers == [2, 1]  # desc order

    def test_rollback_not_found(self, service, db):
        created = service.create_component("u1", "R1", "<div>x</div>")
        got = service.rollback_component(created["component_id"], 99, "u1")
        assert got["error"] == "Target version not found"

    def test_rollback_component_not_found(self, service, db):
        got = service.rollback_component("nope", 1, "u1")
        assert got["error"] == "Component not found"

    def test_rollback_not_owner(self, service, db):
        created = service.create_component("u1", "R2", "<div>x</div>")
        assert service.rollback_component(created["component_id"], 1, "u2")[
            "error"
        ] == "Access denied: Not component owner"

    def test_rollback_restores_content(self, service, db):
        created = service.create_component("u1", "R3", "<div>original</div>")
        service.update_component(created["component_id"], "u1", html_content="<div>changed</div>")
        # current_version is now 2; rollback to version 1 creates version 3.
        result = service.rollback_component(created["component_id"], 1, "u1")
        assert result["new_version"] == 3
        assert result["status"] == "rolled_back"
        comp = db.query(CustomComponent).filter(CustomComponent.name == "R3").one()
        assert comp.html_content == "<div>original</div>"


# ===========================================================================
# Usage tracking
# ===========================================================================
class TestUsageTracking:
    def test_record_usage_returns_id(self, service, db):
        created = service.create_component("u1", "U1", "<div>x</div>")
        result = service.record_component_usage(
            created["component_id"], "canvas1", "u1",
            rendering_time_ms=42, governance_check_passed=True,
        )
        assert result["status"] == "recorded"
        assert result["usage_id"]

    def test_usage_stats_not_found(self, service, db):
        assert service.get_component_usage_stats("nope", "u1")["error"] == "Component not found"

    def test_usage_stats_not_owner(self, service, db):
        created = service.create_component("u1", "U2", "<div>x</div>")
        assert service.get_component_usage_stats(created["component_id"], "u2")[
            "error"
        ] == "Access denied: Not component owner"

    def test_usage_stats_empty(self, service, db):
        created = service.create_component("u1", "U3", "<div>x</div>")
        stats = service.get_component_usage_stats(created["component_id"], "u1")
        assert stats["total_renders"] == 0
        assert stats["success_rate"] == 0
        assert stats["avg_rendering_time_ms"] == 0

    def test_usage_stats_with_renders(self, service, db):
        created = service.create_component("u1", "U4", "<div>x</div>")
        service.record_component_usage(created["component_id"], "c1", "u1", rendering_time_ms=100)
        service.record_component_usage(created["component_id"], "c1", "u1", rendering_time_ms=200)
        service.record_component_usage(created["component_id"], "c2", "u1", error_message="boom")
        stats = service.get_component_usage_stats(created["component_id"], "u1")
        assert stats["total_renders"] == 3
        assert stats["successful_renders"] == 2
        assert stats["failed_renders"] == 1
        # Top canvas c1 should have render_count 2.
        top = {c["canvas_id"]: c["render_count"] for c in stats["top_canvases"]}
        assert top["c1"] == 2


# ===========================================================================
# Security helpers (direct unit coverage)
# ===========================================================================
class TestSecurityHelpers:
    def test_sanitize_html_passes_clean(self, service, db):
        assert service._sanitize_html("<div>ok</div>") == "<div>ok</div>"

    def test_sanitize_html_blocks_javascript_uri(self, service, db):
        with pytest.raises(ComponentSecurityError):
            service._sanitize_html('<a href="javascript:alert(1)">x</a>')

    def test_sanitize_css_none_returns_none(self, service, db):
        assert service._sanitize_css(None) is None
        assert service._sanitize_css("") == ""

    def test_sanitize_css_blocks_expression(self, service, db):
        with pytest.raises(ComponentSecurityError):
            service._sanitize_css("x { width: expression(alert(1)); }")

    def test_validate_js_empty_returns_empty(self, service, db):
        assert service._validate_js("") == ""

    def test_validate_js_blocks_localstorage(self, service, db):
        with pytest.raises(ComponentSecurityError):
            service._validate_js("localStorage.setItem('x', 1)")

    def test_validate_js_blocks_innerhtml_assignment(self, service, db):
        with pytest.raises(ComponentSecurityError):
            service._validate_js("el.innerHTML = '<b>x</b>'")

    def test_validate_js_clean_passes(self, service, db):
        clean = "function add(a, b) { return a + b; }"
        assert service._validate_js(clean) == clean

    def test_validate_dependencies_empty_list_ok(self, service, db):
        # Empty list -> no iteration -> no raise.
        service._validate_dependencies([])

    def test_slugify(self, service, db):
        assert service._slugify("Hello World!") == "hello-world"
        assert service._slugify("  Multiple   Spaces  ") == "multiple-spaces"

    def test_generate_unique_slug_collision(self, service, db):
        service.create_component("u1", "My Comp", "<div>x</div>")
        # First collision -> suffix -1.
        assert service._generate_unique_slug("my-comp") == "my-comp-1"

    def test_component_security_error_str(self, db):
        err = ComponentSecurityError("bad", component_name="Widget", validation_reason="xss")
        s = str(err)
        assert "bad" in s
        assert "Widget" in s
        assert "xss" in s


# ===========================================================================
# BUG-HUNT (TDD) — failing tests written BEFORE the fix
# ===========================================================================
class TestBugs:
    def test_bug_update_renaming_to_existing_name_raises_integrityerror(self, service, db):
        """BUG: update_component has no duplicate-name check, so renaming a
        component to a name that already exists leaks a raw SQLAlchemy
        IntegrityError (HTTP 500) instead of a clean ValueError like
        create_component returns. Function: update_component (line ~411).
        """
        service.create_component("u1", "Existing", "<div>a</div>")
        other = service.create_component("u2", "Other", "<div>b</div>")
        # Renaming 'Other' (owned by u2) to 'Existing' must be rejected
        # gracefully with a ValueError, NOT raise IntegrityError.
        with pytest.raises(ValueError, match="already exists"):
            service.update_component(other["component_id"], "u2", name="Existing")

    def test_bug_avg_rendering_time_wrong_denominator(self, service, db):
        """BUG: get_component_usage_stats computes avg_rendering_time_ms as
        (sum of ALL rendering_time_ms values, including failed renders)
        divided by successful_renders. When renders fail but carry timing,
        the average is miscomputed, and when 0 renders succeed the timing
        data is silently discarded (reported as 0). The average should be
        over the records that actually HAVE a rendering_time_ms.
        Function: get_component_usage_stats (lines ~724-726).
        """
        created = service.create_component("u1", "AvgBug", "<div>x</div>")
        # Two FAILED renders, both carrying timing data.
        service.record_component_usage(
            created["component_id"], "c1", "u1",
            rendering_time_ms=100, error_message="boom",
        )
        service.record_component_usage(
            created["component_id"], "c1", "u1",
            rendering_time_ms=200, error_message="boom2",
        )
        stats = service.get_component_usage_stats(created["component_id"], "u1")
        # The two timed records average to 150.0 — NOT 0.
        assert stats["avg_rendering_time_ms"] == 150.0
