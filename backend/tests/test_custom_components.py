"""
Custom Canvas Components Tests

Comprehensive test suite for custom HTML/CSS/JS components including:
- Component CRUD operations
- Security validation (HTML, CSS, JS)
- Governance integration
- Version control and rollback
- Usage tracking
"""

import pytest
import uuid
from datetime import datetime
from sqlalchemy.orm import Session

from core.models import (
    CustomComponent,
    ComponentVersion,
    ComponentUsage,
    User,
    AgentRegistry
)
from core.custom_components_service import (
    CustomComponentsService,
    ComponentSecurityError
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db():
    """Create a test database session."""
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_user(db):
    """Create a test user."""
    user_id = f"user-{uuid.uuid4()}"
    user = User(
        id=user_id,
        email=f"test-{uuid.uuid4()}@example.com",
        first_name="Test",
        last_name="User"
    )
    db.add(user)
    db.commit()
    db.expunge(user)
    yield user
    db.query(ComponentUsage).filter(ComponentUsage.user_id == user_id).delete(synchronize_session=False)
    db.query(CustomComponent).filter(CustomComponent.user_id == user_id).delete(synchronize_session=False)
    db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
    db.commit()


@pytest.fixture
def autonomous_agent(db):
    """Create an AUTONOMOUS agent (can create JS components)."""
    agent_id = f"agent-autonomous-{uuid.uuid4()}"
    agent = AgentRegistry(
        id=agent_id,
        name="Autonomous Agent",
        category="Operations",
        module_path="agents.autonomous_agent",
        class_name="AutonomousAgent",
        status="AUTONOMOUS",
        confidence_score=0.95
    )
    db.add(agent)
    db.commit()
    db.expunge(agent)
    yield agent
    db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).delete(synchronize_session=False)
    db.commit()


@pytest.fixture
def supervised_agent(db):
    """Create a SUPERVISED agent (cannot create JS components)."""
    agent_id = f"agent-supervised-{uuid.uuid4()}"
    agent = AgentRegistry(
        id=agent_id,
        name="Supervised Agent",
        category="Operations",
        module_path="agents.supervised_agent",
        class_name="SupervisedAgent",
        status="SUPERVISED",
        confidence_score=0.80
    )
    db.add(agent)
    db.commit()
    db.expunge(agent)
    yield agent
    db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).delete(synchronize_session=False)
    db.commit()


# ============================================================================
# Component Creation Tests
# ============================================================================

