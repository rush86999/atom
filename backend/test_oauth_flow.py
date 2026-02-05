#!/usr/bin/env python3
"""
OAuth Flow Test Suite
Tests OAuth User Context and related functionality
"""

from datetime import datetime, timedelta
import os
import sys

# Add backend to path
sys.path.insert(0, '/Users/rushiparikh/projects/atom/backend')

def test_oauth_user_context():
    """Test OAuth User Context implementation"""
    print("\n" + "=" * 70)
    print("TESTING OAUTH USER CONTEXT")
    print("=" * 70)

    from core.oauth_user_context import OAuthUserContext, OAuthUserContextManager

    # Test 1: Context Creation
    print("\n1. Testing Context Creation...")
    context = OAuthUserContext('test_user', 'google')
    assert context.user_id == 'test_user'
    assert context.provider == 'google'
    assert not context.is_authenticated()
    print("   ✅ Context creation works")

    # Test 2: Token Expiry Detection
    print("\n2. Testing Token Expiry Detection...")
    now = datetime.now()

    # Expired token
    expired_connection = {
        'access_token': 'test_token',
        'expires_at': (now - timedelta(minutes=10)).timestamp()
    }
    assert context._is_token_expired(expired_connection) is True
    print("   ✅ Expired tokens detected correctly")

    # Valid token
    valid_connection = {
        'access_token': 'test_token',
        'expires_at': (now + timedelta(hours=1)).timestamp()
    }
    assert context._is_token_expired(valid_connection) is False
    print("   ✅ Valid tokens detected correctly")

    # Token expiring soon (within 5 minutes)
    expiring_soon_connection = {
        'access_token': 'test_token',
        'expires_at': (now + timedelta(minutes=3)).timestamp()
    }
    assert context._is_token_expired(expiring_soon_connection) is True
    print("   ✅ Tokens expiring soon detected correctly")

    # No expiry (never expires)
    no_expiry_connection = {
        'access_token': 'test_token'
    }
    assert context._is_token_expired(no_expiry_connection) is False
    print("   ✅ Tokens without expiry handled correctly")

    # Test 3: ISO String Format
    print("\n3. Testing ISO String Format...")
    expired_str = {
        'access_token': 'test_token',
        'expires_at': (now - timedelta(minutes=10)).isoformat()
    }
    assert context._is_token_expired(expired_str) is True
    print("   ✅ ISO string format handled correctly")

    # Test 4: Manager
    print("\n4. Testing OAuth User Context Manager...")
    manager = OAuthUserContextManager()
    ctx1 = manager.get_context('user1', 'google')
    ctx2 = manager.get_context('user1', 'google')  # Should return cached instance
    assert ctx1 is ctx2
    print("   ✅ Context caching works")

    ctx3 = manager.get_context('user2', 'slack')
    assert ctx3.user_id == 'user2'
    assert ctx3.provider == 'slack'
    print("   ✅ Multiple contexts managed correctly")

    print("\n" + "=" * 70)
    print("✅ ALL OAUTH USER CONTEXT TESTS PASSED")
    print("=" * 70)

    return True


def test_communication_ingestion_pipeline():
    """Test that communication ingestion methods exist and are callable"""
    print("\n" + "=" * 70)
    print("TESTING COMMUNICATION INGESTION PIPELINE")
    print("=" * 70)

    from integrations.atom_communication_ingestion_pipeline import CommunicationIngestionPipeline

    pipeline = CommunicationIngestionPipeline(memory_manager=None)

    # Test that all methods exist
    methods = [
        '_fetch_whatsapp_messages',
        '_fetch_slack_messages',
        '_fetch_teams_messages',
        '_fetch_email_messages',
        '_fetch_gmail_messages',
        '_fetch_outlook_messages'
    ]

    print("\nChecking implemented methods...")
    for method in methods:
        assert hasattr(pipeline, method), f"Missing method: {method}"
        assert callable(getattr(pipeline, method)), f"Method not callable: {method}"
        print(f"   ✅ {method}")

    print("\n" + "=" * 70)
    print("✅ ALL COMMUNICATION INGESTION TESTS PASSED")
    print("=" * 70)

    return True


