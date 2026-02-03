
import os
import sys
from dotenv import load_dotenv

# Add backend to path
sys.path.append(os.getcwd())

from core.byok_endpoints import get_byok_manager


def refresh_keys():
    load_dotenv()
    manager = get_byok_manager()
    
    keys_to_refresh = {
        "openai": os.getenv("OPENAI_API_KEY"),
        "anthropic": os.getenv("ANTHROPIC_API_KEY"),
        "deepseek": os.getenv("DEEPSEEK_API_KEY")
    }
    
    print(f"Refreshing keys with BYOK_ENCRYPTION_KEY: {os.getenv('BYOK_ENCRYPTION_KEY')[:10]}...")
    
    for provider, key in keys_to_refresh.items():
        try:
            manager.store_api_key(provider, key)
            print(f"Successfully refreshed {provider}")
        except Exception as e:
            print(f"Failed to refresh {provider}: {e}")

if __name__ == "__main__":
    refresh_keys()
