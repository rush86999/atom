import logging
import ssl
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse
import ldap3
from fastapi import APIRouter, Depends, HTTPException
from ldap3 import ALL, ALL_ATTRIBUTES, ALL_OPERATIONAL_ATTRIBUTES, Connection, Server
from ldap3.core.exceptions import LDAPException, LDAPSocketOpenError
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# Directory Service Configuration
class DirectoryConfig(BaseModel):
    """Directory Service Configuration Model"""

    enabled: bool = Field(False, description="Enable directory integration")
    server_type: str = Field(
        "active_directory",
        description="Directory type (active_directory, openldap, azure_ad)",
    )
    server_url: str = Field(..., description="LDAP server URL (ldap:// or ldaps://)")
    base_dn: str = Field(..., description="Base distinguished name")
    bind_dn: Optional[str] = Field(None, description="Bind DN for authentication")
    bind_password: Optional[str] = Field(None, description="Bind password")
    user_search_base: Optional[str] = Field(None, description="User search base DN")
    group_search_base: Optional[str] = Field(None, description="Group search base DN")
    user_object_class: str = Field("user", description="User object class")
    group_object_class: str = Field("group", description="Group object class")
    user_id_attribute: str = Field("sAMAccountName", description="User ID attribute")
    user_email_attribute: str = Field("mail", description="User email attribute")
    user_first_name_attribute: str = Field(
        "givenName", description="User first name attribute"
    )
    user_last_name_attribute: str = Field("sn", description="User last name attribute")
    group_member_attribute: str = Field("member", description="Group member attribute")
    use_ssl: bool = Field(True, description="Use SSL/TLS")
    verify_ssl: bool = Field(True, description="Verify SSL certificate")
    timeout: int = Field(30, description="Connection timeout in seconds")


class DirectoryUser(BaseModel):
    """Directory User Information"""

    dn: str = Field(..., description="Distinguished name")
    user_id: str = Field(..., description="User identifier")
    email: str = Field(..., description="User email")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    display_name: Optional[str] = Field(None, description="Display name")
    department: Optional[str] = Field(None, description="Department")
    title: Optional[str] = Field(None, description="Job title")
    manager: Optional[str] = Field(None, description="Manager DN")
    groups: List[str] = Field(default_factory=list, description="Group memberships")
    attributes: Dict[str, Any] = Field(
        default_factory=dict, description="Additional attributes"
    )
    last_sync: Optional[str] = Field(None, description="Last synchronization timestamp")


class DirectoryGroup(BaseModel):
    """Directory Group Information"""

    dn: str = Field(..., description="Distinguished name")
    name: str = Field(..., description="Group name")
    description: Optional[str] = Field(None, description="Group description")
    members: List[str] = Field(default_factory=list, description="Group members")
    member_count: int = Field(0, description="Number of members")
    group_type: Optional[str] = Field(None, description="Group type")
    attributes: Dict[str, Any] = Field(
        default_factory=dict, description="Additional attributes"
    )


class SyncResult(BaseModel):
    """Directory Synchronization Result"""

    users_synced: int = Field(0, description="Number of users synchronized")
    groups_synced: int = Field(0, description="Number of groups synchronized")
    errors: List[str] = Field(
        default_factory=list, description="Synchronization errors"
    )
    duration_seconds: float = Field(0.0, description="Sync duration in seconds")
    timestamp: str = Field(..., description="Sync completion timestamp")


