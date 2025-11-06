"""
Shopify Custom App Extensions
Custom app support and extensions for Shopify
"""

import json
import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

class AppExtensionType(Enum):
    """Shopify app extension types"""
    PRODUCT_SUBSCRIPTION = "PRODUCT_SUBSCRIPTION"
    THEME_EXTENSION = "THEME_EXTENSION"
    BLOCK_EXTENSION = "BLOCK_EXTENSION"
    CHECKOUT_EXTENSION = "CHECKOUT_EXTENSION"
    POST_PURCHASE_EXTENSION = "POST_PURCHASE_EXTENSION"
    CUSTOMER_ACCOUNT_EXTENSION = "CUSTOMER_ACCOUNT_EXTENSION"

class AppPermission(Enum):
    """Shopify app permissions (scopes)"""
    # Store permissions
    READ_PRODUCTS = "read_products"
    WRITE_PRODUCTS = "write_products"
    READ_PRODUCT_LISTINGS = "read_product_listings"
    WRITE_PRODUCT_LISTINGS = "write_product_listings"
    READ_CUSTOMERS = "read_customers"
    WRITE_CUSTOMERS = "write_customers"
    READ_ORDERS = "read_orders"
    WRITE_ORDERS = "write_orders"
    READ_DRAFT_ORDERS = "read_draft_orders"
    WRITE_DRAFT_ORDERS = "write_draft_orders"
    READ_INVENTORY = "read_inventory"
    WRITE_INVENTORY = "write_inventory"
    READ_LOCATIONS = "read_locations"
    WRITE_LOCATIONS = "write_locations"
    READ_SCRIPT_TAGS = "read_script_tags"
    WRITE_SCRIPT_TAGS = "write_script_tags"
    READ_CONTENT = "read_content"
    WRITE_CONTENT = "write_content"
    READ_THEMES = "read_themes"
    WRITE_THEMES = "write_themes"
    READ_PRICE_RULES = "read_price_rules"
    WRITE_PRICE_RULES = "write_price_rules"
    READ_DISCOUNTS = "read_discounts"
    WRITE_DISCOUNTS = "write_discounts"
    READ_SHIPPING = "read_shipping"
    WRITE_SHIPPING = "write_shipping"
    READ_ANALYTICS = "read_analytics"
    READ_CHECKOUTS = "read_checkouts"
    WRITE_CHECKOUTS = "write_checkouts"
    READ_REPORTS = "read_reports"
    WRITE_REPORTS = "write_reports"
    
    # Admin permissions
    READ_ALL_ORDERS = "read_all_orders"
    READ_USERS = "read_users"
    WRITE_USERS = "write_users"
    
    # Developer permissions
    UNINSTALLED_READ_WEBHOOKS = "uninstalled_read_webhooks"
    
    # Partner permissions
    READ_ORGANIZATION = "read_organization"
    READ_ORGANIZATIONS = "read_organizations"
    WRITE_ORGANIZATIONS = "write_organizations"
    READ_APPS = "read_apps"
    WRITE_APPS = "write_apps"
    READ_DEVICES = "read_devices"
    WRITE_DEVICES = "write_devices"

