"""
Storage Service Tests

Tests for StorageService S3/R2 operations.
Coverage target: 80%+ for core/storage.py

Tests cover:
- StorageService.__init__: S3 client loading, R2/AWS credentials
- upload_file: File upload with content_type, S3 URI format
- check_exists: File existence checking with error handling
- get_storage_service: Singleton pattern

Reference: Phase 181-05 Plan - Storage Service coverage
"""

import os
os.environ["TESTING"] = "1"

import pytest
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO
from botocore.exceptions import ClientError

from core.storage import StorageService, get_storage_service


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def clear_storage_singleton():
    """Clear the StorageService singleton before each test."""
    StorageService._instance = None
    yield
    StorageService._instance = None


@pytest.fixture
def mock_s3_client():
    """Create a mock S3 client."""
    mock_client = MagicMock()
    return mock_client


@pytest.fixture
def sample_file_obj():
    """Create a sample file-like object for testing."""
    return BytesIO(b"sample file content for testing")


@pytest.fixture
def sample_bytesio():
    """Create a BytesIO object for testing."""
    return BytesIO(b"bytesio content for testing")


# ============================================================================
# TEST CLASS: StorageServiceInit
# ============================================================================

class TestStorageServiceInit:
    """Tests for StorageService initialization."""

    @patch('core.storage.boto3.client')
    def test_init_loads_s3_client(self, mock_boto3_client, mock_s3_client, clear_storage_singleton):
        """
        GIVEN StorageService class
        WHEN initialized
        THEN S3 client is created via boto3.client
        """
        mock_boto3_client.return_value = mock_s3_client

        service = StorageService()

        # Verify boto3.client was called
        mock_boto3_client.assert_called_once()
        assert service.s3 == mock_s3_client

    @patch('core.storage.boto3.client')
    def test_init_with_r2_credentials(self, mock_boto3_client, mock_s3_client, clear_storage_singleton):
        """
        GIVEN environment variables for R2 (Cloudflare)
        WHEN StorageService is initialized
        THEN endpoint_url is configured for R2
        """
        # Set R2 environment variables
        os.environ['S3_ENDPOINT'] = 'https://example.r2.cloudflarestorage.com'
        os.environ['R2_ACCESS_KEY_ID'] = 'r2_access_key'
        os.environ['R2_SECRET_ACCESS_KEY'] = 'r2_secret_key'

        mock_boto3_client.return_value = mock_s3_client

        service = StorageService()

        # Verify boto3.client was called with endpoint_url
        mock_boto3_client.assert_called_once()
        call_kwargs = mock_boto3_client.call_args[1]
        assert 'endpoint_url' in call_kwargs
        assert call_kwargs['endpoint_url'] == 'https://example.r2.cloudflarestorage.com'

        # Clean up
        del os.environ['S3_ENDPOINT']
        del os.environ['R2_ACCESS_KEY_ID']
        del os.environ['R2_SECRET_ACCESS_KEY']

    @patch('core.storage.boto3.client')
    def test_init_with_aws_credentials(self, mock_boto3_client, mock_s3_client, clear_storage_singleton):
        """
        GIVEN environment variables for AWS S3
        WHEN StorageService is initialized
        THEN uses default endpoint (no endpoint_url)
        """
        # Set AWS environment variables
        os.environ['AWS_ACCESS_KEY_ID'] = 'aws_access_key'
        os.environ['AWS_SECRET_ACCESS_KEY'] = 'aws_secret_key'

        mock_boto3_client.return_value = mock_s3_client

        service = StorageService()

        # Verify boto3.client was called
        mock_boto3_client.assert_called_once()
        call_kwargs = mock_boto3_client.call_args[1]
        # Should NOT have endpoint_url for AWS
        assert 'endpoint_url' not in call_kwargs or call_kwargs.get('endpoint_url') is None

        # Clean up
        del os.environ['AWS_ACCESS_KEY_ID']
        del os.environ['AWS_SECRET_ACCESS_KEY']


# ============================================================================
# TEST CLASS: UploadFile
# ============================================================================

