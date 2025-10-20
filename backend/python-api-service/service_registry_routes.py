from flask import Blueprint, jsonify, request
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
import uuid

logger = logging.getLogger(__name__)

service_registry_bp = Blueprint("service_registry", __name__)

# Comprehensive service registry with all third-party integrations
SERVICE_REGISTRY = {
    # Core Services
    "workflow_automation": {
        "name": "Workflow Automation",
        "status": "active",
        "type": "core",
        "description": "Natural language workflow automation with RRule scheduling",
        "capabilities": [
            "create_workflow",
            "execute_workflow",
            "schedule_workflow",
            "analyze_natural_language",
        ],
        "health": "healthy",
        "workflow_triggers": ["time_based", "event_based", "chat_command"],
        "workflow_actions": ["execute_workflow", "schedule_workflow", "notify_user"],
        "chat_commands": ["create workflow", "schedule task", "automate process"],
        "last_checked": datetime.now().isoformat(),
    },
    "atom_agent": {
        "name": "Atom Agent",
        "status": "active",
        "type": "core",
        "description": "AI-powered personal assistant with natural language processing",
        "capabilities": ["chat_interface", "command_execution", "workflow_triggering"],
        "health": "healthy",
        "workflow_triggers": ["chat_command", "voice_command"],
        "workflow_actions": [
            "execute_command",
            "trigger_workflow",
            "provide_assistance",
        ],
        "chat_commands": [
            "help",
            "create workflow",
            "connect service",
            "automate task",
        ],
        "last_checked": datetime.now().isoformat(),
    },
    # Calendar & Scheduling
    "google_calendar": {
        "name": "Google Calendar",
        "status": "connected",
        "type": "integration",
        "description": "Google Calendar integration for event management",
        "capabilities": [
            "create_event",
            "find_availability",
            "list_events",
            "update_event",
            "delete_event",
        ],
        "health": "healthy",
        "workflow_triggers": ["new_event", "event_updated", "event_reminder"],
        "workflow_actions": [
            "create_calendar_event",
            "find_free_slots",
            "schedule_meeting",
        ],
        "chat_commands": ["schedule meeting", "check calendar", "create event"],
        "last_checked": datetime.now().isoformat(),
    },
    "outlook_calendar": {
        "name": "Outlook Calendar",
        "status": "connected",
        "type": "integration",
        "description": "Microsoft Outlook calendar integration",
        "capabilities": ["create_event", "list_events", "update_event"],
        "health": "healthy",
        "workflow_triggers": ["new_event", "event_updated"],
        "workflow_actions": ["create_calendar_event", "schedule_meeting"],
        "chat_commands": ["schedule outlook meeting", "check outlook calendar"],
        "last_checked": datetime.now().isoformat(),
    },
    # Task Management
    "asana": {
        "name": "Asana",
        "status": "connected",
        "type": "integration",
        "description": "Asana task and project management",
        "capabilities": [
            "create_task",
            "update_task",
            "list_tasks",
            "create_project",
            "assign_task",
        ],
        "health": "healthy",
        "workflow_triggers": ["task_created", "task_completed", "task_assigned"],
        "workflow_actions": ["create_task", "update_task_status", "assign_task"],
        "chat_commands": ["create asana task", "check tasks", "assign task"],
        "last_checked": datetime.now().isoformat(),
    },
    "trello": {
        "name": "Trello",
        "status": "connected",
        "type": "integration",
        "description": "Trello board and card management",
        "capabilities": [
            "create_card",
            "update_card",
            "move_card",
            "create_board",
            "add_comment",
        ],
        "health": "healthy",
        "workflow_triggers": ["card_created", "card_moved", "card_updated"],
        "workflow_actions": ["create_card", "move_card", "add_comment"],
        "chat_commands": ["create trello card", "move card", "check board"],
        "last_checked": datetime.now().isoformat(),
    },
    "notion": {
        "name": "Notion",
        "status": "connected",
        "type": "integration",
        "description": "Notion workspace and database integration",
        "capabilities": [
            "create_page",
            "update_page",
            "search_pages",
            "query_database",
            "create_database",
        ],
        "health": "healthy",
        "workflow_triggers": ["page_created", "page_updated", "database_updated"],
        "workflow_actions": ["create_page", "update_page", "query_database"],
        "chat_commands": ["create notion page", "search notion", "update database"],
        "last_checked": datetime.now().isoformat(),
    },
    "jira": {
        "name": "Jira",
        "status": "connected",
        "type": "integration",
        "description": "Jira issue and project tracking",
        "capabilities": [
            "create_issue",
            "update_issue",
            "search_issues",
            "create_project",
        ],
        "health": "healthy",
        "workflow_triggers": ["issue_created", "issue_updated", "issue_assigned"],
        "workflow_actions": ["create_issue", "update_issue_status", "assign_issue"],
        "chat_commands": ["create jira issue", "check issues", "update jira"],
        "last_checked": datetime.now().isoformat(),
    },
    # Communication
    "gmail": {
        "name": "Gmail",
        "status": "connected",
        "type": "integration",
        "description": "Gmail email integration",
        "capabilities": [
            "send_email",
            "list_emails",
            "search_emails",
            "create_draft",
            "label_email",
        ],
        "health": "healthy",
        "workflow_triggers": ["new_email", "email_received", "email_labeled"],
        "workflow_actions": ["send_email", "search_emails", "label_email"],
        "chat_commands": ["send email", "check emails", "search gmail"],
        "last_checked": datetime.now().isoformat(),
    },
    "slack": {
        "name": "Slack",
        "status": "connected",
        "type": "integration",
        "description": "Slack messaging and channel management",
        "capabilities": [
            "send_message",
            "list_channels",
            "search_messages",
            "create_channel",
            "upload_file",
        ],
        "health": "healthy",
        "workflow_triggers": ["message_received", "channel_created", "file_uploaded"],
        "workflow_actions": ["send_message", "create_channel", "upload_file"],
        "chat_commands": ["send slack message", "create channel", "search slack"],
        "last_checked": datetime.now().isoformat(),
    },
    "microsoft_teams": {
        "name": "Microsoft Teams",
        "status": "connected",
        "type": "integration",
        "description": "Microsoft Teams integration",
        "capabilities": ["send_message", "list_channels", "create_team"],
        "health": "healthy",
        "workflow_triggers": ["message_received", "team_created"],
        "workflow_actions": ["send_message", "create_team"],
        "chat_commands": ["send teams message", "create team"],
        "last_checked": datetime.now().isoformat(),
    },
    "discord": {
        "name": "Discord",
        "status": "connected",
        "type": "integration",
        "description": "Discord messaging integration",
        "capabilities": ["send_message", "list_channels", "create_channel"],
        "health": "healthy",
        "workflow_triggers": ["message_received", "channel_created"],
        "workflow_actions": ["send_message", "create_channel"],
        "chat_commands": ["send discord message", "create channel"],
        "last_checked": datetime.now().isoformat(),
    },
    # File Storage
    "google_drive": {
        "name": "Google Drive",
        "status": "connected",
        "type": "integration",
        "description": "Google Drive file storage integration",
        "capabilities": [
            "upload_file",
            "download_file",
            "list_files",
            "create_folder",
            "share_file",
        ],
        "health": "healthy",
        "workflow_triggers": ["file_uploaded", "file_shared", "folder_created"],
        "workflow_actions": ["upload_file", "download_file", "share_file"],
        "chat_commands": ["upload to drive", "share file", "list files"],
        "last_checked": datetime.now().isoformat(),
    },
    "dropbox": {
        "name": "Dropbox",
        "status": "connected",
        "type": "integration",
        "description": "Dropbox file storage integration",
        "capabilities": [
            "upload_file",
            "download_file",
            "list_files",
            "create_folder",
            "share_link",
        ],
        "health": "healthy",
        "workflow_triggers": ["file_uploaded", "file_shared", "folder_created"],
        "workflow_actions": ["upload_file", "download_file", "share_link"],
        "chat_commands": [
            "upload to dropbox",
            "share dropbox file",
            "list dropbox files",
        ],
        "last_checked": datetime.now().isoformat(),
    },
    "box": {
        "name": "Box",
        "status": "connected",
        "type": "integration",
        "description": "Box file storage integration",
        "capabilities": ["upload_file", "download_file", "list_files", "create_folder"],
        "health": "healthy",
        "workflow_triggers": ["file_uploaded", "folder_created"],
        "workflow_actions": ["upload_file", "download_file", "create_folder"],
        "chat_commands": ["upload to box", "list box files"],
        "last_checked": datetime.now().isoformat(),
    },
    "onedrive": {
        "name": "OneDrive",
        "status": "connected",
        "type": "integration",
        "description": "Microsoft OneDrive integration",
        "capabilities": ["upload_file", "download_file", "list_files", "create_folder"],
        "health": "healthy",
        "workflow_triggers": ["file_uploaded", "folder_created"],
        "workflow_actions": ["upload_file", "download_file", "create_folder"],
        "chat_commands": ["upload to onedrive", "list onedrive files"],
        "last_checked": datetime.now().isoformat(),
    },
    # Development & Code
    "github": {
        "name": "GitHub",
        "status": "connected",
        "type": "integration",
        "description": "GitHub repository and issue management",
        "capabilities": [
            "create_issue",
            "list_repos",
            "search_code",
            "create_repo",
            "create_pull_request",
        ],
        "health": "healthy",
        "workflow_triggers": ["issue_created", "pull_request_created", "commit_pushed"],
        "workflow_actions": ["create_issue", "create_repo", "create_pull_request"],
        "chat_commands": ["create github issue", "search code", "create repo"],
        "last_checked": datetime.now().isoformat(),
    },
    "gitlab": {
        "name": "GitLab",
        "status": "connected",
        "type": "integration",
        "description": "GitLab repository management",
        "capabilities": ["create_issue", "list_projects", "create_project"],
        "health": "healthy",
        "workflow_triggers": ["issue_created", "project_created"],
        "workflow_actions": ["create_issue", "create_project"],
        "chat_commands": ["create gitlab issue", "create project"],
        "last_checked": datetime.now().isoformat(),
    },
    # Financial Services
    "plaid": {
        "name": "Plaid",
        "status": "connected",
        "type": "integration",
        "description": "Plaid financial data integration",
        "capabilities": [
            "get_transactions",
            "get_accounts",
            "get_balance",
            "categorize_transactions",
        ],
        "health": "healthy",
        "workflow_triggers": [
            "new_transaction",
            "low_balance",
            "transaction_categorized",
        ],
        "workflow_actions": [
            "get_transactions",
            "get_balance",
            "categorize_transactions",
        ],
        "chat_commands": ["check balance", "get transactions", "categorize spending"],
        "last_checked": datetime.now().isoformat(),
    },
    "quickbooks": {
        "name": "QuickBooks",
        "status": "connected",
        "type": "integration",
        "description": "QuickBooks accounting integration",
        "capabilities": [
            "create_invoice",
            "get_invoices",
            "create_customer",
            "get_reports",
        ],
        "health": "healthy",
        "workflow_triggers": [
            "invoice_created",
            "payment_received",
            "customer_created",
        ],
        "workflow_actions": ["create_invoice", "create_customer", "generate_report"],
        "chat_commands": ["create invoice", "get quickbooks report", "add customer"],
        "last_checked": datetime.now().isoformat(),
    },
    "xero": {
        "name": "Xero",
        "status": "connected",
        "type": "integration",
        "description": "Xero accounting integration",
        "capabilities": [
            "create_invoice",
            "get_invoices",
            "create_contact",
            "get_reports",
        ],
        "health": "healthy",
        "workflow_triggers": ["invoice_created", "contact_created"],
        "workflow_actions": ["create_invoice", "create_contact", "generate_report"],
        "chat_commands": ["create xero invoice", "add contact", "get xero report"],
        "last_checked": datetime.now().isoformat(),
    },
    # CRM & Sales
    "salesforce": {
        "name": "Salesforce",
        "status": "connected",
        "type": "integration",
        "description": "Salesforce CRM integration",
        "capabilities": [
            "create_lead",
            "update_contact",
            "create_opportunity",
            "get_reports",
        ],
        "health": "healthy",
        "workflow_triggers": ["lead_created", "contact_updated", "opportunity_won"],
        "workflow_actions": ["create_lead", "update_contact", "create_opportunity"],
        "chat_commands": [
            "create salesforce lead",
            "update contact",
            "create opportunity",
        ],
        "last_checked": datetime.now().isoformat(),
    },
    "hubspot": {
        "name": "HubSpot",
        "status": "connected",
        "type": "integration",
        "description": "HubSpot CRM and marketing integration",
        "capabilities": [
            "create_contact",
            "update_contact",
            "create_deal",
            "send_email",
        ],
        "health": "healthy",
        "workflow_triggers": ["contact_created", "deal_created", "email_sent"],
        "workflow_actions": ["create_contact", "create_deal", "send_email"],
        "chat_commands": [
            "create hubspot contact",
            "create deal",
            "send hubspot email",
        ],
        "last_checked": datetime.now().isoformat(),
    },
    "zoho": {
        "name": "Zoho",
        "status": "connected",
        "type": "integration",
        "description": "Zoho CRM integration",
        "capabilities": ["create_lead", "update_contact", "create_deal"],
        "health": "healthy",
        "workflow_triggers": ["lead_created", "contact_updated"],
        "workflow_actions": ["create_lead", "update_contact", "create_deal"],
        "chat_commands": ["create zoho lead", "update contact"],
        "last_checked": datetime.now().isoformat(),
    },
    # Social Media
    "twitter": {
        "name": "Twitter/X",
        "status": "connected",
        "type": "integration",
        "description": "Twitter/X social media integration",
        "capabilities": ["send_tweet", "search_tweets", "get_timeline", "like_tweet"],
        "health": "healthy",
        "workflow_triggers": ["tweet_posted", "tweet_liked", "mention_received"],
        "workflow_actions": ["send_tweet", "search_tweets", "like_tweet"],
        "chat_commands": ["send tweet", "search twitter", "check mentions"],
        "last_checked": datetime.now().isoformat(),
    },
    "linkedin": {
        "name": "LinkedIn",
        "status": "connected",
        "type": "integration",
        "description": "LinkedIn professional network integration",
        "capabilities": [
            "post_update",
            "search_posts",
            "get_connections",
            "send_message",
        ],
        "health": "healthy",
        "workflow_triggers": ["post_created", "message_received", "connection_added"],
        "workflow_actions": ["post_update", "send_message", "search_posts"],
        "chat_commands": [
            "post to linkedin",
            "send linkedin message",
            "search linkedin",
        ],
        "last_checked": datetime.now().isoformat(),
    },
    # Marketing & E-commerce
    "mailchimp": {
        "name": "Mailchimp",
        "status": "connected",
        "type": "integration",
        "description": "Mailchimp email marketing integration",
        "capabilities": [
            "send_campaign",
            "create_audience",
            "add_subscriber",
            "get_reports",
        ],
        "health": "healthy",
        "workflow_triggers": ["campaign_sent", "subscriber_added", "audience_created"],
        "workflow_actions": ["send_campaign", "create_audience", "add_subscriber"],
        "chat_commands": [
            "send mailchimp campaign",
            "add subscriber",
            "create audience",
        ],
        "last_checked": datetime.now().isoformat(),
    },
    "shopify": {
        "name": "Shopify",
        "status": "connected",
        "type": "integration",
        "description": "Shopify e-commerce integration",
        "capabilities": [
            "create_product",
            "update_product",
            "get_orders",
            "create_order",
        ],
        "health": "healthy",
        "workflow_triggers": ["order_created", "product_updated", "customer_created"],
        "workflow_actions": ["create_product", "update_product", "get_orders"],
        "chat_commands": ["create shopify product", "get orders", "update product"],
        "last_checked": datetime.now().isoformat(),
    },
    "wordpress": {
        "name": "WordPress",
        "status": "connected",
        "type": "integration",
        "description": "WordPress CMS integration",
        "capabilities": ["create_post", "update_post", "get_posts", "create_page"],
        "health": "healthy",
        "workflow_triggers": ["post_published", "page_created", "comment_added"],
        "workflow_actions": ["create_post", "update_post", "create_page"],
        "chat_commands": ["create wordpress post", "update post", "get posts"],
        "last_checked": datetime.now().isoformat(),
    },
    # Other Services
    "zapier": {
        "name": "Zapier",
        "status": "connected",
        "type": "integration",
        "description": "Zapier automation integration",
        "capabilities": ["trigger_zap", "create_zap", "get_zaps"],
        "health": "healthy",
        "workflow_triggers": ["zap_triggered", "zap_created"],
        "workflow_actions": ["trigger_zap", "create_zap"],
        "chat_commands": ["trigger zap", "create zapier automation"],
        "last_checked": datetime.now().isoformat(),
    },
    "zendesk": {
        "name": "Zendesk",
        "status": "connected",
        "type": "integration",
        "description": "Zendesk customer support integration",
        "capabilities": [
            "create_ticket",
            "update_ticket",
            "get_tickets",
            "create_user",
        ],
        "health": "healthy",
        "workflow_triggers": ["ticket_created", "ticket_updated", "user_created"],
        "workflow_actions": ["create_ticket", "update_ticket", "create_user"],
        "chat_commands": ["create zendesk ticket", "update ticket", "get tickets"],
        "last_checked": datetime.now().isoformat(),
    },
    "docusign": {
        "name": "DocuSign",
        "status": "connected",
        "type": "integration",
        "description": "DocuSign electronic signature integration",
        "capabilities": ["send_envelope", "get_envelopes", "create_template"],
        "health": "healthy",
        "workflow_triggers": ["envelope_sent", "envelope_completed"],
        "workflow_actions": ["send_envelope", "create_template"],
        "chat_commands": ["send docusign document", "create template"],
        "last_checked": datetime.now().isoformat(),
    },
    "bamboohr": {
        "name": "BambooHR",
        "status": "connected",
        "type": "integration",
        "description": "BambooHR HR management integration",
        "capabilities": [
            "create_employee",
            "update_employee",
            "get_employees",
            "create_time_off",
        ],
        "health": "healthy",
        "workflow_triggers": ["employee_created", "time_off_requested"],
        "workflow_actions": ["create_employee", "update_employee", "create_time_off"],
        "chat_commands": [
            "create employee",
            "update employee record",
            "request time off",
        ],
        "last_checked": datetime.now().isoformat(),
    },
}


