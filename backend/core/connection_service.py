
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional
import uuid
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from core.config import get_config
from core.database import get_db_session
from core.models import UserConnection

logger = logging.getLogger(__name__)

class ConnectionService:
    """
    Manages user connections for both native and remote (ActivePieces) integrations.
    """
    def __init__(self):
        self.security_config = get_config().security
        self._fernet = None
        
    def _get_fernet(self) -> Fernet:
        if self._fernet is None:
            key = self.security_config.encryption_key or self.security_config.secret_key
            # Fernet key must be 32 url-safe base64-encoded bytes
            key_bytes = key.encode()
            key_hash = hashlib.sha256(key_bytes).digest()
            fernet_key = base64.urlsafe_b64encode(key_hash)
            self._fernet = Fernet(fernet_key)
        return self._fernet

    def _encrypt(self, data: Dict[str, Any]) -> str:
        f = self._get_fernet()
        return f.encrypt(json.dumps(data).encode()).decode()

    def _decrypt(self, encrypted_data: Any) -> Dict[str, Any]:
        if not encrypted_data:
            return {}
        
        # If it's already a dict (SQLAlchemy JSON column might return it as dict if it was stored as JSON)
        # However, we intend to store it as an encrypted string.
        if isinstance(encrypted_data, dict):
            return encrypted_data
            
        # Support for transitional plain-text (if it starts with { look like JSON)
        if isinstance(encrypted_data, str) and encrypted_data.startswith('{'):
            try:
                return json.loads(encrypted_data)
            except Exception as e:
                logger.warning(f"Failed to parse plain-text credentials: {e}")
        
        try:
            f = self._get_fernet()
            decrypted = f.decrypt(encrypted_data.encode()).decode()
            return json.loads(decrypted)
        except Exception as e:
            logger.error(f"Failed to decrypt credentials: {e}")
            return {}
    
    async def list_connections(self, user_id: str, integration_id: Optional[str] = None) -> List["UserConnection"]:
        """List connections for a user as ORM rows (used by MCP tool dispatch).

        The MCP tool handlers (``integrations/mcp_service.py``) await
        ``conn_service.list_connections(...)`` and then access attributes
        like ``conn.piece_name`` / ``conn.credentials`` / ``conn.metadata``
        on the rows. ``get_connections`` returns plain dicts, which does not
        satisfy that contract — this method returns the ORM rows instead.
        """
        with get_db_session() as db:
            try:
                query = db.query(UserConnection).filter(UserConnection.user_id == user_id)
                if integration_id:
                    query = query.filter(UserConnection.integration_id == integration_id)
                return query.all()
            except Exception as e:
                logger.error(f"Error retrieving connection rows: {e}")
                return []

    def get_connections(self, user_id: str, integration_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List connections for a user, optionally filtered by integration.
        """
        with get_db_session() as db:
            try:
                query = db.query(UserConnection).filter(UserConnection.user_id == user_id)
                if integration_id:
                    query = query.filter(UserConnection.integration_id == integration_id)

                connections = query.all()
                return [
                    {
                        "id": c.id,
                        "name": c.connection_name,
                        "integration_id": c.integration_id,
                        "status": c.status,
                        "created_at": c.created_at.isoformat() if c.created_at else None,
                        "last_used": c.last_used.isoformat() if c.last_used else None
                    }
                    for c in connections
                ]
            except Exception as e:
                logger.error(f"Error retrieving connections: {e}")
                return []

    def save_connection(self, user_id: str, integration_id: str, name: str, credentials: Dict[str, Any], workspace_id: Optional[str] = None) -> UserConnection:
        """
        Saves or updates a user connection.
        Calculates expires_at if possible and encrypts credentials.
        """
        with get_db_session() as db:
            try:
                # Check for existing connection for this user and integration
                conn = db.query(UserConnection).filter(
                    UserConnection.user_id == user_id,
                    UserConnection.integration_id == integration_id
                ).first()

                # Calculate expires_at — use timezone-aware UTC to match
                # get_connection_health_status and _refresh_token_if_needed
                # (Bug #10: previously used naive datetime.now(timezone.utc) which was
                # compared against aware datetime.now(timezone.utc), causing
                # expiry checks to be off by the server's UTC offset).
                expires_at = None
                expires_in = credentials.get("expires_in")
                if expires_in:
                    try:
                        expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to parse expires_in: {e}")

                encrypted_creds = self._encrypt(credentials)

                if conn:
                    conn.connection_name = name
                    conn.credentials = encrypted_creds
                    conn.updated_at = datetime.now(timezone.utc)
                    if expires_at:
                        conn.expires_at = expires_at
                    db.commit()
                    db.refresh(conn)
                    return conn
                else:
                    new_conn = UserConnection(
                        id=str(uuid.uuid4()),
                        user_id=user_id,
                        workspace_id=workspace_id,
                        integration_id=integration_id,
                        connection_name=name,
                        credentials=encrypted_creds,
                        expires_at=expires_at,
                        status="active"
                    )
                    db.add(new_conn)
                    db.commit()
                    db.refresh(new_conn)
                    return new_conn
            except Exception as e:
                logger.error(f"Error saving connection: {e}")
                raise

    async def get_connection_credentials(self, connection_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the credentials for a connection.
        Ensures user owns the connection and refreshes token if needed.
        """
        with get_db_session() as db:
            try:
                conn = db.query(UserConnection).filter(
                    UserConnection.id == connection_id,
                    UserConnection.user_id == user_id
                ).first()

                if conn:
                    # Decrypt credentials for use
                    creds = self._decrypt(conn.credentials)

                    # Automatic refresh logic
                    updated_creds = await self._refresh_token_if_needed(conn, creds)
                    if updated_creds:
                        conn.credentials = self._encrypt(updated_creds)
                        # Recalculate expires_at from new data
                        expires_in = updated_creds.get("expires_in")
                        if expires_in:
                            conn.expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
                        conn.updated_at = datetime.now(timezone.utc)
                        conn.status = "active" # Mark as active if refresh succeeds
                        db.commit()
                        creds = updated_creds
                    else:
                        # Refresh failed — _refresh_token_if_needed returned None.
                        # The old code returned the stale/expired token as if it
                        # were valid. Check if the token is actually expired and
                        # refuse to hand it back.
                        expires_at = conn.expires_at
                        if expires_at and datetime.now(timezone.utc) >= expires_at:
                            logger.error(
                                f"Token for connection {connection_id} is expired "
                                f"and refresh failed — refusing to return stale token"
                            )
                            conn.status = "error"
                            db.commit()
                            return None

                    # Update last used
                    conn.last_used = datetime.now(timezone.utc)
                    db.commit()
                    return creds
                return None
            except Exception as e:
                logger.error(f"Error retrieving connection credentials: {e}")
                return None

    @staticmethod
    def _has_nonempty_identifier(value: Any) -> bool:
        """Return True only for a usable, non-blank string identifier."""
        return isinstance(value, str) and bool(value.strip())

    @staticmethod
    def get_scoped_connection_metadata(
        db, *, user_id, tenant_id, workspace_id, connection_id, integration_id,
    ):
        """Read exact active connection identity without reading credentials.

        Raw tenant/workspace values are compared exactly, including SQL NULL.
        This is metadata authority for saved event bindings, not proof that a
        provider is reachable or that a credential can be refreshed.
        """
        if not all(isinstance(v, str) and v.strip() for v in (
                user_id, connection_id, integration_id)):
            return None
        row = db.query(
            UserConnection.id, UserConnection.user_id, UserConnection.tenant_id,
            UserConnection.workspace_id, UserConnection.integration_id,
            UserConnection.status,
        ).filter(
            UserConnection.id == connection_id,
            UserConnection.user_id == user_id,
            UserConnection.tenant_id == tenant_id,
            UserConnection.workspace_id == workspace_id,
            UserConnection.integration_id == integration_id,
            UserConnection.status == "active",
        ).first()
        return dict(row._mapping) if row is not None else None

    def get_scoped_connection_credentials(
        self,
        user_id: str,
        tenant_id: str,
        workspace_id: str,
        connection_id: str,
        integration_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Read exactly one active, fully scoped connection's credentials.

        This is an opt-in, server-side verification read. It deliberately does
        no provider I/O, token refresh, last_used update, database writes, or
        fallback lookup. Provider refresh is an explicit opt-in through
        ensure_scoped_connection_credentials.
        """
        identifiers = (
            user_id,
            tenant_id,
            workspace_id,
            connection_id,
            integration_id,
        )
        if not all(self._has_nonempty_identifier(value) for value in identifiers):
            return None

        with get_db_session() as db:
            try:
                conn = db.query(UserConnection).filter(
                    UserConnection.id == connection_id,
                    UserConnection.user_id == user_id,
                    UserConnection.tenant_id == tenant_id,
                    UserConnection.workspace_id == workspace_id,
                    UserConnection.integration_id == integration_id,
                    UserConnection.status == "active",
                ).first()

                if not conn:
                    return None

                # Reuse the existing timezone normalization for naive DB values.
                expires_at = self._ensure_aware_datetime(
                    getattr(conn, "expires_at", None)
                )
                if expires_at is not None and datetime.now(timezone.utc) >= expires_at:
                    return None

                encrypted = getattr(conn, "credentials", None)
                if not isinstance(encrypted, str) or not encrypted.strip():
                    return None
                if encrypted.lstrip().startswith("{"):
                    # Never accept _decrypt's legacy plain-text fallback here.
                    return None

                creds = self._decrypt(encrypted)
                if not isinstance(creds, dict) or not creds:
                    return None
                return creds
            except Exception as e:
                logger.error(f"Error retrieving scoped connection credentials: {e}")
                return None

    async def ensure_scoped_connection_credentials(
        self, *, user_id: str, tenant_id: str, workspace_id: str,
        connection_id: str, integration_id: str, provider: str, db_factory=None,
    ) -> Optional[Dict[str, Any]]:
        """Refresh an exact current grant through the existing operation arbiter.

        Opt-in only: the synchronous verification read remains read-only. The
        server adapter supplies the registered OAuth provider, never a payload.
        One observed encrypted credential version has one durable refresh
        attempt. Unknown outcomes do not resend; a reconnect supplies a new
        credential version. Tokens are stored encrypted with the success
        receipt in one winning transition, never in operation metadata.
        """
        import hmac
        from sqlalchemy import update
        from core.models import User, TaskOperationRecord, AuditLog
        from core import outbound_operation_claim as operations
        from core.oauth_handler import OAuthHandler, OAuthRefreshRefused, PROVIDER_CONFIGS
        factory = db_factory or get_db_session
        identifiers = (user_id, tenant_id, workspace_id, connection_id, integration_id, provider)
        if not all(self._has_nonempty_identifier(value) for value in identifiers):
            return None
        scope = dict(id=connection_id, user_id=user_id, tenant_id=tenant_id,
                     workspace_id=workspace_id, integration_id=integration_id, status='active')
        with factory() as db:
            actor = db.query(User).filter(User.id == user_id, User.tenant_id == tenant_id,
                User.workspace_id == workspace_id, User.is_active.is_(True), User.status == 'active').first()
            row = db.query(UserConnection).filter(*(getattr(UserConnection, k) == v for k, v in scope.items())).first()
            if actor is None or row is None:
                return None
            raw = row.credentials
            if not isinstance(raw, str) or not raw or raw.lstrip().startswith('{'):
                return None
            credentials = self._decrypt(raw)
            if not isinstance(credentials, dict) or not credentials:
                return None
            authority = {k: getattr(actor, k) for k in ('id', 'role', 'status', 'is_active', 'tenant_id', 'workspace_id')}
            observed = dict(scope, credentials=raw, expires_at=row.expires_at, scope=row.scope)
            expiry = self._ensure_aware_datetime(row.expires_at)
            if expiry is None or expiry > datetime.now(timezone.utc) + timedelta(minutes=5):
                return credentials
        refresh = credentials.get('refresh_token')
        config = PROVIDER_CONFIGS.get(provider)
        if not isinstance(refresh, str) or not refresh or config is None or not config.is_configured():
            # Proactive refresh must not discard a grant that is still valid.
            return credentials if expiry is not None and expiry > datetime.now(timezone.utc) else None
        authorized_material = {'token_url': config.token_url, 'client_id': config.client_id, 'client_secret': config.client_secret}
        material_digest = hmac.new(self.security_config.secret_key.encode(),
            json.dumps(authorized_material, sort_keys=True).encode(), hashlib.sha256).hexdigest()
        # Only this keyed commitment leaves the private observed state.
        version = hmac.new(self.security_config.secret_key.encode(),
            json.dumps({'connection_id': connection_id, 'credentials': raw}, sort_keys=True).encode(), hashlib.sha256).hexdigest()
        observed_digest = hmac.new(self.security_config.secret_key.encode(),
            json.dumps(observed, sort_keys=True, default=str).encode(), hashlib.sha256).hexdigest()
        operation_id = str(uuid.uuid5(uuid.NAMESPACE_URL, 'atom:connection-refresh:' + version))
        payload_hash = operations.operation_payload_sha256(workspace_id=workspace_id, tenant_id=tenant_id,
            actor_id=user_id, agent_id=None, execution_id=operation_id, action='refresh_connection_credentials',
            actor_kind='user', execution_kind='connection_maintenance',
            frozen_args={'version': version, 'observed': observed_digest, 'provider': provider, 'authority': authority, 'oauth_material': material_digest})
        claim = operations.claim_generic_operation(workspace_id=workspace_id, tenant_id=tenant_id,
            operation_id=operation_id, action='refresh_connection_credentials', payload_hash=payload_hash,
            execution_id=operation_id, db_factory=factory)
        if claim.get('status') != operations.CLAIMED or not claim.get('record_id'):
            return None
        record_id = claim['record_id']
        def claim_current(db, values=None):
            principal = db.execute(update(User).where(*(getattr(User, k) == v for k, v in authority.items()))
                .values(status=User.status, updated_at=User.updated_at).execution_options(synchronize_session=False))
            target = db.execute(update(UserConnection).where(*(getattr(UserConnection, k) == v for k, v in observed.items()))
                .values(**(values or {'status': UserConnection.status, 'updated_at': UserConnection.updated_at}))
                .execution_options(synchronize_session=False))
            if principal.rowcount != 1 or target.rowcount != 1:
                raise ValueError('connection authority or credential version changed')
            prior = db.query(TaskOperationRecord).filter(TaskOperationRecord.operation_id == operation_id,
                TaskOperationRecord.id != record_id, TaskOperationRecord.status != operations.CLAIMED).first()
            if prior is not None:
                raise ValueError('credential version already dispatched under another scope')
        if not operations.mark_status(record_id, operations.DISPATCHING, expected_status=operations.CLAIMED,
                expected_payload_sha256=payload_hash, transition_effect=claim_current, db_factory=factory):
            return None
        try:
            grant = await OAuthHandler(config).refresh_access_token(refresh, authorized_material=authorized_material)
            if (not isinstance(grant, dict) or not isinstance(grant.get('access_token'), str)
                    or not grant['access_token'].strip()):
                raise ValueError('refresh grant is unavailable')
            if 'refresh_token' in grant and (not isinstance(grant['refresh_token'], str) or not grant['refresh_token']):
                raise ValueError('refresh replacement is malformed')
            seconds = grant.get('expires_in')
            if isinstance(seconds, bool) or not isinstance(seconds, (int, str)):
                raise ValueError('refresh lifetime is unavailable')
            seconds = int(seconds)
            if seconds <= 0:
                raise ValueError('refresh lifetime is invalid')
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
            renewed = {**credentials, **grant}
            encrypted = self._encrypt(renewed)
            commitment = hmac.new(self.security_config.secret_key.encode(), encrypted.encode(), hashlib.sha256).hexdigest()
            receipt = dict(connection_id=connection_id, result_digest=commitment, expires_at=expires_at.isoformat())
            def store(db):
                claim_current(db, {'credentials': encrypted, 'expires_at': expires_at,
                    'last_refresh_at': datetime.now(timezone.utc), 'last_refresh_error': None,
                    'refresh_failure_count': 0, 'updated_at': datetime.now(timezone.utc)})
                db.add(AuditLog(event_type='connection_credential_refreshed', security_level='INFO',
                    threat_level='NONE', user_id=user_id, tenant_id=tenant_id, workspace_id=workspace_id,
                    resource=connection_id, action='refresh_connection_credentials', success=True,
                    description='Scoped connection credential refreshed', metadata_json=json.dumps({
                        'operation_id': operation_id, 'provider': provider, 'result_digest': commitment})))
            if not operations.mark_status(record_id, operations.SUCCEEDED, expected_status=operations.DISPATCHING,
                    expected_payload_sha256=payload_hash, result=receipt, transition_effect=store, db_factory=factory):
                raise ValueError('refresh storage outcome is unavailable')
            with factory() as db:
                current = db.query(UserConnection).filter(*(getattr(UserConnection, k) == v for k, v in scope.items())).first()
                principal = db.query(User).filter(*(getattr(User, k) == v for k, v in authority.items())).first()
                operation = db.get(TaskOperationRecord, record_id)
                if (current is None or principal is None or current.credentials != encrypted
                        or self._ensure_aware_datetime(current.expires_at) != expires_at
                        or operation is None or operation.status != operations.SUCCEEDED
                        or operation.payload_sha256 != payload_hash or operation.result_json != receipt):
                    return None
            return renewed
        except OAuthRefreshRefused:
            operations.mark_status(record_id, operations.FAILED_BEFORE_EFFECT, expected_status=operations.DISPATCHING,
                expected_payload_sha256=payload_hash, db_factory=factory)
            return None
        except Exception as exc:
            logger.warning('Scoped credential refresh unavailable (%s)', type(exc).__name__)
            operations.mark_status(record_id, operations.UNCERTAIN_EFFECT, expected_status=operations.DISPATCHING,
                expected_payload_sha256=payload_hash, db_factory=factory)
            return None

    def create_scoped_connection(
        self,
        user_id: str,
        tenant_id: str,
        workspace_id: str,
        integration_id: str,
        name: str,
        credentials: Dict[str, Any],
        connection_id: str,
    ) -> bool:
        """Create exactly one fully scoped connection with a caller-chosen ID.

        This is the paired write for ``get_scoped_connection_credentials``. The
        caller is responsible for resolving the user/tenant/workspace scope
        from authenticated state; none of these values are inferred here.

        The supplied ``connection_id`` is used for one insert attempt only. This
        method never updates an existing row, never widens another row's scope,
        and never adopts or re-encrypts legacy credentials. It returns ``True``
        only when a new row was committed, and ``False`` for invalid input,
        an already-existing ID, or a concurrent primary-key collision.
        Credential material is never logged.
        """
        identifiers = (
            user_id,
            tenant_id,
            workspace_id,
            integration_id,
            name,
            connection_id,
        )
        if not all(self._has_nonempty_identifier(value) for value in identifiers):
            return False
        if not isinstance(credentials, dict) or not credentials:
            return False

        with get_db_session() as db:
            try:
                existing = db.query(UserConnection).filter(
                    UserConnection.id == connection_id
                ).first()
                if existing is not None:
                    return False

                # Match save_connection's expiry semantics exactly.
                expires_at = None
                expires_in = credentials.get("expires_in")
                if expires_in:
                    try:
                        expires_at = datetime.now(timezone.utc) + timedelta(
                            seconds=int(expires_in)
                        )
                    except (ValueError, TypeError):
                        logger.warning(
                            "Failed to parse expires_in for scoped connection %s",
                            connection_id,
                        )

                new_conn = UserConnection(
                    id=connection_id,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    integration_id=integration_id,
                    connection_name=name,
                    credentials=self._encrypt(credentials),
                    expires_at=expires_at,
                    status="active",
                )
                db.add(new_conn)
                db.commit()
                return True
            except Exception as exc:
                # A concurrent insert may win after the existence check. Roll
                # back so the failed primary key is not left pending, and do
                # not retry with a different ID or fall back to an update.
                try:
                    db.rollback()
                except Exception:
                    pass
                logger.warning(
                    "Scoped connection creation failed for %s: %s",
                    connection_id,
                    type(exc).__name__,
                )
                return False

    # H2 fix: per-connection locks prevent concurrent refresh races where
    # two requests for the same expired credential each fire a refresh,
    # and for providers that rotate refresh tokens (Google, Microsoft), the
    # second request uses an already-invalidated token → permanent breakage.
    _refresh_locks: dict = {}

    def _get_refresh_lock(self, conn_id: str):
        """Get or create an asyncio.Lock for a specific connection."""
        import asyncio
        if conn_id not in self._refresh_locks:
            self._refresh_locks[conn_id] = asyncio.Lock()
        return self._refresh_locks[conn_id]

    async def _refresh_token_if_needed(self, conn: UserConnection, creds: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Checks if the token is expired and refreshes it using refresh_token if available.
        Serializes refresh per-connection to prevent race conditions (H2).
        """
        if not creds:
            return None

        # Check if we have a refresh token
        refresh_token = creds.get("refresh_token")
        if not refresh_token:
            return None

        # Check if token is expired or near expiry (within 5 minutes)
        should_refresh = False
        if conn.expires_at:
            # H3 fix: ensure both sides are timezone-aware before comparison.
            expires = conn.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) + timedelta(minutes=5) >= expires:
                should_refresh = True
        else:
            # Heuristic: if last updated > 55 mins ago and we have a refresh token, maybe just refresh?
            # For now, we'll use this heuristic: if token was updated more than 55 minutes ago
            # and we have a refresh token available, proactively refresh it.
            if conn.updated_at:
                token_age = datetime.now(timezone.utc) - conn.updated_at
                if token_age > timedelta(minutes=55) and refresh_token:
                    logger.info(
                        f"Token for {conn.integration_id} is {int(token_age.total_seconds()) // 60} minutes old, "
                        f"proactively refreshing"
                    )
                    should_refresh = True
            
        if not should_refresh:
            return None

        from integrations.universal.config import get_oauth_config
        config = get_oauth_config(conn.integration_id)
        if not config:
            return None

        import httpx
        # H2 fix: acquire per-connection lock so concurrent callers serialize.
        async with self._get_refresh_lock(conn.id):
            try:
                logger.info(f"Attempting to refresh token for {conn.integration_id} (Connection: {conn.id})")
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        config["token_url"],
                        data={
                            "grant_type": "refresh_token",
                            "refresh_token": refresh_token,
                            "client_id": config["client_id"],
                            "client_secret": config["client_secret"]
                        }
                    )
                    if resp.status_code == 200:
                        new_token_data = resp.json()
                        updated_creds = {**creds, **new_token_data}
                        return updated_creds
                    else:
                        logger.error(f"Refresh failed for {conn.integration_id}: {resp.text}")
                        with get_db_session() as db:
                            conn_to_update = db.query(UserConnection).get(conn.id)
                            if conn_to_update:
                                conn_to_update.status = "error"
                                db.commit()
            except Exception as e:
                logger.error(f"Error during token refresh: {e}")
            
        return None

    def update_connection_name(self, connection_id: str, user_id: str, new_name: str) -> bool:
        with get_db_session() as db:
            try:
                conn = db.query(UserConnection).filter(
                    UserConnection.id == connection_id,
                    UserConnection.user_id == user_id
                ).first()
                if conn:
                    conn.connection_name = new_name
                    conn.updated_at = datetime.now(timezone.utc)
                    db.commit()
                    return True
                return False
            except Exception as e:
                logger.error(f"Error updating connection name: {e}")
                return False

    def _ensure_aware_datetime(self, dt: Optional[datetime]) -> Optional[datetime]:
        """
        Convert naive datetime to timezone-aware (UTC).
        If already aware, return as-is. Handles None.
        """
        if dt is None:
            return None
        from datetime import timezone
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def get_connection_health_status(self, connection_id: str, user_id: str) -> Dict[str, Any]:
        """
        Calculate health status for a connection.
        """
        with get_db_session() as db:
            try:
                conn = db.query(UserConnection).filter(
                    UserConnection.id == connection_id,
                    UserConnection.user_id == user_id
                ).first()

                if not conn:
                    return {
                        "health_status": "error",
                        "last_sync_at": None,
                        "error_message": "Connection not found",
                        "expires_at": None,
                    }

                from datetime import timezone
                now = datetime.now(timezone.utc)
                health_status = "healthy"
                error_message = None

                # Calculate health status based on status and expiry
                if conn.status == "error":
                    health_status = "error"
                    error_message = "Connection is in error state"
                elif conn.status == "expired":
                    health_status = "expired"
                    error_message = "Connection has expired"
                elif conn.status == "disabled":
                    health_status = "error"
                    error_message = "Connection is disabled"
                elif conn.expires_at:
                    # Ensure expires_at is timezone-aware for comparison
                    expires_at = self._ensure_aware_datetime(conn.expires_at)
                    if now > expires_at:
                        health_status = "expired"
                        error_message = "Connection credentials have expired"
                    elif now + timedelta(hours=24) >= expires_at:
                        health_status = "expiring_soon"
                        error_message = None
                    else:
                        health_status = "healthy"
                        error_message = None
                else:
                    # No expires_at - assume healthy if status is active
                    health_status = "healthy" if conn.status == "active" else "error"

                return {
                    "health_status": health_status,
                    "last_sync_at": conn.updated_at.isoformat() if conn.updated_at else None,
                    "error_message": error_message,
                    "expires_at": conn.expires_at.isoformat() if conn.expires_at else None,
                }
            except Exception as e:
                logger.error(f"Error calculating connection health: {e}")
                return {
                    "health_status": "error",
                    "last_sync_at": None,
                    "error_message": str(e),
                    "expires_at": None,
                }

    def delete_connection(self, connection_id: str, user_id: str) -> bool:
        with get_db_session() as db:
            try:
                conn = db.query(UserConnection).filter(
                    UserConnection.id == connection_id,
                    UserConnection.user_id == user_id
                ).first()
                if conn:
                    db.delete(conn)
                    db.commit()
                    return True
                return False
            except Exception as e:
                logger.error(f"Error deleting connection: {e}")
                return False

# Singleton
connection_service = ConnectionService()
