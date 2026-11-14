"""
Menu Bar Companion API Tests

Tests for menu bar companion app endpoints:
- Authentication
- Connection status
- Recent items (agents, canvases)
- Quick chat
"""

import pytest
import pyotp
import time
import uuid
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import MagicMock, patch

from core.auth import get_password_hash
from core.database import get_db
from core.llm_service import LLMService
from core.models import (
    User,
    AgentRegistry,
    AgentExecution,
    Canvas,
    CanvasAudit,
    DeviceNode,
    MenuBarAudit,
    Tenant,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client(fastapi_app, db_session: Session):
    """Create a TestClient bound to the test database session.

    The API is exercised through the real application (including its
    authentication dependencies) so the login/401/device assertions below
    keep their meaning. Only the database dependency is redirected to the
    per-test session; authentication is never bypassed.
    """
    original_override = fastapi_app.dependency_overrides.get(get_db)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(fastapi_app) as test_client:
            yield test_client
    finally:
        if original_override is None:
            fastapi_app.dependency_overrides.pop(get_db, None)
        else:
            fastapi_app.dependency_overrides[get_db] = original_override


@pytest.fixture
def menubar_user(db_session: Session):
    """Create a test user (with tenant) for menu bar tests."""
    tenant = Tenant(
        name="Menu Bar Test Tenant",
        subdomain=f"menubar-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(tenant)
    db_session.flush()

    user = User(
        email="menubar@test.com",
        first_name="Menu",
        last_name="Bar User",
        hashed_password="$2b$12$test_hashed_password",
        role="member",
        status="active",
        tenant_id=str(tenant.id),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def menubar_agents(db_session: Session, menubar_user):
    """Create test agents for menu bar."""
    agents = []

    # Create agents with different maturity levels
    for i, maturity in enumerate(["AUTONOMOUS", "SUPERVISED", "INTERN", "STUDENT"]):
        agent = AgentRegistry(
            name=f"Test Agent {maturity}",
            status=maturity,
            description=f"Test agent for {maturity} level",
            category="Testing",
            module_path="test.agents",
            class_name=f"TestAgent{maturity}",
            version="1.0.0",
            configuration={"capabilities": ["chat", "canvas"]},
            user_id=str(menubar_user.id),
            created_at=datetime.utcnow() - timedelta(days=i),
        )
        db_session.add(agent)
        agents.append(agent)

    db_session.commit()
    for agent in agents:
        db_session.refresh(agent)
    return agents


@pytest.fixture
def menubar_executions(db_session: Session, menubar_agents, menubar_user):
    """Create test agent executions."""
    executions = []

    for i, agent in enumerate(menubar_agents[:3]):
        # Create multiple executions for each agent
        for j in range(3):
            execution = AgentExecution(
                agent_id=str(agent.id),
                workspace_id="default",
                triggered_by="manual",
                status="completed",
                started_at=datetime.utcnow() - timedelta(days=i, hours=j),
                completed_at=datetime.utcnow() - timedelta(days=i, hours=j) + timedelta(minutes=5),
                duration_seconds=300,
            )
            db_session.add(execution)
            executions.append(execution)

    db_session.commit()
    return executions


@pytest.fixture
def menubar_canvases(db_session: Session, menubar_agents, menubar_user):
    """Create test canvas audits (backed by real Canvas rows)."""
    canvases = []

    for i, agent in enumerate(menubar_agents[:2]):
        canvas_types = ["sheets", "charts", "forms", "docs"]
        canvas_type = canvas_types[i % len(canvas_types)]

        canvas = Canvas(
            tenant_id=str(menubar_user.tenant_id),
            created_by=str(menubar_user.id),
            name=f"Test Canvas {i}",
            canvas_type=canvas_type,
        )
        db_session.add(canvas)
        db_session.flush()

        audit = CanvasAudit(
            canvas_id=str(canvas.id),
            tenant_id=str(menubar_user.tenant_id),
            user_id=str(menubar_user.id),
            session_id=f"session_{i}",
            created_at=datetime.utcnow() - timedelta(hours=i),
            action_type='present',
            canvas_type=canvas_type,
            details_json={
                'canvas_type': canvas_type,
                'component_type': 'chart',
                'audit_metadata': {"title": f"Test Canvas {i}"},
            },
            agent_id=str(agent.id),
        )
        db_session.add(audit)
        canvases.append(audit)

    db_session.commit()
    for canvas_audit in canvases:
        db_session.refresh(canvas_audit)
    return canvases


class _ControlledProviderTransport:
    """Deterministic stand-in for the provider transport.

    Only the two provider-facing ``LLMService`` methods are replaced. The
    route, scoped agent lookup, governance decisions, ``execute_agent_chat``
    dispatch, and the execution/audit records all stay real, so a regression
    in any of them still fails these tests.
    """

    def __init__(self):
        self.chunks = ["Controlled ", "provider ", "reply."]
        self.error = None
        self.calls = []

    @property
    def reply_text(self) -> str:
        return "".join(self.chunks)


@pytest.fixture
def controlled_llm_transport(db_session: Session):
    """Replace only the LLM provider boundary for quick-chat tests.

    ``LLMService.get_optimal_provider`` would otherwise contact the provider
    catalogue and raise ``NoProvidersConfiguredError`` in a keyless checkout,
    and ``LLMService.stream_completion`` would perform a live network call in
    an environment that happens to have keys. Neither is acceptable in a test.

    The service opens its own ``SessionLocal`` sessions; binding that factory
    to the per-test session makes the real agent-resolution/dispatch code see
    the fixture agents instead of falling back to the system default. Chat
    persistence is stubbed out because it writes to the shared dev LanceDB /
    chat-session files, which must not be touched by a unit test.
    """
    transport = _ControlledProviderTransport()

    async def controlled_stream(self, messages, **kwargs):
        transport.calls.append(
            {
                "messages": [dict(message) for message in messages],
                "kwargs": dict(kwargs),
            }
        )
        if transport.error is not None:
            raise transport.error
        for chunk in transport.chunks:
            yield chunk

    session_manager = MagicMock()
    session_manager.create_session.return_value = "controlled-test-session"

    with (
        patch.object(
            LLMService,
            "get_optimal_provider",
            return_value=("controlled-provider", "controlled-model"),
        ),
        patch.object(LLMService, "stream_completion", controlled_stream),
        patch(
            "core.agent_execution_service.SessionLocal",
            return_value=db_session,
        ),
        patch(
            "core.agent_execution_service.get_chat_history_manager",
            return_value=MagicMock(),
        ),
        patch(
            "core.agent_execution_service.get_chat_session_manager",
            return_value=session_manager,
        ),
        patch("core.agent_execution_service.trigger_episode_creation"),
    ):
        yield transport


# ============================================================================
# Authentication Tests
# ============================================================================

class TestMenuBarAuthentication:
    """Tests for menu bar authentication endpoints."""

    @patch("api.menubar_routes.verify_password")
    def test_menubar_login_success(self, mock_verify, client: TestClient, menubar_user):
        """Test successful menu bar login."""
        # Mock password verification to return True
        mock_verify.return_value = True

        response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
                "platform": "darwin",
            }
        )

        # Debug: print response if not 200
        if response.status_code != 200:
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "access_token" in data
        assert "device_id" in data
        assert data["user"]["email"] == "menubar@test.com"

    @patch("api.menubar_routes.verify_password")
    def test_menubar_login_invalid_credentials(self, mock_verify, client: TestClient):
        """Test login with invalid credentials."""
        # Mock password verification to return False
        mock_verify.return_value = False

        response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "invalid@test.com",
                "password": "wrong_password",
                "device_name": "MenuBar",
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "error" in data

    @patch("api.menubar_routes.verify_password")
    def test_menubar_login_creates_device(self, mock_verify, client: TestClient, menubar_user, db_session: Session):
        """Test that login creates a DeviceNode entry."""
        mock_verify.return_value = True

        response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
                "platform": "darwin",
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Verify device was created
        device = db_session.query(DeviceNode).filter(
            DeviceNode.device_id == data["device_id"]
        ).first()

        assert device is not None
        assert device.app_type == "menubar"
        assert device.status == "online"
        assert "quick_chat" in device.capabilities

    @patch("api.menubar_routes.verify_password")
    def test_menubar_login_updates_existing_device(self, mock_verify, client: TestClient, menubar_user, db_session: Session):
        """Test that login updates existing device."""
        mock_verify.return_value = True

        # First login
        response1 = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
                "platform": "darwin",
                "app_version": "0.1.0",
            }
        )

        assert response1.status_code == 200
        device_id = response1.json()["device_id"]

        # Second login with updated info
        response2 = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar Updated",
                "platform": "darwin",
                "app_version": "0.2.0",
            }
        )

        assert response2.status_code == 200

        # Verify device was updated
        device = db_session.query(DeviceNode).filter(
            DeviceNode.device_id == device_id
        ).first()

        assert device is not None
        assert device.name == "MenuBar Updated"
        assert device.app_version == "0.2.0"


