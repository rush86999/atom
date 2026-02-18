"""
Canvas Sheets Routes API Tests

Tests for spreadsheet canvas endpoints including:
- Creating a spreadsheet canvas
- Updating a cell
- Adding a chart
- Getting a spreadsheet canvas
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from main_api_app import app


class TestCanvasSheetsRoutes:
    """Test spreadsheet canvas API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @patch('api.canvas_sheets_routes.SpreadsheetCanvasService')
    def test_create_spreadsheet_success(self, mock_service_class, client):
        """Test successful spreadsheet creation."""
        mock_service = Mock()
        mock_service.create_spreadsheet_canvas.return_value = {
            "success": True,
            "canvas_id": "canvas-123",
            "title": "Sales Data"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/sheets/create",
            json={
                "user_id": "user-123",
                "title": "Sales Data",
                "data": {"A1": "Product", "B1": "Price"}
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "canvas_id" in data or "success" in data

    @patch('api.canvas_sheets_routes.SpreadsheetCanvasService')
    def test_create_spreadsheet_failure(self, mock_service_class, client):
        """Test spreadsheet creation with service error."""
        mock_service = Mock()
        mock_service.create_spreadsheet_canvas.return_value = {
            "success": False,
            "error": "Invalid data format"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/sheets/create",
            json={
                "user_id": "user-123",
                "title": "Invalid Sheet",
                "data": {}
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data or "error" in data or "message" in data

    @patch('api.canvas_sheets_routes.SpreadsheetCanvasService')
    def test_create_spreadsheet_with_formulas(self, mock_service_class, client):
        """Test creating spreadsheet with formulas."""
        mock_service = Mock()
        mock_service.create_spreadsheet_canvas.return_value = {
            "success": True,
            "canvas_id": "canvas-formula"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/sheets/create",
            json={
                "user_id": "user-456",
                "title": "Financial Model",
                "data": {"A1": 100, "A2": 200},
                "formulas": ["=SUM(A1:A2)", "=AVERAGE(A1:A2)"]
            }
        )

        assert response.status_code == 200

    @patch('api.canvas_sheets_routes.SpreadsheetCanvasService')
    def test_create_spreadsheet_with_all_params(self, mock_service_class, client):
        """Test creating spreadsheet with all parameters."""
        mock_service = Mock()
        mock_service.create_spreadsheet_canvas.return_value = {
            "success": True,
            "canvas_id": "canvas-full"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/sheets/create",
            json={
                "user_id": "user-789",
                "title": "Complete Sheet",
                "data": {"A1": "Test"},
                "canvas_id": "existing-canvas",
                "agent_id": "agent-123",
                "layout": "sheet",
                "formulas": ["=A1*2"]
            }
        )

        assert response.status_code == 200

    @patch('api.canvas_sheets_routes.SpreadsheetCanvasService')
    def test_create_spreadsheet_calls_service(self, mock_service_class, client):
        """Test that create calls service correctly."""
        mock_service = Mock()
        mock_service.create_spreadsheet_canvas.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/sheets/create",
            json={
                "user_id": "user-call",
                "title": "Test",
                "data": {}
            }
        )

        assert response.status_code == 200
        mock_service.create_spreadsheet_canvas.assert_called_once()

    @patch('api.canvas_sheets_routes.SpreadsheetCanvasService')
    def test_update_cell_success(self, mock_service_class, client):
        """Test successfully updating a cell."""
        mock_service = Mock()
        mock_service.update_cell.return_value = {
            "success": True,
            "cell_ref": "A1",
            "value": "New Value"
        }
        mock_service_class.return_value = mock_service

        response = client.put(
            "/api/canvas/sheets/canvas-123/cell",
            json={
                "user_id": "user-123",
                "cell_ref": "A1",
                "value": "New Value",
                "cell_type": "text"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "cell_ref" in data or "success" in data

    @patch('api.canvas_sheets_routes.SpreadsheetCanvasService')
    def test_update_cell_failure(self, mock_service_class, client):
        """Test updating cell with service error."""
        mock_service = Mock()
        mock_service.update_cell.return_value = {
            "success": False,
            "error": "Invalid cell reference"
        }
        mock_service_class.return_value = mock_service

        response = client.put(
            "/api/canvas/sheets/canvas-123/cell",
            json={
                "user_id": "user-123",
                "cell_ref": "INVALID",
                "value": "test"
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data or "error" in data or "message" in data

    @patch('api.canvas_sheets_routes.SpreadsheetCanvasService')
    def test_update_cell_with_formula(self, mock_service_class, client):
        """Test updating cell with formula."""
        mock_service = Mock()
        mock_service.update_cell.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        response = client.put(
            "/api/canvas/sheets/canvas-123/cell",
            json={
                "user_id": "user-123",
                "cell_ref": "C1",
                "value": 0,
                "cell_type": "number",
                "formula": "=SUM(A1:B1)"
            }
        )

        assert response.status_code == 200

    @patch('api.canvas_sheets_routes.SpreadsheetCanvasService')
    def test_update_cell_calls_service(self, mock_service_class, client):
        """Test that update_cell calls service correctly."""
        mock_service = Mock()
        mock_service.update_cell.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        response = client.put(
            "/api/canvas/sheets/canvas-test/cell",
            json={
                "user_id": "user-test",
                "cell_ref": "B2",
                "value": "test value"
            }
        )

        assert response.status_code == 200
        mock_service.update_cell.assert_called_once_with(
            canvas_id="canvas-test",
            user_id="user-test",
            cell_ref="B2",
            value="test value",
            cell_type="text",
            formula=None
        )

    @patch('api.canvas_sheets_routes.SpreadsheetCanvasService')
    def test_add_chart_success(self, mock_service_class, client):
        """Test successfully adding a chart."""
        mock_service = Mock()
        mock_service.add_chart.return_value = {
            "success": True,
            "chart_id": "chart-123",
            "chart_type": "bar"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/sheets/canvas-123/chart",
            json={
                "user_id": "user-123",
                "chart_type": "bar",
                "data_range": "A1:B10",
                "title": "Sales Chart"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "chart_id" in data or "success" in data

    @patch('api.canvas_sheets_routes.SpreadsheetCanvasService')
    def test_add_chart_failure(self, mock_service_class, client):
        """Test adding chart with service error."""
        mock_service = Mock()
        mock_service.add_chart.return_value = {
            "success": False,
            "error": "Invalid data range"
        }
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/sheets/canvas-123/chart",
            json={
                "user_id": "user-123",
                "chart_type": "line",
                "data_range": "INVALID"
            }
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data or "error" in data or "message" in data

    @patch('api.canvas_sheets_routes.SpreadsheetCanvasService')
    def test_add_chart_different_types(self, mock_service_class, client):
        """Test adding different chart types."""
        mock_service = Mock()
        mock_service.add_chart.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        chart_types = ["bar", "line", "pie", "area"]

        for chart_type in chart_types:
            response = client.post(
                "/api/canvas/sheets/canvas-123/chart",
                json={
                    "user_id": "user-123",
                    "chart_type": chart_type,
                    "data_range": "A1:B10"
                }
            )
            assert response.status_code == 200

    @patch('api.canvas_sheets_routes.SpreadsheetCanvasService')
    def test_add_chart_calls_service(self, mock_service_class, client):
        """Test that add_chart calls service correctly."""
        mock_service = Mock()
        mock_service.add_chart.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/canvas/sheets/canvas-test/chart",
            json={
                "user_id": "user-test",
                "chart_type": "pie",
                "data_range": "A1:C5",
                "title": "Distribution"
            }
        )

        assert response.status_code == 200
        mock_service.add_chart.assert_called_once_with(
            canvas_id="canvas-test",
            user_id="user-test",
            chart_type="pie",
            data_range="A1:C5",
            title="Distribution"
        )

    @patch('api.canvas_sheets_routes.SpreadsheetCanvasService')
    def test_update_multiple_cells(self, mock_service_class, client):
        """Test updating multiple cells."""
        mock_service = Mock()
        mock_service.update_cell.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        cells = [
            {"cell_ref": "A1", "value": "Product A"},
            {"cell_ref": "A2", "value": "Product B"},
            {"cell_ref": "A3", "value": "Product C"}
        ]

        for cell in cells:
            response = client.put(
                "/api/canvas/sheets/canvas-multi/cell",
                json={
                    "user_id": "user-123",
                    "cell_ref": cell["cell_ref"],
                    "value": cell["value"]
                }
            )
            assert response.status_code == 200

    @patch('api.canvas_sheets_routes.SpreadsheetCanvasService')
    def test_create_multiple_spreadsheets(self, mock_service_class, client):
        """Test creating multiple spreadsheets."""
        mock_service = Mock()
        mock_service.create_spreadsheet_canvas.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        spreadsheets = [
            {"title": "Q1 Sales", "data": {"A1": "Jan"}},
            {"title": "Q2 Sales", "data": {"A1": "Apr"}},
            {"title": "Q3 Sales", "data": {"A1": "Jul"}}
        ]

        for sheet in spreadsheets:
            response = client.post(
                "/api/canvas/sheets/create",
                json={
                    "user_id": "user-456",
                    "title": sheet["title"],
                    "data": sheet["data"]
                }
            )
            assert response.status_code == 200

    @patch('api.canvas_sheets_routes.SpreadsheetCanvasService')
    def test_sheets_endpoints_return_json(self, mock_service_class, client):
        """Test that sheets endpoints return JSON."""
        mock_service = Mock()
        mock_service.create_spreadsheet_canvas.return_value = {"success": True}
        mock_service.update_cell.return_value = {"success": True}
        mock_service.add_chart.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        # Test create endpoint
        response = client.post(
            "/api/canvas/sheets/create",
            json={"user_id": "u", "title": "T", "data": {}}
        )
        assert response.headers["content-type"].startswith("application/json")

        # Test update cell endpoint
        response = client.put(
            "/api/canvas/sheets/c/cell",
            json={"user_id": "u", "cell_ref": "A1", "value": "v"}
        )
        assert response.headers["content-type"].startswith("application/json")

        # Test add chart endpoint
        response = client.post(
            "/api/canvas/sheets/c/chart",
            json={"user_id": "u", "chart_type": "bar", "data_range": "A1:B1"}
        )
        assert response.headers["content-type"].startswith("application/json")

    @patch('api.canvas_sheets_routes.SpreadsheetCanvasService')
    def test_create_spreadsheet_various_data_types(self, mock_service_class, client):
        """Test creating spreadsheets with various data types."""
        mock_service = Mock()
        mock_service.create_spreadsheet_canvas.return_value = {"success": True}
        mock_service_class.return_value = mock_service

        data_sets = [
            {"A1": "Text", "B1": "More Text"},
            {"A1": 123, "B1": 456},
            {"A1": True, "B1": False},
            {"A1": 3.14, "B1": 2.71}
        ]

        for data in data_sets:
            response = client.post(
                "/api/canvas/sheets/create",
                json={
                    "user_id": "user-dt",
                    "title": "Data Type Test",
                    "data": data
                }
            )
            assert response.status_code == 200
