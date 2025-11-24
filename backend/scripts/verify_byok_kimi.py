import sys
import os
sys.path.append(os.getcwd())

from backend.core.byok_endpoints import BYOKManager

def test_byok_initialization():
    print("Initializing BYOKManager...")
    manager = BYOKManager()
    
    print(f"Total providers: {len(manager.providers)}")
    print("Providers list:")
    for p_id, provider in manager.providers.items():
        print(f"- {provider.name} ({p_id}): {provider.model}")
        
    if "moonshot" in manager.providers:
        print("\nSUCCESS: Moonshot AI (Kimi) found!")
        kimi = manager.providers["moonshot"]
        print(f"Kimi Config: {kimi}")
    else:
        print("\nFAILURE: Moonshot AI (Kimi) NOT found!")

if __name__ == "__main__":
    test_byok_initialization()