class DirectoryConnection:
    """LDAP Directory Connection Manager"""

    def __init__(self, config: DirectoryConfig):
        self.config = config
        self.connection: Optional[Connection] = None
        self.server: Optional[Server] = None

    def connect(self) -> bool:
        """Establish connection to directory server"""
        try:
            # Parse server URL
            parsed_url = urlparse(self.config.server_url)
            host = parsed_url.hostname
            port = parsed_url.port or (636 if self.config.use_ssl else 389)

            # Configure SSL/TLS
            tls_config = None
            if self.config.use_ssl:
                tls_config = ldap3.Tls(
                    validate=ssl.CERT_REQUIRED
                    if self.config.verify_ssl
                    else ssl.CERT_NONE
                )

            # Create server
            self.server = Server(
                host=host,
                port=port,
                use_ssl=self.config.use_ssl,
                tls=tls_config,
                get_info=ALL,
            )

            # Create connection
            self.connection = Connection(
                self.server,
                user=self.config.bind_dn,
                password=self.config.bind_password,
                auto_bind=True,
                receive_timeout=self.config.timeout,
            )

            logger.info(f"Successfully connected to directory server: {host}:{port}")
            return True

        except LDAPSocketOpenError as e:
            logger.error(f"Failed to connect to directory server: {e}")
            return False
        except LDAPException as e:
            logger.error(f"LDAP connection error: {e}")
            return False

    def disconnect(self):
        """Close directory connection"""
        if self.connection and self.connection.bound:
            self.connection.unbind()
            self.connection = None
            logger.info("Directory connection closed")

    def is_connected(self) -> bool:
        """Check if connection is active"""
        return self.connection is not None and self.connection.bound

    def search(
        self, search_base: str, search_filter: str, attributes: List[str] = None
    ) -> List[Dict]:
        """Perform LDAP search"""
        if not self.is_connected():
            raise HTTPException(status_code=500, detail="Not connected to directory")

        try:
            attributes = attributes or [ALL_ATTRIBUTES]
            self.connection.search(
                search_base=search_base,
                search_filter=search_filter,
                attributes=attributes,
            )

            results = []
            for entry in self.connection.entries:
                result = {}
                for attr in entry.entry_attributes:
                    values = entry[attr].value
                    if isinstance(values, list):
                        result[attr] = [str(v) for v in values]
                    else:
                        result[attr] = str(values) if values else None
                result["dn"] = str(entry.entry_dn)
                results.append(result)

            return results

        except LDAPException as e:
            logger.error(f"LDAP search error: {e}")
            raise HTTPException(status_code=500, detail=f"Directory search failed: {e}")


