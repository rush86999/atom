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
                    "description": "Call an external integration (Salesforce, HubSpot, etc.)",
                    "parameters": {
                        "service": "string (salesforce, hubspot)",
                        "action": "string (create, read, list, update, query)",
                        "params": "dict"
                    }
                },
                {"name": "search_integration", "description": "Search for entities in an integration", "parameters": {"service": "string", "query": "string", "entity_type": "string (optional)"}},
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
                    "name": "get_shopify_inventory",
                    "description": "Fetch current stock levels from Shopify",
                    "parameters": {"threshold": "number (optional)"}
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

            elif tool_name == "get_shopify_inventory":
                from integrations.shopify_service import ShopifyService
                from core.database import SessionLocal
                
                threshold = arguments.get("threshold", 0)
                workspace_id = context.get("workspace_id", "default")
                
                # We need credentials - in a real MCP call, these would come from the user's connection
                # For this tool, we assume we can fetch them or the service handles it.
                try:
                    # This is a bit complex as we need access_token/shop
                    # In a truly integrated MCP, this would be injected by the ConnectionService
                    from core.external_integration_service import ConnectionService
                    conn_service = ConnectionService()
                    
                    # Find a Shopify connection for this user/workspace
                    user_id = context.get("user_id", "default_user")
                    connections = await conn_service.list_connections(user_id=user_id)
                    shopify_conn = next((c for c in connections if c.piece_name == "shopify"), None)
                    
                    if not shopify_conn:
                        return {"error": "Shopify is not connected. Please connect it in the Integrations tab.", "status": "not_configured"}
                    
                    # Use ShopifyService
                    from integrations.shopify_service import shopify_service
                    # Assuming we store shop domain in metadata or use a default
                    shop = shopify_conn.metadata.get("shop_url")
                    
                    # Fetch real inventory
                    inventory = await shopify_service.get_inventory_levels(
                        access_token=shopify_conn.credentials.get("access_token"),
                        shop=shop
                    )
                    
                    # Filter by threshold if needed
                    if threshold > 0:
                        inventory = [item for item in inventory if item.get("available", 0) <= threshold]
                        
                    return inventory
                except Exception as e:
                    logger.error(f"Shopify inventory fetch failed: {e}")
                    return {"error": f"Failed to fetch Shopify inventory: {str(e)}"}

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
