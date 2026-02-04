import os
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent))

import logging

from core.workflow_template_system import (
    TemplateCategory,
    TemplateComplexity,
    WorkflowTemplateManager,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Seeding")

def seed_marketplace():
    manager = WorkflowTemplateManager()
    
    journeys = [
        {
            "template_id": "lead_enrichment_crm",
            "name": "Lead Enrichment & CRM sync",
            "description": "Automatically enrich LinkedIn leads via Clearbit and sync to Salesforce/HubSpot.",
            "category": TemplateCategory.BUSINESS,
            "complexity": TemplateComplexity.INTERMEDIATE,
            "tags": ["sales", "crm", "enrichment", "salesforce", "hubspot"],
            "inputs": [
                {"name": "source_type", "label": "Lead Source", "description": "LinkedIn or Spreadsheet", "type": "string", "required": True},
                {"name": "crm_platform", "label": "Target CRM", "description": "Salesforce or HubSpot", "type": "string", "required": True}
            ],
            "steps": [
                {"step_id": "extract", "name": "Extract Leads", "description": "Get leads from source", "step_type": "extraction", "parameters": []},
                {"step_id": "enrich", "name": "Enrich with Clearbit", "description": "Lookup company/person info", "step_type": "enrichment", "depends_on": ["extract"], "parameters": []},
                {"step_id": "sync", "name": "Sync to CRM", "description": "Update or create CRM record", "step_type": "crm_sync", "depends_on": ["enrich"], "parameters": []}
            ],
            "is_featured": True,
            "is_public": True
        },
        {
            "template_id": "meeting_summary_slack",
            "name": "Cross-Platform Meeting Summary",
            "description": "Summarize Zoom/Meet calls and post to Slack/Discord.",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.BEGINNER,
            "tags": ["meeting", "ai", "summary", "slack", "zoom"],
            "inputs": [
                {"name": "platform", "label": "Meeting Platform", "description": "Zoom or Google Meet", "type": "string", "required": True},
                {"name": "channel", "label": "Post to Channel", "description": "Slack/Discord channel name", "type": "string", "required": True}
            ],
            "steps": [
                {"step_id": "transcript", "name": "Get Transcript", "description": "Fetch call transcript", "step_type": "extraction", "parameters": []},
                {"step_id": "summarize", "name": "AI Summarize", "description": "Generate key takeaways", "step_type": "ai_transformation", "depends_on": ["transcript"], "parameters": []},
                {"step_id": "post", "name": "Post to Chat", "description": "Share summary in channel", "step_type": "notification", "depends_on": ["summarize"], "parameters": []}
            ],
            "is_featured": True,
            "is_public": True
        },
        {
            "template_id": "support_sentiment_draft",
            "name": "Automated Support Response",
            "description": "Analyze Zendesk ticket sentiment and draft preliminary responses.",
            "category": TemplateCategory.BUSINESS,
            "complexity": TemplateComplexity.INTERMEDIATE,
            "tags": ["support", "ai", "zendesk", "sentiment"],
            "inputs": [
                {"name": "ticket_id", "label": "Specific Ticket ID", "description": "Leave blank to monitor all", "type": "string", "required": False}
            ],
            "steps": [
                {"step_id": "fetch", "name": "Fetch Tickets", "description": "Get latest Support tickets", "step_type": "extraction", "parameters": []},
                {"step_id": "analyze", "name": "Sentiment Check", "description": "Detect frustration/urgency", "step_type": "ai_transformation", "depends_on": ["fetch"], "parameters": []},
                {"step_id": "draft", "name": "Draft Response", "description": "Prepare response in Zendesk", "step_type": "action", "depends_on": ["analyze"], "parameters": []}
            ],
            "is_public": True
        },
        {
            "template_id": "financial_report_email",
            "name": "Financial Report Generation",
            "description": "Aggregate Stripe/Quickbooks data into a PDF report sent via email.",
            "category": TemplateCategory.REPORTING,
            "complexity": TemplateComplexity.ADVANCED,
            "tags": ["finance", "stripe", "pdf", "reporting"],
            "inputs": [
                {"name": "date_range", "label": "Reporting Period", "description": "Last 30 days, Quater, etc.", "type": "string", "required": True},
                {"name": "recipient", "label": "Email Recipient", "description": "Who gets the report?", "type": "string", "required": True}
            ],
            "steps": [
                {"step_id": "agg", "name": "Aggregate Revenue", "description": "Sum Stripe transactions", "step_type": "extraction", "parameters": []},
                {"step_id": "calc", "name": "Analyze Metrics", "description": "Compare to previous period", "step_type": "transformation", "depends_on": ["agg"], "parameters": []},
                {"step_id": "pdf", "name": "Generate PDF", "description": "Build visual report", "step_type": "transformation", "depends_on": ["calc"], "parameters": []},
                {"step_id": "send", "name": "Email Report", "description": "Send PDF as attachment", "step_type": "notification", "depends_on": ["pdf"], "parameters": []}
            ],
            "is_public": True
        },
        {
            "template_id": "voice_daily_summary",
            "name": "Voice-Driven Daily Audit",
            "description": "Trigger a daily summary of all apps via voice command.",
            "category": TemplateCategory.GENERAL,
            "complexity": TemplateComplexity.BEGINNER,
            "tags": ["voice", "audit", "summary", "productivity"],
            "inputs": [
                {"name": "voice_trigger", "label": "Trigger Phrase", "description": "e.g. 'Audit my day'", "type": "string", "required": True, "default_value": "Audit my day"}
            ],
            "steps": [
                {"step_id": "gather", "name": "Gather Data", "description": "Check Tasks/Calendar/Email", "step_type": "extraction", "parameters": []},
                {"step_id": "speak", "name": "Audio Summary", "description": "Speak summary back to user", "step_type": "notification", "depends_on": ["gather"], "parameters": []}
            ],
            "is_public": True
        },
        {
            "template_id": "unified_inventory_restock",
            "name": "Multi-Platform Restocking Automation",
            "description": "Monitor Shopify or Zoho inventory and notify suppliers if stock is low.",
            "category": TemplateCategory.BUSINESS,
            "complexity": TemplateComplexity.INTERMEDIATE,
            "tags": ["shopify", "zoho", "e-commerce", "inventory", "sales"],
            "inputs": [
                {"name": "platform", "label": "Inventory Platform", "description": "shopify or zoho", "type": "string", "required": False},
                {"name": "threshold", "label": "Low Stock Level", "description": "Items remaining to trigger", "type": "number", "required": True, "default_value": 5}
            ],
            "steps": [
                {"step_id": "check", "name": "Monitor Inventory", "description": "Fetch stock levels from connected platforms", "step_type": "extraction", "parameters": []},
                {"step_id": "filter", "name": "Filter Low Items", "description": "Find items meeting threshold", "step_type": "transformation", "depends_on": ["check"], "parameters": []},
                {"step_id": "notify", "name": "Email Supplier", "description": "Send P.O. request", "step_type": "notification", "depends_on": ["filter"], "parameters": []}
            ],
            "is_public": True
        },
        {
            "template_id": "social_media_multi",
            "name": "Social Media Orchestration",
            "description": "AI-drafted content scheduled across Twitter and LinkedIn.",
            "category": TemplateCategory.AUTOMATION,
            "complexity": TemplateComplexity.INTERMEDIATE,
            "tags": ["marketing", "social", "ai", "content"],
            "inputs": [
                {"name": "topic", "label": "Post Topic", "description": "Subject of the social posts", "type": "string", "required": True}
            ],
            "steps": [
                {"step_id": "draft", "name": "AI Draft", "description": "Generate multi-platform content", "step_type": "ai_transformation", "parameters": []},
                {"step_id": "review", "name": "User Review", "description": "Approve or edit drafts", "step_type": "human_action", "depends_on": ["draft"], "parameters": []},
                {"step_id": "schedule", "name": "Schedule Posts", "description": "Post to Twitter/LinkedIn", "step_type": "action", "depends_on": ["review"], "parameters": []}
            ],
            "is_public": True
        },
        {
            "template_id": "infra_health_check",
            "name": "Integration Health Monitoring",
            "description": "Periodic checks of all integration health with SMS alerts on failure.",
            "category": TemplateCategory.MONITORING,
            "complexity": TemplateComplexity.ADVANCED,
            "tags": ["ops", "monitoring", "alerting", "infra"],
            "inputs": [
                {"name": "sms_recipient", "label": "Critical Alert Phone", "description": "E.164 formatted number", "type": "string", "required": True}
            ],
            "steps": [
                {"step_id": "probe", "name": "Probe Connections", "description": "Check all API statuses", "step_type": "extraction", "parameters": []},
                {"step_id": "evaluate", "name": "Health Eval", "description": "Identify critical failures", "step_type": "transformation", "depends_on": ["probe"], "parameters": []},
                {"step_id": "sms", "name": "Send SMS Alert", "description": "Emergency notification", "step_type": "notification", "depends_on": ["evaluate"], "parameters": []}
            ],
            "is_public": True
        },
        {
            "template_id": "agent_pm_auto",
            "name": "Agentic Project Management",
            "description": "AI agent reorganizes Jira/Asana tasks based on team velocity.",
            "category": TemplateCategory.GENERAL,
            "complexity": TemplateComplexity.EXPERT,
            "tags": ["pm", "ai", "jira", "asana"],
            "inputs": [
                {"name": "platform", "label": "PM Platform", "description": "Jira or Asana", "type": "string", "required": True}
            ],
            "steps": [
                {"step_id": "fetch", "name": "Fetch Backlog", "description": "Collect uncompleted tasks", "step_type": "extraction", "parameters": []},
                {"step_id": "analyze", "name": "AI Priority Sort", "description": "Re-balance based on deadlines", "step_type": "ai_transformation", "depends_on": ["fetch"], "parameters": []},
                {"step_id": "update", "name": "Apply Changes", "description": "Update PM tool task orders", "step_type": "action", "depends_on": ["analyze"], "parameters": []}
            ],
            "is_featured": True,
            "is_public": True
        },
        {
            "template_id": "sales_pipeline_opt",
            "name": "Sales Pipeline Optimization",
            "description": "Comprehensive pipeline management from lead to forecast.",
            "category": TemplateCategory.BUSINESS,
            "complexity": TemplateComplexity.EXPERT,
            "tags": ["sales", "pipeline", "automation"],
            "inputs": [
                {"name": "sales_lead", "label": "Pipeline Lead Email", "description": "Who owns this forecast?", "type": "string", "required": True}
            ],
            "steps": [
                {"step_id": "scan", "name": "Scan Deals", "description": "Find stagnant lead deals", "step_type": "extraction", "parameters": []},
                {"step_id": "assign", "name": "Assign Tasks", "description": "Create follow-up actions", "step_type": "action", "depends_on": ["scan"], "parameters": []},
                {"step_id": "forecast", "name": "Weekly Forecast", "description": "AI revenue prediction", "step_type": "ai_transformation", "depends_on": ["assign"], "parameters": []}
            ],
            "is_featured": True,
            "is_public": True
        }
    ]

    for journey in journeys:
        try:
            manager.create_template(journey)
            print(f"Seeded: {journey['name']}")
        except Exception as e:
            print(f"Failed: {journey['name']}")

if __name__ == "__main__":
    seed_marketplace()