def test_slack_config():
    """Test Slack configuration updates"""
    print("\n" + "=" * 70)
    print("TESTING SLACK CONFIGURATION")
    print("=" * 70)

    from integrations.slack_config import SlackConfigManager

    manager = SlackConfigManager()

    # Test API config updates
    print("\n1. Testing API config updates...")
    original_client_id = manager.config.api.client_id
    manager.update_config({'client_id': 'test_client_123'})
    assert manager.config.api.client_id == 'test_client_123'
    print("   ✅ Client ID updated")

    manager.update_config({'client_id': original_client_id})
    assert manager.config.api.client_id == original_client_id
    print("   ✅ Client ID restored")

    # Test rate limit updates
    print("\n2. Testing rate limit updates...")
    original_limit = manager.config.rate_limits.tier_1_limit
    manager.update_config({'tier_1_limit': 999})
    assert manager.config.rate_limits.tier_1_limit == 999
    print("   ✅ Rate limits updated")

    manager.update_config({'tier_1_limit': original_limit})
    assert manager.config.rate_limits.tier_1_limit == original_limit
    print("   ✅ Rate limits restored")

    # Test cache config updates
    print("\n3. Testing cache config updates...")
    original_enabled = manager.config.cache.enabled
    manager.update_config({'cache_enabled': not original_enabled})
    assert manager.config.cache.enabled != original_enabled
    print("   ✅ Cache config updated")

    manager.update_config({'cache_enabled': original_enabled})
    assert manager.config.cache.enabled == original_enabled
    print("   ✅ Cache config restored")

    print("\n" + "=" * 70)
    print("✅ ALL SLACK CONFIGURATION TESTS PASSED")
    print("=" * 70)

    return True


def test_google_services():
    """Test Google services don't have dummy classes"""
    print("\n" + "=" * 70)
    print("TESTING GOOGLE SERVICES")
    print("=" * 70)

    # Test Google Calendar Service
    print("\n1. Testing Google Calendar Service...")
    from integrations.google_calendar_service import GOOGLE_APIS_AVAILABLE, GoogleCalendarService

    service = GoogleCalendarService()
    assert hasattr(service, 'authenticate')
    assert hasattr(service, 'get_events')
    print(f"   ✅ Google Calendar Service has proper methods")
    print(f"   ✅ GOOGLE_APIS_AVAILABLE flag: {GOOGLE_APIS_AVAILABLE}")

    # Test Gmail Service
    print("\n2. Testing Gmail Service...")
    from integrations.gmail_service import (
        GOOGLE_APIS_AVAILABLE as GMAIL_API_AVAILABLE,
        GmailService,
    )

    gmail_service = GmailService()
    assert hasattr(gmail_service, '_authenticate')
    print(f"   ✅ Gmail Service has proper methods")
    print(f"   ✅ GMAIL_API_AVAILABLE flag: {GMAIL_API_AVAILABLE}")

    print("\n" + "=" * 70)
    print("✅ ALL GOOGLE SERVICES TESTS PASSED")
    print("=" * 70)

    return True


def main():
    """Run all OAuth flow tests"""
    print("\n" + "=" * 70)
    print("ATOM OAUTH FLOW TEST SUITE")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 70)

    tests = [
        ("OAuth User Context", test_oauth_user_context),
        ("Communication Ingestion Pipeline", test_communication_ingestion_pipeline),
        ("Slack Configuration", test_slack_config),
        ("Google Services", test_google_services),
    ]

    results = {}
    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            if test_func():
                results[test_name] = "✅ PASSED"
                passed += 1
        except Exception as e:
            results[test_name] = f"❌ FAILED: {e}"
            failed += 1
            import traceback
            traceback.print_exc()

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    for test_name, result in results.items():
        print(f"{test_name}: {result}")

    print(f"\nTotal Tests: {len(tests)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {(passed / len(tests) * 100):.1f}%")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
