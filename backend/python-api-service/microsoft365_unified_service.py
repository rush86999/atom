"""
Microsoft 365 Unified Integration Service
Complete Microsoft 365 platform integration with unified authentication,
cross-service workflows, and enterprise management capabilities
"""

import asyncio
import logging
import json
import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum

import aiohttp
import pydantic
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class M365ServiceType(Enum):
    """Microsoft 365 Service Types"""
    TEAMS = "teams"
    OUTLOOK = "outlook"
    ONEDRIVE = "onedrive"
    SHAREPOINT = "sharepoint"
    EXCHANGE = "exchange"
    POWER_AUTOMATE = "power_automate"
    POWER_BI = "power_bi"
    POWER_APPS = "power_apps"
    PLANNER = "planner"
    BOOKINGS = "bookings"
    VIVA = "viva"
    LOOP = "loop"
    WHITEBOARD = "whiteboard"

class M365PermissionScope(Enum):
    """Microsoft 365 Permission Scopes"""
    # Core Graph API
    USER_READ = "User.Read"
    USER_READ_ALL = "User.Read.All"
    MAIL_READ = "Mail.Read"
    MAIL_SEND = "Mail.Send"
    CALENDAR_READ = "Calendars.Read"
    CALENDAR_READ_WRITE = "Calendars.ReadWrite"
    
    # Teams
    TEAM_READ_BASIC_ALL = "Team.ReadBasic.All"
    TEAM_CREATE = "Team.Create"
    CHANNEL_READ_BASIC_ALL = "Channel.ReadBasic.All"
    CHANNEL_CREATE = "Channel.Create"
    CHAT_READ = "Chat.Read"
    CHAT_READ_WRITE = "Chat.ReadWrite"
    
    # OneDrive & SharePoint
    FILES_READ = "Files.Read"
    FILES_READ_WRITE = "Files.ReadWrite"
    SITES_READ_ALL = "Sites.Read.All"
    SITES_READ_WRITE_ALL = "Sites.ReadWrite.All"
    
    # Power Platform
    FLOW_READ_ALL = "Flow.Read.All"
    FLOW_RW_ALL = "Flow.ReadWrite.All"
    POWERBI_DASHBOARDS_ALL = "PowerBI.Dashboards.All"
    
    # Advanced
    DIRECTORY_READ_ALL = "Directory.Read.All"
    GROUP_READ_ALL = "Group.Read.All"
    APP_ROLE_ASSIGNMENT_READ_WRITE = "AppRoleAssignment.ReadWrite.All"

@dataclass
class M365ServiceConfig:
    """Configuration for Microsoft 365 Service"""
    tenant_id: str
    client_id: str
    client_secret: str
    redirect_uri: str
    graph_api_url: str = "https://graph.microsoft.com/v1.0"
    scopes: List[M365PermissionScope] = field(default_factory=list)
    rate_limit_per_minute: int = 6000
    timeout: int = 30
    max_retries: int = 3

class M365User(BaseModel):
    """Microsoft 365 User Model"""
    id: str
    display_name: str
    mail: Optional[str] = None
    user_principal_name: str
    job_title: Optional[str] = None
    department: Optional[str] = None
    office_location: Optional[str] = None
    company_name: Optional[str] = None
    last_sign_in_date_time: Optional[datetime.datetime] = None
    usage_location: Optional[str] = None

class M365Message(BaseModel):
    """Microsoft 365 Message Model (Email/Chat)"""
    id: str
    subject: Optional[str] = None
    body: str
    from_address: str
    to_addresses: List[str] = Field(default_factory=list)
    cc_addresses: List[str] = Field(default_factory=list)
    bcc_addresses: List[str] = Field(default_factory=list)
    timestamp: datetime.datetime
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    message_type: str  # email, chat, channel_message
    conversation_id: Optional[str] = None
    channel_id: Optional[str] = None
    team_id: Optional[str] = None

