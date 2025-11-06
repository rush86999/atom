"""
Slack Integration Configuration
Complete configuration management for Slack integration
"""

import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class SyncFrequency(Enum):
    REALTIME = "realtime"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class MessageScope(Enum):
    MESSAGES = "messages"
    REPLIES = "replies"
    FILES = "files"
    THREADS = "threads"
    REACTIONS = "reactions"
    MENTIONS = "mentions"


@dataclass
class SlackAPIConfig:
    """Slack API configuration"""
    api_base_url: str
    client_id: str
    client_secret: str
    signing_secret: str
    redirect_uri: str
    timeout: int = 30
    max_retries: int = 3
    retry_delay: int = 1


@dataclass
class SlackOAuthConfig:
    """Slack OAuth configuration"""
    scopes: List[str]
    required_scopes: List[str]
    optional_scopes: List[str]
    state_ttl: int = 600  # 10 minutes


@dataclass
class SlackRateLimitConfig:
    """Rate limiting configuration"""
    tier_1_limit: int = 1  # 1 per minute (Search)
    tier_2_limit: int = 1  # 1 per second (Actions)
    tier_3_limit: int = 20  # 20+ per second (Fetching)
    default_backoff: float = 1.0
    max_backoff: float = 60.0
    backoff_multiplier: float = 2.0


@dataclass
class SlackCacheConfig:
    """Caching configuration"""
    enabled: bool = True
    ttl: int = 300  # 5 minutes
    max_size: int = 1000
    workspace_ttl: int = 3600  # 1 hour
    channel_ttl: int = 1800  # 30 minutes
    user_ttl: int = 900  # 15 minutes


@dataclass
class SlackSyncConfig:
    """Data synchronization configuration"""
    frequency: SyncFrequency
    message_scopes: List[MessageScope]
    batch_size: int = 100
    max_concurrent_requests: int = 5
    retry_failed_requests: bool = True
    sync_archived: bool = False
    sync_private: bool = False
    sync_bots: bool = False
    date_range_days: int = 90


@dataclass
class SlackNotificationConfig:
    """Notification configuration"""
    new_messages: bool = True
    mentions: bool = True
    file_shares: bool = True
    channel_updates: bool = False
    workspace_updates: bool = False
    webhook_url: Optional[str] = None


@dataclass
class SlackAnalyticsConfig:
    """Analytics configuration"""
    enabled: bool = True
    activity_tracking: bool = True
    sentiment_analysis: bool = False
    engagement_metrics: bool = True
    trending_topics: bool = True
    export_interval_hours: int = 24


@dataclass
class SlackWebhookConfig:
    """Webhook configuration"""
    events_url: str
    enabled_events: List[str]
    verification_enabled: bool = True
    retry_failed_events: bool = True
    max_retry_attempts: int = 3
    event_timeout: int = 30


@dataclass
class SlackIntegrationConfig:
    """Complete Slack integration configuration"""
    api: SlackAPIConfig
    oauth: SlackOAuthConfig
    rate_limits: SlackRateLimitConfig
    cache: SlackCacheConfig
    sync: SlackSyncConfig
    notifications: SlackNotificationConfig
    analytics: SlackAnalyticsConfig
    webhooks: SlackWebhookConfig


