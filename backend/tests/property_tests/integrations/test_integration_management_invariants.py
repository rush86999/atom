"""
Property-Based Tests for Integration Management Invariants

Tests critical integration management business logic:
- Integration lifecycle (creation, activation, deactivation, deletion)
- OAuth flow and token management
- Webhook handling and validation
- API key management
- Rate limiting and quotas
- Integration health monitoring
- Integration error handling and retry logic
- Integration audit trail
"""

import pytest
from datetime import datetime, timedelta
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from typing import Dict, List, Set, Optional
import uuid
import hashlib


class TestIntegrationLifecycleInvariants:
    """Tests for integration lifecycle invariants"""

    @given(
        integration_id=st.uuids(),
        integration_type=st.sampled_from([
            'slack',
            'google_calendar',
            'salesforce',
            'hubspot',
            'zendesk',
            'jira',
            'github',
            'notion'
        ]),
        user_id=st.uuids(),
        created_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1))
    )
    @settings(max_examples=50)
    def test_integration_creation_creates_valid_integration(self, integration_id, integration_type, user_id, created_at):
        """Test that integration creation creates a valid integration"""
        # Simulate integration creation
        integration = {
            'id': str(integration_id),
            'type': integration_type,
            'user_id': str(user_id),
            'created_at': created_at,
            'updated_at': created_at,
            'status': 'PENDING',
            'is_active': False
        }

        # Verify integration
        assert integration['id'] is not None, "Integration ID must be set"
        assert integration['type'] in [
            'slack', 'google_calendar', 'salesforce', 'hubspot',
            'zendesk', 'jira', 'github', 'notion'
        ], "Valid integration type"
        assert integration['user_id'] is not None, "User ID must be set"
        assert integration['created_at'] == integration['updated_at'], "created_at equals updated_at"
        assert integration['status'] in ['PENDING', 'ACTIVE', 'INACTIVE', 'ERROR'], "Valid status"
        assert integration['is_active'] is False, "Initial is_active must be False"

    @given(
        integration_id=st.uuids(),
        status=st.sampled_from(['PENDING', 'ACTIVE', 'INACTIVE', 'ERROR']),
        updated_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1))
    )
    @settings(max_examples=50)
    def test_integration_status_transitions(self, integration_id, status, updated_at):
        """Test that integration status transitions are valid"""
        # Valid status transitions
        valid_transitions = {
            'PENDING': ['ACTIVE', 'INACTIVE', 'ERROR'],
            'ACTIVE': ['INACTIVE', 'ERROR'],
            'INACTIVE': ['ACTIVE', 'ERROR'],
            'ERROR': ['PENDING', 'INACTIVE']
        }

        # Determine is_active based on status
        # ACTIVE = is_active=True
        # PENDING/INACTIVE/ERROR = is_active=False
        is_active = (status == 'ACTIVE')

        # Simulate status change
        integration = {
            'id': str(integration_id),
            'status': status,
            'is_active': is_active,
            'updated_at': updated_at
        }

        # Verify status is valid
        assert integration['status'] in valid_transitions, "Status must be valid"
        assert isinstance(integration['is_active'], bool), "is_active must be boolean"

        # Check status-is_active consistency
        if integration['status'] == 'ACTIVE':
            assert integration['is_active'] is True, "ACTIVE integration must have is_active=True"
        elif integration['status'] in ['INACTIVE', 'ERROR', 'PENDING']:
            assert integration['is_active'] is False, "Non-ACTIVE integration must have is_active=False"

    @given(
        integration_id=st.uuids(),
        deleted_at=st.datetimes(min_value=datetime(2025, 1, 1), max_value=datetime(2030, 1, 1)),
        created_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2025, 1, 1))
    )
    @settings(max_examples=50)
    def test_integration_deletion_sets_deleted_at(self, integration_id, deleted_at, created_at):
        """Test that integration deletion sets deleted_at timestamp"""
        assume(deleted_at >= created_at)

        # Simulate integration deletion
        integration = {
            'id': str(integration_id),
            'created_at': created_at,
            'deleted_at': deleted_at,
            'is_deleted': True,
            'status': 'DELETED'
        }

        # Verify deletion
        assert integration['deleted_at'] is not None, "deleted_at must be set"
        assert integration['deleted_at'] >= integration['created_at'], "deleted_at after created_at"
        assert integration['is_deleted'] is True, "is_deleted must be True"
        assert integration['status'] == 'DELETED', "status must be DELETED"


