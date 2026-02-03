"""
User Workflow Templates API Tests
Test suite for database-backed template system
"""

import pytest
from fastapi.testclient import TestClient
from main import app
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base, get_db

# Test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_templates.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session():
    """Create a fresh database session for each test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    """Create a test client with database dependency override"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestTemplateCreation:
    """Test template creation endpoints"""

    def test_create_template(self, client):
        """Test creating a new template"""
        request_data = {
            "name": "Test Template",
            "description": "A test template for unit testing",
            "category": "automation",
            "complexity": "beginner",
            "tags": ["test", "automation"],
            "template_json": {
                "nodes": [],
                "edges": []
            },
            "inputs_schema": [],
            "steps_schema": [],
            "output_schema": {},
            "estimated_duration_seconds": 60,
            "is_public": False
        }

        response = client.post(
            "/api/user/templates?user_id=test-user-123",
            json=request_data
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Template"
        assert data["template_id"] is not None
        assert data["author_id"] == "test-user-123"
        assert data["version"] == "1.0.0"

    def test_create_template_validation_error(self, client):
        """Test creating a template with invalid data"""
        request_data = {
            "name": "",  # Empty name should fail validation
            "description": "Test",
            "category": "automation",
            "complexity": "beginner",
            "template_json": {}
        }

        response = client.post(
            "/api/user/templates?user_id=test-user-123",
            json=request_data
        )

        assert response.status_code == 422  # Validation error


class TestTemplateRetrieval:
    """Test template retrieval endpoints"""

    def test_list_templates(self, client):
        """Test listing all templates"""
        # Create a few templates first
        for i in range(3):
            client.post(
                "/api/user/templates?user_id=test-user-123",
                json={
                    "name": f"Template {i}",
                    "description": f"Test template {i}",
                    "category": "automation",
                    "complexity": "beginner",
                    "template_json": {}
                }
            )

        response = client.get("/api/user/templates")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 3

    def test_get_template_by_id(self, client):
        """Test getting a specific template"""
        # Create a template
        create_response = client.post(
            "/api/user/templates?user_id=test-user-123",
            json={
                "name": "Get Test Template",
                "description": "Template for get test",
                "category": "automation",
                "complexity": "beginner",
                "template_json": {}
            }
        )
        template_id = create_response.json()["template_id"]

        # Get the template
        response = client.get(f"/api/user/templates/{template_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["template_id"] == template_id
        assert data["name"] == "Get Test Template"

    def test_get_nonexistent_template(self, client):
        """Test getting a template that doesn't exist"""
        response = client.get("/api/user/templates/nonexistent-template")
        assert response.status_code == 404


class TestTemplateUpdate:
    """Test template update endpoints"""

    def test_update_template(self, client):
        """Test updating a template"""
        # Create a template
        create_response = client.post(
            "/api/user/templates?user_id=test-user-123",
            json={
                "name": "Update Test",
                "description": "Original description",
                "category": "automation",
                "complexity": "beginner",
                "template_json": {}
            }
        )
        template_id = create_response.json()["template_id"]

        # Update the template
        update_data = {
            "description": "Updated description",
            "change_description": "Improved description"
        }
        response = client.put(
            f"/api/user/templates/{template_id}?user_id=test-user-123",
            json=update_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description"
        assert data["version"] != "1.0.0"  # Version should be incremented

    def test_update_unauthorized_template(self, client):
        """Test updating a template you don't own"""
        # Create a template as user-1
        create_response = client.post(
            "/api/user/templates?user_id=user-1",
            json={
                "name": "Protected Template",
                "description": "Cannot be updated by others",
                "category": "automation",
                "complexity": "beginner",
                "template_json": {}
            }
        )
        template_id = create_response.json()["template_id"]

        # Try to update as user-2
        response = client.put(
            f"/api/user/templates/{template_id}?user_id=user-2",
            json={"description": "Hacked description"}
        )

        assert response.status_code == 403  # Forbidden


class TestTemplateDeletion:
    """Test template deletion endpoints"""

    def test_delete_template(self, client):
        """Test deleting a template"""
        # Create a template
        create_response = client.post(
            "/api/user/templates?user_id=test-user-123",
            json={
                "name": "Delete Test",
                "description": "Template to delete",
                "category": "automation",
                "complexity": "beginner",
                "template_json": {}
            }
        )
        template_id = create_response.json()["template_id"]

        # Delete the template
        response = client.delete(
            f"/api/user/templates/{template_id}?user_id=test-user-123"
        )

        assert response.status_code == 204

        # Verify it's gone
        get_response = client.get(f"/api/user/templates/{template_id}")
        assert get_response.status_code == 404


class TestTemplateDuplication:
    """Test template duplication/forking"""

    def test_duplicate_template(self, client):
        """Test duplicating a template"""
        # Create original template as user-1
        create_response = client.post(
            "/api/user/templates?user_id=user-1",
            json={
                "name": "Original Template",
                "description": "To be duplicated",
                "category": "automation",
                "complexity": "beginner",
                "template_json": {},
                "is_public": True
            }
        )
        original_id = create_response.json()["template_id"]

        # Duplicate as user-2
        duplicate_response = client.post(
            f"/api/user/templates/{original_id}/duplicate?user_id=user-2",
            json={
                "name": "Forked Template"
            }
        )

        assert duplicate_response.status_code == 201
        data = duplicate_response.json()
        assert data["template_id"] != original_id
        assert data["name"] == "Forked Template"
        assert data["author_id"] == "user-2"
        assert data["parent_template_id"] == original_id


class TestTemplateStatistics:
    """Test template statistics endpoint"""

    def test_get_statistics(self, client):
        """Test getting user's template statistics"""
        # Create some templates
        user_id = "stats-user-123"
        for i in range(3):
            client.post(
                f"/api/user/templates?user_id={user_id}",
                json={
                    "name": f"Stats Template {i}",
                    "description": f"Template {i}",
                    "category": "automation",
                    "complexity": "beginner",
                    "template_json": {},
                    "is_public": i % 2 == 0  # Alternate public/private
                }
            )

        response = client.get(f"/api/user/templates/stats?user_id={user_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["total_templates"] == 3
        assert "public_templates" in data
        assert "private_templates" in data
        assert "average_rating" in data


class TestTemplatePublishing:
    """Test template publishing to marketplace"""

    def test_publish_template(self, client):
        """Test publishing a template"""
        # Create a private template
        create_response = client.post(
            "/api/user/templates?user_id=test-user-123",
            json={
                "name": "Publish Test",
                "description": "Template to publish",
                "category": "automation",
                "complexity": "beginner",
                "template_json": {},
                "is_public": False
            }
        )
        template_id = create_response.json()["template_id"]

        # Publish it
        publish_response = client.post(
            f"/api/user/templates/{template_id}/publish?user_id=test-user-123",
            json={
                "visibility": "public"
            }
        )

        assert publish_response.status_code == 200
        data = publish_response.json()
        assert data["is_public"] is True


class TestTemplateRating:
    """Test template rating functionality"""

    def test_rate_template(self, client):
        """Test rating a template"""
        # Create a template
        create_response = client.post(
            "/api/user/templates?user_id=test-user-123",
            json={
                "name": "Rating Test",
                "description": "Template to rate",
                "category": "automation",
                "complexity": "beginner",
                "template_json": {},
                "is_public": True
            }
        )
        template_id = create_response.json()["template_id"]

        # Rate it
        response = client.post(
            f"/api/user/templates/{template_id}/rate?rating=5"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["new_rating"] == 5.0
        assert data["rating_count"] == 1

        # Add another rating
        client.post(f"/api/user/templates/{template_id}/rate?rating=3")

        # Get updated template
        get_response = client.get(f"/api/user/templates/{template_id}")
        template_data = get_response.json()
        assert template_data["rating"] == 4.0  # (5 + 3) / 2
        assert template_data["rating_count"] == 2


class TestTemplateFiltering:
    """Test template filtering and search"""

    def test_filter_by_category(self, client):
        """Test filtering templates by category"""
        # Create templates in different categories
        client.post(
            "/api/user/templates?user_id=test-user-123",
            json={
                "name": "Data Template",
                "description": "Data processing",
                "category": "data_processing",
                "complexity": "beginner",
                "template_json": {},
                "is_public": True
            }
        )

        client.post(
            "/api/user/templates?user_id=test-user-123",
            json={
                "name": "Automation Template",
                "description": "Automation",
                "category": "automation",
                "complexity": "beginner",
                "template_json": {},
                "is_public": True
            }
        )

        # Filter by category
        response = client.get("/api/user/templates?category=data_processing")
        assert response.status_code == 200
        data = response.json()
        assert all(t["category"] == "data_processing" for t in data)

    def test_search_templates(self, client):
        """Test searching templates by name/description"""
        # Create templates
        client.post(
            "/api/user/templates?user_id=test-user-123",
            json={
                "name": "Email Marketing Template",
                "description": "Send marketing emails",
                "category": "automation",
                "complexity": "beginner",
                "template_json": {},
                "is_public": True
            }
        )

        # Search
        response = client.get("/api/user/templates?search=email")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        assert "email" in data[0]["name"].lower() or "email" in data[0]["description"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