@pytest.fixture
def scratch_login_user(db_session: Session):
    """A scratch account with a real bcrypt hash (no auth mocks)."""
    tenant = Tenant(
        name="Scratch Login Tenant",
        subdomain=f"scratch-login-{uuid.uuid4().hex[:8]}",
    )
    db_session.add(tenant)
    db_session.flush()

    user = User(
        email="scratch-login@test.com",
        first_name="Scratch",
        last_name="Login",
        hashed_password=get_password_hash("Scratch-Passw0rd!"),
        role="member",
        status="active",
        is_active=True,
        tenant_id=str(tenant.id),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _normal_middleware(monkeypatch):
    """Run one request with the real CSRF middleware (no pytest bypass).

    ``core.security.middleware.CSRFProtectionMiddleware`` skips validation
    whenever pytest's environment markers are present. Deleting them for the
    request makes these assertions exercise the production path, including
    the narrow credential-exchange exception.
    """
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("PYTEST_VERSION", raising=False)


class TestMenuBarLoginUnderNormalMiddleware:
    """Sign-in behavior with the real CSRF middleware enabled."""

    def test_correct_credentials_sign_in(
        self, monkeypatch, client: TestClient, scratch_login_user, db_session: Session
    ):
        _normal_middleware(monkeypatch)

        response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "scratch-login@test.com",
                "password": "Scratch-Passw0rd!",
                "device_name": "Scratch MenuBar",
                "platform": "darwin",
            },
        )

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["success"] is True
        assert data["access_token"]
        assert data["device_id"] == f"menubar_{scratch_login_user.id}_darwin"
        assert data["user"]["email"] == "scratch-login@test.com"

        device = db_session.query(DeviceNode).filter(
            DeviceNode.device_id == data["device_id"],
            DeviceNode.user_id == str(scratch_login_user.id),
        ).first()
        assert device is not None
        assert device.app_type == "menubar"
        assert device.status == "online"

    def test_incorrect_password_is_rejected(
        self, monkeypatch, client: TestClient, scratch_login_user, db_session: Session
    ):
        _normal_middleware(monkeypatch)

        response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "scratch-login@test.com",
                "password": "Not-The-Password!",
                "device_name": "Scratch MenuBar",
                "platform": "darwin",
            },
        )

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["success"] is False
        assert data["access_token"] is None
        assert data["error"] == "Invalid email or password"
        assert (
            db_session.query(DeviceNode)
            .filter(DeviceNode.user_id == str(scratch_login_user.id))
            .count()
            == 0
        )

    def test_csrf_still_blocks_other_menubar_mutations(self, monkeypatch, client: TestClient):
        """The sign-in exception is exact-path only, never the whole prefix."""
        _normal_middleware(monkeypatch)

        response = client.post(
            "/api/menubar/quick/chat",
            headers={"Host": "localhost", "Content-Type": "application/json"},
            json={"message": "no bearer, no CSRF token"},
        )

        assert response.status_code == 403, response.text
        assert response.json()["error"]["type"] == "csrf_token_invalid"

    def test_two_factor_is_required_then_replay_is_refused(
        self, monkeypatch, client: TestClient, db_session: Session
    ):
        _normal_middleware(monkeypatch)

        tenant = Tenant(
            name="Scratch 2FA Tenant",
            subdomain=f"scratch-2fa-{uuid.uuid4().hex[:8]}",
        )
        db_session.add(tenant)
        db_session.flush()
        secret = pyotp.random_base32()
        user = User(
            email="scratch-2fa@test.com",
            first_name="Scratch",
            last_name="TwoFactor",
            hashed_password=get_password_hash("Scratch-Passw0rd!"),
            role="member",
            status="active",
            is_active=True,
            tenant_id=str(tenant.id),
            two_factor_enabled=True,
            two_factor_secret=secret,
            two_factor_revision=1,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        payload = {
            "email": "scratch-2fa@test.com",
            "password": "Scratch-Passw0rd!",
            "device_name": "Scratch MenuBar",
            "platform": "darwin",
        }

        missing = client.post(
            "/api/menubar/auth/login", headers={"Host": "localhost"}, json=payload
        )
        assert missing.status_code == 200, missing.text
        assert missing.json()["success"] is False
        assert missing.json()["two_factor_required"] is True
        assert missing.json()["error"] == "Two-factor authentication required"

        wrong = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={**payload, "totp_code": "000000"},
        )
        assert wrong.status_code == 200, wrong.text
        assert wrong.json()["success"] is False
        assert wrong.json()["error"] == "Invalid two-factor code"

        # Freeze time so both attempts land in the same TOTP step. Without
        # this the second request could cross a 30s boundary and be rejected
        # as simply stale, leaving the replay fence itself untested.
        frozen_now = time.time()
        monkeypatch.setattr(time, "time", lambda: frozen_now)

        code = pyotp.TOTP(secret).now()
        first = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={**payload, "totp_code": code},
        )
        assert first.status_code == 200, first.text
        assert first.json()["success"] is True
        assert first.json()["access_token"]

        replay = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={**payload, "totp_code": code},
        )
        assert replay.status_code == 200, replay.text
        assert replay.json()["success"] is False
        assert replay.json()["access_token"] is None
        assert "already been used" in replay.json()["error"]
        assert replay.json()["two_factor_required"] is True