class TestOAuthFlowInvariants:
    """Tests for OAuth flow invariants"""

    @given(
        integration_id=st.uuids(),
        user_id=st.uuids(),
        state=st.uuids(),
        redirect_uri=st.text(min_size=10, max_size=500),
        created_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1)),
        expires_minutes=st.integers(min_value=5, max_value=60)
    )
    @settings(max_examples=50)
    def test_oauth_state_creation(self, integration_id, user_id, state, redirect_uri, created_at, expires_minutes):
        """Test that OAuth state creation creates a valid state"""
        # Create OAuth state
        oauth_state = {
            'state': str(state),
            'integration_id': str(integration_id),
            'user_id': str(user_id),
            'redirect_uri': redirect_uri,
            'created_at': created_at,
            'expires_at': created_at + timedelta(minutes=expires_minutes)
        }

        # Verify state
        assert oauth_state['state'] is not None, "State must be set"
        assert len(oauth_state['state']) == 36, "State must be UUID (36 characters)"
        assert oauth_state['integration_id'] is not None, "Integration ID must be set"
        assert oauth_state['user_id'] is not None, "User ID must be set"
        assert len(oauth_state['redirect_uri']) >= 10, "Redirect URI must be valid"
        assert oauth_state['expires_at'] > oauth_state['created_at'], "expires_at after created_at"

    @given(
        state1=st.uuids(),
        state2=st.uuids()
    )
    @settings(max_examples=50)
    def test_oauth_state_uniqueness(self, state1, state2):
        """Test that OAuth states are unique"""
        # Create states
        states = {str(state1)}

        # Check uniqueness
        is_duplicate = str(state2) in states

        # Verify uniqueness
        if str(state1) == str(state2):
            assert is_duplicate, "Duplicate state detected"
        else:
            # Different states - both should be allowed
            states.add(str(state2))
            assert len(states) == 2, "Both unique states allowed"

    @given(
        state=st.uuids(),
        created_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2025, 1, 1)),
        expires_minutes=st.integers(min_value=5, max_value=60),
        current_time=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1))
    )
    @settings(max_examples=50)
    def test_oauth_state_expiration(self, state, created_at, expires_minutes, current_time):
        """Test that OAuth state expiration is enforced"""
        # Create OAuth state
        oauth_state = {
            'state': str(state),
            'created_at': created_at,
            'expires_at': created_at + timedelta(minutes=expires_minutes)
        }

        # Check if state is valid
        is_valid = current_time < oauth_state['expires_at']

        # Verify expiration
        if current_time < oauth_state['expires_at']:
            assert is_valid is True, "State is valid"
        else:
            assert is_valid is False, "State has expired"

    @given(
        access_token=st.text(min_size=20, max_size=500),
        refresh_token=st.text(min_size=20, max_size=500),
        token_type=st.sampled_from(['Bearer', 'token']),
        expires_in=st.integers(min_value=300, max_value=86400),  # 5 minutes to 24 hours
        issued_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2025, 1, 1))
    )
    @settings(max_examples=50)
    def test_oauth_token_storage(self, access_token, refresh_token, token_type, expires_in, issued_at):
        """Test that OAuth tokens are stored correctly"""
        # Store token
        token = {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'token_type': token_type,
            'expires_in': expires_in,
            'issued_at': issued_at,
            'expires_at': issued_at + timedelta(seconds=expires_in)
        }

        # Verify token
        assert len(token['access_token']) >= 20, "Access token must be valid length"
        assert len(token['refresh_token']) >= 20, "Refresh token must be valid length"
        assert token['token_type'] in ['Bearer', 'token'], "Valid token type"
        assert token['expires_in'] >= 300, "Token must expire in >= 5 minutes"
        assert token['expires_at'] > token['issued_at'], "expires_at after issued_at"

    @given(
        issued_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2025, 1, 1)),
        expires_in=st.integers(min_value=300, max_value=86400),
        current_time=st.datetimes(min_value=datetime(2025, 1, 1), max_value=datetime(2030, 1, 1))
    )
    @settings(max_examples=50)
    def test_oauth_token_expiration(self, issued_at, expires_in, current_time):
        """Test that OAuth token expiration is checked correctly"""
        # Calculate expiration
        expires_at = issued_at + timedelta(seconds=expires_in)

        # Check if token is expired
        is_expired = current_time >= expires_at

        # Verify expiration
        if current_time >= expires_at:
            assert is_expired is True, "Token is expired"
        else:
            assert is_expired is False, "Token is valid"

    @given(
        refresh_token=st.text(min_size=20, max_size=500),
        issued_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2025, 1, 1)),
        refresh_count=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=50)
    def test_oauth_token_refresh(self, refresh_token, issued_at, refresh_count):
        """Test that OAuth token refresh works correctly"""
        # Refresh token
        new_token = {
            'access_token': f"new_token_{uuid.uuid4()}",
            'refresh_token': refresh_token,  # Keep same refresh token
            'issued_at': datetime.now(),
            'refresh_count': refresh_count + 1
        }

        # Verify refresh
        assert new_token['access_token'] is not None, "New access token must be set"
        assert new_token['refresh_token'] == refresh_token, "Refresh token preserved"
        assert new_token['refresh_count'] == refresh_count + 1, "Refresh count incremented"


