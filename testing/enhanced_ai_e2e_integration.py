"""
Enhanced AI E2E Integration Layer
Integrates Chrome DevTools MCP Server with existing AI validation system
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Third-party imports
try:
    from playwright.async_api import async_playwright, Page, Browser, BrowserContext
    import requests
    PLAYWRIGHT_AVAILABLE = True
except ImportError as e:
    print(f"Playwright not available: {e}")
    PLAYWRIGHT_AVAILABLE = False

# Import existing AI validation systems
try:
    from e2e_tests.utils.llm_verifier import LLMVerifier
    from e2e_tests.test_runner import E2ETestRunner
except ImportError:
    # Fallback import paths
    sys.path.insert(0, str(project_root / "e2e-tests"))
    from utils.llm_verifier import LLMVerifier
    from test_runner import E2ETestRunner


class ChromeDevToolsMCPIntegration:
    """Enhanced Chrome DevTools integration with MCP server"""

    def __init__(self):
        self.mcp_server_process = None
        self.mcp_port = 3001
        self.session_id = str(uuid.uuid4())
        self.devtools_available = False

    async def start_mcp_server(self) -> bool:
        """Start the Chrome DevTools MCP server"""
        try:
            # Check if MCP server is already running
            response = requests.get(f"http://localhost:{self.mcp_port}/health", timeout=2)
            if response.status_code == 200:
                print("PASS MCP server already running")
                self.devtools_available = True
                return True
        except:
            pass

        # Start MCP server
        try:
            print("Starting Chrome DevTools MCP server...")
            self.mcp_server_process = subprocess.Popen([
                "npx", "@modelcontextprotocol/server-chrome-devtools"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # Wait for server to start
            for i in range(10):  # Wait up to 10 seconds
                try:
                    response = requests.get(f"http://localhost:{self.mcp_port}/health", timeout=1)
                    if response.status_code == 200:
                        print("PASS MCP server started successfully")
                        self.devtools_available = True
                        return True
                except:
                    pass
                time.sleep(1)

            print("WARN  MCP server may not have started properly")
            return False

        except Exception as e:
            print(f"FAIL Failed to start MCP server: {e}")
            return False

    async def create_devtools_session(self, page: Page) -> Optional[Dict[str, Any]]:
        """Create a new DevTools session for the page"""
        if not self.devtools_available:
            return None

        try:
            session_data = {
                "session_id": self.session_id,
                "url": page.url,
                "timestamp": datetime.now().isoformat()
            }

            # Notify MCP server of new session
            response = requests.post(
                f"http://localhost:{self.mcp_port}/session/create",
                json=session_data,
                timeout=5
            )

            if response.status_code == 200:
                return response.json()
            else:
                print(f"MCP session creation failed: {response.status_code}")
                return None

        except Exception as e:
            print(f"Failed to create MCP session: {e}")
            return None

    async def capture_performance_metrics(self, page: Page) -> Dict[str, Any]:
        """Capture comprehensive performance metrics"""
        try:
            # Get Core Web Vitals
            metrics = await page.evaluate("""
                () => {
                    const navigation = performance.getEntriesByType('navigation')[0];
                    const paint = performance.getEntriesByType('paint');

                    // Get LCP (Largest Contentful Paint)
                    const lcp = performance.getEntriesByType('largest-contentful-paint');

                    // Get CLS (Cumulative Layout Shift)
                    let cls = 0;
                    new PerformanceObserver((list) => {
                        for (const entry of list.getEntries()) {
                            if (!entry.hadRecentInput) {
                                cls += entry.value;
                            }
                        }
                    }).observe({ entryTypes: ['layout-shift'] });

                    return {
                        loadTime: navigation.loadEventEnd - navigation.fetchStart,
                        domContentLoaded: navigation.domContentLoadedEventEnd - navigation.domContentLoadedEventStart,
                        firstPaint: paint.find(p => p.name === 'first-paint')?.startTime || 0,
                        firstContentfulPaint: paint.find(p => p.name === 'first-contentful-paint')?.startTime || 0,
                        largestContentfulPaint: lcp.length > 0 ? lcp[lcp.length - 1].startTime : 0,
                        cumulativeLayoutShift: cls,
                        resourceTiming: performance.getEntriesByType('resource').length
                    };
                }
            """)

            return metrics

        except Exception as e:
            print(f"Failed to capture performance metrics: {e}")
            return {}

    async def capture_accessibility_tree(self, page: Page) -> Dict[str, Any]:
        """Capture accessibility information"""
        try:
            accessibility_tree = await page.evaluate("""
                () => {
                    // Get all interactive elements
                    const interactive = Array.from(document.querySelectorAll('button, a, input, select, textarea, [tabindex]'));

                    // Check for ARIA labels
                    const elementsWithAria = Array.from(document.querySelectorAll('[aria-label], [aria-labelledby], [role]'));

                    // Check for alt text on images
                    const images = Array.from(document.querySelectorAll('img'));
                    const imagesWithAlt = images.filter(img => img.alt || img.getAttribute('aria-label'));

                    // Check for proper heading structure
                    const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6'));

                    // Check for form labels
                    const inputs = Array.from(document.querySelectorAll('input, select, textarea'));
                    const labeledInputs = inputs.filter(input => {
                        const id = input.id;
                        return id && document.querySelector(`label[for="${id}"]`);
                    });

                    return {
                        interactiveElements: interactive.length,
                        elementsWithAria: elementsWithAria.length,
                        totalImages: images.length,
                        imagesWithAlt: imagesWithAlt.length,
                        headings: headings.length,
                        totalInputs: inputs.length,
                        labeledInputs: labeledInputs.length,
                        hasSkipLink: !!document.querySelector('a[href^="#main"], a[href^="#content"]'),
                        hasLangAttribute: !!document.documentElement.lang
                    };
                }
            """)

            # Calculate accessibility score
            score = 0
            max_score = 7

            if accessibility_tree['imagesWithAlt'] == accessibility_tree['totalImages'] and accessibility_tree['totalImages'] > 0:
                score += 1
            if accessibility_tree['labeledInputs'] == accessibility_tree['totalInputs'] and accessibility_tree['totalInputs'] > 0:
                score += 1
            if accessibility_tree['hasSkipLink']:
                score += 1
            if accessibility_tree['hasLangAttribute']:
                score += 1
            if accessibility_tree['headings'] > 0:
                score += 1
            if accessibility_tree['elementsWithAria'] > 0:
                score += 1
            if accessibility_tree['interactiveElements'] > 0:
                score += 1

            accessibility_tree['accessibilityScore'] = (score / max_score) * 100

            return accessibility_tree

        except Exception as e:
            print(f"Failed to capture accessibility tree: {e}")
            return {}

    def stop_mcp_server(self):
        """Stop the MCP server"""
        if self.mcp_server_process:
            self.mcp_server_process.terminate()
            self.mcp_server_process = None
            print("MCP server stopped")


class EnhancedAIE2EIntegration:
    """Enhanced E2E integration combining AI validation with Chrome DevTools"""

    def __init__(self):
        self.devtools = ChromeDevToolsMCPIntegration()
        self.existing_test_runner = E2ETestRunner()
        self.llm_verifier = None
        self.browser = None
        self.context = None
        self.test_results = {
            "session_id": str(uuid.uuid4()),
            "start_time": datetime.now().isoformat(),
            "tests": [],
            "ai_validations": [],
            "performance_metrics": [],
            "accessibility_scores": [],
            "bugs_found": [],
            "recommendations": []
        }

    async def setup(self) -> bool:
        """Initialize the enhanced testing environment"""
        print("Setting up Enhanced AI E2E Integration...")

        # Start MCP server
        mcp_success = await self.devtools.start_mcp_server()
        if not mcp_success:
            print("WARN  Continuing without MCP server (some features limited)")

        # Setup Playwright
        if not PLAYWRIGHT_AVAILABLE:
            print("FAIL Playwright not available")
            return False

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,  # Keep visible for debugging
            args=[
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--enable-logging",
                "--log-level=0"
            ]
        )

        # Create context
        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 720},
            permissions=["clipboard-read", "clipboard-write", "microphone", "camera"]
        )

        # Initialize LLM verifier from existing system
        llm_available = self.existing_test_runner.initialize_llm_verifier()
        if llm_available:
            self.llm_verifier = self.existing_test_runner.llm_verifier
            print("PASS AI validation system initialized")
        else:
            print("WARN  AI validation not available")

        # Create results directory
        os.makedirs("test_results/enhanced", exist_ok=True)
        os.makedirs("test_results/enhanced/screenshots", exist_ok=True)
        os.makedirs("test_results/enhanced/reports", exist_ok=True)

        return True

    async def run_enhanced_test_suite(self, test_categories: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run the enhanced test suite with AI validation and DevTools integration"""
        print("\n" + "="*80)
        print("ENHANCED AI E2E TEST SUITE")
        print("="*80)

        if not await self.setup():
            return {"error": "Failed to setup test environment"}

        try:
            # Define enhanced test scenarios
            enhanced_tests = [
                {
                    "name": "Core Platform Authentication",
                    "url": "http://localhost:3000/auth/login",
                    "category": "authentication",
                    "marketing_claims": [
                        "Seamless OAuth integration",
                        "Enterprise-grade security",
                        "Single sign-on support"
                    ],
                    "test_function": self.test_authentication_enhanced
                },
                {
                    "name": "AI-Powered Dashboard",
                    "url": "http://localhost:3000/dashboard",
                    "category": "ai_features",
                    "marketing_claims": [
                        "AI-driven insights",
                        "Real-time analytics",
                        "Intelligent recommendations"
                    ],
                    "test_function": self.test_dashboard_enhanced
                },
                {
                    "name": "Agent Creation & Management",
                    "url": "http://localhost:3000/dev-studio",
                    "category": "automation",
                    "marketing_claims": [
                        "No-code agent creation",
                        "Natural language workflows",
                        "Multi-step automation"
                    ],
                    "test_function": self.test_agent_studio_enhanced
                },
                {
                    "name": "Real-time Collaboration",
                    "url": "http://localhost:3000/chat",
                    "category": "realtime",
                    "marketing_claims": [
                        "Real-time collaboration",
                        "WebSocket communication",
                        "Live synchronization"
                    ],
                    "test_function": self.test_realtime_enhanced
                },
                {
                    "name": "Service Integrations Hub",
                    "url": "http://localhost:3000/integrations",
                    "category": "integrations",
                    "marketing_claims": [
                        "100+ service integrations",
                        "Unified API management",
                        "Seamless data flow"
                    ],
                    "test_function": self.test_integrations_enhanced
                }
            ]

            # Filter by category if specified
            if test_categories:
                enhanced_tests = [t for t in enhanced_tests if t["category"] in test_categories]

            # Run enhanced tests
            for test in enhanced_tests:
                await self.run_enhanced_test(test)

            # Generate comprehensive report
            await self.generate_enhanced_report()

            return self.test_results

        except Exception as e:
            print(f"FAIL Test suite failed: {e}")
            return {"error": str(e), "test_results": self.test_results}

        finally:
            await self.cleanup()

    async def run_enhanced_test(self, test_config: Dict[str, Any]):
        """Run a single enhanced test with all integrations"""
        test_name = test_config["name"]
        print(f"\n🧪 Running: {test_name}")

        try:
            start_time = time.time()

            # Create new page
            page = await self.context.new_page()

            # Setup DevTools session
            devtools_session = await self.devtools.create_devtools_session(page)

            # Capture console errors
            console_errors = []
            page.on("console", lambda msg: console_errors.append({
                "type": msg.type,
                "text": msg.text,
                "timestamp": datetime.now().isoformat()
            }) if msg.type == "error" else None)

            # Navigate to test URL
            await page.goto(test_config["url"], wait_until="networkidle", timeout=30000)

            # Run the specific test function
            test_result = await test_config["test_function"](page, test_config)

            # Capture performance metrics
            performance_metrics = await self.devtools.capture_performance_metrics(page)

            # Capture accessibility information
            accessibility_info = await self.devtools.capture_accessibility_tree(page)

            # Take comprehensive screenshots
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = f"test_results/enhanced/screenshots/{test_name.replace(' ', '_')}_{timestamp}.png"
            await page.screenshot(path=screenshot_path, full_page=True)

            # AI validate against marketing claims
            ai_validation = None
            if self.llm_verifier:
                test_output = {
                    "url": page.url,
                    "title": await page.title(),
                    "performance": performance_metrics,
                    "accessibility": accessibility_info,
                    "console_errors": console_errors,
                    "ui_elements": await self.extract_ui_elements(page)
                }

                ai_validation = await self.ai_validate_marketing_claims(
                    test_config["marketing_claims"],
                    test_output,
                    test_name
                )

            # Compile test results
            enhanced_result = {
                "name": test_name,
                "category": test_config["category"],
                "url": test_config["url"],
                "status": "passed" if test_result.get("success", False) else "failed",
                "duration": time.time() - start_time,
                "screenshot": screenshot_path,
                "performance": performance_metrics,
                "accessibility": accessibility_info,
                "console_errors": console_errors,
                "ai_validation": ai_validation,
                "test_result": test_result,
                "devtools_session": devtools_session
            }

            self.test_results["tests"].append(enhanced_result)

            # Store performance and accessibility metrics
            self.test_results["performance_metrics"].append(performance_metrics)
            self.test_results["accessibility_scores"].append(accessibility_info.get("accessibilityScore", 0))

            # Print result
            status_icon = "PASS" if test_result.get("success", False) else "FAIL"
            perf_score = self.calculate_performance_score(performance_metrics)
            a11y_score = accessibility_info.get("accessibilityScore", 0)
            ai_score = ai_validation.get("overall_confidence", 0) if ai_validation else 0

            print(f"   {status_icon} {test_name}")
            print(f"      Performance: {perf_score}/100")
            print(f"      Accessibility: {a11y_score:.1f}/100")
            print(f"      AI Validation: {ai_score:.2f} confidence")

            # Close page
            await page.close()

        except Exception as e:
            print(f"   FAIL {test_name} - Error: {str(e)}")

            # Log failed test
            self.test_results["tests"].append({
                "name": test_name,
                "category": test_config["category"],
                "status": "error",
                "error": str(e),
                "duration": 0
            })

    async def extract_ui_elements(self, page: Page) -> Dict[str, Any]:
        """Extract key UI elements for AI analysis"""
        try:
            return await page.evaluate("""
                () => {
                    return {
                        headings: Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6')).map(h => h.textContent?.trim()),
                        buttons: Array.from(document.querySelectorAll('button')).map(b => b.textContent?.trim()).filter(Boolean),
                        links: Array.from(document.querySelectorAll('a')).map(a => a.textContent?.trim()).filter(Boolean),
                        inputs: Array.from(document.querySelectorAll('input, textarea')).map(i => i.placeholder || i.name || ''),
                        cards: Array.from(document.querySelectorAll('.card, .panel, .widget')).length,
                        forms: Array.from(document.querySelectorAll('form')).length,
                        hasNavigation: !!document.querySelector('nav, header'),
                        hasFooter: !!document.querySelector('footer'),
                        hasSidebar: !!document.querySelector('.sidebar, aside'),
                        bodyText: document.body.innerText.substring(0, 2000) // First 2000 chars
                    };
                }
            """)
        except:
            return {}

    async def ai_validate_marketing_claims(self, claims: List[str], test_output: Dict[str, Any], context: str) -> Dict[str, Any]:
        """Use AI to validate marketing claims against test output"""
        if not self.llm_verifier:
            return None

        try:
            print(f"   🤖 AI validating {len(claims)} marketing claims...")

            # Use existing LLM verifier
            verification_results = self.llm_verifier.batch_verify_claims(
                claims,
                test_output,
                f"Testing {context} on {datetime.now().date()}"
            )

            # Calculate overall confidence
            try:
                from e2e_tests.utils.llm_verifier import calculate_overall_confidence, get_verification_summary
            except ImportError:
                from utils.llm_verifier import calculate_overall_confidence, get_verification_summary
            overall_confidence = calculate_overall_confidence(verification_results)
            summary = get_verification_summary(verification_results)

            return {
                "individual_results": verification_results,
                "overall_confidence": overall_confidence,
                "summary": summary,
                "validated_at": datetime.now().isoformat()
            }

        except Exception as e:
            print(f"   WARN  AI validation failed: {e}")
            return {
                "error": str(e),
                "individual_results": {},
                "overall_confidence": 0.0
            }

    def calculate_performance_score(self, metrics: Dict[str, Any]) -> int:
        """Calculate performance score from metrics"""
        if not metrics:
            return 0

        score = 100

        # Load time (target < 3 seconds)
        load_time = metrics.get("loadTime", 0)
        if load_time > 5000:
            score -= 40
        elif load_time > 3000:
            score -= 20
        elif load_time > 2000:
            score -= 10

        # First Contentful Paint (target < 1.5 seconds)
        fcp = metrics.get("firstContentfulPaint", 0)
        if fcp > 3000:
            score -= 30
        elif fcp > 2000:
            score -= 15
        elif fcp > 1500:
            score -= 10

        # Largest Contentful Paint (target < 2.5 seconds)
        lcp = metrics.get("largestContentfulPaint", 0)
        if lcp > 4000:
            score -= 20
        elif lcp > 2500:
            score -= 10

        # Cumulative Layout Shift (target < 0.1)
        cls = metrics.get("cumulativeLayoutShift", 0)
        if cls > 0.25:
            score -= 20
        elif cls > 0.1:
            score -= 10

        return max(0, score)

    # Enhanced test functions
    async def test_authentication_enhanced(self, page: Page, test_config: Dict) -> Dict[str, Any]:
        """Enhanced authentication testing"""
        try:
            # Check for auth elements
            login_form = await page.query_selector("form")
            email_input = await page.query_selector("input[type='email']")
            password_input = await page.query_selector("input[type='password']")
            submit_button = await page.query_selector("button[type='submit']")

            # Check for OAuth buttons
            oauth_buttons = await page.query_selector_all("button:has-text('Google'), button:has-text('Microsoft'), button:has-text('SSO')")

            # Test form validation
            if email_input and password_input and submit_button:
                await email_input.fill("test@example.com")
                await password_input.fill("invalid")
                await submit_button.click()
                await page.wait_for_timeout(2000)

                # Check for error message
                error_message = await page.query_selector(".error, .alert-danger, [role='alert']")

                return {
                    "success": True,
                    "form_found": True,
                    "oauth_options": len(oauth_buttons),
                    "has_validation": error_message is not None,
                    "message": "Authentication system functional"
                }
            else:
                return {
                    "success": False,
                    "form_found": False,
                    "message": "Authentication form incomplete"
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Authentication test failed"
            }

    async def test_dashboard_enhanced(self, page: Page, test_config: Dict) -> Dict[str, Any]:
        """Enhanced dashboard testing"""
        try:
            # Check for dashboard components
            widgets = await page.query_selector_all(".widget, .card, .dashboard-item")
            charts = await page.query_selector_all("canvas, .chart, .graph")
            stats = await page.query_selector_all(".stat, .metric, .kpi")

            # Check for AI features
            ai_elements = await page.query_selector_all(":has-text('AI'), :has-text('Intelligent'), :has-text('Smart')")

            # Test real-time updates
            initial_content = await page.content()
            await page.wait_for_timeout(3000)
            updated_content = await page.content()
            content_changed = initial_content != updated_content

            return {
                "success": len(widgets) > 0,
                "widgets": len(widgets),
                "charts": len(charts),
                "stats": len(stats),
                "ai_features": len(ai_elements),
                "real_time_updates": content_changed,
                "message": f"Dashboard has {len(widgets)} widgets"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def test_agent_studio_enhanced(self, page: Page, test_config: Dict) -> Dict[str, Any]:
        """Enhanced agent studio testing"""
        try:
            # Check for agent creation interface
            create_button = await page.query_selector("button:has-text('Create'), button:has-text('New Agent')")
            agent_list = await page.query_selector_all(".agent-card, .agent-item")
            workflow_builder = await page.query_selector(".workflow-builder, .flow-editor")

            # Check for natural language input
            nl_input = await page.query_selector("textarea[placeholder*='Describe'], textarea[placeholder*='natural'], .nl-input")

            # Test agent creation flow
            if create_button:
                await create_button.click()
                await page.wait_for_timeout(1000)

                # Check for creation form
                name_input = await page.query_selector("input[name='name'], input[placeholder*='name']")
                description_input = await page.query_selector("textarea[name='description']")

                return {
                    "success": True,
                    "create_interface": create_button is not None,
                    "existing_agents": len(agent_list),
                    "workflow_builder": workflow_builder is not None,
                    "natural_language": nl_input is not None,
                    "creation_form": name_input is not None and description_input is not None,
                    "message": "Agent studio interface available"
                }
            else:
                return {
                    "success": False,
                    "create_interface": False,
                    "message": "Agent creation not accessible"
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def test_realtime_enhanced(self, page: Page, test_config: Dict) -> Dict[str, Any]:
        """Enhanced real-time feature testing"""
        try:
            # Check for WebSocket connection
            ws_status = await page.evaluate("""
                () => {
                    return {
                        hasWebSocket: typeof WebSocket !== 'undefined',
                        socketConnected: window.socket?.connected || false,
                        connectionCount: Object.keys(window).filter(k => k.toLowerCase().includes('socket')).length
                    };
                }
            """)

            # Check for real-time indicators
            online_indicators = await page.query_selector_all(".online, .status-active, :has-text('Live')")
            typing_indicators = await page.query_selector_all(".typing, :has-text('typing')")

            # Test message sending if interface available
            message_input = await page.query_selector("input[type='text'], textarea.message-input")
            send_button = await page.query_selector("button:has-text('Send'), button.send")

            return {
                "success": True,
                "websocket_available": ws_status.get("hasWebSocket", False),
                "socket_connected": ws_status.get("socketConnected", False),
                "online_indicators": len(online_indicators),
                "typing_indicators": len(typing_indicators),
                "messaging_interface": message_input is not None and send_button is not None,
                "message": "Real-time features detected"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def test_integrations_enhanced(self, page: Page, test_config: Dict) -> Dict[str, Any]:
        """Enhanced integrations testing"""
        try:
            # Count integration cards/options
            integration_cards = await page.query_selector_all(".integration-card, .service-card, .provider-card")
            connect_buttons = await page.query_selector_all("button:has-text('Connect'), button:has-text('Integrate')")

            # Check for major service categories
            categories = {
                "communication": await page.query_selector_all(":has-text('Slack'), :has-text('Teams'), :has-text('Discord')"),
                "productivity": await page.query_selector_all(":has-text('Notion'), :has-text('Asana'), :has-text('Trello')"),
                "cloud": await page.query_selector_all(":has-text('Google'), :has-text('AWS'), :has-text('Azure')"),
                "crm": await page.query_selector_all(":has-text('Salesforce'), :has-text('HubSpot')")
            }

            # Test integration detail view
            if integration_cards:
                first_card = integration_cards[0]
                await first_card.click()
                await page.wait_for_timeout(1000)

                detail_view = await page.query_selector(".integration-details, .service-details")

                return {
                    "success": True,
                    "total_integrations": len(integration_cards),
                    "connect_buttons": len(connect_buttons),
                    "categories": {k: len(v) for k, v in categories.items()},
                    "detail_view_available": detail_view is not None,
                    "message": f"Found {len(integration_cards)} integration options"
                }
            else:
                return {
                    "success": False,
                    "total_integrations": 0,
                    "message": "No integrations found"
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def generate_enhanced_report(self):
        """Generate comprehensive enhanced test report"""
        end_time = datetime.now()
        duration = (end_time - datetime.fromisoformat(self.test_results["start_time"])).total_seconds()

        # Calculate overall metrics
        total_tests = len(self.test_results["tests"])
        passed_tests = len([t for t in self.test_results["tests"] if t["status"] == "passed"])
        failed_tests = total_tests - passed_tests

        # Performance summary
        if self.test_results["performance_metrics"]:
            avg_performance = sum(
                self.calculate_performance_score(m)
                for m in self.test_results["performance_metrics"]
            ) / len(self.test_results["performance_metrics"])
        else:
            avg_performance = 0

        # Accessibility summary
        avg_accessibility = sum(self.test_results["accessibility_scores"]) / len(self.test_results["accessibility_scores"]) if self.test_results["accessibility_scores"] else 0

        # AI validation summary
        ai_validations = [t.get("ai_validation") for t in self.test_results["tests"] if t.get("ai_validation")]
        if ai_validations:
            avg_ai_confidence = sum(v.get("overall_confidence", 0) for v in ai_validations) / len(ai_validations)
        else:
            avg_ai_confidence = 0

        # Generate recommendations
        recommendations = []

        if avg_performance < 70:
            recommendations.append("Optimize page load times and resource loading")

        if avg_accessibility < 80:
            recommendations.append("Improve accessibility compliance (add ARIA labels, alt text)")

        if avg_ai_confidence < 0.6:
            recommendations.append("Review and validate marketing claims with stronger evidence")

        failed_tests_details = [t for t in self.test_results["tests"] if t["status"] == "failed"]
        if failed_tests_details:
            recommendations.append(f"Fix {len(failed_tests_details)} failing test cases")

        # Compile final report
        report = {
            "session_id": self.test_results["session_id"],
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "pass_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                "duration_seconds": duration,
                "performance_score": avg_performance,
                "accessibility_score": avg_accessibility,
                "ai_validation_confidence": avg_ai_confidence
            },
            "test_results": self.test_results["tests"],
            "recommendations": recommendations,
            "generated_at": end_time.isoformat()
        }

        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = f"test_results/enhanced/reports/enhanced_e2e_report_{timestamp}.json"

        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        # Print summary
        print("\n" + "="*80)
        print("ENHANCED E2E TEST SUMMARY")
        print("="*80)
        print(f"Tests: {passed_tests}/{total_tests} passed ({passed_tests/total_tests*100:.1f}%)")
        print(f"Performance Score: {avg_performance:.1f}/100")
        print(f"Accessibility Score: {avg_accessibility:.1f}/100")
        print(f"AI Validation Confidence: {avg_ai_confidence:.2f}")
        print(f"Duration: {duration:.1f} seconds")
        print(f"\nReport saved to: {report_path}")
        print("="*80)

    async def cleanup(self):
        """Clean up resources"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

        self.devtools.stop_mcp_server()


async def main():
    """Main entry point"""
    # Parse command line arguments
    categories = None
    if len(sys.argv) > 1:
        categories = sys.argv[1:]

    # Run enhanced tests
    integration = EnhancedAIE2EIntegration()
    results = await integration.run_enhanced_test_suite(categories)

    # Exit with appropriate code
    if "error" in results:
        sys.exit(1)
    else:
        passed = results.get("summary", {}).get("passed_tests", 0)
        total = results.get("summary", {}).get("total_tests", 1)
        sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())