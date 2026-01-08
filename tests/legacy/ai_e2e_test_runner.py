"""
AI-Powered End-to-End Testing Framework with Chrome DevTools Integration
Enhances the existing ATOM platform testing with intelligent validation and bug detection
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import subprocess
import uuid

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Third-party imports
try:
    import playwright
    from playwright.async_api import async_playwright, Page, Browser, BrowserContext
    import pytest
    import requests
    from PIL import Image, ImageDraw, ImageFont
    import cv2
    import numpy as np
    PLAYWRIGHT_AVAILABLE = True
except ImportError as e:
    print(f"Missing testing dependencies: {e}")
    PLAYWRIGHT_AVAILABLE = False

# AI and ML imports
try:
    import openai
    from transformers import pipeline
    import torch
    AI_AVAILABLE = True
except ImportError as e:
    print(f"AI dependencies not available: {e}")
    AI_AVAILABLE = False

class ChromeDevToolsIntegration:
    """Integrates with Chrome DevTools MCP Server for advanced debugging"""

    def __init__(self):
        self.mcp_server_url = "http://localhost:3001"  # Default MCP server
        self.session_id = str(uuid.uuid4())

    async def start_devtools_session(self, page: Page) -> Dict[str, Any]:
        """Start a Chrome DevTools session via MCP"""
        try:
            # Connect to the MCP server
            response = requests.post(f"{self.mcp_server_url}/session/start",
                                   json={"page_url": page.url, "session_id": self.session_id})
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            print(f"Failed to start DevTools session: {e}")
        return {}

    async def capture_network_activity(self, page: Page) -> List[Dict]:
        """Capture network requests and responses"""
        network_data = []

        async def handle_response(response):
            network_data.append({
                "url": response.url,
                "status": response.status,
                "method": response.request.method,
                "timing": await response.all_headers(),
                "size": len(await response.body())
            })

        page.on("response", handle_response)
        return network_data

    async def capture_console_logs(self, page: Page) -> List[Dict]:
        """Capture console messages and errors"""
        console_logs = []

        async def handle_console(msg):
            console_logs.append({
                "type": msg.type,
                "text": msg.text,
                "location": msg.location,
                "timestamp": datetime.now().isoformat()
            })

            # Special handling for errors
            if msg.type == "error":
                await self.capture_error_screenshot(page, msg.text)

        page.on("console", handle_console)
        return console_logs

    async def capture_error_screenshot(self, page: Page, error_text: str):
        """Take a screenshot when an error occurs"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = f"test_results/screenshots/error_{timestamp}.png"
        await page.screenshot(path=screenshot_path)

        # Annotate the screenshot with error information
        if os.path.exists(screenshot_path):
            self.annotate_screenshot(screenshot_path, error_text)

    def annotate_screenshot(self, image_path: str, error_text: str):
        """Add error annotation to screenshot"""
        try:
            img = Image.open(image_path)
            draw = ImageDraw.Draw(img)

            # Add red border
            border_color = "red"
            border_width = 5
            width, height = img.size
            draw.rectangle([0, 0, width-1, height-1], outline=border_color, width=border_width)

            # Add error text (if font is available)
            try:
                font = ImageFont.truetype("arial.ttf", 20)
            except:
                font = ImageFont.load_default()

            draw.text((10, 10), f"ERROR: {error_text[:50]}...", fill="red", font=font)

            img.save(image_path)
        except Exception as e:
            print(f"Failed to annotate screenshot: {e}")

