"""
Factory for core platform models.

Provides factories for Tenant, UserAccount, OAuthToken, and ChatMessage models.
Note: Workspace, Team, and ChatSession factories already exist in workspace_factory.py
and chat_session_factory.py respectively.
"""

import factory
from factory import fuzzy
from tests.factories.base import BaseFactory
from core.models import (
    Tenant,
    UserAccount,
    OAuthToken,
    ChatMessage,
)


class TenantFactory(BaseFactory):
    """Factory for creating Tenant instances."""

    class Meta:
        model = Tenant

    # Required fields
    id = factory.Faker('uuid4')
    name = factory.Faker('company')
    subdomain = factory.Faker('domain_name')  # e.g., "example.org"

    # Optional fields
    plan_type = fuzzy.FuzzyChoice(['personal', 'team', 'enterprise'])
    edition = fuzzy.FuzzyChoice(['personal', 'professional', 'enterprise'])
    created_at = factory.Faker('date_time_this_year')


class UserAccountFactory(BaseFactory):
    """Factory for creating UserAccount instances (IM platform linking)."""

    class Meta:
        model = UserAccount

    # Required fields
    id = factory.Faker('uuid4')
    user_id = factory.Faker('uuid4')
    tenant_id = factory.Faker('uuid4')
    platform = fuzzy.FuzzyChoice(['slack', 'discord', 'teams', 'telegram'])

    # Optional fields
    platform_user_id = factory.Faker('user_name')
    chat_id = factory.Faker('uuid4')
    username = factory.Faker('user_name')
    linked_at = factory.Faker('date_time_this_year')


class OAuthTokenFactory(BaseFactory):
    """Factory for creating OAuthToken instances.

    OAuthToken is the OAuth-server token store (hash-only columns, no
    provider/access_token/status — provider-scoped tokens live on
    IntegrationToken).
    """

    class Meta:
        model = OAuthToken

    # Required fields
    id = factory.Faker('uuid4')
    client_id = factory.Faker('uuid4')
    user_id = factory.Faker('uuid4')
    tenant_id = factory.Faker('uuid4')
    access_token_hash = factory.Faker('sha256')
    scope = 'openid'

    # Optional fields
    refresh_token_hash = factory.Faker('sha256')
    token_type = 'Bearer'
    access_token_expires_at = factory.Faker('date_time_between', start_date='now', end_date='+30d')
    is_active = True
    created_at = factory.Faker('date_time_this_year')


class ChatMessageFactory(BaseFactory):
    """Factory for creating ChatMessage instances."""

    class Meta:
        model = ChatMessage

    # Required fields
    id = factory.Faker('uuid4')
    conversation_id = factory.Faker('uuid4')
    tenant_id = factory.Faker('uuid4')
    role = fuzzy.FuzzyChoice(['user', 'assistant', 'system'])
    content = factory.Faker('text', max_nb_chars=500)

    # Optional fields
    agent_id = factory.Faker('uuid4')
    metadata_json = factory.LazyFunction(lambda: '{"tokens": 150, "model": "gpt-4"}')
    created_at = factory.Faker('date_time_this_year')
