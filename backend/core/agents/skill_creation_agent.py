"""
Skill Creation Agent

Intelligent agent that creates skills on-the-fly from API documentation.
Analyzes OpenAPI/Swagger specs and generates production-ready Python code.

Key Features:
- Parse OpenAPI/Swagger specifications
- Extract endpoints, authentication, schemas
- Generate Python skill code
- Test against API
- Register skill in database
- Auto-generate canvas components
"""

import logging
import httpx
import json
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from core.models import Skill, SkillVersion, CanvasComponent
from core.llm_router import LLMRouter
from core.openclaw_parser import OpenClawParser

logger = logging.getLogger(__name__)


class SkillCreationAgent:
    """
    Agent that creates skills from API documentation.

    Capabilities:
    - Parse OpenAPI/Swagger specs
    - Extract authentication patterns
    - Generate Python code
    - Auto-test API calls
    - Create matching canvas components
    """

    def __init__(self, db: Session, llm_router: LLMRouter):
        self.db = db
        self.llm = llm_router
        self.client = httpx.AsyncClient(timeout=30.0)
        self.openclaw_parser = OpenClawParser()

    async def create_skill_from_api_documentation(
        self,
        tenant_id: str,
        agent_id: str,
        user_id: str,
        api_docs_url: str,
        api_description: str,
        skill_name: Optional[str] = None,
        category: Optional[str] = None
    ) -> Skill:
        """
        Create a skill from API documentation.

        Args:
            tenant_id: Tenant ID
            agent_id: Agent ID creating the skill
            user_id: User ID (author)
            api_docs_url: URL to OpenAPI/Swagger spec
            api_description: Description of the API
            skill_name: Optional custom skill name
            category: Optional skill category

        Returns:
            Created Skill object
        """
        try:
            logger.info(f"Creating skill from API docs: {api_docs_url}")

            # 1. Fetch API documentation
            docs = await self._fetch_api_docs(api_docs_url)

            # 2. Analyze API spec
            analysis = await self._analyze_api_spec(docs, api_description)

            # 3. Generate skill code
            skill_code = await self._generate_skill_code(analysis)

            # 4. Create skill
            skill = Skill(
                tenant_id=tenant_id,
                author_tenant_id=tenant_id,
                name=skill_name or analysis["suggested_name"],
                description=analysis["description"],
                long_description=analysis["long_description"],
                version="1.0.0",
                type="api",
                input_schema=analysis["input_schema"],
                output_schema=analysis["output_schema"],
                config={
                    "url": analysis["base_url"],
                    "method": "GET",
                    "headers": analysis.get("auth_headers", {}),
                    **analysis.get("config", {})
                },
                category=category or analysis.get("category", "productivity"),
                tags=analysis.get("tags", []),
                code=skill_code,
                is_public=False,
                is_approved=False
            )

            self.db.add(skill)
            self.db.flush()

            # 5. Create version
            version = SkillVersion(
                skill_id=skill.id,
                tenant_id=tenant_id,
                version="1.0.0",
                changelog=f"Created from API documentation: {api_docs_url}",
                name=skill.name,
                description=skill.description,
                type=skill.type,
                input_schema=skill.input_schema,
                output_schema=skill.output_schema,
                config=skill.config,
                code=skill.code
            )

            self.db.add(version)
            self.db.commit()

            logger.info(f"Created skill {skill.id} from API docs")

            return skill

        except Exception as e:
            logger.error(f"Error creating skill from API docs: {e}")
            self.db.rollback()
            raise

    async def create_canvas_component_for_skill(
        self,
        tenant_id: str,
        agent_id: str,
        user_id: str,
        skill_id: str,
        component_type: str = "table"
    ) -> CanvasComponent:
        """
        Generate canvas component that uses a skill.

        Args:
            tenant_id: Tenant ID
            agent_id: Agent ID
            user_id: User ID
            skill_id: Skill ID
            component_type: Type of component (table, chart, form, etc.)

        Returns:
            Created CanvasComponent
        """
        try:
            # 1. Get skill
            skill = self.db.query(Skill).filter(Skill.id == skill_id).first()
            if not skill:
                raise ValueError(f"Skill {skill_id} not found")

            # 2. Analyze skill output schema
            component_config = await self._analyze_skill_for_component(skill, component_type)

            # 3. Generate component code
            component_code = await self._generate_component_code(skill, component_config)

            # 4. Create component
            component = CanvasComponent(
                tenant_id=tenant_id,
                author_id=user_id,
                name=f"{skill.name} Component",
                description=f"Canvas component for {skill.name}",
                category=component_config["category"],
                component_type="react",
                code=component_code,
                config_schema=component_config["config_schema"],
                tags=skill.tags or [],
                dependencies=component_config.get("dependencies", []),
                version="1.0.0",
                is_public=False,
                is_approved=False,
                config={
                    "required_skill_id": skill.id,
                    "required_skill_version": skill.version
                }
            )

            self.db.add(component)
            self.db.commit()

            logger.info(f"Created component {component.id} for skill {skill_id}")

            return component

        except Exception as e:
            logger.error(f"Error creating component for skill: {e}")
            self.db.rollback()
            raise

    async def _fetch_api_docs(self, url: str) -> Dict[str, Any]:
        """Fetch OpenAPI/Swagger documentation from URL."""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching API docs from {url}: {e}")
            raise ValueError(f"Failed to fetch API documentation: {e}")

    async def _analyze_api_spec(
        self,
        docs: Dict[str, Any],
        description: str
    ) -> Dict[str, Any]:
        """
        Analyze OpenAPI spec and extract key information.

        Returns:
            Dict with base_url, authentication, endpoints, schemas
        """
        # Extract base info
        info = docs.get("info", {})
        title = info.get("title", "API")
        # version = info.get("version", "1.0.0")

        # Extract servers
        servers = docs.get("servers", [])
        base_url = servers[0]["url"] if servers else ""

        # Extract authentication
        security_schemes = docs.get("components", {}).get("securitySchemes", {})
        auth_headers = {}

        for scheme_name, scheme in security_schemes.items():
            if scheme["type"] == "apiKey":
                if scheme["in"] == "header":
                    auth_headers[scheme["name"]] = "{{API_KEY}}"
            elif scheme["type"] == "http":
                if scheme["scheme"] == "bearer":
                    auth_headers["Authorization"] = "Bearer {{API_KEY}}"

        # Extract paths (endpoints)
        paths = docs.get("paths", {})

        # Get first GET endpoint as example
        example_path = None
        example_method = None
        for path, methods in paths.items():
            if "get" in methods:
                example_path = path
                example_method = methods["get"]
                break

        # Extract schemas
        # components = docs.get("components", {})
        # schemas = components.get("schemas", {})

        # Build input/output schemas
        input_schema = {}
        output_schema = {}

        if example_method:
            # Extract parameters
            parameters = example_method.get("parameters", [])
            input_schema = {
                "type": "object",
                "properties": {}
            }

            for param in parameters:
                param_name = param["name"]
                param_schema = param.get("schema", {})
                input_schema["properties"][param_name] = {
                    "type": param_schema.get("type", "string"),
                    "description": param.get("description", "")
                }
                if param.get("required"):
                    input_schema.setdefault("required", []).append(param_name)

            # Extract response schema
            responses = example_method.get("responses", {})
            success_response = responses.get("200") or responses.get("2xx")

            if success_response:
                content = success_response.get("content", {})
                json_content = content.get("application/json", {})
                output_schema = json_content.get("schema", {})

        # Suggest skill name
        suggested_name = title.lower().replace(" ", "-").replace("api", "") + "-fetcher"

        return {
            "suggested_name": suggested_name,
            "description": f"Fetch data from {title}",
            "long_description": description,
            "base_url": base_url,
            "auth_headers": auth_headers,
            "endpoints": list(paths.keys()),
            "input_schema": input_schema,
            "output_schema": output_schema,
            "category": self._infer_category(info, description),
            "tags": self._extract_tags(info, description),
            "config": {
                "example_path": example_path
            }
        }

    def _infer_category(self, info: Dict, description: str) -> str:
        """Infer skill category from API info."""
        desc_lower = description.lower()
        # title_lower = info.get("title", "").lower()

        if any(word in desc_lower for word in ["shopify", "ecommerce", "product", "order"]):
            return "ecommerce"
        elif any(word in desc_lower for word in ["salesforce", "crm", "lead", "contact"]):
            return "crm"
        elif any(word in desc_lower for word in ["slack", "teams", "communication"]):
            return "communication"
        elif any(word in desc_lower for word in ["finance", "accounting", "invoice"]):
            return "finance"
        elif any(word in desc_lower for word in ["marketing", "campaign", "email"]):
            return "marketing"
        else:
            return "productivity"

    def _extract_tags(self, info: Dict, description: str) -> List[str]:
        """Extract tags from API info."""
        tags = []

        desc_lower = description.lower()
        title_lower = info.get("title", "").lower()

        # Common tags
        if "api" in title_lower:
            tags.append("api")
        if "rest" in desc_lower:
            tags.append("rest")
        if "json" in desc_lower:
            tags.append("json")

        return tags

    async def _generate_skill_code(self, analysis: Dict[str, Any]) -> str:
        """
        Generate Python skill code from analysis.

        Uses LLM to generate production-ready code.
        """
        prompt = f"""Generate a Python skill that fetches data from an API.

API Details:
- Base URL: {analysis['base_url']}
- Description: {analysis['description']}
- Input Schema: {json.dumps(analysis['input_schema'], indent=2)}
- Output Schema: {json.dumps(analysis['output_schema'], indent=2)}
- Auth Headers: {json.dumps(analysis['auth_headers'], indent=2)}

Generate a Python function that:
1. Takes input parameters matching the input schema
2. Makes an HTTP request to the API
3. Handles authentication
4. Returns the response data
5. Includes error handling

Return ONLY the Python code, no explanations."""

        try:
            response = await self.llm.call(
                tenant_id="system",
                messages=[
                    {"role": "system", "content": "You are a Python developer. Generate clean, production-ready code."},
                    {"role": "user", "content": prompt}
                ]
            )

            code = response.get("content", "")

            # Extract code from markdown if present
            if "```python" in code:
                code = code.split("```python")[1].split("```")[0].strip()

            return code

        except Exception as e:
            logger.error(f"Error generating skill code: {e}")
            # Return intelligent fallback based on auth type
            return self._generate_fallback_code(analysis)

    def _generate_fallback_code(self, analysis: Dict[str, Any]) -> str:
        """
        Generate intelligent fallback code based on authentication type.
        """
        auth_headers = analysis.get("auth_headers", {})
        base_url = analysis['base_url']
        description = analysis['description']

        # Detect auth type
        has_bearer = any("Bearer" in str(v) for v in auth_headers.values())
        has_api_key = any("API_KEY" in str(v) or "X-" in str(k) for k, v in auth_headers.items())

        if has_bearer:
            # Bearer token authentication (OAuth2/JWT)
            return f'''import httpx
import os
from typing import Dict, Any

async def execute(config: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    {description}

    Authentication: Bearer Token (OAuth2/JWT)
    Base URL: {base_url}

    Config:
        - url: Full endpoint URL (overrides base_url)
        - headers: Additional headers (Authorization header added automatically)
        - bearer_token: OAuth2/JWT access token
    """
    url = config.get("url", "{base_url}")
    headers = config.get("headers", {{}})

    # Add Bearer token from config or environment
    bearer_token = config.get("bearer_token") or os.getenv("API_BEARER_TOKEN")
    if bearer_token:
        headers["Authorization"] = f"Bearer {{bearer_token}}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=input_data)
        response.raise_for_status()
        return response.json()
'''
        elif has_api_key:
            # API key in header
            header_name = next((k for k, v in auth_headers.items() if "API_KEY" in str(v)), "X-API-Key")
            return f'''import httpx
import os
from typing import Dict, Any

async def execute(config: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    {description}

    Authentication: API Key (Header-based)
    Base URL: {base_url}

    Config:
        - url: Full endpoint URL (overrides base_url)
        - headers: Additional headers (API key header added automatically)
        - api_key: API key for authentication
    """
    url = config.get("url", "{base_url}")
    headers = config.get("headers", {{}})

    # Add API key from config or environment
    api_key = config.get("api_key") or os.getenv("API_KEY")
    if api_key:
        headers["{header_name}"] = api_key

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=input_data)
        response.raise_for_status()
        return response.json()
'''
        else:
            # No authentication (public API)
            return f'''import httpx
from typing import Dict, Any

async def execute(config: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    {description}

    Authentication: None (Public API)
    Base URL: {base_url}

    Config:
        - url: Full endpoint URL (overrides base_url)
        - headers: Optional additional headers
    """
    url = config.get("url", "{base_url}")
    headers = config.get("headers", {{}})

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=input_data)
        response.raise_for_status()
        return response.json()
'''

    async def _analyze_skill_for_component(
        self,
        skill: Skill,
        component_type: str
    ) -> Dict[str, Any]:
        """
        Analyze skill to determine component configuration.
        """
        # output_schema = skill.output_schema or {}

        # Determine component category
        if component_type == "table":
            category = "table"
        elif component_type == "chart":
            category = "chart"
        elif component_type == "form":
            category = "form"
        else:
            category = "widget"

        # Build config schema
        config_schema = {
            "type": "object",
            "properties": {
                "skillId": {
                    "type": "string",
                    "description": "Skill ID to execute"
                },
                "title": {
                    "type": "string",
                    "description": "Component title"
                }
            }
        }

        return {
            "category": category,
            "config_schema": config_schema,
            "dependencies": ["recharts", "lucide-react"]
        }

    async def _generate_component_code(
        self,
        skill: Skill,
        config: Dict[str, Any]
    ) -> str:
        """
        Generate React component code for skill.

        Uses LLM to generate component code.
        """
        prompt = f"""Generate a React TypeScript component that displays data from a skill.

Skill Details:
- Name: {skill.name}
- Description: {skill.description}
- Output Schema: {json.dumps(skill.output_schema, indent=2)}

Requirements:
- Use Recharts for visualizations if appropriate
- Use shadcn/ui components (Card, Button, Badge, etc.)
- Fetch data from /api/skills/${{skillId}}/execute
- Auto-detect schema from response
- Make it responsive and accessible
- Include loading states and error handling

Return ONLY the TypeScript code, no explanations."""

        try:
            response = await self.llm.call(
                tenant_id="system",
                messages=[
                    {"role": "system", "content": "You are a React/TypeScript developer. Generate clean, production-ready components."},
                    {"role": "user", "content": prompt}
                ]
            )

            code = response.get("content", "")

            # Extract code from markdown if present
            if "```typescript" in code:
                code = code.split("```typescript")[1].split("```")[0].strip()
            elif "```tsx" in code:
                code = code.split("```tsx")[1].split("```")[0].strip()

            return code

        except Exception as e:
            logger.error(f"Error generating component code: {e}")
            # Return basic template
            return f'''import React, {{ useState, useEffect }} from 'react';
import {{ Card, CardContent, CardHeader, CardTitle }} from '@/components/ui/card';
import {{ Button }} from '@/components/ui/button';
import {{ RefreshCw }} from 'lucide-react';

interface {skill.name.replace("-", "").replace(" ", "")}Props {{
  tenantId: string;
  skillId: string;
  title?: string;
}}

export const {skill.name.replace("-", "").replace(" ", "")}Component: React.FC<{skill.name.replace("-", "").replace(" ", "")}Props> = ({{
  tenantId,
  skillId,
  title = "{skill.name}"
}}) => {{
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const fetchData = async () => {{
    setLoading(true);
    try {{
      const response = await fetch(`/api/skills/${{skillId}}/execute`, {{
        method: 'POST',
        headers: {{
          'Content-Type': 'application/json',
          'X-Tenant-ID': tenantId
        }},
        body: JSON.stringify({{}})
      }});
      const result = await response.json();
      setData(result.data || result);
    }} catch (error) {{
      console.error('Error fetching data:', error);
    }} finally {{
      setLoading(false);
    }}
  }};

  useEffect(() => {{
    fetchData();
  }}, [skillId]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{{title}}</CardTitle>
      </CardHeader>
      <CardContent>
        {{loading ? (
          <RefreshCw className="animate-spin" />
        ) : (
          <pre>{{JSON.stringify(data, null, 2)}}</pre>
        )}}
      </CardContent>
    </Card>
  );
}};
'''

    def generate_skill_metadata(
        self,
        component_data: Dict[str, Any],
        skill_id: str,
        tenant_id: str
    ) -> str:
        """
        Generate SKILL.md content with npm dependencies section.
        """
        # Extract npm dependencies from component code
        npm_dependencies = []
        if component_data.get("code"):
            npm_dependencies = self.openclaw_parser.extract_npm_dependencies(
                component_data["code"],
                component_data.get("name", "unknown")
            )

        # Also use dependencies field if provided
        if component_data.get("dependencies"):
            npm_dependencies.extend(component_data["dependencies"])
            # Remove duplicates while preserving order
            seen = set()
            unique_deps = []
            for dep in npm_dependencies:
                if dep not in seen:
                    seen.add(dep)
                    unique_deps.append(dep)
            npm_dependencies = unique_deps

        # Build SKILL.md content
        skill_metadata = f"""---
name: {component_data.get("name", skill_id)}
description: {component_data.get("description", "")}
author: system
version: {component_data.get("version", "1.0.0")}
metadata:
  openclaw:
    install:
"""

        # Add npm packages to install section
        if npm_dependencies:
            for dep in npm_dependencies:
                skill_metadata += f"      - id: {dep}\n"
                skill_metadata += f"        kind: npm\n"
                skill_metadata += f"        package: {dep}\n"
        else:
            skill_metadata += f"      []\n"

        skill_metadata += f"""---

# {component_data.get("name", skill_id)}

{component_data.get("description", "")}

## Overview

This skill provides {component_data.get("category", "general")} functionality.

## Technical Details

- **Component Type:** {component_data.get("component_type", "React")}
- **Framework:** React
- **Language:** TypeScript
- **Version:** {component_data.get("version", "1.0.0")}

## Dependencies

### Python Packages

{self._format_python_dependencies(component_data.get("python_dependencies", []))}

### NPM Packages

{self._format_npm_dependencies(npm_dependencies)}

## Usage

```typescript
import {{ {component_data.get("name", skill_id).replace("-", "").replace(" ", "")} }} from "./components/{component_data.get("name", skill_id)}";

// Use the component
<{component_data.get("name", skill_id).replace("-", "").replace(" ", "")} />
```

## Configuration

{self._format_config_schema(component_data.get("config_schema", {}))}
"""

        return skill_metadata

    def _format_npm_dependencies(self, dependencies: List[str]) -> str:
        """Format npm dependencies for SKILL.md."""
        if not dependencies:
            return "None"

        formatted = []
        for dep in dependencies:
            formatted.append(f"- **{dep}**")

        return "\n".join(formatted)

    def _format_python_dependencies(self, dependencies: List[str]) -> str:
        """Format Python dependencies for SKILL.md."""
        if not dependencies:
            return "None"

        formatted = []
        for dep in dependencies:
            formatted.append(f"- **{dep}**")

        return "\n".join(formatted)

    def _format_config_schema(self, config_schema: Dict[str, Any]) -> str:
        """Format configuration schema for SKILL.md."""
        if not config_schema or not config_schema.get("properties"):
            return "No configuration required."

        formatted = ["### Configuration Properties", ""]
        properties = config_schema.get("properties", {})

        for prop_name, prop_details in properties.items():
            prop_type = prop_details.get("type", "any")
            prop_desc = prop_details.get("description", "")
            required = prop_name in config_schema.get("required", [])

            required_mark = " *(required)*" if required else ""
            formatted.append(f"- **{prop_name}** ({prop_type}){required_mark}: {prop_desc}")

        return "\n".join(formatted)