@dataclass
class ShopifyCustomApp:
    """Shopify custom app model"""
    id: Optional[str] = None
    name: str = ""
    app_url: str = ""
    redirect_urls: List[str] = field(default_factory=list)
    permissions: List[AppPermission] = field(default_factory=list)
    webhook_url: Optional[str] = None
    webhook_topics: List[str] = field(default_factory=list)
    public_url: Optional[str] = None
    embedded: bool = True
    pos: bool = False
    plan_name: Optional[str] = None
    app_integration_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    api_key: Optional[str] = None
    api_secret_key: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    extensions: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class AppExtension:
    """App extension model"""
    id: Optional[str] = None
    app_id: Optional[str] = None
    title: str = ""
    extension_type: AppExtensionType = AppExtensionType.PRODUCT_SUBSCRIPTION
    uuid: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    development_store_id: Optional[str] = None
    registration_id: Optional[str] = None
    draft_version: Dict[str, Any] = field(default_factory=dict)
    version: Dict[str, Any] = field(default_factory=dict)
    configuration: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AppInstallation:
    """App installation model"""
    id: str
    app_id: str
    shop_domain: str
    access_token: str
    token_expires_at: Optional[datetime]
    granted_scopes: List[str] = field(default_factory=list)
    installed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class ShopifyCustomApps:
    """Shopify custom apps and extensions management"""
    
    def __init__(self, shopify_service, db_pool=None):
        self.shopify_service = shopify_service
        self.db_pool = db_pool
        self.apps_cache: Dict[str, ShopifyCustomApp] = {}
        self.installations_cache: Dict[str, AppInstallation] = {}
    
    async def create_custom_app(
        self,
        user_id: str,
        app_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create custom Shopify app"""
        try:
            app = ShopifyCustomApp(
                name=app_data.get("name"),
                app_url=app_data.get("app_url"),
                redirect_urls=app_data.get("redirect_urls", []),
                permissions=[
                    AppPermission(scope) for scope in app_data.get("permissions", [])
                ],
                webhook_url=app_data.get("webhook_url"),
                webhook_topics=app_data.get("webhook_topics", []),
                public_url=app_data.get("public_url"),
                embedded=app_data.get("embedded", True),
                pos=app_data.get("pos", False),
                plan_name=app_data.get("plan_name")
            )
            
            # Generate API keys and secrets
            app.api_key = self._generate_api_key()
            app.api_secret_key = self._generate_api_secret()
            app.client_id = app.api_key
            app.client_secret = app.api_secret_key
            
            # Create app via Shopify API
            result = await self._create_app_via_api(user_id, app)
            
            if result.get("success"):
                # Update app with API response data
                app.id = result.get("app", {}).get("id")
                app.app_integration_id = result.get("app", {}).get("app_integration_id")
                app.created_at = datetime.now(timezone.utc)
                app.updated_at = datetime.now(timezone.utc)
                
                # Store in cache
                self.apps_cache[app.id] = app
                
                # Store in database
                if self.db_pool:
                    await self._store_app_in_db(app)
                
                return {
                    "success": True,
                    "app": self._app_to_dict(app)
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Error creating custom app: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _create_app_via_api(
        self, 
        user_id: str, 
        app: ShopifyCustomApp
    ) -> Dict[str, Any]:
        """Create app via Shopify API"""
        try:
            app_data = {
                "app": {
                    "name": app.name,
                    "app_url": app.app_url,
                    "redirect_url_whitelist": app.redirect_urls,
                    "requested_scopes": [perm.value for perm in app.permissions],
                    "embedded": app.embedded,
                    "pos": app.pos
                }
            }
            
            if app.webhook_url:
                app_data["webhook_url"] = app.webhook_url
            
            if app.webhook_topics:
                app_data["webhook_topics"] = app.webhook_topics
            
            # Use Shopify service to create app
            response = await self.shopify_service._make_request(
                user_id=user_id,
                method="POST",
                endpoint="apps.json",
                data=app_data
            )
            
            if "app" in response:
                return {
                    "success": True,
                    "app": response["app"]
                }
            else:
                return {
                    "success": False,
                    "error": response.get("errors", "Unknown error")
                }
                
        except Exception as e:
            logger.error(f"Error creating app via API: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_custom_apps(self, user_id: str) -> List[Dict[str, Any]]:
        """Get custom apps for user"""
        try:
            response = await self.shopify_service._make_request(
                user_id=user_id,
                method="GET",
                endpoint="apps.json"
            )
            
            if "apps" in response:
                apps = []
                for app_data in response["apps"]:
                    # Convert to CustomApp model
                    app = self._dict_to_app(app_data)
                    self.apps_cache[app.id] = app
                    apps.append(self._app_to_dict(app))
                
                return apps
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting custom apps: {e}")
            return []
    
    async def create_app_extension(
        self,
        user_id: str,
        app_id: str,
        extension_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create app extension"""
        try:
            extension = AppExtension(
                app_id=app_id,
                title=extension_data.get("title"),
                extension_type=AppExtensionType(extension_data.get("type", "PRODUCT_SUBSCRIPTION")),
                uuid=self._generate_uuid(),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                configuration=extension_data.get("configuration", {})
            )
            
            # Create extension via Shopify API
            result = await self._create_extension_via_api(user_id, extension)
            
            if result.get("success"):
                extension.id = result.get("extension", {}).get("id")
                extension.registration_id = result.get("extension", {}).get("registration_id")
                extension.development_store_id = result.get("extension", {}).get("development_store_id")
                
                # Add to app extensions
                if app_id in self.apps_cache:
                    self.apps_cache[app_id].extensions.append(self._extension_to_dict(extension))
                
                # Store in database
                if self.db_pool:
                    await self._store_extension_in_db(extension)
                
                return {
                    "success": True,
                    "extension": self._extension_to_dict(extension)
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Error creating app extension: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _create_extension_via_api(
        self,
        user_id: str,
        extension: AppExtension
    ) -> Dict[str, Any]:
        """Create extension via Shopify API"""
        try:
            extension_data = {
                "extension": {
                    "title": extension.title,
                    "type": extension.extension_type.value,
                    "uuid": extension.uuid,
                    "draft_version": extension.draft_version,
                    "configuration": extension.configuration
                }
            }
            
            response = await self.shopify_service._make_request(
                user_id=user_id,
                method="POST",
                endpoint=f"apps/{extension.app_id}/extensions.json",
                data=extension_data
            )
            
            if "extension" in response:
                return {
                    "success": True,
                    "extension": response["extension"]
                }
            else:
                return {
                    "success": False,
                    "error": response.get("errors", "Unknown error")
                }
                
        except Exception as e:
            logger.error(f"Error creating extension via API: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def install_app(
        self,
        user_id: str,
        app_id: str,
        shop_domain: str,
        granted_scopes: List[str]
    ) -> Dict[str, Any]:
        """Install app on shop"""
        try:
            # Generate installation token
            access_token = self._generate_access_token()
            token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
            
            installation = AppInstallation(
                id=self._generate_uuid(),
                app_id=app_id,
                shop_domain=shop_domain,
                access_token=access_token,
                token_expires_at=token_expires_at,
                granted_scopes=granted_scopes
            )
            
            # Store installation
            self.installations_cache[installation.id] = installation
            
            # Store in database
            if self.db_pool:
                await self._store_installation_in_db(installation)
            
            return {
                "success": True,
                "installation": self._installation_to_dict(installation)
            }
            
        except Exception as e:
            logger.error(f"Error installing app: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_app_installations(
        self,
        user_id: str,
        app_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get app installations"""
        try:
            if self.db_pool:
                # Get from database
                installations = await self._get_installations_from_db(user_id, app_id)
            else:
                # Get from cache
                installations = list(self.installations_cache.values())
                
                # Filter by app_id if provided
                if app_id:
                    installations = [inst for inst in installations if inst.app_id == app_id]
            
            return [self._installation_to_dict(inst) for inst in installations]
            
        except Exception as e:
            logger.error(f"Error getting app installations: {e}")
            return []
    
    async def update_app_permissions(
        self,
        user_id: str,
        app_id: str,
        permissions: List[AppPermission]
    ) -> Dict[str, Any]:
        """Update app permissions"""
        try:
            app = self.apps_cache.get(app_id)
            if not app:
                return {
                    "success": False,
                    "error": "App not found"
                }
            
            old_permissions = app.permissions
            app.permissions = permissions
            
            # Update via API
            response = await self.shopify_service._make_request(
                user_id=user_id,
                method="PUT",
                endpoint=f"apps/{app_id}.json",
                data={
                    "app": {
                        "requested_scopes": [perm.value for perm in permissions]
                    }
                }
            )
            
            if "app" in response:
                app.updated_at = datetime.now(timezone.utc)
                
                # Update in database
                if self.db_pool:
                    await self._update_app_in_db(app)
                
                return {
                    "success": True,
                    "app": self._app_to_dict(app)
                }
            else:
                # Revert permissions on failure
                app.permissions = old_permissions
                return {
                    "success": False,
                    "error": response.get("errors", "Unknown error")
                }
                
        except Exception as e:
            logger.error(f"Error updating app permissions: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _generate_api_key(self) -> str:
        """Generate API key"""
        return f"app_{secrets.token_urlsafe(16)}"
    
    def _generate_api_secret(self) -> str:
        """Generate API secret"""
        return secrets.token_urlsafe(32)
    
    def _generate_access_token(self) -> str:
        """Generate access token"""
        return f"shpat_{secrets.token_urlsafe(24)}"
    
    def _generate_uuid(self) -> str:
        """Generate UUID"""
        return secrets.token_urlsafe(32)
    
    def _app_to_dict(self, app: ShopifyCustomApp) -> Dict[str, Any]:
        """Convert app to dictionary"""
        return {
            "id": app.id,
            "name": app.name,
            "app_url": app.app_url,
            "redirect_urls": app.redirect_urls,
            "permissions": [perm.value for perm in app.permissions],
            "webhook_url": app.webhook_url,
            "webhook_topics": app.webhook_topics,
            "public_url": app.public_url,
            "embedded": app.embedded,
            "pos": app.pos,
            "plan_name": app.plan_name,
            "app_integration_id": app.app_integration_id,
            "client_id": app.client_id,
            "extensions": app.extensions,
            "created_at": app.created_at.isoformat() if app.created_at else None,
            "updated_at": app.updated_at.isoformat() if app.updated_at else None
        }
    
    def _dict_to_app(self, app_data: Dict[str, Any]) -> ShopifyCustomApp:
        """Convert dictionary to app"""
        return ShopifyCustomApp(
            id=app_data.get("id"),
            name=app_data.get("name", ""),
            app_url=app_data.get("app_url", ""),
            redirect_urls=app_data.get("redirect_url_whitelist", []),
            permissions=[
                AppPermission(scope) for scope in app_data.get("requested_scopes", [])
            ],
            webhook_url=app_data.get("webhook_url"),
            webhook_topics=app_data.get("webhook_topics", []),
            public_url=app_data.get("public_url"),
            embedded=app_data.get("embedded", True),
            pos=app_data.get("pos", False),
            app_integration_id=app_data.get("app_integration_id"),
            client_id=app_data.get("client_id"),
            created_at=datetime.fromisoformat(app_data["created_at"].replace("Z", "+00:00")) if app_data.get("created_at") else None
        )
    
    def _extension_to_dict(self, extension: AppExtension) -> Dict[str, Any]:
        """Convert extension to dictionary"""
        return {
            "id": extension.id,
            "app_id": extension.app_id,
            "title": extension.title,
            "type": extension.extension_type.value,
            "uuid": extension.uuid,
            "development_store_id": extension.development_store_id,
            "registration_id": extension.registration_id,
            "draft_version": extension.draft_version,
            "configuration": extension.configuration,
            "created_at": extension.created_at.isoformat() if extension.created_at else None,
            "updated_at": extension.updated_at.isoformat() if extension.updated_at else None
        }
    
    def _installation_to_dict(self, installation: AppInstallation) -> Dict[str, Any]:
        """Convert installation to dictionary"""
        return {
            "id": installation.id,
            "app_id": installation.app_id,
            "shop_domain": installation.shop_domain,
            "granted_scopes": installation.granted_scopes,
            "installed_at": installation.installed_at.isoformat(),
            "updated_at": installation.updated_at.isoformat(),
            "token_expires_at": installation.token_expires_at.isoformat() if installation.token_expires_at else None
        }
    
    # Database operations (if db_pool is available)
    async def _store_app_in_db(self, app: ShopifyCustomApp):
        """Store app in database"""
        if not self.db_pool:
            return
        
        try:
            query = """
            INSERT INTO shopify_custom_apps (
                id, name, app_url, redirect_urls, permissions, webhook_url,
                webhook_topics, public_url, embedded, pos, plan_name,
                app_integration_id, client_id, client_secret, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                app_url = EXCLUDED.app_url,
                redirect_urls = EXCLUDED.redirect_urls,
                permissions = EXCLUDED.permissions,
                webhook_url = EXCLUDED.webhook_url,
                webhook_topics = EXCLUDED.webhook_topics,
                public_url = EXCLUDED.public_url,
                embedded = EXCLUDED.embedded,
                pos = EXCLUDED.pos,
                plan_name = EXCLUDED.plan_name,
                app_integration_id = EXCLUDED.app_integration_id,
                client_id = EXCLUDED.client_id,
                client_secret = EXCLUDED.client_secret,
                updated_at = EXCLUDED.updated_at
            """
            
            await self.db_pool.execute(
                query,
                app.id,
                app.name,
                app.app_url,
                json.dumps(app.redirect_urls),
                json.dumps([perm.value for perm in app.permissions]),
                app.webhook_url,
                json.dumps(app.webhook_topics),
                app.public_url,
                app.embedded,
                app.pos,
                app.plan_name,
                app.app_integration_id,
                app.client_id,
                app.client_secret,
                app.created_at,
                app.updated_at
            )
            
        except Exception as e:
            logger.error(f"Error storing app in database: {e}")
    
    async def _store_extension_in_db(self, extension: AppExtension):
        """Store extension in database"""
        if not self.db_pool:
            return
        
        try:
            query = """
            INSERT INTO shopify_app_extensions (
                id, app_id, title, type, uuid, development_store_id,
                registration_id, draft_version, configuration, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                type = EXCLUDED.type,
                draft_version = EXCLUDED.draft_version,
                configuration = EXCLUDED.configuration,
                updated_at = EXCLUDED.updated_at
            """
            
            await self.db_pool.execute(
                query,
                extension.id,
                extension.app_id,
                extension.title,
                extension.extension_type.value,
                extension.uuid,
                extension.development_store_id,
                extension.registration_id,
                json.dumps(extension.draft_version),
                json.dumps(extension.configuration),
                extension.created_at,
                extension.updated_at
            )
            
        except Exception as e:
            logger.error(f"Error storing extension in database: {e}")
    
    async def _store_installation_in_db(self, installation: AppInstallation):
        """Store installation in database"""
        if not self.db_pool:
            return
        
        try:
            query = """
            INSERT INTO shopify_app_installations (
                id, app_id, shop_domain, access_token, token_expires_at,
                granted_scopes, installed_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (id) DO UPDATE SET
                access_token = EXCLUDED.access_token,
                token_expires_at = EXCLUDED.token_expires_at,
                granted_scopes = EXCLUDED.granted_scopes,
                updated_at = EXCLUDED.updated_at
            """
            
            await self.db_pool.execute(
                query,
                installation.id,
                installation.app_id,
                installation.shop_domain,
                installation.access_token,
                installation.token_expires_at,
                json.dumps(installation.granted_scopes),
                installation.installed_at,
                installation.updated_at
            )
            
        except Exception as e:
            logger.error(f"Error storing installation in database: {e}")
    
    async def _get_installations_from_db(
        self,
        user_id: str,
        app_id: Optional[str] = None
    ) -> List[AppInstallation]:
        """Get installations from database"""
        if not self.db_pool:
            return []
        
        try:
            query = """
            SELECT id, app_id, shop_domain, access_token, token_expires_at,
                   granted_scopes, installed_at, updated_at
            FROM shopify_app_installations
            WHERE 1=1
            """
            params = []
            
            if app_id:
                query += " AND app_id = $1"
                params.append(app_id)
            
            rows = await self.db_pool.fetch(query, *params)
            
            installations = []
            for row in rows:
                installation = AppInstallation(
                    id=row["id"],
                    app_id=row["app_id"],
                    shop_domain=row["shop_domain"],
                    access_token=row["access_token"],
                    token_expires_at=row["token_expires_at"],
                    granted_scopes=json.loads(row["granted_scopes"]),
                    installed_at=row["installed_at"],
                    updated_at=row["updated_at"]
                )
                installations.append(installation)
            
            return installations
            
        except Exception as e:
            logger.error(f"Error getting installations from database: {e}")
            return []
    
    async def _update_app_in_db(self, app: ShopifyCustomApp):
        """Update app in database"""
        await self._store_app_in_db(app)

# Export components
__all__ = [
    "ShopifyCustomApps",
    "ShopifyCustomApp",
    "AppExtension",
    "AppInstallation",
    "AppPermission",
    "AppExtensionType"
]