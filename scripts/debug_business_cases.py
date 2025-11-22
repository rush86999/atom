
import json
from pathlib import Path
import sys

# Mocking the path logic from validator_engine.py
# Assuming this script is run from project root
BASE_DIR = Path("backend/independent_ai_validator")
BUSINESS_CASES_FILE = BASE_DIR / "data" / "integration_business_cases.json"

def load_business_cases():
    print(f"Looking for file at: {BUSINESS_CASES_FILE.absolute()}")
    if BUSINESS_CASES_FILE.exists():
        with open(BUSINESS_CASES_FILE, 'r') as f:
            data = json.load(f)
            print(f"File loaded. Keys: {list(data.keys())}")
            return data.get("integration_business_cases", {})
    else:
        print("File not found!")
        return {}

def verify_business_value(integration_key):
    business_cases = load_business_cases()
    print(f"Loaded {len(business_cases)} integrations.")
    
    cases = business_cases.get(integration_key, [])
    print(f"Cases for '{integration_key}': {len(cases)}")
    
    if not cases:
        return {
            "has_business_cases": False,
            "validated_value": 0
        }
        
    total_value = sum(case.get("business_value", {}).get("annual_value_usd", 0) for case in cases)
    return {
        "has_business_cases": True,
        "validated_value": total_value
    }

if __name__ == "__main__":
    print("Testing GitHub...")
    result = verify_business_value("github")
    print(f"GitHub Result: {result}")
    
    print("\nTesting WhatsApp...")
    result = verify_business_value("whatsapp")
    print(f"WhatsApp Result: {result}")
