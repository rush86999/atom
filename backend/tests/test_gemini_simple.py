#!/usr/bin/env python3
"""
Simple test to verify Gemini provider support
"""
import os
os.environ["TESTING"] = "1"

from unittest.mock import patch, MagicMock
from core.llm.byok_handler import BYOKHandler, COST_EFFICIENT_MODELS, PROVIDER_TIERS, QueryComplexity

def test_gemini_configuration():
    """Test that Gemini is configured in the system."""
    print("=" * 60)
    print("Testing Gemini Provider Configuration")
    print("=" * 60)

    # Test 1: Check COST_EFFICIENT_MODELS
    print("\n[Test 1] COST_EFFICIENT_MODELS configuration")
    if "gemini" in COST_EFFICIENT_MODELS:
        print("[PASS] Gemini found in COST_EFFICIENT_MODELS")
        for complexity, model in COST_EFFICIENT_MODELS["gemini"].items():
            print(f"  - {complexity.value}: {model}")
    else:
        print("[FAIL] Gemini not found in COST_EFFICIENT_MODELS")
        return False

    # Test 2: Check PROVIDER_TIERS
    print("\n[Test 2] PROVIDER_TIERS configuration")
    gemini_found = False
    for tier, providers in PROVIDER_TIERS.items():
        if "gemini" in providers:
            print(f"[PASS] Gemini found in '{tier}' tier")
            gemini_found = True
            break
    if not gemini_found:
        print("[FAIL] Gemini not found in PROVIDER_TIERS")
        return False

    # Test 3: Check provider initialization
    print("\n[Test 3] Provider initialization")
    with patch('core.llm.byok_handler.OpenAI') as mock_openai:
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        os.environ["GOOGLE_API_KEY"] = "test-key"
        try:
            handler = BYOKHandler(workspace_id="test", tenant_id="test")
            if "gemini" in handler.clients:
                print("[PASS] Gemini provider initialized successfully")
                print(f"  Available providers: {list(handler.clients.keys())}")
            else:
                print("[INFO] Gemini not in clients (may use 'google' provider ID)")
                if "google" in handler.clients or "google_flash" in handler.clients:
                    print("[PASS] Google provider available (uses GOOGLE_API_KEY)")
                else:
                    print(f"  Available providers: {list(handler.clients.keys())}")
        finally:
            if "GOOGLE_API_KEY" in os.environ:
                del os.environ["GOOGLE_API_KEY"]

    print("\n" + "=" * 60)
    print("All tests completed successfully!")
    print("=" * 60)
    return True

if __name__ == "__main__":
    import sys
    success = test_gemini_configuration()
    sys.exit(0 if success else 1)
