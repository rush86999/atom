"""
Test Suite for User API Key Management

This module provides comprehensive testing for the BYOK (Bring Your Own Keys) system,
including the new GLM-4.6 and Kimi K2 providers.
"""

import unittest
import json
import os
import sqlite3
import tempfile
from unittest.mock import patch, MagicMock

from user_api_key_service import UserAPIKeyService
from user_api_key_routes import AVAILABLE_AI_PROVIDERS


class TestUserAPIKeyService(unittest.TestCase):
    """Test cases for UserAPIKeyService"""

    def setUp(self):
        """Set up test environment"""
        # Create temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        
        self.test_service = UserAPIKeyService(self.temp_db.name)
        self.test_user_id = "test_user_123"
        
        # Test API keys (these are fake keys for testing)
        self.test_keys = {
            "openai": "sk-test-key-123456789",
            "deepseek": "sk-deepseek-test-123456",
            "anthropic": "sk-ant-test-123456789",
            "google_gemini": "AIzaTestKey123456789",
            "glm_4_6": "glm-test-key-123456789",
            "kimi_k2": "sk-kimi-test-123456789"
        }

    def tearDown(self):
        """Clean up test environment"""
        # Remove temporary database
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def test_encryption_decryption(self):
        """Test API key encryption and decryption"""
        original_key = "sk-test-key-123456789"
        
        # Test encryption
        encrypted_key = self.test_service._encrypt_key(original_key)
        self.assertNotEqual(original_key, encrypted_key)
        self.assertIsInstance(encrypted_key, str)
        
        # Test decryption
        decrypted_key = self.test_service._decrypt_key(encrypted_key)
        self.assertEqual(original_key, decrypted_key)

    def test_save_api_key(self):
        """Test saving API keys"""
        for provider, api_key in self.test_keys.items():
            if provider in AVAILABLE_AI_PROVIDERS:
                success = self.test_service.save_api_key(
                    self.test_user_id, provider, api_key
                )
                self.assertTrue(success, f"Failed to save API key for {provider}")

    def test_get_api_key(self):
        """Test retrieving API keys"""
        provider = "openai"
        api_key = self.test_keys[provider]
        
        # Save key first
        self.test_service.save_api_key(self.test_user_id, provider, api_key)
        
        # Retrieve key
        retrieved_key = self.test_service.get_api_key(self.test_user_id, provider)
        self.assertEqual(api_key, retrieved_key)

    def test_get_nonexistent_api_key(self):
        """Test retrieving non-existent API key"""
        result = self.test_service.get_api_key(self.test_user_id, "nonexistent_provider")
        self.assertIsNone(result)

    def test_delete_api_key(self):
        """Test deleting API keys"""
        provider = "deepseek"
        api_key = self.test_keys[provider]
        
        # Save key first
        self.test_service.save_api_key(self.test_user_id, provider, api_key)
        
        # Verify key exists
        retrieved_key = self.test_service.get_api_key(self.test_user_id, provider)
        self.assertEqual(api_key, retrieved_key)
        
        # Delete key
        success = self.test_service.delete_api_key(self.test_user_id, provider)
        self.assertTrue(success)
        
        # Verify key is deleted
        deleted_key = self.test_service.get_api_key(self.test_user_id, provider)
        self.assertIsNone(deleted_key)

    def test_list_user_services(self):
        """Test listing user's configured services"""
        # Save some keys
        providers_to_save = ["openai", "deepseek", "glm_4_6", "kimi_k2"]
        for provider in providers_to_save:
            if provider in AVAILABLE_AI_PROVIDERS:
                self.test_service.save_api_key(
                    self.test_user_id, provider, self.test_keys[provider]
                )
        
        # List services
        services = self.test_service.list_user_services(self.test_user_id)
        
        # Check that saved providers are in the list
        for provider in providers_to_save:
            if provider in AVAILABLE_AI_PROVIDERS:
                self.assertIn(provider, services)
        
        # Check that non-saved providers are not in the list
        self.assertNotIn("nonexistent_provider", services)

    def test_get_all_user_keys(self):
        """Test retrieving all user keys"""
        # Save some keys
        providers_to_save = ["openai", "deepseek", "glm_4_6", "kimi_k2"]
        for provider in providers_to_save:
            if provider in AVAILABLE_AI_PROVIDERS:
                self.test_service.save_api_key(
                    self.test_user_id, provider, self.test_keys[provider]
                )
        
        # Get all keys
        all_keys = self.test_service.get_all_user_keys(self.test_user_id)
        
        # Check that saved keys are present
        for provider in providers_to_save:
            if provider in AVAILABLE_AI_PROVIDERS:
                self.assertIn(provider, all_keys)
                self.assertEqual(all_keys[provider], self.test_keys[provider])

    def test_update_api_key(self):
        """Test updating existing API key"""
        provider = "openai"
        original_key = self.test_keys[provider]
        updated_key = "sk-updated-key-987654321"
        
        # Save original key
        self.test_service.save_api_key(self.test_user_id, provider, original_key)
        
        # Update key
        success = self.test_service.save_api_key(self.test_user_id, provider, updated_key)
        self.assertTrue(success)
        
        # Verify updated key
        retrieved_key = self.test_service.get_api_key(self.test_user_id, provider)
        self.assertEqual(updated_key, retrieved_key)
        self.assertNotEqual(original_key, retrieved_key)

    @patch('glm_46_handler_real.GLM46ServiceReal.test_connection')
    def test_glm_4_6_key_validation(self, mock_test):
        """Test GLM-4.6 API key validation"""
        # Mock successful test
        mock_test.return_value = {
            "success": True,
            "message": "GLM-4.6 API connection successful"
        }
        
        provider = "glm_4_6"
        api_key = self.test_keys[provider]
        
        # Save key first
        self.test_service.save_api_key(self.test_user_id, provider, api_key)
        
        # Test key
        result = self.test_service.test_api_key(self.test_user_id, provider)
        
        self.assertTrue(result.get("success"))
        self.assertIn("successful", result.get("message", "").lower())

    @patch('kimi_k2_handler_real.KimiK2ServiceReal.test_connection')
    def test_kimi_k2_key_validation(self, mock_test):
        """Test Kimi K2 API key validation"""
        # Mock successful test
        mock_test.return_value = {
            "success": True,
            "message": "Kimi K2 API connection successful"
        }
        
        provider = "kimi_k2"
        api_key = self.test_keys[provider]
        
        # Save key first
        self.test_service.save_api_key(self.test_user_id, provider, api_key)
        
        # Test key
        result = self.test_service.test_api_key(self.test_user_id, provider)
        
        self.assertTrue(result.get("success"))
        self.assertIn("successful", result.get("message", "").lower())

    def test_unsupported_service_test(self):
        """Test testing API key for unsupported service"""
        result = self.test_service.test_api_key(self.test_user_id, "unsupported_service")
        
        self.assertFalse(result.get("success"))
        message = result.get("message", "").lower()
        self.assertTrue(
            "not supported" in message or "no api key found" in message,
            f"Unexpected error message: {result.get('message')}"
        )

    def test_empty_api_key_handling(self):
        """Test handling of empty API keys"""
        provider = "openai"
        
        # Test saving empty key
        success = self.test_service.save_api_key(self.test_user_id, provider, "")
        # The service should still save it, but validation happens at API level
        self.assertTrue(success)
        
        # Test retrieving empty key
        retrieved_key = self.test_service.get_api_key(self.test_user_id, provider)
        self.assertEqual("", retrieved_key)

    def test_database_persistence(self):
        """Test that data persists across service instances"""
        provider = "deepseek"
        api_key = self.test_keys[provider]
        
        # Save key with first service instance
        self.test_service.save_api_key(self.test_user_id, provider, api_key)
        
        # Create new service instance with same database
        new_service = UserAPIKeyService(self.temp_db.name)
        
        # Verify key is still there
        retrieved_key = new_service.get_api_key(self.test_user_id, provider)
        self.assertEqual(api_key, retrieved_key)


