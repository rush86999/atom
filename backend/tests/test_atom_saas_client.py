"""
Test suite for Atom SaaS Client - Marketplace integration and federation support.

Tests cover:
- SaaS marketplace client initialization
- API communication (skills, agents, workflows, domains, components)
- Federation headers and authentication
- Synchronous wrapper methods
- Error handling and edge cases
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
import os
import httpx


# Import target module
from core.atom_saas_client import (
    AtomAgentOSMarketplaceClient,
    AtomSaaSConfig,
    AtomSaaSClient  # Alias
)


class TestAtomSaaSConfig:
    """Test AtomSaaSConfig dataclass."""

    def test_config_creation(self):
        """AtomSaaSConfig can be created with all required fields."""
        config = AtomSaaSConfig(
            ws_url="wss://atomagentos.com/api/ws",
            api_url="https://atomagentos.com/api/v1",
            api_token="test-token-123",
            instance_id="instance-001",
            timeout=30,
            cache_ttl_seconds=300
        )
        assert config.ws_url == "wss://atomagentos.com/api/ws"
        assert config.api_url == "https://atomagentos.com/api/v1"
        assert config.api_token == "test-token-123"
        assert config.instance_id == "instance-001"
        assert config.timeout == 30
        assert config.cache_ttl_seconds == 300

    def test_config_with_defaults(self):
        """AtomSaaSConfig uses default values for optional fields."""
        config = AtomSaaSConfig(
            ws_url="wss://test.com/api",
            api_url="https://test.com/api",
            api_token="token"
        )
        assert config.instance_id is None
        assert config.timeout == 30
        assert config.cache_ttl_seconds == 300


class TestAtomSaaSClientInit:
    """Test AtomAgentOSMarketplaceClient initialization."""

    def test_initialization_with_config(self):
        """Client initializes with provided config."""
        config = AtomSaaSConfig(
            ws_url="wss://test.com/api",
            api_url="https://test.com/api",
            api_token="test-token"
        )

        with patch('core.atom_saas_client.httpx.AsyncClient'):
            client = AtomAgentOSMarketplaceClient(config=config)
            assert client.config.api_token == "test-token"
            assert client._http_client is None
            assert client._connected is False

    def test_initialization_without_config(self):
        """Client initializes with default config from environment."""
        with patch.dict(os.environ, {
            'ATOM_SAAS_API_TOKEN': 'env-token',
            'ATOM_INSTANCE_ID': 'instance-123'
        }):
            with patch('core.atom_saas_client.httpx.AsyncClient'):
                client = AtomAgentOSMarketplaceClient()
                assert client.config.api_token == 'env-token'
                assert client.config.instance_id == 'instance-123'

    def test_instance_id_generation_from_token(self):
        """Instance ID is generated from token if not provided."""
        with patch.dict(os.environ, {
            'ATOM_SAAS_API_TOKEN': 'test-token-for-hash'
        }):
            with patch('core.atom_saas_client.httpx.AsyncClient'):
                client = AtomAgentOSMarketplaceClient()
                # Instance ID should be SHA256 hash of token (first 32 chars)
                assert client.config.instance_id is not None
                assert len(client.config.instance_id) == 32


class TestMarketplaceSkills:
    """Test skill marketplace operations."""

    @pytest.mark.asyncio
    async def test_fetch_skills(self):
        """Client can fetch skills from marketplace."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "skills": [
                {"id": "skill-1", "name": "Data Processing"},
                {"id": "skill-2", "name": "Web Scraping"}
            ],
            "total": 2,
            "page": 1,
            "page_size": 20
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        with patch('core.atom_saas_client.httpx.AsyncClient', return_value=mock_client):
            client = AtomAgentOSMarketplaceClient()
            client._http_client = mock_client

            result = await client.fetch_skills(query="data", category="processing")

            assert result["total"] == 2
            assert len(result["skills"]) == 2
            assert result["skills"][0]["name"] == "Data Processing"

    @pytest.mark.asyncio
    async def test_get_skill_by_id(self):
        """Client can get skill details by ID."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "skill-1",
            "name": "Data Processing",
            "description": "Process data files",
            "category": "data"
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        with patch('core.atom_saas_client.httpx.AsyncClient', return_value=mock_client):
            client = AtomAgentOSMarketplaceClient()
            client._http_client = mock_client

            result = await client.get_skill_by_id("skill-1")

            assert result["id"] == "skill-1"
            assert result["name"] == "Data Processing"

    @pytest.mark.asyncio
    async def test_get_categories(self):
        """Client can fetch skill categories."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"id": "cat-1", "name": "Data Processing"},
            {"id": "cat-2", "name": "Web Scraping"}
        ]
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        with patch('core.atom_saas_client.httpx.AsyncClient', return_value=mock_client):
            client = AtomAgentOSMarketplaceClient()
            client._http_client = mock_client

            result = await client.get_categories()

            assert len(result) == 2
            assert result[0]["name"] == "Data Processing"


