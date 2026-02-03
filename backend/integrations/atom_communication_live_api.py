import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query

# Import Services (Lazy load or direct import depending on architecture)
# For now, we import directly but handle missing dependencies gracefully
try:
    from integrations.slack_service_unified import slack_unified_service
    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False

try:
    from integrations.discord_service import discord_service
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False

try:
    from integrations.gmail_service import gmail_service
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False

try:
    from integrations.zoho_mail_service import ZohoMailService
    ZOHO_MAIL_AVAILABLE = True
except ImportError:
    ZOHO_MAIL_AVAILABLE = False

try:
    from integrations.microsoft365_service import microsoft365_service
    from integrations.outlook_service import OutlookService
    from integrations.teams_service import TeamsService
    M365_AVAILABLE = True
except ImportError:
    M365_AVAILABLE = False

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/atom/communication/live", tags=["communication-live"])

# --- Unified Data Models ---

class UnifiedLiveMessage:
    """
    Standardized message object for the Live Inbox.
    Unlike the Memory object, this is optimized for UI display (avatars, status, actions).
    """
    def __init__(self, 
                 id: str,
                 provider: str, # slack, gmail, discord, zoho, outlook, teams
                 content: str,
                 sender: str,
                 timestamp: datetime,
                 channel_name: Optional[str] = None,
                 channel_id: Optional[str] = None,
                 thread_id: Optional[str] = None,
                 url: Optional[str] = None,
                 status: str = "read", # read, unread
                 metadata: Dict[str, Any] = {}
                 ):
        self.id = id
        self.provider = provider
        self.content = content
        self.sender = sender
        self.timestamp = timestamp
        self.channel_name = channel_name
        self.channel_id = channel_id
        self.thread_id = thread_id
        self.url = url
        self.status = status
        self.metadata = metadata

    def to_dict(self):
        return {
            "id": self.id,
            "provider": self.provider,
            "content": self.content,
            "sender": self.sender,
            "timestamp": self.timestamp.isoformat(),
            "channel_name": self.channel_name,
            "channel_id": self.channel_id,
            "thread_id": self.thread_id,
            "url": self.url,
            "status": self.status,
            "metadata": self.metadata
        }

# --- Aggregation Logic ---

async def fetch_slack_recent(limit: int = 20) -> List[Dict]:
    """Fetch recent messages from active Slack channels"""
    if not SLACK_AVAILABLE:
        return []

    messages = []
    try:
        # Use user context manager for token retrieval
        from core.user_context_manager import get_user_context_manager

        context_manager = get_user_context_manager()
        token_context = context_manager.get_token_with_context("slack")

        if not token_context or "token" not in token_context:
            logger.warning("No Slack token found for Live API")
            return []

        token = token_context["token"]
        source = token_context.get("source", "bot")

        logger.debug(f"Using Slack token from {source} mode")

        # 2. List public channels to scan
        # For responsiveness, we limit to scanning the first few active channels or a specific 'general'
        channels = await slack_unified_service.list_channels(token=token, types="public_channel")

        # Sort channels by activity or just take first few?
        # For MVP, let's look at the first 3 channels to build the "Inbox"
        target_channels = channels[:3]

        for ch in target_channels:
            ch_id = ch.get("id")
            ch_name = ch.get("name")

            # Fetch history
            history = await slack_unified_service.get_channel_history(token=token, channel_id=ch_id, limit=5)
            msgs = history.get("messages", [])

            for m in msgs:
                # Filter out subtypes like 'channel_join'
                if "subtype" in m:
                    continue

                # Convert timestamp
                ts_str = m.get("ts")
                ts_dt = datetime.fromtimestamp(float(ts_str))

                unified_msg = UnifiedLiveMessage(
                    id=f"slack_{ch_id}_{ts_str}",
                    provider="slack",
                    content=m.get("text", ""),
                    sender=m.get("user", "unknown"),
                    timestamp=ts_dt,
                    channel_name=f"#{ch_name}",
                    channel_id=ch_id,
                    metadata={"original_id": ts_str}
                )
                messages.append(unified_msg.to_dict())

    except Exception as e:
        logger.error(f"Error fetching Slack live: {e}")

    return messages

