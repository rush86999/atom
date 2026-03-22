
import pytest
from unittest.mock import MagicMock, patch
from tools.platform_management_tool import get_platform_settings, update_platform_setting, update_tenant_profile

@pytest.fixture
def mock_db():
    with patch("core.database.SessionLocal") as mock:
        yield mock

@pytest.mark.asyncio
async def test_get_platform_settings(mock_db):
    # Setup
    db_instance = mock_db.return_value.__enter__.return_value
    mock_setting = MagicMock()
    mock_setting.setting_key = "test_key"
    mock_setting.setting_value = "test_value"
    db_instance.query.return_value.filter.return_value.all.return_value = [mock_setting]
    
    context = {"workspace_id": "test_ws"}
    
    # Execute
    result = await get_platform_settings(context)
    
    # Verify
    assert result == {"test_key": "test_value"}
    db_instance.query.assert_called()

@pytest.mark.asyncio
async def test_update_platform_setting_new(mock_db):
    # Setup
    db_instance = mock_db.return_value.__enter__.return_value
    db_instance.query.return_value.filter.return_value.first.return_value = None
    
    context = {"workspace_id": "test_ws"}
    
    # Execute
    result = await update_platform_setting("new_key", "new_value", context)
    
    # Verify
    assert "successfully updated" in result
    db_instance.add.assert_called()
    db_instance.commit.assert_called()

@pytest.mark.asyncio
async def test_update_tenant_profile(mock_db):
    # Setup
    db_instance = mock_db.return_value.__enter__.return_value
    
    # Mock workspace
    mock_ws = MagicMock()
    mock_ws.id = "test_ws"
    mock_ws.tenant_id = "test_tenant"
    
    # Mock tenant
    mock_tenant = MagicMock()
    mock_tenant.id = "test_tenant"
    mock_tenant.name = "Old Name"
    
    # Setup query sequence
    # 1. query(Workspace).filter(...).first()
    # 2. query(Tenant).filter(...).first()
    db_instance.query.return_value.filter.return_value.first.side_effect = [mock_ws, mock_tenant]
    
    context = {"workspace_id": "test_ws"}
    
    # Execute
    result = await update_tenant_profile(name="New Name", context=context)
    
    # Verify
    assert "updated successfully" in result
    assert mock_tenant.name == "New Name"
    db_instance.commit.assert_called()