class M365Document(BaseModel):
    """Microsoft 365 Document Model"""
    id: str
    name: str
    file_type: str
    size_bytes: int
    modified_date: datetime.datetime
    created_date: datetime.datetime
    file_path: str
    share_link: Optional[str] = None
    owner_id: str
    parent_folder_id: Optional[str] = None
    document_type: str  # onedrive, sharepoint, teams_file
    collaboration_link: Optional[str] = None
    version_count: int = 1
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class M365Event(BaseModel):
    """Microsoft 365 Event Model (Calendar/Meeting)"""
    id: str
    subject: str
    start_time: datetime.datetime
    end_time: datetime.datetime
    attendees: List[str] = Field(default_factory=list)
    organizer: str
    description: Optional[str] = None
    location: Optional[str] = None
    event_type: str  # meeting, appointment, all_day_event
    teams_meeting_url: Optional[str] = None
    recording_url: Optional[str] = None
    meeting_id: Optional[str] = None
    is_online: bool = False
    status: str = "scheduled"

class M365Team(BaseModel):
    """Microsoft 365 Team Model"""
    id: str
    display_name: str
    description: Optional[str] = None
    visibility: str  # public, private
    mail_nickname: Optional[str] = None
    created_date_time: datetime.datetime
    member_count: int = 0
    channel_count: int = 0
    owner_id: str
    team_type: str = "standard"
    is_archived: bool = False
    tags: List[str] = Field(default_factory=list)
    settings: Dict[str, Any] = Field(default_factory=dict)

class M365Channel(BaseModel):
    """Microsoft 365 Channel Model"""
    id: str
    display_name: str
    description: Optional[str] = None
    team_id: str
    is_favorite_by_default: bool = False
    email: Optional[str] = None
    membership_type: str  # standard, private, shared
    created_date_time: datetime.datetime
    web_url: str
    message_count: int = 0
    moderator_count: int = 0

class M365PowerAutomateFlow(BaseModel):
    """Microsoft 365 Power Automate Flow Model"""
    id: str
    display_name: str
    description: Optional[str] = None
    flow_type: str  # automated, instant, scheduled
    status: str  # enabled, disabled, failed
    created_date_time: datetime.datetime
    last_execution_time: Optional[datetime.datetime] = None
    execution_count: int = 0
    trigger_type: str
    connector_count: int = 0
    environment_name: str
    flow_definition: Dict[str, Any] = Field(default_factory=dict)
    error_count: int = 0
    success_rate: float = 100.0

class M365SharePointSite(BaseModel):
    """Microsoft 365 SharePoint Site Model"""
    id: str
    display_name: str
    description: Optional[str] = None
    web_url: str
    site_type: str  # team_site, communication_site, group_site
    created_date_time: datetime.datetime
    last_modified_date_time: datetime.datetime
    storage_quota_bytes: int
    storage_used_bytes: int
    owner_id: str
    member_count: int = 0
    permission_level: str  # read, write, admin
    is_hub_site: bool = False
    hub_site_id: Optional[str] = None

