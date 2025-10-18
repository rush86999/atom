import logging
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Any
from enum import Enum

# Configure logging
logger = logging.getLogger(__name__)


class ContactProvider(Enum):
    """Supported contact providers"""

    GOOGLE = "google"
    OUTLOOK = "outlook"
    APPLE = "apple"
    SALESFORCE = "salesforce"
    HUBSPOT = "hubspot"
    LOCAL = "local"


class Contact:
    """Unified contact representation"""

    def __init__(
        self,
        id: str,
        name: str,
        email: str,
        phone: Optional[str] = None,
        company: Optional[str] = None,
        title: Optional[str] = None,
        provider: ContactProvider = ContactProvider.LOCAL,
        provider_contact_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        notes: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.id = id
        self.name = name
        self.email = email
        self.phone = phone
        self.company = company
        self.title = title
        self.provider = provider
        self.provider_contact_id = provider_contact_id
        self.tags = tags or []
        self.notes = notes
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert contact to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "company": self.company,
            "title": self.title,
            "provider": self.provider.value,
            "provider_contact_id": self.provider_contact_id,
            "tags": self.tags,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Contact":
        """Create contact from dictionary"""
        return cls(
            id=data["id"],
            name=data["name"],
            email=data["email"],
            phone=data.get("phone"),
            company=data.get("company"),
            title=data.get("title"),
            provider=ContactProvider(data["provider"]),
            provider_contact_id=data.get("provider_contact_id"),
            tags=data.get("tags", []),
            notes=data.get("notes"),
            created_at=datetime.fromisoformat(data["created_at"])
            if data.get("created_at")
            else None,
            updated_at=datetime.fromisoformat(data["updated_at"])
            if data.get("updated_at")
            else None,
        )


class ContactService:
    """Service for contact management operations"""

    def __init__(self):
        self.contacts = {}  # In-memory storage for demo purposes

    async def get_contacts(
        self,
        user_id: str,
        provider: Optional[ContactProvider] = None,
        tags: Optional[List[str]] = None,
        search_query: Optional[str] = None,
    ) -> List[Contact]:
        """
        Get contacts for a user

        Args:
            user_id: User identifier
            provider: Filter by contact provider
            tags: Filter by tags
            search_query: Search in name, email, company

        Returns:
            List of contacts
        """
        try:
            # Get user's contacts from storage
            user_contacts = self._get_user_contacts(user_id)

            # Apply filters
            filtered_contacts = user_contacts

            if provider:
                filtered_contacts = [
                    c for c in filtered_contacts if c.provider == provider
                ]

            if tags:
                filtered_contacts = [
                    c for c in filtered_contacts if any(tag in c.tags for tag in tags)
                ]

            if search_query:
                query_lower = search_query.lower()
                filtered_contacts = [
                    c
                    for c in filtered_contacts
                    if (
                        query_lower in c.name.lower()
                        or query_lower in c.email.lower()
                        or (c.company and query_lower in c.company.lower())
                    )
                ]

            return filtered_contacts

        except Exception as e:
            logger.error(f"Error getting contacts for user {user_id}: {e}")
            return []

    async def create_contact(
        self,
        user_id: str,
        name: str,
        email: str,
        phone: Optional[str] = None,
        company: Optional[str] = None,
        title: Optional[str] = None,
        provider: ContactProvider = ContactProvider.LOCAL,
        tags: Optional[List[str]] = None,
        notes: Optional[str] = None,
    ) -> Optional[Contact]:
        """
        Create a new contact

        Args:
            user_id: User identifier
            name: Contact name
            email: Contact email
            phone: Contact phone
            company: Company name
            title: Job title
            provider: Contact provider
            tags: Contact tags
            notes: Contact notes

        Returns:
            Created contact or None if failed
        """
        try:
            contact_id = str(uuid.uuid4())
            contact = Contact(
                id=contact_id,
                name=name,
                email=email,
                phone=phone,
                company=company,
                title=title,
                provider=provider,
                tags=tags or [],
                notes=notes,
            )

            # Store contact
            if user_id not in self.contacts:
                self.contacts[user_id] = {}
            self.contacts[user_id][contact_id] = contact

            logger.info(f"Created contact {contact_id} for user {user_id}")
            return contact

        except Exception as e:
            logger.error(f"Error creating contact for user {user_id}: {e}")
            return None

    async def update_contact(
        self, user_id: str, contact_id: str, updates: Dict[str, Any]
    ) -> Optional[Contact]:
        """
        Update an existing contact

        Args:
            user_id: User identifier
            contact_id: Contact identifier
            updates: Fields to update

        Returns:
            Updated contact or None if not found
        """
        try:
            if user_id not in self.contacts or contact_id not in self.contacts[user_id]:
                logger.warning(f"Contact {contact_id} not found for user {user_id}")
                return None

            contact = self.contacts[user_id][contact_id]

            # Update fields
            if "name" in updates:
                contact.name = updates["name"]
            if "email" in updates:
                contact.email = updates["email"]
            if "phone" in updates:
                contact.phone = updates["phone"]
            if "company" in updates:
                contact.company = updates["company"]
            if "title" in updates:
                contact.title = updates["title"]
            if "tags" in updates:
                contact.tags = updates["tags"]
            if "notes" in updates:
                contact.notes = updates["notes"]

            contact.updated_at = datetime.now()

            logger.info(f"Updated contact {contact_id} for user {user_id}")
            return contact

        except Exception as e:
            logger.error(f"Error updating contact {contact_id} for user {user_id}: {e}")
            return None

    async def delete_contact(self, user_id: str, contact_id: str) -> bool:
        """
        Delete a contact

        Args:
            user_id: User identifier
            contact_id: Contact identifier

        Returns:
            True if deleted, False if not found
        """
        try:
            if user_id in self.contacts and contact_id in self.contacts[user_id]:
                del self.contacts[user_id][contact_id]
                logger.info(f"Deleted contact {contact_id} for user {user_id}")
                return True
            else:
                logger.warning(f"Contact {contact_id} not found for user {user_id}")
                return False

        except Exception as e:
            logger.error(f"Error deleting contact {contact_id} for user {user_id}: {e}")
            return False

    async def sync_contacts(
        self, user_id: str, provider: ContactProvider
    ) -> Dict[str, Any]:
        """
        Sync contacts from external provider

        Args:
            user_id: User identifier
            provider: Contact provider to sync from

        Returns:
            Sync result with statistics
        """
        try:
            logger.info(
                f"Starting contact sync for user {user_id} from {provider.value}"
            )

            # Mock sync implementation
            # In production, this would integrate with provider APIs

            if provider == ContactProvider.GOOGLE:
                # Mock Google Contacts sync
                synced_contacts = [
                    Contact(
                        id=str(uuid.uuid4()),
                        name="John Doe",
                        email="john.doe@example.com",
                        phone="+1-555-0101",
                        company="Example Corp",
                        title="Software Engineer",
                        provider=ContactProvider.GOOGLE,
                        provider_contact_id="google_contact_123",
                    ),
                    Contact(
                        id=str(uuid.uuid4()),
                        name="Jane Smith",
                        email="jane.smith@example.com",
                        phone="+1-555-0102",
                        company="Tech Solutions",
                        title="Product Manager",
                        provider=ContactProvider.GOOGLE,
                        provider_contact_id="google_contact_456",
                    ),
                ]
            elif provider == ContactProvider.OUTLOOK:
                # Mock Outlook sync
                synced_contacts = [
                    Contact(
                        id=str(uuid.uuid4()),
                        name="Bob Wilson",
                        email="bob.wilson@example.com",
                        phone="+1-555-0103",
                        company="Business Inc",
                        title="Sales Director",
                        provider=ContactProvider.OUTLOOK,
                        provider_contact_id="outlook_contact_789",
                    )
                ]
            else:
                synced_contacts = []

            # Store synced contacts
            for contact in synced_contacts:
                if user_id not in self.contacts:
                    self.contacts[user_id] = {}
                self.contacts[user_id][contact.id] = contact

            return {
                "success": True,
                "provider": provider.value,
                "contacts_synced": len(synced_contacts),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(
                f"Error syncing contacts from {provider.value} for user {user_id}: {e}"
            )
            return {
                "success": False,
                "provider": provider.value,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def _get_user_contacts(self, user_id: str) -> List[Contact]:
        """Get all contacts for a user"""
        if user_id in self.contacts:
            return list(self.contacts[user_id].values())
        return []


# Global contact service instance
contact_service = ContactService()


# Utility functions
async def search_contacts(user_id: str, query: str) -> List[Contact]:
    """Search contacts by name, email, or company"""
    return await contact_service.get_contacts(user_id, search_query=query)


async def get_contact_by_email(user_id: str, email: str) -> Optional[Contact]:
    """Get contact by email address"""
    contacts = await contact_service.get_contacts(user_id)
    for contact in contacts:
        if contact.email.lower() == email.lower():
            return contact
    return None


async def get_contacts_by_company(user_id: str, company: str) -> List[Contact]:
    """Get contacts by company"""
    contacts = await contact_service.get_contacts(user_id)
    return [c for c in contacts if c.company and company.lower() in c.company.lower()]


async def add_contact_tag(user_id: str, contact_id: str, tag: str) -> Optional[Contact]:
    """Add tag to contact"""
    contact = await contact_service.get_contact_by_id(user_id, contact_id)
    if contact and tag not in contact.tags:
        contact.tags.append(tag)
        return await contact_service.update_contact(
            user_id, contact_id, {"tags": contact.tags}
        )
    return contact


async def remove_contact_tag(
    user_id: str, contact_id: str, tag: str
) -> Optional[Contact]:
    """Remove tag from contact"""
    contact = await contact_service.get_contact_by_id(user_id, contact_id)
    if contact and tag in contact.tags:
        contact.tags.remove(tag)
        return await contact_service.update_contact(
            user_id, contact_id, {"tags": contact.tags}
        )
    return contact


# Add missing method to ContactService
async def get_contact_by_id(self, user_id: str, contact_id: str) -> Optional[Contact]:
    """Get contact by ID"""
    if user_id in self.contacts and contact_id in self.contacts[user_id]:
        return self.contacts[user_id][contact_id]
    return None


# Add the method to the class
ContactService.get_contact_by_id = get_contact_by_id