class TestMarketplaceAgents:
    """Test agent marketplace operations."""

    @pytest.mark.asyncio
    async def test_fetch_agents(self):
        """Client can fetch agents from marketplace."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "agents": [
                {"id": "agent-1", "name": "Finance Analyst"},
                {"id": "agent-2", "name": "Marketing Assistant"}
            ],
            "total": 2,
            "page": 1
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        with patch('core.atom_saas_client.httpx.AsyncClient', return_value=mock_client):
            client = AtomAgentOSMarketplaceClient()
            client._http_client = mock_client

            result = await client.fetch_agents(query="finance")

            assert result["total"] == 2
            assert len(result["agents"]) == 2

    @pytest.mark.asyncio
    async def test_get_agent_template(self):
        """Client can get agent template details."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "template-1",
            "name": "Finance Analyst Template",
            "description": "Specialized finance analysis agent"
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        with patch('core.atom_saas_client.httpx.AsyncClient', return_value=mock_client):
            client = AtomAgentOSMarketplaceClient()
            client._http_client = mock_client

            result = await client.get_agent_template("template-1")

            assert result["id"] == "template-1"
            assert result["name"] == "Finance Analyst Template"

    @pytest.mark.asyncio
    async def test_install_agent(self):
        """Client can install agent template."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "agent_id": "agent-001"
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        with patch('core.atom_saas_client.httpx.AsyncClient', return_value=mock_client):
            client = AtomAgentOSMarketplaceClient()
            client._http_client = mock_client

            result = await client.install_agent("template-1", "tenant-123")

            assert result["success"] is True
            assert result["agent_id"] == "agent-001"


class TestMarketplaceWorkflows:
    """Test workflow marketplace operations."""

    @pytest.mark.asyncio
    async def test_fetch_workflows(self):
        """Client can fetch workflows from marketplace."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "workflows": [
                {"id": "workflow-1", "name": "Daily Report"},
                {"id": "workflow-2", "name": "Data Pipeline"}
            ],
            "total": 2,
            "page": 1
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        with patch('core.atom_saas_client.httpx.AsyncClient', return_value=mock_client):
            client = AtomAgentOSMarketplaceClient()
            client._http_client = mock_client

            result = await client.fetch_workflows()

            assert result["total"] == 2
            assert len(result["workflows"]) == 2

    @pytest.mark.asyncio
    async def test_get_workflow_template(self):
        """Client can get workflow template details."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "workflow-1",
            "name": "Daily Report",
            "steps": ["step1", "step2"]
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        with patch('core.atom_saas_client.httpx.AsyncClient', return_value=mock_client):
            client = AtomAgentOSMarketplaceClient()
            client._http_client = mock_client

            result = await client.get_workflow_template("workflow-1")

            assert result["id"] == "workflow-1"
            assert len(result["steps"]) == 2


class TestMarketplaceDomains:
    """Test domain marketplace operations."""

    @pytest.mark.asyncio
    async def test_fetch_domains(self):
        """Client can fetch domains from marketplace."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "domains": [
                {"id": "domain-1", "name": "Finance"},
                {"id": "domain-2", "name": "Marketing"}
            ],
            "total": 2
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        with patch('core.atom_saas_client.httpx.AsyncClient', return_value=mock_client):
            client = AtomAgentOSMarketplaceClient()
            client._http_client = mock_client

            result = await client.fetch_domains()

            assert result["total"] == 2
            assert len(result["domains"]) == 2

    @pytest.mark.asyncio
    async def test_install_domain(self):
        """Client can install domain template."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "domain_id": "domain-001"
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        with patch('core.atom_saas_client.httpx.AsyncClient', return_value=mock_client):
            client = AtomAgentOSMarketplaceClient()
            client._http_client = mock_client

            result = await client.install_domain("domain-1", "tenant-123")

            assert result["success"] is True


class TestMarketplaceComponents:
    """Test canvas component marketplace operations."""

    @pytest.mark.asyncio
    async def test_fetch_components(self):
        """Client can fetch canvas components from marketplace."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "components": [
                {"id": "comp-1", "name": "Line Chart"},
                {"id": "comp-2", "name": "Data Table"}
            ],
            "total": 2
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        with patch('core.atom_saas_client.httpx.AsyncClient', return_value=mock_client):
            client = AtomAgentOSMarketplaceClient()
            client._http_client = mock_client

            result = await client.fetch_components()

            assert result["total"] == 2
            assert len(result["components"]) == 2

    @pytest.mark.asyncio
    async def test_install_component(self):
        """Client can install canvas component."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "component_id": "comp-001"
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        with patch('core.atom_saas_client.httpx.AsyncClient', return_value=mock_client):
            client = AtomAgentOSMarketplaceClient()
            client._http_client = mock_client

            result = await client.install_component("comp-1", "canvas-123")

            assert result["success"] is True


class TestSkillRating:
    """Test skill rating operations."""

    @pytest.mark.asyncio
    async def test_rate_skill_valid_rating(self):
        """Client can submit skill rating with valid rating (1-5)."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "rating": 5
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        with patch('core.atom_saas_client.httpx.AsyncClient', return_value=mock_client):
            client = AtomAgentOSMarketplaceClient()
            client._http_client = mock_client

            result = await client.rate_skill(
                skill_id="skill-1",
                user_id="user-123",
                rating=5,
                comment="Excellent skill"
            )

            assert result["success"] is True
            assert result["rating"] == 5

    @pytest.mark.asyncio
    async def test_rate_skill_invalid_rating(self):
        """Client rejects invalid rating (outside 1-5 range)."""
        client = AtomAgentOSMarketplaceClient()

        result = await client.rate_skill(
            skill_id="skill-1",
            user_id="user-123",
            rating=10  # Invalid: > 5
        )

        assert result["success"] is False
        assert "Rating must be between 1 and 5" in result["error"]


