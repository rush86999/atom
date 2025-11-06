"""
🧪 Zoom Speech-to-Text BYOK System Test Suite
Comprehensive testing for Bring Your Own Key functionality
"""

import pytest
import asyncio
import json
import base64
import secrets
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import asyncpg
import httpx

from zoom_speech_byok_system import (
    ZoomSpeechBYOKManager,
    BYOKKeyRequest,
    ProviderKey,
    ProviderType,
    KeyStatus,
    KeyRotationStatus,
    KeyUsageLog,
    KeyRotation
)

class TestZoomSpeechBYOKManager:
    """Test suite for Zoom Speech BYOK Manager"""
    
    @pytest.fixture
    async def db_pool(self):
        """Mock database pool"""
        pool = AsyncMock()
        pool.acquire = AsyncMock()
        pool.__aenter__ = AsyncMock(return_value=pool)
        pool.__aexit__ = AsyncMock()
        return pool
    
    @pytest.fixture
    def encryption_key(self):
        """Test encryption key"""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    
    @pytest.fixture
    async def byok_manager(self, db_pool, encryption_key):
        """Create BYOK manager for testing"""
        manager = ZoomSpeechBYOKManager(db_pool, encryption_key)
        return manager
    
    @pytest.fixture
    def sample_key_request(self):
        """Sample key request for testing"""
        return BYOKKeyRequest(
            provider="openai",
            key_name="Test OpenAI Key",
            api_key="sk-test123456789",
            account_id="acc_test123",
            account_name="Test Account",
            billing_id="bill_test123",
            key_permissions=["transcription", "analysis"],
            usage_quota=1000000,
            usage_quota_period="monthly",
            rate_limit_per_minute=1000
        )
    
    @pytest.fixture
    def sample_provider_key(self):
        """Sample provider key for testing"""
        return ProviderKey(
            key_id="key_test123456",
            provider=ProviderType.OPENAI,
            key_name="Test OpenAI Key",
            encrypted_key="encrypted_test_key",
            key_hash="hashed_test_key",
            key_algorithm="AES-256-GCM",
            account_id="acc_test123",
            account_name="Test Account",
            billing_id="bill_test123",
            key_permissions=["transcription", "analysis"],
            key_usage_count=0,
            key_status=KeyStatus.ACTIVE,
            rotation_status=KeyRotationStatus.NONE,
            rotation_frequency_days=90,
            usage_quota=1000000,
            usage_quota_period="monthly",
            rate_limit_per_minute=1000,
            metadata={"test": True},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
    
    # Basic Manager Tests
    @pytest.mark.asyncio
    async def test_manager_initialization(self, db_pool, encryption_key):
        """Test BYOK manager initialization"""
        manager = ZoomSpeechBYOKManager(db_pool, encryption_key)
        
        assert manager.db_pool == db_pool
        assert manager.encryption_key == encryption_key
        assert manager.cipher_suite is not None
        assert manager.provider_keys == {}
        assert manager.key_rotation_config is not None
        assert not manager.is_running
    
    @pytest.mark.asyncio
    async def test_manager_start_processing(self, byok_manager):
        """Test manager start processing"""
        with patch.object(byok_manager, '_load_existing_keys') as mock_load:
            mock_load.return_value = None
            
            await byok_manager.start_processing()
            
            assert byok_manager.is_running
            assert len(byok_manager.background_tasks) > 0
            
            await byok_manager.stop_processing()
            assert not byok_manager.is_running
    
    # Key Management Tests
    @pytest.mark.asyncio
    async def test_add_provider_key_success(self, byok_manager, sample_key_request):
        """Test successful provider key addition"""
        with patch.object(byok_manager, '_validate_provider_key') as mock_validate:
            mock_validate.return_value = True
            
            with patch.object(byok_manager, '_store_provider_key') as mock_store:
                mock_store.return_value = None
                
                with patch.object(byok_manager, '_log_security_event') as mock_log:
                    mock_log.return_value = None
                    
                    key = await byok_manager.add_provider_key(
                        sample_key_request, "test_user", "127.0.0.1", "Test-Agent"
                    )
                    
                    assert key is not None
                    assert key.provider == ProviderType.OPENAI
                    assert key.key_name == sample_key_request.key_name
                    assert key.key_status == KeyStatus.PENDING
                    assert key.key_id in byok_manager.provider_keys
                    assert key.key_id in byok_manager.quota_trackers
                    assert byok_manager.metrics['keys_managed'] == 1
                    assert byok_manager.metrics['encryption_operations'] == 1
    
    @pytest.mark.asyncio
    async def test_add_provider_key_validation_failure(self, byok_manager, sample_key_request):
        """Test provider key addition with validation failure"""
        with patch.object(byok_manager, '_validate_provider_key') as mock_validate:
            mock_validate.return_value = False
            
            with patch.object(byok_manager, '_log_security_event') as mock_log:
                mock_log.return_value = None
                
                key = await byok_manager.add_provider_key(
                    sample_key_request, "test_user", "127.0.0.1", "Test-Agent"
                )
                
                assert key is None
                assert byok_manager.metrics['security_incidents'] == 1
    
    @pytest.mark.asyncio
    async def test_get_active_key_success(self, byok_manager, sample_provider_key):
        """Test successful active key retrieval"""
        byok_manager.provider_keys[sample_provider_key.key_id] = sample_provider_key
        
        active_key = await byok_manager.get_active_key(
            ProviderType.OPENAI, sample_provider_key.account_id
        )
        
        assert active_key is not None
        assert active_key.key_id == sample_provider_key.key_id
        assert active_key.provider == ProviderType.OPENAI
        assert active_key.key_status == KeyStatus.ACTIVE
    
    @pytest.mark.asyncio
    async def test_get_active_key_no_active_keys(self, byok_manager):
        """Test active key retrieval with no active keys"""
        sample_key = ProviderKey(
            key_id="key_test",
            provider=ProviderType.OPENAI,
            key_name="Test Key",
            encrypted_key="encrypted",
            key_hash="hash",
            key_algorithm="AES-256-GCM",
            account_id="acc_test",
            account_name="Test Account",
            key_permissions=[],
            key_status=KeyStatus.INACTIVE,  # Inactive key
            rotation_status=KeyRotationStatus.NONE,
            rotation_frequency_days=90
        )
        
        byok_manager.provider_keys[sample_key.key_id] = sample_key
        
        active_key = await byok_manager.get_active_key(ProviderType.OPENAI)
        
        assert active_key is None
    
    @pytest.mark.asyncio
    async def test_get_decrypted_key_success(self, byok_manager, sample_provider_key):
        """Test successful key decryption"""
        byok_manager.provider_keys[sample_provider_key.key_id] = sample_provider_key
        
        with patch.object(byok_manager, '_decrypt_api_key') as mock_decrypt:
            mock_decrypt.return_value = "decrypted_api_key"
            
            with patch.object(byok_manager, '_log_security_event') as mock_log:
                mock_log.return_value = None
                
                decrypted_key = await byok_manager.get_decrypted_key(
                    sample_provider_key.key_id, "test_user", "127.0.0.1", "Test-Agent"
                )
                
                assert decrypted_key == "decrypted_api_key"
                assert byok_manager.metrics['decryption_operations'] == 1
    
    @pytest.mark.asyncio
    async def test_get_decrypted_key_not_found(self, byok_manager):
        """Test key decryption with non-existent key"""
        decrypted_key = await byok_manager.get_decrypted_key(
            "non_existent_key", "test_user", "127.0.0.1", "Test-Agent"
        )
        
        assert decrypted_key is None
    
    @pytest.mark.asyncio
    async def test_rotate_key_success(self, byok_manager, sample_provider_key):
        """Test successful key rotation"""
        byok_manager.provider_keys[sample_provider_key.key_id] = sample_provider_key
        
        new_key_request = BYOKKeyRequest(
            provider="openai",
            key_name="Rotated OpenAI Key",
            api_key="sk-rotated123456789",
            account_id="acc_test123",
            account_name="Test Account"
        )
        
        with patch.object(byok_manager, 'add_provider_key') as mock_add:
            mock_key = ProviderKey(
                key_id="key_rotated123",
                provider=ProviderType.OPENAI,
                key_name="Rotated OpenAI Key",
                encrypted_key="encrypted_rotated",
                key_hash="hash_rotated",
                key_algorithm="AES-256-GCM",
                account_id="acc_test123",
                account_name="Test Account",
                key_permissions=[],
                key_status=KeyStatus.ACTIVE,
                rotation_status=KeyRotationStatus.NONE,
                rotation_frequency_days=90
            )
            mock_add.return_value = mock_key
            
            with patch.object(byok_manager, '_store_key_rotation') as mock_store:
                mock_store.return_value = None
                
                rotation = await byok_manager.rotate_key(
                    sample_provider_key.key_id, 
                    rotation_type="manual",
                    new_key_data=new_key_request,
                    rotation_reason="Manual rotation test"
                )
                
                assert rotation is not None
                assert rotation.key_id == sample_provider_key.key_id
                assert rotation.rotation_type == "manual"
                assert rotation.rotation_status == KeyRotationStatus.COMPLETED
                assert rotation.new_key_id == mock_key.key_id
                assert byok_manager.metrics['key_rotations'] == 1
    
    @pytest.mark.asyncio
    async def test_revoke_key_success(self, byok_manager, sample_provider_key):
        """Test successful key revocation"""
        byok_manager.provider_keys[sample_provider_key.key_id] = sample_provider_key
        byok_manager.quota_trackers[sample_provider_key.key_id] = {
            'current_usage': 0,
            'quota': 1000000,
            'period': 'monthly'
        }
        
        with patch.object(byok_manager, '_update_provider_key') as mock_update:
            mock_update.return_value = None
            
            with patch.object(byok_manager, '_log_security_event') as mock_log:
                mock_log.return_value = None
                
                success = await byok_manager.revoke_key(
                    sample_provider_key.key_id,
                    revoke_reason="Test revocation",
                    revoked_by="test_user",
                    ip_address="127.0.0.1",
                    user_agent="Test-Agent"
                )
                
                assert success
                assert byok_manager.provider_keys[sample_provider_key.key_id].key_status == KeyStatus.REVOKED
                assert sample_provider_key.key_id not in byok_manager.quota_trackers
    
    @pytest.mark.asyncio
    async def test_revoke_key_not_found(self, byok_manager):
        """Test key revocation with non-existent key"""
        success = await byok_manager.revoke_key(
            "non_existent_key",
            revoke_reason="Test revocation"
        )
        
        assert not success
    
    # Usage Tracking Tests
    @pytest.mark.asyncio
    async def test_update_key_usage_success(self, byok_manager, sample_provider_key):
        """Test successful key usage update"""
        byok_manager.provider_keys[sample_provider_key.key_id] = sample_provider_key
        
        with patch.object(byok_manager, '_store_usage_log') as mock_store:
            mock_store.return_value = None
            
            with patch.object(byok_manager, '_check_quota') as mock_quota:
                mock_quota.return_value = None
                
                with patch.object(byok_manager, '_update_cost_tracking') as mock_cost:
                    mock_cost.return_value = None
                    
                    await byok_manager.update_key_usage(
                        sample_provider_key.key_id,
                        usage_type="transcription",
                        audio_duration=120.5,
                        cost_incurred=0.01205,
                        request_id="req_test123",
                        meeting_id="meet_test123",
                        participant_id="part_test123",
                        response_time_ms=234,
                        success=True,
                        user_id="test_user",
                        ip_address="127.0.0.1",
                        user_agent="Test-Agent"
                    )
                    
                    assert len(byok_manager.usage_logs[sample_provider_key.key_id]) == 1
                    assert byok_manager.provider_keys[sample_provider_key.key_id].key_usage_count == 1
                    assert byok_manager.metrics['usage_logs'] == 1
    
    @pytest.mark.asyncio
    async def test_update_key_usage_key_not_found(self, byok_manager):
        """Test key usage update with non-existent key"""
        # Should not raise exception, just log error
        await byok_manager.update_key_usage(
            "non_existent_key",
            usage_type="transcription",
            audio_duration=120.5,
            cost_incurred=0.01205,
            request_id="req_test123",
            user_id="test_user",
            ip_address="127.0.0.1",
            user_agent="Test-Agent"
        )
    
    # Reporting Tests
    @pytest.mark.asyncio
    async def test_get_key_usage_report_success(self, byok_manager, sample_provider_key):
        """Test successful key usage report generation"""
        byok_manager.provider_keys[sample_provider_key.key_id] = sample_provider_key
        
        # Add some usage logs
        usage_log = KeyUsageLog(
            log_id="log_test123",
            key_id=sample_provider_key.key_id,
            provider=ProviderType.OPENAI,
            usage_type="transcription",
            audio_duration=120.5,
            cost_incurred=0.01205,
            request_id="req_test123",
            response_time_ms=234,
            success=True,
            user_id="test_user",
            ip_address="127.0.0.1",
            user_agent="Test-Agent",
            timestamp=datetime.now(timezone.utc)
        )
        
        byok_manager.usage_logs[sample_provider_key.key_id].append(usage_log)
        
        with patch.object(byok_manager, '_get_usage_logs') as mock_get_logs:
            mock_get_logs.return_value = [usage_log]
            
            report = await byok_manager.get_key_usage_report(
                sample_provider_key.key_id,
                datetime.now(timezone.utc) - timedelta(days=30),
                datetime.now(timezone.utc)
            )
            
            assert report is not None
            assert report['key_id'] == sample_provider_key.key_id
            assert report['total_requests'] == 1
            assert report['successful_requests'] == 1
            assert report['total_duration_seconds'] == 120.5
            assert report['total_cost_usd'] == 0.01205
            assert report['success_rate'] == 1.0
    
    @pytest.mark.asyncio
    async def test_get_cost_report_success(self, byok_manager):
        """Test successful cost report generation"""
        with patch.object(byok_manager, '_get_cost_tracking_data') as mock_get_data:
            mock_get_data.return_value = [
                {
                    'provider': 'openai',
                    'total_cost': 100.50,
                    'total_requests': 5000,
                    'total_duration_seconds': 10000,
                    'budget_exceeded': False
                }
            ]
            
            report = await byok_manager.get_cost_report(
                account_id="acc_test123",
                provider=ProviderType.OPENAI,
                period_start=datetime.now(timezone.utc) - timedelta(days=30),
                period_end=datetime.now(timezone.utc)
            )
            
            assert report is not None
            assert report['total_cost_usd'] == 100.50
            assert report['total_requests'] == 5000
            assert report['average_cost_per_request'] == 100.50 / 5000
    
    # Security Tests
    @pytest.mark.asyncio
    async def test_encrypt_api_key(self, byok_manager):
        """Test API key encryption"""
        api_key = "sk-test123456789"
        
        encrypted_key = byok_manager._encrypt_api_key(api_key)
        
        assert encrypted_key is not None
        assert encrypted_key != api_key
        
        # Verify decryption works
        decrypted_key = byok_manager._decrypt_api_key(encrypted_key)
        assert decrypted_key == api_key
    
    @pytest.mark.asyncio
    async def test_decrypt_api_key(self, byok_manager):
        """Test API key decryption"""
        api_key = "sk-test123456789"
        encrypted_key = byok_manager._encrypt_api_key(api_key)
        
        decrypted_key = byok_manager._decrypt_api_key(encrypted_key)
        
        assert decrypted_key == api_key
    
    @pytest.mark.asyncio
    async def test_hash_api_key(self, byok_manager):
        """Test API key hashing"""
        api_key = "sk-test123456789"
        
        key_hash = byok_manager._hash_api_key(api_key)
        
        assert key_hash is not None
        assert key_hash != api_key
        assert len(key_hash) == 64  # SHA-256 hash length
    
    @pytest.mark.asyncio
    async def test_validate_openai_key_success(self, byok_manager):
        """Test OpenAI key validation success"""
        headers = {'Authorization': 'Bearer sk-test123456789'}
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            result = await byok_manager._validate_openai_key(headers, "acc_test123")
            
            assert result
    
    @pytest.mark.asyncio
    async def test_validate_openai_key_failure(self, byok_manager):
        """Test OpenAI key validation failure"""
        headers = {'Authorization': 'Bearer sk-invalid123'}
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            result = await byok_manager._validate_openai_key(headers, "acc_test123")
            
            assert not result
    
    # Performance Tests
    @pytest.mark.asyncio
    async def test_concurrent_key_addition(self, byok_manager, sample_key_request):
        """Test concurrent key addition"""
        with patch.object(byok_manager, '_validate_provider_key') as mock_validate:
            mock_validate.return_value = True
            
            with patch.object(byok_manager, '_store_provider_key') as mock_store:
                mock_store.return_value = None
                
                with patch.object(byok_manager, '_log_security_event') as mock_log:
                    mock_log.return_value = None
                    
                    # Add 10 keys concurrently
                    tasks = []
                    for i in range(10):
                        task = byok_manager.add_provider_key(
                            sample_key_request, f"test_user_{i}", "127.0.0.1", "Test-Agent"
                        )
                        tasks.append(task)
                    
                    results = await asyncio.gather(*tasks)
                    
                    assert len(results) == 10
                    assert len(byok_manager.provider_keys) == 10
                    assert byok_manager.metrics['keys_managed'] == 10
    
    @pytest.mark.asyncio
    async def test_high_frequency_usage_logging(self, byok_manager, sample_provider_key):
        """Test high frequency usage logging"""
        byok_manager.provider_keys[sample_provider_key.key_id] = sample_provider_key
        
        with patch.object(byok_manager, '_store_usage_log') as mock_store:
            mock_store.return_value = None
            
            with patch.object(byok_manager, '_check_quota') as mock_quota:
                mock_quota.return_value = None
                
                with patch.object(byok_manager, '_update_cost_tracking') as mock_cost:
                    mock_cost.return_value = None
                    
                    # Log 1000 usage entries
                    tasks = []
                    for i in range(1000):
                        task = byok_manager.update_key_usage(
                            sample_provider_key.key_id,
                            usage_type="transcription",
                            audio_duration=120.5,
                            cost_incurred=0.01205,
                            request_id=f"req_{i}",
                            user_id="test_user",
                            ip_address="127.0.0.1",
                            user_agent="Test-Agent"
                        )
                        tasks.append(task)
                    
                    await asyncio.gather(*tasks)
                    
                    assert len(byok_manager.usage_logs[sample_provider_key.key_id]) == 1000
                    assert byok_manager.provider_keys[sample_provider_key.key_id].key_usage_count == 1000
    
    # Background Task Tests
    @pytest.mark.asyncio
    async def test_key_rotation_scheduler(self, byok_manager, sample_provider_key):
        """Test key rotation scheduler"""
        # Set up a key that needs rotation
        sample_provider_key.created_at = datetime.now(timezone.utc) - timedelta(days=100)
        sample_provider_key.rotation_frequency_days = 90
        byok_manager.provider_keys[sample_provider_key.key_id] = sample_provider_key
        
        with patch.object(byok_manager, 'rotate_key') as mock_rotate:
            mock_rotate.return_value = None
            
            # Run one iteration of the scheduler
            await byok_manager._key_rotation_scheduler()
            
            # Check if rotation was triggered
            mock_rotate.assert_called()
    
    @pytest.mark.asyncio
    async def test_quota_monitor(self, byok_manager):
        """Test quota monitoring"""
        # Set up a key that exceeds quota
        key_id = "key_test_quota"
        byok_manager.quota_trackers[key_id] = {
            'current_usage': 1500000,  # Exceeds quota of 1000000
            'quota': 1000000,
            'period': 'monthly',
            'period_start': datetime.now(timezone.utc),
            'rate_limiter': asyncio.Semaphore(1000)
        }
        
        with patch.object(byok_manager, '_handle_quota_violation') as mock_handle:
            mock_handle.return_value = None
            
            # Run one iteration of the quota monitor
            await byok_manager._quota_monitor()
            
            # Check if quota violation was handled
            mock_handle.assert_called_with(key_id, byok_manager.quota_trackers[key_id])
    
    # Metrics Tests
    @pytest.mark.asyncio
    async def test_get_metrics(self, byok_manager):
        """Test metrics retrieval"""
        metrics = byok_manager.get_metrics()
        
        assert metrics is not None
        assert 'keys_managed' in metrics
        assert 'encryption_operations' in metrics
        assert 'decryption_operations' in metrics
        assert 'key_rotations' in metrics
        assert 'usage_logs' in metrics
        assert 'quota_violations' in metrics
        assert 'security_incidents' in metrics
    
    # Error Handling Tests
    @pytest.mark.asyncio
    async def test_invalid_provider_type(self):
        """Test handling of invalid provider type"""
        with pytest.raises(ValueError):
            BYOKKeyRequest(
                provider="invalid_provider",
                key_name="Test Key",
                api_key="sk-test123",
                account_id="acc_test",
                account_name="Test Account"
            )
    
    @pytest.mark.asyncio
    async def test_missing_required_fields(self):
        """Test handling of missing required fields"""
        with pytest.raises(Exception):  # Pydantic validation error
            BYOKKeyRequest(
                # Missing required fields
                key_name="Test Key"
            )

class TestBYOKRoutes:
    """Test suite for BYOK API routes"""
    
    @pytest.fixture
    def client(self):
        """Test client fixture"""
        from flask import Flask
        app = Flask(__name__)
        
        # Register blueprint
        from zoom_speech_byok_routes import zoom_speech_byok_bp
        app.register_blueprint(zoom_speech_byok_bp)
        
        return app.test_client()
    
    # API Endpoint Tests
    def test_add_provider_key_success(self, client):
        """Test successful provider key addition via API"""
        with patch('zoom_speech_byok_routes.byok_manager') as mock_manager:
            mock_key = ProviderKey(
                key_id="key_test123",
                provider=ProviderType.OPENAI,
                key_name="Test OpenAI Key",
                encrypted_key="encrypted_test",
                key_hash="hash_test",
                key_algorithm="AES-256-GCM",
                account_id="acc_test123",
                account_name="Test Account",
                key_permissions=[],
                key_status=KeyStatus.PENDING,
                rotation_status=KeyRotationStatus.NONE,
                rotation_frequency_days=90,
                created_at=datetime.now(timezone.utc)
            )
            mock_manager.add_provider_key.return_value = mock_key
            
            response = client.post(
                '/api/zoom/speech/byok/keys/add',
                json={
                    'provider': 'openai',
                    'key_name': 'Test OpenAI Key',
                    'api_key': 'sk-test123456789',
                    'account_id': 'acc_test123',
                    'account_name': 'Test Account'
                },
                headers={'X-Admin-Token': 'test-admin-token'}
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['ok']
            assert data['data']['key_id'] == 'key_test123'
            assert data['data']['provider'] == 'openai'
    
    def test_add_provider_key_missing_token(self, client):
        """Test provider key addition without admin token"""
        response = client.post(
            '/api/zoom/speech/byok/keys/add',
            json={
                'provider': 'openai',
                'key_name': 'Test OpenAI Key',
                'api_key': 'sk-test123456789',
                'account_id': 'acc_test123',
                'account_name': 'Test Account'
            }
        )
        
        assert response.status_code == 403
        data = json.loads(response.data)
        assert not data['ok']
        assert 'Admin privileges required' in data['error']['message']
    
    def test_list_provider_keys_success(self, client):
        """Test successful provider key listing via API"""
        with patch('zoom_speech_byok_routes.byok_manager') as mock_manager:
            mock_keys = [
                ProviderKey(
                    key_id="key_test1",
                    provider=ProviderType.OPENAI,
                    key_name="Test Key 1",
                    encrypted_key="encrypted1",
                    key_hash="hash1",
                    key_algorithm="AES-256-GCM",
                    account_id="acc_test1",
                    account_name="Test Account 1",
                    key_permissions=[],
                    key_status=KeyStatus.ACTIVE,
                    rotation_status=KeyRotationStatus.NONE,
                    rotation_frequency_days=90
                ),
                ProviderKey(
                    key_id="key_test2",
                    provider=ProviderType.GOOGLE,
                    key_name="Test Key 2",
                    encrypted_key="encrypted2",
                    key_hash="hash2",
                    key_algorithm="AES-256-GCM",
                    account_id="acc_test2",
                    account_name="Test Account 2",
                    key_permissions=[],
                    key_status=KeyStatus.ACTIVE,
                    rotation_status=KeyRotationStatus.NONE,
                    rotation_frequency_days=90
                )
            ]
            mock_manager.get_all_keys.return_value = mock_keys
            
            response = client.get(
                '/api/zoom/speech/byok/keys/list',
                headers={'X-Admin-Token': 'test-admin-token'}
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['ok']
            assert len(data['data']['keys']) == 2
            assert data['data']['total_count'] == 2
    
    def test_get_active_key_success(self, client):
        """Test successful active key retrieval via API"""
        with patch('zoom_speech_byok_routes.byok_manager') as mock_manager:
            mock_key = ProviderKey(
                key_id="key_test123",
                provider=ProviderType.OPENAI,
                key_name="Test OpenAI Key",
                encrypted_key="encrypted_test",
                key_hash="hash_test",
                key_algorithm="AES-256-GCM",
                account_id="acc_test123",
                account_name="Test Account",
                key_permissions=[],
                key_status=KeyStatus.ACTIVE,
                rotation_status=KeyRotationStatus.NONE,
                rotation_frequency_days=90
            )
            mock_manager.get_active_key.return_value = mock_key
            mock_manager.update_key_usage.return_value = None
            mock_manager.get_decrypted_key.return_value = "sk-decrypted123456789"
            
            response = client.get(
                '/api/zoom/speech/byok/keys/active?provider=openai',
                headers={'X-Service-Token': 'test-service-token'}
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['ok']
            assert data['data']['key_id'] == 'key_test123'
            assert data['data']['provider'] == 'openai'
            assert data['data']['api_key'] == 'sk-decrypted123456789'
    
    def test_health_check_success(self, client):
        """Test successful health check"""
        with patch('zoom_speech_byok_routes.byok_manager') as mock_manager:
            mock_manager.is_running = True
            mock_manager.db_pool = AsyncMock()
            mock_manager.background_tasks = []
            mock_manager.http_clients = {}
            mock_manager.provider_keys = {}
            mock_manager.get_provider_key.return_value = None
            mock_manager.get_active_keys.return_value = []
            mock_manager.metrics = {
                'keys_managed': 0,
                'encryption_operations': 0,
                'decryption_operations': 0,
                'key_rotations': 0,
                'usage_logs': 0,
                'quota_violations': 0,
                'security_incidents': 0
            }
            mock_manager.key_rotation_config = {
                'auto_rotation_enabled': True,
                'rotation_check_interval_hours': 24,
                'default_rotation_frequency_days': 90,
                'grace_period_days': 7,
                'fallback_enabled': True,
                'rollback_enabled': True
            }
            
            response = client.get('/api/zoom/speech/byok/health')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['ok']
            assert data['data']['byok_manager']
            assert data['data']['manager_running']
            assert data['data']['encryption_available']
            assert data['data']['database_connected']

# Integration Tests
class TestBYOKIntegration:
    """Integration tests for BYOK system"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_key_lifecycle(self):
        """Test complete key lifecycle from addition to deletion"""
        # This would require a real database and actual API keys
        # For testing purposes, we'll mock the external dependencies
        pass
    
    @pytest.mark.asyncio
    async def test_provider_integration(self):
        """Test integration with actual provider APIs"""
        # This would require real API keys for testing
        # Should be run in a separate integration test environment
        pass

# Performance Tests
class TestBYOKPerformance:
    """Performance tests for BYOK system"""
    
    @pytest.mark.asyncio
    async def test_encryption_performance(self, byok_manager):
        """Test encryption performance"""
        import time
        
        # Test encryption of 1000 keys
        start_time = time.time()
        for i in range(1000):
            api_key = f"sk-test123456789_{i}"
            encrypted = byok_manager._encrypt_api_key(api_key)
            assert encrypted is not None
        end_time = time.time()
        
        encryption_time = end_time - start_time
        encryption_ops_per_second = 1000 / encryption_time
        
        # Should handle at least 100 encryption operations per second
        assert encryption_ops_per_second >= 100
    
    @pytest.mark.asyncio
    async def test_decryption_performance(self, byok_manager):
        """Test decryption performance"""
        import time
        
        # Pre-encrypt keys for decryption test
        encrypted_keys = []
        for i in range(1000):
            api_key = f"sk-test123456789_{i}"
            encrypted = byok_manager._encrypt_api_key(api_key)
            encrypted_keys.append(encrypted)
        
        # Test decryption of 1000 keys
        start_time = time.time()
        for encrypted in encrypted_keys:
            decrypted = byok_manager._decrypt_api_key(encrypted)
            assert decrypted is not None
        end_time = time.time()
        
        decryption_time = end_time - start_time
        decryption_ops_per_second = 1000 / decryption_time
        
        # Should handle at least 100 decryption operations per second
        assert decryption_ops_per_second >= 100

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])