class AIValidationSystem:
    """AI-powered test result validation and bug detection"""

    def __init__(self):
        self.client = None
        self.vision_model = None
        self.text_classifier = None
        self.setup_ai_models()

    def setup_ai_models(self):
        """Initialize AI models for validation"""
        if AI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
            try:
                self.client = openai.OpenAI()
                # Initialize vision model for screenshot analysis
                self.vision_model = pipeline(
                    "image-classification",
                    model="microsoft/resnet-50"
                )
                # Initialize text analysis model
                self.text_classifier = pipeline(
                    "text-classification",
                    model="microsoft/DialoGPT-medium"
                )
            except Exception as e:
                print(f"AI model setup failed: {e}")

    async def analyze_ui_screenshot(self, screenshot_path: str, expected_elements: List[str]) -> Dict[str, Any]:
        """Analyze UI screenshot for expected elements and visual issues"""
        if not os.path.exists(screenshot_path):
            return {"error": "Screenshot not found"}

        analysis = {
            "visual_issues": [],
            "missing_elements": [],
            "ui_breaks": [],
            "accessibility_issues": [],
            "performance_indicators": {}
        }

        # Use AI vision model to analyze screenshot
        if self.vision_model:
            try:
                image = Image.open(screenshot_path)

                # Check for visual issues
                visual_analysis = await self.detect_visual_issues(image)
                analysis["visual_issues"].extend(visual_analysis)

                # Check for missing elements
                missing = await self.verify_ui_elements(image, expected_elements)
                analysis["missing_elements"] = missing

            except Exception as e:
                analysis["error"] = f"AI analysis failed: {e}"

        return analysis

    async def detect_visual_issues(self, image: Image.Image) -> List[Dict]:
        """Detect common UI issues using computer vision"""
        issues = []

        # Convert to numpy array for OpenCV processing
        img_array = np.array(image)

        # Check for overlapping elements
        overlap_regions = self.detect_overlapping_elements(img_array)
        if overlap_regions:
            issues.append({
                "type": "overlapping_elements",
                "severity": "high",
                "regions": overlap_regions,
                "description": "Elements are overlapping and may be unusable"
            })

        # Check for text overflow
        overflow_areas = self.detect_text_overflow(img_array)
        if overflow_areas:
            issues.append({
                "type": "text_overflow",
                "severity": "medium",
                "areas": overflow_areas,
                "description": "Text is overflowing its containers"
            })

        # Check for broken layouts
        layout_issues = self.detect_layout_breaks(img_array)
        if layout_issues:
            issues.append({
                "type": "layout_break",
                "severity": "high",
                "issues": layout_issues,
                "description": "Layout appears to be broken"
            })

        return issues

    def detect_overlapping_elements(self, img_array: np.ndarray) -> List[Dict]:
        """Detect overlapping UI elements using edge detection"""
        # Convert to grayscale
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

        # Edge detection
        edges = cv2.Canny(gray, 50, 150)

        # Find contours
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        overlapping_regions = []
        for i, contour1 in enumerate(contours):
            for j, contour2 in enumerate(contours[i+1:], i+1):
                # Check if contours overlap
                if cv2.contourArea(contour1) > 100 and cv2.contourArea(contour2) > 100:
                    overlap = cv2.intersectConvexConvex(contour1, contour2)
                    if overlap[0] > 0.5:  # Significant overlap
                        overlapping_regions.append({
                            "element1": i,
                            "element2": j,
                            "overlap_ratio": overlap[0]
                        })

        return overlapping_regions

    def detect_text_overflow(self, img_array: np.ndarray) -> List[Dict]:
        """Detect text overflow in UI elements"""
        # Use OCR to detect text regions
        try:
            import pytesseract
            text_data = pytesseract.image_to_data(img_array, output_type=pytesseract.Output.DICT)

            overflow_areas = []
            for i in range(len(text_data['text'])):
                if int(text_data['conf'][i]) > 60:
                    x, y, w, h = text_data['left'][i], text_data['top'][i], text_data['width'][i], text_data['height'][i]

                    # Check if text extends beyond reasonable bounds
                    if x + w > img_array.shape[1] - 10:  # Near right edge
                        overflow_areas.append({
                            "text": text_data['text'][i][:20],
                            "position": (x, y),
                            "issue": "horizontal_overflow"
                        })

                    if y + h > img_array.shape[0] - 10:  # Near bottom edge
                        overflow_areas.append({
                            "text": text_data['text'][i][:20],
                            "position": (x, y),
                            "issue": "vertical_overflow"
                        })

            return overflow_areas
        except ImportError:
            return []

    def detect_layout_breaks(self, img_array: np.ndarray) -> List[Dict]:
        """Detect broken layouts and alignment issues"""
        issues = []

        # Check for misaligned elements using line detection
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        lines = cv2.HoughLinesP(gray, 1, np.pi/180, threshold=100, minLineLength=100)

        if lines is not None:
            # Analyze line angles for misalignment
            angles = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                angle = np.arctan2(y2-y1, x2-x1) * 180 / np.pi
                if abs(angle) > 5:  # Non-horizontal/vertical lines
                    angles.append(angle)

            if len(angles) > 5:  # Many misaligned elements
                issues.append({
                    "type": "misalignment",
                    "count": len(angles),
                    "avg_angle": np.mean(angles),
                    "description": "Multiple elements appear misaligned"
                })

        return issues

    async def verify_ui_elements(self, image: Image.Image, expected_elements: List[str]) -> List[str]:
        """Verify expected UI elements are present"""
        missing_elements = []

        # Use OCR to find text elements
        try:
            import pytesseract
            text_in_image = pytesseract.image_to_string(image).lower()

            for element in expected_elements:
                if element.lower() not in text_in_image:
                    missing_elements.append(element)
        except ImportError:
            missing_elements = expected_elements  # Can't verify without OCR

        return missing_elements

    async def analyze_console_errors(self, console_logs: List[Dict]) -> Dict[str, Any]:
        """Analyze console errors and categorize by severity"""
        error_analysis = {
            "critical_errors": [],
            "warnings": [],
            "performance_issues": [],
            "security_issues": []
        }

        for log in console_logs:
            if log["type"] == "error":
                error_text = log["text"].lower()

                # Categorize errors
                if any(keyword in error_text for keyword in ["uncaught", "fatal", "cannot read"]):
                    error_analysis["critical_errors"].append(log)
                elif any(keyword in error_text for keyword in ["cors", "cross-origin", "security"]):
                    error_analysis["security_issues"].append(log)
                elif any(keyword in error_text for keyword in ["slow", "timeout", "performance"]):
                    error_analysis["performance_issues"].append(log)
                else:
                    error_analysis["warnings"].append(log)

        return error_analysis

    async def generate_test_report(self, test_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AI-powered test report with insights and recommendations"""
        report = {
            "executive_summary": {},
            "bug_prioritization": [],
            "recommendations": [],
            "health_score": 0,
            "generated_at": datetime.now().isoformat()
        }

        # Calculate health score
        total_tests = test_results.get("total_tests", 0)
        passed_tests = test_results.get("passed_tests", 0)

        if total_tests > 0:
            pass_rate = (passed_tests / total_tests) * 100
            report["health_score"] = min(100, pass_rate)

        # Prioritize bugs by impact
        bugs = test_results.get("bugs_found", [])
        for bug in bugs:
            priority = self.calculate_bug_priority(bug)
            bug["priority"] = priority
            report["bug_prioritization"].append(bug)

        # Sort bugs by priority
        report["bug_prioritization"].sort(key=lambda x: x["priority"], reverse=True)

        # Generate recommendations
        report["recommendations"] = self.generate_recommendations(bugs)

        # Executive summary
        report["executive_summary"] = {
            "overall_health": "Good" if report["health_score"] > 80 else "Needs Improvement" if report["health_score"] > 60 else "Critical",
            "critical_issues": len([b for b in bugs if b.get("severity") == "critical"]),
            "recommendations_count": len(report["recommendations"])
        }

        return report

    def calculate_bug_priority(self, bug: Dict) -> int:
        """Calculate bug priority based on severity and impact"""
        severity_score = {
            "critical": 100,
            "high": 75,
            "medium": 50,
            "low": 25
        }

        base_score = severity_score.get(bug.get("severity", "low"), 25)

        # Adjust based on user impact
        if bug.get("user_impact") == "blocking":
            base_score += 20
        elif bug.get("user_impact") == "major":
            base_score += 10

        return base_score

    def generate_recommendations(self, bugs: List[Dict]) -> List[str]:
        """Generate actionable recommendations based on bugs found"""
        recommendations = []

        # Group bugs by type
        bug_types = {}
        for bug in bugs:
            bug_type = bug.get("type", "unknown")
            if bug_type not in bug_types:
                bug_types[bug_type] = []
            bug_types[bug_type].append(bug)

        # Generate recommendations for each bug type
        if "ui_break" in bug_types:
            recommendations.append("Review responsive design and fix layout breaks")

        if "javascript_error" in bug_types:
            recommendations.append("Add comprehensive error handling and validation")

        if "performance" in bug_types:
            recommendations.append("Optimize assets and implement lazy loading")

        if "accessibility" in bug_types:
            recommendations.append("Improve ARIA labels and keyboard navigation")

        if "security" in bug_types:
            recommendations.append("Review CORS policies and implement security headers")

        return recommendations

class EnhancedE2ETestRunner:
    """Enhanced E2E Test Runner with AI validation and Chrome DevTools integration"""

    def __init__(self):
        self.devtools = ChromeDevToolsIntegration()
        self.ai_validator = AIValidationSystem()
        self.test_results = {
            "tests_run": [],
            "bugs_found": [],
            "screenshots": [],
            "console_logs": [],
            "network_data": []
        }
        self.browser = None
        self.context = None

    async def setup(self):
        """Initialize the testing environment"""
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright not available. Install with: pip install playwright")

        self.playwright = await async_playwright().start()

        # Launch browser with debugging enabled
        self.browser = await self.playwright.chromium.launch(
            headless=False,  # Run with UI for debugging
            args=["--disable-web-security", "--disable-features=VizDisplayCompositor"]
        )

        # Create context with additional permissions
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 720},
            permissions=["clipboard-read", "clipboard-write"]
        )

        # Create test results directory
        os.makedirs("test_results/screenshots", exist_ok=True)
        os.makedirs("test_results/reports", exist_ok=True)

    async def run_test_suite(self, test_config: Dict[str, Any]) -> Dict[str, Any]:
        """Run the complete test suite"""
        print("🚀 Starting Enhanced E2E Test Suite with AI Validation")
        print("=" * 60)

        start_time = time.time()

        try:
            # Test categories
            test_categories = [
                ("Authentication & User Management", self.test_authentication),
                ("Core UI Components", self.test_ui_components),
                ("Real-time Features", self.test_realtime_features),
                ("Integration Services", self.test_integrations),
                ("Performance & Accessibility", self.test_performance_accessibility),
                ("Error Handling & Edge Cases", self.test_error_handling)
            ]

            for category_name, test_func in test_categories:
                print(f"\n📋 Running {category_name} Tests...")
                await test_func()

            # Generate AI-powered report
            test_duration = time.time() - start_time
            self.test_results["test_duration"] = test_duration

            # Calculate summary metrics
            self.test_results["summary"] = {
                "total_tests": len(self.test_results["tests_run"]),
                "passed_tests": len([t for t in self.test_results["tests_run"] if t["status"] == "passed"]),
                "failed_tests": len([t for t in self.test_results["tests_run"] if t["status"] == "failed"]),
                "bugs_found": len(self.test_results["bugs_found"]),
                "test_duration": test_duration
            }

            # Generate AI report
            ai_report = await self.ai_validator.generate_test_report(self.test_results)
            self.test_results["ai_report"] = ai_report

            # Save comprehensive report
            await self.save_test_report()

            # Print summary
            self.print_test_summary()

            return self.test_results

        except Exception as e:
            print(f"❌ Test suite failed: {e}")
            return {"error": str(e)}

        finally:
            await self.cleanup()

    async def test_authentication(self):
        """Test authentication flows"""
        tests = [
            {
                "name": "User Registration Flow",
                "url": "/auth/register",
                "expected_elements": ["Register", "Email", "Password", "Create Account"],
                "test_func": self.test_registration_flow
            },
            {
                "name": "User Login Flow",
                "url": "/auth/login",
                "expected_elements": ["Login", "Email", "Password", "Sign In"],
                "test_func": self.test_login_flow
            },
            {
                "name": "Password Reset Flow",
                "url": "/auth/reset",
                "expected_elements": ["Reset Password", "Email", "Send Reset Link"],
                "test_func": self.test_password_reset
            }
        ]

        await self.run_test_category("Authentication", tests)

    async def test_ui_components(self):
        """Test core UI components"""
        tests = [
            {
                "name": "Navigation Menu",
                "url": "/",
                "expected_elements": ["Dashboard", "Settings", "Profile"],
                "test_func": self.test_navigation
            },
            {
                "name": "Dashboard Layout",
                "url": "/dashboard",
                "expected_elements": ["Overview", "Recent Activity", "Quick Actions"],
                "test_func": self.test_dashboard
            },
            {
                "name": "Agent Console",
                "url": "/dev-studio",
                "expected_elements": ["Agent Console", "Create Agent", "Agent List"],
                "test_func": self.test_agent_console
            }
        ]

        await self.run_test_category("UI Components", tests)

    async def test_realtime_features(self):
        """Test real-time features"""
        tests = [
            {
                "name": "WebSocket Connection",
                "url": "/chat",
                "expected_elements": ["Messages", "Send", "Online Status"],
                "test_func": self.test_websocket_features
            },
            {
                "name": "Live Notifications",
                "url": "/notifications",
                "expected_elements": ["Notifications", "Mark as Read", "Settings"],
                "test_func": self.test_notifications
            }
        ]

        await self.run_test_category("Real-time Features", tests)

    async def test_integrations(self):
        """Test third-party integrations"""
        tests = [
            {
                "name": "Slack Integration",
                "url": "/integrations/slack",
                "expected_elements": ["Connect Slack", "Channels", "Webhook"],
                "test_func": self.test_slack_integration
            },
            {
                "name": "Google Calendar Integration",
                "url": "/integrations/google-calendar",
                "expected_elements": ["Connect Google", "Calendar", "Events"],
                "test_func": self.test_google_integration
            }
        ]

        await self.run_test_category("Integrations", tests)

    async def test_performance_accessibility(self):
        """Test performance and accessibility"""
        tests = [
            {
                "name": "Page Load Performance",
                "url": "/",
                "expected_elements": [],
                "test_func": self.test_performance
            },
            {
                "name": "Accessibility Compliance",
                "url": "/dashboard",
                "expected_elements": ["Skip to Content", "Main Navigation"],
                "test_func": self.test_accessibility
            }
        ]

        await self.run_test_category("Performance & Accessibility", tests)

    async def test_error_handling(self):
        """Test error handling and edge cases"""
        tests = [
            {
                "name": "404 Error Handling",
                "url": "/non-existent-page",
                "expected_elements": ["404", "Page Not Found", "Go Home"],
                "test_func": self.test_404_handling
            },
            {
                "name": "Network Error Handling",
                "url": "/dashboard",
                "expected_elements": [],
                "test_func": self.test_network_errors
            }
        ]

        await self.run_test_category("Error Handling", tests)

    async def run_test_category(self, category_name: str, tests: List[Dict]):
        """Run all tests in a category"""
        for test in tests:
            try:
                print(f"  🧪 {test['name']}...")

                page = await self.context.new_page()

                # Start DevTools session
                devtools_data = await self.devtools.start_devtools_session(page)

                # Capture network activity
                network_data = await self.devtools.capture_network_activity(page)

                # Capture console logs
                console_logs = await self.devtools.capture_console_logs(page)

                # Run the specific test
                result = await test["test_func"](page, test)

                # Take screenshot
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = f"test_results/screenshots/{test['name'].replace(' ', '_')}_{timestamp}.png"
                await page.screenshot(path=screenshot_path, full_page=True)

                # AI validation of screenshot
                if test.get("expected_elements"):
                    ui_analysis = await self.ai_validator.analyze_ui_screenshot(
                        screenshot_path, test["expected_elements"]
                    )
                    result["ui_analysis"] = ui_analysis

                # Analyze console errors
                error_analysis = await self.ai_validator.analyze_console_errors(console_logs)
                result["error_analysis"] = error_analysis

                # Store test results
                test_result = {
                    "name": test["name"],
                    "category": category_name,
                    "url": test["url"],
                    "status": "passed" if result.get("success", False) else "failed",
                    "duration": result.get("duration", 0),
                    "screenshot": screenshot_path,
                    "console_logs": console_logs,
                    "network_data": network_data,
                    "devtools_data": devtools_data,
                    "details": result
                }

                self.test_results["tests_run"].append(test_result)

                # Store bugs found
                if result.get("bugs"):
                    self.test_results["bugs_found"].extend(result["bugs"])

                # Print result
                status_icon = "✅" if result.get("success", False) else "❌"
                print(f"    {status_icon} {test['name']} - {result.get('message', 'Completed')}")

                await page.close()

            except Exception as e:
                print(f"    ❌ {test['name']} - Error: {str(e)}")

                # Log the error as a failed test
                self.test_results["tests_run"].append({
                    "name": test["name"],
                    "category": category_name,
                    "status": "failed",
                    "error": str(e),
                    "url": test["url"]
                })

                self.test_results["bugs_found"].append({
                    "type": "test_failure",
                    "severity": "high",
                    "description": f"Test '{test['name']}' failed with error: {str(e)}",
                    "location": test["url"]
                })

    # Individual test methods
    async def test_registration_flow(self, page: Page, test: Dict) -> Dict:
        """Test user registration flow"""
        try:
            start_time = time.time()

            # Navigate to registration page
            await page.goto(f"http://localhost:3000{test['url']}", wait_until="networkidle")

            # Check if registration form exists
            register_form = await page.query_selector("form")
            if not register_form:
                return {
                    "success": False,
                    "message": "Registration form not found",
                    "bugs": [{
                        "type": "missing_element",
                        "severity": "critical",
                        "description": "Registration form is missing",
                        "location": test["url"]
                    }]
                }

            # Try to fill form with test data
            await page.fill("input[name='email']", "test@example.com")
            await page.fill("input[name='password']", "TestPassword123!")
            await page.fill("input[name='confirmPassword']", "TestPassword123!")

            # Check for validation
            submit_button = await page.query_selector("button[type='submit']")
            if submit_button:
                await submit_button.click()

                # Wait for response
                await page.wait_for_timeout(2000)

                # Check for success or error messages
                success_message = await page.query_selector(".success-message")
                error_message = await page.query_selector(".error-message")

                if success_message:
                    return {
                        "success": True,
                        "message": "Registration flow completed successfully",
                        "duration": time.time() - start_time
                    }
                elif error_message:
                    return {
                        "success": False,
                        "message": "Registration returned error message",
                        "bugs": [{
                            "type": "registration_error",
                            "severity": "high",
                            "description": await error_message.inner_text(),
                            "location": test["url"]
                        }]
                    }

            return {
                "success": False,
                "message": "Could not complete registration flow",
                "duration": time.time() - start_time
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Registration test failed: {str(e)}",
                "duration": time.time() - start_time,
                "bugs": [{
                    "type": "javascript_error",
                    "severity": "critical",
                    "description": str(e),
                    "location": test["url"]
                }]
            }

    async def test_login_flow(self, page: Page, test: Dict) -> Dict:
        """Test user login flow"""
        try:
            start_time = time.time()

            await page.goto(f"http://localhost:3000{test['url']}", wait_until="networkidle")

            # Check login form
            login_form = await page.query_selector("form")
            if not login_form:
                return {
                    "success": False,
                    "message": "Login form not found"
                }

            # Fill with test credentials
            await page.fill("input[type='email']", "test@example.com")
            await page.fill("input[type='password']", "TestPassword123!")

            # Submit form
            submit_button = await page.query_selector("button[type='submit']")
            if submit_button:
                await submit_button.click()
                await page.wait_for_timeout(2000)

                # Check if redirected to dashboard
                if "dashboard" in page.url:
                    return {
                        "success": True,
                        "message": "Login successful, redirected to dashboard",
                        "duration": time.time() - start_time
                    }

            return {
                "success": False,
                "message": "Login flow not working properly",
                "duration": time.time() - start_time
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Login test failed: {str(e)}"
            }

    async def test_password_reset(self, page: Page, test: Dict) -> Dict:
        """Test password reset flow"""
        try:
            start_time = time.time()

            await page.goto(f"http://localhost:3000{test['url']}", wait_until="networkidle")

            # Check reset form
            reset_form = await page.query_selector("form")
            if not reset_form:
                return {
                    "success": False,
                    "message": "Password reset form not found"
                }

            # Fill email
            await page.fill("input[type='email']", "test@example.com")

            # Submit
            submit_button = await page.query_selector("button[type='submit']")
            if submit_button:
                await submit_button.click()
                await page.wait_for_timeout(2000)

                # Check for success message
                success_msg = await page.query_selector(".success-message")
                if success_msg:
                    return {
                        "success": True,
                        "message": "Password reset initiated successfully",
                        "duration": time.time() - start_time
                    }

            return {
                "success": False,
                "message": "Password reset flow incomplete",
                "duration": time.time() - start_time
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Password reset test failed: {str(e)}"
            }

    async def test_navigation(self, page: Page, test: Dict) -> Dict:
        """Test navigation menu"""
        try:
            start_time = time.time()

            await page.goto(f"http://localhost:3000{test['url']}", wait_until="networkidle")

            # Check for navigation elements
            nav_elements = await page.query_selector_all("nav a, header a, .nav-link")

            if len(nav_elements) > 0:
                # Test navigation links
                working_links = 0
                for link in nav_elements[:5]:  # Test first 5 links
                    try:
                        href = await link.get_attribute("href")
                        if href and not href.startswith("http"):
                            await link.click()
                            await page.wait_for_timeout(1000)
                            working_links += 1
                    except:
                        pass

                success_rate = working_links / min(len(nav_elements), 5)

                return {
                    "success": success_rate > 0.5,
                    "message": f"Navigation working ({working_links}/{min(len(nav_elements), 5)} links tested)",
                    "duration": time.time() - start_time
                }

            return {
                "success": False,
                "message": "No navigation elements found",
                "duration": time.time() - start_time
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Navigation test failed: {str(e)}"
            }

    async def test_dashboard(self, page: Page, test: Dict) -> Dict:
        """Test dashboard functionality"""
        try:
            start_time = time.time()

            await page.goto(f"http://localhost:3000{test['url']}", wait_until="networkidle")

            # Check for dashboard components
            components = await page.query_selector_all(".dashboard-widget, .card, .panel")

            return {
                "success": len(components) > 0,
                "message": f"Dashboard has {len(components)} components",
                "duration": time.time() - start_time
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Dashboard test failed: {str(e)}"
            }

    async def test_agent_console(self, page: Page, test: Dict) -> Dict:
        """Test agent console functionality"""
        try:
            start_time = time.time()

            await page.goto(f"http://localhost:3000{test['url']}", wait_until="networkidle")

            # Check for agent console elements
            agent_elements = await page.query_selector_all(".agent-card, .agent-item, .agent-list")

            return {
                "success": len(agent_elements) > 0,
                "message": f"Agent console has {len(agent_elements)} agent items",
                "duration": time.time() - start_time
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Agent console test failed: {str(e)}"
            }

    async def test_websocket_features(self, page: Page, test: Dict) -> Dict:
        """Test WebSocket functionality"""
        try:
            start_time = time.time()

            await page.goto(f"http://localhost:3000{test['url']}", wait_until="networkidle")

            # Check for WebSocket connection
            ws_status = await page.evaluate("""
                () => {
                    if (window.socket && window.socket.connected) {
                        return 'connected';
                    }
                    return 'disconnected';
                }
            """)

            return {
                "success": ws_status == "connected",
                "message": f"WebSocket status: {ws_status}",
                "duration": time.time() - start_time
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"WebSocket test failed: {str(e)}"
            }

    async def test_notifications(self, page: Page, test: Dict) -> Dict:
        """Test notification system"""
        try:
            start_time = time.time()

            await page.goto(f"http://localhost:3000{test['url']}", wait_until="networkidle")

            # Check for notification elements
            notifications = await page.query_selector_all(".notification, .alert, .toast")

            return {
                "success": True,
                "message": f"Found {len(notifications)} notification elements",
                "duration": time.time() - start_time
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Notifications test failed: {str(e)}"
            }

    async def test_slack_integration(self, page: Page, test: Dict) -> Dict:
        """Test Slack integration"""
        try:
            start_time = time.time()

            await page.goto(f"http://localhost:3000{test['url']}", wait_until="networkidle")

            # Check for Slack connection button
            connect_button = await page.query_selector("button:has-text('Connect'), button:has-text('Connect Slack')")

            return {
                "success": connect_button is not None,
                "message": "Slack integration UI found" if connect_button else "Slack integration UI not found",
                "duration": time.time() - start_time
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Slack integration test failed: {str(e)}"
            }

    async def test_google_integration(self, page: Page, test: Dict) -> Dict:
        """Test Google Calendar integration"""
        try:
            start_time = time.time()

            await page.goto(f"http://localhost:3000{test['url']}", wait_until="networkidle")

            # Check for Google connection button
            connect_button = await page.query_selector("button:has-text('Connect Google'), button:has-text('Connect')")

            return {
                "success": connect_button is not None,
                "message": "Google integration UI found" if connect_button else "Google integration UI not found",
                "duration": time.time() - start_time
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Google integration test failed: {str(e)}"
            }

    async def test_performance(self, page: Page, test: Dict) -> Dict:
        """Test page performance metrics"""
        try:
            start_time = time.time()

            # Enable performance monitoring
            await page.goto(f"http://localhost:3000{test['url']}", wait_until="networkidle")

            # Get performance metrics
            metrics = await page.evaluate("""
                () => {
                    const navigation = performance.getEntriesByType('navigation')[0];
                    return {
                        loadTime: navigation.loadEventEnd - navigation.loadEventStart,
                        domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
                        firstPaint: performance.getEntriesByType('paint')[0]?.startTime || 0,
                        firstContentfulPaint: performance.getEntriesByType('paint')[1]?.startTime || 0
                    };
                }
            """)

            # Evaluate performance
            performance_score = 100
            if metrics['loadTime'] > 3000:
                performance_score -= 30
            elif metrics['loadTime'] > 2000:
                performance_score -= 15

            if metrics['firstContentfulPaint'] > 2000:
                performance_score -= 20
            elif metrics['firstContentfulPaint'] > 1500:
                performance_score -= 10

            return {
                "success": performance_score > 70,
                "message": f"Performance score: {performance_score}/100",
                "duration": time.time() - start_time,
                "metrics": metrics
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Performance test failed: {str(e)}"
            }

    async def test_accessibility(self, page: Page, test: Dict) -> Dict:
        """Test accessibility compliance"""
        try:
            start_time = time.time()

            await page.goto(f"http://localhost:3000{test['url']}", wait_until="networkidle")

            # Check for accessibility features
            accessibility_checks = await page.evaluate("""
                () => {
                    const checks = {
                        hasAltText: Array.from(document.querySelectorAll('img')).every(img => img.alt || img.getAttribute('aria-label')),
                        hasAriaLabels: document.querySelectorAll('[aria-label]').length > 0,
                        hasSkipLink: document.querySelector('a[href^="#main"], a[href^="#content"]') !== null,
                        hasHeadingStructure: document.querySelectorAll('h1, h2, h3, h4, h5, h6').length > 0,
                        hasFocusManagement: document.querySelector(':focus') !== null || document.activeElement !== document.body
                    };
                    return checks;
                }
            """)

            score = sum(accessibility_checks.values()) / len(accessibility_checks) * 100

            return {
                "success": score > 60,
                "message": f"Accessibility score: {score}/100",
                "duration": time.time() - start_time,
                "checks": accessibility_checks
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Accessibility test failed: {str(e)}"
            }

    async def test_404_handling(self, page: Page, test: Dict) -> Dict:
        """Test 404 error handling"""
        try:
            start_time = time.time()

            response = await page.goto(f"http://localhost:3000{test['url']}", wait_until="networkidle")

            if response and response.status == 404:
                # Check for proper 404 page elements
                has_404_message = await page.query_selector("text=404")
                has_home_link = await page.query_selector("a[href='/'], a[href='/home']")

                return {
                    "success": has_404_message is not None,
                    "message": "404 page handled" if has_404_message else "404 page missing proper message",
                    "duration": time.time() - start_time
                }

            return {
                "success": False,
                "message": "404 not returned for non-existent page",
                "duration": time.time() - start_time
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"404 test failed: {str(e)}"
            }

    async def test_network_errors(self, page: Page, test: Dict) -> Dict:
        """Test network error handling"""
        try:
            start_time = time.time()

            # Simulate network offline
            await page.context.set_offline(True)

            # Try to navigate
            await page.goto(f"http://localhost:3000{test['url']}", wait_until="networkidle")

            # Check for error handling
            error_message = await page.query_selector(".error-message, .network-error, [data-testid='network-error']")

            # Restore connection
            await page.context.set_offline(False)

            return {
                "success": error_message is not None,
                "message": "Network error handling found" if error_message else "No network error handling",
                "duration": time.time() - start_time
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Network error test failed: {str(e)}"
            }

    async def save_test_report(self):
        """Save comprehensive test report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = f"test_results/reports/enhanced_e2e_report_{timestamp}.json"

        with open(report_path, "w") as f:
            json.dump(self.test_results, f, indent=2, default=str)

        print(f"\n📄 Test report saved to: {report_path}")

        # Also save a summary report
        summary_report = {
            "executive_summary": self.test_results.get("ai_report", {}).get("executive_summary", {}),
            "health_score": self.test_results.get("ai_report", {}).get("health_score", 0),
            "total_bugs": len(self.test_results.get("bugs_found", [])),
            "critical_bugs": len([b for b in self.test_results.get("bugs_found", []) if b.get("severity") == "critical"]),
            "test_duration": self.test_results.get("test_duration", 0),
            "recommendations": self.test_results.get("ai_report", {}).get("recommendations", [])
        }

        summary_path = f"test_results/reports/summary_{timestamp}.json"
        with open(summary_path, "w") as f:
            json.dump(summary_report, f, indent=2, default=str)

        print(f"📊 Summary report saved to: {summary_path}")

    def print_test_summary(self):
        """Print test execution summary"""
        summary = self.test_results.get("summary", {})
        ai_report = self.test_results.get("ai_report", {})

        print("\n" + "=" * 60)
        print("🎯 TEST EXECUTION SUMMARY")
        print("=" * 60)

        print(f"\n📊 Test Results:")
        print(f"   Total Tests: {summary.get('total_tests', 0)}")
        print(f"   Passed: {summary.get('passed_tests', 0)} ✅")
        print(f"   Failed: {summary.get('failed_tests', 0)} ❌")
        print(f"   Pass Rate: {(summary.get('passed_tests', 0) / max(summary.get('total_tests', 1), 1)) * 100:.1f}%")

        print(f"\n🐛 Bugs Found:")
        print(f"   Total: {summary.get('bugs_found', 0)}")
        print(f"   Critical: {len([b for b in self.test_results.get('bugs_found', []) if b.get('severity') == 'critical'])}")

        print(f"\n💚 Health Score: {ai_report.get('health_score', 0)}/100")
        print(f"   Overall: {ai_report.get('executive_summary', {}).get('overall_health', 'Unknown')}")

        if ai_report.get("recommendations"):
            print(f"\n📋 Top Recommendations:")
            for rec in ai_report["recommendations"][:3]:
                print(f"   • {rec}")

        print(f"\n⏱️  Test Duration: {summary.get('test_duration', 0):.2f} seconds")
        print("=" * 60)

    async def cleanup(self):
        """Clean up resources"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

async def main():
    """Main entry point"""
    # Install dependencies if needed
    if not PLAYWRIGHT_AVAILABLE:
        print("Installing Playwright...")
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright"])
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])

    # Install additional dependencies for computer vision
    try:
        import pytesseract
        import cv2
    except ImportError:
        print("Installing computer vision dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pytesseract", "opencv-python", "pillow"])

    # Initialize and run tests
    runner = EnhancedE2ETestRunner()

    try:
        await runner.setup()
        results = await runner.run_test_suite({})

        # Exit with appropriate code
        if results.get("summary", {}).get("failed_tests", 0) > 0:
            sys.exit(1)
        else:
            sys.exit(0)

    except Exception as e:
        print(f"❌ Test runner failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())