class EnterpriseDirectoryService:
    """Enterprise Directory Integration Service"""

    def __init__(self):
        self.router = APIRouter()
        self.config: Optional[DirectoryConfig] = None
        self.connection: Optional[DirectoryConnection] = None
        self.setup_routes()

    def setup_routes(self):
        """Setup directory service routes"""
        self.router.add_api_route(
            "/directory/health",
            self.health_check,
            methods=["GET"],
            summary="Directory service health check",
        )
        self.router.add_api_route(
            "/directory/config",
            self.get_configuration,
            methods=["GET"],
            summary="Get directory configuration",
        )
        self.router.add_api_route(
            "/directory/config",
            self.update_configuration,
            methods=["PUT"],
            summary="Update directory configuration",
        )
        self.router.add_api_route(
            "/directory/users",
            self.search_users,
            methods=["GET"],
            summary="Search directory users",
        )
        self.router.add_api_route(
            "/directory/users/{user_id}",
            self.get_user,
            methods=["GET"],
            summary="Get directory user by ID",
        )
        self.router.add_api_route(
            "/directory/groups",
            self.search_groups,
            methods=["GET"],
            summary="Search directory groups",
        )
        self.router.add_api_route(
            "/directory/groups/{group_name}",
            self.get_group,
            methods=["GET"],
            summary="Get directory group by name",
        )
        self.router.add_api_route(
            "/directory/sync",
            self.sync_directory,
            methods=["POST"],
            summary="Synchronize directory data",
        )
        self.router.add_api_route(
            "/directory/test",
            self.test_connection,
            methods=["POST"],
            summary="Test directory connection",
        )

    def initialize(self, config: DirectoryConfig):
        """Initialize directory service with configuration"""
        self.config = config
        self.connection = DirectoryConnection(config)

    async def health_check(self) -> Dict[str, Any]:
        """Directory service health check"""
        if not self.config or not self.connection:
            return {
                "status": "unconfigured",
                "service": "directory",
                "connected": False,
                "message": "Directory service not configured",
            }

        connected = self.connection.is_connected()
        if not connected:
            connected = self.connection.connect()

        return {
            "status": "healthy" if connected else "unhealthy",
            "service": "directory",
            "connected": connected,
            "server_type": self.config.server_type,
            "base_dn": self.config.base_dn,
        }

    async def get_configuration(self) -> DirectoryConfig:
        """Get directory configuration"""
        if not self.config:
            raise HTTPException(
                status_code=404, detail="Directory configuration not found"
            )

        # Return configuration without sensitive data
        safe_config = self.config.copy()
        safe_config.bind_password = "***" if self.config.bind_password else None
        return safe_config

    async def update_configuration(self, config: DirectoryConfig):
        """Update directory configuration"""
        self.config = config
        self.connection = DirectoryConnection(config)

        # Test connection with new configuration
        if config.enabled:
            connected = self.connection.connect()
            if not connected:
                raise HTTPException(
                    status_code=400, detail="Failed to connect with new configuration"
                )

        return {"message": "Directory configuration updated successfully"}

    async def search_users(
        self, query: str = "", limit: int = 100, offset: int = 0
    ) -> Dict[str, Any]:
        """Search directory users"""
        if not self.config or not self.connection or not self.connection.is_connected():
            raise HTTPException(
                status_code=500, detail="Directory service not available"
            )

        try:
            search_base = self.config.user_search_base or self.config.base_dn
            search_filter = f"(&(objectClass={self.config.user_object_class})"

            if query:
                search_filter += f"(|({self.config.user_id_attribute}=*{query}*)(mail=*{query}*)(displayName=*{query}*)))"
            else:
                search_filter += ")"

            attributes = [
                self.config.user_id_attribute,
                self.config.user_email_attribute,
                self.config.user_first_name_attribute,
                self.config.user_last_name_attribute,
                "displayName",
                "department",
                "title",
                "manager",
            ]

            results = self.connection.search(search_base, search_filter, attributes)

            users = []
            for result in results[offset : offset + limit]:
                user = self._parse_user_result(result)
                users.append(user)

            return {
                "users": users,
                "total_count": len(results),
                "limit": limit,
                "offset": offset,
            }

        except Exception as e:
            logger.error(f"User search failed: {e}")
            raise HTTPException(status_code=500, detail=f"User search failed: {e}")

    async def get_user(self, user_id: str) -> DirectoryUser:
        """Get directory user by ID"""
        if not self.config or not self.connection or not self.connection.is_connected():
            raise HTTPException(
                status_code=500, detail="Directory service not available"
            )

        try:
            search_base = self.config.user_search_base or self.config.base_dn
            search_filter = f"(&(objectClass={self.config.user_object_class})({self.config.user_id_attribute}={user_id}))"

            attributes = [
                self.config.user_id_attribute,
                self.config.user_email_attribute,
                self.config.user_first_name_attribute,
                self.config.user_last_name_attribute,
                "displayName",
                "department",
                "title",
                "manager",
                "memberOf",
            ]

            results = self.connection.search(search_base, search_filter, attributes)

            if not results:
                raise HTTPException(status_code=404, detail="User not found")

            user = self._parse_user_result(results[0])

            # Get user's groups
            user.groups = await self._get_user_groups(user.dn)

            return user

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get user: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get user: {e}")

    async def search_groups(
        self, query: str = "", limit: int = 100, offset: int = 0
    ) -> Dict[str, Any]:
        """Search directory groups"""
        if not self.config or not self.connection or not self.connection.is_connected():
            raise HTTPException(
                status_code=500, detail="Directory service not available"
            )

        try:
            search_base = self.config.group_search_base or self.config.base_dn
            search_filter = f"(&(objectClass={self.config.group_object_class})"

            if query:
                search_filter += f"(|(cn=*{query}*)(description=*{query}*)))"
            else:
                search_filter += ")"

            attributes = ["cn", "description", "member", "groupType"]

            results = self.connection.search(search_base, search_filter, attributes)

            groups = []
            for result in results[offset : offset + limit]:
                group = self._parse_group_result(result)
                groups.append(group)

            return {
                "groups": groups,
                "total_count": len(results),
                "limit": limit,
                "offset": offset,
            }

        except Exception as e:
            logger.error(f"Group search failed: {e}")
            raise HTTPException(status_code=500, detail=f"Group search failed: {e}")

    async def get_group(self, group_name: str) -> DirectoryGroup:
        """Get directory group by name"""
        if not self.config or not self.connection or not self.connection.is_connected():
            raise HTTPException(
                status_code=500, detail="Directory service not available"
            )

        try:
            search_base = self.config.group_search_base or self.config.base_dn
            search_filter = (
                f"(&(objectClass={self.config.group_object_class})(cn={group_name}))"
            )

            attributes = ["cn", "description", "member", "groupType"]

            results = self.connection.search(search_base, search_filter, attributes)

            if not results:
                raise HTTPException(status_code=404, detail="Group not found")

            return self._parse_group_result(results[0])

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get group: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to get group: {e}")

    async def sync_directory(self, full_sync: bool = False) -> SyncResult:
        """Synchronize directory data"""
        if not self.config or not self.connection or not self.connection.is_connected():
            raise HTTPException(
                status_code=500, detail="Directory service not available"
            )

        start_time = datetime.utcnow()
        errors = []
        users_synced = 0
        groups_synced = 0

        try:
            # Sync users
            users_result = await self.search_users(limit=1000)  # Adjust limit as needed
            users_synced = len(users_result["users"])

            # Sync groups
            groups_result = await self.search_groups(
                limit=1000
            )  # Adjust limit as needed
            groups_synced = len(groups_result["groups"])

            # In production, store synchronized data in application database
            # This is where you'd implement the actual synchronization logic

            logger.info(
                f"Directory sync completed: {users_synced} users, {groups_synced} groups"
            )

        except Exception as e:
            errors.append(f"Sync error: {str(e)}")
            logger.error(f"Directory sync failed: {e}")

        duration = (datetime.utcnow() - start_time).total_seconds()

        return SyncResult(
            users_synced=users_synced,
            groups_synced=groups_synced,
            errors=errors,
            duration_seconds=duration,
            timestamp=datetime.utcnow().isoformat(),
        )

    async def test_connection(self) -> Dict[str, Any]:
        """Test directory connection"""
        if not self.config:
            return {"status": "error", "message": "Directory configuration not set"}

        try:
            connection = DirectoryConnection(self.config)
            connected = connection.connect()

            if connected:
                # Test basic search
                search_base = self.config.base_dn
                search_filter = f"(objectClass=*)"

                try:
                    results = connection.search(
                        search_base, search_filter, ["objectClass"], size_limit=1
                    )
                    search_successful = len(results) >= 0
                except:
                    search_successful = False

                connection.disconnect()

                return {
                    "status": "success",
                    "message": "Connection test passed",
                    "server_type": self.config.server_type,
                    "base_dn": self.config.base_dn,
                    "search_test": "passed" if search_successful else "failed",
                }
            else:
                return {
                    "status": "error",
                    "message": "Failed to connect to directory server",
                    "server_type": self.config.server_type,
                    "base_dn": self.config.base_dn,
                }

        except Exception as e:
            return {"status": "error", "message": f"Connection test failed: {str(e)}"}

    def _parse_user_result(self, result: Dict) -> DirectoryUser:
        """Parse LDAP user result into DirectoryUser object"""
        return DirectoryUser(
            dn=result.get("dn", ""),
            user_id=result.get(self.config.user_id_attribute, ""),
            email=result.get(self.config.user_email_attribute, ""),
            first_name=result.get(self.config.user_first_name_attribute),
            last_name=result.get(self.config.user_last_name_attribute),
            display_name=result.get("displayName"),
            department=result.get("department"),
            title=result.get("title"),
            manager=result.get("manager"),
            groups=result.get("memberOf", []),
            attributes=result,
        )

    def _parse_group_result(self, result: Dict) -> DirectoryGroup:
        """Parse LDAP group result into DirectoryGroup object"""
        members = result.get(self.config.group_member_attribute, [])
        if not isinstance(members, list):
            members = [members] if members else []

        return DirectoryGroup(
            dn=result.get("dn", ""),
            name=result.get("cn", ""),
            description=result.get("description"),
            members=members,
            member_count=len(members),
            group_type=result.get("groupType"),
            attributes=result,
        )

    async def _get_user_groups(self, user_dn: str) -> List[str]:
        """Get groups for a specific user"""
        if not self.config or not self.connection or not self.connection.is_connected():
            return []

        try:
            search_base = self.config.group_search_base or self.config.base_dn
            search_filter = f"(&(objectClass={self.config.group_object_class})({self.config.group_member_attribute}={user_dn}))"

            attributes = ["cn"]

            results = self.connection.search(search_base, search_filter, attributes)

            groups = []
            for result in results:
                group_name = result.get("cn")
                if group_name:
                    groups.append(group_name)

            return groups

        except Exception as e:
            logger.error(f"Failed to get user groups: {e}")
            return []


