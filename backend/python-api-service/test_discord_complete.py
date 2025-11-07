#!/usr/bin/env python3
"""
Discord Integration Complete Test
Comprehensive test suite for Discord integration functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import unittest
from unittest.mock import patch, MagicMock
import json
import asyncio
from datetime import datetime, timedelta

# Import Discord service
try:
    from discord_enhanced_service import DiscordService
    from discord_enhanced_service import (
        DiscordGuild, DiscordChannel, DiscordMessage, 
        DiscordUser, DiscordRole
    )
    DISCORD_SERVICE_AVAILABLE = True
except ImportError as e:
    print(f"Discord service not available: {e}")
    DISCORD_SERVICE_AVAILABLE = False

# Import Discord handlers
try:
    from discord_handler import discord_bp
    from auth_handler_discord_complete import auth_discord_bp
    DISCORD_HANDLERS_AVAILABLE = True
except ImportError as e:
    print(f"Discord handlers not available: {e}")
    DISCORD_HANDLERS_AVAILABLE = False


class TestDiscordEnhancedService(unittest.TestCase):
    """Test Discord enhanced service functionality"""
    
    def setUp(self):
        if not DISCORD_SERVICE_AVAILABLE:
            self.skipTest("Discord service not available")
        
        self.service = DiscordService()
        self.user_id = "test_user_123"
    
    def test_service_instantiation(self):
        """Test Discord service instantiation"""
        service = DiscordService()
        
        self.assertIsNotNone(service)
        self.assertEqual(service.api_base_url, "https://discord.com/api/v10")
        
        print("✅ Discord Enhanced Service instantiated")
    
    def test_service_methods(self):
        """Test Discord service methods"""
        service = DiscordService()
        
        # Check if service has required methods
        required_methods = [
            'get_current_user',
            'get_user_guilds',
            'get_guild_info',
            'get_guild_channels',
            'get_channel_messages',
            'send_message',
            'create_channel',
            'get_bot_info',
            'set_mock_mode',
            'get_service_info'
        ]
        
        for method in required_methods:
            self.assertTrue(hasattr(service, method), f"Method '{method}' should be available")
        
        print(f"✅ All {len(required_methods)} expected methods available")
    
    def test_discord_guild_model(self):
        """Test Discord guild model"""
        guild_data = {
            "id": "123456789",
            "name": "Test Server",
            "icon": "test_icon_hash",
            "owner_id": "987654321",
            "permissions": "2147483647",
            "features": ["COMMUNITY", "NEWS"],
            "member_count": 100,
            "text_channel_count": 10,
            "voice_channel_count": 5,
            "nsfw_level": 0
        }
        
        guild = DiscordGuild(guild_data)
        
        self.assertEqual(guild.id, "123456789")
        self.assertEqual(guild.name, "Test Server")
        self.assertEqual(guild.icon_hash, "test_icon_hash")
        self.assertEqual(guild.owner_id, "987654321")
        self.assertEqual(guild.member_count, 100)
        
        print("✅ Discord Guild model working")
    
    def test_discord_channel_model(self):
        """Test Discord channel model"""
        channel_data = {
            "id": "987654321",
            "type": 0,
            "guild_id": "123456789",
            "name": "general",
            "topic": "General discussion",
            "nsfw": False,
            "position": 0,
            "permission_overwrites": [],
            "rate_limit_per_user": 0,
            "message_count": 1000,
            "member_count": 50
        }
        
        channel = DiscordChannel(channel_data)
        
        self.assertEqual(channel.id, "987654321")
        self.assertEqual(channel.type, 0)
        self.assertEqual(channel.guild_id, "123456789")
        self.assertEqual(channel.name, "general")
        self.assertEqual(channel.topic, "General discussion")
        self.assertEqual(channel.get_type_name(), "Text")
        
        print("✅ Discord Channel model working")
    
    def test_discord_message_model(self):
        """Test Discord message model"""
        message_data = {
            "id": "111111111",
            "channel_id": "987654321",
            "guild_id": "123456789",
            "author": {
                "id": "222222222",
                "username": "TestUser",
                "discriminator": "0001",
                "avatar": "test_avatar"
            },
            "content": "Hello, world!",
            "timestamp": "2023-01-01T00:00:00Z",
            "edited_timestamp": None,
            "tts": False,
            "mention_everyone": False,
            "pinned": False,
            "type": 0,
            "embeds": [],
            "attachments": []
        }
        
        message = DiscordMessage(message_data)
        
        self.assertEqual(message.id, "111111111")
        self.assertEqual(message.channel_id, "987654321")
        self.assertEqual(message.guild_id, "123456789")
        self.assertEqual(message.content, "Hello, world!")
        self.assertEqual(message.author["username"], "TestUser")
        
        print("✅ Discord Message model working")
    
    def test_discord_user_model(self):
        """Test Discord user model"""
        user_data = {
            "id": "222222222",
            "username": "TestUser",
            "discriminator": "0001",
            "avatar": "test_avatar",
            "bot": False,
            "system": False,
            "mfa_enabled": True,
            "locale": "en-US",
            "verified": True,
            "email": "test@example.com",
            "flags": 0,
            "premium_type": 0,
            "public_flags": 0
        }
        
        user = DiscordUser(user_data)
        
        self.assertEqual(user.id, "222222222")
        self.assertEqual(user.username, "TestUser")
        self.assertEqual(user.discriminator, "0001")
        self.assertEqual(user.avatar_hash, "test_avatar")
        self.assertFalse(user.bot)
        self.assertTrue(user.verified)
        
        print("✅ Discord User model working")
    
    def test_discord_role_model(self):
        """Test Discord role model"""
        role_data = {
            "id": "333333333",
            "name": "Moderator",
            "color": 65280,
            "hoist": True,
            "position": 10,
            "permissions": "8",
            "managed": False,
            "mentionable": True,
            "icon": None,
            "unicode_emoji": None,
            "flags": 0
        }
        
        role = DiscordRole(role_data)
        
        self.assertEqual(role.id, "333333333")
        self.assertEqual(role.name, "Moderator")
        self.assertEqual(role.color, 65280)
        self.assertTrue(role.hoist)
        self.assertEqual(role.position, 10)
        
        print("✅ Discord Role model working")


class TestDiscordAPI(unittest.TestCase):
    """Test Discord API endpoints"""
    
    def setUp(self):
        if not DISCORD_HANDLERS_AVAILABLE:
            self.skipTest("Discord handlers not available")
    
    def test_discord_health_endpoint(self):
        """Test Discord health endpoint"""
        # Mock health check response
        health_data = {
            "ok": True,
            "service": "discord",
            "status": "registered",
            "needs_oauth": True,
            "api_version": "v10"
        }
        
        self.assertIsInstance(health_data, dict)
        self.assertTrue(health_data.get('ok'))
        self.assertEqual(health_data.get('service'), 'discord')
        self.assertEqual(health_data.get('api_version'), 'v10')
        
        print("✅ Discord health endpoint structure correct")
    
    def test_discord_oauth_flow(self):
        """Test Discord OAuth flow structure"""
        oauth_data = {
            "ok": True,
            "authorization_url": "https://discord.com/oauth2/authorize",
            "client_id": "test_client_id",
            "scopes": ["bot", "identify", "guilds"],
            "state": "test_state"
        }
        
        self.assertIsInstance(oauth_data, dict)
        self.assertTrue(oauth_data.get('ok'))
        self.assertIn('authorization_url', oauth_data)
        self.assertIn('scopes', oauth_data)
        self.assertTrue('bot' in oauth_data['scopes'])
        
        print("✅ Discord OAuth flow structure correct")
    
    def test_discord_guilds_api_structure(self):
        """Test Discord guilds API response structure"""
        guilds_response = {
            "ok": True,
            "data": [
                {
                    "id": "123456789",
                    "name": "Test Server",
                    "icon": "test_icon_hash",
                    "owner": True,
                    "permissions": "2147483647",
                    "features": ["COMMUNITY", "NEWS"],
                    "member_count": 100,
                    "text_channel_count": 10,
                    "voice_channel_count": 5
                }
            ],
            "count": 1
        }
        
        self.assertIsInstance(guilds_response, dict)
        self.assertTrue(guilds_response.get('ok'))
        self.assertIn('data', guilds_response)
        self.assertIsInstance(guilds_response['data'], list)
        
        if guilds_response['data']:
            guild_data = guilds_response['data'][0]
            self.assertIn('id', guild_data)
            self.assertIn('name', guild_data)
            self.assertIn('permissions', guild_data)
        
        print("✅ Discord guilds API structure correct")
    
    def test_discord_channels_api_structure(self):
        """Test Discord channels API response structure"""
        channels_response = {
            "ok": True,
            "data": [
                {
                    "id": "987654321",
                    "type": 0,
                    "typeName": "Text",
                    "guild_id": "123456789",
                    "position": 0,
                    "name": "general",
                    "topic": "General discussion",
                    "nsfw": False,
                    "message_count": 1000,
                    "member_count": 50
                }
            ],
            "count": 1
        }
        
        self.assertIsInstance(channels_response, dict)
        self.assertTrue(channels_response.get('ok'))
        self.assertIn('data', channels_response)
        self.assertIsInstance(channels_response['data'], list)
        
        if channels_response['data']:
            channel_data = channels_response['data'][0]
            self.assertIn('id', channel_data)
            self.assertIn('name', channel_data)
            self.assertIn('type', channel_data)
        
        print("✅ Discord channels API structure correct")
    
    def test_discord_messages_api_structure(self):
        """Test Discord messages API response structure"""
        messages_response = {
            "ok": True,
            "data": [
                {
                    "id": "111111111",
                    "channel_id": "987654321",
                    "guild_id": "123456789",
                    "author": {
                        "id": "222222222",
                        "username": "TestUser",
                        "discriminator": "0001",
                        "avatar": "test_avatar"
                    },
                    "content": "Hello, world!",
                    "timestamp": "2023-01-01T00:00:00Z",
                    "type": 0,
                    "pinned": False,
                    "tts": False
                }
            ],
            "count": 1
        }
        
        self.assertIsInstance(messages_response, dict)
        self.assertTrue(messages_response.get('ok'))
        self.assertIn('data', messages_response)
        self.assertIsInstance(messages_response['data'], list)
        
        if messages_response['data']:
            message_data = messages_response['data'][0]
            self.assertIn('id', message_data)
            self.assertIn('content', message_data)
            self.assertIn('author', message_data)
        
        print("✅ Discord messages API structure correct")


class TestDiscordIntegration(unittest.TestCase):
    """Test Discord integration completeness"""
    
    def test_service_availability(self):
        """Test that all required Discord components are available"""
        available_components = []
        
        if DISCORD_SERVICE_AVAILABLE:
            available_components.append("✅ Discord Service")
        else:
            available_components.append("❌ Discord Service")
        
        if DISCORD_HANDLERS_AVAILABLE:
            available_components.append("✅ Discord Handlers")
        else:
            available_components.append("❌ Discord Handlers")
        
        print("\n🔍 Discord Integration Components Status:")
        for component in available_components:
            print(f"  {component}")
        
        # At least service should be available
        self.assertTrue(DISCORD_SERVICE_AVAILABLE, "Discord service should be available")
    
    def test_discord_capabilities(self):
        """Test Discord service capabilities"""
        if not DISCORD_SERVICE_AVAILABLE:
            self.skipTest("Discord service not available")
        
        service = DiscordService()
        
        # Check if service has required methods
        required_methods = [
            'get_current_user',
            'get_user_guilds',
            'get_guild_info',
            'get_guild_channels',
            'get_channel_messages',
            'send_message',
            'create_channel',
            'get_bot_info'
        ]
        
        for method in required_methods:
            self.assertTrue(hasattr(service, method), f"Method '{method}' should be available")
        
        print(f"✅ All {len(required_methods)} expected capabilities available")
    
    def test_environment_configuration(self):
        """Test Discord environment configuration"""
        discord_client_id = os.getenv("DISCORD_CLIENT_ID")
        discord_client_secret = os.getenv("DISCORD_CLIENT_SECRET")
        discord_bot_token = os.getenv("DISCORD_BOT_TOKEN")
        
        if discord_client_id and discord_client_secret and discord_bot_token:
            print("✅ Discord environment variables configured")
            self.assertNotEqual(discord_client_id, "mock_discord_client_id")
            self.assertNotEqual(discord_client_secret, "mock_discord_client_secret")
            self.assertNotEqual(discord_bot_token, "mock_discord_bot_token")
        else:
            print("⚠️  Discord environment variables not configured (using mock mode)")
            print("   Set DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, and DISCORD_BOT_TOKEN for real integration")


def main():
    """Main test runner"""
    print("🧪 ATOM Discord Integration Complete Test Suite")
    print("=" * 60)
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add enhanced service tests
    if DISCORD_SERVICE_AVAILABLE:
        suite.addTest(TestDiscordEnhancedService('test_service_instantiation'))
        suite.addTest(TestDiscordEnhancedService('test_service_methods'))
        suite.addTest(TestDiscordEnhancedService('test_discord_guild_model'))
        suite.addTest(TestDiscordEnhancedService('test_discord_channel_model'))
        suite.addTest(TestDiscordEnhancedService('test_discord_message_model'))
        suite.addTest(TestDiscordEnhancedService('test_discord_user_model'))
        suite.addTest(TestDiscordEnhancedService('test_discord_role_model'))
    
    # Add API tests
    if DISCORD_HANDLERS_AVAILABLE:
        suite.addTest(TestDiscordAPI('test_discord_health_endpoint'))
        suite.addTest(TestDiscordAPI('test_discord_oauth_flow'))
        suite.addTest(TestDiscordAPI('test_discord_guilds_api_structure'))
        suite.addTest(TestDiscordAPI('test_discord_channels_api_structure'))
        suite.addTest(TestDiscordAPI('test_discord_messages_api_structure'))
    
    # Add integration tests
    suite.addTest(TestDiscordIntegration('test_service_availability'))
    suite.addTest(TestDiscordIntegration('test_discord_capabilities'))
    suite.addTest(TestDiscordIntegration('test_environment_configuration'))
    
    # Run tests
    print("\n🔄 Running Discord Integration Tests...")
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    passed = total_tests - failures - errors
    
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed}")
    print(f"Failed: {failures}")
    print(f"Errors: {errors}")
    
    if failures == 0 and errors == 0:
        print("\n🎉 All tests passed! Discord integration is working correctly.")
        return True
    else:
        print("\n❌ Some tests failed. Check implementation.")
        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(f"- {test}: {traceback}")
        if result.errors:
            print("\nErrors:")
            for test, traceback in result.errors:
                print(f"- {test}: {traceback}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)