# ============================================================================
# Connection Status Tests
# ============================================================================

class TestMenuBarConnectionStatus:
    """Tests for connection status endpoint."""

    @patch("api.menubar_routes.verify_password")
    def test_get_connection_status_authenticated(self, mock_verify, client: TestClient, menubar_user):
        """Test getting connection status when authenticated."""
        mock_verify.return_value = True

        # Login first
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]
        device_id = login_response.json()["device_id"]

        # Get connection status
        response = client.get(
            "/api/menubar/status",
            headers={"Authorization": f"Bearer {token}", "X-Device-ID": device_id, "Host": "localhost"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "connected"
        assert data["device_id"] == device_id
        assert "server_time" in data

    def test_get_connection_status_unauthenticated(self, client: TestClient):
        """Test getting connection status without authentication."""
        response = client.get("/api/menubar/status", headers={"Host": "localhost"})

        # Should return 401 or similar
        assert response.status_code == 401

    @patch("api.menubar_routes.verify_password")
    def test_connection_status_updates_last_seen(self, mock_verify, client: TestClient, menubar_user, db_session: Session):
        """Test that status check updates last_seen timestamp."""
        mock_verify.return_value = True

        # Login
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]
        device_id = login_response.json()["device_id"]

        # Get initial last_seen
        device = db_session.query(DeviceNode).filter(
            DeviceNode.device_id == device_id
        ).first()
        initial_last_seen = device.last_seen

        # Wait a bit and check status
        import time
        time.sleep(0.1)

        response = client.get(
            "/api/menubar/status",
            headers={"Authorization": f"Bearer {token}", "X-Device-ID": device_id, "Host": "localhost"}
        )

        assert response.status_code == 200

        # Verify last_seen was updated
        db_session.refresh(device)
        assert device.last_seen > initial_last_seen


# ============================================================================
# Recent Items Tests
# ============================================================================

class TestMenuBarRecentItems:
    """Tests for recent items endpoints."""

    @patch("api.menubar_routes.verify_password")
    def test_get_recent_agents(self, mock_verify, client: TestClient, menubar_user, menubar_executions):
        """Test getting recent agents."""
        mock_verify.return_value = True

        # Login
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]

        # Get recent agents
        response = client.get(
            "/api/menubar/recent/agents",
            headers={"Authorization": f"Bearer {token}", "Host": "localhost"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        # Verify structure
        agent = data[0]
        assert "id" in agent
        assert "name" in agent
        assert "maturity_level" in agent
        assert "execution_count" in agent

    @patch("api.menubar_routes.verify_password")
    def test_get_recent_canvases(self, mock_verify, client: TestClient, menubar_user, menubar_canvases):
        """Test getting recent canvases."""
        mock_verify.return_value = True

        # Login
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]

        # Get recent canvases
        response = client.get(
            "/api/menubar/recent/canvases",
            headers={"Authorization": f"Bearer {token}", "Host": "localhost"}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        # Verify structure
        canvas = data[0]
        assert "id" in canvas
        assert "canvas_type" in canvas
        assert "created_at" in canvas

    @patch("api.menubar_routes.verify_password")
    def test_get_recent_items_combined(self, mock_verify, client: TestClient, menubar_user, menubar_executions, menubar_canvases):
        """Test getting both agents and canvases in one request."""
        mock_verify.return_value = True

        # Login
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]

        # Get all recent items
        response = client.get(
            "/api/menubar/recent",
            headers={"Authorization": f"Bearer {token}", "Host": "localhost"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert "canvases" in data
        assert len(data["agents"]) > 0
        assert len(data["canvases"]) > 0

    @patch("api.menubar_routes.verify_password")
    def test_recent_agents_limit(self, mock_verify, client: TestClient, menubar_user):
        """Test limiting the number of recent agents."""
        mock_verify.return_value = True

        # Login
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]

        # Request only 2 agents
        response = client.get(
            "/api/menubar/recent/agents?limit=2",
            headers={"Authorization": f"Bearer {token}", "Host": "localhost"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 2


# ============================================================================
# Quick Chat Tests
# ============================================================================

class TestMenuBarQuickChat:
    """Tests for quick chat endpoint."""

    @patch("api.menubar_routes.verify_password")
    def test_quick_chat_with_agent(
        self,
        mock_verify,
        client: TestClient,
        menubar_user,
        menubar_agents,
        db_session: Session,
        controlled_llm_transport,
    ):
        """Test sending a quick chat message with specific agent.

        The provider transport is controlled, but the request still goes
        through real route authorization, scoped agent lookup, governance, and
        ``execute_agent_chat``. Asserting the exact reply (not just
        ``success``) separates real output from a plausible-looking failure.
        """
        mock_verify.return_value = True

        # Login
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]
        device_id = login_response.json()["device_id"]
        agent_id = str(menubar_agents[0].id)

        # Send quick chat
        response = client.post(
            "/api/menubar/quick/chat",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Device-ID": device_id,
                "Host": "localhost",
            },
            json={
                "message": "Hello, agent!",
                "agent_id": agent_id,
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True, data
        assert data["error"] is None
        assert data["response"] == controlled_llm_transport.reply_text
        assert data["agent_id"] == agent_id
        assert data["execution_id"]
        assert data["session_id"] == "controlled-test-session"

        # The controlled transport received the real dispatched conversation:
        # the resolved agent's system prompt plus the caller's message.
        assert len(controlled_llm_transport.calls) == 1
        dispatched = controlled_llm_transport.calls[0]["messages"]
        assert [msg["role"] for msg in dispatched] == ["system", "user"]
        assert menubar_agents[0].name in dispatched[0]["content"]
        assert dispatched[-1]["content"] == "Hello, agent!"

        # Real execution accounting was written for the dispatched agent.
        execution = db_session.query(AgentExecution).filter(
            AgentExecution.id == data["execution_id"]
        ).first()
        assert execution is not None
        assert execution.status == "completed"
        assert execution.result_summary == controlled_llm_transport.reply_text

        audit = db_session.query(MenuBarAudit).filter(
            MenuBarAudit.action == "quick_chat",
            MenuBarAudit.agent_execution_id == data["execution_id"],
        ).first()
        assert audit is not None
        assert audit.success is True
        assert audit.agent_id == agent_id

    @patch("api.menubar_routes.verify_password")
    def test_quick_chat_auto_select_agent(
        self,
        mock_verify,
        client: TestClient,
        menubar_user,
        menubar_agents,
        controlled_llm_transport,
    ):
        """Test quick chat without specifying an agent (auto-select)."""
        mock_verify.return_value = True

        # Login
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]
        device_id = login_response.json()["device_id"]

        # Send quick chat without agent_id
        response = client.post(
            "/api/menubar/quick/chat",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Device-ID": device_id,
                "Host": "localhost",
            },
            json={
                "message": "Hello!",
            }
        )

        assert response.status_code == 200
        data = response.json()
        # Auto-select prefers the most mature agent (AUTONOMOUS is first).
        assert data["success"] is True, data
        assert data["error"] is None
        assert data["agent_id"] == str(menubar_agents[0].id)
        assert data["response"] == controlled_llm_transport.reply_text

    @patch("api.menubar_routes.verify_password")
    def test_quick_chat_updates_last_command_at(
        self,
        mock_verify,
        client: TestClient,
        menubar_user,
        menubar_agents,
        db_session: Session,
        controlled_llm_transport,
    ):
        """Test that quick chat updates last_command_at timestamp."""
        mock_verify.return_value = True

        # Login
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]
        device_id = login_response.json()["device_id"]
        agent_id = str(menubar_agents[0].id)

        # Send quick chat
        response = client.post(
            "/api/menubar/quick/chat",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Device-ID": device_id,
                "Host": "localhost",
            },
            json={
                "message": "Test message",
                "agent_id": agent_id,
            }
        )

        # The timestamp assertion only means something if dispatch succeeded.
        assert response.json()["success"] is True, response.json()

        # Verify last_command_at was updated
        device = db_session.query(DeviceNode).filter(
            DeviceNode.device_id == device_id
        ).first()

        assert device is not None
        assert device.last_command_at is not None

    @patch("api.menubar_routes.verify_password")
    def test_quick_chat_provider_failure_is_not_success(
        self,
        mock_verify,
        client: TestClient,
        menubar_user,
        menubar_agents,
        db_session: Session,
        controlled_llm_transport,
    ):
        """A provider failure must be observably different from real output."""
        mock_verify.return_value = True
        controlled_llm_transport.error = RuntimeError("provider transport down")

        # Login
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]
        device_id = login_response.json()["device_id"]
        agent_id = str(menubar_agents[0].id)

        response = client.post(
            "/api/menubar/quick/chat",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Device-ID": device_id,
                "Host": "localhost",
            },
            json={
                "message": "Hello, agent!",
                "agent_id": agent_id,
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["error"] == "Agent chat execution failed"
        assert data["response"] is None
        assert data["response"] != controlled_llm_transport.reply_text

        # The provider WAS dispatched; the failure happened at the transport.
        assert len(controlled_llm_transport.calls) == 1

        # Failure is audited distinctly from a successful reply.
        audit = db_session.query(MenuBarAudit).filter(
            MenuBarAudit.action == "quick_chat",
            MenuBarAudit.success.is_(False),
        ).order_by(MenuBarAudit.timestamp.desc()).first()
        assert audit is not None
        assert audit.error_message == "Agent chat execution failed"

    @patch("api.menubar_routes.verify_password")
    def test_quick_chat_provider_failure_token_is_not_success(
        self,
        mock_verify,
        client: TestClient,
        menubar_user,
        menubar_agents,
        controlled_llm_transport,
    ):
        """A provider-exhaustion sentinel must not masquerade as a reply."""
        mock_verify.return_value = True
        controlled_llm_transport.chunks = [
            "\n\n[Error: All LLM providers failed. Please check your API key "
            "configuration and try again.]"
        ]

        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]
        device_id = login_response.json()["device_id"]

        response = client.post(
            "/api/menubar/quick/chat",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Device-ID": device_id,
                "Host": "localhost",
            },
            json={
                "message": "Hello, agent!",
                "agent_id": str(menubar_agents[0].id),
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False, data
        assert data["error"]
        assert "[Error:" not in (data.get("response") or "")


# ============================================================================
# Health Check Tests
# ============================================================================

class TestMenuBarHealth:
    """Tests for health check endpoint."""

    def test_health_check(self, client: TestClient):
        """Test health check endpoint."""
        response = client.get("/api/menubar/health", headers={"Host": "localhost"})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data


# ============================================================================
# Performance Tests
# ============================================================================

class TestMenuBarPerformance:
    """Performance tests for menu bar endpoints."""

    @patch("api.menubar_routes.verify_password")
    def test_login_performance(self, mock_verify, client: TestClient, menubar_user):
        """Test login performance."""
        mock_verify.return_value = True

        import time

        start = time.time()
        response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )
        end = time.time()

        assert response.status_code == 200
        # Should complete in less than 1 second
        assert (end - start) < 1.0

    @patch("api.menubar_routes.verify_password")
    def test_recent_items_performance(self, mock_verify, client: TestClient, menubar_user, menubar_executions, menubar_canvases):
        """Test recent items retrieval performance."""
        mock_verify.return_value = True

        import time

        # Login
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]

        start = time.time()
        response = client.get(
            "/api/menubar/recent",
            headers={"Authorization": f"Bearer {token}", "Host": "localhost"}
        )
        end = time.time()

        assert response.status_code == 200
        # Should complete in less than 500ms
        assert (end - start) < 0.5

    @patch("api.menubar_routes.verify_password")
    def test_quick_chat_performance(
        self,
        mock_verify,
        client: TestClient,
        menubar_user,
        menubar_agents,
        controlled_llm_transport,
    ):
        """Test quick chat performance."""
        mock_verify.return_value = True

        import time

        # Login
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]
        device_id = login_response.json()["device_id"]
        agent_id = str(menubar_agents[0].id)

        start = time.time()
        response = client.post(
            "/api/menubar/quick/chat",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Device-ID": device_id,
                "Host": "localhost",
            },
            json={
                "message": "Test message",
                "agent_id": agent_id,
            }
        )
        end = time.time()

        assert response.status_code == 200
        assert response.json()["success"] is True, response.json()
        # Should complete in less than 2 seconds
        assert (end - start) < 2.0