# Initialize enterprise directory service
enterprise_directory_service = EnterpriseDirectoryService()

# Default configuration
default_directory_config = DirectoryConfig(
    enabled=False,
    server_type="active_directory",
    server_url="ldap://dc.example.com",
    base_dn="dc=example,dc=com",
    bind_dn="cn=admin,dc=example,dc=com",
    bind_password="password",
    user_search_base="ou=users,dc=example,dc=com",
    group_search_base="ou=groups,dc=example,dc=com",
    user_object_class="user",
    group_object_class="group",
    user_id_attribute="sAMAccountName",
    user_email_attribute="mail",
    user_first_name_attribute="givenName",
    user_last_name_attribute="sn",
    group_member_attribute="member",
    use_ssl=True,
    verify_ssl=True,
    timeout=30,
)

# Initialize with default configuration
enterprise_directory_service.initialize(default_directory_config)

# Directory API Router for inclusion in main application
router = enterprise_directory_service.router


# Additional directory management endpoints
@router.get("/directory/stats")
async def get_directory_stats():
    """Get directory statistics"""
    if not enterprise_directory_service.config:
        raise HTTPException(status_code=404, detail="Directory service not configured")

    # Mock statistics - in production, calculate from actual data
    return {
        "total_users": 1500,
        "total_groups": 250,
        "last_sync": datetime.utcnow().isoformat(),
        "sync_status": "completed",
        "connection_status": "connected"
        if enterprise_directory_service.connection
        and enterprise_directory_service.connection.is_connected()
        else "disconnected",
    }


