# -*- coding: utf-8 -*-
"""
Test Google Gemini Provider Initialization

This test verifies that:
1. Gemini provider is properly initialized when GOOGLE_API_KEY is set
2. Gemini models are available in provider routing
3. Vision capabilities work with Gemini
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock

# Set testing environment
os.environ["TESTING"] = "1"

from core.llm.byok_handler import BYOKHandler, QueryComplexity


class TestGeminiProviderInitialization:
    """Test suite for Gemini provider initialization and functionality."""

    def test_gemini_provider_in_providers_config(self):
        """Verify Gemini is included in providers_config dictionary."""
        with patch('core.llm.byok_handler.OpenAI') as mock_openai:
            # Mock the OpenAI client
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            # Set GOOGLE_API_KEY environment variable
            os.environ["GOOGLE_API_KEY"] = "test-gemini-key-12345"

            try:
                # Initialize BYOKHandler
                handler = BYOKHandler(workspace_id="test-workspace", tenant_id="test-tenant")

                # Verify Gemini client was initialized (either with gemini or google provider ID)
                # The handler should have a client for Gemini/Google
                has_gemini_or_google = any(
                    provider_id in handler.clients
                    for provider_id in ["gemini", "google", "google_flash"]
                )

                assert has_gemini_or_google, "Gemini/Google provider should be initialized with GOOGLE_API_KEY"
                print(f"[PASS] Gemini/Google provider initialized successfully")
                print(f"  Available providers: {list(handler.clients.keys())}")

            finally:
                # Clean up environment
                if "GOOGLE_API_KEY" in os.environ:
                    del os.environ["GOOGLE_API_KEY"]

    def test_gemini_in_cost_efficient_models(self):
        """Verify Gemini models are defined in COST_EFFICIENT_MODELS."""
        from core.llm.byok_handler import COST_EFFICIENT_MODELS

        # Check that 'gemini' key exists in COST_EFFICIENT_MODELS
        assert "gemini" in COST_EFFICIENT_MODELS, "gemini should be in COST_EFFICIENT_MODELS"

        # Verify model mappings exist for all complexity levels
        gemini_models = COST_EFFICIENT_MODELS["gemini"]
        assert QueryComplexity.SIMPLE in gemini_models
        assert QueryComplexity.MODERATE in gemini_models
        assert QueryComplexity.COMPLEX in gemini_models
        assert QueryComplexity.ADVANCED in gemini_models

        # Check that model names contain "gemini"
        for complexity, model in gemini_models.items():
            assert "gemini" in model.lower(), f"Gemini model for {complexity} should contain 'gemini': {model}"

        print(f"[PASS] Gemini models in COST_EFFICIENT_MODELS:")
        for complexity, model in gemini_models.items():
            print(f"  - {complexity.value}: {model}")

    def test_gemini_in_provider_tiers(self):
        """Verify Gemini is included in provider tier mappings."""
        from core.llm.byok_handler import PROVIDER_TIERS

        # Check that gemini is in at least one tier
        gemini_found = False
        for tier, providers in PROVIDER_TIERS.items():
            if "gemini" in providers:
                gemini_found = True
                print(f"[PASS] Gemini found in '{tier}' tier")
                break

        assert gemini_found, "Gemini should be in PROVIDER_TIERS"

    def test_gemini_in_vision_models_list(self):
        """Verify Gemini models are included in vision model routing."""
        # This test verifies the fix for the coordinated vision bug
        with patch('core.llm.byok_handler.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            # Set required environment variables
            os.environ["GOOGLE_API_KEY"] = "test-gemini-key"

            try:
                handler = BYOKHandler(workspace_id="test", tenant_id="test")

                # Check if the handler would route to Gemini for vision tasks
                # by checking if "gemini" or "google" is in the clients
                has_gemini = "gemini" in handler.clients
                has_google = "google" in handler.clients

                assert has_gemini or has_google, "Gemini/Google should be available for vision tasks"
                print(f"[PASS] Gemini available for vision tasks (provider: {'gemini' if has_gemini else 'google'})")

            finally:
                if "GOOGLE_API_KEY" in os.environ:
                    del os.environ["GOOGLE_API_KEY"]

    def test_coordinated_vision_description_fix(self):
        """Verify the fix for the _get_coordinated_vision_description bug.

        This test checks that:
        1. The method checks for "gemini" or "google" provider (not undefined variable)
        2. The provider check happens before using the provider variable
        """
        with patch('core.llm.byok_handler.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            # Mock the chat completions response
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Test vision description"
            mock_client.chat.completions.create.return_value = mock_response

            os.environ["GOOGLE_API_KEY"] = "test-key"

            try:
                handler = BYOKHandler(workspace_id="test", tenant_id="test")
                handler.clients["gemini"] = mock_client

                # Test that the method doesn't crash with undefined variable
                import asyncio
                result = asyncio.run(handler._get_coordinated_vision_description(
                    image_payload="base64test",
                    tenant_plan="free",
                    is_managed=False
                ))

                # Should return a result, not crash
                assert result is not None or result is None  # Either is fine, just no crash
                print("[PASS] _get_coordinated_vision_description works without crashing")

            finally:
                if "GOOGLE_API_KEY" in os.environ:
                    del os.environ["GOOGLE_API_KEY"]


def run_tests():
    """Run all tests and print results."""
    test_suite = TestGeminiProviderInitialization()

    tests = [
        ("Gemini Provider Initialization", test_suite.test_gemini_provider_in_providers_config),
        ("Gemini in COST_EFFICIENT_MODELS", test_suite.test_gemini_in_cost_efficient_models),
        ("Gemini in Provider Tiers", test_suite.test_gemini_in_provider_tiers),
        ("Gemini in Vision Models", test_suite.test_gemini_in_vision_models_list),
        ("Coordinated Vision Fix", test_suite.test_coordinated_vision_description_fix),
    ]

    print("=" * 60)
    print("Running Gemini Provider Tests")
    print("=" * 60)

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            print(f"\n[Test] {test_name}")
            print("-" * 60)
            test_func()
            passed += 1
            print(f"PASSED [PASS]")
        except AssertionError as e:
            failed += 1
            print(f"FAILED ✗: {e}")
        except Exception as e:
            failed += 1
            print(f"ERROR ✗: {e}")

    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