class SlackConfigManager:
    """Manages Slack integration configuration"""
    
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self) -> SlackIntegrationConfig:
        """Load configuration from environment and defaults"""
        
        # API Configuration
        api_config = SlackAPIConfig(
            api_base_url=os.getenv('SLACK_API_BASE_URL', 'https://slack.com/api'),
            client_id=os.getenv('SLACK_CLIENT_ID', ''),
            client_secret=os.getenv('SLACK_CLIENT_SECRET', ''),
            signing_secret=os.getenv('SLACK_SIGNING_SECRET', ''),
            redirect_uri=os.getenv('SLACK_REDIRECT_URI', 'http://localhost:3000/integrations/slack/callback'),
            timeout=int(os.getenv('SLACK_TIMEOUT', '30')),
            max_retries=int(os.getenv('SLACK_MAX_RETRIES', '3')),
            retry_delay=int(os.getenv('SLACK_RETRY_DELAY', '1'))
        )
        
        # OAuth Configuration
        required_scopes = [
            'channels:read',
            'channels:history',
            'groups:read',
            'groups:history',
            'im:read',
            'im:history',
            'mpim:read',
            'mpim:history',
            'users:read',
            'users:read.email',
            'team:read',
            'files:read',
            'reactions:read'
        ]
        
        optional_scopes = [
            'chat:write',
            'chat:write.public',
            'channels:manage',
            'groups:manage',
            'users:write'
        ]
        
        oauth_config = SlackOAuthConfig(
            scopes=required_scopes + optional_scopes,
            required_scopes=required_scopes,
            optional_scopes=optional_scopes,
            state_ttl=int(os.getenv('SLACK_STATE_TTL', '600'))
        )
        
        # Rate Limit Configuration
        rate_limit_config = SlackRateLimitConfig(
            tier_1_limit=int(os.getenv('SLACK_RATE_LIMIT_TIER1', '1')),
            tier_2_limit=int(os.getenv('SLACK_RATE_LIMIT_TIER2', '1')),
            tier_3_limit=int(os.getenv('SLACK_RATE_LIMIT_TIER3', '20')),
            default_backoff=float(os.getenv('SLACK_DEFAULT_BACKOFF', '1.0')),
            max_backoff=float(os.getenv('SLACK_MAX_BACKOFF', '60.0')),
            backoff_multiplier=float(os.getenv('SLACK_BACKOFF_MULTIPLIER', '2.0'))
        )
        
        # Cache Configuration
        cache_config = SlackCacheConfig(
            enabled=os.getenv('SLACK_CACHE_ENABLED', 'true').lower() == 'true',
            ttl=int(os.getenv('SLACK_CACHE_TTL', '300')),
            max_size=int(os.getenv('SLACK_CACHE_MAX_SIZE', '1000')),
            workspace_ttl=int(os.getenv('SLACK_WORKSPACE_CACHE_TTL', '3600')),
            channel_ttl=int(os.getenv('SLACK_CHANNEL_CACHE_TTL', '1800')),
            user_ttl=int(os.getenv('SLACK_USER_CACHE_TTL', '900'))
        )
        
        # Sync Configuration
        sync_frequency = os.getenv('SLACK_SYNC_FREQUENCY', 'realtime')
        sync_scopes_env = os.getenv('SLACK_SYNC_SCOPES', 'messages,replies,files')
        sync_scopes = [MessageScope(scope.strip()) for scope in sync_scopes_env.split(',')]
        
        sync_config = SlackSyncConfig(
            frequency=SyncFrequency(sync_frequency),
            message_scopes=sync_scopes,
            batch_size=int(os.getenv('SLACK_SYNC_BATCH_SIZE', '100')),
            max_concurrent_requests=int(os.getenv('SLACK_MAX_CONCURRENT_REQUESTS', '5')),
            retry_failed_requests=os.getenv('SLACK_RETRY_FAILED_REQUESTS', 'true').lower() == 'true',
            sync_archived=os.getenv('SLACK_SYNC_ARCHIVED', 'false').lower() == 'true',
            sync_private=os.getenv('SLACK_SYNC_PRIVATE', 'false').lower() == 'true',
            sync_bots=os.getenv('SLACK_SYNC_BOTS', 'false').lower() == 'true',
            date_range_days=int(os.getenv('SLACK_DATE_RANGE_DAYS', '90'))
        )
        
        # Notification Configuration
        notification_config = SlackNotificationConfig(
            new_messages=os.getenv('SLACK_NOTIFY_NEW_MESSAGES', 'true').lower() == 'true',
            mentions=os.getenv('SLACK_NOTIFY_MENTIONS', 'true').lower() == 'true',
            file_shares=os.getenv('SLACK_NOTIFY_FILE_SHARES', 'true').lower() == 'true',
            channel_updates=os.getenv('SLACK_NOTIFY_CHANNEL_UPDATES', 'false').lower() == 'true',
            workspace_updates=os.getenv('SLACK_NOTIFY_WORKSPACE_UPDATES', 'false').lower() == 'true',
            webhook_url=os.getenv('SLACK_NOTIFICATION_WEBHOOK_URL')
        )
        
        # Analytics Configuration
        analytics_config = SlackAnalyticsConfig(
            enabled=os.getenv('SLACK_ANALYTICS_ENABLED', 'true').lower() == 'true',
            activity_tracking=os.getenv('SLACK_ACTIVITY_TRACKING', 'true').lower() == 'true',
            sentiment_analysis=os.getenv('SLACK_SENTIMENT_ANALYSIS', 'false').lower() == 'true',
            engagement_metrics=os.getenv('SLACK_ENGAGEMENT_METRICS', 'true').lower() == 'true',
            trending_topics=os.getenv('SLACK_TRENDING_TOPICS', 'true').lower() == 'true',
            export_interval_hours=int(os.getenv('SLACK_ANALYTICS_EXPORT_INTERVAL', '24'))
        )
        
        # Webhook Configuration
        enabled_events_env = os.getenv('SLACK_WEBHOOK_ENABLED_EVENTS', 
            'message,message_changed,message_deleted,file_shared,file_shared,channel_created,channel_deleted')
        enabled_events = [event.strip() for event in enabled_events_env.split(',')]
        
        webhook_config = SlackWebhookConfig(
            events_url=os.getenv('SLACK_WEBHOOK_URL', '/api/integrations/slack/events'),
            enabled_events=enabled_events,
            verification_enabled=os.getenv('SLACK_WEBHOOK_VERIFICATION_ENABLED', 'true').lower() == 'true',
            retry_failed_events=os.getenv('SLACK_RETRY_FAILED_EVENTS', 'true').lower() == 'true',
            max_retry_attempts=int(os.getenv('SLACK_MAX_RETRY_ATTEMPTS', '3')),
            event_timeout=int(os.getenv('SLACK_EVENT_TIMEOUT', '30'))
        )
        
        return SlackIntegrationConfig(
            api=api_config,
            oauth=oauth_config,
            rate_limits=rate_limit_config,
            cache=cache_config,
            sync=sync_config,
            notifications=notification_config,
            analytics=analytics_config,
            webhooks=webhook_config
        )
    
    def get_config(self) -> SlackIntegrationConfig:
        """Get current configuration"""
        return self.config
    
    def update_config(self, updates: Dict[str, Any]):
        """Update configuration with new values"""
        # Implementation for dynamic config updates
        pass
    
    def validate_config(self) -> List[str]:
        """Validate configuration and return list of errors"""
        errors = []
        
        # Validate API config
        if not self.config.api.client_id:
            errors.append("SLACK_CLIENT_ID is required")
        if not self.config.api.client_secret:
            errors.append("SLACK_CLIENT_SECRET is required")
        if not self.config.api.signing_secret:
            errors.append("SLACK_SIGNING_SECRET is required")
        
        # Validate redirect URI
        if not self.config.api.redirect_uri:
            errors.append("SLACK_REDIRECT_URI is required")
        elif not self.config.api.redirect_uri.startswith(('http://', 'https://')):
            errors.append("SLACK_REDIRECT_URI must be a valid URL")
        
        # Validate rate limits
        if self.config.rate_limits.tier_1_limit < 1:
            errors.append("Rate limit tier 1 must be at least 1")
        if self.config.rate_limits.tier_2_limit < 1:
            errors.append("Rate limit tier 2 must be at least 1")
        if self.config.rate_limits.tier_3_limit < 1:
            errors.append("Rate limit tier 3 must be at least 1")
        
        # Validate cache config
        if self.config.cache.enabled:
            if self.config.cache.ttl <= 0:
                errors.append("Cache TTL must be greater than 0")
            if self.config.cache.max_size <= 0:
                errors.append("Cache max size must be greater than 0")
        
        # Validate sync config
        if self.config.sync.batch_size <= 0:
            errors.append("Sync batch size must be greater than 0")
        if self.config.sync.max_concurrent_requests <= 0:
            errors.append("Max concurrent requests must be greater than 0")
        if self.config.sync.date_range_days <= 0:
            errors.append("Date range days must be greater than 0")
        
        # Validate webhook config
        if not self.config.webhooks.events_url:
            errors.append("Webhook events URL is required")
        if not self.config.webhooks.enabled_events:
            errors.append("At least one webhook event must be enabled")
        if self.config.webhooks.event_timeout <= 0:
            errors.append("Event timeout must be greater than 0")
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return asdict(self.config)
    
    def to_json(self) -> str:
        """Convert configuration to JSON string"""
        import json
        return json.dumps(self.to_dict(), indent=2, default=str)
    
    def save_to_file(self, filepath: str):
        """Save configuration to file"""
        with open(filepath, 'w') as f:
            f.write(self.to_json())
    
    def load_from_file(self, filepath: str) -> bool:
        """Load configuration from file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            # Update config with loaded data
            # This would need to properly reconstruct the dataclasses
            return True
        except Exception as e:
            print(f"Failed to load config from {filepath}: {e}")
            return False


# Global configuration manager
slack_config_manager = SlackConfigManager()


def get_slack_config() -> SlackIntegrationConfig:
    """Get global Slack configuration"""
    return slack_config_manager.get_config()


def validate_slack_config() -> List[str]:
    """Validate global Slack configuration"""
    return slack_config_manager.validate_config()


# Environment variable documentation
ENVIRONMENT_VARIABLES = {
    # API Configuration
    'SLACK_API_BASE_URL': {
        'description': 'Slack API base URL',
        'default': 'https://slack.com/api',
        'required': False
    },
    'SLACK_CLIENT_ID': {
        'description': 'Slack OAuth client ID',
        'default': None,
        'required': True
    },
    'SLACK_CLIENT_SECRET': {
        'description': 'Slack OAuth client secret',
        'default': None,
        'required': True
    },
    'SLACK_SIGNING_SECRET': {
        'description': 'Slack webhook signing secret',
        'default': None,
        'required': True
    },
    'SLACK_REDIRECT_URI': {
        'description': 'OAuth callback redirect URI',
        'default': 'http://localhost:3000/integrations/slack/callback',
        'required': True
    },
    'SLACK_TIMEOUT': {
        'description': 'API request timeout in seconds',
        'default': 30,
        'required': False
    },
    'SLACK_MAX_RETRIES': {
        'description': 'Maximum number of retries for failed requests',
        'default': 3,
        'required': False
    },
    
    # Rate Limiting
    'SLACK_RATE_LIMIT_TIER1': {
        'description': 'Rate limit for tier 1 (search) - requests per minute',
        'default': 1,
        'required': False
    },
    'SLACK_RATE_LIMIT_TIER2': {
        'description': 'Rate limit for tier 2 (actions) - requests per second',
        'default': 1,
        'required': False
    },
    'SLACK_RATE_LIMIT_TIER3': {
        'description': 'Rate limit for tier 3 (fetching) - requests per second',
        'default': 20,
        'required': False
    },
    
    # Caching
    'SLACK_CACHE_ENABLED': {
        'description': 'Enable API response caching',
        'default': 'true',
        'required': False
    },
    'SLACK_CACHE_TTL': {
        'description': 'Cache TTL in seconds',
        'default': 300,
        'required': False
    },
    'SLACK_CACHE_MAX_SIZE': {
        'description': 'Maximum cache size',
        'default': 1000,
        'required': False
    },
    
    # Synchronization
    'SLACK_SYNC_FREQUENCY': {
        'description': 'Sync frequency (realtime, hourly, daily, weekly)',
        'default': 'realtime',
        'required': False
    },
    'SLACK_SYNC_SCOPES': {
        'description': 'Comma-separated list of sync scopes',
        'default': 'messages,replies,files',
        'required': False
    },
    'SLACK_SYNC_BATCH_SIZE': {
        'description': 'Batch size for sync operations',
        'default': 100,
        'required': False
    },
    'SLACK_MAX_CONCURRENT_REQUESTS': {
        'description': 'Maximum concurrent API requests',
        'default': 5,
        'required': False
    },
    'SLACK_SYNC_ARCHIVED': {
        'description': 'Include archived channels in sync',
        'default': 'false',
        'required': False
    },
    'SLACK_SYNC_PRIVATE': {
        'description': 'Include private channels in sync',
        'default': 'false',
        'required': False
    },
    'SLACK_SYNC_BOTS': {
        'description': 'Include bot messages in sync',
        'default': 'false',
        'required': False
    },
    
    # Notifications
    'SLACK_NOTIFY_NEW_MESSAGES': {
        'description': 'Enable new message notifications',
        'default': 'true',
        'required': False
    },
    'SLACK_NOTIFY_MENTIONS': {
        'description': 'Enable mention notifications',
        'default': 'true',
        'required': False
    },
    'SLACK_NOTIFY_FILE_SHARES': {
        'description': 'Enable file share notifications',
        'default': 'true',
        'required': False
    },
    
    # Analytics
    'SLACK_ANALYTICS_ENABLED': {
        'description': 'Enable Slack analytics',
        'default': 'true',
        'required': False
    },
    'SLACK_SENTIMENT_ANALYSIS': {
        'description': 'Enable sentiment analysis',
        'default': 'false',
        'required': False
    },
    'SLACK_TRENDING_TOPICS': {
        'description': 'Enable trending topics analysis',
        'default': 'true',
        'required': False
    },
    
    # Webhooks
    'SLACK_WEBHOOK_ENABLED_EVENTS': {
        'description': 'Comma-separated list of enabled webhook events',
        'default': 'message,message_changed,message_deleted,file_shared',
        'required': False
    },
    'SLACK_WEBHOOK_VERIFICATION_ENABLED': {
        'description': 'Enable webhook signature verification',
        'default': 'true',
        'required': False
    }
}


if __name__ == '__main__':
    # Configuration validation
    config = get_slack_config()
    errors = validate_slack_config()
    
    if errors:
        print("Configuration errors found:")
        for error in errors:
            print(f"  - {error}")
    else:
        print("Configuration is valid!")
        print(f"API Base URL: {config.api.api_base_url}")
        print(f"Client ID: {config.api.client_id[:10]}..." if config.api.client_id else "Not set")
        print(f"Cache Enabled: {config.cache.enabled}")
        print(f"Sync Frequency: {config.sync.frequency.value}")
        print(f"Analytics Enabled: {config.analytics.enabled}")