# ============================================================================
# Edge Case Tests
# ============================================================================

class TestMenuBarEdgeCases:
    """Tests for edge cases and error handling."""

    @patch("api.menubar_routes.verify_password")
    def test_empty_recent_items(self, mock_verify, client: TestClient, menubar_user):
        """Test handling when no recent items exist."""
        mock_verify.return_value = True

        # Login (without creating any executions or canvases)
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]

        # Get recent items
        response = client.get(
            "/api/menubar/recent",
            headers={"Authorization": f"Bearer {token}", "Host": "localhost"}
        )

        assert response.status_code == 200
        data = response.json()
        # Should return empty lists, not error
        assert "agents" in data
        assert "canvases" in data

    def test_invalid_token(self, client: TestClient):
        """Test using invalid token."""
        response = client.get(
            "/api/menubar/recent",
            headers={"Authorization": "Bearer invalid_token", "Host": "localhost"}
        )

        assert response.status_code == 401

    @patch("api.menubar_routes.verify_password")
    def test_missing_device_id_header(
        self,
        mock_verify,
        client: TestClient,
        menubar_user,
        menubar_agents,
        controlled_llm_transport,
    ):
        """Test quick chat without X-Device-ID header."""
        mock_verify.return_value = True

        # Login
        login_response = client.post(
            "/api/menubar/auth/login",
            headers={"Host": "localhost"},
            json={
                "email": "menubar@test.com",
                "password": "test_password",
                "device_name": "MenuBar",
            }
        )

        token = login_response.json()["access_token"]

        # Send quick chat without device ID
        response = client.post(
            "/api/menubar/quick/chat",
            headers={"Authorization": f"Bearer {token}", "Host": "localhost"},
            json={
                "message": "Test",
            }
        )

        # Should still work (device_id is optional)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True, data
        assert data["response"] == controlled_llm_transport.reply_text
