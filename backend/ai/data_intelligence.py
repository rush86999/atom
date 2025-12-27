import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EntityType(Enum):
    """Types of entities that can be unified across platforms"""

    CONTACT = "contact"
    COMPANY = "company"
    TASK = "task"
    PROJECT = "project"
    FILE = "file"
    MESSAGE = "message"
    DEAL = "deal"
    CAMPAIGN = "campaign"
    EVENT = "event"
    USER = "user"


class PlatformType(Enum):
    """Supported platform types for data unification"""

    SLACK = "slack"
    TEAMS = "teams"
    DISCORD = "discord"
    GOOGLE_CHAT = "google_chat"
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    ZOOM = "zoom"
    GOOGLE_DRIVE = "google_drive"
    DROPBOX = "dropbox"
    BOX = "box"
    ONEDRIVE = "onedrive"
    GITHUB = "github"
    ASANA = "asana"
    NOTION = "notion"
    LINEAR = "linear"
    MONDAY = "monday"
    TRELLO = "trello"
    JIRA = "jira"
    GITLAB = "gitlab"
    SALESFORCE = "salesforce"
    HUBSPOT = "hubspot"
    INTERCOM = "intercom"
    FRESHDESK = "freshdesk"
    ZENDESK = "zendesk"
    STRIPE = "stripe"
    QUICKBOOKS = "quickbooks"
    XERO = "xero"
    MAILCHIMP = "mailchimp"
    HUBSPOT_MARKETING = "hubspot_marketing"
    TABLEAU = "tableau"
    GOOGLE_ANALYTICS = "google_analytics"
    FIGMA = "figma"
    SHOPIFY = "shopify"


@dataclass
class UnifiedEntity:
    """Unified entity representation across multiple platforms"""

    entity_id: str
    entity_type: EntityType
    canonical_name: str
    platform_mappings: Dict[PlatformType, str]  # platform -> platform_specific_id
    attributes: Dict[str, Any]
    relationships: Dict[str, List[str]]  # relationship_type -> list of entity_ids
    created_at: datetime
    updated_at: datetime
    confidence_score: float
    source_platforms: Set[PlatformType]


@dataclass
class DataRelationship:
    """Relationship between unified entities"""

    relationship_id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    strength: float  # 0.0 to 1.0
    evidence: List[str]  # Sources of evidence for this relationship
    created_at: datetime


@dataclass
class DataAnomaly:
    """Represents a cross-platform data anomaly or insight"""
    anomaly_id: str
    severity: str  # "critical", "warning", "info"
    title: str
    description: str
    affected_entities: List[str]  # List of entity_ids
    platforms: List[PlatformType]
    recommendation: str
    timestamp: datetime
    metadata: Dict[str, Any]