class TestComponentCreation:
    """Test component creation with security validation."""

    def test_create_html_css_component(self, db, test_user):
        """Test creating component with HTML and CSS only."""
        service = CustomComponentsService(db)

        result = service.create_component(
            user_id=test_user.id,
            name="Test Widget",
            html_content="<div class='widget'>Hello World</div>",
            css_content=".widget { color: blue; }",
            description="A simple test widget"
        )

        assert "error" not in result
        assert result["name"] == "Test Widget"
        assert result["slug"] == "test-widget"
        assert result["has_js"] is False
        assert result["is_public"] is False

    def test_create_component_with_js_autonomous(self, db, test_user, autonomous_agent):
        """Test creating JS component with AUTONOMOUS agent."""
        service = CustomComponentsService(db)

        result = service.create_component(
            user_id=test_user.id,
            name="Interactive Widget",
            html_content="<div id='app'>Loading...</div>",
            css_content="#app { padding: 20px; }",
            js_content="document.getElementById('app').textContent = 'Ready!';",
            agent_id=autonomous_agent.id
        )

        assert "error" not in result
        assert result["has_js"] is True
        assert result["name"] == "Interactive Widget"

    def test_create_component_with_js_supervised_fails(self, db, test_user, supervised_agent):
        """Test that SUPERVISED agents cannot create JS components."""
        service = CustomComponentsService(db)

        with pytest.raises(ComponentSecurityError) as exc_info:
            service.create_component(
                user_id=test_user.id,
                name="Bad Widget",
                html_content="<div>Test</div>",
                js_content="console.log('test');",
                agent_id=supervised_agent.id
            )

        assert "AUTONOMOUS" in str(exc_info.value)

    def test_create_component_blocks_dangerous_html(self, db, test_user):
        """Test that dangerous HTML patterns are blocked."""
        service = CustomComponentsService(db)

        with pytest.raises(ComponentSecurityError) as exc_info:
            service.create_component(
                user_id=test_user.id,
                name="XSS Widget",
                html_content="<div><script>alert('XSS')</script></div>"
            )

        assert "dangerous" in str(exc_info.value).lower()

    def test_create_component_blocks_dangerous_js(self, db, test_user, autonomous_agent):
        """Test that dangerous JavaScript patterns are blocked."""
        service = CustomComponentsService(db)

        with pytest.raises(ComponentSecurityError) as exc_info:
            service.create_component(
                user_id=test_user.id,
                name="Eval Widget",
                html_content="<div>Test</div>",
                js_content="eval('malicious code');",
                agent_id=autonomous_agent.id
            )

        assert "blocked" in str(exc_info.value).lower()

    def test_create_component_with_dependencies(self, db, test_user):
        """Test creating component with external dependencies."""
        service = CustomComponentsService(db)

        result = service.create_component(
            user_id=test_user.id,
            name="Chart Widget",
            html_content="<div id='chart'></div>",
            dependencies=["https://cdn.jsdelivr.net/npm/chart.js"]
        )

        assert "error" not in result
        assert result["name"] == "Chart Widget"

    def test_create_component_blocks_bad_dependencies(self, db, test_user):
        """Test that non-whitelisted dependencies are blocked."""
        service = CustomComponentsService(db)

        with pytest.raises(ComponentSecurityError) as exc_info:
            service.create_component(
                user_id=test_user.id,
                name="Bad Dep Widget",
                html_content="<div>Test</div>",
                dependencies=["https://evil.com/malware.js"]
            )

        assert "not in allowed list" in str(exc_info.value)

    def test_create_public_component(self, db, test_user):
        """Test creating a public component."""
        service = CustomComponentsService(db)

        result = service.create_component(
            user_id=test_user.id,
            name="Public Widget",
            html_content="<div>Public</div>",
            is_public=True
        )

        assert "error" not in result
        assert result["is_public"] is True

    def test_unique_slug_generation(self, db, test_user):
        """Test that unique slugs are generated for duplicate names."""
        service = CustomComponentsService(db)

        result1 = service.create_component(
            user_id=test_user.id,
            name="My Widget",
            html_content="<div>First</div>"
        )

        result2 = service.create_component(
            user_id=test_user.id,
            name="My Widget",
            html_content="<div>Second</div>"
        )

        assert result1["slug"] == "my-widget"
        assert result2["slug"] == "my-widget-1"


# ============================================================================
# Component Retrieval Tests
# ============================================================================

class TestComponentRetrieval:
    """Test component retrieval and listing."""

    def test_get_component_by_id(self, db, test_user):
        """Test retrieving component by ID."""
        service = CustomComponentsService(db)

        # Create component
        created = service.create_component(
            user_id=test_user.id,
            name="Test Component",
            html_content="<div>Test</div>"
        )

        # Get component
        result = service.get_component(
            component_id=created["component_id"],
            user_id=test_user.id
        )

        assert "error" not in result
        assert result["name"] == "Test Component"

    def test_get_component_by_slug(self, db, test_user):
        """Test retrieving component by slug."""
        service = CustomComponentsService(db)

        # Create component
        created = service.create_component(
            user_id=test_user.id,
            name="Test Widget",
            html_content="<div>Test</div>"
        )

        # Get by slug
        result = service.get_component(
            slug=created["slug"],
            user_id=test_user.id
        )

        assert "error" not in result
        assert result["slug"] == "test-widget"

    def test_get_component_js_only_for_owner(self, db, test_user, autonomous_agent):
        """Test that JS content is only returned to owner."""
        service = CustomComponentsService(db)

        # Create component with JS
        created = service.create_component(
            user_id=test_user.id,
            name="Secret JS",
            html_content="<div>Test</div>",
            js_content="console.log('secret');",
            agent_id=autonomous_agent.id
        )

        # Owner gets JS
        result_owner = service.get_component(
            component_id=created["component_id"],
            user_id=test_user.id
        )

        assert result_owner["js_content"] is not None

        # Different user (if public) would not get JS
        # For now, just verify owner gets it
        assert result_owner["js_content"] == "console.log('secret');"

    def test_list_components_includes_public(self, db, test_user):
        """Test that listing includes user's own + public components."""
        service = CustomComponentsService(db)

        # Create private component
        service.create_component(
            user_id=test_user.id,
            name="Private Widget",
            html_content="<div>Private</div>",
            is_public=False
        )

        # Create public component
        service.create_component(
            user_id=test_user.id,
            name="Public Widget",
            html_content="<div>Public</div>",
            is_public=True
        )

        # List
        result = service.list_components(user_id=test_user.id)

        assert "error" not in result
        assert result["total"] == 2

    def test_list_components_filter_by_category(self, db, test_user):
        """Test filtering components by category."""
        service = CustomComponentsService(db)

        # Create components in different categories
        service.create_component(
            user_id=test_user.id,
            name="Chart Widget",
            html_content="<div>Chart</div>",
            category="chart"
        )

        service.create_component(
            user_id=test_user.id,
            name="Form Widget",
            html_content="<div>Form</div>",
            category="form"
        )

        # Filter by category
        result = service.list_components(
            user_id=test_user.id,
            category="chart"
        )

        assert result["total"] == 1
        assert result["components"][0]["name"] == "Chart Widget"