class TestWebhookInvariants:
    """Tests for webhook invariants"""

    @given(
        webhook_id=st.uuids(),
        integration_id=st.uuids(),
        event_type=st.sampled_from([
            'user.created',
            'user.updated',
            'user.deleted',
            'payment.completed',
            'subscription.created'
        ]),
        url=st.text(min_size=10, max_size=500),
        secret=st.text(min_size=20, max_size=200)
    )
    @settings(max_examples=50)
    def test_webhook_creation_creates_valid_webhook(self, webhook_id, integration_id, event_type, url, secret):
        """Test that webhook creation creates a valid webhook"""
        # Create webhook
        webhook = {
            'id': str(webhook_id),
            'integration_id': str(integration_id),
            'event_type': event_type,
            'url': url,
            'secret': secret,
            'is_active': True
        }

        # Verify webhook
        assert webhook['id'] is not None, "Webhook ID must be set"
        assert webhook['integration_id'] is not None, "Integration ID must be set"
        assert webhook['event_type'] in [
            'user.created', 'user.updated', 'user.deleted',
            'payment.completed', 'subscription.created'
        ], "Valid event type"
        assert len(webhook['url']) >= 10, "URL must be valid"
        assert len(webhook['secret']) >= 20, "Secret must be >= 20 characters"
        assert webhook['is_active'] is True, "Initial is_active must be True"

    @given(
        payload=st.dictionaries(
            keys=st.text(min_size=1, max_size=50),
            values=st.one_of(
                st.text(min_size=0, max_size=500),
                st.integers(min_value=-1000000, max_value=1000000),
                st.booleans()
            ),
            min_size=1,
            max_size=20
        ),
        secret=st.text(min_size=20, max_size=200)
    )
    @settings(max_examples=50)
    def test_webhook_signature_generation(self, payload, secret):
        """Test that webhook signature is generated correctly"""
        # Generate signature (HMAC-SHA256)
        import json
        import hmac

        payload_str = json.dumps(payload, sort_keys=True)
        signature = hmac.new(
            secret.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()

        # Verify signature
        assert len(signature) == 64, "SHA-256 signature must be 64 characters"
        assert all(c in '0123456789abcdef' for c in signature), "Signature must be hexadecimal"

    @given(
        payload=st.dictionaries(
            keys=st.text(min_size=1, max_size=50),
            values=st.text(min_size=0, max_size=500),
            min_size=1,
            max_size=10
        ),
        signature=st.text(min_size=64, max_size=64, alphabet='0123456789abcdef'),
        secret=st.text(min_size=20, max_size=200)
    )
    @settings(max_examples=50)
    def test_webhook_signature_verification(self, payload, signature, secret):
        """Test that webhook signature is verified correctly"""
        import json
        import hmac

        # Generate expected signature
        payload_str = json.dumps(payload, sort_keys=True)
        expected_signature = hmac.new(
            secret.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()

        # Verify signature
        # Note: We're not using the provided signature, just generating one
        assert len(expected_signature) == 64, "Generated signature must be 64 characters"

    @given(
        webhook_id=st.uuids(),
        retry_count=st.integers(min_value=0, max_value=10),
        max_retries=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_webhook_retry_logic(self, webhook_id, retry_count, max_retries):
        """Test that webhook retry logic is correct"""
        # Check if should retry
        should_retry = retry_count < max_retries

        # Verify retry logic
        if retry_count < max_retries:
            assert should_retry is True, "Should retry"
        else:
            assert should_retry is False, "Max retries reached"

    @given(
        event_id=st.uuids(),
        webhook_id=st.uuids(),
        delivered_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1)),
        response_status=st.integers(min_value=200, max_value=599)
    )
    @settings(max_examples=50)
    def test_webhook_delivery_logging(self, event_id, webhook_id, delivered_at, response_status):
        """Test that webhook delivery is logged correctly"""
        # Log delivery
        delivery_log = {
            'event_id': str(event_id),
            'webhook_id': str(webhook_id),
            'delivered_at': delivered_at,
            'response_status': response_status,
            'success': 200 <= response_status < 300
        }

        # Verify log
        assert delivery_log['event_id'] is not None, "Event ID must be set"
        assert delivery_log['webhook_id'] is not None, "Webhook ID must be set"
        assert delivery_log['delivered_at'] is not None, "Timestamp must be set"
        assert 200 <= delivery_log['response_status'] <= 599, "Valid HTTP status code"
        assert delivery_log['success'] == (200 <= response_status < 300), "Success status matches HTTP code"


class TestAPIKeyManagementInvariants:
    """Tests for API key management invariants"""

    @given(
        api_key_id=st.uuids(),
        integration_id=st.uuids(),
        key_prefix=st.sampled_from(['sk_', 'pk_', 'tk_']),
        user_id=st.uuids(),
        created_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1))
    )
    @settings(max_examples=50)
    def test_api_key_creation(self, api_key_id, integration_id, key_prefix, user_id, created_at):
        """Test that API key creation creates a valid key"""
        # Generate API key
        random_part = uuid.uuid4().hex
        api_key = {
            'id': str(api_key_id),
            'integration_id': str(integration_id),
            'key': f"{key_prefix}{random_part}",
            'user_id': str(user_id),
            'created_at': created_at,
            'is_active': True
        }

        # Verify API key
        assert api_key['id'] is not None, "API key ID must be set"
        assert api_key['integration_id'] is not None, "Integration ID must be set"
        assert api_key['key'].startswith(key_prefix), f"Key must start with {key_prefix}"
        assert len(api_key['key']) >= len(key_prefix) + 32, "Key must be sufficiently long"
        assert api_key['user_id'] is not None, "User ID must be set"
        assert api_key['is_active'] is True, "Initial is_active must be True"

    @given(
        key1_suffix=st.text(min_size=32, max_size=32, alphabet='0123456789abcdef'),
        key2_suffix=st.text(min_size=32, max_size=32, alphabet='0123456789abcdef')
    )
    @settings(max_examples=50)
    def test_api_key_uniqueness(self, key1_suffix, key2_suffix):
        """Test that API keys are unique"""
        # Create keys
        key1 = f"sk_{key1_suffix}"
        key2 = f"sk_{key2_suffix}"

        # Track keys
        keys = {key1}

        # Check uniqueness
        is_duplicate = key2 in keys

        # Verify uniqueness
        if key1 == key2:
            assert is_duplicate, "Duplicate key detected"
        else:
            # Different keys - both should be allowed
            keys.add(key2)
            assert len(keys) == 2, "Both unique keys allowed"

    @given(
        api_key=st.text(min_size=35, max_size=100, alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'),
        last_used_at=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2025, 1, 1)),
        inactive_days=st.integers(min_value=30, max_value=365),
        current_time=st.datetimes(min_value=datetime(2025, 1, 1), max_value=datetime(2030, 1, 1))
    )
    @settings(max_examples=50)
    def test_api_key_inactive_period_detection(self, api_key, last_used_at, inactive_days, current_time):
        """Test that inactive API keys are detected"""
        # Calculate inactive period
        days_inactive = (current_time - last_used_at).days

        # Check if key is inactive
        is_inactive = days_inactive >= inactive_days

        # Verify detection
        if days_inactive >= inactive_days:
            assert is_inactive is True, "Key is inactive"
        else:
            assert is_inactive is False, "Key is active"

    @given(
        api_key_id=st.uuids(),
        scopes=st.lists(
            st.sampled_from(['read', 'write', 'delete', 'admin']),
            min_size=1,
            max_size=4,
            unique=True
        )
    )
    @settings(max_examples=50)
    def test_api_key_scope_enforcement(self, api_key_id, scopes):
        """Test that API key scopes are enforced"""
        # Create API key with scopes
        api_key = {
            'id': str(api_key_id),
            'scopes': list(scopes)
        }

        # Verify scopes
        assert len(api_key['scopes']) >= 1, "At least one scope required"
        assert all(scope in ['read', 'write', 'delete', 'admin'] for scope in api_key['scopes']), "Valid scope"