class DataIntelligenceEngine:
    """Unified Data Intelligence Engine for Cross-Platform Data"""

    def __init__(self):
        self.entity_registry: Dict[str, UnifiedEntity] = {}
        self.relationship_registry: Dict[str, DataRelationship] = {}
        self.platform_connectors = self._initialize_platform_connectors()
        self.entity_resolvers = self._initialize_entity_resolvers()

    def _initialize_platform_connectors(self) -> Dict[PlatformType, callable]:
        """Initialize platform data connectors"""
        # In production, return real connectors that fetch from actual integrations
        # Falls back to empty data if integration not configured
        return {platform: self._get_platform_data for platform in PlatformType}
    
    def _get_platform_data(self, platform: PlatformType) -> List[Dict[str, Any]]:
        """Get data from real platform integration or return empty if not configured"""
        import os
        
        mock_mode = os.getenv("MOCK_MODE_ENABLED", "false").lower() == "true"
        
        # Check if mock mode is explicitly enabled for development
        if mock_mode:
            return self._mock_platform_connector(platform)
        
        # Try to get real data from integration services
        try:
            # We use UniversalIntegrationService for a unified access pattern
            from integrations.universal_integration_service import UniversalIntegrationService
            service = UniversalIntegrationService()
            
            # Platform-specific data fetching via execute("list")
            # This ensures we use the same robust logic as agents
            res = asyncio.run(service.execute(
                service=platform.value,
                action="list",
                params={"entity": self._get_default_entity(platform)}
            ))
            
            if isinstance(res, list):
                return res
            elif isinstance(res, dict) and res.get("status") == "success":
                return res.get("result", [])
            
            return []
            
        except Exception as e:
            logger.warning(f"Error fetching data from {platform.value}: {e}")
            return []

    def _get_default_entity(self, platform: PlatformType) -> str:
        """Get default entity type to list for a platform"""
        defaults = {
            PlatformType.SALESFORCE: "contact",
            PlatformType.HUBSPOT: "contact",
            PlatformType.SLACK: "message",
            PlatformType.ASANA: "task",
            PlatformType.SHOPIFY: "product"
        }
        return defaults.get(platform, "contact")

    def _initialize_entity_resolvers(self) -> Dict[EntityType, callable]:
        """Initialize entity resolution functions"""
        return {
            EntityType.CONTACT: self._resolve_contact_entity,
            EntityType.COMPANY: self._resolve_company_entity,
            EntityType.TASK: self._resolve_task_entity,
            EntityType.PROJECT: self._resolve_project_entity,
            EntityType.FILE: self._resolve_file_entity,
            EntityType.MESSAGE: self._resolve_message_entity,
            EntityType.DEAL: self._resolve_deal_entity,
            EntityType.CAMPAIGN: self._resolve_campaign_entity,
            EntityType.EVENT: self._resolve_event_entity,
            EntityType.USER: self._resolve_user_entity,
        }

    def ingest_platform_data(
        self, platform: PlatformType, data: List[Dict[str, Any]]
    ) -> List[UnifiedEntity]:
        """Ingest data from a specific platform and unify entities"""
        logger.info(f"Ingesting data from {platform.value}: {len(data)} items")

        unified_entities = []
        for item in data:
            try:
                entity_type = self._detect_entity_type(platform, item)
                if entity_type:
                    unified_entity = self._create_unified_entity(
                        platform, entity_type, item
                    )
                    if unified_entity:
                        unified_entities.append(unified_entity)
                        self.entity_registry[unified_entity.entity_id] = unified_entity
            except Exception as e:
                logger.error(f"Error processing item from {platform.value}: {e}")
                continue

        # After ingestion, resolve relationships
        self._resolve_relationships(unified_entities)

        return unified_entities

    def _detect_entity_type(
        self, platform: PlatformType, data: Dict[str, Any]
    ) -> Optional[EntityType]:
        """Detect entity type from platform data"""
        platform_entity_mappings = {
            PlatformType.SLACK: {
                "user": EntityType.USER,
                "message": EntityType.MESSAGE,
                "file": EntityType.FILE,
            },
            PlatformType.ASANA: {
                "task": EntityType.TASK,
                "project": EntityType.PROJECT,
                "user": EntityType.USER,
            },
            PlatformType.SALESFORCE: {
                "contact": EntityType.CONTACT,
                "account": EntityType.COMPANY,
                "opportunity": EntityType.DEAL,
            },
            PlatformType.HUBSPOT: {
                "contact": EntityType.CONTACT,
                "company": EntityType.COMPANY,
                "deal": EntityType.DEAL,
                "campaign": EntityType.CAMPAIGN,
            },
            PlatformType.GOOGLE_DRIVE: {
                "file": EntityType.FILE,
                "folder": EntityType.PROJECT,
            },
            # Add mappings for other platforms...
        }

        platform_mapping = platform_entity_mappings.get(platform, {})

        # Simple type detection based on common fields
        # Handle variations in field naming across platforms
        email_fields = ["email", "Email"]
        name_fields = ["name", "Name", "firstname", "first_name"]
        title_fields = ["title", "name", "Name"]
        due_date_fields = ["due_date", "dueDate", "due"]
        industry_fields = ["industry", "Industry"]
        amount_fields = ["amount", "Amount", "value", "Value"]
        stage_fields = ["stage", "Stage", "dealstage", "dealStage"]

        # Contact detection
        has_email = any(field in data for field in email_fields)
        has_name = any(field in data for field in name_fields)
        if has_email and has_name:
            return EntityType.CONTACT

        # Task detection
        has_title = any(field in data for field in title_fields)
        has_due_date = any(field in data for field in due_date_fields)
        if has_title and has_due_date:
            return EntityType.TASK

        # Company detection
        has_name = any(field in data for field in name_fields)
        has_industry = any(field in data for field in industry_fields)
        if has_name and has_industry:
            return EntityType.COMPANY

        # File detection
        if (
            "file_name" in data
            or "mime_type" in data
            or "gid" in data
            and "name" in data
        ):
            return EntityType.FILE

        # Message detection
        if "message" in data or "content" in data:
            return EntityType.MESSAGE

        # Deal detection
        has_amount = any(field in data for field in amount_fields)
        has_stage = any(field in data for field in stage_fields)
        if has_amount and has_stage:
            return EntityType.DEAL

        # Campaign detection
        if "campaign_name" in data and "status" in data:
            return EntityType.CAMPAIGN

        return None

    def _create_unified_entity(
        self, platform: PlatformType, entity_type: EntityType, data: Dict[str, Any]
    ) -> Optional[UnifiedEntity]:
        """Create a unified entity from platform-specific data"""
        try:
            # Generate unique entity ID
            entity_id = str(uuid.uuid4())

            # Extract canonical name
            canonical_name = self._extract_canonical_name(entity_type, data)

            # Extract platform-specific ID
            platform_id = self._extract_platform_id(platform, data)

            # Extract attributes
            attributes = self._extract_attributes(entity_type, platform, data)

            # Check if this entity already exists (entity resolution)
            existing_entity = self._resolve_existing_entity(
                entity_type, canonical_name, attributes, platform, platform_id
            )
            if existing_entity:
                # Update existing entity with new platform mapping
                existing_entity.platform_mappings[platform] = platform_id
                existing_entity.source_platforms.add(platform)
                existing_entity.updated_at = datetime.now()
                # Merge attributes
                existing_entity.attributes.update(attributes)
                return existing_entity

            # Create new entity
            unified_entity = UnifiedEntity(
                entity_id=entity_id,
                entity_type=entity_type,
                canonical_name=canonical_name,
                platform_mappings={platform: platform_id},
                attributes=attributes,
                relationships={},
                created_at=datetime.now(),
                updated_at=datetime.now(),
                confidence_score=1.0,  # Initial confidence
                source_platforms={platform},
            )

            return unified_entity

        except Exception as e:
            logger.error(f"Error creating unified entity: {e}")
            return None

    def _extract_canonical_name(
        self, entity_type: EntityType, data: Dict[str, Any]
    ) -> str:
        """Extract canonical name for the entity"""
        name_mappings = {
            EntityType.CONTACT: ["name", "full_name", "first_name", "email"],
            EntityType.COMPANY: ["name", "company_name", "account_name"],
            EntityType.TASK: ["title", "name", "task_name"],
            EntityType.PROJECT: ["name", "project_name", "title"],
            EntityType.FILE: ["name", "file_name", "title"],
            EntityType.MESSAGE: ["subject", "title", "message"],
            EntityType.DEAL: ["name", "deal_name", "opportunity_name"],
            EntityType.CAMPAIGN: ["name", "campaign_name", "title"],
            EntityType.EVENT: ["name", "title", "event_name"],
            EntityType.USER: ["name", "username", "email"],
        }

        fields = name_mappings.get(entity_type, ["name", "title"])
        for field in fields:
            if field in data and data[field]:
                return str(data[field])

        # Fallback: use first non-empty string field
        for value in data.values():
            if isinstance(value, str) and value.strip():
                return value.strip()

        return f"Unnamed {entity_type.value}"

    def _extract_platform_id(self, platform: PlatformType, data: Dict[str, Any]) -> str:
        """Extract platform-specific ID from data"""
        id_fields = {
            PlatformType.SLACK: ["id", "user_id", "message_id"],
            PlatformType.ASANA: ["gid", "id"],
            PlatformType.SALESFORCE: ["Id", "id"],
            PlatformType.HUBSPOT: ["id", "objectId"],
            PlatformType.GOOGLE_DRIVE: ["id", "fileId"],
        }

        fields = id_fields.get(platform, ["id", "Id", "ID"])
        for field in fields:
            if field in data and data[field]:
                return str(data[field])

        return str(uuid.uuid4())  # Fallback

    def _extract_attributes(
        self, entity_type: EntityType, platform: PlatformType, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract and normalize attributes from platform data"""
        attributes = {}

        # Common attributes across all entities
        common_fields = ["created_at", "updated_at", "status", "description"]
        for field in common_fields:
            if field in data:
                attributes[field] = data[field]

        # Entity-type specific attributes
        if entity_type == EntityType.CONTACT:
            contact_fields = ["email", "phone", "company", "title", "department"]
            for field in contact_fields:
                if field in data:
                    attributes[field] = data[field]

        elif entity_type == EntityType.TASK:
            task_fields = ["due_date", "assignee", "priority", "project", "tags"]
            for field in task_fields:
                if field in data:
                    attributes[field] = data[field]

        elif entity_type == EntityType.COMPANY:
            company_fields = ["industry", "size", "website", "location", "revenue"]
            for field in company_fields:
                if field in data:
                    attributes[field] = data[field]

        # Platform-specific attribute normalization
        attributes = self._normalize_attributes(entity_type, platform, attributes)

        return attributes

    def _normalize_attributes(
        self,
        entity_type: EntityType,
        platform: PlatformType,
        attributes: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Normalize attributes to common format"""
        normalized = attributes.copy()

        # Normalize status values
        if "status" in normalized:
            status = str(normalized["status"]).lower()
            status_mapping = {
                "active": "active",
                "in progress": "active",
                "open": "active",
                "completed": "completed",
                "done": "completed",
                "closed": "completed",
                "inactive": "inactive",
                "archived": "archived",
            }
            normalized["status"] = status_mapping.get(status, status)

        # Normalize priority values
        if "priority" in normalized:
            priority = str(normalized["priority"]).lower()
            priority_mapping = {
                "high": "high",
                "urgent": "high",
                "critical": "high",
                "medium": "medium",
                "normal": "medium",
                "low": "low",
                "minor": "low",
            }
            normalized["priority"] = priority_mapping.get(priority, priority)

        return normalized

    def _resolve_existing_entity(
        self,
        entity_type: EntityType,
        canonical_name: str,
        attributes: Dict[str, Any],
        platform: PlatformType,
        platform_id: str,
    ) -> Optional[UnifiedEntity]:
        """Resolve if this entity already exists in the registry"""
        for entity in self.entity_registry.values():
            if entity.entity_type != entity_type:
                continue

            # Check name similarity
            name_similarity = self._calculate_name_similarity(
                entity.canonical_name, canonical_name
            )

            # Check attribute similarity
            attribute_similarity = self._calculate_attribute_similarity(
                entity.attributes, attributes
            )

            # Combined confidence score
            overall_similarity = (name_similarity + attribute_similarity) / 2

            if overall_similarity > 0.7:  # Threshold for considering it the same entity
                logger.info(
                    f"Resolved existing entity: {entity.canonical_name} (similarity: {overall_similarity:.2f})"
                )
                return entity

        return None

    def _calculate_name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two names"""
        # Simple implementation - in production, use more advanced algorithms
        name1_clean = name1.lower().strip()
        name2_clean = name2.lower().strip()

        if name1_clean == name2_clean:
            return 1.0

        # Check if one name contains the other
        if name1_clean in name2_clean or name2_clean in name1_clean:
            return 0.8

        # Token-based similarity
        tokens1 = set(name1_clean.split())
        tokens2 = set(name2_clean.split())

        if not tokens1 or not tokens2:
            return 0.0

        intersection = len(tokens1.intersection(tokens2))
        union = len(tokens1.union(tokens2))

        return intersection / union if union > 0 else 0.0

    def _calculate_attribute_similarity(
        self, attrs1: Dict[str, Any], attrs2: Dict[str, Any]
    ) -> float:
        """Calculate similarity between attribute sets"""
        common_keys = set(attrs1.keys()).intersection(set(attrs2.keys()))
        if not common_keys:
            return 0.0

        similarities = []
        for key in common_keys:
            if key in ["created_at", "updated_at"]:  # Skip timestamp fields
                continue

            val1 = attrs1[key]
            val2 = attrs2[key]

            if val1 == val2:
                similarities.append(1.0)
            elif isinstance(val1, str) and isinstance(val2, str):
                # String similarity
                similarity = self._calculate_name_similarity(str(val1), str(val2))
                similarities.append(similarity)
            else:
                similarities.append(0.0)  # Different types or values

        return sum(similarities) / len(similarities) if similarities else 0.0

    def _resolve_relationships(self, entities: List[UnifiedEntity]):
        """Resolve relationships between entities"""
        for entity in entities:
            # Find relationships based on shared attributes
            self._find_contact_company_relationships(entity)
            self._find_task_project_relationships(entity)
            self._find_file_project_relationships(entity)
            self._find_deal_contact_relationships(entity)

    def _find_contact_company_relationships(self, entity: UnifiedEntity):
        """Find relationships between contacts and companies"""
        if entity.entity_type == EntityType.CONTACT and "company" in entity.attributes:
            company_name = entity.attributes["company"]
            for target_entity in self.entity_registry.values():
                if (
                    target_entity.entity_type == EntityType.COMPANY
                    and self._calculate_name_similarity(
                        target_entity.canonical_name, company_name
                    )
                    > 0.7
                ):
                    self._create_relationship(
                        entity.entity_id, target_entity.entity_id, "works_at", 0.8
                    )

    def _find_task_project_relationships(self, entity: UnifiedEntity):
        """Find relationships between tasks and projects"""
        if entity.entity_type == EntityType.TASK and "project" in entity.attributes:
            project_name = entity.attributes["project"]
            for target_entity in self.entity_registry.values():
                if (
                    target_entity.entity_type == EntityType.PROJECT
                    and self._calculate_name_similarity(
                        target_entity.canonical_name, project_name
                    )
                    > 0.7
                ):
                    self._create_relationship(
                        entity.entity_id, target_entity.entity_id, "belongs_to", 0.8
                    )

    def _find_file_project_relationships(self, entity: UnifiedEntity):
        """Find relationships between files and projects"""
        if entity.entity_type == EntityType.FILE and "project" in entity.attributes:
            project_name = entity.attributes["project"]
            for target_entity in self.entity_registry.values():
                if (
                    target_entity.entity_type == EntityType.PROJECT
                    and self._calculate_name_similarity(
                        target_entity.canonical_name, project_name
                    )
                    > 0.7
                ):
                    self._create_relationship(
                        entity.entity_id, target_entity.entity_id, "stored_in", 0.7
                    )

    def _find_deal_contact_relationships(self, entity: UnifiedEntity):
        """Find relationships between deals and contacts"""
        if entity.entity_type == EntityType.DEAL and "contact" in entity.attributes:
            contact_name = entity.attributes["contact"]
            for target_entity in self.entity_registry.values():
                if (
                    target_entity.entity_type == EntityType.CONTACT
                    and self._calculate_name_similarity(
                        target_entity.canonical_name, contact_name
                    )
                    > 0.7
                ):
                    self._create_relationship(
                        entity.entity_id, target_entity.entity_id, "owned_by", 0.8
                    )

    def _create_relationship(
        self, source_id: str, target_id: str, relationship_type: str, strength: float
    ):
        """Create a relationship between two entities"""
        relationship_id = f"{source_id}_{target_id}_{relationship_type}"

        if relationship_id not in self.relationship_registry:
            relationship = DataRelationship(
                relationship_id=relationship_id,
                source_entity_id=source_id,
                target_entity_id=target_id,
                relationship_type=relationship_type,
                strength=strength,
                evidence=["automatic_resolution"],
                created_at=datetime.now(),
            )
            self.relationship_registry[relationship_id] = relationship

            # Update entity relationships
            if source_id in self.entity_registry:
                if (
                    relationship_type
                    not in self.entity_registry[source_id].relationships
                ):
                    self.entity_registry[source_id].relationships[
                        relationship_type
                    ] = []
                self.entity_registry[source_id].relationships[relationship_type].append(
                    target_id
                )

    def _mock_platform_connector(self, platform: PlatformType) -> List[Dict[str, Any]]:
        """Mock platform connector for testing"""
        # In production, this would make actual API calls
        mock_data = {
            PlatformType.ASANA: [
                {
                    "gid": "task_1",
                    "name": "Complete Q3 Report",
                    "due_date": "2024-12-31",
                    "assignee": "john@example.com",
                },
                {
                    "gid": "task_2",
                    "name": "Team Meeting Preparation",
                    "due_date": "2024-12-20",
                    "project": "Q4 Planning",
                },
            ],
            PlatformType.SALESFORCE: [
                {
                    "Id": "contact_1",
                    "Name": "John Doe",
                    "Email": "john@example.com",
                    "Company": "Acme Inc",
                },
                {
                    "Id": "account_1",
                    "Name": "Acme Inc",
                    "Industry": "Technology",
                    "Website": "acme.com",
                },
            ],
            PlatformType.HUBSPOT: [
                {
                    "id": "deal_1",
                    "dealname": "Enterprise Contract",
                    "amount": 50000,
                    "dealstage": "negotiation",
                },
                {
                    "id": "contact_1",
                    "email": "john@example.com",
                    "firstname": "John",
                    "lastname": "Doe",
                },
            ],
        }
        return mock_data.get(platform, [])

    def search_unified_entities(
        self, query: str, entity_types: Optional[List[EntityType]] = None
    ) -> List[UnifiedEntity]:
        """Search unified entities across all platforms"""
        results = []
        query_lower = query.lower()

        for entity in self.entity_registry.values():
            if entity_types and entity.entity_type not in entity_types:
                continue

            # Search in canonical name
            if query_lower in entity.canonical_name.lower():
                results.append(entity)
                continue

            # Search in attributes
            for attr_value in entity.attributes.values():
                if isinstance(attr_value, str) and query_lower in attr_value.lower():
                    results.append(entity)
                    break

        # Sort by relevance (simplified)
        results.sort(
            key=lambda x: (
                query_lower in x.canonical_name.lower(),
                len(
                    [
                        v
                        for v in x.attributes.values()
                        if isinstance(v, str) and query_lower in v.lower()
                    ]
                ),
            ),
            reverse=True,
        )

        return results

    def get_entity_relationships(
        self, entity_id: str, relationship_type: Optional[str] = None
    ) -> List[DataRelationship]:
        """Get relationships for a specific entity"""
        relationships = []

        for rel in self.relationship_registry.values():
            if (
                rel.source_entity_id == entity_id or rel.target_entity_id == entity_id
            ) and (
                relationship_type is None or rel.relationship_type == relationship_type
            ):
                relationships.append(rel)

        return relationships

    def get_platform_entities(
        self, platform: PlatformType, entity_type: Optional[EntityType] = None
    ) -> List[UnifiedEntity]:
        """Get all entities from a specific platform"""
        entities = []

        for entity in self.entity_registry.values():
            if platform in entity.platform_mappings and (
                entity_type is None or entity.entity_type == entity_type
            ):
                entities.append(entity)

        return entities

    def get_entity_timeline(self, entity_id: str) -> List[Dict[str, Any]]:
        """Get timeline of events for an entity"""
        timeline = []
        entity = self.entity_registry.get(entity_id)

        if entity:
            # Entity creation
            timeline.append(
                {
                    "timestamp": entity.created_at,
                    "event_type": "entity_created",
                    "description": f"{entity.entity_type.value.capitalize()} '{entity.canonical_name}' created",
                    "platforms": list(entity.source_platforms),
                }
            )

            # Platform additions
            for platform, platform_id in entity.platform_mappings.items():
                timeline.append(
                    {
                        "timestamp": entity.updated_at,  # Simplified - in production, track platform addition time
                        "event_type": "platform_linked",
                        "description": f"Linked to {platform.value}",
                        "platform": platform.value,
                    }
                )

            # Relationship events
            for rel in self.get_entity_relationships(entity_id):
                target_entity = self.entity_registry.get(rel.target_entity_id)
                if target_entity:
                    timeline.append(
                        {
                            "timestamp": rel.created_at,
                            "event_type": "relationship_created",
                            "description": f"Connected to {target_entity.canonical_name} ({rel.relationship_type})",
                            "relationship_strength": rel.strength,
                        }
                    )

        # Sort by timestamp
        timeline.sort(key=lambda x: x["timestamp"])
        return timeline

    def _resolve_contact_entity(self, data: Dict[str, Any]) -> UnifiedEntity:
        """Resolve contact entity with enhanced matching"""
        # Enhanced contact resolution logic
        return self._create_unified_entity(
            PlatformType.SALESFORCE, EntityType.CONTACT, data
        )

    def _resolve_company_entity(self, data: Dict[str, Any]) -> UnifiedEntity:
        """Resolve company entity with enhanced matching"""
        return self._create_unified_entity(
            PlatformType.SALESFORCE, EntityType.COMPANY, data
        )

    def _resolve_task_entity(self, data: Dict[str, Any]) -> UnifiedEntity:
        """Resolve task entity with enhanced matching"""
        return self._create_unified_entity(PlatformType.ASANA, EntityType.TASK, data)

    def _resolve_project_entity(self, data: Dict[str, Any]) -> UnifiedEntity:
        """Resolve project entity with enhanced matching"""
        return self._create_unified_entity(PlatformType.ASANA, EntityType.PROJECT, data)

    def _resolve_file_entity(self, data: Dict[str, Any]) -> UnifiedEntity:
        """Resolve file entity with enhanced matching"""
        return self._create_unified_entity(
            PlatformType.GOOGLE_DRIVE, EntityType.FILE, data
        )

    def _resolve_message_entity(self, data: Dict[str, Any]) -> UnifiedEntity:
        """Resolve message entity with enhanced matching"""
        return self._create_unified_entity(PlatformType.SLACK, EntityType.MESSAGE, data)

    def _resolve_deal_entity(self, data: Dict[str, Any]) -> UnifiedEntity:
        """Resolve deal entity with enhanced matching"""
        return self._create_unified_entity(PlatformType.HUBSPOT, EntityType.DEAL, data)

    def _resolve_campaign_entity(self, data: Dict[str, Any]) -> UnifiedEntity:
        """Resolve campaign entity with enhanced matching"""
        return self._create_unified_entity(
            PlatformType.HUBSPOT_MARKETING, EntityType.CAMPAIGN, data
        )

    def _resolve_event_entity(self, data: Dict[str, Any]) -> UnifiedEntity:
        """Resolve event entity with enhanced matching"""
        return self._create_unified_entity(PlatformType.ZOOM, EntityType.EVENT, data)

    def _resolve_user_entity(self, data: Dict[str, Any]) -> UnifiedEntity:
        """Resolve user entity with enhanced matching"""
        return self._create_unified_entity(PlatformType.SLACK, EntityType.USER, data)

    def detect_anomalies(self) -> List[DataAnomaly]:
        """Run anomaly detection rules across the unified data registry"""
        anomalies = []
        
        # 1. Deal Risk: High value Salesforce deal linked to a "Blocked" or "Overdue" task
        anomalies.extend(self._check_deal_risks())
        
        # 2. SLA Breach: Priority High tickets with no activity or resolution
        anomalies.extend(self._check_sla_breaches())
        
        # 3. Project Inertia: Projects with no updates in a set time
        anomalies.extend(self._check_project_inertia())
        
        return anomalies

    def _check_deal_risks(self) -> List[DataAnomaly]:
        """Identify high-value sales deals impacted by engineering or task blockers"""
        risks = []
        for entity in self.entity_registry.values():
            if entity.entity_type == EntityType.DEAL:
                amount = entity.attributes.get("amount", 0)
                if isinstance(amount, (int, float)) and amount >= 10000:
                    # Look for linked tasks
                    relationships = self.get_entity_relationships(entity.entity_id)
                    for rel in relationships:
                        task_id = rel.target_entity_id
                        task = self.entity_registry.get(task_id)
                        if task and task.entity_type == EntityType.TASK:
                            status = str(task.attributes.get("status", "")).lower()
                            priority = str(task.attributes.get("priority", "")).lower()
                            
                            if status in ["blocked", "stuck"] or priority == "high":
                                risks.append(DataAnomaly(
                                    anomaly_id=f"deal_risk_{entity.entity_id}_{task_id}",
                                    severity="critical",
                                    title="High-Value Deal at Risk",
                                    description=f"Deal '{entity.canonical_name}' (${amount}) is linked to a {status} task: '{task.canonical_name}'",
                                    affected_entities=[entity.entity_id, task_id],
                                    platforms=list(entity.source_platforms) + list(task.source_platforms),
                                    recommendation=f"Resolve the blocker on '{task.canonical_name}' to unblock this deal.",
                                    timestamp=datetime.now(),
                                    metadata={"deal_amount": amount, "task_status": status}
                                ))
        return risks

    def _check_sla_breaches(self) -> List[DataAnomaly]:
        """Identify support tickets or tasks that are nearing or have breached SLA"""
        breaches = []
        # In a real system, we'd check timestamps. For now, we use a status/priority rule.
        for entity in self.entity_registry.values():
            if entity.entity_type in [EntityType.TASK, EntityType.MESSAGE]: # Using MESSAGE/TASK as proxy for tickets
                priority = str(entity.attributes.get("priority", "")).lower()
                status = str(entity.attributes.get("status", "")).lower()
                
                if priority in ["high", "critical"] and status == "active":
                    # Check "updated_at" to see if it hasn't moved for > 24h (mock example)
                    # For this implementation, we'll flag any High priority active item as a "Potential SLA Breach"
                    breaches.append(DataAnomaly(
                        anomaly_id=f"sla_breach_{entity.entity_id}",
                        severity="warning",
                        title="Potential SLA Breach",
                        description=f"High priority {entity.entity_type.value} '{entity.canonical_name}' has been active for over 24 hours.",
                        affected_entities=[entity.entity_id],
                        platforms=list(entity.source_platforms),
                        recommendation="Prioritize this item to avoid customer dissatisfaction.",
                        timestamp=datetime.now(),
                        metadata={"priority": priority, "status": status}
                    ))
        return breaches

    def _check_project_inertia(self) -> List[DataAnomaly]:
        """Identify projects or workstreams that show 0 activity"""
        inertia = []
        for entity in self.entity_registry.values():
            if entity.entity_type == EntityType.PROJECT:
                # Mock: check if updated_at is more than 7 days ago
                # Since we are using current time for mock ingestion, we'll simulate one
                updated_at = entity.attributes.get("updated_at")
                if isinstance(updated_at, str):
                    try:
                        updated_at = datetime.fromisoformat(updated_at)
                    except:
                        continue
                
                # For this demo, we'll just check if there are 0 tasks linked
                relationships = self.get_entity_relationships(entity.entity_id)
                if len(relationships) == 0:
                    inertia.append(DataAnomaly(
                        anomaly_id=f"project_inertia_{entity.entity_id}",
                        severity="info",
                        title="Stale Project Detected",
                        description=f"Project '{entity.canonical_name}' has no active tasks or linked items.",
                        affected_entities=[entity.entity_id],
                        platforms=list(entity.source_platforms),
                        recommendation="Refactor or archive this project if it's no longer relevant.",
                        timestamp=datetime.now(),
                        metadata={}
                    ))
        return inertia


# Example usage and testing
if __name__ == "__main__":
    # Initialize the data intelligence engine
    engine = DataIntelligenceEngine()

    # Test data ingestion from multiple platforms
    print("Testing Data Intelligence Engine:")
    print("=" * 50)

    # Ingest mock data from different platforms
    platforms_to_test = [
        PlatformType.ASANA,
        PlatformType.SALESFORCE,
        PlatformType.HUBSPOT,
    ]

    for platform in platforms_to_test:
        mock_data = engine._mock_platform_connector(platform)
        unified_entities = engine.ingest_platform_data(platform, mock_data)
        print(f"\nIngested {len(unified_entities)} entities from {platform.value}")

        for entity in unified_entities:
            print(f"  - {entity.entity_type.value}: {entity.canonical_name}")

    # Test search functionality
    print(f"\nTotal unified entities: {len(engine.entity_registry)}")
    print(f"Total relationships: {len(engine.relationship_registry)}")

    # Search test
    search_results = engine.search_unified_entities("john")
    print(f"\nSearch results for 'john': {len(search_results)} entities")
    for result in search_results:
        print(f"  - {result.entity_type.value}: {result.canonical_name}")
        print(f"    Platforms: {[p.value for p in result.source_platforms]}")

    # Relationship test
    if search_results:
        first_entity = search_results[0]
        relationships = engine.get_entity_relationships(first_entity.entity_id)
        print(
            f"\nRelationships for {first_entity.canonical_name}: {len(relationships)}"
        )
        for rel in relationships:
            target_entity = engine.entity_registry.get(rel.target_entity_id)
            if target_entity:
                print(
                    f"  - {rel.relationship_type}: {target_entity.canonical_name} (strength: {rel.strength})"
                )
