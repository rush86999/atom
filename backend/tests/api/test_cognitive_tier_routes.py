"""
Cognitive Tier Routes API Tests

Comprehensive tests for cognitive tier endpoints from api/cognitive_tier_routes.py.

Coverage:
- GET /api/v1/cognitive-tier/preferences/{workspace_id} - Get workspace tier preferences
- POST /api/v1/cognitive-tier/preferences/{workspace_id} - Create or update preferences
- PUT /api/v1/cognitive-tier/preferences/{workspace_id}/budget - Update budget settings
- DELETE /api/v1/cognitive-tier/preferences/{workspace_id} - Delete preferences
- GET /api/v1/cognitive-tier/estimate-cost - Estimate cost by tier
- GET /api/v1/cognitive-tier/compare-tiers - Compare all cognitive tiers

Target: 75%+ line coverage on cognitive_tier_routes.py (601 lines)
"""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.cognitive_tier_routes import router
from core.models import CognitiveTierPreference


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client(db_session: Session):
    """Create TestClient for cognitive tier routes with database dependency override."""
    from fastapi import FastAPI
    from core.database import get_db

    app = FastAPI()
    app.include_router(router)

    # Override the database dependency
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    yield TestClient(app)

    # Clean up override
    app.dependency_overrides.clear()


@pytest.fixture
def db_session():
    """Create database session with transaction rollback."""
    from core.database import Base, get_db
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import tempfile
    import os

    # Use file-based temp SQLite for tests
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False
    )

    # Store path for cleanup
    engine._test_db_path = db_path

    # Create tables
    try:
        Base.metadata.create_all(engine, checkfirst=True)
    except Exception:
        for table in Base.metadata.tables.values():
            try:
                table.create(engine, checkfirst=True)
            except Exception:
                continue

    # Create session
    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()

    yield session

    # Cleanup
    session.close()
    engine.dispose()
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def mock_preference(db_session: Session):
    """Create a test CognitiveTierPreference record."""
    pref_id = str(uuid.uuid4())
    workspace_id = f"workspace_{uuid.uuid4()}"

    preference = CognitiveTierPreference(
        id=pref_id,
        workspace_id=workspace_id,
        default_tier="standard",
        min_tier="micro",
        max_tier="complex",
        monthly_budget_cents=10000,
        max_cost_per_request_cents=50,
        enable_cache_aware_routing=True,
        enable_auto_escalation=False,
        enable_minimax_fallback=True,
        preferred_providers=["openai", "anthropic"],
        metadata_json={"custom_field": "custom_value"}
    )
    db_session.add(preference)
    db_session.commit()
    db_session.refresh(preference)

    return preference


# ============================================================================
# TestGetPreferences - GET /preferences/{workspace_id}
# ============================================================================