# ============================================================================
# Component Update Tests
# ============================================================================

class TestComponentUpdate:
    """Test component updates and versioning."""

    def test_update_component(self, db, test_user):
        """Test updating a component."""
        service = CustomComponentsService(db)

        # Create component
        created = service.create_component(
            user_id=test_user.id,
            name="Original Name",
            html_content="<div>Original</div>"
        )

        # Update
        result = service.update_component(
            component_id=created["component_id"],
            user_id=test_user.id,
            name="Updated Name",
            html_content="<div>Updated</div>"
        )

        assert "error" not in result
        assert result["version"] == 2

    def test_update_component_creates_version(self, db, test_user):
        """Test that updates create new version records."""
        service = CustomComponentsService(db)

        # Create component
        created = service.create_component(
            user_id=test_user.id,
            name="Versioned Widget",
            html_content="<div>v1</div>"
        )

        # Update
        service.update_component(
            component_id=created["component_id"],
            user_id=test_user.id,
            html_content="<div>v2</div>"
        )

        # Check versions
        versions = service.get_component_versions(
            component_id=created["component_id"],
            user_id=test_user.id
        )

        assert versions["total_versions"] == 2
        assert versions["current_version"] == 2

    def test_update_non_owner_fails(self, db, test_user):
        """Test that only owners can update components."""
        service = CustomComponentsService(db)

        # Create component
        created = service.create_component(
            user_id=test_user.id,
            name="Protected Widget",
            html_content="<div>Protected</div>"
        )

        # Try to update as different user
        result = service.update_component(
            component_id=created["component_id"],
            user_id="different-user-id",
            name="Hacked"
        )

        assert "error" in result
        assert "Access denied" in result["error"]


# ============================================================================
# Component Deletion Tests
# ============================================================================

class TestComponentDeletion:
    """Test component soft deletion."""

    def test_delete_component(self, db, test_user):
        """Test soft deleting a component."""
        service = CustomComponentsService(db)

        # Create component
        created = service.create_component(
            user_id=test_user.id,
            name="To Delete",
            html_content="<div>Delete me</div>"
        )

        # Delete
        result = service.delete_component(
            component_id=created["component_id"],
            user_id=test_user.id
        )

        assert "error" not in result
        assert result["status"] == "deleted"

        # Verify it's soft deleted (not in active list)
        list_result = service.list_components(user_id=test_user.id)
        assert list_result["total"] == 0


# ============================================================================
# Version Control Tests
# ============================================================================

