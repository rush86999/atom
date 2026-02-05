"""
Industry-Specific Workflow Templates
Pre-built workflow templates tailored for different industries and use cases
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json
import os
from typing import Any, Dict, List, Optional


class Industry(Enum):
    """Industry categories for workflow templates"""
    HEALTHCARE = "healthcare"
    FINANCE = "finance"
    EDUCATION = "education"
    RETAIL = "retail"
    MANUFACTURING = "manufacturing"
    REAL_ESTATE = "real_estate"
    LEGAL = "legal"
    NON_PROFIT = "non_profit"
    TECHNOLOGY = "technology"
    CONSULTING = "consulting"
    HOSPITALITY = "hospitality"
    LOGISTICS = "logistics"

@dataclass
class IndustryWorkflowTemplate:
    """Industry-specific workflow template"""
    id: str
    name: str
    description: str
    industry: Industry
    sub_category: str
    complexity: str  # "Beginner", "Intermediate", "Advanced"
    estimated_time_savings: str  # e.g., "5 hours/week"
    required_integrations: List[str]
    optional_integrations: List[str]
    workflow_data: Dict[str, Any]
    setup_instructions: List[str]
    benefits: List[str]
    use_cases: List[str]
    compliance_notes: Optional[List[str]] = None
    created_at: str = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

class IndustryWorkflowEngine:
    """Manages industry-specific workflow templates"""

    def __init__(self):
        self.templates: Dict[str, IndustryWorkflowTemplate] = {}
        self._initialize_industry_templates()

    def _initialize_industry_templates(self):
        """Initialize industry-specific workflow templates"""

        # Healthcare Templates
        self.templates["healthcare_patient_onboarding"] = IndustryWorkflowTemplate(
            id="healthcare_patient_onboarding",
            name="Automated Patient Onboarding",
            description="Streamline patient registration, insurance verification, and appointment scheduling",
            industry=Industry.HEALTHCARE,
            sub_category="Patient Management",
            complexity="Intermediate",
            estimated_time_savings="8 hours/week",
            required_integrations=["salesforce_health_cloud", "zoom", "gmail"],
            optional_integrations=["slack", "calendly"],
            workflow_data={
                "nodes": [
                    {
                        "id": "1",
                        "type": "trigger",
                        "label": "New Patient Registration",
                        "config": {
                            "integration": "salesforce_health_cloud",
                            "event": "new_patient",
                            "object": "Patient"
                        }
                    },
                    {
                        "id": "2",
                        "type": "action",
                        "label": "Verify Insurance",
                        "config": {
                            "integration": "salesforce_health_cloud",
                            "action": "verify_insurance",
                            "api": "insurance_verification"
                        }
                    },
                    {
                        "id": "3",
                        "type": "condition",
                        "label": "Insurance Approved?",
                        "config": {
                            "conditions": [{"field": "insurance_status", "operator": "equals", "value": "approved"}]
                        }
                    },
                    {
                        "id": "4",
                        "type": "action",
                        "label": "Schedule Initial Consultation",
                        "config": {
                            "integration": "calendly",
                            "action": "create_event",
                            "event_type": "new_patient_consultation"
                        }
                    },
                    {
                        "id": "5",
                        "type": "action",
                        "label": "Send Welcome Email",
                        "config": {
                            "integration": "gmail",
                            "action": "send_template",
                            "template_id": "patient_welcome"
                        }
                    },
                    {
                        "id": "6",
                        "type": "action",
                        "label": "Notify Staff",
                        "config": {
                            "integration": "slack",
                            "action": "send_message",
                            "channel": "#patient-updates"
                        }
                    }
                ],
                "edges": [
                    {"source": "1", "target": "2"},
                    {"source": "2", "target": "3"},
                    {"source": "3", "target": "4", "condition": "yes"},
                    {"source": "4", "target": "5"},
                    {"source": "5", "target": "6"}
                ]
            },
            setup_instructions=[
                "Connect Salesforce Health Cloud with patient data model",
                "Configure insurance verification API endpoints",
                "Set up Calendly event types for consultations",
                "Create email templates for patient communications",
                "Configure Slack notifications for staff"
            ],
            benefits=[
                "Reduce manual patient onboarding time by 70%",
                "Automate insurance verification process",
                "Improve patient experience with instant scheduling",
                "Ensure compliance with healthcare regulations",
                "Reduce administrative workload"
            ],
            use_cases=[
                "Private medical practices",
                "Dental clinics",
                "Specialty healthcare providers",
                "Multi-location healthcare systems"
            ],
            compliance_notes=[
                "Ensure HIPAA compliance for all patient data",
                "Maintain secure communication channels",
                "Follow healthcare data retention policies",
                "Obtain necessary patient consents for automation"
            ]
        )

        # Finance Templates
        self.templates["finance_expense_approval"] = IndustryWorkflowTemplate(
            id="finance_expense_approval",
            name="Automated Expense Approval",
            description="Streamline expense submission, approval, and reimbursement process",
            industry=Industry.FINANCE,
            sub_category="Expense Management",
            complexity="Intermediate",
            estimated_time_savings="10 hours/week",
            required_integrations=["quickbooks", "slack", "gmail"],
            optional_integrations=["zendesk", "dropbox"],
            workflow_data={
                "nodes": [
                    {
                        "id": "1",
                        "type": "trigger",
                        "label": "New Expense Submission",
                        "config": {
                            "integration": "quickbooks",
                            "event": "expense_created",
                            "object": "Purchase"
                        }
                    },
                    {
                        "id": "2",
                        "type": "action",
                        "label": "Validate Expense Policy",
                        "config": {
                            "integration": "openai",
                            "action": "validate_expense",
                            "policy_rules": ["amount_limits", "category_rules", "receipt_required"]
                        }
                    },
                    {
                        "id": "3",
                        "type": "condition",
                        "label": "Auto-Approve?",
                        "config": {
                            "conditions": [
                                {"field": "amount", "operator": "less_than", "value": 100},
                                {"field": "policy_compliant", "operator": "equals", "value": True}
                            ]
                        }
                    },
                    {
                        "id": "4",
                        "type": "action",
                        "label": "Send for Manager Approval",
                        "config": {
                            "integration": "slack",
                            "action": "send_approval_request",
                            "channel": "#expense-approvals"
                        }
                    },
                    {
                        "id": "5",
                        "type": "action",
                        "label": "Process Reimbursement",
                        "config": {
                            "integration": "quickbooks",
                            "action": "create_reimbursement",
                            "auto_pay": True
                        }
                    },
                    {
                        "id": "6",
                        "type": "action",
                        "label": "Notify Employee",
                        "config": {
                            "integration": "gmail",
                            "action": "send_template",
                            "template_id": "expense_approved"
                        }
                    }
                ],
                "edges": [
                    {"source": "1", "target": "2"},
                    {"source": "2", "target": "3"},
                    {"source": "3", "target": "5", "condition": "yes"},
                    {"source": "3", "target": "4", "condition": "no"},
                    {"source": "4", "target": "5"},
                    {"source": "5", "target": "6"}
                ]
            },
            setup_instructions=[
                "Configure QuickBooks expense categories",
                "Set up Slack approval workflows",
                "Create expense policy validation rules",
                "Configure automated reimbursement settings",
                "Create email notification templates"
            ],
            benefits=[
                "Reduce expense processing time by 80%",
                "Automate policy compliance checking",
                "Faster reimbursement for employees",
                "Better expense visibility and control",
                "Reduced manual errors"
            ],
            use_cases=[
                "Corporate expense management",
                "Small business expense tracking",
                "Non-profit expense processing",
                "Startup reimbursement systems"
            ]
        )

        # Education Templates
        self.templates["education_student_enrollment"] = IndustryWorkflowTemplate(
            id="education_student_enrollment",
            name="Automated Student Enrollment",
            description="Manage student applications, enrollment, and onboarding process",
            industry=Industry.EDUCATION,
            sub_category="Student Management",
            complexity="Advanced",
            estimated_time_savings="15 hours/week",
            required_integrations=["salesforce", "gmail", "zoom"],
            optional_integrations=["notion", "slack", "calendly"],
            workflow_data={
                "nodes": [
                    {
                        "id": "1",
                        "type": "trigger",
                        "label": "New Student Application",
                        "config": {
                            "integration": "salesforce",
                            "event": "new_application",
                            "object": "Application__c"
                        }
                    },
                    {
                        "id": "2",
                        "type": "action",
                        "label": "Application Review",
                        "config": {
                            "integration": "openai",
                            "action": "analyze_application",
                            "check_criteria": ["grades", "essay", "recommendations"]
                        }
                    },
                    {
                        "id": "3",
                        "type": "action",
                        "label": "Schedule Interview",
                        "config": {
                            "integration": "calendly",
                            "action": "create_event",
                            "event_type": "student_interview"
                        }
                    },
                    {
                        "id": "4",
                        "type": "condition",
                        "label": "Application Approved?",
                        "config": {
                            "conditions": [{"field": "approval_status", "operator": "equals", "value": "approved"}]
                        }
                    },
                    {
                        "id": "5",
                        "type": "action",
                        "label": "Create Student Record",
                        "config": {
                            "integration": "salesforce",
                            "action": "create_student",
                            "object": "Student__c"
                        }
                    },
                    {
                        "id": "6",
                        "type": "action",
                        "label": "Send Acceptance Package",
                        "config": {
                            "integration": "gmail",
                            "action": "send_template",
                            "template_id": "acceptance_package"
                        }
                    },
                    {
                        "id": "7",
                        "type": "action",
                        "label": "Setup Orientation",
                        "config": {
                            "integration": "zoom",
                            "action": "schedule_meeting",
                            "meeting_type": "orientation"
                        }
                    }
                ],
                "edges": [
                    {"source": "1", "target": "2"},
                    {"source": "2", "target": "3"},
                    {"source": "3", "target": "4"},
                    {"source": "4", "target": "5", "condition": "yes"},
                    {"source": "5", "target": "6"},
                    {"source": "6", "target": "7"}
                ]
            },
            setup_instructions=[
                "Configure Salesforce Education Cloud",
                "Set up application evaluation criteria",
                "Create Calendly interview scheduling",
                "Prepare acceptance email templates",
                "Configure Zoom orientation sessions"
            ],
            benefits=[
                "Reduce enrollment processing time by 60%",
                "Automate application evaluation",
                "Improve applicant experience",
                "Streamline student onboarding",
                "Better data organization"
            ],
            use_cases=[
                "University admissions",
                "K-12 school enrollment",
                "Online course registration",
                "Training program enrollment"
            ]
        )

        # Retail Templates
        self.templates["retail_inventory_management"] = IndustryWorkflowTemplate(
            id="retail_inventory_management",
            name="Smart Inventory Management",
            description="Automated inventory tracking, reordering, and supplier coordination",
            industry=Industry.RETAIL,
            sub_category="Inventory",
            complexity="Intermediate",
            estimated_time_savings="12 hours/week",
            required_integrations=["shopify", "quickbooks", "gmail"],
            optional_integrations=["slack", "zendesk"],
            workflow_data={
                "nodes": [
                    {
                        "id": "1",
                        "type": "trigger",
                        "label": "Low Stock Alert",
                        "config": {
                            "integration": "shopify",
                            "event": "inventory_low",
                            "threshold": 10
                        }
                    },
                    {
                        "id": "2",
                        "type": "action",
                        "label": "Analyze Sales Trends",
                        "config": {
                            "integration": "openai",
                            "action": "analyze_sales_trends",
                            "lookback_days": 30
                        }
                    },
                    {
                        "id": "3",
                        "type": "action",
                        "label": "Calculate Optimal Order",
                        "config": {
                            "integration": "openai",
                            "action": "calculate_reorder",
                            "factors": ["seasonality", "trends", "lead_time"]
                        }
                    },
                    {
                        "id": "4",
                        "type": "action",
                        "label": "Create Purchase Order",
                        "config": {
                            "integration": "quickbooks",
                            "action": "create_purchase_order"
                        }
                    },
                    {
                        "id": "5",
                        "type": "action",
                        "label": "Notify Manager",
                        "config": {
                            "integration": "slack",
                            "action": "send_message",
                            "channel": "#inventory"
                        }
                    }
                ],
                "edges": [
                    {"source": "1", "target": "2"},
                    {"source": "2", "target": "3"},
                    {"source": "3", "target": "4"},
                    {"source": "4", "target": "5"}
                ]
            },
            setup_instructions=[
                "Configure Shopify inventory thresholds",
                "Set up QuickBooks purchase order system",
                "Configure supplier information",
                "Set up Slack notifications",
                "Create inventory analysis rules"
            ],
            benefits=[
                "Prevent stockouts automatically",
                "Optimize inventory levels",
                "Reduce manual ordering effort",
                "Better cash flow management",
                "Improve supplier relationships"
            ],
            use_cases=[
                "E-commerce stores",
                "Retail chains",
                "Small businesses",
                "Warehouse management"
            ]
        )

        # Real Estate Templates
        self.templates["real_estate_client_onboarding"] = IndustryWorkflowTemplate(
            id="real_estate_client_onboarding",
            name="Real Estate Client Onboarding",
            description="Automate client intake, property matching, and communication workflow",
            industry=Industry.REAL_ESTATE,
            sub_category="Client Management",
            complexity="Intermediate",
            estimated_time_savings="8 hours/week",
            required_integrations=["salesforce", "gmail", "zillow"],
            optional_integrations=["slack", "calendly", "notion"],
            workflow_data={
                "nodes": [
                    {
                        "id": "1",
                        "type": "trigger",
                        "label": "New Client Lead",
                        "config": {
                            "integration": "salesforce",
                            "event": "new_lead",
                            "object": "Lead"
                        }
                    },
                    {
                        "id": "2",
                        "type": "action",
                        "label": "Search Matching Properties",
                        "config": {
                            "integration": "zillow",
                            "action": "search_properties",
                            "match_criteria": ["budget", "location", "preferences"]
                        }
                    },
                    {
                        "id": "3",
                        "type": "action",
                        "label": "Create Property Portfolio",
                        "config": {
                            "integration": "notion",
                            "action": "create_database",
                            "template": "property_portfolio"
                        }
                    },
                    {
                        "id": "4",
                        "type": "action",
                        "label": "Schedule Property Tours",
                        "config": {
                            "integration": "calendly",
                            "action": "create_events",
                            "event_type": "property_tour"
                        }
                    },
                    {
                        "id": "5",
                        "type": "action",
                        "label": "Send Welcome Package",
                        "config": {
                            "integration": "gmail",
                            "action": "send_template",
                            "template_id": "client_welcome"
                        }
                    }
                ],
                "edges": [
                    {"source": "1", "target": "2"},
                    {"source": "2", "target": "3"},
                    {"source": "3", "target": "4"},
                    {"source": "4", "target": "5"}
                ]
            },
            setup_instructions=[
                "Configure Salesforce real estate objects",
                "Set up Zillow API access",
                "Create Notion property templates",
                "Configure Calendly tour scheduling",
                "Prepare client communication templates"
            ],
            benefits=[
                "Automate property matching process",
                "Improve client response time",
                "Organized property management",
                "Professional client experience",
                "Reduced administrative work"
            ],
            use_cases=[
                "Real estate agencies",
                "Property management companies",
                "Individual real estate agents",
                "Rental property services"
            ]
        )

        # Legal Templates
        self.templates["legal_case_management"] = IndustryWorkflowTemplate(
            id="legal_case_management",
            name="Legal Case Intake Management",
            description="Streamline client intake, document collection, and case assignment",
            industry=Industry.LEGAL,
            sub_category="Case Management",
            complexity="Advanced",
            estimated_time_savings="10 hours/week",
            required_integrations=["salesforce", "gmail", "dropbox"],
            optional_integrations=["slack", "zoom"],
            workflow_data={
                "nodes": [
                    {
                        "id": "1",
                        "type": "trigger",
                        "label": "New Case Inquiry",
                        "config": {
                            "integration": "salesforce",
                            "event": "new_case",
                            "object": "Case__c"
                        }
                    },
                    {
                        "id": "2",
                        "type": "action",
                        "label": "Document Collection",
                        "config": {
                            "integration": "dropbox",
                            "action": "create_folder",
                            "folder_structure": "client_documents"
                        }
                    },
                    {
                        "id": "3",
                        "type": "action",
                        "label": "Conflict Check",
                        "config": {
                            "integration": "openai",
                            "action": "check_conflicts",
                            "search_criteria": ["names", "companies", "matters"]
                        }
                    },
                    {
                        "id": "4",
                        "type": "condition",
                        "label": "No Conflicts?",
                        "config": {
                            "conditions": [{"field": "conflict_detected", "operator": "equals", "value": False}]
                        }
                    },
                    {
                        "id": "5",
                        "type": "action",
                        "label": "Assign Attorney",
                        "config": {
                            "integration": "salesforce",
                            "action": "assign_attorney",
                            "assignment_rules": ["specialty", "workload"]
                        }
                    },
                    {
                        "id": "6",
                        "type": "action",
                        "label": "Send Retainer Package",
                        "config": {
                            "integration": "gmail",
                            "action": "send_template",
                            "template_id": "retainer_package"
                        }
                    }
                ],
                "edges": [
                    {"source": "1", "target": "2"},
                    {"source": "2", "target": "3"},
                    {"source": "3", "target": "4"},
                    {"source": "4", "target": "5", "condition": "yes"},
                    {"source": "5", "target": "6"}
                ]
            },
            setup_instructions=[
                "Configure Salesforce legal objects",
                "Set up Dropbox folder structures",
                "Create conflict check criteria",
                "Define attorney assignment rules",
                "Prepare legal document templates"
            ],
            benefits=[
                "Automate conflict checking",
                "Streamline document collection",
                "Optimize attorney assignment",
                "Improve client intake process",
                "Better case organization"
            ],
            use_cases=[
                "Law firms",
                "Legal clinics",
                "Corporate legal departments",
                "Solo practitioners"
            ],
            compliance_notes=[
                "Maintain attorney-client privilege",
                "Follow legal ethics requirements",
                "Secure document handling",
                "Comply with jurisdictional rules"
            ]
        )

        # Technology Templates
        self.templates["tech_content_file_management"] = IndustryWorkflowTemplate(
            id="tech_content_file_management",
            name="Content & File Management",
            description="Automatically archive, tag, or link new files from cloud storage to related tasks",
            industry=Industry.TECHNOLOGY,
            sub_category="File Management",
            complexity="Intermediate",
            estimated_time_savings="5 hours/week",
            required_integrations=["google_drive", "asana", "slack"],
            optional_integrations=["dropbox", "trello"],
            workflow_data={
                "nodes": [
                    {
                        "id": "1",
                        "type": "trigger",
                        "label": "New File in Drive",
                        "config": {
                            "integration": "google_drive",
                            "event": "new_file",
                            "folder": "root"
                        }
                    },
                    {
                        "id": "2",
                        "type": "action",
                        "label": "Analyze File Content",
                        "config": {
                            "integration": "openai",
                            "action": "extract_metadata",
                            "fields": ["project", "task_id", "priority"]
                        }
                    },
                    {
                        "id": "3",
                        "type": "action",
                        "label": "Link to Asana Task",
                        "config": {
                            "integration": "asana",
                            "action": "attach_file",
                            "task_id": "{{task_id}}"
                        }
                    },
                    {
                        "id": "4",
                        "type": "action",
                        "label": "Archive File",
                        "config": {
                            "integration": "google_drive",
                            "action": "move_file",
                            "target_folder": "Archive/{{project}}"
                        }
                    },
                    {
                        "id": "5",
                        "type": "action",
                        "label": "Notify Slack",
                        "config": {
                            "integration": "slack",
                            "action": "send_message",
                            "channel": "#file-updates"
                        }
                    }
                ],
                "edges": [
                    {"source": "1", "target": "2"},
                    {"source": "2", "target": "3"},
                    {"source": "3", "target": "4"},
                    {"source": "4", "target": "5"}
                ]
            },
            setup_instructions=[
                "Configure Google Drive folder monitoring",
                "Set up Asana project and task mapping",
                "Configure Slack notification channel",
                "Define archiving folder structure"
            ],
            benefits=[
                "Reduce manual file organization time by 90%",
                "Ensure all project files are correctly linked to tasks",
                "Maintain clean and organized cloud storage",
                "Improve team visibility on new document uploads"
            ],
            use_cases=[
                "Software development projects",
                "Marketing campaign management",
                "Design asset organization",
                "General business document management"
            ]
        )

    def get_templates_by_industry(self, industry: Industry) -> List[IndustryWorkflowTemplate]:
        """Get all templates for a specific industry"""
        return [template for template in self.templates.values() if template.industry == industry]

    def get_template_by_id(self, template_id: str) -> Optional[IndustryWorkflowTemplate]:
        """Get a specific template by ID"""
        return self.templates.get(template_id)

    def get_all_industries(self) -> List[Industry]:
        """Get list of all supported industries"""
        return list(set(template.industry for template in self.templates.values()))

    def search_templates(
        self,
        industry: Optional[Industry] = None,
        complexity: Optional[str] = None,
        keywords: Optional[List[str]] = None
    ) -> List[IndustryWorkflowTemplate]:
        """Search templates with filters"""
        results = list(self.templates.values())

        if industry:
            results = [t for t in results if t.industry == industry]

        if complexity:
            results = [t for t in results if t.complexity == complexity]

        if keywords:
            results = [
                t for t in results
                if any(
                    keyword.lower() in t.name.lower() or
                    keyword.lower() in t.description.lower() or
                    keyword.lower() in ' '.join(t.use_cases).lower()
                    for keyword in keywords
                )
            ]

        return results

    def calculate_roi(self, template_id: str, hourly_rate: float = 50.0) -> Dict[str, Any]:
        """Calculate ROI for implementing a template"""
        template = self.get_template_by_id(template_id)
        if not template:
            return {"error": "Template not found"}

        # Extract hours saved per week from description
        import re
        hours_match = re.search(r'(\d+)\s*hours?/?\s*week', template.estimated_time_savings.lower())
        if not hours_match:
            return {"error": "Could not calculate time savings"}

        hours_saved_per_week = int(hours_match.group(1))
        weekly_savings = hours_saved_per_week * hourly_rate
        monthly_savings = weekly_savings * 4.33
        annual_savings = monthly_savings * 12

        return {
            "template_id": template_id,
            "time_savings": {
                "hours_per_week": hours_saved_per_week,
                "weekly_savings": weekly_savings,
                "monthly_savings": monthly_savings,
                "annual_savings": annual_savings
            },
            "implementation": {
                "estimated_setup_hours": 8,
                "setup_cost": 8 * hourly_rate,
                "payback_period_weeks": (8 * hourly_rate) / weekly_savings if weekly_savings > 0 else "Never"
            }
        }

# Global industry workflow engine instance
_industry_workflow_engine = None

def get_industry_workflow_engine() -> IndustryWorkflowEngine:
    """Get the global industry workflow engine instance"""
    global _industry_workflow_engine
    if _industry_workflow_engine is None:
        _industry_workflow_engine = IndustryWorkflowEngine()
    return _industry_workflow_engine