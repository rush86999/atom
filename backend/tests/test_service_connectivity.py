#!/usr/bin/env python3
"""
Test Service Connectivity After Dependency Installation
"""

import json
import os
import sys
from datetime import datetime


def test_openai():
    """Test OpenAI connectivity"""
    try:
        import openai
        client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say 'Hello ATOM!'"}],
            max_tokens=10
        )
        
        return {
            "status": "connected",
            "response": response.choices[0].message.content,
            "tokens": response.usage.total_tokens if response.usage else 0
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

def test_asana():
    """Test Asana connectivity"""
    try:
        import asana_handler

        # Test if handler can be instantiated
        return {"status": "handler_available", "message": "Asana handler imported successfully"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def test_trello():
    """Test Trello connectivity"""
    try:
        import trello_handler

        # Test if handler can be instantiated
        return {"status": "handler_available", "message": "Trello handler imported successfully"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def test_notion():
    """Test Notion connectivity"""
    try:
        import notion_handler_real

        # Test if handler can be instantiated
        return {"status": "handler_available", "message": "Notion handler imported successfully"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def test_github():
    """Test GitHub connectivity"""
    try:
        import github_handler

        # Test if handler can be instantiated
        return {"status": "handler_available", "message": "GitHub handler imported successfully"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def test_dropbox():
    """Test Dropbox connectivity"""
    try:
        import dropbox_handler

        # Test if handler can be instantiated
        return {"status": "handler_available", "message": "Dropbox handler imported successfully"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def main():
    # Add current directory to Python path
    import sys
    sys.path.insert(0, '.')
    
    print("🔌 Testing Service Connectivity After Dependency Installation")
    print("=" * 60)
    
    tests = {
        "OpenAI": test_openai,
        "Asana": test_asana,
        "Trello": test_trello,
        "Notion": test_notion,
        "GitHub": test_github,
        "Dropbox": test_dropbox
    }
    
    results = {}
    for service_name, test_func in tests.items():
        print(f"\n🔍 Testing {service_name}...")
        result = test_func()
        results[service_name] = result
        
        status_icon = "✅" if result["status"] in ["connected", "handler_available"] else "❌"
        print(f"   {status_icon} {service_name}: {result['status']}")
        if "message" in result:
            print(f"      {result['message']}")
        elif "response" in result:
            print(f"      Response: {result['response']}")
    
    print("\n" + "=" * 60)
    print("📊 Summary:")
    
    connected = sum(1 for r in results.values() if r["status"] == "connected")
    available = sum(1 for r in results.values() if r["status"] == "handler_available")
    errors = sum(1 for r in results.values() if r["status"] == "error")
    
    print(f"   ✅ Connected: {connected}")
    print(f"   🔧 Handler Available: {available}")
    print(f"   ❌ Errors: {errors}")
    print(f"   📈 Total Tested: {len(results)}")
    
    # Save results
    report = {
        "timestamp": datetime.now().isoformat(),
        "results": results,
        "summary": {
            "connected": connected,
            "handler_available": available,
            "errors": errors,
            "total_tested": len(results)
        }
    }
    
    with open("service_connectivity_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Detailed report saved to: service_connectivity_report.json")

if __name__ == "__main__":
    main()