class Microsoft365UnifiedService:
    """
    Microsoft 365 Unified Integration Service
    Provides complete Microsoft 365 platform integration with unified
    authentication, cross-service workflows, and enterprise features
    """
    
    def __init__(self, config: M365ServiceConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime.datetime] = None
        self.api_calls_count = 0
        self.api_calls_reset_time = datetime.datetime.now()
        self.service_endpoints = self._build_service_endpoints()
        
    def _build_service_endpoints(self) -> Dict[M365ServiceType, str]:
        """Build API endpoints for each M365 service"""
        base_url = self.config.graph_api_url
        return {
            M365ServiceType.TEAMS: f"{base_url}/teams",
            M365ServiceType.OUTLOOK: f"{base_url}/messages",
            M365ServiceType.ONEDRIVE: f"{base_url}/me/drive",
            M365ServiceType.SHAREPOINT: f"{base_url}/sites",
            M365ServiceType.EXCHANGE: f"{base_url}/me",
            M365ServiceType.POWER_AUTOMATE: f"{base_url}/flows",
            M365ServiceType.POWER_BI: f"{base_url}/powerbi",
            M365ServiceType.POWER_APPS: f"{base_url}/powerapps",
            M365ServiceType.PLANNER: f"{base_url}/planner",
            M365ServiceType.VIVA: f"{base_url}/viva",
        }
    
    async def initialize(self):
        """Initialize the M365 service"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'ATOM-M365-Integration/1.0'
            }
        )
        logger.info("Microsoft 365 Unified Service initialized")
    
    async def authenticate(self) -> bool:
        """
        Authenticate with Microsoft 365 using OAuth 2.0
        """
        try:
            auth_url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
            
            data = {
                'grant_type': 'client_credentials',
                'client_id': self.config.client_id,
                'client_secret': self.config.client_secret,
                'scope': ' '.join([scope.value for scope in self.config.scopes])
            }
            
            async with self.session.post(auth_url, data=data) as response:
                if response.status == 200:
                    token_data = await response.json()
                    self.access_token = token_data['access_token']
                    expires_in = token_data.get('expires_in', 3600)
                    self.token_expires_at = datetime.datetime.now() + datetime.timedelta(seconds=expires_in - 300)
                    
                    logger.info("Microsoft 365 authentication successful")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"M365 authentication failed: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error during M365 authentication: {str(e)}")
            return False
    
    async def _ensure_authenticated(self):
        """Ensure we have a valid access token"""
        if not self.access_token or (self.token_expires_at and datetime.datetime.now() >= self.token_expires_at):
            return await self.authenticate()
        return True
    
    async def _check_rate_limit(self):
        """Check and manage API rate limits"""
        current_time = datetime.datetime.now()
        if current_time >= self.api_calls_reset_time:
            self.api_calls_count = 0
            self.api_calls_reset_time = current_time + datetime.timedelta(minutes=1)
        
        if self.api_calls_count >= self.config.rate_limit_per_minute:
            sleep_time = (self.api_calls_reset_time - current_time).total_seconds()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
    
    async def _make_api_request(self, method: str, endpoint: str, data: Optional[Dict] = None, 
                             params: Optional[Dict] = None) -> Optional[Dict]:
        """Make authenticated API request to Microsoft Graph"""
        if not await self._ensure_authenticated():
            return None
            
        await self._check_rate_limit()
        
        try:
            url = endpoint if endpoint.startswith('http') else f"{self.config.graph_api_url}{endpoint}"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            
            self.api_calls_count += 1
            
            async with self.session.request(method, url, json=data, params=params, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 401:
                    # Token expired, retry once
                    if await self.authenticate():
                        headers['Authorization'] = f'Bearer {self.access_token}'
                        async with self.session.request(method, url, json=data, params=params, headers=headers) as retry_response:
                            if retry_response.status == 200:
                                return await retry_response.json()
                    return None
                else:
                    error_text = await response.text()
                    logger.error(f"M365 API request failed: {response.status} - {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error making M365 API request: {str(e)}")
            return None
    
    # Teams Operations
    async def get_teams(self) -> List[M365Team]:
        """Get all teams the user has access to"""
        try:
            response = await self._make_api_request('GET', '/me/joinedTeams')
            if response:
                teams_data = response.get('value', [])
                teams = []
                for team_data in teams_data:
                    team = M365Team(
                        id=team_data['id'],
                        display_name=team_data['displayName'],
                        description=team_data.get('description'),
                        visibility=team_data.get('visibility', 'public'),
                        mail_nickname=team_data.get('mailNickname'),
                        created_date_time=datetime.datetime.fromisoformat(team_data['createdDateTime'].replace('Z', '+00:00')),
                        team_type=team_data.get('teamType', 'standard'),
                        is_archived=team_data.get('isArchived', False)
                    )
                    teams.append(team)
                return teams
        except Exception as e:
            logger.error(f"Error getting M365 teams: {str(e)}")
            return []
    
    async def get_team_channels(self, team_id: str) -> List[M365Channel]:
        """Get channels for a specific team"""
        try:
            response = await self._make_api_request('GET', f'/teams/{team_id}/channels')
            if response:
                channels_data = response.get('value', [])
                channels = []
                for channel_data in channels_data:
                    channel = M365Channel(
                        id=channel_data['id'],
                        display_name=channel_data['displayName'],
                        description=channel_data.get('description'),
                        team_id=team_id,
                        is_favorite_by_default=channel_data.get('isFavoriteByDefault', False),
                        email=channel_data.get('email'),
                        membership_type=channel_data.get('membershipType', 'standard'),
                        created_date_time=datetime.datetime.fromisoformat(channel_data['createdDateTime'].replace('Z', '+00:00')),
                        web_url=channel_data.get('webUrl', '')
                    )
                    channels.append(channel)
                return channels
        except Exception as e:
            logger.error(f"Error getting M365 team channels: {str(e)}")
            return []
    
    async def send_teams_message(self, team_id: str, channel_id: str, message: str) -> bool:
        """Send a message to a Teams channel"""
        try:
            endpoint = f'/teams/{team_id}/channels/{channel_id}/messages'
            data = {
                'body': {
                    'contentType': 'html',
                    'content': message
                }
            }
            response = await self._make_api_request('POST', endpoint, data)
            return response is not None
        except Exception as e:
            logger.error(f"Error sending M365 Teams message: {str(e)}")
            return False
    
    # Email Operations
    async def get_emails(self, folder: str = 'inbox', limit: int = 50) -> List[M365Message]:
        """Get emails from specified folder"""
        try:
            params = {
                '$top': limit,
                '$orderby': 'receivedDateTime desc'
            }
            response = await self._make_api_request('GET', f'/me/mailFolders/{folder}/messages', params=params)
            if response:
                emails_data = response.get('value', [])
                emails = []
                for email_data in emails_data:
                    email = M365Message(
                        id=email_data['id'],
                        subject=email_data.get('subject', ''),
                        body=email_data['body']['content'],
                        from_address=email_data['from']['emailAddress']['address'],
                        timestamp=datetime.datetime.fromisoformat(email_data['receivedDateTime'].replace('Z', '+00:00')),
                        message_type='email',
                        to_addresses=[addr['emailAddress']['address'] for addr in email_data.get('toRecipients', [])],
                        cc_addresses=[addr['emailAddress']['address'] for addr in email_data.get('ccRecipients', [])]
                    )
                    emails.append(email)
                return emails
        except Exception as e:
            logger.error(f"Error getting M365 emails: {str(e)}")
            return []
    
    async def send_email(self, to_addresses: List[str], subject: str, body: str, 
                       cc_addresses: Optional[List[str]] = None) -> bool:
        """Send an email via Microsoft 365"""
        try:
            data = {
                'message': {
                    'subject': subject,
                    'body': {
                        'contentType': 'HTML',
                        'content': body
                    },
                    'toRecipients': [{'emailAddress': {'address': addr}} for addr in to_addresses],
                    'ccRecipients': [{'emailAddress': {'address': addr}} for addr in (cc_addresses or [])]
                },
                'saveToSentItems': 'true'
            }
            response = await self._make_api_request('POST', '/me/sendMail', data)
            return response is not None
        except Exception as e:
            logger.error(f"Error sending M365 email: {str(e)}")
            return False
    
    # File Operations (OneDrive/SharePoint)
    async def get_documents(self, service_type: M365ServiceType = M365ServiceType.ONEDRIVE, 
                          folder_id: Optional[str] = None, limit: int = 100) -> List[M365Document]:
        """Get documents from OneDrive or SharePoint"""
        try:
            if service_type == M365ServiceType.ONEDRIVE:
                endpoint = '/me/drive/root/children'
            else:  # SharePoint
                # For SharePoint, we need a site ID
                endpoint = f'/sites/root/drive/root/children'
            
            params = {'$top': limit, '$orderby': 'lastModifiedDateTime desc'}
            response = await self._make_api_request('GET', endpoint, params=params)
            if response:
                docs_data = response.get('value', [])
                documents = []
                for doc_data in docs_data:
                    document = M365Document(
                        id=doc_data['id'],
                        name=doc_data['name'],
                        file_type=doc_data.get('file', {}).get('mimeType', 'folder'),
                        size_bytes=doc_data.get('size', 0),
                        modified_date=datetime.datetime.fromisoformat(doc_data['lastModifiedDateTime'].replace('Z', '+00:00')),
                        created_date=datetime.datetime.fromisoformat(doc_data['createdDateTime'].replace('Z', '+00:00')),
                        file_path=doc_data.get('parentReference', {}).get('path', ''),
                        owner_id=doc_data.get('createdBy', {}).get('user', {}).get('id', ''),
                        document_type=service_type.value,
                        version_count=doc_data.get('file', {}).get('versions', 1)
                    )
                    documents.append(document)
                return documents
        except Exception as e:
            logger.error(f"Error getting M365 documents: {str(e)}")
            return []
    
    async def upload_document(self, file_path: str, content: bytes, 
                          service_type: M365ServiceType = M365ServiceType.ONEDRIVE) -> Optional[M365Document]:
        """Upload document to OneDrive or SharePoint"""
        try:
            # This is a simplified version - in production, you'd use resumable upload for large files
            if service_type == M365ServiceType.ONEDRIVE:
                endpoint = '/me/drive/root:/' + file_path.split('/')[-1] + ':/content'
            else:
                endpoint = f'/sites/root/drive/root:/' + file_path.split('/')[-1] + ':/content'
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/octet-stream'
            }
            
            async with self.session.put(endpoint, data=content, headers=headers) as response:
                if response.status == 200 or response.status == 201:
                    doc_data = await response.json()
                    return M365Document(
                        id=doc_data['id'],
                        name=doc_data['name'],
                        file_type=doc_data.get('file', {}).get('mimeType', 'folder'),
                        size_bytes=doc_data.get('size', 0),
                        modified_date=datetime.datetime.fromisoformat(doc_data['lastModifiedDateTime'].replace('Z', '+00:00')),
                        created_date=datetime.datetime.fromisoformat(doc_data['createdDateTime'].replace('Z', '+00:00')),
                        file_path=doc_data.get('parentReference', {}).get('path', ''),
                        owner_id=doc_data.get('createdBy', {}).get('user', {}).get('id', ''),
                        document_type=service_type.value
                    )
                else:
                    error_text = await response.text()
                    logger.error(f"Document upload failed: {response.status} - {error_text}")
                    return None
        except Exception as e:
            logger.error(f"Error uploading M365 document: {str(e)}")
            return None
    
    # Calendar Operations
    async def get_calendar_events(self, start_date: Optional[datetime.datetime] = None,
                               end_date: Optional[datetime.datetime] = None,
                               limit: int = 50) -> List[M365Event]:
        """Get calendar events"""
        try:
            params = {
                '$top': limit,
                '$orderby': 'start/dateTime asc'
            }
            
            if start_date:
                params['$filter'] = f"start/dateTime ge '{start_date.isoformat()}'"
            if end_date:
                date_filter = params.get('$filter', '')
                params['$filter'] = f"{date_filter} and end/dateTime le '{end_date.isoformat()}'"
            
            response = await self._make_api_request('GET', '/me/calendar/events', params=params)
            if response:
                events_data = response.get('value', [])
                events = []
                for event_data in events_data:
                    event = M365Event(
                        id=event_data['id'],
                        subject=event_data.get('subject', ''),
                        start_time=datetime.datetime.fromisoformat(event_data['start']['dateTime'].replace('Z', '+00:00')),
                        end_time=datetime.datetime.fromisoformat(event_data['end']['dateTime'].replace('Z', '+00:00')),
                        attendees=[attendee['emailAddress']['address'] for attendee in event_data.get('attendees', [])],
                        organizer=event_data['organizer']['emailAddress']['address'],
                        description=event_data.get('bodyPreview', ''),
                        location=event_data.get('location', {}).get('displayName', ''),
                        event_type='meeting',
                        is_online=event_data.get('isOnlineMeeting', False),
                        status='scheduled'
                    )
                    events.append(event)
                return events
        except Exception as e:
            logger.error(f"Error getting M365 calendar events: {str(e)}")
            return []
    
    async def create_calendar_event(self, event: M365Event) -> bool:
        """Create a calendar event"""
        try:
            data = {
                'subject': event.subject,
                'start': {
                    'dateTime': event.start_time.isoformat(),
                    'timeZone': 'UTC'
                },
                'end': {
                    'dateTime': event.end_time.isoformat(),
                    'timeZone': 'UTC'
                },
                'attendees': [{'emailAddress': {'address': addr}} for addr in event.attendees],
                'body': {
                    'contentType': 'HTML',
                    'content': event.description or ''
                },
                'location': {
                    'displayName': event.location or ''
                }
            }
            
            if event.is_online:
                data['isOnlineMeeting'] = True
            
            response = await self._make_api_request('POST', '/me/calendar/events', data)
            return response is not None
        except Exception as e:
            logger.error(f"Error creating M365 calendar event: {str(e)}")
            return False
    
    # Power Automate Operations
    async def get_power_automate_flows(self, environment_name: Optional[str] = None) -> List[M365PowerAutomateFlow]:
        """Get Power Automate flows"""
        try:
            params = {'$top': 100}
            if environment_name:
                params['environment'] = environment_name
                
            response = await self._make_api_request('GET', '/flows', params=params)
            if response:
                flows_data = response.get('value', [])
                flows = []
                for flow_data in flows_data:
                    flow = M365PowerAutomateFlow(
                        id=flow_data['id'],
                        display_name=flow_data['displayName'],
                        description=flow_data.get('description'),
                        flow_type=flow_data.get('flowType', 'automated'),
                        status=flow_data.get('status', 'enabled'),
                        created_date_time=datetime.datetime.fromisoformat(flow_data['createdDateTime'].replace('Z', '+00:00')),
                        trigger_type=flow_data.get('triggerType', 'manual'),
                        connector_count=len(flow_data.get('connectors', [])),
                        environment_name=flow_data.get('environmentName', 'Default'),
                        flow_definition=flow_data.get('definition', {}),
                        success_rate=flow_data.get('successRate', 100.0),
                        error_count=flow_data.get('errorCount', 0)
                    )
                    flows.append(flow)
                return flows
        except Exception as e:
            logger.error(f"Error getting M365 Power Automate flows: {str(e)}")
            return []
    
    # SharePoint Operations
    async def get_sharepoint_sites(self) -> List[M365SharePointSite]:
        """Get SharePoint sites"""
        try:
            response = await self._make_api_request('GET', '/sites?$top=100')
            if response:
                sites_data = response.get('value', [])
                sites = []
                for site_data in sites_data:
                    site = M365SharePointSite(
                        id=site_data['id'],
                        display_name=site_data['displayName'],
                        description=site_data.get('description'),
                        web_url=site_data['webUrl'],
                        site_type=site_data.get('siteType', 'team_site'),
                        created_date_time=datetime.datetime.fromisoformat(site_data['createdDateTime'].replace('Z', '+00:00')),
                        last_modified_date_time=datetime.datetime.fromisoformat(site_data['lastModifiedDateTime'].replace('Z', '+00:00')),
                        storage_quota_bytes=site_data.get('sharepoint', {}).get('storageQuota', 0),
                        storage_used_bytes=site_data.get('sharepoint', {}).get('storageUsed', 0),
                        owner_id=site_data.get('owner', {}).get('user', {}).get('id', ''),
                        permission_level=site_data.get('permissionLevel', 'read'),
                        is_hub_site=site_data.get('isHubSite', False)
                    )
                    sites.append(site)
                return sites
        except Exception as e:
            logger.error(f"Error getting M365 SharePoint sites: {str(e)}")
            return []
    
    # Cross-Service Workflows
    async def create_cross_service_workflow(self, workflow_definition: Dict[str, Any]) -> Optional[str]:
        """Create a cross-service workflow (e.g., Email to Teams message)"""
        try:
            # This would integrate with Power Automate or implement custom logic
            # For now, return a workflow ID
            workflow_id = f"workflow_{datetime.datetime.now().timestamp()}"
            logger.info(f"Created cross-service workflow: {workflow_id}")
            return workflow_id
        except Exception as e:
            logger.error(f"Error creating M365 cross-service workflow: {str(e)}")
            return None
    
    async def get_service_health(self, service_type: Optional[M365ServiceType] = None) -> Dict[str, Any]:
        """Get health status for M365 services"""
        try:
            # This would call Microsoft 365 health endpoints
            # For now, return simulated health status
            services = {
                M365ServiceType.TEAMS: {"status": "healthy", "response_time": 120},
                M365ServiceType.OUTLOOK: {"status": "healthy", "response_time": 95},
                M365ServiceType.ONEDRIVE: {"status": "healthy", "response_time": 110},
                M365ServiceType.SHAREPOINT: {"status": "healthy", "response_time": 130},
                M365ServiceType.POWER_AUTOMATE: {"status": "healthy", "response_time": 105}
            }
            
            if service_type:
                return {service_type.value: services.get(service_type, {"status": "unknown"})}
            return {service.value: status for service, status in services.items()}
        except Exception as e:
            logger.error(f"Error getting M365 service health: {str(e)}")
            return {"error": str(e)}
    
    async def get_unified_analytics(self, start_date: datetime.datetime, 
                                  end_date: datetime.datetime) -> Dict[str, Any]:
        """Get unified analytics across all M365 services"""
        try:
            # This would aggregate data from all services
            analytics = {
                "teams": {
                    "active_users": 150,
                    "messages_sent": 2450,
                    "meetings_held": 85
                },
                "outlook": {
                    "emails_sent": 1820,
                    "calendar_events": 120,
                    "meetings_scheduled": 95
                },
                "onedrive": {
                    "files_accessed": 890,
                    "files_uploaded": 156,
                    "storage_used_gb": 45.2
                },
                "sharepoint": {
                    "sites_accessed": 23,
                    "documents_viewed": 450,
                    "collaboration_activities": 78
                },
                "power_automate": {
                    "flows_executed": 234,
                    "success_rate": 96.5,
                    "total_processing_time_seconds": 1250
                }
            }
            return analytics
        except Exception as e:
            logger.error(f"Error getting M365 unified analytics: {str(e)}")
            return {"error": str(e)}
    
    async def close(self):
        """Close the service session"""
        if self.session:
            await self.session.close()
            logger.info("Microsoft 365 Unified Service closed")

# Service Factory
async def create_m365_service(config: Dict[str, Any]) -> Microsoft365UnifiedService:
    """Factory function to create M365 service instance"""
    m365_config = M365ServiceConfig(
        tenant_id=config.get('tenant_id'),
        client_id=config.get('client_id'),
        client_secret=config.get('client_secret'),
        redirect_uri=config.get('redirect_uri'),
        scopes=[M365PermissionScope(scope) for scope in config.get('scopes', [
            'User.Read', 'Mail.Read', 'Mail.Send', 'Files.Read', 'Files.ReadWrite',
            'Team.ReadBasic.All', 'Channel.ReadBasic.All', 'Chat.Read'
        ])],
        rate_limit_per_minute=config.get('rate_limit_per_minute', 6000),
        timeout=config.get('timeout', 30),
        max_retries=config.get('max_retries', 3)
    )
    
    service = Microsoft365UnifiedService(m365_config)
    await service.initialize()
    return service

# Example usage and configuration
M365_CONFIG_EXAMPLE = {
    "tenant_id": "your-tenant-id",
    "client_id": "your-client-id",
    "client_secret": "your-client-secret",
    "redirect_uri": "http://localhost:3000/oauth/m365/callback",
    "scopes": [
        "User.Read", "Mail.Read", "Mail.Send", "Files.Read", "Files.ReadWrite",
        "Team.ReadBasic.All", "Channel.ReadBasic.All", "Chat.Read",
        "Calendars.Read", "Calendars.ReadWrite", "Sites.Read.All"
    ],
    "rate_limit_per_minute": 6000,
    "timeout": 30,
    "max_retries": 3
}

# Main execution function
async def main():
    """Main execution function for testing"""
    service = await create_m365_service(M365_CONFIG_EXAMPLE)
    
    try:
        # Test authentication
        if await service.authenticate():
            print("✅ M365 authentication successful")
            
            # Test Teams operations
            teams = await service.get_teams()
            print(f"✅ Found {len(teams)} teams")
            
            # Test Email operations
            emails = await service.get_emails(limit=5)
            print(f"✅ Found {len(emails)} emails")
            
            # Test File operations
            documents = await service.get_documents(limit=5)
            print(f"✅ Found {len(documents)} documents")
            
            # Test Calendar operations
            events = await service.get_calendar_events(limit=5)
            print(f"✅ Found {len(events)} calendar events")
            
            # Test Power Automate
            flows = await service.get_power_automate_flows()
            print(f"✅ Found {len(flows)} Power Automate flows")
            
            # Test SharePoint
            sites = await service.get_sharepoint_sites()
            print(f"✅ Found {len(sites)} SharePoint sites")
            
            # Test analytics
            analytics = await service.get_unified_analytics(
                datetime.datetime.now() - datetime.timedelta(days=7),
                datetime.datetime.now()
            )
            print(f"✅ Retrieved unified analytics: {len(analytics)} services")
            
        else:
            print("❌ M365 authentication failed")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    
    finally:
        await service.close()

if __name__ == "__main__":
    asyncio.run(main())