class TestSkillInstallation:
    """Test skill installation operations."""

    @pytest.mark.asyncio
    async def test_install_skill(self):
        """Client can install skill from marketplace."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "skill_id": "skill-001"
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        with patch('core.atom_saas_client.httpx.AsyncClient', return_value=mock_client):
            client = AtomAgentOSMarketplaceClient()
            client._http_client = mock_client

            result = await client.install_skill(
                skill_id="skill-1",
                agent_id="agent-123",
                auto_install_deps=True
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_uninstall_skill(self):
        """Client can uninstall skill."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.delete.return_value = mock_response

        with patch('core.atom_saas_client.httpx.AsyncClient', return_value=mock_client):
            client = AtomAgentOSMarketplaceClient()
            client._http_client = mock_client

            result = await client.uninstall_skill(
                skill_id="skill-1",
                agent_id="agent-123"
            )

            assert result["success"] is True


class TestFederationHeaders:
    """Test federation header support.

    Contract (2026-09-13, aligned to atom-saas
    backend-saas/api/dependencies/federation_auth.py:validate_federation_peer):
    self-hosted instances authenticate with X-Instance-ID (registered,
    active MarketplaceInstance id) + X-Federation-Key (the accepted
    FederationConnection shared_secret — atom reuses its API token). The
    legacy X-API-Token header is read by NO server route and is NOT sent.
    """

    @pytest.mark.asyncio
    async def test_http_client_includes_federation_headers(self):
        """HTTP client includes federation headers."""
        mock_client = AsyncMock()

        with patch('core.atom_saas_client.httpx.AsyncClient', return_value=mock_client) as mock_httpx:
            client = AtomAgentOSMarketplaceClient(
                config=AtomSaaSConfig(
                    ws_url="wss://test.com",
                    api_url="https://test.com",
                    api_token="test-token",
                    instance_id="instance-123"
                )
            )

            # Trigger HTTP client creation
            await client._get_http_client()

            # Verify httpx.AsyncClient was called with correct headers
            call_args = mock_httpx.call_args
            headers = call_args[1]['headers']

            assert headers["X-Federation-Key"] == "test-token"
            assert headers["X-Instance-ID"] == "instance-123"
            assert headers["Content-Type"] == "application/json"
            # X-API-Token is deliberately gone — no server route reads it
            assert "X-API-Token" not in headers

    def test_sync_calls_send_federation_headers_not_api_token(
            self, monkeypatch):
        """End-to-end over a mock transport: the wire carries exactly the
        federation pair."""
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(200, json={"ok": True})

        monkeypatch.setenv("ATOM_SAAS_INSTANCE_ID", "inst-reg-9")
        monkeypatch.setenv("ATOM_SAAS_API_TOKEN", "tok-9")
        client = AtomAgentOSMarketplaceClient(
            transport=httpx.MockTransport(handler))
        assert client.health_check_sync() is True
        assert seen[0].headers["X-Instance-ID"] == "inst-reg-9"
        assert seen[0].headers["X-Federation-Key"] == "tok-9"
        assert "X-API-Token" not in seen[0].headers


