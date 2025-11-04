#!/usr/bin/env python3
"""
Comprehensive Service Validation for ATOM Application

This script validates all integrated services by:
1. Checking service handler imports
2. Testing API key availability
3. Validating service configurations
4. Testing actual service connectivity
"""

import os
import sys
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ServiceValidator:
    """Comprehensive service validation framework"""
    
    def __init__(self):
        self.results = {}
        self.service_categories = {
            "ai_providers": [
                "openai", "deepseek", "anthropic", "google"
            ],
            "task_management": [
                "asana", "trello", "notion", "jira"
            ],
            "communication": [
                "slack", "teams", "gmail", "outlook"
            ],
            "file_storage": [
                "dropbox", "box", "gdrive", "onedrive"
            ],
            "development": [
                "github", "gitlab"
            ],
            "financial": [
                "quickbooks", "xero", "plaid"
            ],
            "crm_sales": [
                "salesforce", "hubspot", "zoho"
            ],
            "social_media": [
                "twitter", "linkedin"
            ],
            "marketing": [
                "mailchimp", "shopify", "wordpress"
            ],
            "other_services": [
                "zapier", "zendesk", "docusign", "bamboohr"
            ]
        }
        
    def check_api_keys(self) -> Dict[str, Any]:
        """Check which API keys are configured"""
        api_keys = {}
        missing_keys = []
        
        # AI Providers
        ai_keys = {
            "OPENAI_API_KEY": "OpenAI",
            "DEEPSEEK_API_KEY": "DeepSeek", 
            "ANTHROPIC_API_KEY": "Anthropic",
            "GOOGLE_CLIENT_ID": "Google",
            "GOOGLE_CLIENT_SECRET": "Google"
        }
        
        # Task Management
        task_keys = {
            "ASANA_CLIENT_ID": "Asana",
            "ASANA_CLIENT_SECRET": "Asana",
            "TRELLO_API_KEY": "Trello",
            "TRELLO_API_TOKEN": "Trello",
            "NOTION_TOKEN": "Notion",
            "JIRA_SERVER_URL": "Jira",
            "JIRA_API_TOKEN": "Jira"
        }
        
        # Communication
        comm_keys = {
            "SLACK_CLIENT_ID": "Slack",
            "SLACK_CLIENT_SECRET": "Slack",
            "SLACK_VERIFICATION_TOKEN": "Slack"
        }
        
        # File Storage
        file_keys = {
            "DROPBOX_APP_KEY": "Dropbox",
            "DROPBOX_APP_SECRET": "Dropbox",
            "BOX_CLIENT_ID": "Box",
            "BOX_CLIENT_SECRET": "Box"
        }
        
        # Combine all keys
        all_keys = {**ai_keys, **task_keys, **comm_keys, **file_keys}
        
        for env_key, service_name in all_keys.items():
            value = os.getenv(env_key)
            if value:
                api_keys[env_key] = {
                    "service": service_name,
                    "configured": True,
                    "value_preview": value[:10] + "..." if len(value) > 10 else "***"
                }
            else:
                missing_keys.append(f"{service_name} ({env_key})")
        
        return {
            "configured_keys": api_keys,
            "missing_keys": missing_keys,
            "total_configured": len(api_keys),
            "total_missing": len(missing_keys)
        }
    
    def check_service_imports(self) -> Dict[str, Any]:
        """Check which service handlers can be imported"""
        handlers_to_check = [
            # AI Providers
            ("openai_handler_real", "OpenAI"),
            ("deepseek_handler_real", "DeepSeek"),
            
            # Task Management
            ("asana_handler", "Asana"),
            ("trello_handler", "Trello"),
            ("notion_handler_real", "Notion"),
            ("jira_handler", "Jira"),
            
            # Communication
            ("slack_handler_simple", "Slack"),
            
            # File Storage
            ("dropbox_handler", "Dropbox"),
            ("box_handler", "Box"),
            ("gdrive_handler", "Google Drive"),
            
            # Development
            ("github_handler", "GitHub"),
            
            # Financial
            ("quickbooks_service", "QuickBooks"),
            
            # CRM
            ("salesforce_handler", "Salesforce"),
            ("zoho_handler", "Zoho"),
            
            # Social Media
            ("twitter_handler", "Twitter"),
            ("linkedin_service", "LinkedIn"),
            
            # Marketing
            ("mailchimp_handler", "Mailchimp"),
            ("shopify_handler", "Shopify"),
            ("wordpress_service", "WordPress")
        ]
        
        working_handlers = []
        failed_handlers = []
        
        for handler_name, service_name in handlers_to_check:
            try:
                __import__(handler_name)
                working_handlers.append({
                    "handler": handler_name,
                    "service": service_name,
                    "status": "importable"
                })
            except ImportError as e:
                failed_handlers.append({
                    "handler": handler_name,
                    "service": service_name,
                    "status": "import_failed",
                    "error": str(e)
                })
            except Exception as e:
                failed_handlers.append({
                    "handler": handler_name,
                    "service": service_name,
                    "status": "error",
                    "error": str(e)
                })
        
        return {
            "working_handlers": working_handlers,
            "failed_handlers": failed_handlers,
            "total_working": len(working_handlers),
            "total_failed": len(failed_handlers)
        }
    
    def test_openai_connection(self) -> Dict[str, Any]:
        """Test OpenAI API connectivity"""
        try:
            import openai
            
            client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            
            # Test with a simple completion
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Say 'Hello ATOM!'"}],
                max_tokens=10
            )
            
            return {
                "status": "connected",
                "model": "gpt-3.5-turbo",
                "response": response.choices[0].message.content,
                "tokens_used": response.usage.total_tokens if response.usage else 0
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def test_asana_connection(self) -> Dict[str, Any]:
        """Test Asana API connectivity"""
        try:
            from asana.api_client import ApiClient
            from asana.configuration import Configuration
            
            # Note: This requires OAuth tokens for full testing
            return {
                "status": "sdk_available",
                "message": "Asana SDK available - requires OAuth tokens for full testing"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def test_trello_connection(self) -> Dict[str, Any]:
        """Test Trello API connectivity"""
        try:
            from trello import TrelloClient
            
            client = TrelloClient(
                api_key=os.getenv('TRELLO_API_KEY'),
                api_secret=os.getenv('TRELLO_API_TOKEN')
            )
            
            return {
                "status": "sdk_available",
                "message": "Trello client initialized - requires OAuth for full testing"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def test_notion_connection(self) -> Dict[str, Any]:
        """Test Notion API connectivity"""
        try:
            from notion_client import Client
            
            notion = Client(auth=os.getenv('NOTION_TOKEN'))
            
            # Test simple operation
            try:
                # This is a lightweight operation to test connectivity
                user_info = notion.users.me()
                return {
                    "status": "connected",
                    "user": user_info.get('name', 'Unknown'),
                    "bot_id": user_info.get('id', 'Unknown')
                }
            except Exception as e:
                return {
                    "status": "sdk_available",
                    "message": f"Notion SDK available but connection failed: {str(e)}"
                }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def test_github_connection(self) -> Dict[str, Any]:
        """Test GitHub API connectivity"""
        try:
            from github import Github
            
            # Note: This requires a GitHub token for full testing
            return {
                "status": "sdk_available",
                "message": "GitHub SDK available - requires token for full testing"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    def validate_all_services(self) -> Dict[str, Any]:
        """Run comprehensive service validation"""
        logger.info("🚀 Starting comprehensive service validation...")
        
        # Check API keys
        api_key_status = self.check_api_keys()
        
        # Check service imports
        import_status = self.check_service_imports()
        
        # Test actual service connections
        service_tests = {
            "openai": self.test_openai_connection(),
            "asana": self.test_asana_connection(),
            "trello": self.test_trello_connection(),
            "notion": self.test_notion_connection(),
            "github": self.test_github_connection()
        }
        
        # Generate comprehensive report
        report = {
            "timestamp": datetime.now().isoformat(),
            "api_keys": api_key_status,
            "service_imports": import_status,
            "service_tests": service_tests,
            "summary": {
                "total_services_configured": api_key_status["total_configured"],
                "total_services_importable": import_status["total_working"],
                "total_services_testable": len([v for v in service_tests.values() if v.get("status") == "connected"]),
                "overall_status": "healthy" if api_key_status["total_configured"] > 5 else "degraded"
            }
        }
        
        return report
    
    def print_report(self, report: Dict[str, Any]):
        """Print formatted validation report"""
        print("\n" + "="*80)
        print("🎯 ATOM SERVICE VALIDATION REPORT")
        print("="*80)
        
        # API Keys Summary
        print(f"\n🔑 API Keys Configuration:")
        print(f"   Configured: {report['api_keys']['total_configured']}")
        print(f"   Missing: {report['api_keys']['total_missing']}")
        
        if report['api_keys']['missing_keys']:
            print(f"\n   Missing Keys:")
            for key in report['api_keys']['missing_keys'][:10]:  # Show first 10
                print(f"     ❌ {key}")
        
        # Service Imports Summary
        print(f"\n🔧 Service Handler Imports:")
        print(f"   Working: {report['service_imports']['total_working']}")
        print(f"   Failed: {report['service_imports']['total_failed']}")
        
        # Service Tests
        print(f"\n🔌 Service Connectivity Tests:")
        for service, result in report['service_tests'].items():
            status_icon = "✅" if result.get("status") == "connected" else "⚠️" if result.get("status") == "sdk_available" else "❌"
            print(f"   {status_icon} {service.title()}: {result.get('status', 'unknown')}")
            if result.get("message"):
                print(f"        {result['message']}")
        
        # Overall Summary
        print(f"\n📊 Overall Summary:")
        print(f"   Services with API Keys: {report['summary']['total_services_configured']}")
        print(f"   Importable Handlers: {report['summary']['total_services_importable']}")
        print(f"   Testable Services: {report['summary']['total_services_testable']}")
        print(f"   Overall Status: {report['summary']['overall_status'].upper()}")
        
        print("\n" + "="*80)
        
        if report['summary']['overall_status'] == "healthy":
            print("🎉 ATOM is well-configured with multiple service integrations!")
        elif report['summary']['overall_status'] == "degraded":
            print("⚠️  ATOM has some service integrations but needs additional configuration")
        else:
            print("❌ ATOM needs significant service configuration")

def main():
    """Main function to run service validation"""
    validator = ServiceValidator()
    report = validator.validate_all_services()
    validator.print_report(report)
    
    # Save detailed report
    report_file = f"service_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\n📄 Detailed report saved to: {report_file}")

if __name__ == "__main__":
    main()