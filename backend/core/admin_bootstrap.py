import logging
import os
import secrets
from sqlalchemy.orm import Session

from core.auth import get_password_hash
from core.database import get_db_session
from core.models import User, UserStatus, Tenant, Workspace

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
                logger.info(f"BOOTSTRAP: User {email} found. Resetting password...")
                user.hashed_password = get_password_hash(password)
                user.status = UserStatus.ACTIVE
                user.role = "workspace_admin"  # Ensure role is set
                db.commit()
                logger.info(f"BOOTSTRAP: Password for {email} has been reset")
                if is_generated:
                    pwd_file = _write_password_to_secure_file(password)
                    logger.warning("BOOTSTRAP: Generated temporary password written to %s (mode 0600). Set ADMIN_PASSWORD env var for production.", pwd_file or "<none>")
                    logger.warning("BOOTSTRAP: Set ADMIN_PASSWORD environment variable for production!")
            else:
                logger.info(f"BOOTSTRAP: User {email} not found. Creating...")
                new_user = User(
                    id="00000000-0000-0000-0000-000000000000", # Fixed ID for development stability
                    email=email,
                    hashed_password=get_password_hash(password),
                    first_name="Admin",
                    last_name="User",
                    role="workspace_admin", # Explicitly set role
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
            
        except Exception as e:
            logger.error(f"BOOTSTRAP FAILED: {e}")
            db.rollback()
        finally:
            db.close()

def ensure_default_tenant_and_workspace(db: Session):
    """Ensures a default tenant and workspace exist for single-tenant mode."""
    # 1. Ensure Default Tenant
    tenant = db.query(Tenant).filter(Tenant.id == "default").first()
    if not tenant:
        logger.info("BOOTSTRAP: Creating default tenant...")
        tenant = Tenant(
            id="default",
            name="Default Tenant",
            subdomain="default",
            edition="personal"
        )
        db.add(tenant)
        db.flush() # Get ID if not fixed
    
    # 2. Ensure Default Workspace
    workspace = db.query(Workspace).filter(Workspace.id == "default").first()
    if not workspace:
        logger.info("BOOTSTRAP: Creating default workspace...")
        workspace = Workspace(
            id="default",
            tenant_id="default",
            name="Default Workspace",
            description="Your personal workspace"
        )
        db.add(workspace)
    
    db.commit()
    logger.info("BOOTSTRAP: Default tenant and workspace ensured.")