class TestSynchronousWrappers:
    """Synchronous wrapper methods (2026-09-13: each runs on a PRIVATE
    event loop via _run_sync and drops the cached AsyncClient afterwards —
    the wrappers await the async method, so the patches are AsyncMocks)."""

    def test_fetch_skills_sync(self):
        """Synchronous wrapper for fetch_skills works."""
        client = AtomAgentOSMarketplaceClient()

        with patch.object(client, 'fetch_skills', new=AsyncMock(return_value={"skills": []})) as mock_fetch:
            result = client.fetch_skills_sync()
            mock_fetch.assert_called_once()
            assert result == {"skills": []}

    def test_get_skill_by_id_sync(self):
        """Synchronous wrapper for get_skill_by_id works."""
        client = AtomAgentOSMarketplaceClient()

        with patch.object(client, 'get_skill_by_id', new=AsyncMock(return_value={"id": "skill-1"})) as mock_get:
            result = client.get_skill_by_id_sync("skill-1")
            mock_get.assert_called_once_with("skill-1")
            assert result["id"] == "skill-1"

    def test_rate_skill_sync(self):
        """Synchronous wrapper for rate_skill works."""
        client = AtomAgentOSMarketplaceClient()

        with patch.object(client, 'rate_skill', new=AsyncMock(return_value={"success": True})) as mock_rate:
            result = client.rate_skill_sync("skill-1", "user-123", 5)
            mock_rate.assert_called_once()
            assert result["success"] is True

    def test_install_skill_sync(self):
        """Synchronous wrapper for install_skill works."""
        client = AtomAgentOSMarketplaceClient()

        with patch.object(client, 'install_skill', new=AsyncMock(return_value={"success": True})) as mock_install:
            result = client.install_skill_sync("skill-1", "agent-123")
            mock_install.assert_called_once()
            assert result["success"] is True

    def test_uninstall_skill_sync(self):
        """Synchronous wrapper for uninstall_skill works."""
        client = AtomAgentOSMarketplaceClient()

        with patch.object(client, 'uninstall_skill', new=AsyncMock(return_value={"success": True})) as mock_uninstall:
            result = client.uninstall_skill_sync("skill-1", "agent-123")
            mock_uninstall.assert_called_once()
            assert result["success"] is True