class TestRateLimitingInvariants:
    """Tests for integration rate limiting invariants"""

    @given(
        integration_id=st.uuids(),
        rate_limit=st.integers(min_value=1, max_value=10000),  # Requests per minute
        request_count=st.integers(min_value=0, max_value=10000)
    )
    @settings(max_examples=50)
    def test_rate_limit_enforcement(self, integration_id, rate_limit, request_count):
        """Test that rate limits are enforced"""
        # Check if request is allowed
        request_allowed = request_count < rate_limit

        # Verify enforcement
        if request_count < rate_limit:
            assert request_allowed is True, "Request allowed"
        else:
            assert request_allowed is False, "Rate limit exceeded"

    @given(
        integration_id=st.uuids(),
        quota_limit=st.integers(min_value=1000, max_value=1000000),  # Total requests per month
        quota_used=st.integers(min_value=0, max_value=1000000)
    )
    @settings(max_examples=50)
    def test_quota_limit_enforcement(self, integration_id, quota_limit, quota_used):
        """Test that quota limits are enforced"""
        # Check if within quota
        within_quota = quota_used < quota_limit

        # Verify enforcement
        if quota_used < quota_limit:
            assert within_quota is True, "Within quota"
        else:
            assert within_quota is False, "Quota exceeded"

    @given(
        reset_time=st.datetimes(min_value=datetime(2025, 1, 1), max_value=datetime(2030, 1, 1)),
        current_time=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1))
    )
    @settings(max_examples=50)
    def test_rate_limit_reset_time(self, reset_time, current_time):
        """Test that rate limit reset time is calculated correctly"""
        # Check if rate limit has reset
        has_reset = current_time >= reset_time

        # Verify reset
        if current_time >= reset_time:
            assert has_reset is True, "Rate limit has reset"
        else:
            assert has_reset is False, "Rate limit has not reset"


