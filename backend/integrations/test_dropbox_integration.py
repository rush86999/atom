import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dropbox_service_enhanced import (
    DropboxEnhancedService,
    DropboxUser,
    DropboxFile,
    DropboxFolder,
    DropboxSharedLink,
    DropboxSpaceUsage,
)


class TestDropboxIntegration:
    """Comprehensive test suite for Dropbox integration"""

    def setup_method(self):
        """Setup test fixtures"""
        self.service = DropboxEnhancedService()
        self.user_id = "test_user_123"
        self.mock_access_token = "mock_access_token_123"

    @pytest.fixture
    def mock_file_metadata(self):
        """Mock file metadata for testing"""
        return {
            "id": "file_123",
            "name": "test_document.pdf",
            "path_lower": "/documents/test_document.pdf",
            "path_display": "/Documents/test_document.pdf",
            "client_modified": "2024-01-15T10:00:00Z",
            "server_modified": "2024-01-15T10:00:00Z",
            "rev": "rev_123",
            "size": 1024,
            "is_downloadable": True,
            "content_hash": "hash_123",
            "media_info": {"mime_type": "application/pdf"},
        }

    @pytest.fixture
    def mock_folder_metadata(self):
        """Mock folder metadata for testing"""
        return {
            "id": "folder_123",
            "name": "Documents",
            "path_lower": "/documents",
            "path_display": "/Documents",
            "shared_folder_id": None,
            "sharing_info": None,
        }

    @pytest.fixture
    def mock_user_info(self):
        """Mock user info for testing"""
        return {
            "account_id": "user_123",
            "name": {
                "given_name": "Test",
                "surname": "User",
                "familiar_name": "Test",
                "display_name": "Test User",
                "abbreviated_name": "TU",
            },
            "email": "test@example.com",
            "email_verified": True,
            "profile_photo_url": None,
            "disabled": False,
            "country": "US",
            "locale": "en",
            "referral_link": "https://db.tt/mock_referral",
        }

    @pytest.fixture
    def mock_space_usage(self):
        """Mock space usage for testing"""
        return {
            "used": 1073741824,  # 1 GB
            "allocation": {
                ".tag": "individual",
                "allocated": 21474836480,  # 20 GB
            },
        }

    @pytest.mark.asyncio
    async def test_list_files_success(self, mock_file_metadata, mock_folder_metadata):
        """Test successful file listing"""
        with (
            patch.object(self.service, "_get_access_token") as mock_token,
            patch.object(self.service, "_get_dropbox_client") as mock_client,
        ):
            mock_token.return_value = self.mock_access_token
            mock_dbx = Mock()
            mock_client.return_value = mock_dbx

            # Mock list folder response
            mock_result = Mock()
            mock_result.entries = [
                Mock(
                    id="file_123",
                    name="test_document.pdf",
                    path_lower="/documents/test_document.pdf",
                    path_display="/Documents/test_document.pdf",
                    client_modified=datetime(2024, 1, 15, 10, 0, 0),
                    server_modified=datetime(2024, 1, 15, 10, 0, 0),
                    rev="rev_123",
                    size=1024,
                    is_downloadable=True,
                    content_hash="hash_123",
                    media_info=Mock(to_dict=lambda: {"mime_type": "application/pdf"}),
                ),
                Mock(
                    id="folder_123",
                    name="Documents",
                    path_lower="/documents",
                    path_display="/Documents",
                    shared_folder_id=None,
                    sharing_info=None,
                ),
            ]
            mock_result.cursor = "cursor_123"
            mock_result.has_more = False
            mock_dbx.files_list_folder.return_value = mock_result

            result = await self.service.list_files(self.user_id, "/", False, 100)

            assert result is not None
            assert "entries" in result
            assert len(result["entries"]) == 2
            assert result["cursor"] == "cursor_123"
            assert result["has_more"] is False
            mock_dbx.files_list_folder.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_files_no_token(self):
        """Test file listing with no access token"""
        with patch.object(self.service, "_get_access_token") as mock_token:
            mock_token.return_value = None

            result = await self.service.list_files(self.user_id, "/")

            assert result == {"entries": [], "cursor": None, "has_more": False}

    @pytest.mark.asyncio
    async def test_upload_file_success(self, mock_file_metadata):
        """Test successful file upload"""
        with (
            patch.object(self.service, "_get_access_token") as mock_token,
            patch.object(self.service, "_get_dropbox_client") as mock_client,
        ):
            mock_token.return_value = self.mock_access_token
            mock_dbx = Mock()
            mock_client.return_value = mock_dbx

            # Mock upload response
            mock_result = Mock(
                id="file_123",
                name="test_document.pdf",
                path_lower="/documents/test_document.pdf",
                path_display="/Documents/test_document.pdf",
                client_modified=datetime(2024, 1, 15, 10, 0, 0),
                server_modified=datetime(2024, 1, 15, 10, 0, 0),
                rev="rev_123",
                size=1024,
                is_downloadable=True,
                content_hash="hash_123",
                media_info=Mock(to_dict=lambda: {"mime_type": "application/pdf"}),
            )
            mock_dbx.files_upload.return_value = mock_result

            result = await self.service.upload_file(
                self.user_id, "test_document.pdf", "base64_content", "/documents"
            )

            assert result is not None
            assert result["id"] == "file_123"
            assert result["name"] == "test_document.pdf"
            mock_dbx.files_upload.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_file_success(self):
        """Test successful file download"""
        with (
            patch.object(self.service, "_get_access_token") as mock_token,
            patch.object(self.service, "_get_dropbox_client") as mock_client,
        ):
            mock_token.return_value = self.mock_access_token
            mock_dbx = Mock()
            mock_client.return_value = mock_dbx

            # Mock download response
            mock_metadata = Mock(
                name="test_document.pdf",
                rev="rev_123",
                size=1024,
                media_info=Mock(mime_type="application/pdf"),
            )
            mock_response = Mock(content=b"file_content")
            mock_dbx.files_download.return_value = (mock_metadata, mock_response)

            result = await self.service.download_file(
                self.user_id, "/documents/test_document.pdf"
            )

            assert result is not None
            assert result["file_name"] == "test_document.pdf"
            assert result["mime_type"] == "application/pdf"
            assert result["rev"] == "rev_123"
            mock_dbx.files_download.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_files_success(self, mock_file_metadata):
        """Test successful file search"""
        with (
            patch.object(self.service, "_get_access_token") as mock_token,
            patch.object(self.service, "_get_dropbox_client") as mock_client,
        ):
            mock_token.return_value = self.mock_access_token
            mock_dbx = Mock()
            mock_client.return_value = mock_dbx

            # Mock search response
            mock_match = Mock()
            mock_match.metadata.get_metadata.return_value = Mock(
                id="file_123",
                name="test_document.pdf",
                path_lower="/documents/test_document.pdf",
                path_display="/Documents/test_document.pdf",
                client_modified=datetime(2024, 1, 15, 10, 0, 0),
                server_modified=datetime(2024, 1, 15, 10, 0, 0),
                rev="rev_123",
                size=1024,
                is_downloadable=True,
                content_hash="hash_123",
                media_info=Mock(to_dict=lambda: {"mime_type": "application/pdf"}),
            )
            mock_result = Mock()
            mock_result.matches = [mock_match]
            mock_result.has_more = False
            mock_result.start = 0
            mock_dbx.files_search_v2.return_value = mock_result

            result = await self.service.search_files(self.user_id, "test", "/", 50)

            assert result is not None
            assert "matches" in result
            assert len(result["matches"]) == 1
            assert result["more"] is False
            mock_dbx.files_search_v2.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_folder_success(self, mock_folder_metadata):
        """Test successful folder creation"""
        with (
            patch.object(self.service, "_get_access_token") as mock_token,
            patch.object(self.service, "_get_dropbox_client") as mock_client,
        ):
            mock_token.return_value = self.mock_access_token
            mock_dbx = Mock()
            mock_client.return_value = mock_dbx

            # Mock create folder response
            mock_metadata = Mock(
                id="folder_123",
                name="Documents",
                path_lower="/documents",
                path_display="/Documents",
                shared_folder_id=None,
                sharing_info=None,
            )
            mock_result = Mock(metadata=mock_metadata)
            mock_dbx.files_create_folder_v2.return_value = mock_result

            result = await self.service.create_folder(self.user_id, "/documents")

            assert result is not None
            assert result["id"] == "folder_123"
            assert result["name"] == "Documents"
            mock_dbx.files_create_folder_v2.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_item_success(self, mock_file_metadata):
        """Test successful item deletion"""
        with (
            patch.object(self.service, "_get_access_token") as mock_token,
            patch.object(self.service, "_get_dropbox_client") as mock_client,
        ):
            mock_token.return_value = self.mock_access_token
            mock_dbx = Mock()
            mock_client.return_value = mock_dbx

            # Mock delete response
            mock_metadata = Mock(
                id="file_123",
                name="test_document.pdf",
                path_lower="/documents/test_document.pdf",
                path_display="/Documents/test_document.pdf",
                client_modified=datetime(2024, 1, 15, 10, 0, 0),
                server_modified=datetime(2024, 1, 15, 10, 0, 0),
                rev="rev_123",
                size=1024,
                is_downloadable=True,
                content_hash="hash_123",
            )
            mock_result = Mock(metadata=mock_metadata)
            mock_dbx.files_delete_v2.return_value = mock_result

            result = await self.service.delete_item(
                self.user_id, "/documents/test_document.pdf"
            )

            assert result is not None
            assert "metadata" in result
            assert result["metadata"]["id"] == "file_123"
            mock_dbx.files_delete_v2.assert_called_once()

    @pytest.mark.asyncio
    async def test_move_item_success(self, mock_file_metadata):
        """Test successful item move"""
        with (
            patch.object(self.service, "_get_access_token") as mock_token,
            patch.object(self.service, "_get_dropbox_client") as mock_client,
        ):
            mock_token.return_value = self.mock_access_token
            mock_dbx = Mock()
            mock_client.return_value = mock_dbx

            # Mock move response
            mock_metadata = Mock(
                id="file_123",
                name="test_document.pdf",
                path_lower="/new_location/test_document.pdf",
                path_display="/New Location/test_document.pdf",
                client_modified=datetime(2024, 1, 15, 10, 0, 0),
                server_modified=datetime(2024, 1, 15, 10, 0, 0),
                rev="rev_123",
                size=1024,
                is_downloadable=True,
                content_hash="hash_123",
            )
            mock_result = Mock(metadata=mock_metadata)
            mock_dbx.files_move_v2.return_value = mock_result

            result = await self.service.move_item(
                self.user_id,
                "/old_location/test_document.pdf",
                "/new_location/test_document.pdf",
            )

            assert result is not None
            assert "metadata" in result
            assert result["metadata"]["path_lower"] == "/new_location/test_document.pdf"
            mock_dbx.files_move_v2.assert_called_once()

    @pytest.mark.asyncio
    async def test_copy_item_success(self, mock_file_metadata):
        """Test successful item copy"""
        with (
            patch.object(self.service, "_get_access_token") as mock_token,
            patch.object(self.service, "_get_dropbox_client") as mock_client,
        ):
            mock_token.return_value = self.mock_access_token
            mock_dbx = Mock()
            mock_client.return_value = mock_dbx

            # Mock copy response
            mock_metadata = Mock(
                id="file_123_copy",
                name="test_document_copy.pdf",
                path_lower="/copied/test_document_copy.pdf",
                path_display="/Copied/test_document_copy.pdf",
                client_modified=datetime(2024, 1, 15, 10, 0, 0),
                server_modified=datetime(2024, 1, 15, 10, 0, 0),
                rev="rev_123_copy",
                size=1024,
                is_downloadable=True,
                content_hash="hash_123",
            )
            mock_result = Mock(metadata=mock_metadata)
            mock_dbx.files_copy_v2.return_value = mock_result

            result = await self.service.copy_item(
                self.user_id,
                "/original/test_document.pdf",
                "/copied/test_document_copy.pdf",
            )

            assert result is not None
            assert "metadata" in result
            assert result["metadata"]["name"] == "test_document_copy.pdf"
            mock_dbx.files_copy_v2.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_shared_link_success(self):
        """Test successful shared link creation"""
        with (
            patch.object(self.service, "_get_access_token") as mock_token,
            patch.object(self.service, "_get_dropbox_client") as mock_client,
        ):
            mock_token.return_value = self.mock_access_token
            mock_dbx = Mock()
            mock_client.return_value = mock_dbx

            # Mock shared link response
            mock_result = Mock(
                url="https://www.dropbox.com/s/mock_link/test_document.pdf?dl=0",
                name="test_document.pdf",
                path_lower="/documents/test_document.pdf",
                link_permissions=Mock(to_dict=lambda: {"can_revoke": True}),
                preview_type="file",
                client_modified=datetime(2024, 1, 15, 10, 0, 0),
                server_modified=datetime(2024, 1, 15, 10, 0, 0),
            )
            mock_dbx.sharing_create_shared_link_with_settings.return_value = mock_result

            result = await self.service.create_shared_link(
                self.user_id, "/documents/test_document.pdf"
            )

            assert result is not None
            assert (
                result["url"]
                == "https://www.dropbox.com/s/mock_link/test_document.pdf?dl=0"
            )
            assert result["name"] == "test_document.pdf"
            mock_dbx.sharing_create_shared_link_with_settings.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_info_success(self, mock_user_info):
        """Test successful user info retrieval"""
        with (
            patch.object(self.service, "_get_access_token") as mock_token,
            patch.object(self.service, "_get_dropbox_client") as mock_client,
        ):
            mock_token.return_value = self.mock_access_token
            mock_dbx = Mock()
            mock_client.return_value = mock_dbx

            # Mock user info response
            mock_result = Mock(
                account_id="user_123",
                name=Mock(
                    given_name="Test",
                    surname="User",
                    familiar_name="Test",
                    display_name="Test User",
                    abbreviated_name="TU",
                ),
                email="test@example.com",
                email_verified=True,
                profile_photo_url=None,
                disabled=False,
                country="US",
                locale="en",
                referral_link="https://db.tt/mock_referral",
            )
            mock_dbx.users_get_current_account.return_value = mock_result

            result = await self.service.get_user_info(self.user_id)

            assert result is not None
            assert result["account_id"] == "user_123"
            assert result["email"] == "test@example.com"
            assert result["name"]["display_name"] == "Test User"
            mock_dbx.users_get_current_account.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_space_usage_success(self, mock_space_usage):
        """Test successful space usage retrieval"""
        with (
            patch.object(self.service, "_get_access_token") as mock_token,
            patch.object(self.service, "_get_dropbox_client") as mock_client,
        ):
            mock_token.return_value = self.mock_access_token
            mock_dbx = Mock()
            mock_client.return_value = mock_dbx

            # Mock space usage response
            mock_result = Mock(
                used=1073741824,
                allocation=Mock(
                    to_dict=lambda: {".tag": "individual", "allocated": 21474836480}
                ),
            )
            mock_dbx.users_get_space_usage.return_value = mock_result

            result = await self.service.get_space_usage(self.user_id)

            assert result is not None
            assert result["used"] == 1073741824
            assert result["allocation"][".tag"] == "individual"
            mock_dbx.users_get_space_usage.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_file_metadata_success(self, mock_file_metadata):
        """Test successful file metadata retrieval"""
        with (
            patch.object(self.service, "_get_access_token") as mock_token,
            patch.object(self.service, "_get_dropbox_client") as mock_client,
        ):
            mock_token.return_value = self.mock_access_token
            mock_dbx = Mock()
            mock_client.return_value = mock_dbx

            # Mock file metadata response
            mock_result = Mock(
                id="file_123",
                name="test_document.pdf",
                path_lower="/documents/test_document.pdf",
                path_display="/Documents/test_document.pdf",
                client_modified=datetime(2024, 1, 15, 10, 0, 0),
                server_modified=datetime(2024, 1, 15, 10, 0, 0),
                rev="rev_123",
                size=1024,
                is_downloadable=True,
                content_hash="hash_123",
                media_info=Mock(to_dict=lambda: {"mime_type": "application/pdf"}),
            )
            mock_dbx.files_get_metadata.return_value = mock_result

            result = await self.service.get_file_metadata(
                self.user_id, "/documents/test_document.pdf"
            )

            assert result is not None
            assert result["id"] == "file_123"
            assert result["name"] == "test_document.pdf"
            mock_dbx.files_get_metadata.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_file_versions_success(self, mock_file_metadata):
        """Test successful file version listing"""
        with (
            patch.object(self.service, "_get_access_token") as mock_token,
            patch.object(self.service, "_get_dropbox_client") as mock_client,
        ):
            mock_token.return_value = self.mock_access_token
            mock_dbx = Mock()
            mock_client.return_value = mock_dbx

            # Mock file versions response
            mock_entry = Mock(
                id="file_123",
                name="test_document.pdf",
                path_lower="/documents/test_document.pdf",
                path_display="/Documents/test_document.pdf",
                client_modified=datetime(2024, 1, 15, 10, 0, 0),
                server_modified=datetime(2024, 1, 15, 10, 0, 0),
                rev="rev_123",
                size=1024,
                is_downloadable=True,
                content_hash="hash_123",
            )
            mock_result = Mock(entries=[mock_entry], is_deleted=False)
            mock_dbx.files_list_revisions.return_value = mock_result

            result = await self.service.list_file_versions(
                self.user_id, "/documents/test_document.pdf"
            )

            assert result is not None
            assert "versions" in result
            assert len(result["versions"]) == 1
            assert result["is_deleted"] is False
            mock_dbx.files_list_revisions.assert_called_once()

    @pytest.mark.asyncio
    async def test_restore_file_version_success(self, mock_file_metadata):
        """Test successful file version restoration"""
        with (
            patch.object(self.service, "_get_access_token") as mock_token,
            patch.object(self.service, "_get_dropbox_client") as mock_client,
        ):
            mock_token.return_value = self.mock_access_token
            mock_dbx = Mock()
            mock_client.return_value = mock_dbx

            # Mock restore response
            mock_result = Mock(
                id="file_123",
                name="test_document.pdf",
                path_lower="/documents/test_document.pdf",
                path_display="/Documents/test_document.pdf",
                client_modified=datetime(2024, 1, 15, 10, 0, 0),
                server_modified=datetime(2024, 1, 15, 10, 0, 0),
                rev="rev_123_restored",
                size=1024,
                is_downloadable=True,
                content_hash="hash_123",
            )
            mock_dbx.files_restore.return_value = mock_result

            result = await self.service.restore_file_version(
                self.user_id, "/documents/test_document.pdf", "rev_123"
            )

            assert result is not None
            assert result["id"] == "file_123"
            assert result["rev"] == "rev_123_restored"
            mock_dbx.files_restore.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_file_preview_success(self):
        """Test successful file preview retrieval"""
        with (
            patch.object(self.service, "_get_access_token") as mock_token,
            patch.object(self.service, "_get_dropbox_client") as mock_client,
        ):
            mock_token.return_value = self.mock_access_token
            mock_dbx = Mock()
            mock_client.return_value = mock_dbx

            # Mock preview response
            mock_metadata = Mock(
                name="test_document.pdf",
                rev="rev_123",
                size=1024,
                media_info=Mock(mime_type="application/pdf"),
            )
            mock_response = Mock(content=b"preview_content")
            mock_dbx.files_get_preview.return_value = (mock_metadata, mock_response)

            result = await self.service.get_file_preview(
                self.user_id, "/documents/test_document.pdf"
            )

            assert result is not None
            assert result["file_name"] == "test_document.pdf"
            assert result["mime_type"] == "application/pdf"
            assert "content_bytes" in result
            mock_dbx.files_get_preview.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_service_status_success(self):
        """Test successful service status retrieval"""
        with (
            patch.object(self.service, "_get_access_token") as mock_token,
            patch.object(self.service, "_get_dropbox_client") as mock_client,
        ):
            mock_token.return_value = self.mock_access_token
            mock_dbx = Mock()
            mock_client.return_value = mock_dbx

            # Mock user info response
            mock_user = Mock(
                name=Mock(display_name="Test User"), email="test@example.com"
            )
            mock_dbx.users_get_current_account.return_value = mock_user

            result = await self.service.get_service_status(self.user_id)

            assert result is not None
            assert result["status"] == "healthy"
            assert result["user"] == "Test User"
            assert result["email"] == "test@example.com"
            mock_dbx.users_get_current_account.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_service_status_no_token(self):
        """Test service status with no access token"""
        with patch.object(self.service, "_get_access_token") as mock_token:
            mock_token.return_value = None

            result = await self.service.get_service_status(self.user_id)

            assert result is not None
            assert result["status"] == "unavailable"
            assert "No access token" in result["message"]

    def test_dropbox_user_dataclass(self):
        """Test DropboxUser dataclass functionality"""
        user = DropboxUser(
            account_id="test_id",
            name={"given_name": "Test", "surname": "User"},
            email="test@example.com",
            email_verified=True,
            country="US",
        )

        assert user.account_id == "test_id"
        assert user.email == "test@example.com"
        assert user.country == "US"

    def test_dropbox_file_dataclass(self):
        """Test DropboxFile dataclass functionality"""
        file = DropboxFile(
            id="test_id",
            name="test_file.pdf",
            path_lower="/test_file.pdf",
            path_display="/Test File.pdf",
            client_modified="2024-01-15T10:00:00Z",
            server_modified="2024-01-15T10:00:00Z",
            rev="test_rev",
            size=1024,
            is_downloadable=True,
        )

        assert file.id == "test_id"
        assert file.name == "test_file.pdf"
        assert file.size == 1024
        assert file.is_downloadable is True

    def test_dropbox_folder_dataclass(self):
        """Test DropboxFolder dataclass functionality"""
        folder = DropboxFolder(
            id="test_id",
            name="Test Folder",
            path_lower="/test_folder",
            path_display="/Test Folder",
        )

        assert folder.id == "test_id"
        assert folder.name == "Test Folder"
        assert folder.path_display == "/Test Folder"

    def test_dropbox_shared_link_dataclass(self):
        """Test DropboxSharedLink dataclass functionality"""
        shared_link = DropboxSharedLink(
            url="https://dropbox.com/s/test",
            name="test_file.pdf",
            path_lower="/test_file.pdf",
            link_permissions={"can_revoke": True},
            preview_type="file",
            client_modified="2024-01-15T10:00:00Z",
            server_modified="2024-01-15T10:00:00Z",
        )

        assert shared_link.url == "https://dropbox.com/s/test"
        assert shared_link.name == "test_file.pdf"
        assert shared_link.preview_type == "file"

    def test_dropbox_space_usage_dataclass(self):
        """Test DropboxSpaceUsage dataclass functionality"""
        space_usage = DropboxSpaceUsage(
            used=1073741824, allocation={".tag": "individual", "allocated": 21474836480}
        )

        assert space_usage.used == 1073741824
        assert space_usage.allocation[".tag"] == "individual"
