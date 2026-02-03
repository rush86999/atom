"""
Workflow Step Types Reference - Phase 38
Complete list of all available step types for building workflow templates.
"""

from typing import Any, Dict, List

# All available step types for workflow templates
STEP_TYPE_REFERENCE: Dict[str, Dict[str, Any]] = {
    # ==================== CORE WORKFLOW ====================
    "conditional_logic": {
        "category": "core",
        "description": "If/else branching based on conditions",
        "parameters": ["conditions", "ai_option", "ai_prompt"],
        "outputs": ["next_steps", "condition_met"]
    },
    "parallel_execution": {
        "category": "core",
        "description": "Execute multiple steps in parallel",
        "parameters": ["parallel_steps"],
        "outputs": ["parallel_results"]
    },
    "delay": {
        "category": "core",
        "description": "Wait for specified duration",
        "parameters": ["seconds"],
        "outputs": []
    },
    "approval_required": {
        "category": "core",
        "description": "Pause workflow until human approval",
        "parameters": ["approver", "message", "timeout"],
        "outputs": ["approved", "approver_response"]
    },
    "data_transformation": {
        "category": "core",
        "description": "Transform data between steps",
        "parameters": ["transformation_rules", "input_data"],
        "outputs": ["transformed_data"]
    },
    "api_call": {
        "category": "core",
        "description": "Make HTTP API call",
        "parameters": ["url", "method", "headers", "body"],
        "outputs": ["response", "status_code"]
    },
    
    # ==================== COMMUNICATION ====================
    "email_send": {
        "category": "communication",
        "description": "Send email notification",
        "parameters": ["recipient", "subject", "template", "content"],
        "outputs": ["sent_at"]
    },
    "slack_notification": {
        "category": "communication",
        "description": "Send Slack message",
        "parameters": ["channel", "message", "title"],
        "outputs": ["sent_at"]
    },
    
    # ==================== INTEGRATIONS ====================
    "gmail_fetch": {
        "category": "integration",
        "description": "Fetch emails from Gmail",
        "parameters": ["query", "max_results"],
        "outputs": ["emails"]
    },
    "gmail_search": {
        "category": "integration",
        "description": "Search Gmail messages",
        "parameters": ["query"],
        "outputs": ["results"]
    },
    "gmail_integration": {
        "category": "integration",
        "description": "Full Gmail integration actions",
        "parameters": ["action", "email_id"],
        "outputs": ["result"]
    },
    "notion_integration": {
        "category": "integration",
        "description": "Notion page/database operations",
        "parameters": ["action", "page_id", "database_id"],
        "outputs": ["result"]
    },
    "notion_search": {
        "category": "integration",
        "description": "Search Notion workspace",
        "parameters": ["query"],
        "outputs": ["results"]
    },
    "notion_db_query": {
        "category": "integration",
        "description": "Query Notion database",
        "parameters": ["database_id", "filter"],
        "outputs": ["results"]
    },
    "asana_integration": {
        "category": "integration",
        "description": "Asana task operations",
        "parameters": ["action", "project_id", "task_data"],
        "outputs": ["result"]
    },
    "hubspot_integration": {
        "category": "integration",
        "description": "HubSpot CRM operations",
        "parameters": ["action", "object_type", "object_id", "data"],
        "outputs": ["result"]
    },
    "salesforce_integration": {
        "category": "integration",
        "description": "Salesforce CRM operations",
        "parameters": ["action", "object_type", "sobject_id", "data"],
        "outputs": ["result"]
    },
    "universal_integration": {
        "category": "integration",
        "description": "Generic integration adapter",
        "parameters": ["service", "action", "params"],
        "outputs": ["result"]
    },
    
    # ==================== AI & KNOWLEDGE ====================
    "nlu_analysis": {
        "category": "ai",
        "description": "Natural language understanding analysis",
        "parameters": ["text", "analysis_type"],
        "outputs": ["entities", "intent", "sentiment"]
    },
    "knowledge_lookup": {
        "category": "ai",
        "description": "Query knowledge base",
        "parameters": ["query", "filters"],
        "outputs": ["results", "confidence"]
    },
    "knowledge_update": {
        "category": "ai",
        "description": "Update knowledge base",
        "parameters": ["content", "metadata"],
        "outputs": ["record_id"]
    },
    "system_reasoning": {
        "category": "ai",
        "description": "Cross-system AI reasoning",
        "parameters": ["context", "question"],
        "outputs": ["answer", "sources"]
    },
    "app_search": {
        "category": "ai",
        "description": "Search across connected apps",
        "parameters": ["query", "apps"],
        "outputs": ["results"]
    },
    
    # ==================== E-COMMERCE ====================
    "ecommerce_sync": {
        "category": "ecommerce",
        "description": "Sync orders to ledger",
        "parameters": ["order_id", "action"],
        "outputs": ["transaction_id"]
    },
    "invoice_processing": {
        "category": "ecommerce",
        "description": "Process and record invoices",
        "parameters": ["invoice_data"],
        "outputs": ["ledger_entry"]
    },
    
    # ==================== AGENTS (Phase 28+) ====================
    "agent_execution": {
        "category": "agent",
        "description": "Execute Computer Use agent",
        "parameters": ["agent_id", "agent_params"],
        "outputs": ["agent_output"]
    },
    "background_agent_start": {
        "category": "agent",
        "description": "Start periodic background agent",
        "parameters": ["agent_id", "interval_seconds"],
        "outputs": ["status"]
    },
    "background_agent_stop": {
        "category": "agent",
        "description": "Stop background agent",
        "parameters": ["agent_id"],
        "outputs": ["status"]
    },
    
    # ==================== FINANCIAL OPS (Phase 37) ====================
    "cost_leak_detection": {
        "category": "financial",
        "description": "Detect unused SaaS and redundant tools",
        "parameters": [],
        "outputs": ["cost_report", "unused_count", "potential_savings"]
    },
    "budget_check": {
        "category": "financial",
        "description": "Check spend against budget limits",
        "parameters": ["category", "amount", "deal_stage", "milestone"],
        "outputs": ["status", "remaining"]
    },
    "invoice_reconciliation": {
        "category": "financial",
        "description": "Match invoices to contracts",
        "parameters": [],
        "outputs": ["reconciliation_result", "matched", "discrepancies"]
    },
    
    # ==================== TASK MANAGEMENT ====================
    "task_creation": {
        "category": "task",
        "description": "Create task in connected task manager",
        "parameters": ["title", "description", "assignee", "due_date"],
        "outputs": ["task_id"]
    }
}

def get_step_types_by_category(category: str = None) -> List[Dict[str, Any]]:
    """Get step types optionally filtered by category"""
    if category:
        return [
            {"type": k, **v}
            for k, v in STEP_TYPE_REFERENCE.items()
            if v["category"] == category
        ]
    return [{"type": k, **v} for k, v in STEP_TYPE_REFERENCE.items()]

def get_all_categories() -> List[str]:
    """Get all available step categories"""
    return list(set(v["category"] for v in STEP_TYPE_REFERENCE.values()))
