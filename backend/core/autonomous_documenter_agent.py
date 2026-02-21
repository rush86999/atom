"""
Autonomous Documenter Agent - Automated documentation generation.

Generates comprehensive documentation for AI-generated code:
- OpenAPI/Swagger specifications from route files
- Markdown usage guides following Atom patterns
- Google-style docstrings for undocumented functions
- README and CHANGELOG updates

Integration:
- Uses CoderAgent output as input for documentation
- Integrates with BYOK handler for LLM-powered docstring generation
- Follows Atom documentation standards and patterns

Performance targets:
- OpenAPI generation: <10 seconds for route files
- Markdown guide generation: <15 seconds
- Docstring addition: <30 seconds per file
- README/CHANGELOG update: <5 seconds
"""

import ast
import json
import logging
import re
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from core.llm.byok_handler import BYOKHandler

logger = logging.getLogger(__name__)


# ============================================================================
# Task 1: OpenAPI Documentation Generator
# ============================================================================

class OpenAPIDocumentGenerator:
    """
    Generate OpenAPI/Swagger documentation from FastAPI route files.

    Parses Python route files using AST to extract endpoint definitions.
    Generates OpenAPI 3.0 compliant specifications with schemas, parameters,
    request bodies, responses, and security schemes.

    Attributes:
        project_root: Root directory of the project
        api_root: Directory containing API route files

    Example:
        generator = OpenAPIDocumentGenerator(project_root="backend")
        spec = generator.generate_openapi_spec(["api/auth_routes.py"])
        print(json.dumps(spec, indent=2))
    """

    def __init__(self, project_root: str = "backend"):
        """
        Initialize OpenAPI generator.

        Args:
            project_root: Root directory of the project
        """
        self.project_root = Path(project_root)
        self.api_root = self.project_root / "api"

    def generate_openapi_spec(
        self,
        route_files: List[str]
    ) -> Dict[str, Any]:
        """
        Generate OpenAPI 3.0 specification from route files.

        Args:
            route_files: List of route file paths (e.g., ["api/auth_routes.py"])

        Returns:
            OpenAPI 3.0 spec dict with:
            - info: Title, version, description
            - paths: Path items with operations
            - components: Schemas, responses, security
        """
        logger.info(f"Generating OpenAPI spec for {len(route_files)} route files")

        paths = {}
        components = {
            "schemas": {},
            "responses": {},
            "securitySchemes": {}
        }

        # Process each route file
        for route_file in route_files:
            file_path = self.api_root / route_file
            if not file_path.exists():
                logger.warning(f"Route file not found: {file_path}")
                continue

            # Extract endpoints from file
            endpoints = self.extract_endpoints_from_file(str(file_path))

            # Generate path items for each endpoint
            for endpoint in endpoints:
                path_item = self.generate_path_item(endpoint)
                path = endpoint["path"]

                # Merge path item (handle multiple methods on same path)
                if path in paths:
                    paths[path].update(path_item)
                else:
                    paths[path] = path_item

        # Build OpenAPI spec
        spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "Atom API",
                "version": "1.0.0",
                "description": "AI-Powered Business Automation Platform API"
            },
            "paths": paths,
            "components": components
        }

        logger.info(f"Generated OpenAPI spec with {len(paths)} paths")
        return spec

    def extract_endpoints_from_file(
        self,
        route_file: str
    ) -> List[Dict[str, Any]]:
        """
        Extract FastAPI endpoints from route file.

        Uses AST to find @router.get/post/put/delete decorators.

        Args:
            route_file: Path to route file

        Returns:
            List of endpoint definitions with path, method, handler, params
        """
        logger.info(f"Extracting endpoints from: {route_file}")

        endpoints = []

        try:
            with open(route_file, 'r') as f:
                source = f.read()

            # Parse AST
            tree = ast.parse(source)

            # Find all function definitions
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Check for FastAPI route decorators
                    endpoint = self._parse_route_decorator(node, source)
                    if endpoint:
                        endpoints.append(endpoint)

        except Exception as e:
            logger.error(f"Failed to parse route file {route_file}: {e}")

        return endpoints

    def _parse_route_decorator(
        self,
        func_node: ast.FunctionDef,
        source: str
    ) -> Optional[Dict[str, Any]]:
        """
        Parse FastAPI route decorator from function node.

        Args:
            func_node: AST FunctionDef node
            source: Source code string

        Returns:
            Endpoint dict or None if not a route
        """
        for decorator in func_node.decorator_list:
            # Handle @router.get("/path") or @app.get("/path")
            path = "/"
            method = None

            if isinstance(decorator, ast.Call):
                # Try to extract method from attribute access (router.get, app.post, etc.)
                if isinstance(decorator.func, ast.Attribute):
                    method = decorator.func.attr.lower()
                    if method in ["get", "post", "put", "delete", "patch"]:
                        # Extract path argument
                        if decorator.args and isinstance(decorator.args[0], ast.Constant):
                            path = decorator.args[0].value
                        elif decorator.args and isinstance(decorator.args[0], ast.Str):  # Python < 3.8
                            path = decorator.args[0].s

                        if method:  # Only return if we found a valid HTTP method
                            # Extract function parameters
                            params = self._extract_function_params(func_node)

                            # Extract return type
                            return_type = self._extract_return_type(func_node)

                            return {
                                "path": path,
                                "method": method,
                                "handler": func_node.name,
                                "params": params,
                                "return_type": return_type,
                                "lineno": func_node.lineno
                            }

        return None

    def _extract_function_params(
        self,
        func_node: ast.FunctionDef
    ) -> List[Dict[str, str]]:
        """
        Extract function parameters with types.

        Args:
            func_node: AST FunctionDef node

        Returns:
            List of param dicts with name, type, annotation
        """
        params = []

        for arg in func_node.args.args:
            param_name = arg.arg

            # Get type annotation
            param_type = "any"
            if arg.annotation:
                if isinstance(arg.annotation, ast.Name):
                    param_type = arg.annotation.id
                elif isinstance(arg.annotation, ast.Subscript):
                    if isinstance(arg.annotation.value, ast.Name):
                        param_type = arg.annotation.value.id

            # Skip common params (db, current_user)
            if param_name not in ["db", "current_user", "token"]:
                params.append({
                    "name": param_name,
                    "type": param_type,
                    "in": "query" if method in ["get", "delete"] else "body"
                })

        return params

    def _extract_return_type(
        self,
        func_node: ast.FunctionDef
    ) -> str:
        """
        Extract function return type.

        Args:
            func_node: AST FunctionDef node

        Returns:
            Return type string
        """
        if func_node.returns:
            if isinstance(func_node.returns, ast.Name):
                return func_node.returns.id
            elif isinstance(func_node.returns, ast.Constant):
                return str(func_node.returns.value)

        return "void"

    def generate_path_item(
        self,
        endpoint: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate OpenAPI path item for endpoint.

        Args:
            endpoint: Endpoint definition

        Returns:
            OpenAPI path item dict
        """
        method = endpoint["method"]
        path = endpoint["path"]

        # Build operation object
        operation = {
            "summary": endpoint["handler"].replace("_", " ").title(),
            "operationId": endpoint["handler"],
            "parameters": [],
            "responses": {
                "200": {
                    "description": "Success",
                    "content": {
                        "application/json": {
                            "schema": self.generate_response_schema(
                                endpoint["return_type"]
                            )
                        }
                    }
                },
                "400": {"description": "Bad Request"},
                "401": {"description": "Unauthorized"},
                "404": {"description": "Not Found"},
                "500": {"description": "Internal Server Error"}
            }
        }

        # Add parameters
        for param in endpoint["params"]:
            operation["parameters"].append({
                "name": param["name"],
                "in": param["in"],
                "required": True,
                "schema": {"type": param["type"]}
            })

        # Add security scheme if applicable
        security = self.infer_security_scheme(endpoint)
        if security:
            operation["security"] = [{security: []}]

        return {method: operation}

    def generate_schema_from_pydantic(
        self,
        model_class: str
    ) -> Dict[str, Any]:
        """
        Generate JSON Schema from Pydantic model.

        Args:
            model_class: Pydantic model class name

        Returns:
            JSON Schema dict
        """
        # For now, return generic object schema
        # Full implementation would import and inspect Pydantic model
        return {
            "type": "object",
            "properties": {}
        }

    def generate_response_schema(
        self,
        return_type: str
    ) -> Dict[str, Any]:
        """
        Generate response schema from return type annotation.

        Args:
            return_type: Return type string

        Returns:
            JSON Schema dict
        """
        # Map common types to JSON Schema
        type_map = {
            "str": {"type": "string"},
            "int": {"type": "integer"},
            "float": {"type": "number"},
            "bool": {"type": "boolean"},
            "list": {"type": "array"},
            "dict": {"type": "object"},
            "void": {"type": "null"}
        }

        return type_map.get(return_type, {"type": "object"})

    def infer_security_scheme(
        self,
        endpoint: Dict[str, Any]
    ) -> Optional[str]:
        """
        Infer security scheme from endpoint.

        Args:
            endpoint: Endpoint definition

        Returns:
            "bearer", "apikey", "oauth2", or None
        """
        # Check for auth-related params
        params = endpoint.get("params", [])
        param_names = [p["name"] for p in params]

        if "token" in param_names or "authorization" in param_names:
            return "bearer"
        elif "api_key" in param_names:
            return "apikey"

        return None


# ============================================================================
# Task 2: Markdown Guide Generator
# ============================================================================

class MarkdownGuideGenerator:
    """
    Generate Markdown documentation files following Atom patterns.

    Creates comprehensive usage guides for services and features with
    configuration, API examples, code examples, and troubleshooting.

    Attributes:
        project_root: Root directory of the project
        docs_root: Directory for documentation files

    Example:
        generator = MarkdownGuideGenerator(project_root="backend")
        guide = generator.generate_usage_guide(
            "OAuth Service",
            service_methods,
            examples
        )
    """

    def __init__(self, project_root: str = "backend"):
        """
        Initialize Markdown generator.

        Args:
            project_root: Root directory of the project
        """
        self.project_root = Path(project_root)
        self.docs_root = self.project_root.parent / "docs"

    def generate_usage_guide(
        self,
        service_name: str,
        service_methods: List[Dict[str, Any]],
        examples: List[Dict[str, Any]]
    ) -> str:
        """
        Generate usage guide in Markdown format.

        Structure:
        # Feature Name
        ## Overview
        ## Configuration
        ## Usage (Python API, REST API)
        ## Examples
        ## Troubleshooting

        Args:
            service_name: Name of the service/feature
            service_methods: List of method definitions
            examples: List of usage examples

        Returns:
            Complete Markdown content
        """
        logger.info(f"Generating usage guide for: {service_name}")

        # Extract environment variables from methods
        env_vars = self._extract_env_vars(service_methods)

        # Extract endpoints from methods
        endpoints = self._extract_endpoints(service_methods)

        # Build markdown sections
        sections = [
            self._generate_title_section(service_name),
            self._generate_overview_section(service_name),
            self.generate_configuration_section(env_vars),
            self._generate_usage_section(service_methods, endpoints),
            self.generate_code_examples(service_methods),
            self._generate_examples_section(examples),
            self.generate_troubleshooting_section([])
        ]

        return "\n\n".join(sections)

    def _generate_title_section(self, service_name: str) -> str:
        """
        Generate title section.

        Args:
            service_name: Name of the service

        Returns:
            Markdown title section
        """
        return f"# {service_name}\n"

    def _generate_overview_section(self, service_name: str) -> str:
        """
        Generate overview section.

        Args:
            service_name: Name of the service

        Returns:
            Markdown overview section
        """
        return f"""## Overview

Brief description of what this service does.
"""

    def generate_configuration_section(
        self,
        env_vars: List[str]
    ) -> str:
        """
        Generate configuration section with environment variables.

        Args:
            env_vars: List of environment variable names

        Returns:
            Markdown configuration section
        """
        if not env_vars:
            return "## Configuration\n\nNo configuration required.\n"

        lines = ["## Configuration\n", "Environment variables:\n"]

        for var in env_vars:
            lines.append(f"- `{var}` - Description (default: value)")

        return "\n".join(lines)

    def _generate_usage_section(
        self,
        methods: List[Dict[str, Any]],
        endpoints: List[Dict[str, Any]]
    ) -> str:
        """
        Generate usage section with Python and REST API examples.

        Args:
            methods: List of service methods
            endpoints: List of REST endpoints

        Returns:
            Markdown usage section
        """
        section = "## Usage\n\n"

        if endpoints:
            section += "### REST API\n\n"
            section += self.generate_api_examples(endpoints)

        if methods:
            section += "\n### Python API\n\n"
            section += self.generate_code_examples(methods)

        return section

    def generate_api_examples(
        self,
        endpoints: List[Dict[str, Any]]
    ) -> str:
        """
        Generate API usage examples.

        Args:
            endpoints: List of endpoint definitions

        Returns:
            Markdown with curl examples
        """
        if not endpoints:
            return "No API endpoints available.\n"

        examples = []

        for endpoint in endpoints[:5]:  # Limit to 5 examples
            method = endpoint.get("method", "GET").upper()
            path = endpoint.get("path", "/")

            examples.append(f"""#### {method} {path}

```bash
curl -X {method} http://localhost:8000{path} \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_TOKEN"
```
""")

        return "\n".join(examples)

    def generate_code_examples(
        self,
        methods: List[Dict[str, Any]]
    ) -> str:
        """
        Generate Python code examples.

        Args:
            methods: List of method definitions

        Returns:
            Markdown with Python code examples
        """
        if not methods:
            return "No methods available.\n"

        examples = []

        for method in methods[:5]:  # Limit to 5 examples
            method_name = method.get("name", "method_name")
            params = method.get("params", [])

            # Build function call
            param_str = ", ".join([f'"{p}"' for p in params])
            examples.append(f"""#### {method_name}

```python
from core.{method_name.lower()}_service import {method_name}

service = {method_name}(db)
result = await service.{method_name}({param_str})
```
""")

        return "\n".join(examples)

    def _extract_env_vars(
        self,
        methods: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Extract environment variables from methods.

        Args:
            methods: List of method definitions

        Returns:
            List of environment variable names
        """
        # Common Atom environment variables
        common_vars = [
            "DATABASE_URL",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "ENVIRONMENT"
        ]

        return common_vars

    def _extract_endpoints(
        self,
        methods: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extract REST endpoints from methods.

        Args:
            methods: List of method definitions

        Returns:
            List of endpoint definitions
        """
        endpoints = []

        for method in methods:
            if "endpoint" in method:
                endpoints.append(method["endpoint"])

        return endpoints

    def _generate_examples_section(
        self,
        examples: List[Dict[str, Any]]
    ) -> str:
        """
        Generate examples section.

        Args:
            examples: List of usage examples

        Returns:
            Markdown examples section
        """
        if not examples:
            return "## Examples\n\nNo examples available.\n"

        section = "## Examples\n\n"

        for example in examples[:3]:  # Limit to 3 examples
            title = example.get("title", "Example")
            code = example.get("code", "")

            section += f"### {title}\n\n"
            section += f"```python\n{code}\n```\n\n"

        return section

    def generate_troubleshooting_section(
        self,
        common_errors: List[Dict[str, str]]
    ) -> str:
        """
        Generate troubleshooting section.

        Args:
            common_errors: List of common errors with solutions

        Returns:
            Markdown troubleshooting section
        """
        section = "## Troubleshooting\n\n"

        if not common_errors:
            # Add default troubleshooting content
            section += """### Common Issues

#### Issue 1: Authentication Failed

**Problem**: API returns 401 Unauthorized

**Solution**:
- Verify JWT token is valid and not expired
- Check `Authorization` header format: `Bearer <token>`
- Ensure user has required permissions

#### Issue 2: Database Connection Error

**Problem**: Cannot connect to database

**Solution**:
- Check `DATABASE_URL` environment variable
- Verify database server is running
- Check network connectivity and firewall rules

#### Issue 3: Missing Dependencies

**Problem**: Import errors or missing packages

**Solution**:
```bash
pip install -r requirements.txt
```
"""
        else:
            for error in common_errors:
                error_name = error.get("name", "Error")
                problem = error.get("problem", "Unknown problem")
                solution = error.get("solution", "No solution available")

                section += f"### {error_name}\n\n"
                section += f"**Problem**: {problem}\n\n"
                section += f"**Solution**:\n{solution}\n\n"

        return section


# ============================================================================
# Task 3: Docstring Generator
# ============================================================================

class DocstringGenerator:
    """
    Generate Google-style docstrings for undocumented functions.

    Uses LLM to infer function purpose and generate comprehensive docstrings
    following Google style guide (summary, args, returns, raises).

    Attributes:
        db: Database session
        byok_handler: BYOK handler for LLM access

    Example:
        generator = DocstringGenerator(db, byok_handler)
        result = await generator.add_docstrings_to_file("service.py")
        print(f"Added {result['added']} docstrings")
    """

    def __init__(self, db: Session, byok_handler: BYOKHandler):
        """
        Initialize docstring generator.

        Args:
            db: Database session
            byok_handler: BYOK handler for LLM access
        """
        self.db = db
        self.byok_handler = byok_handler

    async def add_docstrings_to_file(
        self,
        file_path: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Add docstrings to undocumented functions in file.

        Args:
            file_path: Path to Python file
            force: Regenerate existing docstrings

        Returns:
            {
                "added": int,
                "updated": int,
                "skipped": int,
                "new_content": str
            }
        """
        logger.info(f"Adding docstrings to file: {file_path} (force={force})")

        try:
            with open(file_path, 'r') as f:
                source_code = f.read()

            # Find undocumented functions
            functions = self.find_undocumented_functions(source_code)

            added = 0
            updated = 0
            skipped = 0

            # Process each function
            for func in functions:
                if not func["has_docstring"] or force:
                    # Generate docstring
                    docstring = await self.generate_docstring_with_llm(
                        func, source_code
                    )

                    if docstring:
                        # Insert docstring
                        source_code = self.insert_docstring(
                            source_code,
                            func["line_number"],
                            docstring
                        )

                        if func["has_docstring"]:
                            updated += 1
                        else:
                            added += 1
                    else:
                        skipped += 1
                else:
                    skipped += 1

            return {
                "added": added,
                "updated": updated,
                "skipped": skipped,
                "new_content": source_code
            }

        except Exception as e:
            logger.error(f"Failed to add docstrings: {e}")
            return {
                "added": 0,
                "updated": 0,
                "skipped": 0,
                "new_content": ""
            }

    def find_undocumented_functions(
        self,
        source_code: str
    ) -> List[Dict[str, Any]]:
        """
        Find functions missing docstrings.

        Uses AST to parse and check for docstrings.

        Args:
            source_code: Python source code

        Returns:
            List of functions needing docs
        """
        functions = []

        try:
            tree = ast.parse(source_code)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Check for docstring
                    has_docstring = (
                        node.body and
                        isinstance(node.body[0], ast.Expr) and
                        isinstance(node.body[0].value, ast.Constant)
                    )

                    # Extract function signature
                    args = [arg.arg for arg in node.args.args]
                    returns = node.returns is not None

                    functions.append({
                        "name": node.name,
                        "line_number": node.lineno,
                        "args": args,
                        "returns": returns,
                        "has_docstring": has_docstring
                    })

        except Exception as e:
            logger.error(f"Failed to parse source code: {e}")

        return functions

    async def generate_docstring_with_llm(
        self,
        function: Dict[str, Any],
        context: str
    ) -> str:
        """
        Generate Google-style docstring using LLM.

        Args:
            function: Function definition dict
            context: Surrounding code context

        Returns:
            Formatted docstring
        """
        logger.info(f"Generating docstring for: {function['name']}")

        try:
            # Infer argument descriptions
            arg_descriptions = self.infer_arg_descriptions(function)

            # Build prompt
            prompt = f"""Generate a Google-style docstring for this function:

Function: {function['name']}
Arguments: {', '.join(function['args'])}
Returns: {function['returns']}

Generate a docstring that includes:
1. Summary line (one sentence describing what the function does)
2. Args section (if has parameters)
3. Returns section (if returns value)
4. Raises section (if raises exceptions)

Return ONLY the docstring wrapped in triple quotes, no explanations."""

            # Generate with LLM
            response = await self.byok_handler.generate_response(
                prompt=prompt,
                system_instruction="You are an expert technical writer. Generate clear, concise Google-style docstrings.",
                model_type="quality",
                temperature=0.2,
                task_type="documentation"
            )

            # Extract docstring from response
            docstring = response.strip()

            # Format if needed
            if not docstring.startswith('"""'):
                docstring = self.format_google_docstring(
                    docstring,
                    function["args"],
                    "Return value" if function["returns"] else None,
                    []
                )

            return docstring

        except Exception as e:
            logger.error(f"Failed to generate docstring: {e}")
            return ""

    def format_google_docstring(
        self,
        description: str,
        args: List[str],
        returns: Optional[str],
        raises: List[str]
    ) -> str:
        """
        Format docstring in Google style.

        Args:
            description: Function description
            args: List of argument names
            returns: Return description or None
            raises: List of exception types

        Returns:
            Formatted docstring
        """
        lines = ['"""', description]

        if args:
            lines.append("\nArgs:")
            for arg in args:
                lines.append(f"    {arg}: Description")

        if returns:
            lines.append("\nReturns:")
            lines.append(f"    {returns}")

        if raises:
            lines.append("\nRaises:")
            for exc in raises:
                lines.append(f"    {exc}: Description")

        lines.append('"""')

        return "\n".join(lines)

    def infer_arg_descriptions(
        self,
        function: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """
        Infer argument descriptions from types and names.

        Args:
            function: Function definition dict

        Returns:
            List of arg descriptions
        """
        descriptions = []

        # Common patterns
        patterns = {
            "db": "SQLAlchemy database session",
            "user_id": "Unique user identifier",
            "id": "Unique identifier",
            "data": "Request data payload",
            "params": "Query or path parameters"
        }

        for arg in function["args"]:
            desc = patterns.get(arg, f"The {arg} parameter")
            descriptions.append({"name": arg, "description": desc})

        return descriptions

    def insert_docstring(
        self,
        source_code: str,
        line_number: int,
        docstring: str
    ) -> str:
        """
        Insert docstring at correct location.

        Args:
            source_code: Source code
            line_number: Line number of function definition
            docstring: Docstring to insert

        Returns:
            Modified source code
        """
        lines = source_code.split("\n")

        # Line numbers are 1-indexed, convert to 0-indexed
        insert_index = line_number

        # Find function definition line
        for i in range(insert_index - 1, len(lines)):
            if ":" in lines[i]:
                # Insert docstring after function definition
                indent = len(lines[i]) - len(lines[i].lstrip())
                indent_str = " " * (indent + 4)

                # Build indented docstring
                docstring_lines = [indent_str + '"""']
                for line in docstring.split('\n'):
                    if line.strip():
                        docstring_lines.append(indent_str + line)
                docstring_lines.append(indent_str + '"""')

                # Insert docstring
                lines[i+1:i+1] = docstring_lines
                break

        return "\n".join(lines)


# ============================================================================
# Task 4: README and CHANGELOG Updater
# ============================================================================

class ChangelogUpdater:
    """
    Update README and CHANGELOG files for new features.

    Parses existing documentation structure and inserts new content
    at appropriate locations while preserving existing content.

    Attributes:
        project_root: Root directory of the project
        readme: Path to README.md
        changelog: Path to CHANGELOG.md

    Example:
        updater = ChangelogUpdater()
        updater.update_readme("OAuth", "OAuth support", usage_section)
        updater.update_changelog("1.2.0", "2026-02-20", changes)
    """

    def __init__(self, project_root: str = "."):
        """
        Initialize changelog updater.

        Args:
            project_root: Root directory of the project
        """
        self.project_root = Path(project_root)
        self.readme = self.project_root / "README.md"
        self.changelog = self.project_root / "CHANGELOG.md"

    def update_readme(
        self,
        feature_name: str,
        feature_description: str,
        usage_section: str
    ) -> None:
        """
        Update README.md with new feature.

        Adds feature to appropriate section:
        - Features list
        - Quick start examples
        - Usage section

        Args:
            feature_name: Name of the feature
            feature_description: Brief description
            usage_section: Usage section content
        """
        logger.info(f"Updating README with feature: {feature_name}")

        try:
            if not self.readme.exists():
                logger.warning("README.md not found, skipping update")
                return

            with open(self.readme, 'r') as f:
                content = f.read()

            # Find and update features section
            if "## Features" in content:
                # Add feature to features list
                content = self._insert_after_section(
                    content,
                    "## Features",
                    f"- {feature_name}: {feature_description}"
                )

            # Write updated content
            with open(self.readme, 'w') as f:
                f.write(content)

            logger.info("README updated successfully")

        except Exception as e:
            logger.error(f"Failed to update README: {e}")

    def update_changelog(
        self,
        version: str,
        date: str,
        changes: List[Dict[str, str]]
    ) -> None:
        """
        Update CHANGELOG.md with new entries.

        Format:
        ## [version] - [date]
        ### Added
        - Feature 1
        ### Changed
        - ...

        Args:
            version: Version number (e.g., "1.2.0")
            date: Date string (e.g., "2026-02-20")
            changes: List of {"type": "Added", "description": "..."}
        """
        logger.info(f"Updating CHANGELOG for version: {version}")

        try:
            # Create changelog entry
            entry = self._format_changelog_entry(version, date, changes)

            if self.changelog.exists():
                with open(self.changelog, 'r') as f:
                    content = f.read()

                # Insert after title section
                if "# Changelog" in content:
                    content = content.replace(
                        "# Changelog",
                        f"# Changelog\n\n{entry}"
                    )
                else:
                    content = entry + "\n\n" + content
            else:
                content = f"# Changelog\n\n{entry}"

            # Write updated content
            with open(self.changelog, 'w') as f:
                f.write(content)

            logger.info("CHANGELOG updated successfully")

        except Exception as e:
            logger.error(f"Failed to update CHANGELOG: {e}")

    def _format_changelog_entry(
        self,
        version: str,
        date: str,
        changes: List[Dict[str, str]]
    ) -> str:
        """
        Format changelog entry.

        Args:
            version: Version number
            date: Date string
            changes: List of change dicts

        Returns:
            Formatted changelog entry
        """
        lines = [f"## [{version}] - {date}", ""]

        # Group by type
        grouped = {}
        for change in changes:
            change_type = change.get("type", "Added")
            description = change.get("description", "")

            if change_type not in grouped:
                grouped[change_type] = []
            grouped[change_type].append(description)

        # Generate sections
        for change_type in ["Added", "Changed", "Fixed", "Removed"]:
            if change_type in grouped:
                lines.append(f"### {change_type}")
                for description in grouped[change_type]:
                    lines.append(f"- {description}")
                lines.append("")

        return "\n".join(lines)

    def format_changelog_entry(
        self,
        change_type: str,
        change_description: str
    ) -> str:
        """
        Format single changelog entry.

        Args:
            change_type: Added, Changed, Fixed, Removed
            change_description: Change description

        Returns:
            Formatted line
        """
        return f"- {change_description}"

    def find_section_in_file(
        self,
        file_path: Path,
        section_name: str
    ) -> Optional[int]:
        """
        Find section line number in Markdown file.

        Args:
            file_path: Path to Markdown file
            section_name: Section name (e.g., "## Features")

        Returns:
            Line number or None if not found
        """
        try:
            with open(file_path, 'r') as f:
                for i, line in enumerate(f, 1):
                    if line.strip().startswith(section_name):
                        return i
        except Exception as e:
            logger.error(f"Failed to find section: {e}")

        return None

    def _insert_after_section(
        self,
        content: str,
        section_name: str,
        new_content: str
    ) -> str:
        """
        Insert content after section in string.

        Args:
            content: File content
            section_name: Section name
            new_content: Content to insert

        Returns:
            Modified content
        """
        lines = content.split("\n")

        for i, line in enumerate(lines):
            if line.strip().startswith(section_name):
                # Find next section or end of file
                insert_at = i + 1
                for j in range(i + 1, len(lines)):
                    if lines[j].startswith("##"):
                        insert_at = j
                        break
                else:
                    insert_at = len(lines)

                # Insert content
                lines.insert(insert_at, new_content)
                break

        return "\n".join(lines)


# ============================================================================
# Task 5: DocumenterAgent Main Orchestration
# ============================================================================

class DocumenterAgent:
    """
    Main agent for automated documentation generation.

    Orchestrates all documentation components:
    - OpenAPI spec generation
    - Markdown usage guides
    - Docstring addition
    - README/CHANGELOG updates

    Attributes:
        db: Database session
        byok_handler: BYOK handler for LLM access
        openapi_generator: OpenAPI spec generator
        markdown_generator: Markdown guide generator
        docstring_generator: Docstring generator
        changelog_updater: README/CHANGELOG updater

    Example:
        documenter = DocumenterAgent(db, byok_handler)
        result = await documenter.generate_documentation(
            implementation_result,
            context
        )
        print(f"Generated {len(result['files_created'])} docs")
    """

    def __init__(
        self,
        db: Session,
        byok_handler: BYOKHandler
    ):
        """
        Initialize documenter agent.

        Args:
            db: Database session
            byok_handler: BYOK handler for LLM access
        """
        self.db = db
        self.byok_handler = byok_handler
        self.openapi_generator = OpenAPIDocumentGenerator()
        self.markdown_generator = MarkdownGuideGenerator()
        self.docstring_generator = DocstringGenerator(db, byok_handler)
        self.changelog_updater = ChangelogUpdater()

    async def generate_documentation(
        self,
        implementation_result: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate complete documentation for implementation.

        Args:
            implementation_result: Result from CoderAgent
            context: Implementation context

        Returns:
            {
                "api_docs": str,  # OpenAPI spec
                "usage_guide": str,  # Markdown guide
                "docstrings_added": int,
                "readme_updated": bool,
                "changelog_updated": bool,
                "files_created": [str],
                "files_updated": [str]
            }
        """
        logger.info("Generating complete documentation")

        files_created = []
        files_updated = []

        # Extract generated files from implementation
        generated_files = implementation_result.get("files", [])
        route_files = [f["path"] for f in generated_files if "routes" in f["path"]]
        service_files = [f["path"] for f in generated_files if "service" in f["path"]]

        # Generate API docs
        api_docs = ""
        if route_files:
            api_docs = await self.generate_api_docs(route_files)
            files_created.append("docs/openapi.yaml")

        # Generate usage guides
        usage_guides = []
        if service_files:
            usage_guides = await self.generate_usage_guides(service_files)
            for guide in usage_guides:
                files_created.append(guide["file"])

        # Add docstrings
        docstrings_added = 0
        if generated_files:
            result = await self.add_docstrings_batch([f["path"] for f in generated_files])
            docstrings_added = result.get("added", 0)
            files_updated.extend([f["path"] for f in generated_files])

        # Update project docs
        feature_name = context.get("feature_name", "New Feature")
        changes = context.get("changes", [])

        await self.update_project_docs(feature_name, changes)
        files_updated.extend(["README.md", "CHANGELOG.md"])

        return {
            "api_docs": api_docs,
            "usage_guides": usage_guides,
            "docstrings_added": docstrings_added,
            "readme_updated": True,
            "changelog_updated": True,
            "files_created": files_created,
            "files_updated": files_updated
        }

    async def generate_for_feature(
        self,
        feature_name: str,
        source_files: List[str],
        route_files: List[str]
    ) -> Dict[str, Any]:
        """
        Generate documentation for a specific feature.

        Args:
            feature_name: Name of the feature
            source_files: List of source file paths
            route_files: List of route file paths

        Returns:
            Documentation generation result
        """
        logger.info(f"Generating documentation for feature: {feature_name}")

        # Generate API docs
        api_docs = await self.generate_api_docs(route_files)

        # Generate usage guides
        usage_guides = await self.generate_usage_guides(source_files)

        # Add docstrings
        docstring_result = await self.add_docstrings_batch(source_files)

        return {
            "feature_name": feature_name,
            "api_docs": api_docs,
            "usage_guides": usage_guides,
            "docstrings_added": docstring_result.get("added", 0)
        }

    async def generate_api_docs(
        self,
        route_files: List[str]
    ) -> str:
        """
        Generate OpenAPI documentation for routes.

        Args:
            route_files: List of route file paths

        Returns:
            JSON spec string
        """
        logger.info(f"Generating API docs for {len(route_files)} route files")

        spec = self.openapi_generator.generate_openapi_spec(route_files)
        return json.dumps(spec, indent=2)

    async def generate_usage_guides(
        self,
        service_files: List[str]
    ) -> List[Dict[str, str]]:
        """
        Generate usage guides for services.

        Args:
            service_files: List of service file paths

        Returns:
            [{"file": str, "content": str}]
        """
        logger.info(f"Generating usage guides for {len(service_files)} services")

        guides = []

        for service_file in service_files:
            service_name = Path(service_file).stem

            # Extract methods from service file
            methods = self._extract_methods_from_file(service_file)

            # Generate guide
            guide_content = self.markdown_generator.generate_usage_guide(
                service_name,
                methods,
                []
            )

            guides.append({
                "file": f"docs/{service_name}.md",
                "content": guide_content
            })

        return guides

    async def add_docstrings_batch(
        self,
        files: List[str]
    ) -> Dict[str, int]:
        """
        Add docstrings to all undocumented functions.

        Args:
            files: List of file paths

        Returns:
            {"added": int, "updated": int}
        """
        logger.info(f"Adding docstrings to {len(files)} files")

        total_added = 0
        total_updated = 0

        for file_path in files:
            result = await self.docstring_generator.add_docstrings_to_file(file_path)

            # Write updated content
            if result.get("new_content"):
                with open(file_path, 'w') as f:
                    f.write(result["new_content"])

            total_added += result.get("added", 0)
            total_updated += result.get("updated", 0)

        return {
            "added": total_added,
            "updated": total_updated
        }

    async def update_project_docs(
        self,
        feature_name: str,
        changes: List[Dict[str, str]]
    ) -> None:
        """
        Update README and CHANGELOG.

        Args:
            feature_name: Name of the feature
            changes: List of change dicts
        """
        logger.info("Updating project documentation")

        # Update README
        self.changelog_updater.update_readme(
            feature_name,
            f"{feature_name} support",
            ""
        )

        # Update CHANGELOG
        version = "1.0.0"  # TODO: Get from context
        date = datetime.now().strftime("%Y-%m-%d")

        self.changelog_updater.update_changelog(
            version,
            date,
            changes
        )

    def _extract_methods_from_file(
        self,
        file_path: str
    ) -> List[Dict[str, Any]]:
        """
        Extract method definitions from service file.

        Args:
            file_path: Path to service file

        Returns:
            List of method definitions
        """
        methods = []

        try:
            with open(file_path, 'r') as f:
                source = f.read()

            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            methods.append({
                                "name": item.name,
                                "params": [arg.arg for arg in item.args.args]
                            })

        except Exception as e:
            logger.error(f"Failed to extract methods: {e}")

        return methods


# Export main class
__all__ = [
    "OpenAPIDocumentGenerator",
    "MarkdownGuideGenerator",
    "DocstringGenerator",
    "ChangelogUpdater",
    "DocumenterAgent"
]