class TestUploadFile:
    """Tests for upload_file method."""

    @patch('core.storage.boto3.client')
    def test_upload_file_success(self, mock_boto3_client, mock_s3_client, sample_file_obj, clear_storage_singleton):
        """
        GIVEN StorageService with mocked S3 client
        WHEN upload_file is called with valid file object
        THEN return s3:// URI format
        """
        mock_boto3_client.return_value = mock_s3_client
        service = StorageService()

        result = service.upload_file(sample_file_obj, "test/file.txt")

        # Verify S3 upload was called
        mock_s3_client.upload_fileobj.assert_called_once()

        # Verify return format
        assert result.startswith("s3://")
        assert "/test/file.txt" in result
        assert service.bucket in result

    @patch('core.storage.boto3.client')
    def test_upload_file_with_content_type(self, mock_boto3_client, mock_s3_client, sample_file_obj, clear_storage_singleton):
        """
        GIVEN StorageService with mocked S3 client
        WHEN upload_file is called with content_type parameter
        THEN content_type is passed to S3 upload_fileobj
        """
        mock_boto3_client.return_value = mock_s3_client
        service = StorageService()

        service.upload_file(sample_file_obj, "test/file.pdf", content_type="application/pdf")

        # Verify upload_fileobj was called with ContentType
        call_args = mock_s3_client.upload_fileobj.call_args
        assert 'ExtraArgs' in call_args[1]
        assert call_args[1]['ExtraArgs']['ContentType'] == "application/pdf"

    @patch('core.storage.boto3.client')
    def test_upload_file_returns_s3_uri(self, mock_boto3_client, mock_s3_client, sample_file_obj, clear_storage_singleton):
        """
        GIVEN StorageService with mocked S3 client
        WHEN upload_file is called
        THEN return URI in s3://bucket/key format
        """
        mock_boto3_client.return_value = mock_s3_client
        service = StorageService()

        result = service.upload_file(sample_file_obj, "path/to/file.txt")

        # Verify URI format
        assert result == f"s3://{service.bucket}/path/to/file.txt"

    @patch('core.storage.boto3.client')
    def test_upload_file_bucket_from_env(self, mock_boto3_client, mock_s3_client, sample_file_obj, clear_storage_singleton):
        """
        GIVEN S3_BUCKET environment variable is set
        WHEN StorageService is initialized and upload_file is called
        THEN bucket from env is used in S3 URI
        """
        # Set bucket env var
        os.environ['AWS_S3_BUCKET'] = 'custom-bucket'

        mock_boto3_client.return_value = mock_s3_client
        service = StorageService()

        result = service.upload_file(sample_file_obj, "test/file.txt")

        # Verify bucket from env is used
        assert service.bucket == 'custom-bucket'
        assert result == "s3://custom-bucket/test/file.txt"

        # Clean up
        del os.environ['AWS_S3_BUCKET']

    @patch('core.storage.boto3.client')
    def test_upload_file_failure_raises_exception(self, mock_boto3_client, mock_s3_client, sample_file_obj, clear_storage_singleton):
        """
        GIVEN StorageService with mocked S3 client that raises exception
        WHEN upload_file is called
        THEN exception is propagated to caller
        """
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.upload_fileobj.side_effect = Exception("S3 connection failed")

        service = StorageService()

        # Verify exception is raised
        with pytest.raises(Exception, match="S3 connection failed"):
            service.upload_file(sample_file_obj, "test/file.txt")

    @patch('core.storage.boto3.client')
    def test_upload_file_with_bytesio(self, mock_boto3_client, mock_s3_client, sample_bytesio, clear_storage_singleton):
        """
        GIVEN StorageService with mocked S3 client
        WHEN upload_file is called with BytesIO object
        THEN upload_fileobj is called with BytesIO
        """
        mock_boto3_client.return_value = mock_s3_client
        service = StorageService()

        service.upload_file(sample_bytesio, "test/bytesio.bin")

        # Verify upload_fileobj was called
        mock_s3_client.upload_fileobj.assert_called_once()
        call_args = mock_s3_client.upload_fileobj.call_args
        assert call_args[0][0] == sample_bytesio


# ============================================================================
# TEST CLASS: CheckExists
# ============================================================================

