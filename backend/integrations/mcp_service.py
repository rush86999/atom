import logging
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import os
import httpx

logger = logging.getLogger(__name__)

class MCPService:
    """
    Model Context Protocol (MCP) Service.
    Enables agents to use tools from MCP servers and perform web search.
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(MCPService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self.active_servers = {}
            self.search_api_key = os.getenv("TAVILY_API_KEY") or os.getenv("BRAVE_SEARCH_API_KEY")
            logger.info("MCP Service initialized")

    async def get_active_connections(self) -> List[Dict[str, Any]]:
        """Returns a list of currently connected MCP servers."""
        return [
            {
                "server_id": sid,
                "name": info.get("name"),
                "connected_at": info.get("connected_at"),
                "status": "connected"
            } for sid, info in self.active_servers.items()
        ]

    async def get_server_tools(self, server_id: str) -> List[Dict[str, Any]]:
        """Returns a list of tools supported by a specific MCP server."""
        if server_id == "google-search":
            return [
                {"name": "web_search", "description": "Search the web for real-time information", "parameters": {"query": "string"}},
                {"name": "fetch_page", "description": "Fetch the content of a specific URL", "parameters": {"url": "string"}}
            ]
        elif server_id == "local-tools":
            return [
                {
                    "name": "finance_close_check", 
                    "description": "Run a financial close readiness check for a period",
                    "parameters": {"workspace_id": "string", "period": "YYYY-MM"}
                },
                {
                    "name": "marketing_review_request", 
                    "description": "Trigger a review request for a customer based on sentiment",
                    "parameters": {"workspace_id": "string", "customer_id": "string"}
                },
                {
                    "name": "track_competitor_pricing",
                    "description": "Scrape competitor sites for product pricing",
                    "parameters": {"competitors": "list[str]", "product": "string"}
                },
                {
                    "name": "reconcile_inventory",
                    "description": "Reconcile inventory between Shopify and WMS",
                    "parameters": {"skus": "list[str]"}
                },
                {
                    "name": "reconcile_payroll",
                    "description": "Reconcile external payroll reports (ADP/Gusto) with internal ledger",
                    "parameters": {"period": "YYYY-MM"}
                },
                {
                    "name": "list_workflows",
                    "description": "List all available automated workflows",
                    "parameters": {}
                },
                {
                    "name": "trigger_workflow",
                    "description": "Trigger a specific workflow automation",
                    "parameters": {
                        "workflow_id": "string",
                        "input_data": "dict (optional)"
                    }
                },
                {
                    "name": "call_integration",
                    "description": "Execute actions on any of 39 native integrations or 280+ Activepieces connectors",
                    "parameters": {
                        "service": "string (salesforce, hubspot, shopify, slack, teams, discord, asana, jira, linear, trello, monday, google_drive, dropbox, onedrive, box, notion, zendesk, freshdesk, intercom, github, gitlab, stripe, quickbooks, xero, zoho_crm, zoho_mail, zoho_workdrive, zoho_books, zoho_inventory, zoho_projects, mailchimp, tableau, google_analytics, figma, telegram, whatsapp, zoom, or any Activepieces piece)",
                        "action": "string (create, read, list, update, delete, search, send_message, analytics, etc.)",
                        "params": "dict (action-specific parameters)",
                        "entity": "string (optional - contact, deal, task, file, ticket, etc.)"
                    }
                },
                {
                    "name": "list_integrations", 
                    "description": "List all available integrations (39 native + Activepieces catalog)",
                    "parameters": {}
                },
                {"name": "search_integration", "description": "Search for entities across any integration", "parameters": {"service": "string", "query": "string", "entity_type": "string (optional)"}},

                {"name": "list_agents", "description": "List all available specialty agent templates", "parameters": {}},
                {"name": "spawn_agent", "description": "Spawn a specialty agent to handle a sub-task", "parameters": {"template": "string", "task": "string"}},
                {
                    "name": "generate_pdf_report",
                    "description": "Generate a PDF report from data or HTML content",
                    "parameters": {"content": "string", "filename": "string"}
                },
                {
                    "name": "query_financial_metrics",
                    "description": "Extract aggregated revenue and expense metrics from Stripe/Quickbooks",
                    "parameters": {"period": "string", "metrics": "list[str]"}
                },
                {
                    "name": "get_inventory_levels",
                    "description": "Fetch current stock levels from integrated platforms (shopify, zoho)",
                    "parameters": {"platform": "string (optional)", "threshold": "number (optional)"}
                },
                {
                    "name": "get_tasks",
                    "description": "Fetch tasks from integrated project management platforms (jira, asana, trello, monday)",
                    "parameters": {"platform": "string (optional)", "project": "string (optional)", "assignee": "string (optional)"}
                },
                {
                    "name": "create_task",
                    "description": "Create a task in an integrated project management platform",
                    "parameters": {
                        "platform": "string (optional)",
                        "project": "string",
                        "title": "string",
                        "description": "string (optional)",
                        "due_date": "string (optional)"
                    }
                },
                {
                    "name": "search_contacts",
                    "description": "Search for contacts across CRM platforms (salesforce, hubspot, zoho)",
                    "parameters": {"query": "string", "platform": "string (optional)"}
                },
                {
                    "name": "get_sales_pipeline",
                    "description": "Fetch the current sales pipeline/deals from CRM platforms",
                    "parameters": {"platform": "string (optional)", "status": "string (optional)"}
                },
                {
                    "name": "send_message",
                    "description": "Send a message across integrated platforms (slack, teams, discord, whatsapp)",
                    "parameters": {
                        "platform": "string (optional)",
                        "target": "string",
                        "message": "string"
                    }
                },
                {
                    "name": "unified_knowledge_search",
                    "description": "Global semantic search across all business systems (storage, project management, crm, support)",
                    "parameters": {
                        "query": "string",
                        "platform": "string (optional)",
                        "type": "string (optional)"
                    }
                },
                # Phase 8: New Platform Tools
                {
                    "name": "send_telegram_message",
                    "description": "Send a message via Telegram to a chat or channel",
                    "parameters": {
                        "channel_id": "int",
                        "message": "string"
                    }
                },
                {
                    "name": "send_whatsapp_message",
                    "description": "Send a WhatsApp message to a phone number",
                    "parameters": {
                        "to": "string (phone number with country code)",
                        "message": "string"
                    }
                },
                {
                    "name": "create_zoom_meeting",
                    "description": "Create a Zoom meeting and get the join URL",
                    "parameters": {
                        "topic": "string",
                        "duration": "int (minutes, optional)",
                        "start_time": "string (ISO format, optional)"
                    }
                },
                {
                    "name": "get_zoom_meetings",
                    "description": "List upcoming Zoom meetings",
                    "parameters": {}
                }
            ]
        return self.active_servers.get(server_id, {}).get("tools", [])

    async def get_all_tools(self) -> List[Dict[str, Any]]:
        """Returns a unified list of all tools from all available servers."""
        all_tools = []
        
        # 1. Hardcoded internal "servers"
        all_tools.extend(await self.get_server_tools("google-search"))
        all_tools.extend(await self.get_server_tools("local-tools"))
        
        # 2. Dynamic MCP server tools
        for server_id in self.active_servers:
            all_tools.extend(await self.get_server_tools(server_id))
            
        return all_tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any:
        """Executes a tool by name, dynamically resolving the server_id."""
        # 1. Look in hardcoded servers
        for server_id in ["google-search", "local-tools"]:
            tools = await self.get_server_tools(server_id)
            if any(t["name"] == tool_name for t in tools):
                return await self.execute_tool(server_id, tool_name, arguments, context)
        
        # 2. Look in dynamic MCP servers
        for server_id, server_info in self.active_servers.items():
            if any(t["name"] == tool_name for t in server_info.get("tools", [])):
                return await self.execute_tool(server_id, tool_name, arguments, context)
        
        return {"error": f"Tool '{tool_name}' not found on any active server."}

    async def execute_tool(self, server_id: str, tool_name: str, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any:
        """Executes a tool on a specific MCP server."""
        logger.info(f"Executing MCP tool {tool_name} on server {server_id} with args: {arguments}")
        context = context or {}
        
        if server_id == "google-search" or tool_name == "web_search":
            return await self.web_search(arguments.get("query", ""))
            
        # Local Internal Tools
        if server_id == "local-tools":
            if tool_name == "finance_close_check":
                from accounting.close_agent import CloseChecklistAgent
                from core.database import SessionLocal
                
                with SessionLocal() as db:
                    agent = CloseChecklistAgent(db)
                    # Use a default workspace or passed one
                    workspace_id = arguments.get("workspace_id", "default")
                    period = arguments.get("period", datetime.now().strftime("%Y-%m"))
                    return await agent.run_close_check(workspace_id, period)
                    

            elif tool_name == "list_workflows":
                try:
                    import os
                    import json
                    workflows = []
                    storage_dir = "workflow_states"
                    
                    if not os.path.exists(storage_dir):
                        return []
                        
                    for filename in os.listdir(storage_dir):
                        if filename.endswith(".json"):
                            try:
                                with open(os.path.join(storage_dir, filename), 'r') as f:
                                    data = json.load(f)
                                    workflows.append({
                                        "id": data.get("workflow_id"),
                                        "name": data.get("name"),
                                        "description": data.get("description"),
                                        "category": data.get("category"),
                                        "status": data.get("state")
                                    })
                            except: continue
                    return workflows
                except Exception as e:
                    logger.error(f"MCP list_workflows failed: {e}")
                    return []

            elif tool_name == "trigger_workflow":
                from advanced_workflow_orchestrator import get_orchestrator
                orchestrator = get_orchestrator()
                
                wf_id = arguments.get("workflow_id")
                input_data = arguments.get("input_data", {})
                
                if not wf_id:
                     return {"error": "workflow_id is required"}
                     
                # Trigger via execute_workflow (async)
                # Since execute_tool is async, we can await it
                context = await orchestrator.execute_workflow(wf_id, input_data)
                
                return {
                    "status": context.status.value,
                    "execution_id": context.workflow_id,
                    "result": context.results,
                    "error": context.error_message
                }

            elif tool_name == "marketing_review_request":
                from core.marketing_agent import MarketingAgent
                from core.database import SessionLocal
                
                with SessionLocal() as db:
                     agent = MarketingAgent(db_session=db)
                     # Assuming customer_id is passed
                     return await agent.trigger_review_request(
                         arguments.get("customer_id"), 
                         arguments.get("workspace_id", "default")
                     )

            elif tool_name == "track_competitor_pricing":
                from operations.automations.competitive_intel import CompetitiveIntelWorkflow
                agent = CompetitiveIntelWorkflow()
                return await agent.track_competitor_pricing(
                    competitors=arguments.get("competitors", []),
                    target_product=arguments.get("product", "")
                )
            elif tool_name == "reconcile_inventory":
                from operations.automations.inventory_reconcile import InventoryReconciliationWorkflow
                agent = InventoryReconciliationWorkflow()
                return await agent.reconcile_inventory(
                    sku_list=arguments.get("skus", [])
                )
            elif tool_name == "reconcile_payroll":
                from finance.automations.payroll_guardian import PayrollReconciliationWorkflow
                agent = PayrollReconciliationWorkflow()
                return await agent.reconcile_payroll(
                    period=arguments.get("period", "")
                )
            
            elif tool_name == "call_integration":
                from integrations.universal_integration_service import UniversalIntegrationService
                workspace_id = context.get("workspace_id") or "default"
                service = UniversalIntegrationService(workspace_id=workspace_id)
                
                # Extract context-aware bits
                user_id = context.get("user_id") or "default_user"
                workspace_id = context.get("workspace_id") or "default"
                
                return await service.execute(
                    service=arguments.get("service"),
                    action=arguments.get("action"),
                    params=arguments.get("params", {}),
                    context={"user_id": user_id, "workspace_id": workspace_id}
                )
                
            elif tool_name == "search_integration":
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                return await service.search(
                     service=arguments.get("service"),
                     query=arguments.get("query"),
                     entity_type=arguments.get("entity_type"),
                     context=context
                )

            elif tool_name == "list_integrations":
                from integrations.universal_integration_service import NATIVE_INTEGRATIONS
                # Try to get Activepieces catalog
                activepieces_count = 0
                try:
                    from core.external_integration_service import external_integration_service
                    pieces = await external_integration_service.list_available_pieces()
                    activepieces_count = len(pieces) if pieces else 280  # Default estimate
                except:
                    activepieces_count = 280  # Default estimate
                
                return {
                    "native_integrations": sorted(list(NATIVE_INTEGRATIONS)),
                    "native_count": len(NATIVE_INTEGRATIONS),
                    "activepieces_count": activepieces_count,
                    "total_available": len(NATIVE_INTEGRATIONS) + activepieces_count,
                    "categories": {
                        "sales_crm": ["salesforce", "hubspot", "zoho_crm"],
                        "communication": ["slack", "teams", "discord", "google_chat", "telegram", "whatsapp", "zoom", "zoho_mail"],
                        "project_management": ["asana", "jira", "linear", "trello", "monday", "zoho_projects"],
                        "storage_knowledge": ["google_drive", "dropbox", "onedrive", "box", "notion", "zoho_workdrive"],
                        "support": ["zendesk", "freshdesk", "intercom"],
                        "development": ["github", "gitlab", "figma"],
                        "finance": ["stripe", "quickbooks", "xero", "zoho_books", "zoho_inventory"],
                        "marketing": ["mailchimp", "hubspot_marketing"],
                        "analytics": ["tableau", "google_analytics"],
                        "ecommerce": ["shopify"]
                    }
                }

            elif tool_name == "list_agents":

                from core.atom_meta_agent import SpecialtyAgentTemplate
                return SpecialtyAgentTemplate.TEMPLATES

            elif tool_name == "spawn_agent":
                from core.atom_meta_agent import get_atom_agent
                atom = get_atom_agent(context.get("workspace_id", "default"))
                return await atom.spawn_agent(
                    template_name=arguments.get("template"),
                    persist=arguments.get("persist", False)
                )

            elif tool_name == "generate_pdf_report":
                try:
                    from fpdf import FPDF
                    import tempfile
                    
                    content = arguments.get("content", "No content provided")
                    filename = arguments.get("filename", f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
                    
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", size=12)
                    
                    # Split content by lines and add to PDF
                    for line in content.split('\n'):
                        pdf.multi_cell(0, 10, txt=line)
                    
                    # Save to a temporary location or /tmp
                    target_path = os.path.join("/tmp", filename)
                    pdf.output(target_path)
                    
                    logger.info(f"PDF generated successfully: {target_path}")
                    return {
                        "status": "success", 
                        "file_path": target_path, 
                        "filename": filename,
                        "message": f"PDF generated successfully with {len(content)} characters."
                    }
                except ImportError:
                    logger.error("fpdf2 not installed")
                    return {"error": "PDF generation failed: fpdf2 library not installed"}
                except Exception as e:
                    logger.error(f"PDF generation failed: {e}")
                    return {"error": f"PDF generation failed: {str(e)}"}

            elif tool_name == "query_financial_metrics":
                from integrations.universal_integration_service import UniversalIntegrationService
                period = arguments.get("period", "last_30_days")
                metrics = arguments.get("metrics", ["revenue", "expenses"])
                
                service = UniversalIntegrationService(workspace_id=context.get("workspace_id", "default"))
                
                # Attempt to get real data from Stripe via Universal Service
                try:
                    # In a real scenario, this would call a specific 'analytics' or 'metrics' action
                    # For now, we'll try to use the query action if supported, or a specialized one
                    res = await service.execute(
                        service="stripe",
                        action="get_metrics",
                        params={"period": period, "metrics": metrics},
                        context=context
                    )
                    
                    if res.get("status") == "success":
                        return res.get("result")
                    
                    # Fallback if specific metrics action fails/not implemented, indicate real failure or unconfigured
                    return {
                        "error": "Could not fetch real financial metrics. Please ensure Stripe/Quickbooks is connected.",
                        "status": "not_configured",
                        "period": period
                    }
                except Exception as e:
                    logger.error(f"Financial query failed: {e}")
                    return {"error": f"Financial query failed: {str(e)}"}

            elif tool_name == "get_inventory_levels":
                from core.database import SessionLocal
                from core.external_integration_service import ConnectionService
                
                threshold = arguments.get("threshold", 0)
                platform = arguments.get("platform", "").lower()
                user_id = context.get("user_id", "default_user")
                
                # Fetch available inventory connections
                conn_service = ConnectionService()
                connections = await conn_service.list_connections(user_id=user_id)
                
                inventory_results = []
                
                # Helper to fetch Shopify inventory
                async def fetch_shopify():
                    shopify_conn = next((c for c in connections if c.piece_name == "shopify"), None)
                    if shopify_conn:
                        from integrations.shopify_service import shopify_service
                        shop = shopify_conn.metadata.get("shop_url")
                        data = await shopify_service.get_inventory_levels(
                            access_token=shopify_conn.credentials.get("access_token"),
                            shop=shop
                        )
                        return data
                    return []

                # Helper to fetch Zoho inventory
                async def fetch_zoho():
                    zoho_conn = next((c for c in connections if c.piece_name == "zoho_inventory"), None)
                    if zoho_conn:
                        from integrations.zoho_inventory_service import zoho_inventory_service
                        # Zoho often needs org ID which might be in metadata
                        org_id = zoho_conn.metadata.get("organization_id")
                        data = await zoho_inventory_service.get_inventory_levels(
                            token=zoho_conn.credentials.get("access_token"),
                            organization_id=org_id
                        )
                        return data
                    return []

                # Route based on platform or fetch all if not specified
                if platform == "shopify":
                    inventory_results.extend(await fetch_shopify())
                elif platform == "zoho":
                    inventory_results.extend(await fetch_zoho())
                else:
                    # Fetch all available
                    shopify_data, zoho_data = await asyncio.gather(fetch_shopify(), fetch_zoho())
                    inventory_results.extend(shopify_data)
                    inventory_results.extend(zoho_data)

                # Filter by threshold if requested
                if threshold > 0:
                    inventory_results = [item for item in inventory_results if item.get("available", 0) <= threshold]
                
                if not inventory_results and not platform:
                    return {"error": "No inventory platforms connected (Shopify/Zoho).", "status": "not_configured"}
                
                return inventory_results

            elif tool_name == "get_tasks":
                from core.external_integration_service import ConnectionService
                user_id = context.get("user_id", "default_user")
                platform = arguments.get("platform", "").lower()
                
                conn_service = ConnectionService()
                connections = await conn_service.list_connections(user_id=user_id)
                
                all_tasks = []
                
                # Jira
                if not platform or platform == "jira":
                    jira_conn = next((c for c in connections if c.piece_name == "jira"), None)
                    if jira_conn:
                        from integrations.jira_service import JiraService
                        jira = JiraService(
                            base_url=jira_conn.metadata.get("base_url"),
                            username=jira_conn.credentials.get("username"),
                            api_token=jira_conn.credentials.get("api_token")
                        )
                        res = jira.search_issues("assignee = currentUser()")
                        for issue in res.get("issues", []):
                            all_tasks.append({
                                "id": issue["key"],
                                "title": issue["fields"]["summary"],
                                "status": issue["fields"]["status"]["name"],
                                "platform": "jira",
                                "url": f"{jira.base_url}/browse/{issue['key']}"
                            })

                # Asana
                if not platform or platform == "asana":
                    asana_conn = next((c for c in connections if c.piece_name == "asana"), None)
                    if asana_conn:
                        from integrations.asana_service import asana_service
                        res = await asana_service.get_tasks(asana_conn.credentials.get("access_token"))
                        if res.get("ok"):
                            for task in res.get("tasks", []):
                                all_tasks.append({
                                    "id": task["gid"],
                                    "title": task["name"],
                                    "status": "Completed" if task["completed"] else "Incomplete",
                                    "platform": "asana",
                                    "url": f"https://app.asana.com/0/0/{task['gid']}"
                                })

                # Trello
                if not platform or platform == "trello":
                    trello_conn = next((c for c in connections if c.piece_name == "trello"), None)
                    if trello_conn:
                        from integrations.trello_service import TrelloService
                        trello = TrelloService(
                            api_key=trello_conn.credentials.get("api_key"),
                            access_token=trello_conn.credentials.get("access_token")
                        )
                        cards = trello.get_cards()
                        for card in cards:
                            all_tasks.append({
                                "id": card["id"],
                                "title": card["name"],
                                "status": "Closed" if card["closed"] else "Open",
                                "platform": "trello",
                                "url": card["url"]
                            })

                return all_tasks

            elif tool_name == "create_task":
                from core.external_integration_service import ConnectionService
                user_id = context.get("user_id", "default_user")
                platform = arguments.get("platform", "").lower()
                title = arguments.get("title")
                description = arguments.get("description", "")
                project = arguments.get("project")
                
                conn_service = ConnectionService()
                connections = await conn_service.list_connections(user_id=user_id)
                
                # If platform not specified, pick first available PM
                pm_pieces = ["jira", "asana", "trello", "monday"]
                active_conn = None
                
                if platform:
                    active_conn = next((c for c in connections if c.piece_name == platform), None)
                else:
                    active_conn = next((c for c in connections if c.piece_name in pm_pieces), None)
                
                if not active_conn:
                    return {"error": "No project management platform connected.", "status": "not_configured"}

                p_name = active_conn.piece_name
                if p_name == "jira":
                    from integrations.jira_service import JiraService
                    jira = JiraService(
                        base_url=active_conn.metadata.get("base_url"),
                        username=active_conn.credentials.get("username"),
                        api_token=active_conn.credentials.get("api_token")
                    )
                    issue = jira.create_issue(project, title, "Task", description)
                    return {"status": "success", "platform": "jira", "id": issue["key"] if issue else None}
                
                elif p_name == "asana":
                    from integrations.asana_service import asana_service
                    res = await asana_service.create_task(
                        active_conn.credentials.get("access_token"),
                        {"name": title, "description": description, "projects": [project]}
                    )
                    return res
                
                elif p_name == "trello":
                    from integrations.trello_service import TrelloService
                    trello = TrelloService(
                        api_key=active_conn.credentials.get("api_key"),
                        access_token=active_conn.credentials.get("access_token")
                    )
                    # For Trello, 'project' is used as 'list_id'
                    card = trello.create_card(title, project, description)
                    return {"status": "success", "platform": "trello", "id": card["id"] if card else None}

                return {"error": f"Platform {p_name} not yet fully supported for create_task via MCP."}

            elif tool_name == "search_contacts":
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                
                user_id = context.get("user_id", "default_user")
                platform = arguments.get("platform", "").lower()
                query = arguments.get("query")
                
                all_contacts = []
                
                # Salesforce
                if not platform or platform == "salesforce":
                    try:
                        sf_res = await service.search("salesforce", query, "contact", {"user_id": user_id})
                        for contact in sf_res:
                            all_contacts.append({
                                "name": contact.get("Name"),
                                "email": contact.get("Email"),
                                "platform": "salesforce",
                                "id": contact.get("Id")
                            })
                    except Exception as e:
                        logger.error(f"Salesforce contact search failed: {e}")

                # HubSpot
                if not platform or platform == "hubspot":
                    try:
                        hs_res = await service.search("hubspot", query, "contact", {"user_id": user_id})
                        for contact in hs_res:
                            all_contacts.append({
                                "name": f"{contact.get('properties', {}).get('firstname', '')} {contact.get('properties', {}).get('lastname', '')}".strip(),
                                "email": contact.get('properties', {}).get('email'),
                                "platform": "hubspot",
                                "id": contact.get("id")
                            })
                    except Exception as e:
                        logger.error(f"HubSpot contact search failed: {e}")

                return all_contacts

            elif tool_name == "get_sales_pipeline":
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                
                user_id = context.get("user_id", "default_user")
                platform = arguments.get("platform", "").lower()
                
                pipeline = []
                
                # Fetch Salesforce Opportunities
                if not platform or platform == "salesforce":
                    try:
                        sf_res = await service.execute("salesforce", "list", {"entity": "opportunity"}, context={"user_id": user_id})
                        if isinstance(sf_res, list):
                            for op in sf_res:
                                pipeline.append({
                                    "deal": op.get("Name"),
                                    "value": op.get("Amount", 0),
                                    "status": op.get("StageName"),
                                    "platform": "salesforce",
                                    "company": op.get("Account", {}).get("Name")
                                })
                    except Exception as e:
                        logger.error(f"Failed to fetch Salesforce deals: {e}")

                # Fetch HubSpot Deals
                if not platform or platform == "hubspot":
                    try:
                        hs_res = await service.execute("hubspot", "list", {"entity": "deal"}, context={"user_id": user_id})
                        if isinstance(hs_res, list):
                            for deal in hs_res:
                                pipeline.append({
                                    "deal": deal.get("properties", {}).get("dealname"),
                                    "value": float(deal.get("properties", {}).get("amount") or 0),
                                    "status": deal.get("properties", {}).get("dealstage"),
                                    "platform": "hubspot",
                                    "company": "HubSpot Account" # HubSpot structure varies for associations
                                })
                    except Exception as e:
                        logger.error(f"Failed to fetch HubSpot deals: {e}")

                return pipeline

            elif tool_name == "send_message":
                from core.external_integration_service import ConnectionService
                user_id = context.get("user_id", "default_user")
                platform = arguments.get("platform", "").lower()
                target = arguments.get("target")
                message = arguments.get("message")
                
                conn_service = ConnectionService()
                connections = await conn_service.list_connections(user_id=user_id)
                
                # If platform not specified, pick Slack as default or first available
                active_conn = None
                if platform:
                    active_conn = next((c for c in connections if c.piece_name == platform), None)
                else:
                    active_conn = next((c for c in connections if c.piece_name in ["slack", "teams", "discord", "whatsapp"]), None)

                if not active_conn:
                    return {"error": "No communication platform connected.", "status": "not_configured"}

                p_name = active_conn.piece_name
                if p_name == "slack":
                    from integrations.slack_enhanced_service import slack_enhanced_service
                    # Send to channel or user
                    await slack_enhanced_service.send_message(active_conn.credentials.get("access_token"), target, message)
                    return {"status": "success", "platform": "slack", "recipient": target}
                
                elif p_name == "teams":
                    from integrations.teams_enhanced_service import teams_enhanced_service
                    await teams_enhanced_service.send_chat_message(active_conn.credentials.get("access_token"), target, message)
                    return {"status": "success", "platform": "teams"}

                elif p_name == "discord":
                    from integrations.discord_enhanced_service import discord_enhanced_service
                    await discord_enhanced_service.send_message(target, message)
                    return {"status": "success", "platform": "discord"}

                return {"error": f"Unified messaging for {p_name} not yet implemented."}

            elif tool_name == "unified_knowledge_search":
                from ai.data_intelligence import engine
                query = arguments.get("query", "").lower()
                platform_filter = arguments.get("platform", "").lower()
                type_filter = arguments.get("type", "").lower()
                
                all_results = []
                
                # Query the unified entity registry
                for entity in engine.entity_registry.values():
                    # Apply query match
                    if query and query not in entity.canonical_name.lower():
                        continue
                    
                    # Apply platform filter
                    entity_platforms = [p.value for p in entity.source_platforms]
                    if platform_filter and platform_filter not in entity_platforms:
                        continue
                    
                    # Apply type filter
                    if type_filter and entity.entity_type.value != type_filter:
                        continue
                    
                    # Map to search result format
                    all_results.append({
                        "id": entity.entity_id,
                        "name": entity.canonical_name,
                        "type": entity.entity_type.value,
                        "platform": entity_platforms[0] if entity_platforms else "unknown",
                        "status": entity.attributes.get("status") or entity.attributes.get("StageName") or entity.attributes.get("status"),
                        "value": entity.attributes.get("amount") or entity.attributes.get("value"),
                        "modified_at": entity.updated_at.isoformat()
                    })

                return all_results

            # Phase 8: New Platform Tool Handlers
            elif tool_name == "send_telegram_message":
                try:
                    from integrations.atom_telegram_integration import atom_telegram_integration
                    channel_id = arguments.get("channel_id")
                    message = arguments.get("message")
                    
                    if not channel_id or not message:
                        return {"error": "channel_id and message are required"}
                    
                    result = await atom_telegram_integration.send_intelligent_message(
                        channel_id=int(channel_id),
                        message=message,
                        metadata={"via": "mcp", "context": context}
                    )
                    return result
                except Exception as e:
                    logger.error(f"Telegram MCP tool failed: {e}")
                    return {"error": str(e), "platform": "telegram"}

            elif tool_name == "send_whatsapp_message":
                try:
                    from integrations.whatsapp_business_integration import whatsapp_integration
                    to = arguments.get("to")
                    message = arguments.get("message")
                    
                    if not to or not message:
                        return {"error": "to and message are required"}
                    
                    result = whatsapp_integration.send_message(
                        to=to,
                        message_type="text",
                        content={"text": message}
                    )
                    return result
                except ImportError:
                    return {"error": "WhatsApp integration not available", "status": "not_configured"}
                except Exception as e:
                    logger.error(f"WhatsApp MCP tool failed: {e}")
                    return {"error": str(e), "platform": "whatsapp"}

            elif tool_name == "create_zoom_meeting":
                try:
                    from integrations.zoom_service import zoom_service
                    from core.external_integration_service import ConnectionService
                    
                    user_id = context.get("user_id", "default_user")
                    conn_service = ConnectionService()
                    connections = await conn_service.list_connections(user_id=user_id)
                    zoom_conn = next((c for c in connections if c.piece_name == "zoom"), None)
                    
                    if not zoom_conn:
                        return {"error": "Zoom not connected", "status": "not_configured"}
                    
                    topic = arguments.get("topic", "ATOM Meeting")
                    duration = arguments.get("duration", 60)
                    start_time = arguments.get("start_time")
                    
                    result = await zoom_service.create_meeting(
                        topic=topic,
                        duration=duration,
                        start_time=start_time,
                        access_token=zoom_conn.credentials.get("access_token")
                    )
                    return {"status": "success", "meeting": result}
                except Exception as e:
                    logger.error(f"Zoom MCP tool failed: {e}")
                    return {"error": str(e), "platform": "zoom"}

            elif tool_name == "get_zoom_meetings":
                try:
                    from integrations.zoom_service import zoom_service
                    from core.external_integration_service import ConnectionService
                    
                    user_id = context.get("user_id", "default_user")
                    conn_service = ConnectionService()
                    connections = await conn_service.list_connections(user_id=user_id)
                    zoom_conn = next((c for c in connections if c.piece_name == "zoom"), None)
                    
                    if not zoom_conn:
                        return {"error": "Zoom not connected", "status": "not_configured"}
                    
                    result = await zoom_service.list_meetings(
                        access_token=zoom_conn.credentials.get("access_token")
                    )
                    return {"status": "success", "meetings": result}
                except Exception as e:
                    logger.error(f"Zoom list meetings failed: {e}")
                    return {"error": str(e), "platform": "zoom"}

        # Unknown MCP server - fail explicitly
        return {"error": f"Tool '{tool_name}' on server '{server_id}' is not implemented.", "status": "not_implemented"}

    async def web_search(self, query: str) -> Dict[str, Any]:
        """
        Performs a web search using available search APIs or MCP servers.
        """
        logger.info(f"Performing web search for: {query}")
        
        # If we have a real Tavily API key, use it
        if os.getenv("TAVILY_API_KEY"):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": os.getenv("TAVILY_API_KEY"),
                            "query": query,
                            "include_answer": True
                        },
                        timeout=10.0
                    )
                    if response.status_code == 200:
                        return response.json()
            except Exception as e:
                logger.error(f"Tavily search failed: {e}")

        # No search API key configured - return empty results with error
        logger.warning("No search API key (TAVILY_API_KEY) configured. Search unavailable.")
        return {
            "query": query,
            "results": [],
            "answer": None,
            "error": "Web search is not configured. Please set TAVILY_API_KEY."
        }

# Singleton instance
mcp_service = MCPService()
