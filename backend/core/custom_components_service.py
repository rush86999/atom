"""
Custom Canvas Components Service

Manages custom HTML/CSS/JS components for canvas presentations with:
- Component CRUD operations
- Version control and rollback
- Security sanitization (HTML, CSS, JS)
- Governance integration
- Usage tracking
"""

import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from core.models import (
    AgentExecution,
    AgentRegistry,
    CanvasAudit,
    ComponentUsage,
    ComponentVersion,
    CustomComponent,
    User,
)

logger = logging.getLogger(__name__)


class ComponentSecurityError(Exception):
    """Raised when component content fails security validation."""

    def __init__(self, message: str, component_name: str = "", validation_reason: str = ""):
        super().__init__(message)
        self.component_name = component_name
        self.validation_reason = validation_reason

    def __str__(self):
        msg = super().__str__()
        if self.component_name:
            msg += f" (Component: {self.component_name})"
        if self.validation_reason:
            msg += f" (Reason: {self.validation_reason})"
        return msg


class CustomComponentsService:
    """
    Service for managing custom canvas components.

    Provides secure CRUD operations for custom components with
    governance integration and audit logging.
    """

    # Allowed HTML tags (sanitization)
    ALLOWED_HTML_TAGS = {
        'div', 'span', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li', 'a', 'img', 'button', 'input', 'label',
        'select', 'option', 'textarea', 'form', 'table', 'tr', 'td', 'th',
        'thead', 'tbody', 'strong', 'em', 'code', 'pre', 'blockquote',
        'hr', 'br', 'svg', 'path', 'circle', 'rect', 'line', 'text',
        'canvas', 'video', 'audio', 'source', 'track'
    }

    # Dangerous JavaScript patterns to block
    BLOCKED_JS_PATTERNS = [
        r'eval\s*\(',
        r'Function\s*\(',
        r'document\.write',
        r'\.innerHTML\s*=',
        r'outerHTML\s*=',
        r'window\.location\s*=',
        r'\.src\s*=\s*["\']javascript:',
        r'setTimeout\s*\(\s*["\']',
        r'setInterval\s*\(\s*["\']',
        r'new\s+Function',
        r'__proto__',
        r'constructor\s*\[',
        r'<script',
    ]

    # Allowed external dependencies (whitelist)
    ALLOWED_DEPENDENCIES = [
        'https://cdn.jsdelivr.net/npm/*',
        'https://cdnjs.cloudflare.com/ajax/libs/*',
        'https://unpkg.com/*',
    ]

    def __init__(self, db: Session):
        self.db = db

    # ========================================================================
    # Component CRUD Operations
    # ========================================================================

    def create_component(
        self,
        user_id: str,
        name: str,
        html_content: str,
        css_content: Optional[str] = None,
        js_content: Optional[str] = None,
        description: Optional[str] = None,
        category: str = "custom",
        props_schema: Optional[Dict[str, Any]] = None,
        default_props: Optional[Dict[str, Any]] = None,
        dependencies: Optional[List[str]] = None,
        is_public: bool = False,
        agent_id: Optional[str] = None,
        agent_execution_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new custom component.

        Args:
            user_id: Owner user ID
            name: Component name
            html_content: HTML template
            css_content: Optional CSS styles
            js_content: Optional JavaScript behavior (AUTONOMOUS only)
            description: Component description
            category: Component category
            props_schema: JSON schema for component properties
            default_props: Default property values
            dependencies: External library dependencies
            is_public: Share with other users
            agent_id: Agent creating component (for governance)
            agent_execution_id: Execution record ID

        Returns:
            Created component data

        Raises:
            ComponentSecurityError: If content fails security validation
        """
        # Security checks
        if js_content:
            self._check_governance_for_js(agent_id)

        # Generate unique slug
        base_slug = self._slugify(name)
        slug = self._generate_unique_slug(base_slug)

        # Validate and sanitize content
        html_sanitized = self._sanitize_html(html_content)
        css_sanitized = self._sanitize_css(css_content) if css_content else None
        js_sanitized = self._validate_js(js_content) if js_content else None

        # Validate dependencies
        if dependencies:
            self._validate_dependencies(dependencies)

        # Create component
        component = CustomComponent(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            slug=slug,
            description=description,
            category=category,
            html_content=html_sanitized,
            css_content=css_sanitized,
            js_content=js_sanitized,
            props_schema=props_schema,
            default_props=default_props or {},
            dependencies=dependencies or [],
            is_public=is_public,
            requires_governance=True,
            min_maturity_level="AUTONOMOUS" if js_content else "SUPERVISED",
            current_version=1,
            usage_count=0,
            is_active=True
        )

        self.db.add(component)
        self.db.commit()
        self.db.refresh(component)

        # Create initial version
        version = ComponentVersion(
            id=str(uuid.uuid4()),
            component_id=component.id,
            version_number=1,
            html_content=html_sanitized,
            css_content=css_sanitized,
            js_content=js_sanitized,
            props_schema=props_schema,
            default_props=default_props or {},
            dependencies=dependencies or [],
            change_description=f"Initial version created by {user_id}",
            changed_by=user_id,
            change_type="create"
        )

        self.db.add(version)
        self.db.commit()

        logger.info(
            f"Created custom component '{name}' (ID: {component.id}, slug: {slug}) "
            f"with JS={'yes' if js_content else 'no'}"
        )

        return {
            "component_id": component.id,
            "name": component.name,
            "slug": component.slug,
            "description": component.description,
            "category": component.category,
            "html_content": component.html_content,
            "css_content": component.css_content,
            "has_js": bool(component.js_content),
            "is_public": component.is_public,
            "version": component.current_version,
            "created_at": component.created_at.isoformat()
        }

    def get_component(
        self,
        component_id: Optional[str] = None,
        slug: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get a component by ID or slug.

        Args:
            component_id: Component ID
            slug: Component slug (alternative lookup)
            user_id: User ID (for permission check)

        Returns:
            Component data
        """
        if not component_id and not slug:
            return {"error": "Either component_id or slug required"}

        # Build query
        query = self.db.query(CustomComponent).filter(
            CustomComponent.is_active == True
        )

        if component_id:
            query = query.filter(CustomComponent.id == component_id)
        else:
            query = query.filter(CustomComponent.slug == slug)

        component = query.first()

        if not component:
            return {"error": "Component not found"}

        # Check access permission
        if component.user_id != user_id and not component.is_public:
            return {"error": "Access denied: Component is private"}

        return {
            "component_id": component.id,
            "name": component.name,
            "slug": component.slug,
            "description": component.description,
            "category": component.category,
            "html_content": component.html_content,
            "css_content": component.css_content,
            "js_content": component.js_content if component.user_id == user_id else None,  # JS only for owner
            "props_schema": component.props_schema,
            "default_props": component.default_props,
            "dependencies": component.dependencies,
            "has_js": bool(component.js_content),
            "is_public": component.is_public,
            "version": component.current_version,
            "usage_count": component.usage_count,
            "created_at": component.created_at.isoformat(),
            "updated_at": component.updated_at.isoformat() if component.updated_at else None
        }

    def list_components(
        self,
        user_id: Optional[str] = None,
        category: Optional[str] = None,
        is_public: Optional[bool] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        List components with optional filtering.

        Args:
            user_id: User ID (to include private components)
            category: Filter by category
            is_public: Filter by public/private
            limit: Max results

        Returns:
            List of components
        """
        query = self.db.query(CustomComponent).filter(
            CustomComponent.is_active == True
        )

        # Filter by access: user's own components OR public components
        if user_id:
            query = query.filter(
                or_(
                    CustomComponent.user_id == user_id,
                    CustomComponent.is_public == True
                )
            )
        else:
            query = query.filter(CustomComponent.is_public == True)

        if category:
            query = query.filter(CustomComponent.category == category)

        if is_public is not None:
            query = query.filter(CustomComponent.is_public == is_public)

        components = query.order_by(
            desc(CustomComponent.usage_count),
            desc(CustomComponent.created_at)
        ).limit(limit).all()

        return {
            "total": len(components),
            "components": [
                {
                    "component_id": c.id,
                    "name": c.name,
                    "slug": c.slug,
                    "description": c.description,
                    "category": c.category,
                    "has_js": bool(c.js_content),
                    "is_public": c.is_public,
                    "is_owner": c.user_id == user_id if user_id else False,
                    "usage_count": c.usage_count,
                    "version": c.current_version,
                    "created_at": c.created_at.isoformat()
                }
                for c in components
            ]
        }

    def update_component(
        self,
        component_id: str,
        user_id: str,
        name: Optional[str] = None,
        html_content: Optional[str] = None,
        css_content: Optional[str] = None,
        js_content: Optional[str] = None,
        description: Optional[str] = None,
        props_schema: Optional[Dict[str, Any]] = None,
        default_props: Optional[Dict[str, Any]] = None,
        dependencies: Optional[List[str]] = None,
        is_public: Optional[bool] = None,
        change_description: Optional[str] = None,
        agent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update an existing component (creates new version).

        Args:
            component_id: Component to update
            user_id: User making the update
            ... (other fields same as create_component)
            change_description: Description of changes made

        Returns:
            Updated component data
        """
        component = self.db.query(CustomComponent).filter(
            CustomComponent.id == component_id
        ).first()

        if not component:
            return {"error": "Component not found"}

        # Check ownership
        if component.user_id != user_id:
            return {"error": "Access denied: Not component owner"}

        # Security checks for JS
        if js_content is not None and js_content != component.js_content:
            self._check_governance_for_js(agent_id)

        # Update fields
        if name:
            component.name = name

        if html_content is not None:
            component.html_content = self._sanitize_html(html_content)

        if css_content is not None:
            component.css_content = self._sanitize_css(css_content)

        if js_content is not None:
            component.js_content = self._validate_js(js_content)

        if description is not None:
            component.description = description

        if props_schema is not None:
            component.props_schema = props_schema

        if default_props is not None:
            component.default_props = default_props

        if dependencies is not None:
            self._validate_dependencies(dependencies)
            component.dependencies = dependencies

        if is_public is not None:
            component.is_public = is_public

        # Increment version
        component.current_version += 1
        component.updated_at = datetime.now()

        self.db.commit()

        # Create version record
        version = ComponentVersion(
            id=str(uuid.uuid4()),
            component_id=component.id,
            version_number=component.current_version,
            html_content=component.html_content,
            css_content=component.css_content,
            js_content=component.js_content,
            props_schema=component.props_schema,
            default_props=component.default_props,
            dependencies=component.dependencies,
            change_description=change_description or f"Updated to version {component.current_version}",
            changed_by=user_id,
            change_type="update"
        )

        self.db.add(version)
        self.db.commit()
        self.db.refresh(component)

        logger.info(
            f"Updated component '{component.name}' to version {component.current_version} "
            f"(ID: {component.id})"
        )

        return {
            "component_id": component.id,
            "name": component.name,
            "slug": component.slug,
            "version": component.current_version,
            "updated_at": component.updated_at.isoformat()
        }

    def delete_component(
        self,
        component_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Soft delete a component (sets is_active=False).

        Args:
            component_id: Component to delete
            user_id: User requesting deletion

        Returns:
            Deletion result
        """
        component = self.db.query(CustomComponent).filter(
            CustomComponent.id == component_id
        ).first()

        if not component:
            return {"error": "Component not found"}

        if component.user_id != user_id:
            return {"error": "Access denied: Not component owner"}

        component.is_active = False
        component.updated_at = datetime.now()
        self.db.commit()

        logger.info(f"Deleted component '{component.name}' (ID: {component_id})")

        return {
            "component_id": component_id,
            "status": "deleted"
        }

    # ========================================================================
    # Version Control
    # ========================================================================

    def get_component_versions(
        self,
        component_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get version history for a component.

        Args:
            component_id: Component ID
            user_id: User requesting (must be owner)

        Returns:
            List of versions
        """
        component = self.db.query(CustomComponent).filter(
            CustomComponent.id == component_id
        ).first()

        if not component:
            return {"error": "Component not found"}

        if component.user_id != user_id:
            return {"error": "Access denied: Not component owner"}

        versions = self.db.query(ComponentVersion).filter(
            ComponentVersion.component_id == component_id
        ).order_by(ComponentVersion.version_number.desc()).all()

        return {
            "component_id": component_id,
            "current_version": component.current_version,
            "total_versions": len(versions),
            "versions": [
                {
                    "version_number": v.version_number,
                    "change_description": v.change_description,
                    "change_type": v.change_type,
                    "created_at": v.created_at.isoformat()
                }
                for v in versions
            ]
        }

    def rollback_component(
        self,
        component_id: str,
        target_version: int,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Rollback component to a previous version.

        Args:
            component_id: Component to rollback
            target_version: Version number to restore
            user_id: User requesting rollback

        Returns:
            Rollback result
        """
        component = self.db.query(CustomComponent).filter(
            CustomComponent.id == component_id
        ).first()

        if not component:
            return {"error": "Component not found"}

        if component.user_id != user_id:
            return {"error": "Access denied: Not component owner"}

        # Get target version
        target = self.db.query(ComponentVersion).filter(
            and_(
                ComponentVersion.component_id == component_id,
                ComponentVersion.version_number == target_version
            )
        ).first()

        if not target:
            return {"error": "Target version not found"}

        # Restore content from target version
        component.html_content = target.html_content
        component.css_content = target.css_content
        component.js_content = target.js_content
        component.props_schema = target.props_schema
        component.default_props = target.default_props
        component.dependencies = target.dependencies
        component.current_version += 1
        component.updated_at = datetime.now()

        self.db.commit()

        # Create rollback version record
        rollback_version = ComponentVersion(
            id=str(uuid.uuid4()),
            component_id=component_id,
            version_number=component.current_version,
            html_content=target.html_content,
            css_content=target.css_content,
            js_content=target.js_content,
            props_schema=target.props_schema,
            default_props=target.default_props,
            dependencies=target.dependencies,
            change_description=f"Rollback to version {target_version}",
            changed_by=user_id,
            change_type="rollback"
        )

        self.db.add(rollback_version)
        self.db.commit()

        logger.info(
            f"Rolled back component '{component.name}' from version {target_version} "
            f"to new version {component.current_version}"
        )

        return {
            "component_id": component_id,
            "previous_version": target_version,
            "new_version": component.current_version,
            "status": "rolled_back"
        }

    # ========================================================================
    # Component Usage
    # ========================================================================

    def record_component_usage(
        self,
        component_id: str,
        canvas_id: str,
        user_id: str,
        session_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        props_passed: Optional[Dict[str, Any]] = None,
        rendering_time_ms: Optional[int] = None,
        error_message: Optional[str] = None,
        governance_check_passed: Optional[bool] = None,
        agent_maturity_level: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Record component usage on a canvas.

        Args:
            component_id: Component used
            canvas_id: Canvas where component was used
            user_id: User who rendered component
            session_id: Optional canvas session
            agent_id: Optional agent that rendered component
            props_passed: Properties passed to component
            rendering_time_ms: Rendering performance
            error_message: Any errors during rendering
            governance_check_passed: Governance check result
            agent_maturity_level: Agent maturity at time of usage

        Returns:
            Usage record
        """
        # Update component usage stats
        component = self.db.query(CustomComponent).filter(
            CustomComponent.id == component_id
        ).first()

        if component:
            component.usage_count += 1
            component.last_used_at = datetime.now()

        # Create usage record
        usage = ComponentUsage(
            id=str(uuid.uuid4()),
            component_id=component_id,
            canvas_id=canvas_id,
            session_id=session_id,
            user_id=user_id,
            agent_id=agent_id,
            props_passed=props_passed,
            rendering_time_ms=rendering_time_ms,
            error_message=error_message,
            governance_check_passed=governance_check_passed,
            agent_maturity_level=agent_maturity_level
        )

        self.db.add(usage)
        self.db.commit()

        return {
            "usage_id": usage.id,
            "component_id": component_id,
            "status": "recorded"
        }

    def get_component_usage_stats(
        self,
        component_id: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get usage statistics for a component.

        Args:
            component_id: Component ID
            user_id: User requesting stats (must be owner)

        Returns:
            Usage statistics
        """
        component = self.db.query(CustomComponent).filter(
            CustomComponent.id == component_id
        ).first()

        if not component:
            return {"error": "Component not found"}

        if component.user_id != user_id:
            return {"error": "Access denied: Not component owner"}

        # Get usage records
        usage_records = self.db.query(ComponentUsage).filter(
            ComponentUsage.component_id == component_id
        ).all()

        # Calculate stats
        total_renders = len(usage_records)
        successful_renders = sum(1 for u in usage_records if not u.error_message)
        avg_rendering_time = sum(
            u.rendering_time_ms for u in usage_records if u.rendering_time_ms
        ) / successful_renders if successful_renders > 0 else 0

        # Top canvases
        canvas_usage = {}
        for u in usage_records:
            canvas_usage[u.canvas_id] = canvas_usage.get(u.canvas_id, 0) + 1

        top_canvases = sorted(canvas_usage.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "component_id": component_id,
            "component_name": component.name,
            "total_renders": total_renders,
            "successful_renders": successful_renders,
            "failed_renders": total_renders - successful_renders,
            "success_rate": successful_renders / total_renders if total_renders > 0 else 0,
            "avg_rendering_time_ms": round(avg_rendering_time, 2),
            "top_canvases": [
                {"canvas_id": canvas_id, "render_count": count}
                for canvas_id, count in top_canvases
            ]
        }

    # ========================================================================
    # Security & Governance
    # ========================================================================

    def _check_governance_for_js(self, agent_id: Optional[str] = None):
        """
        Check if agent is allowed to create components with JavaScript.

        Only AUTONOMOUS agents can create components with JavaScript.

        Args:
            agent_id: Agent attempting to create JS component

        Raises:
            ComponentSecurityError: If agent is not AUTONOMOUS
        """
        if not agent_id:
            raise ComponentSecurityError(
                "JavaScript components require AUTONOMOUS agent. "
                "No agent provided."
            )

        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if not agent:
            raise ComponentSecurityError(f"Agent '{agent_id}' not found")

        if agent.status != "AUTONOMOUS":
            raise ComponentSecurityError(
                f"JavaScript components require AUTONOMOUS maturity level. "
                f"Agent '{agent.name}' is at {agent.status} level."
            )

    def _sanitize_html(self, html: str) -> str:
        """
        Sanitize HTML content to remove dangerous tags and attributes.

        Args:
            html: Raw HTML

        Returns:
            Sanitized HTML

        Raises:
            ComponentSecurityError: If HTML contains dangerous content
        """
        # Check for dangerous patterns
        dangerous_patterns = ['<script', 'javascript:', 'onerror=', 'onload=', 'onclick=']

        for pattern in dangerous_patterns:
            if pattern.lower() in html.lower():
                raise ComponentSecurityError(
                    f"HTML contains dangerous pattern: {pattern}"
                )

        # Basic sanitization (in production, use bleach or nh3)
        # For now, just validate structure
        return html

    def _sanitize_css(self, css: str) -> str:
        """
        Sanitize CSS content to remove dangerous rules.

        Args:
            css: Raw CSS

        Returns:
            Sanitized CSS

        Raises:
            ComponentSecurityError: If CSS contains dangerous content
        """
        if not css:
            return css

        # Check for dangerous CSS patterns
        dangerous_patterns = [
            'expression(',
            'javascript:',
            'behavior:url(',
            '-ms-binding',
        ]

        for pattern in dangerous_patterns:
            if pattern.lower() in css.lower():
                raise ComponentSecurityError(
                    f"CSS contains dangerous pattern: {pattern}"
                )

        return css

    def _validate_js(self, js: str) -> str:
        """
        Validate JavaScript content for security.

        Args:
            js: Raw JavaScript

        Returns:
            Validated JavaScript

        Raises:
            ComponentSecurityError: If JS contains dangerous patterns
        """
        if not js:
            return js

        # Check for blocked patterns
        for pattern in self.BLOCKED_JS_PATTERNS:
            if re.search(pattern, js, re.IGNORECASE):
                raise ComponentSecurityError(
                    f"JavaScript contains blocked pattern: {pattern}"
                )

        return js

    def _validate_dependencies(self, dependencies: List[str]):
        """
        Validate external dependencies against whitelist.

        Args:
            dependencies: List of dependency URLs

        Raises:
            ComponentSecurityError: If dependency not in whitelist
        """
        for dep in dependencies:
            # Check against whitelist patterns
            allowed = False
            for allowed_pattern in self.ALLOWED_DEPENDENCIES:
                # Convert glob pattern to regex
                pattern = allowed_pattern.replace('*', '.*')
                if re.match(pattern, dep):
                    allowed = True
                    break

            if not allowed:
                raise ComponentSecurityError(
                    f"Dependency '{dep}' not in allowed list. "
                    f"Allowed patterns: {self.ALLOWED_DEPENDENCIES}"
                )

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _slugify(self, text: str) -> str:
        """Convert text to URL-friendly slug."""
        # Convert to lowercase and replace spaces with hyphens
        slug = text.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug

    def _generate_unique_slug(self, base_slug: str) -> str:
        """Generate a unique slug by adding suffix if needed."""
        slug = base_slug
        counter = 1

        while self.db.query(CustomComponent).filter(
            CustomComponent.slug == slug
        ).first():
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug
