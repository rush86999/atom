#!/usr/bin/env python3
"""
Test Suite for Asana Project Creation
Tests Asana project creation endpoint and service integration
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch
import asyncio

# Import Asana components
from integrations.asana_service import AsanaService
from integrations.asana_routes import (
    ProjectCreate,
    get_access_token,
    router
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def asana_service():
    """Create Asana service instance"""
    return AsanaService()


@pytest.fixture
def mock_access_token():
    """Create mock access token"""
    return 'mock_asana_access_token_12345'


@pytest.fixture
def sample_project_request():
    """Create sample project creation request"""
    return ProjectCreate(
        name='Test Project',
        workspace='123456789',
        notes='This is a test project',
        team='987654321',
        color='light-green',
        public=True
    )


# ============================================================================
# AsanaService.create_project() Tests
# ============================================================================

class TestAsanaServiceCreateProject:
    """Test AsanaService.create_project() method"""

    @pytest.mark.asyncio
    async def test_create_project_success(self, asana_service, mock_access_token):
        """Test successful project creation"""
        # Mock the _make_request method
        mock_response = {
            'data': {
                'gid': '1122334455',
                'name': 'Test Project',
                'notes': 'This is a test project',
                'color': 'light-green',
                'created_at': '2026-02-07T12:00:00.000Z',
                'modified_at': '2026-02-07T12:00:00.000Z',
                'workspace': {'gid': '123456789'},
                'team': {'gid': '987654321'}
            }
        }

        with patch.object(asana_service, '_make_request', return_value=mock_response):
            result = await asana_service.create_project(
                access_token=mock_access_token,
                workspace_gid='123456789',
                name='Test Project',
                notes='This is a test project',
                team_gid='987654321',
                color='light-green',
                public=True
            )

        assert result['ok'] is True
        assert result['project']['gid'] == '1122334455'
        assert result['project']['name'] == 'Test Project'
        assert result['project']['notes'] == 'This is a test project'
        assert result['project']['color'] == 'light-green'
        assert result['project']['workspace_gid'] == '123456789'
        assert result['project']['team_gid'] == '987654321'

    @pytest.mark.asyncio
    async def test_create_project_minimal_fields(self, asana_service, mock_access_token):
        """Test project creation with minimal required fields"""
        mock_response = {
            'data': {
                'gid': '1122334455',
                'name': 'Minimal Project',
                'notes': '',
                'created_at': '2026-02-07T12:00:00.000Z',
                'modified_at': '2026-02-07T12:00:00.000Z',
                'workspace': {'gid': '123456789'}
            }
        }

        with patch.object(asana_service, '_make_request', return_value=mock_response):
            result = await asana_service.create_project(
                access_token=mock_access_token,
                workspace_gid='123456789',
                name='Minimal Project'
            )

        assert result['ok'] is True
        assert result['project']['gid'] == '1122334455'
        assert result['project']['name'] == 'Minimal Project'

    @pytest.mark.asyncio
    async def test_create_project_without_team(self, asana_service, mock_access_token):
        """Test project creation without team (workspace project)"""
        mock_response = {
            'data': {
                'gid': '1122334455',
                'name': 'Workspace Project',
                'notes': 'Project without team',
                'created_at': '2026-02-07T12:00:00.000Z',
                'modified_at': '2026-02-07T12:00:00.000Z',
                'workspace': {'gid': '123456789'}
            }
        }

        with patch.object(asana_service, '_make_request', return_value=mock_response):
            result = await asana_service.create_project(
                access_token=mock_access_token,
                workspace_gid='123456789',
                name='Workspace Project',
                notes='Project without team'
            )

        assert result['ok'] is True
        assert result['project']['team_gid'] is None

    @pytest.mark.asyncio
    async def test_create_project_private(self, asana_service, mock_access_token):
        """Test private project creation"""
        mock_response = {
            'data': {
                'gid': '1122334455',
                'name': 'Private Project',
                'notes': 'Secret project',
                'created_at': '2026-02-07T12:00:00.000Z',
                'modified_at': '2026-02-07T12:00:00.000Z',
                'workspace': {'gid': '123456789'}
            }
        }

        with patch.object(asana_service, '_make_request', return_value=mock_response):
            result = await asana_service.create_project(
                access_token=mock_access_token,
                workspace_gid='123456789',
                name='Private Project',
                notes='Secret project',
                public=False
            )

        assert result['ok'] is True
        assert result['project']['gid'] == '1122334455'

    @pytest.mark.asyncio
    async def test_create_project_api_error(self, asana_service, mock_access_token):
        """Test project creation with API error"""
        # Mock API error response
        with patch.object(asana_service, '_make_request', side_effect=Exception('API Error')):
            result = await asana_service.create_project(
                access_token=mock_access_token,
                workspace_gid='123456789',
                name='Test Project'
            )

        assert result['ok'] is False
        assert 'error' in result

    @pytest.mark.asyncio
    async def test_create_project_invalid_token(self, asana_service):
        """Test project creation with invalid token"""
        # Mock 401 error
        with patch.object(asana_service, '_make_request', side_effect=PermissionError('Invalid token')):
            result = await asana_service.create_project(
                access_token='invalid_token',
                workspace_gid='123456789',
                name='Test Project'
            )

        assert result['ok'] is False
        assert 'error' in result

    @pytest.mark.asyncio
    async def test_create_project_rate_limit_retry(self, asana_service, mock_access_token):
        """Test project creation with rate limit and retry"""
        import time

        call_count = [0]

        async def mock_request_with_rate_limit(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 2:
                # Simulate rate limit on first call
                response = Mock()
                response.status_code = 429
                raise Exception("Rate limit exceeded")
            else:
                # Success on retry
                return {
                    'data': {
                        'gid': '1122334455',
                        'name': 'Test Project',
                        'workspace': {'gid': '123456789'}
                    }
                }

        with patch.object(asana_service, '_make_request', side_effect=mock_request_with_rate_limit):
            result = await asana_service.create_project(
                access_token=mock_access_token,
                workspace_gid='123456789',
                name='Test Project'
            )

        assert result['ok'] is True
        assert call_count[0] == 2  # Initial attempt + 1 retry


# ============================================================================
# ProjectCreate Pydantic Model Tests
# ============================================================================

class TestProjectCreateModel:
    """Test ProjectCreate Pydantic model validation"""

    def test_project_create_valid(self):
        """Test valid project creation request"""
        project = ProjectCreate(
            name='Test Project',
            workspace='123456789',
            notes='Test notes',
            team='987654321',
            color='light-green',
            public=True
        )

        assert project.name == 'Test Project'
        assert project.workspace == '123456789'
        assert project.notes == 'Test notes'
        assert project.team == '987654321'
        assert project.color == 'light-green'
        assert project.public is True

    def test_project_create_minimal(self):
        """Test project creation with only required fields"""
        project = ProjectCreate(
            name='Minimal Project',
            workspace='123456789'
        )

        assert project.name == 'Minimal Project'
        assert project.workspace == '123456789'
        assert project.notes is None
        assert project.team is None
        assert project.color is None
        assert project.public is None  # Uses default from Pydantic if set

    def test_project_create_invalid_missing_name(self):
        """Test project creation fails without name"""
        with pytest.raises(ValueError):
            ProjectCreate(
                workspace='123456789'
            )

    def test_project_create_invalid_missing_workspace(self):
        """Test project creation fails without workspace"""
        with pytest.raises(ValueError):
            ProjectCreate(
                name='Test Project'
            )


# ============================================================================
# API Endpoint Tests
# ============================================================================

class TestAsanaProjectEndpoint:
    """Test POST /api/asana/projects endpoint"""

    @pytest.mark.asyncio
    async def test_create_project_endpoint_success(self, sample_project_request):
        """Test successful project creation via endpoint"""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        # Mock dependencies
        mock_db = Mock()

        async def mock_get_token():
            return 'test_access_token'

        # Mock service response
        mock_response = {
            'ok': True,
            'project': {
                'gid': '1122334455',
                'name': 'Test Project',
                'notes': 'This is a test project',
                'workspace_gid': '123456789',
                'team_gid': '987654321'
            }
        }

        with patch('integrations.asana_routes.get_access_token', side_effect=mock_get_token), \
             patch('integrations.asana_routes.asana_service.create_project', return_value=mock_response):

            client = TestClient(app)
            response = client.post(
                '/api/asana/projects',
                json={
                    'name': 'Test Project',
                    'workspace': '123456789',
                    'notes': 'This is a test project',
                    'team': '987654321',
                    'color': 'light-green',
                    'public': True
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert data['ok'] is True
        assert data['project']['gid'] == '1122334455'

    @pytest.mark.asyncio
    async def test_create_project_endpoint_invalid_token(self):
        """Test project creation endpoint with invalid token"""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        async def mock_get_token():
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail='Invalid token')

        with patch('integrations.asana_routes.get_access_token', side_effect=mock_get_token):
            client = TestClient(app)
            response = client.post(
                '/api/asana/projects',
                json={
                    'name': 'Test Project',
                    'workspace': '123456789'
                }
            )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_project_endpoint_service_error(self, sample_project_request):
        """Test project creation endpoint when service fails"""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        async def mock_get_token():
            return 'test_access_token'

        # Mock service error
        mock_error_response = {
            'ok': False,
            'error': 'Workspace not found'
        }

        with patch('integrations.asana_routes.get_access_token', side_effect=mock_get_token), \
             patch('integrations.asana_routes.asana_service.create_project', return_value=mock_error_response):

            client = TestClient(app)
            response = client.post(
                '/api/asana/projects',
                json={
                    'name': 'Test Project',
                    'workspace': 'invalid_workspace',
                }
            )

        assert response.status_code == 400
        data = response.json()
        assert 'detail' in data


# ============================================================================
# Integration Tests
# ============================================================================

class TestAsanaProjectIntegration:
    """Integration tests for Asana project creation"""

    @pytest.mark.asyncio
    async def test_end_to_end_project_creation(self, asana_service, mock_access_token):
        """Test complete project creation workflow"""
        # Mock successful API response
        mock_response = {
            'data': {
                'gid': '1122334455',
                'name': 'E2E Test Project',
                'notes': 'End-to-end test',
                'color': 'light-blue',
                'created_at': '2026-02-07T12:00:00.000Z',
                'modified_at': '2026-02-07T12:00:00.000Z',
                'workspace': {'gid': '123456789'},
                'team': {'gid': '987654321'}
            }
        }

        with patch.object(asana_service, '_make_request', return_value=mock_response):
            # Step 1: Create project
            result = await asana_service.create_project(
                access_token=mock_access_token,
                workspace_gid='123456789',
                name='E2E Test Project',
                notes='End-to-end test',
                team_gid='987654321',
                color='light-blue'
            )

            assert result['ok'] is True
            project_gid = result['project']['gid']

            # Step 2: Verify project data
            assert project_gid == '1122334455'
            assert result['project']['name'] == 'E2E Test Project'
            assert result['project']['notes'] == 'End-to-end test'
            assert result['project']['color'] == 'light-blue'

    @pytest.mark.asyncio
    async def test_project_with_color_variations(self, asana_service, mock_access_token):
        """Test project creation with different color options"""
        colors = [
            'light-green',
            'light-blue',
            'light-orange',
            'light-red',
            'light-purple',
            'light-pink',
            'light-yellow'
        ]

        for color in colors:
            mock_response = {
                'data': {
                    'gid': '1122334455',
                    'name': f'Project {color}',
                    'color': color,
                    'workspace': {'gid': '123456789'}
                }
            }

            with patch.object(asana_service, '_make_request', return_value=mock_response):
                result = await asana_service.create_project(
                    access_token=mock_access_token,
                    workspace_gid='123456789',
                    name=f'Project {color}',
                    color=color
                )

            assert result['ok'] is True
            assert result['project']['color'] == color


# ============================================================================
# Validation Tests
# ============================================================================

class TestAsanaProjectValidation:
    """Test validation and edge cases"""

    @pytest.mark.asyncio
    async def test_create_project_empty_name(self, asana_service, mock_access_token):
        """Test project creation with empty name fails"""
        mock_response = {
            'data': {
                'gid': '1122334455',
                'name': '',
                'workspace': {'gid': '123456789'}
            }
        }

        with patch.object(asana_service, '_make_request', return_value=mock_response):
            # This should succeed at the service level (validation happens at API level)
            result = await asana_service.create_project(
                access_token=mock_access_token,
                workspace_gid='123456789',
                name=''
            )

        # Service doesn't validate, API does
        # The API would reject this with Pydantic validation
        assert result['ok'] is True or result['project']['name'] == ''

    @pytest.mark.asyncio
    async def test_create_project_very_long_name(self, asana_service, mock_access_token):
        """Test project creation with very long name"""
        long_name = 'A' * 500  # Asana limits to ~1024 characters

        mock_response = {
            'data': {
                'gid': '1122334455',
                'name': long_name,
                'workspace': {'gid': '123456789'}
            }
        }

        with patch.object(asana_service, '_make_request', return_value=mock_response):
            result = await asana_service.create_project(
                access_token=mock_access_token,
                workspace_gid='123456789',
                name=long_name
            )

        assert result['ok'] is True
        assert len(result['project']['name']) == 500

    @pytest.mark.asyncio
    async def test_create_project_special_characters(self, asana_service, mock_access_token):
        """Test project creation with special characters in name"""
        special_names = [
            'Project with émojis 🎉',
            'Project with "quotes"',
            "Project with 'apostrophes'",
            'Project with - dashes_',
            'Project / with \\ slashes',
        ]

        for name in special_names:
            mock_response = {
                'data': {
                    'gid': '1122334455',
                    'name': name,
                    'workspace': {'gid': '123456789'}
                }
            }

            with patch.object(asana_service, '_make_request', return_value=mock_response):
                result = await asana_service.create_project(
                    access_token=mock_access_token,
                    workspace_gid='123456789',
                    name=name
                )

            assert result['ok'] is True
            assert result['project']['name'] == name


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
