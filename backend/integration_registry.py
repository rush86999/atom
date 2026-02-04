#!/usr/bin/env python3
"""
Integration Registry - Auto-discover all ATOM integrations
Scans backend/integrations/ directory and catalogs all services
"""

import importlib.util
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List


class IntegrationRegistry:
    """Discovers and catalogs all ATOM integrations"""
    
    def __init__(self, integrations_dir: str = "backend/integrations"):
        self.integrations_dir = Path(integrations_dir)
        self.services = {}
        
    def discover_integrations(self) -> Dict[str, Any]:
        """Scan directory and discover all integration services"""
        
        # Categories based on common patterns
        categories = {
            "communication": ["slack", "discord", "teams", "whatsapp", "telegram", "zoom", "google_chat"],
            "calendar": ["calendar", "outlook_calendar", "google_calendar"],
            "project_management": ["asana", "jira", "linear", "notion", "trello", "monday"],
            "storage": ["dropbox", "box", "google_drive", "onedrive"],
            "crm": ["salesforce", "hubspot", "zendesk", "freshdesk", "intercom"],
            "finance": ["stripe", "quickbooks", "xero", "shopify"],
            "development": ["github", "gitlab", "bitbucket", "figma"],
            "email": ["gmail", "outlook", "mailchimp"],
            "ai": ["ai_", "voice", "video"],
            "enterprise": ["enterprise", "workflow", "automation"],
            "industry": ["healthcare", "education", "finance_customization"]
        }
        
        service_files = []
        for file in self.integrations_dir.glob("*.py"):
            if file.name.startswith("test_") or file.name.startswith("__"):
                continue
            if "_service" in file.name or "_integration" in file.name or "_routes" in file.name:
                service_files.append(file)
        
        print(f"Found {len(service_files)} potential integration files")
        
        for file in service_files:
            service_info = self._analyze_service_file(file)
            if service_info:
                # Categorize
                category = "other"
                for cat, keywords in categories.items():
                    if any(keyword in file.stem.lower() for keyword in keywords):
                        category = cat
                        break
                
                service_info["category"] = category
                self.services[service_info["name"]] = service_info
        
        return self.services
    
    def _analyze_service_file(self, file: Path) -> Dict[str, Any]:
        """Analyze a service file to extract metadata"""
        try:
            content = file.read_text(encoding="utf-8", errors="ignore")
            
            # Extract class names
            classes = re.findall(r'class\s+(\w+)', content)
            
            # Check for auth methods
            has_oauth = "oauth" in content.lower() or "OAuth" in content
            has_api_key = "api_key" in content.lower() or "API_KEY" in content
            has_token = "token" in content.lower() or "access_token" in content
            
            # Check for common methods
            has_connect = "def connect" in content or "def authenticate" in content
            has_health_check = "def health" in content or "def test_connection" in content
            
            # Determine auth type
            auth_type = "unknown"
            if has_oauth:
                auth_type = "oauth"
            elif has_api_key:
                auth_type = "api_key"
            elif has_token:
                auth_type = "token"
            
            return {
                "name": file.stem,
                "file": str(file),
                "classes": classes[:3],  # First 3 classes
                "auth_type": auth_type,
                "has_connect": has_connect,
                "has_health_check": has_health_check,
                "status": "discovered"
            }
        except Exception as e:
            print(f"Error analyzing {file}: {e}")
            return None
    
    def get_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get all services in a category"""
        return [s for s in self.services.values() if s.get("category") == category]
    
    def get_critical_services(self) -> List[Dict[str, Any]]:
        """Get services marked as critical"""
        critical_categories = ["calendar", "email", "project_management", "storage"]
        return [s for s in self.services.values() if s.get("category") in critical_categories]
    
    def export_registry(self, output_file: str = "backend/integration_registry.json"):
        """Export registry to JSON"""
        Path(output_file).write_text(json.dumps({
            "total_services": len(self.services),
            "by_category": {
                cat: len([s for s in self.services.values() if s.get("category") == cat])
                for cat in set(s.get("category") for s in self.services.values())
            },
            "services": self.services
        }, indent=2))
        print(f"Registry exported to {output_file}")

if __name__ == "__main__":
    registry = IntegrationRegistry()
    services = registry.discover_integrations()
    
    print(f"\n{'=' * 60}")
    print(f"INTEGRATION DISCOVERY COMPLETE")
    print(f"{'=' * 60}\n")
    print(f"Total Services: {len(services)}")
    
    # Group by category
    by_category = {}
    for service in services.values():
        cat = service.get("category", "other")
        by_category[cat] = by_category.get(cat, 0) + 1
    
    print("\nBy Category:")
    for cat, count in sorted(by_category.items(), key=lambda x: -x[1]):
        print(f"  {cat.replace('_', ' ').title()}: {count}")
    
    # Export
    registry.export_registry()
    print(f"\n✅ Registry saved to backend/integration_registry.json")