class TestAvailableProviders(unittest.TestCase):
    """Test cases for available AI providers"""

    def test_glm_4_6_provider_config(self):
        """Test GLM-4.6 provider configuration"""
        self.assertIn("glm_4_6", AVAILABLE_AI_PROVIDERS)
        
        glm_config = AVAILABLE_AI_PROVIDERS["glm_4_6"]
        
        # Check required fields
        required_fields = ["name", "description", "acquisition_url", "expected_format", "capabilities", "models"]
        for field in required_fields:
            self.assertIn(field, glm_config)
        
        # Check specific values
        self.assertEqual(glm_config["name"], "GLM-4.6 (Zhipu AI)")
        self.assertIn("Chinese", glm_config["description"])
        self.assertIn("chat", glm_config["capabilities"])
        self.assertIn("glm-4.6", glm_config["models"])

    def test_kimi_k2_provider_config(self):
        """Test Kimi K2 provider configuration"""
        self.assertIn("kimi_k2", AVAILABLE_AI_PROVIDERS)
        
        kimi_config = AVAILABLE_AI_PROVIDERS["kimi_k2"]
        
        # Check required fields
        required_fields = ["name", "description", "acquisition_url", "expected_format", "capabilities", "models"]
        for field in required_fields:
            self.assertIn(field, kimi_config)
        
        # Check specific values
        self.assertEqual(kimi_config["name"], "Kimi K2 (Moonshot AI)")
        self.assertIn("Long-context", kimi_config["description"])
        self.assertIn("long_context", kimi_config["capabilities"])
        self.assertIn("moonshot", kimi_config["models"][0])

    def test_existing_still_available(self):
        """Test that existing providers are still available"""
        existing_providers = ["openai", "deepseek", "anthropic", "google_gemini", "azure_openai"]
        
        for provider in existing_providers:
            self.assertIn(provider, AVAILABLE_AI_PROVIDERS)
            
            config = AVAILABLE_AI_PROVIDERS[provider]
            required_fields = ["name", "description", "acquisition_url", "expected_format", "capabilities", "models"]
            for field in required_fields:
                self.assertIn(field, config, f"Missing field {field} for provider {provider}")

    def test_provider_config_completeness(self):
        """Test that all providers have complete configurations"""
        required_fields = ["name", "description", "acquisition_url", "expected_format", "capabilities", "models"]
        
        for provider, config in AVAILABLE_AI_PROVIDERS.items():
            for field in required_fields:
                self.assertIn(field, config, f"Missing field {field} for provider {provider}")
                self.assertIsNotNone(config[field], f"Empty field {field} for provider {provider}")
            
            # Check that capabilities and models are lists
            self.assertIsInstance(config["capabilities"], list)
            self.assertIsInstance(config["models"], list)
            self.assertGreater(len(config["capabilities"]), 0)
            self.assertGreater(len(config["models"]), 0)