class TestSyncWrapperLoopSafety:
    """The cross-loop bug (2026-09-13): install_agent makes TWO sequential
    sync calls (get_template_details then install_agent_sync). The cached
    AsyncClient used to survive the first asyncio.run's closed loop, so the
    second call raised RuntimeError — NOT an httpx.HTTPError, so install's
    except-path rolled back local rows it had already created."""

    def _client(self, handler, **env):
        for key, value in env.items():
            os.environ[key] = value
        return AtomAgentOSMarketplaceClient(
            transport=httpx.MockTransport(handler))

    def test_two_sequential_sync_calls(self):
        calls = []

        def handler(request):
            calls.append(str(request.url.path))
            if request.url.path.endswith("/install/tmpl-1"):
                return httpx.Response(200, json={"status": "installed"})
            return httpx.Response(200, json={"id": "tmpl-1",
                                             "verified_record": {}})

        client = self._client(
            handler, ATOM_SAAS_API_TOKEN="tok",
            ATOM_SAAS_INSTANCE_ID="inst-1")
        try:
            first = client.get_agent_template_sync("tmpl-1")
            second = client.install_agent_sync("tmpl-1", "tenant-1")
            assert first["id"] == "tmpl-1"
            assert second["status"] == "installed"
            assert len(calls) == 2
        finally:
            os.environ.pop("ATOM_SAAS_INSTANCE_ID", None)

    def test_client_is_dropped_after_each_sync_call(self):
        def handler(request):
            return httpx.Response(200, json={"ok": True})

        client = self._client(handler, ATOM_SAAS_API_TOKEN="tok",
                              ATOM_SAAS_INSTANCE_ID="inst-1")
        try:
            assert client._http_client is None
            client.health_check_sync()
            assert client._http_client is None  # dropped, not cached
        finally:
            os.environ.pop("ATOM_SAAS_INSTANCE_ID", None)

    def test_sync_wrapper_refuses_a_running_loop(self):
        import asyncio

        def handler(request):
            return httpx.Response(200, json={"ok": True})

        client = self._client(handler, ATOM_SAAS_API_TOKEN="tok",
                              ATOM_SAAS_INSTANCE_ID="inst-1")

        async def _in_loop():
            with pytest.raises(RuntimeError):
                client.health_check_sync()

        try:
            asyncio.run(_in_loop())
        finally:
            os.environ.pop("ATOM_SAAS_INSTANCE_ID", None)


class TestCommittedSaasRouteContract:
    """Route/param alignment to the COMMITTED atom-saas router."""

    def test_details_route_has_no_details_segment(self):
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(200, json={"id": "tmpl-1"})

        client = AtomAgentOSMarketplaceClient(
            transport=httpx.MockTransport(handler))
        out = client.get_agent_template_sync("tmpl-1")
        assert out["id"] == "tmpl-1"
        assert str(seen[0].url).endswith(
            "/agents/api/agent-marketplace/tmpl-1")
        assert "/details/" not in str(seen[0].url)

    def test_browse_maps_page_page_size_to_limit_offset(self):
        seen = []

        def handler(request):
            seen.append(request)
            return httpx.Response(200, json={"agents": [], "total": 0})

        client = AtomAgentOSMarketplaceClient(
            transport=httpx.MockTransport(handler))
        client.fetch_agents_sync(query="quota", category="Sales",
                                 page=3, page_size=25)
        params = dict(httpx.QueryParams(seen[0].url.params))
        assert params == {"limit": "25", "offset": "50",
                          "category": "Sales"}
        # page/page_size/query are NOT sent — the server does not read them


class TestHealthCheck:
    """Test health check operations."""

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Health check returns True on successful connection."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_response

        with patch('core.atom_saas_client.httpx.AsyncClient', return_value=mock_client):
            client = AtomAgentOSMarketplaceClient()
            client._http_client = mock_client

            result = await client.health_check()

            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Health check returns False on connection failure."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.HTTPError("Connection failed")

        with patch('core.atom_saas_client.httpx.AsyncClient', return_value=mock_client):
            client = AtomAgentOSMarketplaceClient()
            client._http_client = mock_client

            result = await client.health_check()

            assert result is False


