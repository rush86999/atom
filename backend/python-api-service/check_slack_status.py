#!/usr/bin/env python3
"""
Simple Slack Integration Test
Quick verification that Slack integration components are properly set up
"""

import os
import sys
import json
from datetime import datetime

def test_imports():
    """Test all Slack-related imports"""
    print("🔍 Testing Slack imports...")
    
    imports = {
        "Slack Events Handler": "slack_events_handler",
        "Enhanced Slack API": "slack_enhanced_api_complete", 
        "Enhanced Slack Service": "slack_enhanced_service_complete",
        "Original Slack Service": "slack_enhanced_service",
        "Slack OAuth Handler": "slack_oauth_handler",
        "Slack DB Operations": "db_oauth_slack",
        "Main API App": "main_api_app"
    }
    
    results = {}
    success_count = 0
    
    for name, module in imports.items():
        try:
            __import__(module)
            print(f"  ✅ {name}")
            results[name] = "SUCCESS"
            success_count += 1
        except ImportError as e:
            print(f"  ❌ {name} - {str(e)}")
            results[name] = f"FAILED: {str(e)}"
    
    return results, success_count, len(imports)

def check_environment():
    """Check Slack environment variables"""
    print("\n🔍 Checking environment variables...")
    
    required_vars = {
        "SLACK_CLIENT_ID": "Slack OAuth Client ID",
        "SLACK_CLIENT_SECRET": "Slack OAuth Client Secret"
    }
    
    optional_vars = {
        "SLACK_SIGNING_SECRET": "Slack Signing Secret (for webhooks)",
        "SLACK_BOT_TOKEN": "Slack Bot Token (for bot features)",
        "SLACK_REDIRECT_URI": "Slack OAuth Redirect URI"
    }
    
    results = {}
    
    print("  Required variables:")
    for var, desc in required_vars.items():
        value = os.getenv(var)
        if value:
            print(f"    ✅ {var}: Set")
            results[var] = "SET"
        else:
            print(f"    ❌ {var}: Missing - {desc}")
            results[var] = "MISSING"
    
    print("  Optional variables:")
    for var, desc in optional_vars.items():
        value = os.getenv(var)
        if value:
            print(f"    ✅ {var}: Set")
            results[var] = "SET"
        else:
            print(f"    ⚠️  {var}: Missing - {desc}")
            results[var] = "MISSING (Optional)"
    
    return results

def check_file_structure():
    """Check if Slack files exist"""
    print("\n🔍 Checking file structure...")
    
    files_to_check = [
        "slack_events_handler.py",
        "slack_enhanced_api_complete.py", 
        "slack_enhanced_service_complete.py",
        "slack_enhanced_service.py",
        "slack_oauth_handler.py",
        "db_oauth_slack.py",
        "main_api_app.py",
        "test_slack_integration_complete.py"
    ]
    
    results = {}
    
    for filename in files_to_check:
        if os.path.exists(filename):
            size = os.path.getsize(filename)
            print(f"    ✅ {filename} ({size:,} bytes)")
            results[filename] = "EXISTS"
        else:
            print(f"    ❌ {filename}: Missing")
            results[filename] = "MISSING"
    
    return results

def check_frontend_files():
    """Check frontend Slack integration files"""
    print("\n🔍 Checking frontend files...")
    
    frontend_path = "../../frontend-nextjs/pages/api/integrations/slack"
    files_to_check = [
        "health.ts",
        "auth/start.ts",
        "auth/callback.ts",
        "channels.ts",
        "messages.ts",
        "messages/send.ts",
        "messages/edit.ts",
        "messages/reactions.ts",
        "users.ts",
        "files.ts",
        "files/upload.ts",
        "search/messages.ts",
        "search/files.ts",
        "channels/create.ts",
        "channels/manage.ts"
    ]
    
    results = {}
    
    for filename in files_to_check:
        filepath = os.path.join(frontend_path, filename)
        if os.path.exists(filepath):
            size = os.path.getsize(filepath)
            print(f"    ✅ {filename} ({size:,} bytes)")
            results[filename] = "EXISTS"
        else:
            print(f"    ❌ {filename}: Missing")
            results[filename] = "MISSING"
    
    return results

def generate_report(imports_result, env_result, files_result, frontend_result):
    """Generate comprehensive report"""
    print("\n" + "="*60)
    print("📊 SLACK INTEGRATION STATUS REPORT")
    print("="*60)
    
    # Import results
    import_success = sum(1 for v in imports_result.values() if v == "SUCCESS")
    import_total = len(imports_result)
    print(f"\n🔧 Backend Imports: {import_success}/{import_total} successful")
    
    # Environment results  
    env_required = [k for k, v in env_result.items() if k in ["SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET"]]
    env_success = sum(1 for k in env_required if env_result[k] == "SET")
    print(f"🔐 Environment: {env_success}/{len(env_required)} required variables set")
    
    # File results
    file_success = sum(1 for v in files_result.values() if v == "EXISTS")
    file_total = len(files_result)
    print(f"📁 Backend Files: {file_success}/{file_total} exist")
    
    # Frontend results
    frontend_success = sum(1 for v in frontend_result.values() if v == "EXISTS")
    frontend_total = len(frontend_result)
    print(f"🌐 Frontend Files: {frontend_success}/{frontend_total} exist")
    
    # Overall status
    total_checks = import_total + len(env_required) + file_total + frontend_total
    total_success = import_success + env_success + file_success + frontend_success
    success_rate = (total_success / total_checks) * 100 if total_checks > 0 else 0
    
    print(f"\n📈 Overall Success Rate: {success_rate:.1f}% ({total_success}/{total_checks})")
    
    if success_rate >= 90:
        print("🎉 Slack integration is EXCELLENT!")
    elif success_rate >= 75:
        print("✅ Slack integration is GOOD!")
    elif success_rate >= 50:
        print("⚠️  Slack integration needs some improvements")
    else:
        print("❌ Slack integration needs significant work")
    
    # Save detailed report
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "imports": imports_result,
        "environment": env_result,
        "backend_files": files_result,
        "frontend_files": frontend_result,
        "summary": {
            "total_checks": total_checks,
            "total_success": total_success,
            "success_rate": success_rate
        }
    }
    
    report_file = "slack_integration_status_report.json"
    with open(report_file, 'w') as f:
        json.dump(report_data, f, indent=2)
    
    print(f"\n📄 Detailed report saved to: {report_file}")
    
    return report_data

def main():
    """Main test runner"""
    print("🚀 SLACK INTEGRATION STATUS CHECK")
    print("⏰ Started at:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    try:
        # Run all checks
        imports_result, import_success, import_total = test_imports()
        env_result = check_environment()
        files_result = check_file_structure()
        frontend_result = check_frontend_files()
        
        # Generate report
        report = generate_report(imports_result, env_result, files_result, frontend_result)
        
        # Exit with appropriate code
        success_rate = report["summary"]["success_rate"]
        if success_rate >= 75:
            print("\n✅ Slack integration is ready!")
            sys.exit(0)
        else:
            print(f"\n⚠️  Slack integration needs attention (Success Rate: {success_rate:.1f}%)")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️  Check interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()