async def fetch_zoho_mail_recent(limit: int = 20) -> List[Dict]:
    """Fetch recent messages from Zoho Mail"""
    if not ZOHO_MAIL_AVAILABLE:
        return []
    
    messages = []
    try:
        import os
        token = os.getenv("ZOHO_CRM_ACCESS_TOKEN") # Reusing token
        if not token:
            return []
            
        zoho = ZohoMailService()
        raw_msgs = await zoho.get_recent_inbox(token, limit=limit)
        
        for m in raw_msgs:
            # Zoho Mail message structure
            msg_id = m.get("messageId")
            sender = m.get("sender")
            subject = m.get("subject")
            content = m.get("summary") or subject
            sent_time = m.get("sentTimeInMS")
            ts_dt = datetime.fromtimestamp(float(sent_time)/1000.0) if sent_time else datetime.now()
            
            unified_msg = UnifiedLiveMessage(
                id=f"zoho_{msg_id}",
                provider="zoho",
                content=content,
                sender=sender,
                timestamp=ts_dt,
                subject=subject,
                status="read" if m.get("status") == "read" else "unread"
            )
            messages.append(unified_msg.to_dict())
    except Exception as e:
        logger.error(f"Error fetching Zoho Mail live: {e}")
        
    return messages

async def fetch_outlook_recent(limit: int = 20) -> List[Dict]:
    """Fetch recent messages from Outlook"""
    if not M365_AVAILABLE:
        return []
    
    messages = []
    try:
        import os
        token = os.getenv("MICROSOFT_365_ACCESS_TOKEN")
        if not token:
            return []
            
        service = OutlookService()
        raw_msgs = await service.get_user_emails("me", token=token, max_results=limit)
        
        for m in raw_msgs:
            unified_msg = UnifiedLiveMessage(
                id=f"outlook_{m.get('id')}",
                provider="outlook",
                content=m.get("body_preview") or m.get("subject"),
                sender=m.get("sender", {}).get("emailAddress", {}).get("address") or "Unknown",
                timestamp=datetime.fromisoformat(m.get("received_date_time").replace("Z", "+00:00")) if m.get("received_date_time") else datetime.now(),
                url=m.get("web_link"),
                status="read" if m.get("is_read") else "unread"
            )
            messages.append(unified_msg.to_dict())
    except Exception as e:
        logger.error(f"Error fetching Outlook live: {e}")
        
    return messages

async def fetch_teams_recent(limit: int = 10) -> List[Dict]:
    """Fetch recent messages from Teams"""
    if not M365_AVAILABLE:
        return []
    
    messages = []
    try:
        import os
        token = os.getenv("MICROSOFT_365_ACCESS_TOKEN")
        if not token:
            return []
            
        service = TeamsService(access_token=token)
        teams = service.get_teams()
        for team in teams[:2]:
            channels = service.get_channels(team['id'])
            for ch in channels[:2]:
                raw_msgs = service.get_messages(team['id'], ch['id'], limit=3)
                for m in raw_msgs:
                    unified_msg = UnifiedLiveMessage(
                        id=f"teams_{m.get('id')}",
                        provider="teams",
                        content=m.get("body", {}).get("content", ""),
                        sender=m.get("from", {}).get("user", {}).get("displayName") or "Unknown",
                        timestamp=datetime.fromisoformat(m.get("createdDateTime").replace("Z", "+00:00")) if m.get("createdDateTime") else datetime.now(),
                        channel_name=ch.get("displayName"),
                        channel_id=ch.get("id")
                    )
                    messages.append(unified_msg.to_dict())
    except Exception as e:
        logger.error(f"Error fetching Teams live: {e}")
        
    return messages

# --- Endpoints ---