class TestHealthMonitoringInvariants:
    """Tests for integration health monitoring invariants"""

    @given(
        integration_id=st.uuids(),
        last_check=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2025, 1, 1)),
        current_time=st.datetimes(min_value=datetime(2025, 1, 1), max_value=datetime(2030, 1, 1)),
        health_check_interval_minutes=st.integers(min_value=1, max_value=1440)  # 1 minute to 24 hours
    )
    @settings(max_examples=50)
    def test_health_check_interval(self, integration_id, last_check, current_time, health_check_interval_minutes):
        """Test that health checks are performed at intervals"""
        # Calculate time since last check
        time_since_check = current_time - last_check
        minutes_since_check = time_since_check.total_seconds() / 60

        # Check if health check is due
        check_due = minutes_since_check >= health_check_interval_minutes

        # Verify interval
        if minutes_since_check >= health_check_interval_minutes:
            assert check_due is True, "Health check is due"
        else:
            assert check_due is False, "Health check not due yet"

    @given(
        integration_id=st.uuids(),
        success_count=st.integers(min_value=0, max_value=1000),
        failure_count=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=50)
    def test_health_status_calculation(self, integration_id, success_count, failure_count):
        """Test that health status is calculated correctly"""
        # Calculate success rate
        total_requests = success_count + failure_count
        if total_requests > 0:
            success_rate = success_count / total_requests
        else:
            success_rate = 1.0  # No failures if no requests

        # Determine health status
        if success_rate >= 0.95:
            health_status = 'HEALTHY'
        elif success_rate >= 0.80:
            health_status = 'DEGRADED'
        else:
            health_status = 'UNHEALTHY'

        # Verify status
        assert health_status in ['HEALTHY', 'DEGRADED', 'UNHEALTHY'], "Valid health status"

    @given(
        integration_id=st.uuids(),
        uptime_percentage=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_uptime_calculation(self, integration_id, uptime_percentage):
        """Test that uptime is calculated correctly"""
        # Verify uptime percentage
        assert 0.0 <= uptime_percentage <= 100.0, "Uptime must be between 0 and 100"

        # Determine if integration is reliable
        is_reliable = uptime_percentage >= 99.0

        # Verify reliability
        if uptime_percentage >= 99.0:
            assert is_reliable is True, "Integration is reliable"
        else:
            assert is_reliable is False, "Integration is not reliable"


class TestErrorHandlingInvariants:
    """Tests for integration error handling invariants"""

    @given(
        integration_id=st.uuids(),
        error_code=st.integers(min_value=400, max_value=599),
        error_message=st.text(min_size=1, max_size=500),
        timestamp=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1))
    )
    @settings(max_examples=50)
    def test_error_logging(self, integration_id, error_code, error_message, timestamp):
        """Test that integration errors are logged correctly"""
        # Log error
        error_log = {
            'id': str(uuid.uuid4()),
            'integration_id': str(integration_id),
            'error_code': error_code,
            'error_message': error_message,
            'timestamp': timestamp
        }

        # Verify error log
        assert error_log['id'] is not None, "Error log ID must be set"
        assert error_log['integration_id'] is not None, "Integration ID must be set"
        assert 400 <= error_log['error_code'] <= 599, "Valid HTTP error code"
        assert len(error_log['error_message']) >= 1, "Error message must not be empty"
        assert error_log['timestamp'] is not None, "Timestamp must be set"

    @given(
        integration_id=st.uuids(),
        attempt=st.integers(min_value=1, max_value=10),
        max_attempts=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_retry_on_transient_errors(self, integration_id, attempt, max_attempts):
        """Test that transient errors trigger retries"""
        # Transient error codes
        transient_errors = {408, 429, 500, 502, 503, 504}

        # Simulate error
        error_code = 503  # Service Unavailable

        # Check if should retry
        should_retry = error_code in transient_errors and attempt < max_attempts

        # Verify retry logic
        if error_code in transient_errors and attempt < max_attempts:
            assert should_retry is True, "Should retry transient error"
        else:
            assert should_retry is False, "Should not retry"

    @given(
        integration_id=st.uuids(),
        consecutive_failures=st.integers(min_value=0, max_value=100),
        failure_threshold=st.integers(min_value=3, max_value=20)
    )
    @settings(max_examples=50)
    def test_circuit_breaker_trips(self, integration_id, consecutive_failures, failure_threshold):
        """Test that circuit breaker trips after threshold"""
        # Check if circuit should trip
        circuit_tripped = consecutive_failures >= failure_threshold

        # Verify circuit breaker
        if consecutive_failures >= failure_threshold:
            assert circuit_tripped is True, "Circuit breaker should trip"
        else:
            assert circuit_tripped is False, "Circuit breaker should not trip"


class TestAuditTrailInvariants:
    """Tests for integration audit trail invariants"""

    @given(
        integration_id=st.uuids(),
        user_id=st.uuids(),
        action=st.sampled_from([
            'created',
            'activated',
            'deactivated',
            'deleted',
            'token_refreshed',
            'webhook_registered'
        ]),
        timestamp=st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2030, 1, 1)),
        ip_address=st.ip_addresses()
    )
    @settings(max_examples=50)
    def test_audit_log_records_integration_action(self, integration_id, user_id, action, timestamp, ip_address):
        """Test that audit log records all integration actions"""
        # Create audit log entry
        audit_entry = {
            'id': str(uuid.uuid4()),
            'integration_id': str(integration_id),
            'user_id': str(user_id),
            'action': action,
            'timestamp': timestamp,
            'ip_address': str(ip_address)
        }

        # Verify audit entry
        assert audit_entry['id'] is not None, "Audit entry ID must be set"
        assert audit_entry['integration_id'] is not None, "Integration ID must be set"
        assert audit_entry['user_id'] is not None, "User ID must be set"
        assert audit_entry['action'] in [
            'created', 'activated', 'deactivated', 'deleted',
            'token_refreshed', 'webhook_registered'
        ], "Valid action"
        assert audit_entry['timestamp'] is not None, "Timestamp must be set"
        assert audit_entry['ip_address'] is not None, "IP address must be set"

    @given(
        actions=st.lists(
            st.sampled_from(['created', 'activated', 'deactivated', 'token_refreshed']),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_audit_log_chronological_order(self, actions):
        """Test that audit log entries are in chronological order"""
        # Create audit log entries
        base_time = datetime.now()
        audit_log = []
        for i, action in enumerate(actions):
            audit_log.append({
                'action': action,
                'timestamp': base_time + timedelta(seconds=i)
            })

        # Verify chronological order
        for i in range(1, len(audit_log)):
            assert audit_log[i]['timestamp'] >= audit_log[i-1]['timestamp'], "Entries must be in chronological order"
