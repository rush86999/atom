#!/usr/bin/env python3
"""
Web App E2E Business Value Tests
Tests user journeys in the Next.js frontend to validate business value delivery
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

try:
    from playwright.async_api import async_playwright, Page, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("[WARN] Playwright not installed. Run: pip install playwright && playwright install")

class WebAppBusinessValueTester:
    """E2E tester for web app business value scenarios"""
    
    def __init__(self, base_url: str = "http://localhost:3000"):
        self.base_url = base_url
        self.browser = None
        self.page = None
        self.results = []
        
    async def setup(self):
        """Initialize browser and page"""
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright not available")
        
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=True)
        self.page = await self.browser.new_page()
        
    async def teardown(self):
        """Close browser"""
        if self.browser:
            await self.browser.close()
    
    async def login(self, email: str = "test@example.com", password: str = "testpassword"):
        """
        Login to the application using credentials form
        NextAuth is now configured with test credentials support
        """
        try:
            # Navigate to signin page
            await self.page.goto(f"{self.base_url}/auth/signin")
            await self.page.wait_for_load_state("networkidle")
            
            # Fill in credentials
            await self.page.fill('input[type="email"]', email)
            await self.page.fill('input[type="password"]', password)
            
            # Submit form
            await self.page.click('button[type="submit"]')
            
            # Wait for redirect - should go to home page
            await self.page.wait_for_url(f"{self.base_url}/", timeout=10000)
            
            print(f"[OK] Logged in as {email}")
            return True
            
        except Exception as e:
            print(f"[WARN] Login failed: {e}")
            return False
    
    async def test_calendar_event_creation_speed(self) -> Dict[str, Any]:
        """
        Test: Calendar event creation via UI
        Business Value: Time savings compared to manual multi-calendar check
        """
        result = {
            "test": "Calendar Event Creation",
            "category": "calendar",
            "status": "pending",
            "metrics": {}
        }
        
        try:
            # Login first
            await self.login()
            
            # Navigate to calendar page
            start_time = time.time()
            await self.page.goto(f"{self.base_url}/calendar")
            
            # Wait for calendar to load
            await self.page.wait_for_selector('[data-testid="calendar-view"]', timeout=5000)
            load_time = time.time() - start_time
            
            # Click "New Event" button
            create_start = time.time()
            await self.page.click('[data-testid="new-event-btn"]')
            await self.page.wait_for_selector('[data-testid="event-form"]')
            
            # Fill event form
            await self.page.fill('[data-testid="event-title"]', "Test Meeting")
            await self.page.fill('[data-testid="event-start"]', "2024-12-01T10:00")
            await self.page.fill('[data-testid="event-end"]', "2024-12-01T11:00")
            
            # Submit
            await self.page.click('[data-testid="event-submit"]')
            await self.page.wait_for_selector('[data-testid="event-created-toast"]', timeout=5000)
            
            create_time = time.time() - create_start
            
            result["metrics"] = {
                "page_load_time": round(load_time, 2),
                "event_creation_time": round(create_time, 2),
                "total_time": round(load_time + create_time, 2),
                "baseline_manual": 300,  # 5 min manual
                "time_saved": round(300 - (load_time + create_time), 2)
            }
            result["status"] = "pass"
            
        except Exception as e:
            result["status"] = "fail"
            result["error"] = str(e)
        
        return result
    
    async def test_unified_search_speed(self) -> Dict[str, Any]:
        """
        Test: Hybrid search across integrations
        Business Value: Find items across multiple services in one query
        """
        result = {
            "test": "Unified Search",
            "category": "search",
            "status": "pending",
            "metrics": {}
        }
        
        try:
            # Login first
            await self.login()
            
            start_time = time.time()
            await self.page.goto(f"{self.base_url}/search")
            
            # Enter search query
            await self.page.fill('[data-testid="search-input"]', "project plan")
            
            # Wait for results
            await self.page.wait_for_selector('[data-testid="search-results"]', timeout=3000)
            
            search_time = time.time() - start_time
            
            # Count results from different sources
            results = await self.page.query_selector_all('[data-testid="search-result-item"]')
            
            result["metrics"] = {
                "search_time": round(search_time, 2),
                "results_count": len(results),
                "baseline_manual": 180,  # 3 min to search 3 apps manually
                "time_saved": round(180 - search_time, 2),
                "target_latency": 0.5,  # 500ms target
                "meets_target": search_time < 0.5
            }
            result["status"] = "pass" if search_time < 2.0 else "slow"
            
        except Exception as e:
            result["status"] = "fail"
            result["error"] = str(e)
        
        return result
    
    async def test_task_management_efficiency(self) -> Dict[str, Any]:
        """
        Test: Create and sync task across PM tools
        Business Value: One action updates multiple services
        """
        result = {
            "test": "Task Management Sync",
            "category": "tasks",
            "status": "pending",
            "metrics": {}
        }
        
        try:
            # Login first
            await self.login()
            
            start_time = time.time()
            await self.page.goto(f"{self.base_url}/tasks")
            
            # Create new task
            await self.page.click('[data-testid="new-task-btn"]')
            await self.page.fill('[data-testid="task-title"]', "Test Task")
            await self.page.select_option('[data-testid="task-project"]', "test-project")
            
            # Enable sync to multiple services
            await self.page.check('[data-testid="sync-asana"]')
            await self.page.check('[data-testid="sync-jira"]')
            
            await self.page.click('[data-testid="task-submit"]')
            await self.page.wait_for_selector('[data-testid="task-synced-toast"]', timeout=5000)
            
            sync_time = time.time() - start_time
            
            result["metrics"] = {
                "sync_time": round(sync_time, 2),
                "services_synced": 2,
                "baseline_manual": 120,  # 2 min to update 2 services manually
                "efficiency_multiplier": round(120 / sync_time, 1),
                "actions_saved": 1  # 2 actions reduced to 1
            }
            result["status"] = "pass"
            
        except Exception as e:
            result["status"] = "fail"
            result["error"] = str(e)
        
        return result
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all business value tests"""
        await self.setup()
        
        print("=" * 70)
        print("WEB APP BUSINESS VALUE E2E TESTS")
        print("=" * 70)
        print()
        
        # Run tests
        tests = [
            self.test_calendar_event_creation_speed(),
            self.test_unified_search_speed(),
            self.test_task_management_efficiency()
        ]
        
        for test_coro in tests:
            result = await test_coro
            self.results.append(result)
            
            status_label = "[PASS]" if result["status"] == "pass" else "[FAIL]" if result["status"] == "fail" else "[WARN]"
            print(f"{status_label} {result['test']}: {result['status'].upper()}")
            
            if "metrics" in result:
                for key, value in result["metrics"].items():
                    print(f"   {key}: {value}")
            print()
        
        await self.teardown()
        
        # Calculate overall score
        passed = sum(1 for r in self.results if r["status"] == "pass")
        total = len(self.results)
        score = (passed / total) * 100 if total > 0 else 0
        
        return {
            "timestamp": datetime.now().isoformat(),
            "total_tests": total,
            "passed": passed,
            "failed": sum(1 for r in self.results if r["status"] == "fail"),
            "score": round(score, 2),
            "results": self.results
        }

async def main():
    if not PLAYWRIGHT_AVAILABLE:
        print("[FAIL] Playwright not installed")
        print("Install: pip install playwright && playwright install")
        return 1
    
    tester = WebAppBusinessValueTester()
    
    try:
        report = await tester.run_all_tests()
        
        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Score: {report['score']}%")
        print(f"Passed: {report['passed']}/{report['total_tests']}")
        
        # Save report
        report_path = Path("backend/web_app_e2e_report.json")
        report_path.write_text(json.dumps(report, indent=2))
        print(f"\n[OK] Report saved: {report_path}")
        
        return 0 if report['score'] >= 80 else 1
        
    except Exception as e:
        print(f"[FAIL] Test suite failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