class TestProviderIntegration(unittest.TestCase):
    """Test cases for provider integration"""

    def setUp(self):
        """Set up test environment"""
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        
        self.test_service = UserAPIKeyService(self.temp_db.name)
        self.test_user_id = "test_user_456"

    def tearDown(self):
        """Clean up test environment"""
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    @patch('glm_46_handler_real.GLM46ServiceReal')
    @patch('kimi_k2_handler_real.KimiK2ServiceReal')
    def test_new_provider_imports(self, mock_kimi, mock_glm):
        """Test that new provider handlers can be imported"""
        try:
            from glm_46_handler_real import GLM46ServiceReal
            from kimi_k2_handler_real import KimiK2ServiceReal
            
            # Test that classes exist
            self.assertTrue(callable(GLM46ServiceReal))
            self.assertTrue(callable(KimiK2ServiceReal))
            
        except ImportError as e:
            self.fail(f"Failed to import new provider handlers: {e}")

    def test_provider_key_format_validation(self):
        """Test provider-specific key format expectations"""
        provider_formats = {
            "openai": "sk-...",
            "deepseek": "sk-...",
            "anthropic": "sk-ant-...",
            "google_gemini": "AIza...",
            "glm_4_6": "glm-...",
            "kimi_k2": "sk-...",
            "azure_openai": "Azure API key + endpoint"
        }
        
        for provider, expected_format in provider_formats.items():
            if provider in AVAILABLE_AI_PROVIDERS:
                actual_format = AVAILABLE_AI_PROVIDERS[provider]["expected_format"]
                self.assertEqual(actual_format, expected_format, 
                               f"Format mismatch for provider {provider}")

    def test_new_provider_models_list(self):
        """Test that new providers have reasonable model lists"""
        new_providers = ["glm_4_6", "kimi_k2"]
        
        for provider in new_providers:
            if provider in AVAILABLE_AI_PROVIDERS:
                models = AVAILABLE_AI_PROVIDERS[provider]["models"]
                
                # Check that models list is not empty
                self.assertGreater(len(models), 0, f"No models listed for {provider}")
                
                # Check that model names are strings
                for model in models:
                    self.assertIsInstance(model, str)
                    self.assertGreater(len(model), 0)
                
                # Check for expected model naming patterns
                if provider == "glm_4_6":
                    self.assertTrue(any("glm-4" in model.lower() for model in models))
                elif provider == "kimi_k2":
                    self.assertTrue(any("moonshot" in model.lower() for model in models))


def run_integration_tests():
    """Run integration tests with actual API calls (requires real API keys)"""
    print("\n" + "="*50)
    print("INTEGRATION TESTS - Requires Real API Keys")
    print("="*50)
    
    # Check for environment variables
    integration_keys = {}
    for provider in ["glm_4_6", "kimi_k2"]:
        env_var = f"{provider.upper()}_API_KEY"
        api_key = os.getenv(env_var)
        if api_key:
            integration_keys[provider] = api_key
            print(f"Found API key for {provider}")
        else:
            print(f"No API key found for {provider} (set {env_var} to run integration tests)")
    
    if not integration_keys:
        print("\nNo integration API keys found. Skipping integration tests.")
        return
    
    # Create service for integration testing
    temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    temp_db.close()
    
    try:
        service = UserAPIKeyService(temp_db.name)
        test_user = "integration_test_user"
        
        for provider, api_key in integration_keys.items():
            print(f"\nTesting {provider} integration...")
            
            # Save API key
            save_success = service.save_api_key(test_user, provider, api_key)
            if save_success:
                print(f"✓ API key saved for {provider}")
                
                # Test API key
                test_result = service.test_api_key(test_user, provider)
                if test_result.get("success"):
                    print(f"✓ {provider} API key is valid")
                    print(f"  Message: {test_result.get('message')}")
                else:
                    print(f"✗ {provider} API key test failed")
                    print(f"  Error: {test_result.get('message')}")
            else:
                print(f"✗ Failed to save API key for {provider}")
    
    finally:
        # Clean up
        if os.path.exists(temp_db.name):
            os.unlink(temp_db.name)
    
    print("\nIntegration tests completed.")


if __name__ == "__main__":
    # Run unit tests
    print("Running unit tests...")
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # Run integration tests
    run_integration_tests()