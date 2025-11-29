import json
import os
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

class WorkflowTemplate(BaseModel):
    id: str
    name: str
    description: str
    category: str
    author: str
    version: str
    integrations: List[str]
    complexity: str  # "Beginner", "Intermediate", "Advanced"
    workflow_data: Dict[str, Any]
    created_at: str
    downloads: int = 0
    rating: float = 0.0

class MarketplaceEngine:
    def __init__(self):
        self.templates_dir = os.path.join(os.path.dirname(__file__), "..", "marketplace_templates")
        os.makedirs(self.templates_dir, exist_ok=True)
        self._initialize_default_templates()

    def _initialize_default_templates(self):
        """Create default templates if they don't exist"""
        defaults = [
            {
                "id": "tmpl_email_summarizer",
                "name": "Daily Email Summarizer",
                "description": "Summarize unread emails from Gmail and send a digest to Slack.",
                "category": "Productivity",
                "author": "ATOM Team",
                "version": "1.0.0",
                "integrations": ["gmail", "slack", "openai"],
                "complexity": "Beginner",
                "workflow_data": {
                    "nodes": [
                        {"id": "1", "type": "trigger", "label": "Every Morning", "config": {"cron": "0 9 * * *"}},
                        {"id": "2", "type": "action", "label": "Fetch Unread Emails", "config": {"integration": "gmail", "action": "list_messages", "query": "is:unread"}},
                        {"id": "3", "type": "action", "label": "Summarize with AI", "config": {"integration": "openai", "action": "summarize"}},
                        {"id": "4", "type": "action", "label": "Send to Slack", "config": {"integration": "slack", "action": "send_message"}}
                    ],
                    "edges": [
                        {"source": "1", "target": "2"},
                        {"source": "2", "target": "3"},
                        {"source": "3", "target": "4"}
                    ]
                }
            },
            {
                "id": "tmpl_lead_enrichment",
                "name": "Sales Lead Enrichment",
                "description": "When a new lead is added to Salesforce, enrich with LinkedIn data and notify team.",
                "category": "Sales",
                "author": "ATOM Team",
                "version": "1.0.0",
                "integrations": ["salesforce", "linkedin", "slack"],
                "complexity": "Intermediate",
                "workflow_data": {
                    "nodes": [
                        {"id": "1", "type": "trigger", "label": "New Salesforce Lead", "config": {"integration": "salesforce", "event": "new_record", "object": "Lead"}},
                        {"id": "2", "type": "action", "label": "Enrich from LinkedIn", "config": {"integration": "linkedin", "action": "get_profile"}},
                        {"id": "3", "type": "action", "label": "Update Salesforce", "config": {"integration": "salesforce", "action": "update_record"}},
                        {"id": "4", "type": "action", "label": "Notify Sales Channel", "config": {"integration": "slack", "action": "send_message"}}
                    ],
                    "edges": [
                        {"source": "1", "target": "2"},
                        {"source": "2", "target": "3"},
                        {"source": "3", "target": "4"}
                    ]
                }
            },
            {
                "id": "tmpl_meeting_notes",
                "name": "Automated Meeting Notes",
                "description": "Transcribe Zoom recording, generate action items, and save to Notion.",
                "category": "Productivity",
                "author": "ATOM Team",
                "version": "1.0.0",
                "integrations": ["zoom", "openai", "notion"],
                "complexity": "Advanced",
                "workflow_data": {
                    "nodes": [
                        {"id": "1", "type": "trigger", "label": "New Zoom Recording", "config": {"integration": "zoom", "event": "recording_completed"}},
                        {"id": "2", "type": "action", "label": "Transcribe Audio", "config": {"integration": "openai", "action": "transcribe"}},
                        {"id": "3", "type": "action", "label": "Extract Action Items", "config": {"integration": "openai", "action": "extract_tasks"}},
                        {"id": "4", "type": "action", "label": "Create Notion Page", "config": {"integration": "notion", "action": "create_page"}}
                    ],
                    "edges": [
                        {"source": "1", "target": "2"},
                        {"source": "2", "target": "3"},
                        {"source": "3", "target": "4"}
                    ]
                }
            }
        ]

        for tmpl in defaults:
            path = os.path.join(self.templates_dir, f"{tmpl['id']}.json")
            if not os.path.exists(path):
                # Add metadata fields
                tmpl["created_at"] = datetime.now().isoformat()
                tmpl["downloads"] = 0
                tmpl["rating"] = 5.0
                with open(path, "w") as f:
                    json.dump(tmpl, f, indent=2)

    def list_templates(self, category: Optional[str] = None) -> List[WorkflowTemplate]:
        """List available workflow templates"""
        templates = []
        for filename in os.listdir(self.templates_dir):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(self.templates_dir, filename), "r") as f:
                        data = json.load(f)
                        if category and data.get("category") != category:
                            continue
                        templates.append(WorkflowTemplate(**data))
                except Exception as e:
                    print(f"Error loading template {filename}: {e}")
        return templates

    def get_template(self, template_id: str) -> Optional[WorkflowTemplate]:
        """Get a specific template by ID"""
        path = os.path.join(self.templates_dir, f"{template_id}.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
                # Increment download count
                data["downloads"] += 1
                with open(path, "w") as fw:
                    json.dump(data, fw, indent=2)
                return WorkflowTemplate(**data)
        return None

    def import_workflow(self, workflow_json: Dict[str, Any]) -> Dict[str, Any]:
        """Import a workflow into the user's workspace"""
        # Validate workflow structure
        if "nodes" not in workflow_json or "edges" not in workflow_json:
            raise ValueError("Invalid workflow structure: missing nodes or edges")
        
        # In a real app, we would save this to the user's DB
        # For now, we just return the validated data to be used by the frontend
        return {
            "id": str(uuid.uuid4()),
            "name": f"Imported: {workflow_json.get('name', 'Untitled Workflow')}",
            "nodes": workflow_json["nodes"],
            "edges": workflow_json["edges"],
            "imported_at": datetime.now().isoformat()
        }

# API Router
router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])
marketplace = MarketplaceEngine()

@router.get("/templates", response_model=List[WorkflowTemplate])
async def get_templates(category: Optional[str] = None):
    return marketplace.list_templates(category)

@router.get("/templates/{template_id}", response_model=WorkflowTemplate)
async def get_template_details(template_id: str):
    template = marketplace.get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template

@router.post("/import")
async def import_workflow(file: UploadFile = File(...)):
    try:
        content = await file.read()
        workflow_data = json.loads(content)
        return marketplace.import_workflow(workflow_data)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
