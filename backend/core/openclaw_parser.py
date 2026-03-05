"""
OpenClaw SKILL.md Parser

Parse YAML frontmatter and Markdown body from OpenClaw SKILL.md files.
Extracts metadata, Python code blocks, and dependency declarations.

Security-critical: This parser is the foundation for all OpenClaw skill imports.
Invalid parsing could lead to security vulnerabilities or data loss.
"""

import frontmatter
import ast
import re
from typing import Dict, Any, List, Tuple


class OpenClawParser:
    """
    Parse OpenClaw SKILL.md format with YAML frontmatter and Markdown body.

    Format specification:
    ---
    name: my-skill
    description: Does something
    author: @username
    version: 1.0.0
    metadata:
      openclaw:
        install:
          - id: uv
            kind: uv
            package: nano-pdf
    ---
    # Skill Description
    Markdown body content...
    """

    def parse_skill_md(self, content: str) -> Dict[str, Any]:
        """
        Parse SKILL.md with YAML frontmatter and Markdown body.

        Args:
            content: Raw SKILL.md file content

        Returns:
            Dict with keys:
                - name (str): Skill name from frontmatter
                - description (str): Skill description from frontmatter
                - author (str): Author username (default: "Unknown")
                - version (str): Version string (default: "1.0.0")
                - homepage (str|None): Homepage URL
                - metadata (dict): Full original frontmatter metadata
                - body (str): Markdown body content
                - code_blocks (list[str]): Extracted Python code blocks
                - dependencies (dict): Parsed dependencies
                - raw_md (str): Original SKILL.md content

        Raises:
            ValueError: If required fields missing or frontmatter malformed
        """
        try:
            post = frontmatter.loads(content)
            metadata = post.metadata
            body = post.content

            # Validate required fields
            required_fields = ['name', 'description']
            missing_fields = [field for field in required_fields if field not in metadata]
            if missing_fields:
                raise ValueError(
                    f"Missing required fields in frontmatter: {', '.join(missing_fields)}. "
                    f"SKILL.md must include: {', '.join(required_fields)}"
                )

            # Extract Python code blocks from markdown body
            code_blocks = self._extract_python_blocks(body)

            # Extract dependencies from metadata
            dependencies = self._extract_dependencies(metadata)

            return {
                'name': metadata.get('name'),
                'description': metadata.get('description'),
                'author': metadata.get('author', 'Unknown'),
                'version': metadata.get('version', '1.0.0'),
                'homepage': metadata.get('homepage'),
                'metadata': metadata,  # Full original metadata
                'body': body,
                'code_blocks': code_blocks,
                'dependencies': dependencies,
                'raw_md': content
            }

        except ValueError:
            # Re-raise ValueErrors (our custom validation errors)
            raise
        except Exception as e:
            # Wrap other exceptions (frontmatter parsing errors, etc.)
            raise ValueError(f"Failed to parse SKILL.md: {str(e)}")

    def _extract_python_blocks(self, markdown: str) -> List[str]:
        """
        Extract Python code blocks from markdown body.

        Pattern: ```python ... ```

        Args:
            markdown: Markdown body content

        Returns:
            List of Python code blocks (strings). Empty list if no blocks found.
        """
        pattern = r'```python\n(.*?)```'
        blocks = re.findall(pattern, markdown, re.DOTALL)
        return blocks

    def validate_python_syntax(self, code: str) -> Tuple[bool, str]:
        """
        Validate Python syntax for extracted code blocks.

        Args:
            code: Python code string to validate

        Returns:
            Tuple (is_valid, error_message):
                - (True, "") if code is syntactically valid
                - (False, "Line {lineno}: {msg}") if syntax error found
        """
        try:
            ast.parse(code)
            return True, ""
        except SyntaxError as e:
            return False, f"Line {e.lineno}: {e.msg}"

    def extract_npm_dependencies(self, component_code: str, component_name: str) -> List[str]:
        """
        Extract npm package names from canvas component code.

        Parses import statements and require() calls to identify npm packages.

        Args:
            component_code: React/JavaScript component code
            component_name: Component name (for logging)

        Returns:
            Sorted list of unique npm package names (with or without scope)
        """
        dependencies = set()

        # Match ES6 import statements
        # Pattern 1: import X from 'package-name'
        # Pattern 2: import { X } from 'package-name'
        # Pattern 3: import * as X from 'package-name'
        import_patterns = [
            r'import\s+.*?\s+from\s+["\']((?:@[\w-]+/)?[\w-]*)["\']',
            r'import\s+["\']((?:@[\w-]+/)?[\w-]*)["\']'
        ]

        for pattern in import_patterns:
            matches = re.findall(pattern, component_code)
            for match in matches:
                # Filter out relative imports (starting with . or /)
                if not match.startswith('.') and not match.startswith('/'):
                    dependencies.add(match)

        # Match CommonJS require() statements
        require_pattern = r'require\(["\']((?:@[\w-]+/)?[\w-]*)["\']\)'
        require_matches = re.findall(require_pattern, component_code)
        for match in require_matches:
            # Filter out relative imports
            if not match.startswith('.') and not match.startswith('/'):
                dependencies.add(match)

        # Match package.json dependencies if included in code
        if 'package.json' in component_code or 'dependencies' in component_code:
            try:
                # Try to extract package.json object
                json_pattern = r'"dependencies"\s*:\s*\{([^}]+)\}'
                json_match = re.search(json_pattern, component_code)
                if json_match:
                    deps_str = json_match.group(1)
                    # Extract package names from "package": "version" pairs
                    dep_pattern = r'"((?:@[\w-]+/)?[\w-]+)"\s*:'
                    dep_matches = re.findall(dep_pattern, deps_str)
                    dependencies.update(dep_matches)
            except Exception:
                # Silently fail if package.json parsing fails
                pass

        return sorted(dependencies)

    def _extract_dependencies(self, metadata: Dict) -> Dict[str, List[str]]:
        """
        Extract dependency declarations from metadata.

        Checks:
        1. metadata['requirements'] list (Python packages)
        2. metadata['metadata']['openclaw']['install'] for uv install steps
        3. metadata['node_packages'] for npm packages

        Args:
            metadata: Parsed frontmatter metadata dict

        Returns:
            Dict with keys:
                - python (list[str]): Python package names
                - npm (list[str]): NPM package names
                - bins (list[str]): Binary dependencies
        """
        deps = {
            'python': [],
            'npm': [],
            'bins': []
        }

        # Check for requirements in metadata
        if 'requirements' in metadata:
            reqs = metadata['requirements']
            if isinstance(reqs, list):
                # Filter to ensure all items are strings
                python_reqs = [str(req) for req in reqs if isinstance(req, (str, int, float))]
                deps['python'].extend(python_reqs)

        # Check for node_packages in metadata (npm packages)
        if 'node_packages' in metadata:
            node_pkgs = metadata['node_packages']
            if isinstance(node_pkgs, list):
                # Filter to ensure all items are strings
                npm_reqs = [str(pkg) for pkg in node_pkgs if isinstance(pkg, (str, int, float))]
                deps['npm'].extend(npm_reqs)

        # Check for openclaw metadata.install section
        if 'metadata' in metadata and isinstance(metadata['metadata'], dict):
            openclaw_meta = metadata['metadata'].get('openclaw', {})
            if isinstance(openclaw_meta, dict):
                install_steps = openclaw_meta.get('install', [])
                if isinstance(install_steps, list):
                    for step in install_steps:
                        if isinstance(step, dict):
                            # Extract uv package names
                            if step.get('kind') == 'uv':
                                pkg = step.get('package')
                                if pkg and isinstance(pkg, str):
                                    deps['python'].append(pkg)

                            # Extract npm package names
                            if step.get('kind') == 'npm':
                                pkg = step.get('package')
                                if pkg and isinstance(pkg, str):
                                    deps['npm'].append(pkg)

                            # Extract binary dependencies
                            if 'bins' in step and isinstance(step['bins'], list):
                                bins = [str(b) for b in step['bins'] if isinstance(b, (str, int, float))]
                                deps['bins'].extend(bins)

        return deps