class TestCheckExists:
    """Tests for check_exists method."""

    @patch('core.storage.boto3.client')
    def test_check_exists_true(self, mock_boto3_client, mock_s3_client, clear_storage_singleton):
        """
        GIVEN StorageService with mocked S3 client
        WHEN check_exists is called and file exists
        THEN return True
        """
        mock_boto3_client.return_value = mock_s3_client
        # head_object succeeds (no exception = file exists)
        mock_s3_client.head_object.return_value = {}

        service = StorageService()
        result = service.check_exists("test/file.txt")

        # Verify head_object was called
        mock_s3_client.head_object.assert_called_once()
        assert result is True

    @patch('core.storage.boto3.client')
    def test_check_exists_false(self, mock_boto3_client, mock_s3_client, clear_storage_singleton):
        """
        GIVEN StorageService with mocked S3 client
        WHEN check_exists is called and file doesn't exist (404)
        THEN return False
        """
        mock_boto3_client.return_value = mock_s3_client
        # Simulate 404 error
        error_response = {'Error': {'Code': '404', 'Message': 'Not Found'}}
        mock_s3_client.head_object.side_effect = ClientError(error_response, 'head_object')

        service = StorageService()
        result = service.check_exists("test/nonexistent.txt")

        # Verify returns False on 404
        assert result is False

    @patch('core.storage.boto3.client')
    def test_check_exists_error_returns_false(self, mock_boto3_client, mock_s3_client, clear_storage_singleton):
        """
        GIVEN StorageService with mocked S3 client
        WHEN check_exists is called and raises other error
        THEN return False (graceful degradation)
        """
        mock_boto3_client.return_value = mock_s3_client
        # Simulate generic error
        mock_s3_client.head_object.side_effect = Exception("Permission denied")

        service = StorageService()
        result = service.check_exists("test/file.txt")

        # Verify returns False on error
        assert result is False

    @patch('core.storage.boto3.client')
    def test_check_exists_bucket_from_env(self, mock_boto3_client, mock_s3_client, clear_storage_singleton):
        """
        GIVEN S3_BUCKET environment variable is set
        WHEN check_exists is called
        THEN bucket from env is used in head_object call
        """
        # Set bucket env var
        os.environ['AWS_S3_BUCKET'] = 'custom-check-bucket'

        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.head_object.return_value = {}

        service = StorageService()
        service.check_exists("test/file.txt")

        # Verify bucket from env is used
        call_args = mock_s3_client.head_object.call_args
        assert call_args[1]['Bucket'] == 'custom-check-bucket'

        # Clean up
        del os.environ['AWS_S3_BUCKET']

    @patch('core.storage.boto3.client')
    def test_check_exists_with_key(self, mock_boto3_client, mock_s3_client, clear_storage_singleton):
        """
        GIVEN StorageService with mocked S3 client
        WHEN check_exists is called with key parameter
        THEN head_object is called with correct Key
        """
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.head_object.return_value = {}

        service = StorageService()
        service.check_exists("documents/test.pdf")

        # Verify Key parameter
        call_args = mock_s3_client.head_object.call_args
        assert call_args[1]['Key'] == "documents/test.pdf"

    @patch('core.storage.boto3.client')
    def test_check_exists_client_error(self, mock_boto3_client, mock_s3_client, clear_storage_singleton):
        """
        GIVEN StorageService with mocked S3 client
        WHEN check_exists raises ClientError
        THEN return False (error handling)
        """
        mock_boto3_client.return_value = mock_s3_client
        # Simulate ClientError
        error_response = {'Error': {'Code': '403', 'Message': 'Forbidden'}}
        mock_s3_client.head_object.side_effect = ClientError(error_response, 'head_object')

        service = StorageService()
        result = service.check_exists("test/file.txt")

        # Verify returns False on ClientError
        assert result is False


# ============================================================================
# TEST CLASS: GetStorageService
# ============================================================================

class TestGetStorageService:
    """Tests for get_storage_service singleton pattern."""

    @patch('core.storage.boto3.client')
    def test_get_storage_service_returns_singleton(self, mock_boto3_client, clear_storage_singleton):
        """
        GIVEN get_storage_service function
        WHEN called multiple times
        THEN return same StorageService instance (singleton pattern)
        """
        mock_boto3_client.return_value = MagicMock()

        service1 = get_storage_service()
        service2 = get_storage_service()

        assert service1 is service2
        assert isinstance(service1, StorageService)

    @patch('core.storage.boto3.client')
    def test_get_storage_service_creates_instance_on_first_call(self, mock_boto3_client, clear_storage_singleton):
        """
        GIVEN get_storage_service function
        WHEN called for the first time
        THEN create and return new StorageService instance
        """
        mock_boto3_client.return_value = MagicMock()

        # Verify singleton is None
        assert StorageService._instance is None

        # Get service
        service = get_storage_service()

        # Verify instance was created
        assert StorageService._instance is not None
        assert StorageService._instance is service

    @patch('core.storage.boto3.client')
    def test_get_storage_service_reuses_existing_instance(self, mock_boto3_client, clear_storage_singleton):
        """
        GIVEN get_storage_service with existing singleton instance
        WHEN called again
        THEN return existing instance without creating new one
        """
        mock_boto3_client.return_value = MagicMock()

        # Create first instance
        service1 = get_storage_service()

        # Get second instance (should be same)
        service2 = get_storage_service()

        # Verify boto3.client was only called once (instance creation)
        assert mock_boto3_client.call_count == 1
        assert service1 is service2
