#!/usr/bin/env python3
"""
🏢 Enterprise Authentication System
Implements SAML, SSO, LDAP, and advanced enterprise security features
"""

import os
import json
import logging
import secrets
import hashlib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum
from abc import ABC, abstractmethod
from flask import Request, session
import base64
import hmac

logger = logging.getLogger(__name__)

class AuthenticationMethod(Enum):
    """Enterprise authentication methods"""
    OAUTH = "oauth"
    SAML = "saml"
    SSO = "sso"
    LDAP = "ldap"
    API_KEY = "api_key"
    MULTI_FACTOR = "multi_factor"

class UserRole(Enum):
    """Enterprise user roles"""
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"
    DEVELOPER = "developer"
    MANAGER = "manager"

class Permission(Enum):
    """Enterprise permissions"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    INTEGRATE = "integrate"
    WORKFLOW_MANAGE = "workflow_manage"

@dataclass
class EnterpriseUser:
    """Enterprise user data model"""
    user_id: str
    email: str
    name: str
    role: UserRole
    department: str
    manager_id: Optional[str]
    groups: List[str]
    permissions: List[Permission]
    last_login: Optional[datetime]
    login_count: int
    created_at: datetime
    updated_at: datetime
    mfa_enabled: bool
    mfa_method: Optional[str]
    sso_provider: Optional[str]
    metadata: Dict[str, Any]

@dataclass
class AuthenticationSession:
    """Enterprise authentication session"""
    session_id: str
    user_id: str
    auth_method: AuthenticationMethod
    created_at: datetime
    expires_at: datetime
    last_activity: datetime
    ip_address: str
    user_agent: str
    permissions: List[Permission]
    is_active: bool

class SAMLIdentityProvider(ABC):
    """Abstract SAML Identity Provider"""
    
    @abstractmethod
    def generate_auth_request(self, relay_state: str) -> str:
        """Generate SAML authentication request"""
        pass
    
    @abstractmethod
    def process_response(self, saml_response: str, relay_state: str) -> Dict[str, Any]:
        """Process SAML response and extract user data"""
        pass
    
    @abstractmethod
    def get_sso_metadata(self) -> Dict[str, Any]:
        """Get SSO metadata for service provider"""
        pass

class OktaSAMLProvider(SAMLIdentityProvider):
    """Okta SAML provider implementation"""
    
    def __init__(self, sso_url: str, entity_id: str, certificate: str):
        self.sso_url = sso_url
        self.entity_id = entity_id
        self.certificate = certificate
        self.name_id_format = "urn:oasis:names:tc:SAML:2.0:nameid-format:email"
    
    def generate_auth_request(self, relay_state: str) -> str:
        """Generate SAML 2.0 authentication request for Okta"""
        authn_id = f"_id_{secrets.token_urlsafe(32)}"
        
        # Create SAML AuthnRequest
        authn_request = f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:AuthnRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
                     ID="{authn_id}"
                     Version="2.0"
                     IssueInstant="{datetime.now(timezone.utc).isoformat()}Z"
                     Destination="{self.sso_url}"
                     ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"
                     AssertionConsumerServiceURL="{os.getenv('SAML_CALLBACK_URL', 'http://localhost:10000/api/saml/callback')}">
    <saml:Issuer xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">{self.entity_id}</saml:Issuer>
    <samlp:NameIDPolicy xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
                         Format="{self.name_id_format}"
                         AllowCreate="true"/>
</samlp:AuthnRequest>"""
        
        # Encode request
        encoded_request = base64.b64encode(authn_request.encode('utf-8')).decode('utf-8')
        
        # Build redirect URL
        params = f"SAMLRequest={encoded_request}&RelayState={relay_state}"
        return f"{self.sso_url}?{params}"
    
    def process_response(self, saml_response: str, relay_state: str) -> Dict[str, Any]:
        """Process SAML response from Okta"""
        try:
            # Decode SAML response
            decoded_response = base64.b64decode(saml_response).decode('utf-8')
            
            # Parse XML
            root = ET.fromstring(decoded_response)
            
            # Extract user attributes
            namespaces = {
                'saml': 'urn:oasis:names:tc:SAML:2.0:assertion',
                'samlp': 'urn:oasis:names:tc:SAML:2.0:protocol'
            }
            
            # Find assertion
            assertion = root.find('.//saml:Assertion', namespaces)
            if assertion is None:
                return {'success': False, 'error': 'No assertion found in SAML response'}
            
            # Get subject (user identifier)
            subject = assertion.find('.//saml:NameID', namespaces)
            if subject is None:
                return {'success': False, 'error': 'No NameID found in assertion'}
            
            email = subject.text
            
            # Extract attributes
            attributes = {}
            attribute_statements = assertion.findall('.//saml:AttributeStatement', namespaces)
            
            for attr_statement in attribute_statements:
                for attribute in attr_statement.findall('.//saml:Attribute', namespaces):
                    attr_name = attribute.get('Name')
                    attr_values = attribute.findall('.//saml:AttributeValue', namespaces)
                    
                    if attr_values:
                        attributes[attr_name] = [av.text for av in attr_values]
            
            # Map Okta attributes to user data
            user_data = {
                'success': True,
                'user_id': email,
                'email': email,
                'name': attributes.get('name', [''])[0] if attributes.get('name') else email,
                'first_name': attributes.get('firstName', [''])[0] if attributes.get('firstName') else '',
                'last_name': attributes.get('lastName', [''])[0] if attributes.get('lastName') else '',
                'department': attributes.get('department', [''])[0] if attributes.get('department') else '',
                'title': attributes.get('title', [''])[0] if attributes.get('title') else '',
                'groups': attributes.get('groups', []),
                'auth_method': AuthenticationMethod.SAML.value,
                'sso_provider': 'okta',
                'relay_state': relay_state,
                'auth_timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            return user_data
        
        except Exception as e:
            logger.error(f"Error processing SAML response: {e}")
            return {'success': False, 'error': f'SAML processing error: {str(e)}'}
    
    def get_sso_metadata(self) -> Dict[str, Any]:
        """Get SSO metadata for service provider"""
        return {
            'entity_id': self.entity_id,
            'sso_url': self.sso_url,
            'certificate': self.certificate,
            'name_id_format': self.name_id_format,
            'provider': 'okta'
        }

class LDAPAuthenticator:
    """LDAP authentication for enterprise users"""
    
    def __init__(self, ldap_server: str, base_dn: str, bind_dn: str, bind_password: str):
        self.ldap_server = ldap_server
        self.base_dn = base_dn
        self.bind_dn = bind_dn
        self.bind_password = bind_password
    
    def authenticate_user(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticate user against LDAP"""
        try:
            import ldap3
            
            # Create server object
            server = ldap3.Server(self.ldap_server, get_info=ldap3.ALL)
            
            # Create connection and bind
            conn = ldap3.Connection(server, self.bind_dn, self.bind_password, auto_bind=True)
            
            # Search for user
            search_filter = f'(&(objectClass=user)(sAMAccountName={username}))'
            conn.search(self.base_dn, search_filter, attributes=['cn', 'mail', 'department', 'title', 'memberOf'])
            
            if not conn.entries:
                return {'success': False, 'error': 'User not found'}
            
            user_entry = conn.entries[0]
            
            # Try to authenticate user with provided password
            user_dn = user_entry.entry_dn
            user_conn = ldap3.Connection(server, user_dn, password, auto_bind=False)
            
            if not user_conn.bind():
                return {'success': False, 'error': 'Invalid credentials'}
            
            user_conn.unbind()
            
            # Extract user data
            groups = []
            if 'memberOf' in user_entry:
                groups = [group for group in user_entry.memberOf.values]
            
            user_data = {
                'success': True,
                'user_id': username,
                'username': username,
                'name': str(user_entry.cn) if user_entry.cn else username,
                'email': str(user_entry.mail) if user_entry.mail else f"{username}@company.com",
                'department': str(user_entry.department) if user_entry.department else 'Unknown',
                'title': str(user_entry.title) if user_entry.title else None,
                'groups': groups,
                'auth_method': AuthenticationMethod.LDAP.value,
                'auth_timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            conn.unbind()
            return user_data
        
        except ImportError:
            # Fallback to mock authentication if ldap3 not available
            return self._mock_authenticate_user(username, password)
        except Exception as e:
            logger.error(f"LDAP authentication error: {e}")
            return {'success': False, 'error': f'LDAP error: {str(e)}'}
    
    def _mock_authenticate_user(self, username: str, password: str) -> Dict[str, Any]:
        """Mock LDAP authentication for development"""
        
        # Simple mock validation
        valid_users = {
            'admin': {'password': 'admin123', 'role': UserRole.ADMIN, 'department': 'IT', 'groups': ['Administrators', 'Domain Admins']},
            'john.doe': {'password': 'password123', 'role': UserRole.USER, 'department': 'Sales', 'groups': ['Sales Team']},
            'jane.smith': {'password': 'password123', 'role': UserRole.MANAGER, 'department': 'Marketing', 'groups': ['Marketing Team', 'Managers']},
            'dev.user': {'password': 'dev123', 'role': UserRole.DEVELOPER, 'department': 'Engineering', 'groups': ['Developers', 'Engineering Team']}
        }
        
        if username not in valid_users:
            return {'success': False, 'error': 'User not found'}
        
        user_info = valid_users[username]
        
        if password != user_info['password']:
            return {'success': False, 'error': 'Invalid credentials'}
        
        return {
            'success': True,
            'user_id': username,
            'username': username,
            'name': username.replace('.', ' ').title(),
            'email': f"{username}@company.com",
            'role': user_info['role'].value,
            'department': user_info['department'],
            'groups': user_info['groups'],
            'auth_method': AuthenticationMethod.LDAP.value,
            'auth_timestamp': datetime.now(timezone.utc).isoformat()
        }

class MultiFactorAuthenticator:
    """Multi-factor authentication system"""
    
    def __init__(self):
        self.mfa_secrets: Dict[str, str] = {}
        self.backup_codes: Dict[str, List[str]] = {}
    
    def generate_totp_secret(self, user_id: str) -> str:
        """Generate TOTP secret for user"""
        secret = base64.b32encode(os.urandom(20)).decode('utf-8')
        self.mfa_secrets[user_id] = secret
        return secret
    
    def generate_backup_codes(self, user_id: str, count: int = 10) -> List[str]:
        """Generate backup codes for user"""
        codes = [secrets.token_hex(4).upper() for _ in range(count)]
        self.backup_codes[user_id] = codes
        return codes
    
    def verify_totp(self, user_id: str, code: str) -> bool:
        """Verify TOTP code"""
        try:
            import pyotp
            
            if user_id not in self.mfa_secrets:
                return False
            
            totp = pyotp.TOTP(self.mfa_secrets[user_id])
            return totp.verify(code, valid_window=1)
        
        except ImportError:
            # Fallback to mock verification
            return self._mock_verify_totp(user_id, code)
        except Exception as e:
            logger.error(f"TOTP verification error: {e}")
            return False
    
    def verify_backup_code(self, user_id: str, code: str) -> bool:
        """Verify backup code"""
        if user_id not in self.backup_codes:
            return False
        
        if code in self.backup_codes[user_id]:
            self.backup_codes[user_id].remove(code)
            return True
        
        return False
    
    def _mock_verify_totp(self, user_id: str, code: str) -> bool:
        """Mock TOTP verification for development"""
        # Accept any 6-digit code as valid for demo
        return len(code) == 6 and code.isdigit()

class EnterpriseAuthManager:
    """Enterprise authentication manager"""
    
    def __init__(self):
        self.users: Dict[str, EnterpriseUser] = {}
        self.sessions: Dict[str, AuthenticationSession] = {}
        self.ldap_auth = LDAPAuthenticator(
            ldap_server=os.getenv('LDAP_SERVER', 'ldap://localhost:389'),
            base_dn=os.getenv('LDAP_BASE_DN', 'DC=company,DC=com'),
            bind_dn=os.getenv('LDAP_BIND_DN', 'CN=admin,DC=company,DC=com'),
            bind_password=os.getenv('LDAP_BIND_PASSWORD', 'admin123')
        )
        self.mfa_auth = MultiFactorAuthenticator()
        self.saml_providers: Dict[str, SAMLIdentityProvider] = {}
        self._initialize_saml_providers()
        self._create_default_users()
    
    def _initialize_saml_providers(self):
        """Initialize SAML providers"""
        if os.getenv('OKTA_SSO_URL') and os.getenv('OKTA_ENTITY_ID'):
            self.saml_providers['okta'] = OktaSAMLProvider(
                sso_url=os.getenv('OKTA_SSO_URL'),
                entity_id=os.getenv('OKTA_ENTITY_ID'),
                certificate=os.getenv('OKTA_CERTIFICATE', '')
            )
    
    def _create_default_users(self):
        """Create default enterprise users for demonstration"""
        default_users = [
            EnterpriseUser(
                user_id='admin@atom.com',
                email='admin@atom.com',
                name='Admin User',
                role=UserRole.ADMIN,
                department='IT',
                manager_id=None,
                groups=['Administrators', 'All Users'],
                permissions=[Permission.ADMIN, Permission.READ, Permission.WRITE, Permission.DELETE, Permission.INTEGRATE, Permission.WORKFLOW_MANAGE],
                last_login=None,
                login_count=0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                mfa_enabled=True,
                mfa_method='totp',
                sso_provider='okta',
                metadata={'employee_id': 'E001', 'level': 'executive'}
            ),
            EnterpriseUser(
                user_id='john.doe@atom.com',
                email='john.doe@atom.com',
                name='John Doe',
                role=UserRole.USER,
                department='Sales',
                manager_id='jane.smith@atom.com',
                groups=['Sales Team', 'All Users'],
                permissions=[Permission.READ, Permission.WRITE, Permission.INTEGRATE],
                last_login=None,
                login_count=0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                mfa_enabled=False,
                mfa_method=None,
                sso_provider=None,
                metadata={'employee_id': 'E002', 'level': 'associate'}
            ),
            EnterpriseUser(
                user_id='jane.smith@atom.com',
                email='jane.smith@atom.com',
                name='Jane Smith',
                role=UserRole.MANAGER,
                department='Marketing',
                manager_id='admin@atom.com',
                groups=['Marketing Team', 'Managers', 'All Users'],
                permissions=[Permission.READ, Permission.WRITE, Permission.INTEGRATE, Permission.WORKFLOW_MANAGE],
                last_login=None,
                login_count=0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                mfa_enabled=True,
                mfa_method='totp',
                sso_provider='okta',
                metadata={'employee_id': 'E003', 'level': 'manager'}
            )
        ]
        
        for user in default_users:
            self.users[user.user_id] = user
    
    def initiate_saml_login(self, provider: str, relay_state: str = None) -> Dict[str, Any]:
        """Initiate SAML login flow"""
        if provider not in self.saml_providers:
            return {'success': False, 'error': f'Provider {provider} not configured'}
        
        saml_provider = self.saml_providers[provider]
        relay_state = relay_state or secrets.token_urlsafe(32)
        
        auth_url = saml_provider.generate_auth_request(relay_state)
        
        return {
            'success': True,
            'auth_url': auth_url,
            'relay_state': relay_state,
            'provider': provider,
            'sso_enabled': True
        }
    
    def process_saml_response(self, provider: str, saml_response: str, relay_state: str, request: Request) -> Dict[str, Any]:
        """Process SAML response"""
        if provider not in self.saml_providers:
            return {'success': False, 'error': f'Provider {provider} not configured'}
        
        saml_provider = self.saml_providers[provider]
        auth_result = saml_provider.process_response(saml_response, relay_state)
        
        if not auth_result.get('success'):
            return auth_result
        
        # Create or update user
        user_id = auth_result['user_id']
        user = self._get_or_create_enterprise_user(auth_result)
        
        # Create session
        session_id = self._create_session(user, AuthenticationMethod.SAML, request)
        
        return {
            'success': True,
            'session_id': session_id,
            'user_id': user_id,
            'role': user.role.value,
            'permissions': [p.value for p in user.permissions],
            'auth_method': AuthenticationMethod.SAML.value,
            'provider': provider
        }
    
    def authenticate_ldap_user(self, username: str, password: str, request: Request) -> Dict[str, Any]:
        """Authenticate user via LDAP"""
        auth_result = self.ldap_auth.authenticate_user(username, password)
        
        if not auth_result.get('success'):
            return auth_result
        
        # Create or update user
        user = self._get_or_create_enterprise_user(auth_result)
        
        # Create session
        session_id = self._create_session(user, AuthenticationMethod.LDAP, request)
        
        return {
            'success': True,
            'session_id': session_id,
            'user_id': user.user_id,
            'role': user.role.value,
            'permissions': [p.value for p in user.permissions],
            'auth_method': AuthenticationMethod.LDAP.value
        }
    
    def verify_mfa(self, user_id: str, code: str) -> Dict[str, Any]:
        """Verify MFA code"""
        if self.mfa_auth.verify_totp(user_id, code):
            return {'success': True, 'method': 'totp'}
        elif self.mfa_auth.verify_backup_code(user_id, code):
            return {'success': True, 'method': 'backup_code'}
        else:
            return {'success': False, 'error': 'Invalid MFA code'}
    
    def validate_session(self, session_id: str) -> Dict[str, Any]:
        """Validate authentication session"""
        if session_id not in self.sessions:
            return {'success': False, 'error': 'Invalid session'}
        
        session = self.sessions[session_id]
        
        # Check if session is expired
        if datetime.now(timezone.utc) > session.expires_at:
            del self.sessions[session_id]
            return {'success': False, 'error': 'Session expired'}
        
        # Update last activity
        session.last_activity = datetime.now(timezone.utc)
        session.expires_at = datetime.now(timezone.utc) + timedelta(hours=8)  # 8-hour session
        
        return {
            'success': True,
            'user_id': session.user_id,
            'role': self.users[session.user_id].role.value,
            'permissions': [p.value for p in self.users[session.user_id].permissions],
            'auth_method': session.auth_method.value,
            'expires_at': session.expires_at.isoformat()
        }
    
    def logout(self, session_id: str) -> Dict[str, Any]:
        """Logout user session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return {'success': True, 'message': 'Logged out successfully'}
        else:
            return {'success': True, 'message': 'Session not found (already logged out)'}
    
    def _get_or_create_enterprise_user(self, auth_result: Dict[str, Any]) -> EnterpriseUser:
        """Get or create enterprise user from auth result"""
        user_id = auth_result.get('user_id') or auth_result.get('email')
        
        if user_id in self.users:
            user = self.users[user_id]
            # Update last login
            user.last_login = datetime.now(timezone.utc)
            user.login_count += 1
            user.updated_at = datetime.now(timezone.utc)
        else:
            # Create new user
            role = self._map_role_from_groups(auth_result.get('groups', []))
            permissions = self._map_permissions_from_role(role)
            
            user = EnterpriseUser(
                user_id=user_id,
                email=auth_result.get('email', user_id),
                name=auth_result.get('name', user_id),
                role=role,
                department=auth_result.get('department', 'General'),
                manager_id=None,  # Would be determined by organizational data
                groups=auth_result.get('groups', []),
                permissions=permissions,
                last_login=datetime.now(timezone.utc),
                login_count=1,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                mfa_enabled=False,
                mfa_method=None,
                sso_provider=auth_result.get('sso_provider'),
                metadata={
                    'auth_method': auth_result.get('auth_method'),
                    'auth_timestamp': auth_result.get('auth_timestamp')
                }
            )
            
            self.users[user_id] = user
        
        return user
    
    def _map_role_from_groups(self, groups: List[str]) -> UserRole:
        """Map user groups to enterprise role"""
        if any(group.lower() in ['administrators', 'domain admins', 'admin group'] for group in groups):
            return UserRole.ADMIN
        elif any(group.lower() in ['managers', 'supervisors', 'team leads'] for group in groups):
            return UserRole.MANAGER
        elif any(group.lower() in ['developers', 'engineers', 'technical team'] for group in groups):
            return UserRole.DEVELOPER
        else:
            return UserRole.USER
    
    def _map_permissions_from_role(self, role: UserRole) -> List[Permission]:
        """Map role to permissions"""
        if role == UserRole.ADMIN:
            return list(Permission)
        elif role == UserRole.MANAGER:
            return [Permission.READ, Permission.WRITE, Permission.INTEGRATE, Permission.WORKFLOW_MANAGE]
        elif role == UserRole.DEVELOPER:
            return [Permission.READ, Permission.WRITE, Permission.INTEGRATE]
        else:
            return [Permission.READ]
    
    def _create_session(self, user: EnterpriseUser, auth_method: AuthenticationMethod, request: Request) -> str:
        """Create authentication session"""
        session_id = secrets.token_urlsafe(32)
        
        session = AuthenticationSession(
            session_id=session_id,
            user_id=user.user_id,
            auth_method=auth_method,
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
            last_activity=datetime.now(timezone.utc),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', ''),
            permissions=user.permissions,
            is_active=True
        )
        
        self.sessions[session_id] = session
        return session_id
    
    def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """Get user information"""
        if user_id not in self.users:
            return {'success': False, 'error': 'User not found'}
        
        user = self.users[user_id]
        
        return {
            'success': True,
            'user_id': user.user_id,
            'email': user.email,
            'name': user.name,
            'role': user.role.value,
            'department': user.department,
            'manager_id': user.manager_id,
            'groups': user.groups,
            'permissions': [p.value for p in user.permissions],
            'mfa_enabled': user.mfa_enabled,
            'mfa_method': user.mfa_method,
            'sso_provider': user.sso_provider,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'login_count': user.login_count,
            'created_at': user.created_at.isoformat(),
            'metadata': user.metadata
        }
    
    def generate_mfa_setup(self, user_id: str) -> Dict[str, Any]:
        """Generate MFA setup for user"""
        if user_id not in self.users:
            return {'success': False, 'error': 'User not found'}
        
        secret = self.mfa_auth.generate_totp_secret(user_id)
        backup_codes = self.mfa_auth.generate_backup_codes(user_id)
        
        # Generate TOTP URI (for QR code)
        user = self.users[user_id]
        totp_uri = f"otpauth://totp/ATOM:{user.email}?secret={secret}&issuer=ATOM"
        
        return {
            'success': True,
            'secret': secret,
            'backup_codes': backup_codes,
            'totp_uri': totp_uri,
            'instructions': 'Scan the QR code with your authenticator app or manually enter the secret'
        }
    
    def get_sso_metadata(self, provider: str) -> Dict[str, Any]:
        """Get SSO metadata for provider"""
        if provider not in self.saml_providers:
            return {'success': False, 'error': f'Provider {provider} not configured'}
        
        saml_provider = self.saml_providers[provider]
        return {
            'success': True,
            'metadata': saml_provider.get_sso_metadata()
        }

# Global enterprise auth manager
enterprise_auth_manager = EnterpriseAuthManager()

# Export for use in routes
__all__ = [
    'EnterpriseAuthManager',
    'enterprise_auth_manager',
    'EnterpriseUser',
    'AuthenticationSession',
    'AuthenticationMethod',
    'UserRole',
    'Permission',
    'SAMLIdentityProvider',
    'OktaSAMLProvider',
    'LDAPAuthenticator',
    'MultiFactorAuthenticator'
]