class TestWebSocketConnection:
    """Test Atom SaaS WebSocket connection (previously a NotImplementedError stub)."""

    @pytest.mark.asyncio
    async def test_connect_dispatches_messages_and_sets_state(self):
        """connect_websocket opens a connection, dispatches messages, sets state."""
        handler = AsyncMock()

        # Fake WebSocket connection that yields two messages then closes.
        class FakeWS:
            def __init__(self, messages):
                self._messages = messages
                self.closed = False

            def __aiter__(self):
                async def gen():
                    for m in self._messages:
                        yield m
                return gen()

            async def close(self):
                self.closed = True

        fake_ws = FakeWS(['{"type": "ping"}', '{"type": "skill_update"}'])

        # connect_websocket imports websockets INSIDE the method
        # (core/atom_saas_client.py:425), so the module attribute
        # core.atom_saas_client.websockets does not exist — patch the real
        # websockets.connect with an AsyncMock (it is awaited).
        with patch('websockets.connect', new_callable=AsyncMock, return_value=fake_ws):
            client = AtomAgentOSMarketplaceClient(
                config=AtomSaaSConfig(
                    ws_url="wss://test.com/api",
                    api_url="https://test.com/api",
                    api_token="test-token",
                    instance_id="instance-123"
                )
            )

            # connect_websocket runs the receive loop until the connection closes.
            await client.connect_websocket(handler)

        assert client._connected is False  # reset after loop ends
        assert handler.await_count == 2
        handler.assert_any_await({"type": "ping"})
        handler.assert_any_await({"type": "skill_update"})

    @pytest.mark.asyncio
    async def test_connect_raises_without_token(self):
        """connect_websocket raises RuntimeError when no API token is set."""
        client = AtomAgentOSMarketplaceClient(
            config=AtomSaaSConfig(
                ws_url="wss://test.com/api",
                api_url="https://test.com/api",
                api_token=""  # missing
            )
        )

        with pytest.raises(RuntimeError, match="ATOM_SAAS_API_TOKEN"):
            await client.connect_websocket(AsyncMock())


class TestInstanceRegistration:
    """Test instance registration and analytics."""

    @pytest.mark.asyncio
    async def test_register_instance(self):
        """Client can register instance with marketplace."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "instance_id": "instance-001",
            "analytics_enabled": True
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        with patch('core.atom_saas_client.httpx.AsyncClient', return_value=mock_client):
            client = AtomAgentOSMarketplaceClient()
            client._http_client = mock_client

            result = await client.register_instance(
                instance_name="test-instance",
                version="1.0.0",
                platform="docker"
            )

            assert result["success"] is True
            assert result["instance_id"] == "instance-001"

    @pytest.mark.asyncio
    async def test_push_analytics(self):
        """Client can push analytics data to marketplace."""
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "count": 10
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response

        with patch('core.atom_saas_client.httpx.AsyncClient', return_value=mock_client):
            client = AtomAgentOSMarketplaceClient()
            client._http_client = mock_client

            reports = [
                {"metric": "executions", "value": 100},
                {"metric": "errors", "value": 5}
            ]

            result = await client.push_analytics("instance-001", reports)

            assert result["success"] is True
            assert result["count"] == 10


class TestErrorHandling:
    """Test error handling in client operations."""

    @pytest.mark.asyncio
    async def test_fetch_skills_http_error(self):
        """Client handles HTTP errors gracefully."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.HTTPError("Network error")

        with patch('core.atom_saas_client.httpx.AsyncClient', return_value=mock_client):
            client = AtomAgentOSMarketplaceClient()
            client._http_client = mock_client

            result = await client.fetch_skills()

            # Should return empty result on error
            assert result["skills"] == []
            assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_get_skill_by_id_not_found(self):
        """Client returns None when skill not found."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.HTTPError("Not found")

        with patch('core.atom_saas_client.httpx.AsyncClient', return_value=mock_client):
            client = AtomAgentOSMarketplaceClient()
            client._http_client = mock_client

            result = await client.get_skill_by_id("nonexistent")

            assert result is None

    @pytest.mark.asyncio
    async def test_install_skill_error(self):
        """Client handles installation errors gracefully."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.HTTPError("Installation failed")

        with patch('core.atom_saas_client.httpx.AsyncClient', return_value=mock_client):
            client = AtomAgentOSMarketplaceClient()
            client._http_client = mock_client

            result = await client.install_skill("skill-1", "agent-123")

            assert result["success"] is False
            assert "error" in result


class TestBackwardCompatibility:
    """Test backward compatibility alias."""

    def test_atom_saas_client_alias(self):
        """AtomSaaSClient alias points to AtomAgentOSMarketplaceClient."""
        assert AtomSaaSClient is AtomAgentOSMarketplaceClient

    def test_client_can_be_created_with_alias(self):
        """Client can be created using AtomSaaSClient alias."""
        with patch('core.atom_saas_client.httpx.AsyncClient'):
            client = AtomSaaSClient()
            assert isinstance(client, AtomAgentOSMarketplaceClient)