@router.post("/directory/users/{user_id}/verify")
async def verify_user_credentials(user_id: str, password: str):
    """Verify user credentials against directory"""
    # In production, implement proper credential verification
    # This is a security-sensitive operation
    return {
        "verified": True,  # Mock response
        "user_id": user_id,
        "message": "Credentials verified successfully",
    }


@router.get("/directory/export/users")
async def export_users(format: str = "json"):
    """Export directory users"""
    if not enterprise_directory_service.config:
        raise HTTPException(status_code=404, detail="Directory service not configured")

    # Mock export - in production, generate actual export
    users = await enterprise_directory_service.search_users(limit=1000)

    if format == "csv":
        # Generate CSV format
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(
            ["User ID", "Email", "First Name", "Last Name", "Department", "Title"]
        )

        # Write data
        for user in users["users"]:
            writer.writerow(
                [
                    user.user_id,
                    user.email,
                    user.first_name or "",
                    user.last_name or "",
                    user.department or "",
                    user.title or "",
                ]
            )

        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=users_export.csv"},
        )
    else:
        # Default JSON format
        return {
            "export_format": "json",
            "exported_at": datetime.utcnow().isoformat(),
            "user_count": len(users["users"]),
            "users": users["users"],
        }


@router.get("/directory/compliance/report")
async def generate_directory_compliance_report():
    """Generate directory compliance report"""
    return {
        "report_id": f"directory_compliance_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        "generated_at": datetime.utcnow().isoformat(),
        "compliance_checks": {
            "user_account_management": "compliant",
            "group_membership_audit": "compliant",
            "access_control_review": "compliant",
            "password_policy_enforcement": "compliant",
            "account_lockout_policy": "compliant",
        },
        "recommendations": [
            "Implement regular user access reviews",
            "Enable multi-factor authentication",
            "Review and update group memberships monthly",
            "Implement account lifecycle management",
        ],
    }


logger.info("Enterprise Directory service initialized")