class TestGetPreferences:
    """Tests for GET /api/v1/cognitive-tier/preferences/{workspace_id}"""

    def test_get_preferences_default_when_none_exists(self, client: TestClient, db_session: Session):
        """Verify default values are returned when no preference exists (200 status)."""
        workspace_id = f"workspace_{uuid.uuid4()}"

        response = client.get(f"/api/v1/cognitive-tier/preferences/{workspace_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["workspace_id"] == workspace_id
        assert data["default_tier"] == "standard"
        assert data["min_tier"] is None
        assert data["max_tier"] is None
        assert data["monthly_budget_cents"] is None
        assert data["max_cost_per_request_cents"] is None
        assert data["enable_cache_aware_routing"] is True
        assert data["enable_auto_escalation"] is True
        assert data["enable_minimax_fallback"] is True
        assert data["preferred_providers"] == []
        assert data["metadata_json"] is None
        assert data["id"] == ""
        assert data["created_at"] == ""
        assert data["updated_at"] is None

    def test_get_preferences_returns_existing_preference(self, client: TestClient, mock_preference: CognitiveTierPreference):
        """Verify existing preference is returned with all fields."""
        workspace_id = mock_preference.workspace_id

        response = client.get(f"/api/v1/cognitive-tier/preferences/{workspace_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == mock_preference.id
        assert data["workspace_id"] == mock_preference.workspace_id
        assert data["default_tier"] == "standard"
        assert data["min_tier"] == "micro"
        assert data["max_tier"] == "complex"
        assert data["monthly_budget_cents"] == 10000
        assert data["max_cost_per_request_cents"] == 50
        assert data["enable_cache_aware_routing"] is True
        assert data["enable_auto_escalation"] is False
        assert data["enable_minimax_fallback"] is True
        assert data["preferred_providers"] == ["openai", "anthropic"]
        assert data["metadata_json"]["custom_field"] == "custom_value"
        assert data["created_at"] is not None
        # updated_at can be None for new records

    def test_get_preferences_with_full_preference_data(self, client: TestClient, db_session: Session):
        """Test with all preference fields populated."""
        pref_id = str(uuid.uuid4())
        workspace_id = f"workspace_{uuid.uuid4()}"

        preference = CognitiveTierPreference(
            id=pref_id,
            workspace_id=workspace_id,
            default_tier="versatile",
            min_tier="standard",
            max_tier="heavy",
            monthly_budget_cents=50000,
            max_cost_per_request_cents=100,
            enable_cache_aware_routing=False,
            enable_auto_escalation=True,
            enable_minimax_fallback=False,
            preferred_providers=["openai"],
            metadata_json={"setting1": "value1", "setting2": "value2"}
        )
        db_session.add(preference)
        db_session.commit()
        db_session.refresh(preference)

        response = client.get(f"/api/v1/cognitive-tier/preferences/{workspace_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["default_tier"] == "versatile"
        assert data["min_tier"] == "standard"
        assert data["max_tier"] == "heavy"
        assert data["monthly_budget_cents"] == 50000
        assert data["max_cost_per_request_cents"] == 100
        assert data["enable_cache_aware_routing"] is False
        assert data["enable_auto_escalation"] is True
        assert data["enable_minimax_fallback"] is False
        assert data["preferred_providers"] == ["openai"]
        assert data["metadata_json"]["setting1"] == "value1"
        assert data["metadata_json"]["setting2"] == "value2"


# ============================================================================
# TestCreateOrUpdatePreferences - POST /preferences/{workspace_id}
# ============================================================================

class TestCreateOrUpdatePreferences:
    """Tests for POST /api/v1/cognitive-tier/preferences/{workspace_id}"""

    # Success cases

    def test_create_new_preference_success(self, client: TestClient, db_session: Session):
        """POST with valid data creates new preference (201 status or 200)."""
        workspace_id = f"workspace_{uuid.uuid4()}"

        request_data = {
            "default_tier": "standard",
            "monthly_budget_cents": 10000,
            "enable_cache_aware_routing": True
        }

        response = client.post(
            f"/api/v1/cognitive-tier/preferences/{workspace_id}",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["workspace_id"] == workspace_id
        assert data["default_tier"] == "standard"
        assert data["monthly_budget_cents"] == 10000
        assert data["enable_cache_aware_routing"] is True
        assert data["id"] is not None
        assert data["created_at"] is not None

    def test_update_existing_preference_success(self, client: TestClient, mock_preference: CognitiveTierPreference):
        """POST to existing workspace_id updates preference."""
        workspace_id = mock_preference.workspace_id

        request_data = {
            "default_tier": "versatile",
            "monthly_budget_cents": 20000,
            "enable_cache_aware_routing": False
        }

        response = client.post(
            f"/api/v1/cognitive-tier/preferences/{workspace_id}",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["workspace_id"] == workspace_id
        assert data["default_tier"] == "versatile"
        assert data["monthly_budget_cents"] == 20000
        assert data["enable_cache_aware_routing"] is False
        # Original fields should be preserved
        assert data["min_tier"] == "micro"
        assert data["max_tier"] == "complex"

    def test_create_preference_with_all_fields(self, client: TestClient, db_session: Session):
        """Test all optional fields (min_tier, max_tier, budgets, providers, flags)."""
        workspace_id = f"workspace_{uuid.uuid4()}"

        request_data = {
            "default_tier": "versatile",
            "min_tier": "micro",
            "max_tier": "complex",
            "monthly_budget_cents": 50000,
            "max_cost_per_request_cents": 100,
            "enable_cache_aware_routing": True,
            "enable_auto_escalation": True,
            "enable_minimax_fallback": True,
            "preferred_providers": ["openai", "anthropic", "deepseek"]
        }

        response = client.post(
            f"/api/v1/cognitive-tier/preferences/{workspace_id}",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["default_tier"] == "versatile"
        assert data["min_tier"] == "micro"
        assert data["max_tier"] == "complex"
        assert data["monthly_budget_cents"] == 50000
        assert data["max_cost_per_request_cents"] == 100
        assert data["enable_cache_aware_routing"] is True
        assert data["enable_auto_escalation"] is True
        assert data["enable_minimax_fallback"] is True
        assert data["preferred_providers"] == ["openai", "anthropic", "deepseek"]

    # Validation error cases (400 Bad Request)

    def test_invalid_default_tier_returns_400(self, client: TestClient, db_session: Session):
        """POST with invalid tier value (e.g., 'invalid_tier') returns 400."""
        workspace_id = f"workspace_{uuid.uuid4()}"

        request_data = {
            "default_tier": "invalid_tier"
        }

        response = client.post(
            f"/api/v1/cognitive-tier/preferences/{workspace_id}",
            json=request_data
        )

        assert response.status_code == 400
        assert "Invalid default_tier" in response.json()["detail"]

    def test_invalid_min_tier_returns_400(self, client: TestClient, db_session: Session):
        """POST with invalid min_tier value returns 400."""
        workspace_id = f"workspace_{uuid.uuid4()}"

        request_data = {
            "default_tier": "standard",
            "min_tier": "wrong_tier"
        }

        response = client.post(
            f"/api/v1/cognitive-tier/preferences/{workspace_id}",
            json=request_data
        )

        assert response.status_code == 400
        assert "Invalid min_tier" in response.json()["detail"]

    def test_invalid_max_tier_returns_400(self, client: TestClient, db_session: Session):
        """POST with invalid max_tier value returns 400."""
        workspace_id = f"workspace_{uuid.uuid4()}"

        request_data = {
            "default_tier": "standard",
            "max_tier": "bad_tier"
        }

        response = client.post(
            f"/api/v1/cognitive-tier/preferences/{workspace_id}",
            json=request_data
        )

        assert response.status_code == 400
        assert "Invalid max_tier" in response.json()["detail"]

    def test_negative_monthly_budget_returns_400(self, client: TestClient, db_session: Session):
        """POST with monthly_budget_cents=-1 returns 400."""
        workspace_id = f"workspace_{uuid.uuid4()}"

        request_data = {
            "default_tier": "standard",
            "monthly_budget_cents": -1
        }

        response = client.post(
            f"/api/v1/cognitive-tier/preferences/{workspace_id}",
            json=request_data
        )

        assert response.status_code == 400
        assert "monthly_budget_cents must be non-negative" in response.json()["detail"]

    def test_negative_max_cost_per_request_returns_400(self, client: TestClient, db_session: Session):
        """POST with max_cost_per_request_cents=-1 returns 400."""
        workspace_id = f"workspace_{uuid.uuid4()}"

        request_data = {
            "default_tier": "standard",
            "max_cost_per_request_cents": -1
        }

        response = client.post(
            f"/api/v1/cognitive-tier/preferences/{workspace_id}",
            json=request_data
        )

        assert response.status_code == 400
        assert "max_cost_per_request_cents must be non-negative" in response.json()["detail"]

    # Edge cases

    def test_empty_preferred_providers_list(self, client: TestClient, db_session: Session):
        """Verify empty list is handled correctly."""
        workspace_id = f"workspace_{uuid.uuid4()}"

        request_data = {
            "default_tier": "standard",
            "preferred_providers": []
        }

        response = client.post(
            f"/api/v1/cognitive-tier/preferences/{workspace_id}",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["preferred_providers"] == []

    def test_null_optional_fields(self, client: TestClient, db_session: Session):
        """Verify None values for optional fields."""
        workspace_id = f"workspace_{uuid.uuid4()}"

        request_data = {
            "default_tier": "standard",
            "min_tier": None,
            "max_tier": None,
            "monthly_budget_cents": None,
            "max_cost_per_request_cents": None
        }

        response = client.post(
            f"/api/v1/cognitive-tier/preferences/{workspace_id}",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["min_tier"] is None
        assert data["max_tier"] is None
        assert data["monthly_budget_cents"] is None
        assert data["max_cost_per_request_cents"] is None


# ============================================================================
# TestUpdateBudget - PUT /preferences/{workspace_id}/budget
# ============================================================================

class TestUpdateBudget:
    """Tests for PUT /api/v1/cognitive-tier/preferences/{workspace_id}/budget"""

    # Success cases

    def test_update_monthly_budget_success(self, client: TestClient, mock_preference: CognitiveTierPreference):
        """Update monthly_budget_cents field only."""
        workspace_id = mock_preference.workspace_id

        request_data = {
            "monthly_budget_cents": 25000
        }

        response = client.put(
            f"/api/v1/cognitive-tier/preferences/{workspace_id}/budget",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["monthly_budget_cents"] == 25000
        # Other fields unchanged
        assert data["max_cost_per_request_cents"] == 50
        assert data["default_tier"] == "standard"

    def test_update_max_cost_per_request_success(self, client: TestClient, mock_preference: CognitiveTierPreference):
        """Update max_cost_per_request_cents field only."""
        workspace_id = mock_preference.workspace_id

        request_data = {
            "max_cost_per_request_cents": 200
        }

        response = client.put(
            f"/api/v1/cognitive-tier/preferences/{workspace_id}/budget",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["max_cost_per_request_cents"] == 200
        # Other fields unchanged
        assert data["monthly_budget_cents"] == 10000

    def test_update_both_budget_fields_success(self, client: TestClient, mock_preference: CognitiveTierPreference):
        """Update both budget fields."""
        workspace_id = mock_preference.workspace_id

        request_data = {
            "monthly_budget_cents": 30000,
            "max_cost_per_request_cents": 150
        }

        response = client.put(
            f"/api/v1/cognitive-tier/preferences/{workspace_id}/budget",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["monthly_budget_cents"] == 30000
        assert data["max_cost_per_request_cents"] == 150

    def test_create_default_preference_when_none_exists(self, client: TestClient, db_session: Session):
        """PUT on non-existent preference creates default."""
        workspace_id = f"workspace_{uuid.uuid4()}"

        request_data = {
            "monthly_budget_cents": 5000
        }

        response = client.put(
            f"/api/v1/cognitive-tier/preferences/{workspace_id}/budget",
            json=request_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["workspace_id"] == workspace_id
        assert data["default_tier"] == "standard"  # Default tier
        assert data["monthly_budget_cents"] == 5000

    # Validation error cases

    def test_negative_monthly_budget_returns_400(self, client: TestClient, mock_preference: CognitiveTierPreference):
        """Negative monthly_budget_cents returns 400."""
        workspace_id = mock_preference.workspace_id

        request_data = {
            "monthly_budget_cents": -100
        }

        response = client.put(
            f"/api/v1/cognitive-tier/preferences/{workspace_id}/budget",
            json=request_data
        )

        assert response.status_code == 400
        assert "monthly_budget_cents must be non-negative" in response.json()["detail"]

    def test_negative_max_cost_per_request_returns_400(self, client: TestClient, mock_preference: CognitiveTierPreference):
        """Negative max_cost_per_request_cents returns 400."""
        workspace_id = mock_preference.workspace_id

        request_data = {
            "max_cost_per_request_cents": -50
        }

        response = client.put(
            f"/api/v1/cognitive-tier/preferences/{workspace_id}/budget",
            json=request_data
        )

        assert response.status_code == 400
        assert "max_cost_per_request_cents must be non-negative" in response.json()["detail"]


# ============================================================================
# TestDeletePreferences - DELETE /preferences/{workspace_id}
# ============================================================================

class TestDeletePreferences:
    """Tests for DELETE /api/v1/cognitive-tier/preferences/{workspace_id}"""

    # Success cases

    def test_delete_existing_preference_success(self, client: TestClient, mock_preference: CognitiveTierPreference, db_session: Session):
        """DELETE removes preference, returns success message."""
        workspace_id = mock_preference.workspace_id

        response = client.delete(f"/api/v1/cognitive-tier/preferences/{workspace_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "deleted" in data["message"].lower()
        assert data["workspace_id"] == workspace_id

        # Verify it's deleted
        deleted_pref = db_session.query(CognitiveTierPreference).filter_by(
            workspace_id=workspace_id
        ).first()
        assert deleted_pref is None

    def test_delete_nonexistent_preference_success(self, client: TestClient, db_session: Session):
        """DELETE on non-existent preference returns success (idempotent)."""
        workspace_id = f"workspace_{uuid.uuid4()}"

        response = client.delete(f"/api/v1/cognitive-tier/preferences/{workspace_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["workspace_id"] == workspace_id

    # Response verification

    def test_delete_response_structure(self, client: TestClient, mock_preference: CognitiveTierPreference):
        """Verify response has success=True, message, workspace_id fields."""
        workspace_id = mock_preference.workspace_id

        response = client.delete(f"/api/v1/cognitive-tier/preferences/{workspace_id}")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "message" in data
        assert "workspace_id" in data
        assert isinstance(data["success"], bool)
        assert isinstance(data["message"], str)
        assert isinstance(data["workspace_id"], str)
        assert data["success"] is True
