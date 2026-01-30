import logging
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import os
import httpx
from .mcp_converter import MCPToolConverter

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


    async def get_openai_tools(self) -> List[Dict[str, Any]]:
        """Returns all available tools in OpenAI function calling format."""
        all_tools = await self.get_all_tools()
        return MCPToolConverter.convert_to_openai_tools(all_tools)

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
                # --- Common & Discovery ---
                {
                    "name": "discover_connections",
                    "description": "List all active integration connections for the current workspace",
                    "parameters": {}
                },
                {
                    "name": "global_search",
                    "description": "Search for a query across all connected platforms simultaneously",
                    "parameters": {
                        "query": "string",
                        "platforms": "array (optional, list of platforms to search, defaults to all active)"
                    }
                },
                # --- CRM & Sales ---
                {
                    "name": "search_contacts",
                    "description": "Search for contacts across CRM platforms (Salesforce, HubSpot, Zoho, Pipedrive, Intercom)",
                    "parameters": {"query": "string", "platform": "string (optional)"}
                },
                {
                    "name": "create_crm_lead",
                    "description": "Create a new lead or contact in a CRM platform",
                    "parameters": {
                        "platform": "string (salesforce, hubspot, zoho_crm)",
                        "first_name": "string",
                        "last_name": "string",
                        "email": "string",
                        "company": "string (optional)"
                    }
                },
                {
                    "name": "get_sales_pipeline",
                    "description": "Fetch the current sales pipeline/deals from CRM platforms",
                    "parameters": {"platform": "string (optional)", "status": "string (optional)"}
                },
                {
                    "name": "update_crm_lead",
                    "description": "Update an existing lead or contact in a CRM platform",
                    "parameters": {
                        "platform": "string (salesforce, hubspot, zoho_crm)",
                        "id": "string (the record ID to update)",
                        "data": "object (fields to update, e.g. {'status': 'Qualified', 'phone': '123-456'})"
                    }
                },
                {
                    "name": "create_crm_deal",
                    "description": "Create a new deal or opportunity in a CRM platform",
                    "parameters": {
                        "platform": "string (salesforce, hubspot)",
                        "title": "string",
                        "amount": "number",
                        "close_date": "string (YYYY-MM-DD)",
                        "stage": "string",
                        "data": "object (optional extra fields)"
                    }
                },
                {
                    "name": "update_crm_deal",
                    "description": "Update an existing deal or opportunity in a CRM platform",
                    "parameters": {
                        "platform": "string (salesforce, hubspot)",
                        "id": "string",
                        "data": "object (e.g. {'stage': 'Closed Won', 'probability': 100})"
                    }
                },

                # --- Project Management ---
                {
                    "name": "list_projects",
                    "description": "List projects/boards from project management platforms (Jira, Asana, Linear, Monday)",
                    "parameters": {"platform": "string"}
                },
                {
                    "name": "get_tasks",
                    "description": "Fetch tasks from integrated project management platforms",
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
                    "name": "update_task",
                    "description": "Update a task in an integrated project management platform (Jira, Asana, Linear, Monday)",
                    "parameters": {
                        "platform": "string",
                        "id": "string (task ID)",
                        "data": "object (fields to update, e.g. {'status': 'Done', 'priority': 'High'})"
                    }
                },
                {
                    "name": "create_support_ticket",
                    "description": "Create a new support ticket (Zendesk, Freshdesk, Intercom)",
                    "parameters": {
                        "platform": "string",
                        "subject": "string",
                        "description": "string",
                        "priority": "string (optional)",
                        "data": "object (optional extra fields)"
                    }
                },
                {
                    "name": "update_support_ticket",
                    "description": "Update an existing support ticket (Zendesk, Freshdesk, Intercom)",
                    "parameters": {
                        "platform": "string",
                        "id": "string",
                        "data": "object (fields to update, e.g. {'status': 'solved', 'priority': 'high'})"
                    }
                },

                # --- Knowledge & Memory (Phase 18) ---
                {
                    "name": "ingest_knowledge_from_text",
                    "description": "Extract structured knowledge (entities/relationships) from text and store it in Atom's memory and knowledge graph",
                    "parameters": {
                        "text": "string (the raw text content to process)",
                        "doc_id": "string (optional ID for the document)",
                        "source": "string (optional source description, e.g. 'email from client')"
                    }
                },
                {
                    "name": "ingest_knowledge_from_file",
                    "description": "Extract structured knowledge from a file (PDF, DOCX, Image, Spreadsheet) and store it in Atom's knowledge systems",
                    "parameters": {
                        "file_path": "string (absolute path to the file)",
                        "file_type": "string (optional extension like 'pdf', 'png')"
                    }
                },
                {
                    "name": "query_knowledge_graph",
                    "description": "Search Atom's knowledge graph for complex relationships and themes. Use 'global' for high-level summaries and 'local' for specific entity details.",
                    "parameters": {
                        "query": "string (the complex question or search term)",
                        "mode": "string (optional: 'global', 'local', or 'auto')"
                    }
                },
                {
                    "name": "save_business_fact",
                    "description": "Store a verifiable business fact with citations. Use this for Truths (policies, rules), not just observations.",
                    "parameters": {
                        "fact": "string (The fact statement)",
                        "citations": "list[str] (List of file paths or docs supporting this)",
                        "reason": "string (Why this fact is relevant)",
                        "source": "string (optional context)"
                    }
                },
                {
                    "name": "verify_citation",
                    "description": "Check if a citation (file path) is valid and read it to confirm the fact.",
                    "parameters": {
                        "path": "string (Absolute file path or unique doc ID)"
                    }
                },
                {
                    "name": "search_tasks",
                    "description": "Search for tasks/issues across project management platforms",
                    "parameters": {"query": "string", "platform": "string (optional)"}
                },
                {
                    "name": "search_formulas",
                    "description": "Search for business logic, math definitions, and extracted Excel formulas in Atom's memory",
                    "parameters": {"query": "string"}
                },
                {
                    "name": "canvas_tool",
                    "description": "Render custom UI widgets (Generative UI) to the user's dashboard. Use to present data visualization, forms, or status.",
                    "parameters": {
                        "action": "string (present, update, close)",
                        "component": "string (optional: 'chart', 'form', 'status_panel', 'markdown', 'custom')",
                        "data": "object (payload for the component)",
                        "title": "string (optional title for the widget)"
                    }
                },

                # --- Communication & Collaboration ---
                {
                    "name": "analyze_message",
                    "description": "Analyze a communication message for sentiment, intent, and suggested tags",
                    "parameters": {"message_id": "string", "content": "string (optional, if not in db)"}
                },
                {
                    "name": "draft_response",
                    "description": "Save a draft response for a message in the Communication Hub",
                    "parameters": {
                        "message_id": "string", 
                        "content": "string", 
                        "confidence": "number (0.0 to 1.0)"
                    }
                },
                {
                    "name": "approve_draft",
                    "description": "Approve and send a draft response",
                    "parameters": {"message_id": "string", "edited_content": "string (optional)"}
                },
                {
                    "name": "send_message",
                    "description": "Send a message across integrated platforms (Slack, Teams, Discord, WhatsApp)",
                    "parameters": {
                        "platform": "string (optional)",
                        "target": "string (channel ID or user ID)",
                        "message": "string"
                    }
                },
                {
                    "name": "ingest_message_attachment",
                    "description": "Extract and ingest an attachment from a message into memory",
                    "parameters": {
                        "message_id": "string", 
                        "attachment_id": "string",
                        "file_name": "string (optional)"
                    }
                },
                {
                    "name": "post_channel_message",
                    "description": "Post a high-visibility update to a specific team channel",
                    "parameters": {
                        "platform": "string (slack, teams, discord)",
                        "channel": "string (channel name or ID)",
                        "message": "string"
                    }
                },
                {
                    "name": "send_email",
                    "description": "Send an email via Gmail, Outlook, or Zoho Mail",
                    "parameters": {
                        "platform": "string (gmail, outlook, zoho_mail, optional)",
                        "to": "string (recipient email)",
                        "subject": "string",
                        "body": "string"
                    }
                },
                {
                    "name": "search_emails",
                    "description": "Search for emails across Gmail, Outlook, and Zoho Mail",
                    "parameters": {"query": "string", "platform": "string (optional)"}
                },
                {
                    "name": "unified_communication_search",
                    "description": "Global search across Slack, Teams, Gmail, and other channels",
                    "parameters": {"query": "string"}
                },
                # --- WhatsApp Business ---
                {
                    "name": "whatsapp_send_message",
                    "description": "Send a WhatsApp message to a customer or contact. Requires connected WhatsApp Business.",
                    "parameters": {
                        "to": "string (recipient phone number with country code, e.g. +14155551234)",
                        "message": "string (message text)"
                    }
                },
                {
                    "name": "whatsapp_send_template",
                    "description": "Send a pre-approved WhatsApp template message for marketing or notifications",
                    "parameters": {
                        "to": "string (recipient phone number)",
                        "template_name": "string (name of pre-approved template)",
                        "language": "string (optional, default 'en')",
                        "components": "array (optional, template variable values)"
                    }
                },
                {
                    "name": "whatsapp_list_templates",
                    "description": "List all available WhatsApp message templates for this business",
                    "parameters": {}
                },

                # --- Storage & Knowledge ---
                {
                    "name": "search_files",
                    "description": "Search for files and folders across storage platforms (Drive, Dropbox, Notion, Box, OneDrive, Zoho WorkDrive)",
                    "parameters": {"query": "string", "platform": "string (optional)"}
                },
                {
                    "name": "upload_file_to_storage",
                    "description": "Upload a file to a storage platform (Drive, Dropbox, OneDrive, Box, S3, GCS)",
                    "parameters": {
                        "platform": "string",
                        "file_path": "string",
                        "destination_path": "string (optional)",
                        "folder_id": "string (optional)"
                    }
                },
                {
                    "name": "create_storage_folder",
                    "description": "Create a new folder in a storage platform",
                    "parameters": {
                        "platform": "string",
                        "name": "string",
                        "parent_id": "string (optional)"
                    }
                },
                {
                    "name": "list_files",
                    "description": "List files from a specific storage platform",
                    "parameters": {"platform": "string", "path": "string (optional)"}
                },
                {
                    "name": "unified_knowledge_search",
                    "description": "Global semantic search across all business systems (storage, project management, crm)",
                    "parameters": {"query": "string"}
                },
                
                # --- Marketing & Social Proof ---
                {
                    "name": "manage_reviews",
                    "description": "Gather new reviews from platforms (e.g. Google Reviews) and suggest responses",
                    "parameters": {"platform": "string (optional, default: 'google_reviews')"}
                },
                {
                    "name": "request_testimonial",
                    "description": "Send a formal testimonial request to a customer via email or slack",
                    "parameters": {"customer_id": "string", "platform": "string (optional, e.g. 'email', 'slack')"}
                },
                {
                    "name": "analyze_ads_performance",
                    "description": "Get performance insights from advertising platforms (Meta, Google, LinkedIn Ads)",
                    "parameters": {"service": "string (e.g. 'meta_ads', 'google_ads', 'linkedin_ads')"}
                },

                # --- Sales & Lead Intelligence ---
                {
                    "name": "score_lead",
                    "description": "Calculate a lead quality score based on CRM data and provide reasoning",
                    "parameters": {"lead_data": "object", "platform": "string (optional, e.g. 'hubspot', 'salesforce')"}
                },
                {
                    "name": "draft_sales_outreach",
                    "description": "Generate personalized sales outreach copy for a specific lead",
                    "parameters": {"lead_id": "string", "context": "string (optional)", "platform": "string (optional)"}
                },
                {
                    "name": "monitor_pipeline_health",
                    "description": "Identify stalled deals and audit CRM pipeline health",
                    "parameters": {"platform": "string (optional, e.g. 'hubspot', 'salesforce')"}
                },

                # --- B2B Procurement (Phase 16) ---
                {
                    "name": "b2b_extract_po",
                    "description": "Extract structured Purchase Order data from email or unstructured text using AI",
                    "parameters": {"text": "string"}
                },
                {
                    "name": "b2b_create_draft_order",
                    "description": "Create a draft order from extracted PO data. Resolves customer identity and applies B2B pricing.",
                    "parameters": {
                        "workspace_id": "string",
                        "customer_email": "string",
                        "po_data": "object"
                    }
                },
                {
                    "name": "b2b_push_to_integrations",
                    "description": "Push a B2B order to external CRM (HubSpot) and Accounting (QuickBooks) systems.",
                    "parameters": {
                        "order_id": "string",
                        "customer_id": "string (optional)"
                    }
                },

                {
                    "name": "shopify_create_product",
                    "description": "Create a new product in Shopify",
                    "parameters": {
                        "title": "string",
                        "body_html": "string (optional)",
                        "vendor": "string (optional)",
                        "product_type": "string (optional)",
                        "tags": "string (optional, comma separated)",
                        "variants": "array (optional, list of variants)"
                    }
                },
                {
                    "name": "shopify_update_inventory",
                    "description": "Update inventory level for a variant",
                    "parameters": {
                        "inventory_item_id": "string",
                        "location_id": "string",
                        "available": "integer (new available quantity)"
                    }
                },
                {
                    "name": "shopify_get_orders",
                    "description": "Get recent orders from Shopify",
                    "parameters": {
                        "limit": "integer (optional, default 10)",
                        "status": "string (optional, any/open/closed)"
                    }
                },
                # --- Finance & Accounting ---
                {
                    "name": "query_financial_metrics",
                    "description": "Extract aggregated revenue and expense metrics from Stripe/Quickbooks",
                    "parameters": {"period": "string", "metrics": "list[str]"}
                },
                {
                    "name": "list_finance_invoices",
                    "description": "List recent invoices from Stripe, QuickBooks, Xero, or Zoho Books",
                    "parameters": {"platform": "string (optional)", "limit": "number (optional)"}
                },
                {
                    "name": "finance_close_check", 
                    "description": "Run a financial close readiness check for a period",
                    "parameters": {"period": "YYYY-MM"}
                },
                {
                    "name": "create_invoice",
                    "description": "Create a new invoice in Stripe, QuickBooks, Xero, or Zoho Books",
                    "parameters": {
                        "platform": "string",
                        "customer_id": "string",
                        "amount": "number",
                        "currency": "string",
                        "description": "string",
                        "data": "object (optional extra fields)"
                    }
                },
                {
                    "name": "push_to_integration",
                    "description": "STANDARDIZED PUSH: Sync or create data in any connected integration in a granular way",
                    "parameters": {
                        "service": "string (e.g. 'salesforce', 'hubspot', 'slack')",
                        "action": "string (e.g. 'create', 'update', 'sync')",
                        "params": "object (granular data for the action)"
                    }
                },
                {
                    "name": "create_ecommerce_order",
                    "description": "Create a new order in Shopify or other ecommerce platforms",
                    "parameters": {
                        "platform": "string",
                        "customer_id": "string",
                        "line_items": "array",
                        "data": "object (optional extra fields)"
                    }
                },
                {
                    "name": "add_marketing_subscriber",
                    "description": "Add a new subscriber to a marketing list (Mailchimp, HubSpot)",
                    "parameters": {
                        "platform": "string",
                        "email": "string",
                        "list_id": "string (optional)",
                        "tags": "array (optional)"
                    }
                },
                {
                    "name": "create_record",
                    "description": "Universal granular record creation across 46+ supported services",
                    "parameters": {
                        "service": "string",
                        "entity": "string (e.g. 'lead', 'task', 'ticket', 'order')",
                        "data": "object"
                    }
                },
                {
                    "name": "update_record",
                    "description": "Universal granular record update across 46+ supported services",
                    "parameters": {
                        "service": "string",
                        "entity": "string",
                        "id": "string",
                        "data": "object"
                    }
                },

                # --- Specialized Specialty Agent Tools ---
                {"name": "list_agents", "description": "List all available specialty agents from the database and templates", "parameters": {}},
                {"name": "spawn_agent", "description": "Spawn a specialty agent to handle a sub-task", "parameters": {"template": "string", "task": "string"}},
                {
                    "name": "bridge_agent_delegate",
                    "description": "Send a task to another agent via the Universal Bridge. This is the preferred way for agents to collaborate asynchronously.",
                    "parameters": {
                        "target_agent": "string (name or ID of the agent)",
                        "message": "string (the task or message to send)"
                    }
                },
                {"name": "list_workflows", "description": "List all available automated workflows", "parameters": {}},
                {"name": "trigger_workflow", "description": "Trigger a specific workflow automation", "parameters": {"workflow_id": "string", "input_data": "dict (optional)"}},
                
                # --- Governance & Meta ---
                {
                    "name": "get_system_health",
                    "description": "Query the health, performance, and drift of integrated services",
                    "parameters": {"service": "string (optional, e.g. 'shopify')"}
                },
                {
                    "name": "request_human_intervention",
                    "description": "Explicitly pause execution to ask a human for approval or clarification on a sensitive action",
                    "parameters": {
                        "action": "string (what you want to do)",
                        "reason": "string (why you need approval)",
                        "params": "object (optional, parameters for the action)"
                    }
                },

                # --- Utilities ---
                {
                    "name": "generate_pdf_report",
                    "description": "Generate a PDF report from data or HTML content",
                    "parameters": {"content": "string", "filename": "string"}
                },

                # --- Shipping & Logistics ---
                {
                    "name": "create_shipment",
                    "description": "Create a shipment with any connected carrier (Shippo, EasyPost, UPS, FedEx, etc.)",
                    "parameters": {
                        "platform": "string (shippo, easypost, ups, fedex, purolator, freightcom, shipstation)",
                        "from_address": "object (address JSON)",
                        "to_address": "object (address JSON)",
                        "parcel": "object (weight, dimensions)"
                    }
                },
                {
                    "name": "get_shipping_rates",
                    "description": "Get shipping rates from connected carriers for a package",
                    "parameters": {
                        "platform": "string (optional, gets from all if not specified)",
                        "from_address": "object",
                        "to_address": "object",
                        "parcel": "object"
                    }
                },
                {
                    "name": "create_shipping_label",
                    "description": "Purchase and create a shipping label for a shipment",
                    "parameters": {
                        "platform": "string",
                        "rate_id": "string (rate selected from get_shipping_rates)"
                    }
                },
                {
                    "name": "track_shipment",
                    "description": "Get tracking status for a shipment",
                    "parameters": {
                        "platform": "string (optional)",
                        "tracking_number": "string",
                        "carrier": "string (optional, auto-detected if not provided)"
                    }
                },
                {
                    "name": "validate_address",
                    "description": "Validate and standardize a shipping address",
                    "parameters": {
                        "platform": "string (shippo, easypost)",
                        "address": "object (street, city, state, postal_code, country)"
                    }
                },

                # --- Cloud Providers ---
                {
                    "name": "s3_upload",
                    "description": "Upload a file or content to AWS S3 bucket",
                    "parameters": {
                        "bucket": "string (S3 bucket name)",
                        "key": "string (object key/path)",
                        "content": "string (file content or base64 data)"
                    }
                },
                {
                    "name": "s3_download",
                    "description": "Download a file from AWS S3 bucket",
                    "parameters": {
                        "bucket": "string (S3 bucket name)",
                        "key": "string (object key/path)"
                    }
                },
                {
                    "name": "lambda_invoke",
                    "description": "Invoke an AWS Lambda function",
                    "parameters": {
                        "function_name": "string (Lambda function name or ARN)",
                        "payload": "object (optional, JSON payload to pass)"
                    }
                },
                {
                    "name": "sqs_send",
                    "description": "Send a message to an AWS SQS queue",
                    "parameters": {
                        "queue_url": "string (SQS queue URL)",
                        "message_body": "string (message content)"
                    }
                },
                {
                    "name": "sns_publish",
                    "description": "Publish a message to an AWS SNS topic",
                    "parameters": {
                        "topic_arn": "string (SNS topic ARN)",
                        "message": "string (message content)"
                    }
                },
                {
                    "name": "azure_blob_upload",
                    "description": "Upload content to Azure Blob Storage",
                    "parameters": {
                        "container": "string (container name)",
                        "blob_name": "string (blob name)",
                        "content": "string (file content)"
                    }
                },
                {
                    "name": "azure_blob_download",
                    "description": "Download content from Azure Blob Storage",
                    "parameters": {
                        "container": "string (container name)",
                        "blob_name": "string (blob name)"
                    }
                },
                {
                    "name": "azure_function_invoke",
                    "description": "Invoke an Azure Function",
                    "parameters": {
                        "function_url": "string (Azure Function HTTP URL)",
                        "payload": "object (optional, JSON payload)"
                    }
                },
                {
                    "name": "gcs_upload",
                    "description": "Upload content to Google Cloud Storage",
                    "parameters": {
                        "bucket": "string (GCS bucket name)",
                        "object_name": "string (object name)",
                        "content": "string (file content)"
                    }
                },
                {
                    "name": "gcs_download",
                    "description": "Download content from Google Cloud Storage",
                    "parameters": {
                        "bucket": "string (GCS bucket name)",
                        "object_name": "string (object name)"
                    }
                },
                {
                    "name": "cloud_function_invoke",
                    "description": "Invoke a Google Cloud Function",
                    "parameters": {
                        "function_url": "string (Cloud Function HTTP URL)",
                        "payload": "object (optional, JSON payload)"
                    }
                },
                {
                    "name": "pubsub_publish",
                    "description": "Publish a message to Google Cloud Pub/Sub",
                    "parameters": {
                        "project_id": "string (GCP project ID)",
                        "topic": "string (Pub/Sub topic name)",
                        "message": "string (message content)"
                    }
                },

                # --- Low-Intent Fallbacks ---
                {
                    "name": "call_integration",
                    "description": "GENERIC FALLBACK: Execute any action on any connected integration",
                    "parameters": {
                        "service": "string",
                        "action": "string",
                        "params": "dict"
                    }
                },
                {
                    "name": "list_integrations", 
                    "description": "List all 46+ available native integrations and Activepieces catalog",
                    "parameters": {}
                },
                # --- Computer Use (Phase 28) ---
                {
                    "name": "browser_navigate",
                    "description": "Navigate a virtual browser to a specific URL",
                    "parameters": {"url": "string"}
                },
                {
                    "name": "browser_click",
                    "description": "Click an element in the virtual browser",
                    "parameters": {"selector": "string", "x": "number (optional)", "y": "number (optional)"}
                },
                {
                    "name": "browser_type",
                    "description": "Type text into a focused element in the virtual browser",
                    "parameters": {"text": "string", "selector": "string (optional)"}
                },
                {
                    "name": "browser_screenshot",
                    "description": "Capture a screenshot of the current virtual browser state",
                    "parameters": {}
                },
                {
                    "name": "run_local_terminal",
                    "description": "Execute a command on the user's LOCAL machine via Atom Satellite. Use this to run shell commands, scripts, or manage local files.",
                    "parameters": {
                        "command": "string",
                        "cwd": "string (optional)",
                        "wait_for_output": "boolean (optional, default true)"
                    }
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

    async def search_tools(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for tools based on a query.
        Returns a list of matching tools (name, description).
        """
        all_tools = await self.get_all_tools()
        query = query.lower()
        
        matches = []
        for tool in all_tools:
            name = tool.get("name", "").lower()
            desc = tool.get("description", "").lower()
            
            # Simple keyword matching for now
            if query in name or query in desc:
                matches.append({
                    "name": tool["name"],
                    "description": tool["description"]
                })
        
        # Sort by relevance (exact match first)
        matches.sort(key=lambda x: 0 if query in x["name"].lower() else 1)
        
        return matches[:limit]

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any:
        """Executes a tool by name, dynamically resolving the server_id."""
        for server_id in ["google-search", "local-tools"]:
            tools = await self.get_server_tools(server_id)
            if any(t["name"] == tool_name for t in tools):
                if server_id == "google-search":
                    # ... (existing google logic) ...
                    # Re-implementing simplified logic just for the patch context if needed, 
                    # but since we are inside call_tool, we just need to add the elif block for local-tools
                    pass 

                if tool_name == "run_local_terminal":
                    from core.satellite_service import SatelliteService, SatelliteNotConnectedError
                    
                    # Get tenant_id from context/auth (Assuming single tenant for now or passed in context)
                    # For now, broadcast or pick first active?
                    # The service handles specific tenant routing if we pass it.
                    # We need the user's tenant_id which might be in context.
                    # If context is missing, we might fail.
                    
                    # Simplification: The SatelliteService needs a tenant_id to route to.
                    # We'll assume the context has 'user' or 'tenant_id'.
                    tenant_id = context.get('tenant_id') if context else 'default'
                    
                    logger.info(f"Executing local terminal command for tenant {tenant_id}: {arguments.get('command')}")
                    service = SatelliteService()
                    return await service.execute_command(
                        tenant_id=tenant_id,
                        command=arguments.get('command'),
                        cwd=arguments.get('cwd'),
                        wait_for_output=arguments.get('wait_for_output', True)
                    )
            tools = await self.get_server_tools(server_id)
            if any(t["name"] == tool_name for t in tools):
                return await self.execute_tool(server_id, tool_name, arguments, context)
        
        # 2. Look in dynamic MCP servers
        for server_id, server_info in self.active_servers.items():
            if any(t["name"] == tool_name for t in server_info.get("tools", [])):
                return await self.execute_tool(server_id, tool_name, arguments, context)
        
        return {"error": f"Tool '{tool_name}' not found on any active server."}

    async def _check_hitl_policy(self, tool_name: str, arguments: Dict[str, Any], context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Policy Engine for Human-in-the-Loop.
        Returns a HITL interception result dict if action should be paused, else None.
        """
        risky_tools = ["send_email", "whatsapp_send_message", "whatsapp_send_template", "send_message", "create_invoice"]
        
        if tool_name not in risky_tools:
            return None

        # 1. Gather Context
        agent_id = context.get("agent_id")
        user_id = context.get("user_id")
        workspace_id = context.get("workspace_id", "default")
        
        should_intercept = True
        
        try:
            from core.database import SessionLocal
            from core.models import AgentRegistry, User, Workspace
            
            with SessionLocal() as db:
                # 2. Check Agent Maturity & Overrides
                if agent_id:
                    agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
                    
                    if agent and agent.maturity_level >= 5: # Autonomous
                        # Check Workspace/Tenant Policy
                        workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
                        allow_autonomous = False
                        if workspace and workspace.metadata_json:
                            # Replicating logic using Workspace as "Tenant" proxy
                            allow_autonomous = workspace.metadata_json.get("governance", {}).get("allow_autonomous_external", False)
                        
                        # Check User Preference Override (Force HITL)
                        user_force_hitl = False
                        if user_id:
                            user = db.query(User).filter(User.id == user_id).first()
                            if user and user.preferences:
                                user_force_hitl = user.preferences.get("force_agent_approval", False)
                        
                        if allow_autonomous and not user_force_hitl:
                            should_intercept = False
                            logger.info(f"HITL Bypass: Agent {agent_id} is Autonomous and allowed by policy.")

        except Exception as e:
            logger.error(f"HITL Policy Check Failed: {e}")
            # Fail safe: intercept if error
            should_intercept = True

        if should_intercept:
            from core.intervention_service import intervention_service
            
            reason = f"Action {tool_name} requires approval (Maturity/Policy check)"
            return await intervention_service.request_intervention(
                workspace_id=workspace_id,
                action_type=tool_name,
                platform="hitl_policy",
                params=arguments,
                reason=reason,
                agent_id=agent_id,
                user_id=user_id
            )
        
        return None

    async def execute_tool(self, server_id: str, tool_name: str, arguments: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any:
        """Executes a tool on a specific MCP server."""
        # Phase 41: Helper to check cloud access
        async def _check_cloud_access() -> bool:
            workspace_id = "default"
            try:
                from core.database import SessionLocal
                from core.models import Workspace
                with SessionLocal() as db:
                    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
                    if not workspace: return False
                    # Use Workspace Plan Tier directly (assuming Tenant model is deprecated/missing in upstream)
                    # Mapping generic plan names to PlanType if needed or just string match
                    return workspace.plan_tier == "enterprise" 
            except Exception as e:
                logger.warning(f"Cloud access check failed: {e}")
                return False

        logger.info(f"Executing MCP tool {tool_name} on server {server_id} with args: {arguments}")
        if context is None:
            context = {}
            
        # HITL Policy Enforcement
        hitl_result = await self._check_hitl_policy(tool_name, arguments, context)
        if hitl_result:
             logger.info(f"Tool execution intercepted by HITL Policy: {tool_name}")
             return hitl_result
        
        if server_id == "google-search" or tool_name == "web_search":
            return await self.web_search(arguments.get("query", ""))
            
        # Local Internal Tools
        if server_id == "local-tools":
            workspace_id = "default"
            
            if tool_name == "finance_close_check":
                from accounting.close_agent import CloseChecklistAgent
                from core.database import SessionLocal
                
                with SessionLocal() as db:
                    agent = CloseChecklistAgent(db)
                    # Use a default workspace or passed one
                    workspace_id = "default"
                    period = arguments.get("period", datetime.now().strftime("%Y-%m"))
                    return await agent.run_close_check(workspace_id, period)

            elif tool_name == "b2b_extract_po":
                from ecommerce.b2b_procurement_service import B2BProcurementService
                from core.database import SessionLocal
                with SessionLocal() as db:
                    service = B2BProcurementService(db)
                    return await service.extract_po_from_text(arguments.get("text", ""))

            elif tool_name == "b2b_create_draft_order":
                from ecommerce.b2b_procurement_service import B2BProcurementService
                from core.database import SessionLocal
                with SessionLocal() as db:
                    service = B2BProcurementService(db)
                    return await service.create_draft_order_from_po(
                        workspace_id="default",
                        customer_email=arguments.get("customer_email"),
                        po_data=arguments.get("po_data")
                    )

            elif tool_name == "b2b_push_to_integrations":
                from ecommerce.b2b_data_push_service import B2BDataPushService
                from core.database import SessionLocal
                with SessionLocal() as db:
                    service = B2BDataPushService(db)
                    return await service.push_draft_order(arguments.get("order_id"))
                    

            elif tool_name == "request_human_intervention":
                from core.intervention_service import intervention_service
                action = arguments.get("action")
                reason = arguments.get("reason")
                params = arguments.get("params") or {}
                workspace_id = "default"
                
                logger.warning(f"Agent requested HUMAN INTERVENTION: {action} due to {reason}")
                
                result = await intervention_service.request_intervention(
                    workspace_id=workspace_id,
                    action_type=action,
                    platform="user", # Explicit agent request
                    params=params,
                    reason=reason
                )
                return result

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

            elif tool_name == "canvas_tool":
                from core.websockets import get_connection_manager
                manager = get_connection_manager()
                
                # Broadcast event to workspace channel
                # Internalize "default" channel
                workspace_id = "default"
                channel = "workspace:default"
                
                event_payload = {
                    "action": arguments.get("action"),
                    "component": arguments.get("component"),
                    "data": arguments.get("data"),
                    "title": arguments.get("title"),
                    "agent_id": context.get("agent_id", "atom")
                }
                
                await manager.broadcast_event(channel, "canvas:update", event_payload)
                return "Canvas update event sent to user dashboard."
            elif tool_name == "reconcile_inventory":
                from operations.automations.inventory_reconcile import InventoryReconciliationWorkflow
                agent = InventoryReconciliationWorkflow()
                return await agent.reconcile_inventory(
                    "default"
                )
            
            # --- Communication Hub Tools ---
            elif tool_name == "analyze_message":
                from core.collaboration_hub_service import get_collaboration_hub_service
                from core.database import SessionLocal
                with SessionLocal() as db:
                    service = get_collaboration_hub_service(db)
                    # For now we just return a success message as the agent's "Thought" process 
                    # usually does the actual analysis. But we can store it.
                    # In this flow, the agent 'thinks' then calls 'update_ai_analysis' via tool.
                    # Wait, our prompt said "analyze_message". 
                    # Let's map this to update_ai_analysis for persistence.
                    return service.update_ai_analysis(
                        arguments.get("message_id"), 
                        arguments.get("analysis", {}) # Agent passes analysis object
                    )

            elif tool_name == "draft_response":
                from core.collaboration_hub_service import get_collaboration_hub_service
                from core.database import SessionLocal
                with SessionLocal() as db:
                    service = get_collaboration_hub_service(db)
                    return service.save_draft_response(
                        arguments.get("message_id"),
                        arguments.get("content"),
                        arguments.get("confidence", 0.8)
                    )

            elif tool_name == "approve_draft":
                from core.collaboration_hub_service import get_collaboration_hub_service
                from core.database import SessionLocal
                with SessionLocal() as db:
                    service = get_collaboration_hub_service(db)
                    return await service.approve_draft(
                        arguments.get("message_id"),
                        arguments.get("edited_content")
                    )

            elif tool_name == "ingest_message_attachment":
                # ... existing implementation ...
                return f"Successfully ingested attachment '{file_name}'. Extracted {edges} knowledge edges. GraphRAG: {graphrag.get('entities', 0)} entities, {graphrag.get('relationships', 0)} relationships."

            elif tool_name.startswith("shopify_"):
                from integrations.shopify_service import ShopifyService
                from core.database import SessionLocal
                from ecommerce.models import EcommerceStore
                
                # Helper to get shop credentials
                def get_shop_creds(ctx_workspace_id):
                    with SessionLocal() as db:
                        store = db.query(EcommerceStore).filter(
                            EcommerceStore.workspace_id == ctx_workspace_id
                        ).first()
                        if not store:
                            return None, None
                        return store.access_token, store.shop_domain

                ws_id = context.get("workspace_id", "default") if context else "default"
                token, shop = get_shop_creds(ws_id)
                
                if not token:
                    return "No Shopify store connected to this workspace."
                    
                service = ShopifyService()
                
                if tool_name == "shopify_create_product":
                    # Simple product creation wrapper
                    # Note: Ideally this would be extended in ShopifyService, simulating here for now
                    # In a real scenario, we'd add create_product to ShopifyService
                    url = f"{service._get_base_url(shop)}/products.json"
                    headers = service._get_headers(token)
                    payload = {"product": arguments}
                    async with httpx.AsyncClient() as client:
                        resp = await client.post(url, headers=headers, json=payload)
                        if resp.status_code == 201:
                            return f"Product created successfully: {resp.json()['product']['id']}"
                        return f"Failed to create product: {resp.text}"

                elif tool_name == "shopify_update_inventory":
                     # Assuming set availability for simplicity
                     url = f"{service._get_base_url(shop)}/inventory_levels/set.json"
                     headers = service._get_headers(token)
                     payload = {
                         "inventory_item_id": arguments.get("inventory_item_id"),
                         "location_id": arguments.get("location_id"),
                         "available": arguments.get("available")
                     }
                     async with httpx.AsyncClient() as client:
                        resp = await client.post(url, headers=headers, json=payload)
                        if resp.status_code == 200:
                            return "Inventory updated successfully."
                        return f"Failed to update inventory: {resp.text}"

                elif tool_name == "shopify_get_orders":
                    limit = arguments.get("limit", 10)
                    orders = await service.get_orders(token, shop, limit=limit)
                    # Summary
                    summary = [f"Order #{o['order_number']}: {o['total_price']} {o['currency']} ({o.get('financial_status')})" for o in orders]
                    return "\n".join(summary) if summary else "No orders found."

            elif tool_name == "reconcile_payroll":
                from finance.automations.payroll_guardian import PayrollReconciliationWorkflow
                agent = PayrollReconciliationWorkflow()
                return await agent.reconcile_payroll(
                    period=arguments.get("period", "")
                )
            
            # --- Specialty Agent & Workflow Tools ---
            elif tool_name == "list_agents":
                from core.atom_meta_agent import SpecialtyAgentTemplate
                from core.models import AgentRegistry
                from core.database import SessionLocal
                
                results = {"templates": SpecialtyAgentTemplate.TEMPLATES, "registered": []}
                try:
                    with SessionLocal() as db:
                        agents = db.query(AgentRegistry).all()
                        results["registered"] = [
                            {"id": a.id, "name": a.name, "description": a.description, "category": a.category} 
                            for a in agents
                        ]
                except Exception as e:
                    logger.error(f"Failed to fetch registered agents: {e}")
                return results

            elif tool_name == "bridge_agent_delegate":
                from integrations.universal_webhook_bridge import universal_webhook_bridge
                
                target_agent = arguments.get("target_agent")
                message = arguments.get("message")
                
                if not target_agent or not message:
                    return {"error": "target_agent and message are required"}
                
                # Create a platform="agent" message
                # The bridge will handle fuzzy lookup of target_agent name to ID
                payload = {
                    "agent_id": context.get("agent_id", "atom_main"),
                    "target_id": target_agent,
                    "message": message
                }
                
                result = await universal_webhook_bridge.process_incoming_message("agent", payload)
                return result

            elif tool_name == "spawn_agent":
                from core.atom_meta_agent import get_atom_agent
                atom = get_atom_agent(context.get("workspace_id", "default"))
                return await atom.spawn_agent(
                    template_name=arguments.get("template"),
                    persist=arguments.get("persist", False)
                )

            elif tool_name == "list_workflows":
                try:
                    import json
                    workflows = []
                    storage_dir = "workflow_states"
                    if not os.path.exists(storage_dir): return []
                    for filename in os.listdir(storage_dir):
                        if filename.endswith(".json"):
                            try:
                                with open(os.path.join(storage_dir, filename), 'r') as f:
                                    data = json.load(f)
                                    workflows.append({
                                        "id": data.get("workflow_id"),
                                        "name": data.get("name"),
                                        "description": data.get("description"),
                                        "description": data.get("description"),
                                        "trigger": data.get("trigger")
                                    })
                            except: pass
                    return workflows
                except:
                    return []
                    
            # --- Computer Use Execution (Dual Mode: Desktop Bridge vs Cloud Headless) ---
            elif tool_name == "browser_navigate":
                mode = context.get("computer_use_mode", "desktop")
                workspace_id = context.get("workspace_id", "default")
                
                # Phase 41: Enforce Tier Restriction
                if mode == "cloud":
                    if not await _check_cloud_access(workspace_id):
                        return "Error: Headless Cloud Browser is restricted to Enterprise tiers. Defaulting to local Desktop Bridge. Please connect your Desktop App."
                
                url = arguments.get("url")
                
                if mode == "cloud":
                    from core.cloud_browser_service import cloud_browser
                    # Use session_id from context or agent_id
                    session_id = context.get("agent_id", "default_session")
                    return await cloud_browser.navigate(session_id, url, context)
                else:
                    # Default: Desktop Bridge
                    from core.notification_manager import notification_manager
                    workspace_id = context.get("workspace_id", "default")
                    
                    payload = {
                        "type": "computer_use",
                        "action": "navigate",
                        "url": url
                    }
                    
                    sent = await notification_manager.send_to_desktop(payload, workspace_id)
                    if sent:
                        return f"Command sent to Desktop App: Navigate to {url}"
                    else:
                        logger.warning(f"No desktop client connected for {workspace_id}. Using simulation.")
                        return f"[SIMULATION] Navigated to {url}. (Connect Desktop App for real execution)"
                
            elif tool_name == "browser_click":
                mode = context.get("computer_use_mode", "desktop")
                workspace_id = context.get("workspace_id", "default")
                
                # Phase 41: Enforce Tier Restriction
                if mode == "cloud":
                    if not await _check_cloud_access(workspace_id):
                        return "Error: Headless Cloud Browser is restricted to Enterprise tiers. Defaulting to local Desktop Bridge."
                
                selector = arguments.get("selector")
                
                if mode == "cloud":
                    from core.cloud_browser_service import cloud_browser
                    session_id = context.get("agent_id", "default_session")
                    return await cloud_browser.click(session_id, selector, context)
                else:
                    from core.notification_manager import notification_manager
                    workspace_id = context.get("workspace_id", "default")
                    
                    payload = {
                        "type": "computer_use",
                        "action": "click",
                        "selector": selector,
                        "x": arguments.get("x"),
                        "y": arguments.get("y")
                    }
                    
                    sent = await notification_manager.send_to_desktop(payload, workspace_id)
                    if sent:
                        return f"Command sent to Desktop App: Click {selector}"
                    else:
                        return f"[SIMULATION] Clicked {selector}. (Connect Desktop App for real execution)"
                
            elif tool_name == "browser_type":
                mode = context.get("computer_use_mode", "desktop")
                workspace_id = context.get("workspace_id", "default")
                
                # Phase 41: Enforce Tier Restriction
                if mode == "cloud":
                    if not await _check_cloud_access(workspace_id):
                        return "Error: Headless Cloud Browser is restricted to Enterprise tiers. Defaulting to local Desktop Bridge."
                
                text = arguments.get("text")
                selector = arguments.get("selector")
                
                if mode == "cloud":
                    from core.cloud_browser_service import cloud_browser
                    session_id = context.get("agent_id", "default_session")
                    return await cloud_browser.type_text(session_id, selector, text, context)
                else:
                    from core.notification_manager import notification_manager
                    workspace_id = context.get("workspace_id", "default")
                    
                    payload = {
                        "type": "computer_use",
                        "action": "type",
                        "text": text,
                        "selector": selector
                    }
                    
                    sent = await notification_manager.send_to_desktop(payload, workspace_id)
                    if sent:
                         return f"Command sent to Desktop App: Type '{text}'"
                    else:
                         return f"[SIMULATION] Typed '{text}'. (Connect Desktop App for real execution)"
                
            elif tool_name == "browser_screenshot":
                mode = context.get("computer_use_mode", "desktop")
                workspace_id = context.get("workspace_id", "default")
                
                if mode == "cloud":
                    if not await _check_cloud_access(workspace_id):
                        return "Error: Cloud screenshot is restricted to Enterprise tiers."
                    from core.cloud_browser_service import cloud_browser
                    session_id = context.get("agent_id", "default_session")
                    return await cloud_browser.screenshot(session_id, context)
                else:
                    from core.notification_manager import notification_manager
                    workspace_id = context.get("workspace_id", "default")
                    
                    payload = {
                        "type": "computer_use",
                        "action": "screenshot"
                    }
                    
                    sent = await notification_manager.send_to_desktop(payload, workspace_id)
                    if sent:
                         return "Screenshot requested from Desktop App. Check 'My Files' shortly."
                    else:
                         return "[SIMULATION] Screenshot captured (mock). (Connect Desktop App for real execution)"

            elif tool_name == "browser_new_tab":
                mode = context.get("computer_use_mode", "desktop")
                workspace_id = context.get("workspace_id", "default")
                url = arguments.get("url")
                if mode == "cloud":
                    if not await _check_cloud_access(workspace_id):
                        return "Error: Headless Cloud Browser is restricted to Enterprise tiers."
                    from core.cloud_browser_service import cloud_browser
                    session_id = context.get("agent_id", "default_session")
                    return await cloud_browser.new_tab(session_id, url, context)
                return "Error: browser_new_tab is only available in cloud mode."

            elif tool_name == "browser_switch_tab":
                mode = context.get("computer_use_mode", "desktop")
                workspace_id = context.get("workspace_id", "default")
                index = arguments.get("index", 0)
                if mode == "cloud":
                    if not await _check_cloud_access(workspace_id):
                        return "Error: Headless Cloud Browser is restricted to Enterprise tiers."
                    from core.cloud_browser_service import cloud_browser
                    session_id = context.get("agent_id", "default_session")
                    return await cloud_browser.switch_tab(session_id, index)
                return "Error: browser_switch_tab is only available in cloud mode."

            elif tool_name == "browser_click_coords":
                mode = context.get("computer_use_mode", "desktop")
                workspace_id = context.get("workspace_id", "default")
                x, y = arguments.get("x"), arguments.get("y")
                
                # Phase 41: Enforce Tier Restriction
                if mode == "cloud":
                    if not await _check_cloud_access(workspace_id):
                        return "Error: Headless Cloud Browser is restricted to Enterprise tiers."
                    from core.cloud_browser_service import cloud_browser
                    session_id = context.get("agent_id", "default_session")
                    return await cloud_browser.click_coords(session_id, int(x), int(y), context)
                return "Error: browser_click_coords is only available in cloud mode."

            elif tool_name == "list_browser_tabs":
                 mode = context.get("computer_use_mode", "desktop")
                 workspace_id = context.get("workspace_id", "default")
                 if mode == "cloud":
                     if not await _check_cloud_access(workspace_id):
                         return "Error: Headless Cloud Browser is restricted to Enterprise tiers."
                     from core.cloud_browser_service import cloud_browser
                     session_id = context.get("agent_id", "default_session")
                     return await cloud_browser.list_tabs(session_id)
                 return "Error: list_browser_tabs is only available in cloud mode."

            elif tool_name == "browser_save_session":
                 mode = context.get("computer_use_mode", "desktop")
                 workspace_id = context.get("workspace_id", "default")
                 if mode == "cloud":
                     if not await _check_cloud_access(workspace_id):
                         return "Error: Headless Cloud Browser is restricted to Enterprise tiers."
                     from core.cloud_browser_service import cloud_browser
                     session_id = context.get("agent_id", "default_session")
                     return await cloud_browser.save_session(session_id)
                 return "Error: browser_save_session is only available in cloud mode."

            elif tool_name == "browser_set_proxy":
                 mode = context.get("computer_use_mode", "desktop")
                 workspace_id = context.get("workspace_id", "default")
                 server = arguments.get("server")
                 if mode == "cloud":
                     if not await _check_cloud_access(workspace_id):
                         return "Error: Headless Cloud Browser is restricted to Enterprise tiers."
                     from core.cloud_browser_service import cloud_browser
                     session_id = context.get("agent_id", "default_session")
                     return await cloud_browser.set_proxy(session_id, server, arguments.get("username"), arguments.get("password"))
                 return "Error: browser_set_proxy is only available in cloud mode."

            elif tool_name == "browser_monitor":
                 mode = context.get("computer_use_mode", "desktop")
                 active = arguments.get("active", True)
                 workspace_id = context.get("workspace_id", "default")
                 if mode == "cloud":
                     if not await _check_cloud_access(workspace_id):
                         return "Error: Headless Cloud Browser is restricted to Enterprise tiers."
                     from core.cloud_browser_service import cloud_browser
                     session_id = context.get("agent_id", "default_session")
                     if active:
                         return await cloud_browser.start_monitoring(session_id, workspace_id)
                     else:
                         return await cloud_browser.stop_monitoring(session_id)
                 return "Error: browser_monitor is only available in cloud mode."

            elif tool_name == "browser_wait_for_selector":
                 mode = context.get("computer_use_mode", "desktop")
                 workspace_id = context.get("workspace_id", "default")
                 selector = arguments.get("selector")
                 timeout = arguments.get("timeout", 5000)
                 if mode == "cloud":
                     if not await _check_cloud_access(workspace_id):
                         return "Error: Headless Cloud Browser is restricted to Enterprise tiers."
                     from core.cloud_browser_service import cloud_browser
                     session_id = context.get("agent_id", "default_session")
                     return await cloud_browser.wait_for_selector(session_id, selector, timeout, context)
                 return "Error: browser_wait_for_selector is only available in cloud mode."

            elif tool_name == "browser_extract_content":
                 mode = context.get("computer_use_mode", "desktop")
                 workspace_id = context.get("workspace_id", "default")
                 selector = arguments.get("selector")
                 extract_mode = arguments.get("mode", "text")
                 if mode == "cloud":
                     if not await _check_cloud_access(workspace_id):
                         return "Error: Headless Cloud Browser is restricted to Enterprise tiers."
                     from core.cloud_browser_service import cloud_browser
                     session_id = context.get("agent_id", "default_session")
                     return await cloud_browser.extract_content(session_id, selector, extract_mode, context)
                 return "Error: browser_extract_content is only available in cloud mode."

            elif tool_name == "browser_upload_file":
                 mode = context.get("computer_use_mode", "desktop")
                 workspace_id = context.get("workspace_id", "default")
                 selector = arguments.get("selector")
                 file_path = arguments.get("file_path")
                 if mode == "cloud":
                     if not await _check_cloud_access(workspace_id):
                         return "Error: Headless Cloud Browser is restricted to Enterprise tiers."
                     from core.cloud_browser_service import cloud_browser
                     session_id = context.get("agent_id", "default_session")
                     return await cloud_browser.upload_file(session_id, selector, file_path, context)
                 return "Error: browser_upload_file is only available in cloud mode."

            elif tool_name == "browser_download_file":
                 mode = context.get("computer_use_mode", "desktop")
                 workspace_id = context.get("workspace_id", "default")
                 url = arguments.get("url")
                 filename = arguments.get("filename")
                 if mode == "cloud":
                     if not await _check_cloud_access(workspace_id):
                         return "Error: Headless Cloud Browser is restricted to Enterprise tiers."
                     from core.cloud_browser_service import cloud_browser
                     session_id = context.get("agent_id", "default_session")
                     return await cloud_browser.download_file(session_id, url, filename, context)
                 return "Error: browser_download_file is only available in cloud mode."

            elif tool_name == "trigger_workflow":
                from advanced_workflow_orchestrator import get_orchestrator
                orchestrator = get_orchestrator()
                wf_id = arguments.get("workflow_id")
                input_data = arguments.get("input_data", {})
                if not wf_id: return {"error": "workflow_id is required"}
                context = await orchestrator.execute_workflow(wf_id, input_data)
                return {
                    "status": context.status.value,
                    "execution_id": context.workflow_id,
                    "result": context.results,
                    "error": context.error_message
                }

            # --- CRM & Sales ---
            elif tool_name == "search_contacts":
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                platform = arguments.get("platform")
                query = arguments.get("query")
                if platform: return await service.search(platform, query, context=context)
                else:
                    results = {}
                    for p in ["salesforce", "hubspot", "zoho_crm", "intercom"]:
                        try: results[p] = await service.search(p, query, context=context)
                        except: continue
                    return results

            elif tool_name == "create_crm_lead":
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                platform = arguments.get("platform")
                if not platform: return {"error": "platform is required"}
                params = {"first_name": arguments.get("first_name"), "last_name": arguments.get("last_name"), "email": arguments.get("email"), "company": arguments.get("company")}
                return await service.execute(platform, "create", {"data": params}, context=context)

            elif tool_name == "get_sales_pipeline":
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                user_id = context.get("user_id", "default_user")
                platform = arguments.get("platform", "").lower()
                pipeline = []
                # Salesforce
                if not platform or platform == "salesforce":
                    try:
                        res = await service.execute("salesforce", "list", {"entity": "opportunity"}, context={"user_id": user_id})
                        if res.get("status") == "success":
                            for op in res.get("data", []):
                                pipeline.append({"deal": op.get("Name"), "value": op.get("Amount", 0), "status": op.get("StageName"), "platform": "salesforce"})
                    except: pass
                # HubSpot
                if not platform or platform == "hubspot":
                    try:
                        res = await service.execute("hubspot", "list", {"entity": "deal"}, context={"user_id": user_id})
                        if res.get("status") == "success":
                            for deal in res.get("data", []):
                                props = deal.get("properties", {})
                                pipeline.append({"deal": props.get("dealname"), "value": float(props.get("amount") or 0), "status": props.get("dealstage"), "platform": "hubspot"})
                    except: pass
                return pipeline

            # --- Project Management ---
            elif tool_name == "get_tasks":
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                platform = arguments.get("platform")
                if platform: return await service.execute(platform, "list", arguments, context=context)
                else:
                    results = {}
                    for p in ["jira", "asana", "linear", "monday"]:
                        try: results[p] = await service.execute(p, "list", {}, context=context)
                        except: continue
                    return results

            elif tool_name == "search_tasks":
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                platform = arguments.get("platform")
                query = arguments.get("query")
                if platform: return await service.search(platform, query, context=context)
                else:
                    results = {}
                    for p in ["jira", "asana", "linear", "monday"]:
                        try: results[p] = await service.search(p, query, context=context)
                        except: continue
                    return results

            elif tool_name == "create_task":
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                platform = arguments.get("platform")
                if not platform:
                    from core.connection_service import ConnectionService
                    conn_service = ConnectionService()
                    connections = await conn_service.list_connections(user_id=context.get("user_id"))
                    pm_pieces = ["jira", "asana", "linear", "monday", "trello"]
                    platform = next((c.piece_name for c in connections if c.piece_name in pm_pieces), None)
                if not platform: return {"error": "No project management platform connected."}
                return await service.execute(platform, "create", arguments, context=context)

            elif tool_name == "list_projects":
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                platform = arguments.get("platform")
                if not platform: return {"error": "platform is required"}
                return await service.execute(platform, "list_projects", arguments, context=context)

            # --- Communication & Collaboration ---
            elif tool_name == "send_message":
                from core.connection_service import ConnectionService
                user_id = context.get("user_id", "default_user")
                platform = arguments.get("platform")
                target = arguments.get("target")
                message = arguments.get("message")
                conn_service = ConnectionService()
                connections = await conn_service.list_connections(user_id=user_id)
                active_conn = next((c for c in connections if c.piece_name == platform), None) if platform else next((c for c in connections if c.piece_name in ["slack", "teams", "discord"]), None)
                if not active_conn: return {"error": "No communication platform connected."}
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                return await service.execute(active_conn.piece_name, "send_message", {"target": target, "message": message}, context=context)

            elif tool_name == "post_channel_message":
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                platform = arguments.get("platform")
                channel = arguments.get("channel")
                message = arguments.get("message")
                if not platform: return {"error": "platform is required"}
                return await service.execute(platform, "send_message", {"target": channel, "message": message}, context=context)

            elif tool_name == "send_email":
                 from integrations.universal_integration_service import UniversalIntegrationService
                 service = UniversalIntegrationService()
                 platform = arguments.get("platform") or "gmail"
                 return await service.execute(platform, "send_message", arguments, context=context)

            elif tool_name == "search_emails":
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                platform = arguments.get("platform")
                query = arguments.get("query")
                if platform: return await service.execute(platform, "list_messages", {"query": query}, context=context)
                else:
                    return {"gmail": await service.execute("gmail", "list_messages", {"query": query}, context=context)}

            elif tool_name == "unified_communication_search":
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                query = arguments.get("query")
                platforms = arguments.get("platforms") or ["slack", "google_chat", "telegram", "whatsapp", "gmail"]
                results = {}
                for p in platforms:
                    try: results[p] = await service.search(p, query, context=context)
                    except: continue
                return results

            elif tool_name == "list_calendar_events":
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                platform = arguments.get("platform") or "google_calendar"
                return await service.execute(platform, "list", arguments, context=context)

            elif tool_name == "create_calendar_event":
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                platform = arguments.get("platform") or "google_calendar"
                return await service.execute(platform, "create", {"data": arguments}, context=context)

            # --- Storage & Knowledge ---
            elif tool_name == "search_files":
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                platform = arguments.get("platform")
                query = arguments.get("query")
                if platform: return await service.search(platform, query, context=context)
                else:
                    results = {}
                    for p in ["google_drive", "dropbox", "notion"]:
                        try: results[p] = await service.search(p, query, context=context)
                        except: continue
                    return results

            elif tool_name == "list_files":
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                platform = arguments.get("platform")
                if not platform: return {"error": "platform is required"}
                return await service.execute(platform, "list", arguments, context=context)

            elif tool_name == "create_folder":
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                platform = arguments.get("platform")
                if not platform: return {"error": "platform is required"}
                return await service.execute(platform, "create_folder", arguments, context=context)

            elif tool_name == "unified_knowledge_search":
                from ai.data_intelligence import engine
                query = arguments.get("query", "").lower()
                results = []
                for entity in engine.entity_registry.values():
                    if query and query not in entity.canonical_name.lower(): continue
                    results.append({
                        "id": entity.entity_id, "name": entity.canonical_name, "type": entity.entity_type.value,
                        "platform": [p.value for p in entity.source_platforms][0] if entity.source_platforms else "unknown",
                        "modified_at": entity.updated_at.isoformat()
                    })
                return results

            elif tool_name == "save_business_fact":
                from core.agent_world_model import WorldModelService, BusinessFact
                import uuid
                
                wm = WorldModelService(context.get("workspace_id", "default"))
                fact_obj = BusinessFact(
                    id=str(uuid.uuid4()),
                    fact=arguments.get("fact"),
                    citations=arguments.get("citations", []),
                    reason=arguments.get("reason"),
                    source_agent_id=context.get("agent_id", "unknown"),
                    created_at=datetime.now(),
                    last_verified=datetime.now(),
                    verification_status="verified", # Implicitly verified upon creation by agent
                    metadata={"source": arguments.get("source")}
                )
                success = await wm.record_business_fact(fact_obj)
                return f"Fact saved: {fact_obj.fact}" if success else "Failed to save fact."

            elif tool_name == "verify_citation":
                path = arguments.get("path")
                if not path: return "Error: Path required"
                
                # Security check (Phase 41): Don't allow agents to read arbitrary system files
                # Simple check: must be in workspace or whitelisted
                if not (path.startswith("/app") or path.startswith("/Users") or path.startswith("/tmp")): 
                    return "Error: Access denied to system paths."
                
                # Check existence
                import os
                if os.path.exists(path):
                    try:
                        # Read first 500 chars to confirm context
                        with open(path, 'r') as f:
                            snippet = f.read(500)
                        return f"Verified: '{path}' exists.\nSnippet: {snippet}..."
                    except Exception as e:
                         return f"Verified existence, but failed to read: {e}"
                else:
                    return f"Error: Citation '{path}' NOT found."

            # --- Support & Customer Success ---
            elif tool_name == "search_tickets":
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                platform = arguments.get("platform")
                query = arguments.get("query")
                if platform: return await service.search(platform, query, context=context)
                else:
                    results = {}
                    for p in ["zendesk", "freshdesk", "intercom"]:
                        try: results[p] = await service.search(p, query, context=context)
                        except: continue
                    return results

            elif tool_name == "create_ticket":
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                platform = arguments.get("platform")
                if not platform: return {"error": "platform is required"}
                return await service.execute(platform, "create", arguments, context=context)

            # --- Development & Design ---
            elif tool_name == "search_repositories":
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                platform = arguments.get("platform")
                query = arguments.get("query")
                if platform: return await service.search(platform, query, context=context)
                else:
                    results = {}
                    for p in ["github", "gitlab"]:
                        try: results[p] = await service.search(p, query, context=context)
                        except: continue
                    return results

            elif tool_name == "search_designs":
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                return await service.search("figma", arguments.get("query"), context=context)

            # --- Finance & Accounting ---
            elif tool_name == "query_financial_metrics":
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                return await service.execute("stripe", "get_metrics", arguments, context=context)

            elif tool_name == "list_finance_invoices":
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                platform = arguments.get("platform")
                if platform: return await service.execute(platform, "list", {"entity": "invoice"}, context=context)
                else:
                    results = {}
                    for p in ["stripe", "quickbooks", "xero", "zoho_books"]:
                        try: results[p] = await service.execute(p, "list", {"entity": "invoice"}, context=context)
                        except: continue
                    return results

            elif tool_name == "finance_close_check":
                from accounting.close_agent import CloseChecklistAgent
                from core.database import SessionLocal
                with SessionLocal() as db:
                    agent = CloseChecklistAgent(db)
                    return await agent.run_close_check(context.get("workspace_id", "default"), arguments.get("period", datetime.now().strftime("%Y-%m")))

            # --- Specialty Tools ---
            elif tool_name == "get_inventory_levels":
                from core.connection_service import ConnectionService
                user_id = context.get("user_id", "default_user")
                platform = arguments.get("platform", "").lower()
                conn_service = ConnectionService()
                connections = await conn_service.list_connections(user_id=user_id)
                results = []
                if platform == "shopify" or not platform:
                    conn = next((c for c in connections if c.piece_name == "shopify"), None)
                    if conn:
                        from integrations.shopify_service import shopify_service
                        results.extend(await shopify_service.get_inventory_levels(access_token=conn.credentials.get("access_token"), shop=conn.metadata.get("shop_url")))
                if platform == "zoho" or not platform:
                    conn = next((c for c in connections if c.piece_name == "zoho_inventory"), None)
                    if conn:
                        from integrations.zoho_inventory_service import zoho_inventory_service
                        results.extend(await zoho_inventory_service.get_inventory_levels(token=conn.credentials.get("access_token"), organization_id=conn.metadata.get("organization_id")))
                return results

            elif tool_name == "search_dashboards":
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                platform = arguments.get("platform")
                query = arguments.get("query")
                if platform: return await service.search(platform, query, context=context)
                else:
                    results = {}
                    for p in ["tableau", "google_analytics"]:
                        try: results[p] = await service.search(p, query, context=context)
                        except: continue
                    return results

            elif tool_name == "create_zoom_meeting":
                from integrations.zoom_service import zoom_service
                from core.connection_service import ConnectionService
                conn_service = ConnectionService()
                connections = await conn_service.list_connections(user_id=context.get("user_id", "default_user"))
                conn = next((c for c in connections if c.piece_name == "zoom"), None)
                if not conn: return {"error": "Zoom not connected"}
                return await zoom_service.create_meeting(topic=arguments.get("topic", "Meeting"), duration=arguments.get("duration", 60), start_time=arguments.get("start_time"), access_token=conn.credentials.get("access_token"))

            # --- System & Health ---
            elif tool_name == "get_system_health":
                from core.circuit_breaker import circuit_breaker
                from core.analytics_engine import analyzer
                service = arguments.get("service")
                if service:
                    stats = circuit_breaker.get_stats(service)
                    drift = analyzer.analyze_service_drift(service)
                    return {"stats": stats, "drift": drift}
                else:
                    return {
                        "circuit_breaker": circuit_breaker.get_all_stats(),
                        "global_report": analyzer.get_global_performance_report()
                    }

            # --- Utilities ---
            elif tool_name == "generate_pdf_report":
                from fpdf import FPDF
                pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial", size=12)
                for line in arguments.get("content", "").split('\n'): pdf.multi_cell(0, 10, txt=line)
                target_path = os.path.join("/tmp", arguments.get("filename", "report.pdf"))
                pdf.output(target_path)
                return {"status": "success", "file_path": target_path}

            # --- Marketing Tools ---
            elif tool_name == "manage_reviews":
                from core.marketing_agent import MarketingAgent
                agent = MarketingAgent()
                return await agent.manage_google_reviews(workspace_id)
                
            elif tool_name == "request_testimonial":
                from core.marketing_agent import MarketingAgent
                agent = MarketingAgent()
                return await agent.request_testimonial(arguments.get("customer_id"), workspace_id, arguments.get("platform", "email"))
                
            elif tool_name == "analyze_ads_performance":
                from core.marketing_agent import MarketingAgent
                agent = MarketingAgent()
                return await agent.run_ads_check(arguments.get("service"), workspace_id)

            # --- Sales & Lead Intelligence ---
            elif tool_name == "score_lead":
                from core.sales_agent import SalesAgent
                agent = SalesAgent()
                return await agent.score_lead(workspace_id, arguments.get("lead_data", {}))
            
            elif tool_name == "draft_sales_outreach":
                from core.sales_agent import SalesAgent
                agent = SalesAgent()
                return await agent.prepare_outreach(workspace_id, arguments.get("lead_id"), arguments.get("context"))
            
            elif tool_name == "monitor_pipeline_health":
                from core.sales_agent import SalesAgent
                agent = SalesAgent()
                return await agent.audit_pipeline(workspace_id)

            # --- Shipping & Logistics ---
            elif tool_name in ["create_shipment", "get_shipping_rates", "create_shipping_label", "track_shipment", "validate_address"]:
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                platform = arguments.get("platform", "").lower()
                
                # Shipping action mapping
                shipping_actions = {
                    "create_shipment": "create_shipment",
                    "get_shipping_rates": "get_rates",
                    "create_shipping_label": "create_label",
                    "track_shipment": "track",
                    "validate_address": "validate_address"
                }
                action = shipping_actions.get(tool_name, tool_name)
                
                # If no platform specified, try all connected shipping platforms
                if not platform:
                    from core.connection_service import ConnectionService
                    conn_service = ConnectionService()
                    connections = await conn_service.list_connections(user_id=context.get("user_id"))
                    shipping_platforms = ["shippo", "easypost", "ups", "fedex", "purolator", "freightcom", "shipstation"]
                    platform = next((c.piece_name for c in connections if c.piece_name in shipping_platforms), None)
                
                if not platform:
                    return {"error": "No shipping platform connected. Please connect Shippo, EasyPost, UPS, FedEx, or another shipping service."}
                
                return await service.execute(platform, action, arguments, context=context)

            # --- Cloud Providers ---
            elif tool_name in ["s3_upload", "s3_download", "lambda_invoke", "sqs_send", "sns_publish"]:
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                action_map = {
                    "s3_upload": "s3_upload",
                    "s3_download": "s3_download",
                    "lambda_invoke": "lambda_invoke",
                    "sqs_send": "sqs_send",
                    "sns_publish": "sns_publish"
                }
                return await service.execute("aws", action_map[tool_name], arguments, context=context)

            elif tool_name in ["azure_blob_upload", "azure_blob_download", "azure_function_invoke"]:
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                action_map = {
                    "azure_blob_upload": "blob_upload",
                    "azure_blob_download": "blob_download",
                    "azure_function_invoke": "function_invoke"
                }
                return await service.execute("azure", action_map[tool_name], arguments, context=context)

            elif tool_name in ["gcs_upload", "gcs_download", "cloud_function_invoke", "pubsub_publish"]:
                from integrations.universal_integration_service import UniversalIntegrationService
                service = UniversalIntegrationService()
                action_map = {
                    "gcs_upload": "storage_upload",
                    "gcs_download": "storage_download",
                    "cloud_function_invoke": "function_invoke",
                    "pubsub_publish": "pubsub_publish"
                }
                return await service.execute("gcp", action_map[tool_name], arguments, context=context)

            # --- Knowledge & Memory Tools (Phase 18) ---
            elif tool_name == "ingest_knowledge_from_text":
                from core.knowledge_ingestion import get_knowledge_ingestion
                ingestion_manager = get_knowledge_ingestion()
                
                text = arguments.get("text")
                doc_id = arguments.get("doc_id", f"agent_text_{datetime.now().timestamp()}")
                source = arguments.get("source", "agent_provided_text")
                workspace_id = context.get("workspace_id") if context else "default"
                user_id = context.get("user_id") if context else "default_user"
                
                if not text: return {"error": "Text content is required"}
                
                result = await ingestion_manager.process_document(
                    text=text,
                    doc_id=doc_id,
                    source=source,
                    user_id=user_id,
                    workspace_id=workspace_id
                )
                return {"success": True, "stats": result}

            elif tool_name == "ingest_knowledge_from_file":
                from core.docling_processor import get_docling_processor
                from core.knowledge_ingestion import get_knowledge_ingestion
                
                processor = get_docling_processor()
                ingestion_manager = get_knowledge_ingestion()
                
                file_path = arguments.get("file_path")
                file_type = arguments.get("file_type")
                workspace_id = context.get("workspace_id") if context else "default"
                user_id = context.get("user_id") if context else "default_user"
                
                if not file_path: return {"error": "File path is required"}
                if not os.path.exists(file_path): return {"error": f"File not found: {file_path}"}
                
                # 1. Parse file with Docling
                parse_result = await processor.process_document(
                    source=file_path,
                    file_type=file_type,
                    file_name=os.path.basename(file_path)
                )
                
                if not parse_result.get("success"):
                    return {"error": f"File parsing failed: {parse_result.get('error')}"}
                
                # --- Formula Extraction (Phase 19) ---
                formula_stats = []
                ext = os.path.splitext(file_path)[1].lower()
                if ext in [".xlsx", ".xls", ".csv", ".ods"]:
                    try:
                        from core.formula_extractor import get_formula_extractor
                        extractor = get_formula_extractor(workspace_id)
                        extracted_formulas = extractor.extract_from_file(
                            file_path=file_path,
                            user_id=user_id,
                            auto_store=True
                        )
                        formula_stats = [
                            {"name": f["name"], "expression": f["expression"], "domain": f["domain"]}
                            for f in extracted_formulas
                        ]
                        logger.info(f"Extracted {len(formula_stats)} formulas from {file_path}")
                    except Exception as fe:
                        logger.warning(f"Formula extraction failed for {file_path}: {fe}")

                # 2. Extract and store knowledge
                text_content = parse_result.get("content", "")
                if not text_content: return {"error": "No content extracted from file"}
                
                doc_id = f"agent_file_{os.path.basename(file_path)}_{datetime.now().timestamp()}"
                source = f"agent_file:{os.path.basename(file_path)}"
                
                result = await ingestion_manager.process_document(
                    text=text_content,
                    doc_id=doc_id,
                    source=source,
                    user_id=user_id,
                    workspace_id=workspace_id
                )
                
                return {
                    "success": True, 
                    "file_stats": {
                        "pages": parse_result.get("page_count"),
                        "chars": parse_result.get("total_chars"),
                        "tables_found": len(parse_result.get("tables", [])),
                        "formulas_extracted": len(formula_stats)
                    },
                    "extracted_formulas": formula_stats,
                    "knowledge_stats": result
                }

            elif tool_name == "search_formulas":
                from core.formula_memory import get_formula_manager
                manager = get_formula_manager(workspace_id=context.get("workspace_id", "default"))
                
                query = arguments.get("query")
                domain = arguments.get("domain")
                user_id = context.get("user_id", "default_user")
                
                if not query: return {"error": "Search query is required"}
                
                results = manager.search_formulas(
                    query=query,
                    domain=domain,
                    user_id=user_id
                )
                return {"results": results}

            elif tool_name == "query_knowledge_graph":
                from core.knowledge_ingestion import get_knowledge_ingestion
                ingestion_manager = get_knowledge_ingestion()
                
                query = arguments.get("query")
                mode = arguments.get("mode", "auto")
                user_id = context.get("user_id") if context else "default_user"
                
                if not query: return {"error": "Search query is required"}
                
                result = ingestion_manager.query_graphrag(
                    user_id=user_id,
                    query=query,
                    mode=mode
                )
                return result

            # --- Standardized & Granular Integration Tools ---
            elif tool_name in [
                "update_crm_lead", "create_crm_deal", "update_crm_deal", "update_task", 
                "create_invoice", "push_to_integration", "create_support_ticket", 
                "update_support_ticket", "create_ecommerce_order", "upload_file_to_storage",
                "create_storage_folder", "add_marketing_subscriber", "create_record", "update_record"
            ]:
                from integrations.universal_integration_service import universal_integration_service
                
                if tool_name == "update_crm_lead":
                    platform = arguments.get("platform")
                    record_id = arguments.get("id")
                    data = arguments.get("data", {})
                    return await universal_integration_service.execute(platform, "update", {"entity": "lead", "id": record_id, "data": data}, context=context)
                
                elif tool_name == "create_crm_deal":
                    platform = arguments.get("platform")
                    data = arguments.get("data", arguments)
                    return await universal_integration_service.execute(platform, "create", {"entity": "deal", "data": data}, context=context)
                    
                elif tool_name == "update_crm_deal":
                    platform = arguments.get("platform")
                    record_id = arguments.get("id")
                    data = arguments.get("data", {})
                    return await universal_integration_service.execute(platform, "update", {"entity": "deal", "id": record_id, "data": data}, context=context)
                
                elif tool_name == "update_task":
                    platform = arguments.get("platform")
                    record_id = arguments.get("id")
                    data = arguments.get("data", {})
                    return await universal_integration_service.execute(platform, "update", {"id": record_id, "data": data}, context=context)

                elif tool_name == "create_support_ticket":
                    platform = arguments.get("platform")
                    return await universal_integration_service.execute(platform, "create", {"data": arguments}, context=context)
                
                elif tool_name == "update_support_ticket":
                    platform = arguments.get("platform")
                    record_id = arguments.get("id")
                    return await universal_integration_service.execute(platform, "update", {"id": record_id, "data": arguments.get("data", {})}, context=context)
                
                elif tool_name == "create_ecommerce_order":
                    platform = arguments.get("platform")
                    return await universal_integration_service.execute(platform, "create_order", arguments, context=context)
                
                elif tool_name == "upload_file_to_storage":
                    platform = arguments.get("platform")
                    return await universal_integration_service.execute(platform, "upload_file", arguments, context=context)
                
                elif tool_name == "create_storage_folder":
                    platform = arguments.get("platform")
                    return await universal_integration_service.execute(platform, "create_folder", arguments, context=context)
                
                elif tool_name == "add_marketing_subscriber":
                    platform = arguments.get("platform")
                    return await universal_integration_service.execute(platform, "add_subscriber", arguments, context=context)

                elif tool_name == "create_invoice":
                    platform = arguments.get("platform")
                    return await universal_integration_service.execute(platform, "create_invoice", arguments, context=context)
                
                elif tool_name == "create_record":
                    return await universal_integration_service.execute(arguments.get("service"), "create", {"entity": arguments.get("entity"), "data": arguments.get("data", {})}, context=context)
                
                elif tool_name == "update_record":
                    return await universal_integration_service.execute(arguments.get("service"), "update", {"entity": arguments.get("entity"), "id": arguments.get("id"), "data": arguments.get("data", {})}, context=context)
                
                elif tool_name == "push_to_integration":
                    return await universal_integration_service.execute(arguments.get("service"), arguments.get("action"), arguments.get("params", {}), context=context)

            elif tool_name == "discover_connections":
                from core.connection_service import connection_service
                user_id = context.get("user_id") if context else "default_user"
                conns = connection_service.get_connections(user_id)
                # Filter for active ones and return platform names
                return {"active_integrations": [c["integration_id"] for c in conns if c.get("status") == "active"]}

            elif tool_name == "global_search":
                from integrations.universal_integration_service import universal_integration_service
                query = arguments.get("query")
                platforms = arguments.get("platforms")
                
                if not platforms:
                    from core.connection_service import connection_service
                    user_id = context.get("user_id") if context else "default_user"
                    conns = connection_service.get_connections(user_id)
                    platforms = [c["integration_id"] for c in conns if c.get("status") == "active"]
                
                results = {}
                import asyncio
                
                async def search_task(p):
                    try:
                        return p, await universal_integration_service.search(p, query, context=context)
                    except Exception as e:
                        return p, {"status": "error", "message": str(e)}

                search_results = await asyncio.gather(*[search_task(p) for p in platforms])
                for platform, res in search_results:
                    results[platform] = res
                
                return results


            # --- WhatsApp Business Tools (Agent Communication) ---
            elif tool_name == "whatsapp_send_message":
                """Send a WhatsApp message to a recipient. Requires connected WhatsApp Business."""
                from core.connection_service import ConnectionService
                conn_service = ConnectionService()
                user_id = context.get("user_id", "default_user")
                
                # Get WhatsApp connection for this user
                connections = await conn_service.list_connections(user_id=user_id)
                whatsapp_conn = next((c for c in connections if c.integration_id == "whatsapp"), None)
                
                if not whatsapp_conn:
                    return {"error": "WhatsApp Business not connected. Please connect via /integrations."}
                
                # Get credentials from connection
                creds = whatsapp_conn.credentials or {}
                access_token = creds.get("access_token")
                phone_number_id = creds.get("phone_number_id")
                
                if not access_token or not phone_number_id:
                    return {"error": "WhatsApp credentials incomplete. Please reconnect WhatsApp."}
                
                # Send message via WhatsApp Cloud API
                to_number = arguments.get("to")
                message_text = arguments.get("message")
                
                if not to_number or not message_text:
                    return {"error": "Both 'to' (phone number) and 'message' are required."}
                
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            f"https://graph.facebook.com/v18.0/{phone_number_id}/messages",
                            headers={
                                "Authorization": f"Bearer {access_token}",
                                "Content-Type": "application/json"
                            },
                            json={
                                "messaging_product": "whatsapp",
                                "recipient_type": "individual",
                                "to": to_number,
                                "type": "text",
                                "text": {"body": message_text}
                            }
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            return {"success": True, "message_id": result.get("messages", [{}])[0].get("id")}
                        else:
                            return {"error": f"WhatsApp API error: {response.text}"}
                except Exception as e:
                    return {"error": f"Failed to send WhatsApp message: {str(e)}"}

            elif tool_name == "whatsapp_send_template":
                """Send a WhatsApp template message. Useful for marketing and notifications."""
                from core.connection_service import ConnectionService
                conn_service = ConnectionService()
                user_id = context.get("user_id", "default_user")
                
                connections = await conn_service.list_connections(user_id=user_id)
                whatsapp_conn = next((c for c in connections if c.integration_id == "whatsapp"), None)
                
                if not whatsapp_conn:
                    return {"error": "WhatsApp Business not connected."}
                
                creds = whatsapp_conn.credentials or {}
                access_token = creds.get("access_token")
                phone_number_id = creds.get("phone_number_id")
                
                if not access_token or not phone_number_id:
                    return {"error": "WhatsApp credentials incomplete."}
                
                to_number = arguments.get("to")
                template_name = arguments.get("template_name")
                language_code = arguments.get("language", "en")
                components = arguments.get("components", [])
                
                if not to_number or not template_name:
                    return {"error": "Both 'to' and 'template_name' are required."}
                
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            f"https://graph.facebook.com/v18.0/{phone_number_id}/messages",
                            headers={
                                "Authorization": f"Bearer {access_token}",
                                "Content-Type": "application/json"
                            },
                            json={
                                "messaging_product": "whatsapp",
                                "to": to_number,
                                "type": "template",
                                "template": {
                                    "name": template_name,
                                    "language": {"code": language_code},
                                    "components": components
                                }
                            }
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            return {"success": True, "message_id": result.get("messages", [{}])[0].get("id")}
                        else:
                            return {"error": f"WhatsApp API error: {response.text}"}
                except Exception as e:
                    return {"error": f"Failed to send WhatsApp template: {str(e)}"}

            elif tool_name == "whatsapp_list_templates":
                """List available WhatsApp message templates for this business."""
                from core.connection_service import ConnectionService
                conn_service = ConnectionService()
                user_id = context.get("user_id", "default_user")
                
                connections = await conn_service.list_connections(user_id=user_id)
                whatsapp_conn = next((c for c in connections if c.integration_id == "whatsapp"), None)
                
                if not whatsapp_conn:
                    return {"error": "WhatsApp Business not connected."}
                
                creds = whatsapp_conn.credentials or {}
                access_token = creds.get("access_token")
                waba_id = creds.get("waba_id")
                
                if not access_token or not waba_id:
                    return {"error": "WhatsApp credentials incomplete."}
                
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(
                            f"https://graph.facebook.com/v18.0/{waba_id}/message_templates",
                            params={"access_token": access_token}
                        )
                        
                        if response.status_code == 200:
                            data = response.json()
                            templates = [
                                {"name": t.get("name"), "status": t.get("status"), "category": t.get("category")}
                                for t in data.get("data", [])
                            ]
                            return {"templates": templates}
                        else:
                            return {"error": f"WhatsApp API error: {response.text}"}
                except Exception as e:
                    return {"error": f"Failed to list WhatsApp templates: {str(e)}"}

            # --- Fallbacks & Discovery ---
            elif tool_name == "call_integration":
                from integrations.universal_integration_service import universal_integration_service
                return await universal_integration_service.execute(arguments.get("service"), arguments.get("action"), arguments.get("params", {}), context=context)

            elif tool_name == "list_integrations":
                from integrations.universal_integration_service import NATIVE_INTEGRATIONS
                return {"native_integrations": sorted(list(NATIVE_INTEGRATIONS)), "native_count": len(NATIVE_INTEGRATIONS)}

        # Unknown MCP server - fail explicitly
        return {"error": f"Tool '{tool_name}' on server '{server_id}' is not implemented.", "status": "not_implemented"}

    async def web_search(self, query: str, user_id: str = None) -> Dict[str, Any]:
        """
        Performs a web search using available search APIs or MCP servers.
        Supports BYOK - checks user's Tavily key first, then falls back to env var.
        """
        logger.info(f"Performing web search for: {query} (user: {user_id})")
        
        # Priority 1: Check for user-specific BYOK Tavily key
        tavily_api_key = None
        if user_id:
            try:
                from core.byok_endpoints import get_byok_manager
                byok_manager = get_byok_manager()
                tavily_api_key = byok_manager.get_api_key("tavily")
                if tavily_api_key:
                    logger.info(f"Using BYOK Tavily key for user {user_id}")
            except Exception as e:
                logger.warning(f"Failed to get BYOK Tavily key: {e}")
        
        # Priority 2: Fall back to environment variable
        if not tavily_api_key:
            tavily_api_key = os.getenv("TAVILY_API_KEY")
        
        # If we have a Tavily API key, use it
        if tavily_api_key:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": tavily_api_key,
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
            "error": "Web search is not configured. Add a Tavily API key via BYOK settings or set TAVILY_API_KEY."
        }

# Singleton instance
mcp_service = MCPService()