@service_registry_bp.route("/api/services", methods=["GET"])
def get_services():
    """Get all registered services and their status"""
    try:
        services_list = []

        for service_id, service_data in SERVICE_REGISTRY.items():
            service_info = {"id": service_id, **service_data}
            services_list.append(service_info)

        response = {
            "success": True,
            "services": services_list,
            "total_services": len(services_list),
            "active_services": len(
                [
                    s
                    for s in services_list
                    if s["status"] == "connected" or s["status"] == "active"
                ]
            ),
            "workflow_integrated_services": len(
                [
                    s
                    for s in services_list
                    if s.get("workflow_triggers") or s.get("workflow_actions")
                ]
            ),
            "chat_integrated_services": len(
                [s for s in services_list if s.get("chat_commands")]
            ),
            "timestamp": datetime.now().isoformat(),
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error getting services: {str(e)}")
        return jsonify(
            {
                "success": False,
                "error": "Failed to retrieve services",
                "services": [],
                "total_services": 0,
                "active_services": 0,
            }
        ), 500


@service_registry_bp.route("/api/services/<service_id>", methods=["GET"])
def get_service(service_id):
    """Get specific service details"""
    try:
        if service_id not in SERVICE_REGISTRY:
            return jsonify(
                {"success": False, "error": f"Service '{service_id}' not found"}
            ), 404

        service_data = SERVICE_REGISTRY[service_id]
        response = {"success": True, "service": {"id": service_id, **service_data}}

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error getting service {service_id}: {str(e)}")
        return jsonify(
            {"success": False, "error": f"Failed to retrieve service {service_id}"}
        ), 500


@service_registry_bp.route("/api/services/health", methods=["GET"])
def get_services_health():
    """Get overall services health status"""
    try:
        services_list = []
        healthy_count = 0

        for service_id, service_data in SERVICE_REGISTRY.items():
            is_healthy = service_data["health"] == "healthy"
            if is_healthy:
                healthy_count += 1

            services_list.append(
                {
                    "id": service_id,
                    "name": service_data["name"],
                    "health": service_data["health"],
                    "status": service_data["status"],
                }
            )

        total_services = len(services_list)
        health_percentage = (
            (healthy_count / total_services) * 100 if total_services > 0 else 0
        )

        overall_health = (
            "healthy"
            if health_percentage >= 80
            else "degraded"
            if health_percentage >= 50
            else "unhealthy"
        )

        response = {
            "success": True,
            "overall_health": overall_health,
            "health_percentage": health_percentage,
            "healthy_services": healthy_count,
            "total_services": total_services,
            "services": services_list,
            "timestamp": datetime.now().isoformat(),
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error getting services health: {str(e)}")
        return jsonify(
            {"success": False, "error": "Failed to retrieve services health"}
        ), 500


@service_registry_bp.route("/api/services/status", methods=["GET"])
def get_services_status():
    """Get services status summary"""
    try:
        status_counts = {"connected": 0, "active": 0, "disconnected": 0, "error": 0}

        for service_data in SERVICE_REGISTRY.values():
            status = service_data["status"]
            if status in status_counts:
                status_counts[status] += 1

        response = {
            "success": True,
            "status_summary": status_counts,
            "total_services": len(SERVICE_REGISTRY),
            "timestamp": datetime.now().isoformat(),
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error getting services status: {str(e)}")
        return jsonify(
            {"success": False, "error": "Failed to retrieve services status"}
        ), 500


@service_registry_bp.route("/api/services/workflow-capabilities", methods=["GET"])
def get_workflow_capabilities():
    """Get all services with workflow automation capabilities"""
    try:
        workflow_services = []

        for service_id, service_data in SERVICE_REGISTRY.items():
            if service_data.get("workflow_triggers") or service_data.get(
                "workflow_actions"
            ):
                workflow_service = {
                    "id": service_id,
                    "name": service_data["name"],
                    "triggers": service_data.get("workflow_triggers", []),
                    "actions": service_data.get("workflow_actions", []),
                    "type": service_data["type"],
                }
                workflow_services.append(workflow_service)

        response = {
            "success": True,
            "workflow_services": workflow_services,
            "total_workflow_services": len(workflow_services),
            "timestamp": datetime.now().isoformat(),
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error getting workflow capabilities: {str(e)}")
        return jsonify(
            {"success": False, "error": "Failed to retrieve workflow capabilities"}
        ), 500


@service_registry_bp.route("/api/services/chat-commands", methods=["GET"])
def get_chat_commands():
    """Get all available chat commands across services"""
    try:
        chat_commands = []

        for service_id, service_data in SERVICE_REGISTRY.items():
            if service_data.get("chat_commands"):
                for command in service_data["chat_commands"]:
                    chat_commands.append(
                        {
                            "command": command,
                            "service_id": service_id,
                            "service_name": service_data["name"],
                            "description": service_data["description"],
                        }
                    )

        response = {
            "success": True,
            "chat_commands": chat_commands,
            "total_commands": len(chat_commands),
            "timestamp": datetime.now().isoformat(),
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error getting chat commands: {str(e)}")
        return jsonify(
            {"success": False, "error": "Failed to retrieve chat commands"}
        ), 500


@service_registry_bp.route("/api/services/integration-status", methods=["GET"])
def get_integration_status():
    """Get comprehensive integration status for workflow and chat"""
    try:
        integration_status = {
            "workflow_automation": {
                "total_services": len(SERVICE_REGISTRY),
                "workflow_enabled": 0,
                "triggers_available": 0,
                "actions_available": 0,
            },
            "chat_interface": {
                "total_services": len(SERVICE_REGISTRY),
                "chat_enabled": 0,
                "commands_available": 0,
            },
        }

        for service_data in SERVICE_REGISTRY.values():
            # Workflow automation stats
            if service_data.get("workflow_triggers"):
                integration_status["workflow_automation"]["workflow_enabled"] += 1
                integration_status["workflow_automation"]["triggers_available"] += len(
                    service_data["workflow_triggers"]
                )
            if service_data.get("workflow_actions"):
                integration_status["workflow_automation"]["actions_available"] += len(
                    service_data["workflow_actions"]
                )

            # Chat interface stats
            if service_data.get("chat_commands"):
                integration_status["chat_interface"]["chat_enabled"] += 1
                integration_status["chat_interface"]["commands_available"] += len(
                    service_data["chat_commands"]
                )

        response = {
            "success": True,
            "integration_status": integration_status,
            "timestamp": datetime.now().isoformat(),
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error getting integration status: {str(e)}")
        return jsonify(
            {"success": False, "error": "Failed to retrieve integration status"}
        ), 500


@service_registry_bp.route("/api/services/register-workflow", methods=["POST"])
def register_workflow_for_service():
    """Register a workflow for a specific service"""
    try:
        data = request.get_json()
        service_id = data.get("service_id")
        workflow_config = data.get("workflow_config", {})

        if not service_id:
            return jsonify({"success": False, "error": "service_id is required"}), 400

        if service_id not in SERVICE_REGISTRY:
            return jsonify(
                {"success": False, "error": f"Service '{service_id}' not found"}
            ), 404

        # In a real implementation, this would store the workflow configuration
        # For now, we'll just return a success response
        workflow_id = str(uuid.uuid4())

        response = {
            "success": True,
            "workflow_id": workflow_id,
            "service_id": service_id,
            "workflow_config": workflow_config,
            "message": f"Workflow registered for {service_id}",
            "timestamp": datetime.now().isoformat(),
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error registering workflow: {str(e)}")
        return jsonify(
            {"success": False, "error": f"Failed to register workflow: {str(e)}"}
        ), 500


@service_registry_bp.route("/api/services/test-chat-command", methods=["POST"])
def test_chat_command():
    """Test a chat command for a specific service"""
    try:
        data = request.get_json()
        service_id = data.get("service_id")
        command = data.get("command")

        if not service_id or not command:
            return jsonify(
                {"success": False, "error": "service_id and command are required"}
            ), 400

        if service_id not in SERVICE_REGISTRY:
            return jsonify(
                {"success": False, "error": f"Service '{service_id}' not found"}
            ), 404

        service_data = SERVICE_REGISTRY[service_id]
        available_commands = service_data.get("chat_commands", [])

        if command not in available_commands:
            return jsonify(
                {
                    "success": False,
                    "error": f"Command '{command}' not available for {service_id}",
                    "available_commands": available_commands,
                }
            ), 400

        # Simulate command execution
        # In a real implementation, this would execute the actual command
        response = {
            "success": True,
            "service_id": service_id,
            "command": command,
            "result": f"Command '{command}' executed successfully for {service_data['name']}",
            "simulated": True,
            "timestamp": datetime.now().isoformat(),
        }

        return jsonify(response)

    except Exception as e:
        logger.error(f"Error testing chat command: {str(e)}")
        return jsonify(
            {"success": False, "error": f"Failed to test chat command: {str(e)}"}
        ), 500


# Register error handlers
@service_registry_bp.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "error": "Endpoint not found"}), 404


@service_registry_bp.errorhandler(405)
def method_not_allowed(error):
    return jsonify({"success": False, "error": "Method not allowed"}), 405


@service_registry_bp.errorhandler(500)
def internal_server_error(error):
    return jsonify({"success": False, "error": "Internal server error"}), 500