class TestVersionControl:
    """Test version control and rollback."""

    def test_get_version_history(self, db, test_user):
        """Test retrieving version history."""
        service = CustomComponentsService(db)

        # Create component
        created = service.create_component(
            user_id=test_user.id,
            name="Versioned Widget",
            html_content="<div>v1</div>"
        )

        # Update to create v2
        service.update_component(
            component_id=created["component_id"],
            user_id=test_user.id,
            html_content="<div>v2</div>"
        )

        # Get versions
        result = service.get_component_versions(
            component_id=created["component_id"],
            user_id=test_user.id
        )

        assert "error" not in result
        assert result["total_versions"] == 2

    def test_rollback_component(self, db, test_user):
        """Test rolling back to a previous version."""
        service = CustomComponentsService(db)

        # Create component
        created = service.create_component(
            user_id=test_user.id,
            name="Rollback Widget",
            html_content="<div>v1</div>"
        )

        # Update to v2
        service.update_component(
            component_id=created["component_id"],
            user_id=test_user.id,
            html_content="<div>v2</div>"
        )

        # Rollback to v1
        result = service.rollback_component(
            component_id=created["component_id"],
            target_version=1,
            user_id=test_user.id
        )

        assert "error" not in result
        assert result["previous_version"] == 1
        assert result["new_version"] == 3  # v3 has content from v1


# ============================================================================
# Usage Tracking Tests
# ============================================================================

class TestUsageTracking:
    """Test component usage tracking."""

    def test_record_usage(self, db, test_user):
        """Test recording component usage."""
        service = CustomComponentsService(db)

        # Create component
        created = service.create_component(
            user_id=test_user.id,
            name="Tracked Widget",
            html_content="<div>Track me</div>"
        )

        # Record usage
        result = service.record_component_usage(
            component_id=created["component_id"],
            canvas_id="canvas-123",
            user_id=test_user.id,
            rendering_time_ms=50
        )

        assert "error" not in result
        assert result["status"] == "recorded"

    def test_get_usage_stats(self, db, test_user):
        """Test getting usage statistics."""
        service = CustomComponentsService(db)

        # Create component
        created = service.create_component(
            user_id=test_user.id,
            name="Popular Widget",
            html_content="<div>Popular</div>"
        )

        # Record multiple usages
        for i in range(3):
            service.record_component_usage(
                component_id=created["component_id"],
                canvas_id=f"canvas-{i}",
                user_id=test_user.id,
                rendering_time_ms=50 + i
            )

        # Get stats
        result = service.get_component_usage_stats(
            component_id=created["component_id"],
            user_id=test_user.id
        )

        assert "error" not in result
        assert result["total_renders"] == 3
        assert result["success_rate"] == 1.0
        assert result["avg_rendering_time_ms"] > 0


# ============================================================================
# Integration Tests
# ============================================================================

class TestCustomComponentsIntegration:
    """Integration tests for complete workflows."""

    def test_full_component_lifecycle(self, db, test_user, autonomous_agent):
        """Test complete component lifecycle."""
        service = CustomComponentsService(db)

        # 1. Create component
        created = service.create_component(
            user_id=test_user.id,
            name="Lifecycle Widget",
            html_content="<div id='app'>Loading...</div>",
            css_content="#app { color: blue; }",
            js_content="document.getElementById('app').textContent = 'Ready!';",
            description="Full lifecycle test",
            category="widget",
            is_public=True,
            agent_id=autonomous_agent.id
        )

        component_id = created["component_id"]

        # 2. Get component
        retrieved = service.get_component(
            component_id=component_id,
            user_id=test_user.id
        )

        assert retrieved["name"] == "Lifecycle Widget"
        assert retrieved["has_js"] is True

        # 3. Update component
        updated = service.update_component(
            component_id=component_id,
            user_id=test_user.id,
            description="Updated description"
        )

        assert updated["version"] == 2

        # 4. Record usage
        service.record_component_usage(
            component_id=component_id,
            canvas_id="canvas-test",
            user_id=test_user.id,
            rendering_time_ms=75
        )

        # 5. Get stats
        stats = service.get_component_usage_stats(
            component_id=component_id,
            user_id=test_user.id
        )

        assert stats["total_renders"] == 1

        # 6. Delete
        deleted = service.delete_component(
            component_id=component_id,
            user_id=test_user.id
        )

        assert deleted["status"] == "deleted"
