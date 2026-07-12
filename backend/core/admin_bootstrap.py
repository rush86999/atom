import logging
import os
import secrets
import uuid
from sqlalchemy.orm import Session

from core.auth import get_password_hash
from core.database import get_db_session
from core.models import (
    AgentRegistry,
    AgentStatus,
    Tenant,
    User,
    UserStatus,
    Workspace,
)
from core.personal_scope import PERSONAL_TENANT_ID, PERSONAL_WORKSPACE_ID

logger = logging.getLogger("ATOM_BOOTSTRAP")


def _write_password_to_secure_file(password: str) -> str:
    """Write the generated admin password to a 0600-permission file and return its path.

    This keeps the plaintext password out of application logs (which are often
    shipped to centralized logging) while still letting the operator retrieve it.
    """
    path = os.getenv("ATOM_BOOTSTRAP_PASSWORD_FILE") or os.path.join(
        os.getcwd(), "logs", "bootstrap_admin_password.txt"
    )
    try:
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        # Write with restrictive permissions: O_CREAT|O_TRUNC|O_WRONLY, mode 0600
        fd = os.open(path, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
        try:
            os.write(fd, password.encode("utf-8"))
        finally:
            os.close(fd)
        # Belt-and-suspenders: chmod again in case the file pre-existed.
        os.chmod(path, 0o600)
        return path
    except OSError as exc:
        logger.error(f"BOOTSTRAP: Could not write password file: {exc}")
        return ""


def ensure_admin_user():
    """
    Ensures the admin@example.com user exists with a secure password.
    This runs INSIDE the main application process to avoid DB locks.

    Password security:
    - Uses ADMIN_PASSWORD env var if set
    - Otherwise generates a secure random password on first run
    - Logs a warning to change the password in production
    """
    with get_db_session() as db:
        try:
            email = "admin@example.com"
            # Use environment variable or generate secure random password
            password = os.getenv("ADMIN_PASSWORD")
            is_generated = False
            if not password:
                password = secrets.token_urlsafe(16)  # Generate secure random password
                is_generated = True

            user = db.query(User).filter(User.email == email).first()

            if user:
                # Only reset the password if ADMIN_PASSWORD env var is explicitly
                # set. Without this guard, every boot generates a new random
                # password and overwrites the file — the admin password flaps
                # on every restart, and anyone with logs/ access gets the live
                # credential.
                if password and os.getenv("ADMIN_PASSWORD"):
                    logger.info(f"BOOTSTRAP: User {email} found. Resetting password (ADMIN_PASSWORD set)...")
                    user.hashed_password = get_password_hash(password)
                    user.status = UserStatus.ACTIVE
                    user.role = "workspace_admin"
                    db.commit()
                    logger.info(f"BOOTSTRAP: Password for {email} has been reset")
                else:
                    logger.info(f"BOOTSTRAP: User {email} found. Keeping existing password (ADMIN_PASSWORD not set).")
            else:
                logger.info(f"BOOTSTRAP: User {email} not found. Creating...")
                new_user = User(
                    id=str(uuid.uuid4()),  # Random UUID — not a predictable constant
                    email=email,
                    hashed_password=get_password_hash(password),
                    first_name="Admin",
                    last_name="User",
                    role="workspace_admin",
                    status=UserStatus.ACTIVE
                )
                db.add(new_user)
                db.commit()
                logger.info(f"BOOTSTRAP: Created {email}")
                if is_generated:
                    pwd_file = _write_password_to_secure_file(password)
                    logger.warning("BOOTSTRAP: Generated temporary password written to %s (mode 0600). Set ADMIN_PASSWORD env var for production.", pwd_file or "<none>")
                    logger.warning("BOOTSTRAP: Set ADMIN_PASSWORD environment variable for production!")
            
            # Ensure default tenant and workspace
            ensure_default_tenant_and_workspace(db)

            # P1.3 — ensure the onboarding demo agent exists. Created at INTERN
            # tier with the explicit demo_agent flag so the governance service
            # can permit complexity ≤ 2 actions even though the agent has zero
            # episodes. New users land on this agent so their first chat can
            # produce a presentation/chart without waiting for graduation.
            ensure_demo_agent(db)
            
        except Exception as e:
            logger.error(f"BOOTSTRAP FAILED: {e}")
            db.rollback()
        finally:
            db.close()

def ensure_default_tenant_and_workspace(db: Session):
    """Ensures a default tenant and workspace exist for single-tenant mode."""
    # 1. Ensure Default Tenant
    tenant = db.query(Tenant).filter(Tenant.id == PERSONAL_TENANT_ID).first()
    if not tenant:
        logger.info("BOOTSTRAP: Creating default tenant...")
        tenant = Tenant(
            id=PERSONAL_TENANT_ID,
            name="Default Tenant",
            subdomain="default",
            edition="personal"
        )
        db.add(tenant)
        db.flush() # Get ID if not fixed

    # 2. Ensure Default Workspace
    workspace = db.query(Workspace).filter(Workspace.id == PERSONAL_WORKSPACE_ID).first()
    if not workspace:
        logger.info("BOOTSTRAP: Creating default workspace...")
        workspace = Workspace(
            id=PERSONAL_WORKSPACE_ID,
            tenant_id=PERSONAL_TENANT_ID,
            name="Default Workspace",
            description="Your personal workspace"
        )
        db.add(workspace)

    db.commit()
    logger.info("BOOTSTRAP: Default tenant and workspace ensured.")


def ensure_demo_agent(db: Session) -> None:
    """Ensure the onboarding "Demo Assistant" agent exists at INTERN tier.

    Rationale (per Plan agent RISK-A): creating an INTERN agent with zero
    episodes technically violates the graduation contract. The
    ``configuration["demo_agent"]`` flag makes the bypass explicit and
    auditable (see agent_governance_service.can_perform_action). The agent is
    workspace-scoped to "default" so single-tenant Personal Edition picks it
    up automatically; multi-tenant SaaS deployments simply never call this
    function because admin_bootstrap is single-tenant-only.

    Idempotent: if the demo agent already exists, no-op. This keeps restarts
    cheap and lets an admin delete the demo agent from the UI without it
    springing back to life on the next process boot.
    """
    existing = db.query(AgentRegistry).filter(
        AgentRegistry.name == "Demo Assistant",
        AgentRegistry.category == "system",
    ).first()
    if existing:
        return

    demo = AgentRegistry(
        name="Demo Assistant",
        description=(
            "Onboarding demo agent. INTERN tier with a governance bypass for "
            "complexity ≤ 2 actions so new users can explore streaming chat "
            "and canvas presentations without waiting to graduate. Delete this "
            "agent any time from Settings → Agents."
        ),
        category="system",
        module_path="system",
        class_name="DemoAssistant",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6,
        workspace_id=PERSONAL_WORKSPACE_ID,
        tenant_id=PERSONAL_TENANT_ID,
        configuration={
            "system_prompt": (
                "You are the Atom Demo Assistant. You help new users explore "
                "multi-agent governance, canvas presentations, and chat. Be "
                "concise and surface the platform's strengths."
            ),
            "capabilities": ["chat", "stream_chat", "present_chart", "present_markdown"],
            "demo_agent": True,
            "graduation_bypass_reason": "onboarding_demo",
        },
    )
    db.add(demo)
    db.commit()
    logger.info("BOOTSTRAP: Created onboarding Demo Assistant agent (id=%s)", demo.id)