@router.get("/inbox")
async def get_live_inbox(limit: int = 50):
    """
    Aggregates 'Inbox' style messages from all connected providers.
    This acts as the single stream of truth for the Communication Command Center.
    """
    all_messages = []
    
    # 1. Fetch Slack
    slack_msgs = await fetch_slack_recent(limit=limit)
    all_messages.extend(slack_msgs)
    
    # 2. Fetch Gmail (Pending Implementation)
    # 3. Fetch Discord (Pending Switch to Unified Service)
    
    # 4. Fetch Zoho Mail
    zoho_msgs = await fetch_zoho_mail_recent(limit=limit)
    all_messages.extend(zoho_msgs)

    # 5. Fetch Outlook
    outlook_msgs = await fetch_outlook_recent(limit=limit)
    all_messages.extend(outlook_msgs)

    # 6. Fetch Teams
    teams_msgs = await fetch_teams_recent(limit=limit)
    all_messages.extend(teams_msgs)
    
    # Sort by timestamp desc (isoformat strings sort correctly)
    all_messages.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return {
        "ok": True,
        "count": len(all_messages),
        "messages": all_messages[:limit],
        "providers": {
            "slack": SLACK_AVAILABLE,
            "discord": DISCORD_AVAILABLE,
            "zoho": ZOHO_MAIL_AVAILABLE,
            "outlook": M365_AVAILABLE,
            "teams": M365_AVAILABLE
        }
    }

@router.get("/channels")
async def get_live_channels():
    """
    Returns a unified list of 'Channels' or 'Folders' to browse.
    e.g. Slack Channels + Email Folders + Discord Guilds
    """
    channels = []
    
    # Mock Implementation to prove architecture
    # In next step, we will wire this to `slack_unified_service.list_channels`
    
    return {
        "ok": True,
        "channels": channels
    }

@router.get("/contacts/recent")
async def get_recent_contacts(limit: int = 10):
    """
    Returns a list of recent contacts based on live inbox activity.
    Aggregates active senders from Slack, Gmail, and Discord.
    """
    contacts = {}
    
    # helper to add contact
    def add_contact(email_or_name: str, provider: str, avatar: str = None):
        if not email_or_name or email_or_name.lower() in ["unknown", "slackbot", "bot"]:
            return
            
        key = email_or_name.lower()
        if key not in contacts:
            contacts[key] = {
                "id": key,
                "name": email_or_name,
                "provider": provider,
                "status": "online" if provider == "slack" else "offline",
                "last_seen": datetime.now().isoformat(),
                "avatar": avatar or f"https://ui-avatars.com/api/?name={email_or_name}&background=random"
            }
    
    # 1. Fetch recent messages (reusing fetch logic)
    try:
        # Slack
        if SLACK_AVAILABLE:
            slack_msgs = await fetch_slack_recent(limit=20)
            for m in slack_msgs:
                add_contact(m.get("sender"), "slack")
                
        # Gmail
        if GMAIL_AVAILABLE:
            gmail_msgs = await fetch_gmail_recent(limit=20)
            for m in gmail_msgs:
                sender = m.get("sender", "")
                add_contact(sender, "gmail")
                
        # Discord
        if DISCORD_AVAILABLE:
            discord_msgs = await fetch_discord_recent(limit=20)
            for m in discord_msgs:
                add_contact(m.get("sender"), "discord")
                
            zoho_msgs = await fetch_zoho_mail_recent(limit=20)
            for m in zoho_msgs:
                add_contact(m.get("sender"), "zoho")

        # Outlook
        if M365_AVAILABLE:
            outlook_msgs = await fetch_outlook_recent(limit=20)
            for m in outlook_msgs:
                add_contact(m.get("sender"), "outlook")
            
            teams_msgs = await fetch_teams_recent(limit=20)
            for m in teams_msgs:
                add_contact(m.get("sender"), "teams")
                
    except Exception as e:
        logger.error(f"Error fetching recent contacts: {e}")
        
    contact_list = list(contacts.values())
    return {
        "ok": True,
        "contacts": contact_list[:limit]
    }

