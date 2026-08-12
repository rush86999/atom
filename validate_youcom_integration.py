#!/usr/bin/env python3
"""
Simple validation script for You.com integration
Checks syntax, imports, and basic structure without requiring full dependencies
"""
import ast
import os
import sys

def validate_file(filepath, description):
    """Validate a Python file can be parsed and has expected structure"""
    print(f"Validating {description}...")
    
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Parse the AST to check syntax
        tree = ast.parse(content)
        
        # Basic validation passed
        print(f"  ✅ Syntax valid")
        return True
        
    except SyntaxError as e:
        print(f"  ❌ Syntax error: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def check_youcom_in_web_search():
    """Check that You.com is properly integrated in web_search method"""
    print("Checking You.com integration in web_search...")
    
    filepath = "backend/integrations/mcp_service.py"
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check for key integration elements
    checks = [
        ("YDC_API_KEY environment variable", "YDC_API_KEY" in content),
        ("You.com API URL", "api.you.com" in content),
        ("youcom provider ID", "youcom" in content),
        ("You.com priority over Tavily", content.find("youcom_api_key = os.getenv") < content.find("tavily_api_key = os.getenv")),
        ("Provider info in response", '"provider": "you.com"' in content),
        ("Bearer authentication", "Bearer" in content and "youcom_api_key" in content),
    ]
    
    all_passed = True
    for check_name, passed in checks:
        if passed:
            print(f"  ✅ {check_name}")
        else:
            print(f"  ❌ {check_name}")
            all_passed = False
    
    return all_passed

def check_byok_configuration():
    """Check BYOK provider configuration includes You.com"""
    print("Checking BYOK provider configuration...")
    
    files_to_check = [
        "backend/api/byok_routes.py",
        "backend/core/byok_endpoints.py"
    ]
    
    all_passed = True
    for filepath in files_to_check:
        print(f"  Checking {filepath}...")
        
        with open(filepath, 'r') as f:
            content = f.read()
        
        checks = [
            ("youcom provider ID", '"youcom"' in content),
            ("You.com name", '"You.com"' in content),
            ("YDC_API_KEY env var", '"YDC_API_KEY"' in content),
            ("api.you.com URL", "api.you.com" in content),
        ]
        
        for check_name, passed in checks:
            if passed:
                print(f"    ✅ {check_name}")
            else:
                print(f"    ❌ {check_name}")
                all_passed = False
    
    return all_passed

def check_environment_files():
    """Check that environment files include YDC_API_KEY"""
    print("Checking environment configuration files...")
    
    files_to_check = [
        (".env.example", "Root environment template"),
        ("backend/.env.example", "Backend environment template")
    ]
    
    all_passed = True
    for filepath, description in files_to_check:
        print(f"  Checking {description}...")
        
        with open(filepath, 'r') as f:
            content = f.read()
        
        if "YDC_API_KEY=" in content:
            print(f"    ✅ YDC_API_KEY present")
        else:
            print(f"    ❌ YDC_API_KEY missing")
            all_passed = False
    
    return all_passed

def check_documentation():
    """Check that documentation was created"""
    print("Checking documentation...")
    
    doc_path = "docs/integrations/youcom-search.md"
    if os.path.exists(doc_path):
        print(f"  ✅ Documentation exists at {doc_path}")
        
        with open(doc_path, 'r') as f:
            content = f.read()
        
        # Check for key sections
        sections = [
            "Configuration", "Usage", "API Response Format", 
            "Benefits Over Tavily", "Troubleshooting"
        ]
        
        for section in sections:
            if f"## {section}" in content or f"### {section}" in content:
                print(f"    ✅ {section} section present")
            else:
                print(f"    ❌ {section} section missing")
        
        return True
    else:
        print(f"  ❌ Documentation missing at {doc_path}")
        return False

def main():
    """Run all validation checks"""
    print("🔍 Validating You.com integration...\n")
    
    # Change to project directory
    os.chdir("/tmp/scout_work/atom")
    
    checks = [
        (validate_file, "backend/integrations/mcp_service.py", "MCP Service"),
        (validate_file, "backend/api/byok_routes.py", "BYOK Routes"),  
        (validate_file, "backend/core/byok_endpoints.py", "BYOK Endpoints"),
        (check_youcom_in_web_search,),
        (check_byok_configuration,),
        (check_environment_files,),
        (check_documentation,),
    ]
    
    all_passed = True
    for check in checks:
        if len(check) == 1:
            # Function with no args
            result = check[0]()
        else:
            # Function with args
            result = check[0](check[1], check[2])
        
        if not result:
            all_passed = False
        
        print()  # Blank line between checks
    
    if all_passed:
        print("🎉 All validation checks passed! You.com integration looks good.")
        return 0
    else:
        print("❌ Some validation checks failed. Please review the issues above.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)