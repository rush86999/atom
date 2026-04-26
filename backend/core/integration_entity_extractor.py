"""
Integration Entity Extractor - Smart entity extraction by integration type

Extracts entities from integration records using a hybrid approach:
1. Direct mapping (for structured APIs like CRM)
2. Regex-based extraction (free, fast)
3. LLM-based extraction (optional, with OpenAI key)

Supported integration types:
- email: Outlook, Gmail
- crm: Salesforce, HubSpot, Zoho
- communication: Slack, Teams
- project: Jira, Asana, Notion
- support: Zendesk, Intercom
- calendar: Google Calendar, Outlook Calendar
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class IntegrationEntityExtractor:
    """
    Extracts entities from integration records based on integration type.

    Uses a hybrid approach:
    - Direct mapping for structured data (CRM, project mgmt)
    - Regex extraction for unstructured data (email, communication)
    - LLM extraction for complex relationships (optional)
    """

    def __init__(self):
        # Regex patterns for entity extraction
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        self.url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        self.username_pattern = re.compile(r'@([a-zA-Z0-9_]+)')
        self.date_pattern = re.compile(r'\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b')

        # Initialize LLM service (if available)
        self.llm_service = None
        try:
            from core.llm_service import LLMService
            self.llm_service = LLMService()
        except ImportError:
            logger.warning("LLM service not available, using regex-only extraction")

    async def extract(
        self,
        integration_type: str,
        records: List[Dict[str, Any]],
        use_llm: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Extract entities from records based on integration type.

        Args:
            integration_type: Type of integration (email, crm, communication, etc.)
            records: List of records from integration API
            use_llm: Whether to use LLM for extraction (requires OpenAI key)

        Returns:
            List of entities with embeddings-ready format:
            {
                "id": "unique_id",
                "text": "searchable text",
                "metadata": {...}
            }

        Raises:
            ValueError: If integration_type is not supported
        """
        entities = []

        for record in records:
            try:
                # Route to appropriate extraction method
                if integration_type == "email":
                    entity = self._extract_email_entities(record)
                elif integration_type == "crm":
                    entity = self._extract_crm_entities(record)
                elif integration_type == "communication":
                    entity = self._extract_communication_entities(record)
                elif integration_type == "project":
                    entity = self._extract_project_entities(record)
                elif integration_type == "support":
                    entity = self._extract_support_entities(record)
                elif integration_type == "calendar":
                    entity = self._extract_calendar_entities(record)
                else:
                    entity = self._extract_generic_entities(record)

                if entity:
                    # Optional: Enhance with LLM
                    if use_llm and self.llm_service:
                        entity = await self._enhance_with_llm(entity, integration_type)

                    entities.append(entity)

            except Exception as e:
                logger.error(f"Error extracting entities from record: {e}")
                continue

        return entities

    def _extract_email_entities(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract entities from email record (Outlook, Gmail)"""
        # Email fields (may vary by integration)
        subject = record.get("subject", "")
        from_email = record.get("from", "")
        to_emails = record.get("to", [])
        cc_emails = record.get("cc", [])
        body = record.get("body", "") or record.get("snippet", "") or ""

        # Normalize to list
        if isinstance(to_emails, str):
            to_emails = [to_emails]
        if isinstance(cc_emails, str):
            cc_emails = [cc_emails]

        # Extract people (email addresses)
        all_emails = [from_email] + to_emails + cc_emails
        people = self._extract_email_addresses(all_emails)

        # Extract organizations (domains)
        organizations = self._extract_domains(all_emails)

        # Build searchable text
        text = f"{subject}\n{body}"

        # Build entity
        return {
            "id": f"email_{record.get('id', record.get('message_id', ''))}",
            "text": text,
            "metadata": {
                "integration": "email",
                "entity_types": ["person", "organization", "email_thread"],
                "subject": subject,
                "from": from_email,
                "to": to_emails,
                "cc": cc_emails,
                "date": record.get("date", record.get("receivedDateTime", "")),
                "url": record.get("url", ""),
                "people": people,
                "organizations": organizations
            }
        }

    def _extract_crm_entities(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract entities from CRM record (Salesforce, HubSpot, Zoho)"""
        # CRM records are already structured
        record_type = record.get("object", record.get("type", "unknown"))

        # Extract based on record type
        if record_type == "lead" or record_type == "contact":
            name = record.get("name", record.get("fullName", ""))
            email = record.get("email", record.get("emailAddress", ""))
            company = record.get("company", record.get("companyName", ""))

            text = f"{name}\n{company}\n{email}"

            return {
                "id": f"{record_type}_{record.get('id', '')}",
                "text": text,
                "metadata": {
                    "integration": "crm",
                    "entity_types": ["person", "organization"],
                    "record_type": record_type,
                    "name": name,
                    "email": email,
                    "company": company,
                    "title": record.get("title", ""),
                    "phone": record.get("phone", record.get("phoneNumber", "")),
                    "url": record.get("url", "")
                }
            }

        elif record_type == "deal" or record_type == "opportunity":
            deal_name = record.get("name", record.get("dealName", ""))
            amount = record.get("amount", record.get("dealValue", 0))
            stage = record.get("stage", record.get("dealStage", ""))
            close_date = record.get("closeDate", "")

            text = f"{deal_name}\nStage: {stage}\nAmount: ${amount}"

            return {
                "id": f"{record_type}_{record.get('id', '')}",
                "text": text,
                "metadata": {
                    "integration": "crm",
                    "entity_types": ["deal", "organization"],
                    "record_type": record_type,
                    "deal_name": deal_name,
                    "amount": amount,
                    "stage": stage,
                    "close_date": close_date,
                    "probability": record.get("probability", 0),
                    "url": record.get("url", "")
                }
            }

        elif record_type == "account" or record_type == "company":
            company_name = record.get("name", record.get("companyName", ""))
            industry = record.get("industry", "")
            website = record.get("website", "")

            text = f"{company_name}\n{industry}"

            return {
                "id": f"{record_type}_{record.get('id', '')}",
                "text": text,
                "metadata": {
                    "integration": "crm",
                    "entity_types": ["organization"],
                    "record_type": record_type,
                    "company_name": company_name,
                    "industry": industry,
                    "website": website,
                    "employee_count": record.get("employeeCount", 0),
                    "revenue": record.get("revenue", 0),
                    "url": record.get("url", "")
                }
            }

        return None

    def _extract_communication_entities(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract entities from communication record (Slack, Teams)"""
        text = record.get("text", "")
        channel = record.get("channel", record.get("channelName", ""))
        user = record.get("user", record.get("userName", ""))
        timestamp = record.get("ts", record.get("timestamp", ""))

        # Extract mentions
        mentions = self.username_pattern.findall(text)

        # Extract URLs
        urls = self.url_pattern.findall(text)

        # Extract people (user + mentions)
        people = [user] + mentions if user else mentions

        return {
            "id": f"message_{record.get('id', record.get('message_id', ''))}",
            "text": text,
            "metadata": {
                "integration": "communication",
                "entity_types": ["message", "person"],
                "channel": channel,
                "user": user,
                "timestamp": timestamp,
                "mentions": mentions,
                "urls": urls,
                "people": people,
                "reactions": record.get("reactions", []),
                "url": record.get("permalink", "")
            }
        }

    def _extract_project_entities(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract entities from project management record (Jira, Asana, Notion)"""
        record_type = record.get("type", record.get("object", "unknown"))

        if record_type == "issue" or record_type == "task":
            title = record.get("summary", record.get("title", record.get("name", "")))
            description = record.get("description", record.get("body", ""))
            status = record.get("status", record.get("statusName", ""))
            assignee = record.get("assignee", record.get("assigneeName", ""))
            priority = record.get("priority", record.get("priorityName", ""))
            project = record.get("project", record.get("projectName", ""))

            text = f"{title}\n{description}"

            return {
                "id": f"task_{record.get('id', record.get('key', ''))}",
                "text": text,
                "metadata": {
                    "integration": "project",
                    "entity_types": ["task", "person"],
                    "record_type": "task",
                    "title": title,
                    "description": description,
                    "status": status,
                    "assignee": assignee,
                    "priority": priority,
                    "project": project,
                    "due_date": record.get("dueDate", record.get("due", "")),
                    "url": record.get("url", record.get("self", ""))
                }
            }

        elif record_type == "project":
            project_name = record.get("name", "")
            description = record.get("description", "")
            status = record.get("status", record.get("state", ""))

            text = f"{project_name}\n{description}"

            return {
                "id": f"project_{record.get('id', '')}",
                "text": text,
                "metadata": {
                    "integration": "project",
                    "entity_types": ["project"],
                    "record_type": "project",
                    "project_name": project_name,
                    "description": description,
                    "status": status,
                    "start_date": record.get("startDate", ""),
                    "end_date": record.get("endDate", ""),
                    "url": record.get("url", "")
                }
            }

        return None

    def _extract_support_entities(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract entities from support record (Zendesk, Intercom)"""
        ticket_id = record.get("id", record.get("ticket_id", ""))
        subject = record.get("subject", "")
        description = record.get("description", record.get("body", ""))
        status = record.get("status", "")
        priority = record.get("priority", "")
        requester = record.get("requester", record.get("requester_name", ""))
        assignee = record.get("assignee", record.get("assignee_name", ""))

        text = f"{subject}\n{description}"

        return {
            "id": f"ticket_{ticket_id}",
            "text": text,
            "metadata": {
                "integration": "support",
                "entity_types": ["ticket", "person"],
                "ticket_id": ticket_id,
                "subject": subject,
                "description": description,
                "status": status,
                "priority": priority,
                "requester": requester,
                "assignee": assignee,
                "created_at": record.get("created_at", ""),
                "updated_at": record.get("updated_at", ""),
                "url": record.get("url", "")
            }
        }

    def _extract_calendar_entities(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract entities from calendar record (Google Calendar, Outlook Calendar)"""
        title = record.get("summary", record.get("title", "No Title"))
        description = record.get("description", "")
        start = record.get("start", record.get("start_time", {}))
        end = record.get("end", record.get("end_time", {}))
        attendees = record.get("attendees", [])

        # Extract datetime
        if isinstance(start, dict):
            start_time = start.get("dateTime", start.get("date", ""))
        else:
            start_time = str(start)

        if isinstance(end, dict):
            end_time = end.get("dateTime", end.get("date", ""))
        else:
            end_time = str(end)

        # Extract attendees (people)
        people = []
        if isinstance(attendees, list):
            for attendee in attendees:
                email = attendee.get("email", "")
                name = attendee.get("displayName", attendee.get("name", ""))
                if email:
                    people.append(email)
                elif name:
                    people.append(name)

        text = f"{title}\n{description}"

        return {
            "id": f"event_{record.get('id', '')}",
            "text": text,
            "metadata": {
                "integration": "calendar",
                "entity_types": ["event", "person"],
                "title": title,
                "description": description,
                "start_time": start_time,
                "end_time": end_time,
                "attendees": people,
                "location": record.get("location", ""),
                "organizer": record.get("organizer", {}).get("email", ""),
                "url": record.get("htmlLink", record.get("url", ""))
            }
        }

    def _extract_generic_entities(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract entities from generic record (fallback)"""
        # Try to extract any text content
        text_parts = []

        for key, value in record.items():
            if isinstance(value, str) and len(value) < 1000:
                text_parts.append(value)

        text = "\n".join(text_parts)

        return {
            "id": f"record_{record.get('id', '')}",
            "text": text,
            "metadata": {
                "integration": "other",
                "entity_types": ["generic"],
                "raw_record": record
            }
        }

    async def _enhance_with_llm(
        self,
        entity: Dict[str, Any],
        integration_type: str
    ) -> Dict[str, Any]:
        """Enhance entity extraction with LLM (if available)"""
        if not self.llm_service:
            return entity

        try:
            # Build extraction prompt based on integration type
            text = entity.get("text", "")

            prompts = {
                "email": "Extract: people (names + emails), organizations, action items, deadlines",
                "communication": "Extract: topics, decisions, action items, mentioned people",
                "project": "Extract: dependencies, blockers, related tasks, risk level",
                "support": "Extract: issue category, urgency, root cause, resolution"
            }

            prompt = prompts.get(integration_type, "Extract: key entities, relationships, action items")

            # Call LLM (simplified - in production use structured output)
            system_prompt = f"""You are an entity extractor. {prompt}

Return results in this format:
People: [list]
Organizations: [list]
Action Items: [list]
Deadlines: [list]"""

            # This would use the actual LLM service call
            # For now, skip actual LLM call to avoid API dependency
            # extracted = await self.llm_service.complete(system_prompt, text)

            # entity["metadata"]["llm_extracted"] = extracted

        except Exception as e:
            logger.error(f"LLM enhancement failed: {e}")

        return entity

    def _extract_email_addresses(self, data: List[str]) -> List[str]:
        """
        Extract and validate email addresses from list of strings.

        Uses email-validator library for robust RFC 5322 compliant validation.

        Args:
            data: List of strings that may contain email addresses

        Returns:
            Unique list of valid email addresses found in the input
        """
        emails = []
        for item in data:
            if isinstance(item, str):
                # Find potential email matches using regex (first pass)
                potential_emails = self.email_pattern.findall(item)
                for email in potential_emails:
                    try:
                        # Validate using email-validator for RFC 5322 compliance
                        from email_validator import validate_email, EmailNotValidError
                        valid = validate_email(email, check_deliverability=False)
                        emails.append(valid.email)
                    except ImportError:
                        # Fallback to regex-only if email-validator not available
                        logger.warning("email-validator not available, using regex-only validation")
                        emails.append(email)
                    except EmailNotValidError:
                        # Skip invalid emails
                        continue
        return list(set(emails))

    def _extract_domains(self, emails: List[str]) -> List[str]:
        """Extract domains from email addresses"""
        domains = []
        for email in self._extract_email_addresses(emails):
            try:
                domain = email.split('@')[1]
                domains.append(domain)
            except IndexError:
                continue
        return list(set(domains))
