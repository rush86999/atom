#!/usr/bin/env python3
import os
import sys
import json
import re
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from core.database import DATABASE_URL
from core.models import IntegrationCatalog, Base

def seed_integrations():
    print(f"Connecting to database: {DATABASE_URL}")
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Ensure table exists
    Base.metadata.create_all(engine)

    # Use a hardcoded list of integrations derived from the TypeScript file
    # This avoids parsing errors and dependency on the frontend file being in a specific state

    def make_obj(name):
        return {"id": name, "name": name.replace("_", " ").title()}

    integrations_data = [
        # CORE PIECES
        {
            "id": "atom-memory",
            "name": "Atom Memory",
            "description": "Store and retrieve data from Atom's intelligent memory system",
            "category": "core",
            "color": "#6366F1",
            "authType": "none",
            "triggers": [make_obj(x) for x in ["memory_updated", "pattern_detected", "insight_generated"]],
            "actions": [make_obj(x) for x in ["store_memory", "retrieve_memory", "search_memories", "create_embedding", "find_similar", "update_context", "ingest_document", "ingest_conversation", "create_knowledge_graph", "query_graph", "extract_entities", "summarize_memories"]],
            "popular": True
        },
        { "id": "loop", "name": "Loop", "description": "Iterate over arrays", "category": "core", "color": "#14B8A6", "authType": "none", "triggers": [], "actions": [make_obj(x) for x in ["for_each", "repeat", "loop_until"]] },
        { "id": "code", "name": "Code", "description": "Run custom code", "category": "core", "color": "#334155", "authType": "none", "triggers": [], "actions": [make_obj(x) for x in ["run_typescript", "run_javascript", "run_python"]] },
        { "id": "condition", "name": "Condition", "description": "Branch based on conditions", "category": "core", "color": "#F59E0B", "authType": "none", "triggers": [], "actions": [make_obj(x) for x in ["if_else", "switch", "filter"]] },
        { "id": "delay", "name": "Delay", "description": "Wait for time", "category": "core", "color": "#6366F1", "authType": "none", "triggers": [make_obj(x) for x in ["schedule", "cron"]], "actions": [make_obj(x) for x in ["wait", "wait_until"]] },
        { "id": "http", "name": "HTTP", "description": "Make HTTP requests", "category": "core", "color": "#EA580C", "authType": "none", "triggers": [make_obj(x) for x in ["webhook"]], "actions": [make_obj(x) for x in ["get", "post", "put", "delete", "patch"]] },

        # AI & ML PIECES
        { "id": "openai", "name": "OpenAI", "description": "GPT-4, DALL-E, Whisper", "category": "ai", "color": "#412991", "authType": "api_key", "triggers": [], "actions": [make_obj(x) for x in ["chat", "complete", "embed", "generate_image", "transcribe", "translate"]], "popular": True },
        { "id": "anthropic", "name": "Anthropic Claude", "description": "Claude AI models", "category": "ai", "color": "#CC785C", "authType": "api_key", "triggers": [], "actions": [make_obj(x) for x in ["chat", "complete", "analyze"]], "popular": True },

        # COMMUNICATION PIECES
        { "id": "slack", "name": "Slack", "description": "Team messaging", "category": "communication", "color": "#4A154B", "authType": "oauth2", "triggers": [make_obj(x) for x in ["message", "reaction", "mention", "channel_created"]], "actions": [make_obj(x) for x in ["send_message", "create_channel", "add_reaction", "upload_file", "update_status"]], "popular": True },
        { "id": "discord", "name": "Discord", "description": "Community platform", "category": "communication", "color": "#5865F2", "authType": "oauth2", "triggers": [make_obj(x) for x in ["message", "member_join"]], "actions": [make_obj(x) for x in ["send_message", "create_channel", "add_role"]], "popular": True },
        { "id": "gmail", "name": "Gmail", "description": "Email service", "category": "communication", "color": "#EA4335", "authType": "oauth2", "triggers": [make_obj(x) for x in ["new_email", "labeled"]], "actions": [make_obj(x) for x in ["send_email", "create_draft", "add_label"]], "popular": True },

        # CRM & SALES PIECES
        { "id": "salesforce", "name": "Salesforce", "description": "Enterprise CRM", "category": "crm", "color": "#00A1E0", "authType": "oauth2", "triggers": [make_obj(x) for x in ["new_lead", "deal_updated", "opportunity_won"]], "actions": [make_obj(x) for x in ["create_lead", "update_contact", "create_opportunity"]], "popular": True },
        { "id": "hubspot", "name": "HubSpot", "description": "Marketing & sales CRM", "category": "crm", "color": "#FF7A59", "authType": "oauth2", "triggers": [make_obj(x) for x in ["new_contact", "deal_stage_changed", "form_submitted"]], "actions": [make_obj(x) for x in ["create_contact", "update_deal", "add_to_list"]], "popular": True },

        # PRODUCTIVITY PIECES
        { "id": "notion", "name": "Notion", "description": "All-in-one workspace", "category": "productivity", "color": "#000000", "authType": "oauth2", "triggers": [make_obj(x) for x in ["page_created", "database_updated"]], "actions": [make_obj(x) for x in ["create_page", "update_database", "add_block"]], "popular": True },
        { "id": "google-calendar", "name": "Google Calendar", "description": "Calendar", "category": "productivity", "color": "#4285F4", "authType": "oauth2", "triggers": [make_obj(x) for x in ["event_created", "event_starting"]], "actions": [make_obj(x) for x in ["create_event", "update_event"]], "popular": True },

        # DEVELOPER PIECES
        { "id": "github", "name": "GitHub", "description": "Code hosting", "category": "developer", "color": "#181717", "authType": "oauth2", "triggers": [make_obj(x) for x in ["push", "pull_request", "issue_created", "star"]], "actions": [make_obj(x) for x in ["create_issue", "create_pr", "add_comment", "add_label"]], "popular": True },

        # STORAGE PIECES
        { "id": "google-drive", "name": "Google Drive", "description": "Cloud storage", "category": "storage", "color": "#4285F4", "authType": "oauth2", "triggers": [make_obj(x) for x in ["file_created", "file_updated"]], "actions": [make_obj(x) for x in ["upload_file", "create_folder", "share_file"]], "popular": True },
        { "id": "dropbox", "name": "Dropbox", "description": "Cloud storage", "category": "storage", "color": "#0061FF", "authType": "oauth2", "triggers": [make_obj(x) for x in ["file_added", "file_modified"]], "actions": [make_obj(x) for x in ["upload_file", "create_folder", "share_link"]], "popular": True },

        # ECOMMERCE PIECES
        { "id": "stripe", "name": "Stripe", "description": "Payment processing", "category": "ecommerce", "color": "#635BFF", "authType": "api_key", "triggers": [make_obj(x) for x in ["payment_succeeded", "subscription_created", "invoice_paid"]], "actions": [make_obj(x) for x in ["create_customer", "create_charge", "create_subscription"]], "popular": True },

        # FINANCE PIECES
        { "id": "quickbooks", "name": "QuickBooks", "description": "Accounting", "category": "finance", "color": "#2CA01C", "authType": "oauth2", "triggers": [make_obj(x) for x in ["invoice_created", "payment_received"]], "actions": [make_obj(x) for x in ["create_invoice", "create_customer"]], "popular": True },
        { "id": "xero", "name": "Xero", "description": "Accounting", "category": "finance", "color": "#13B5EA", "authType": "oauth2", "triggers": [make_obj(x) for x in ["invoice_created"]], "actions": [make_obj(x) for x in ["create_invoice", "create_contact"]], "popular": True },
    ]

    count = 0
    for p in integrations_data:
        # Check if already exists
        existing = session.query(IntegrationCatalog).filter_by(id=p['id']).first()

        if existing:
            # Update
            existing.name = p['name']
            existing.description = p.get('description', '')
            existing.category = p['category']
            existing.icon = p.get('icon', '')
            existing.color = p.get('color', '#6366F1')
            existing.auth_type = p.get('authType', 'none')
            existing.triggers = p.get('triggers', [])
            existing.actions = p.get('actions', [])
            existing.popular = p.get('popular', False)
        else:
            # Insert
            new_piece = IntegrationCatalog(
                id=p['id'],
                name=p['name'],
                description=p.get('description', ''),
                category=p['category'],
                icon=p.get('icon', ''),
                color=p.get('color', '#6366F1'),
                auth_type=p.get('authType', 'none'),
                triggers=p.get('triggers', []),
                actions=p.get('actions', []),
                popular=p.get('popular', False)
            )
            session.add(new_piece)

        count += 1

    session.commit()
    print(f"Successfully seeded {count} integrations into the database.")
    session.close()

if __name__ == "__main__":
    seed_integrations()
