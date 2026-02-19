"""
Skill Parser for OpenClaw SKILL.md files.

Provides lenient parsing with auto-fix for malformed community skills.
Extracts YAML frontmatter and Markdown body, detects skill type, and
extracts function signatures from Python code.

Extended for Python package support (Phase 35):
- Extracts packages from SKILL.md frontmatter
- Validates package format using packaging.requirements.Requirement
- Returns packages list in parsed skill metadata

Extended for npm package support (Phase 36):
- Extracts node_packages from SKILL.md frontmatter
- Parses package_manager field (npm, yarn, pnpm)
- Validates npm package format (name@version or name@range)
- Distinguishes Python vs Node.js packages

Reference: Phase 14 Plan 01 - Skill Adapter
Reference: Phase 35 Plan 06 - Skill Integration
Reference: Phase 36 Plan 06 - npm Skill Integration
"""

import ast
import frontmatter
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from packaging.requirements import Requirement

logger = logging.getLogger(__name__)


class SkillParser:
    """
    Lenient parser for OpenClaw SKILL.md files.

    Handles malformed YAML frontmatter with auto-fix capabilities:
    - Missing name: Use "Unnamed Skill"
    - Missing description: Auto-generate from first line of body
    - Invalid YAML: Log warning, skip file with clear message
    - Version-agnostic: Don't validate openclaw_version field

    Auto-detects skill type:
    - prompt_only: Natural language instructions
    - python_code: Contains ```python fence blocks

    Extended for Python package support (Phase 35):
    - Extracts packages from SKILL.md frontmatter
    - Validates package format using Requirement()
    - Returns packages list in parsed skill metadata

    Extended for npm package support (Phase 36):
    - Extracts node_packages from SKILL.md frontmatter
    - Parses package_manager field (npm, yarn, pnpm)
    - Validates npm package format (name@version or name@range)
    - Returns node_packages and package_manager in parsed skill metadata

    Example SKILL.md with Python packages:
    ```yaml
    ---
    name: "Data Processing Skill"
    packages:
      - numpy==1.21.0
      - pandas>=1.3.0
      - requests
    ---
    ```

    Example SKILL.md with npm packages:
    ```yaml
    ---
    name: "Web Scraper Skill"
    node_packages:
      - lodash@4.17.21
      - express@^4.18.0
      - axios
    package_manager: npm
    ---
    ```
    """

    def parse_skill_file(self, file_path: str) -> Tuple[Dict[str, Any], str]:
        """
        Parse SKILL.md with YAML frontmatter and Markdown body.

        Extended to support Python packages in frontmatter:
        ```yaml
        ---
        name: "Data Processing Skill"
        packages:
          - numpy==1.21.0
          - pandas>=1.3.0
          - requests
        ---
        ```

        Args:
            file_path: Path to SKILL.md file

        Returns:
            Tuple of (metadata_dict, markdown_body)
            - metadata_dict includes 'packages' key with List[str]

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        try:
            file_path_obj = Path(file_path)

            if not file_path_obj.exists():
                raise FileNotFoundError(f"Skill file not found: {file_path}")

            with open(file_path_obj, 'r', encoding='utf-8') as f:
                content = f.read()

            # Use python-frontmatter to split frontmatter
            # Handles missing --- gracefully
            post = frontmatter.loads(content)

            metadata = post.metadata
            body = post.content

            # Extract packages from frontmatter (Phase 35)
            packages = self._extract_packages(metadata, file_path)
            metadata['packages'] = packages

            # Extract node_packages from frontmatter (Phase 36)
            node_packages = self._extract_node_packages(metadata, file_path)
            metadata['node_packages'] = node_packages

            # Extract package_manager (Phase 36)
            package_manager = self._extract_package_manager(metadata, file_path)
            metadata['package_manager'] = package_manager

            # Auto-fix missing required fields
            metadata = self._auto_fix_metadata(metadata, body, file_path)

            # Detect skill type
            skill_type = self._detect_skill_type(metadata, body)
            metadata['skill_type'] = skill_type

            logger.info(
                f"Parsed skill '{metadata.get('name', 'Unknown')}' from {file_path} "
                f"(type: {skill_type}, packages: {len(packages)})"
            )

            return metadata, body

        except FileNotFoundError:
            logger.warning(f"File not found: {file_path}")
            # Return minimal metadata to allow import to continue
            return {"name": "Unnamed Skill", "description": "", "skill_type": "prompt_only", "packages": [], "node_packages": [], "package_manager": "npm"}, ""
        except Exception as e:
            logger.warning(f"Failed to parse {file_path}: {e}")
            # Return minimal metadata to allow import to continue
            return {"name": "Unnamed Skill", "description": "", "skill_type": "prompt_only", "packages": [], "node_packages": [], "package_manager": "npm"}, ""

    def _auto_fix_metadata(
        self,
        metadata: Dict[str, Any],
        body: str,
        file_path: str
    ) -> Dict[str, Any]:
        """
        Apply common fixes for missing required fields.

        Args:
            metadata: Parsed YAML frontmatter
            body: Markdown body
            file_path: File path for logging

        Returns:
            Fixed metadata dictionary
        """
        # Missing name
        if not metadata.get("name"):
            metadata["name"] = "Unnamed Skill"
            logger.info(f"{file_path}: Missing 'name', using 'Unnamed Skill'")

        # Missing description - use first line of body
        if not metadata.get("description"):
            first_line = body.strip().split('\n')[0] if body else ""
            # Remove markdown headers (#) from first line
            first_line = first_line.lstrip('#').strip()

            metadata["description"] = first_line[:100]  # Truncate to 100 chars
            if not metadata["description"]:
                metadata["description"] = "No description available"

            logger.info(f"{file_path}: Missing 'description', auto-generated from body")

        return metadata

    def _extract_packages(self, metadata: Dict[str, Any], file_path: str) -> List[str]:
        """
        Extract Python packages from SKILL.md frontmatter.

        Validates package format using packaging.requirements.Requirement.
        Invalid package formats are filtered out with error logging.

        Args:
            metadata: Parsed YAML frontmatter
            file_path: File path for logging

        Returns:
            List of valid package requirement strings (e.g., ["numpy==1.21.0", "pandas>=1.3.0"])
        """
        # Extract packages from frontmatter
        packages = metadata.get('packages', [])

        # Normalize packages (ensure list)
        if not isinstance(packages, list):
            logger.warning(
                f"packages field must be a list in {file_path}, got {type(packages).__name__}"
            )
            packages = []

        # Validate package format using packaging.requirements.Requirement
        valid_packages = []
        for pkg in packages:
            try:
                # This will raise InvalidRequirement if format is invalid
                Requirement(pkg)
                valid_packages.append(pkg)
            except Exception as e:
                logger.error(
                    f"Invalid package requirement '{pkg}' in {file_path}: {e}"
                )

        logger.debug(
            f"Extracted {len(valid_packages)}/{len(packages)} valid packages from {file_path}"
        )

        return valid_packages

    def _extract_node_packages(self, metadata: Dict[str, Any], file_path: str) -> List[str]:
        """
        Extract npm packages from SKILL.md frontmatter.

        Validates npm package format (name@version or name@range).
        Invalid package formats are filtered out with error logging.

        Args:
            metadata: Parsed YAML frontmatter
            file_path: File path for logging

        Returns:
            List of valid npm package specifiers (e.g., ["lodash@4.17.21", "express@^4.18.0"])
        """
        # Extract node_packages from frontmatter
        node_packages = metadata.get('node_packages', [])

        # Normalize node_packages (ensure list)
        if not isinstance(node_packages, list):
            logger.warning(
                f"node_packages field must be a list in {file_path}, got {type(node_packages).__name__}"
            )
            node_packages = []

        # Validate npm package format
        valid_node_packages = []
        for pkg in node_packages:
            if self._validate_npm_package_format(pkg):
                valid_node_packages.append(pkg)
            else:
                logger.error(
                    f"Invalid npm package specifier '{pkg}' in {file_path}. "
                    f"Expected format: name@version or name@range (e.g., lodash@4.17.21, express@^4.18.0)"
                )

        logger.debug(
            f"Extracted {len(valid_node_packages)}/{len(node_packages)} valid npm packages from {file_path}"
        )

        return valid_node_packages

    def _validate_npm_package_format(self, package: str) -> bool:
        """
        Validate npm package format.

        Args:
            package: Package specifier (e.g., "lodash@4.17.21", "express@^4.18.0", "@scope/name@1.0.0")

        Returns:
            True if format is valid, False otherwise
        """
        if not package or not isinstance(package, str):
            return False

        # Trim whitespace
        package = package.strip()

        # Empty package
        if not package:
            return False

        # Check for scoped packages (@scope/name or @scope/name@version)
        if package.startswith('@'):
            # Scoped package must have at least @scope/name
            if '@' not in package[1:]:  # Check after the initial @
                return False
            return True

        # Check for regular packages (name or name@version or name@range)
        # Allow alphanumeric, hyphens, underscores, @ for version, and special semver chars
        valid_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.@^~*+<>|")
        return all(c in valid_chars for c in package)

    def _extract_package_manager(self, metadata: Dict[str, Any], file_path: str) -> str:
        """
        Extract package_manager field from SKILL.md frontmatter.

        Args:
            metadata: Parsed YAML frontmatter
            file_path: File path for logging

        Returns:
            Package manager string ("npm", "yarn", or "pnpm", defaults to "npm")
        """
        package_manager = metadata.get('package_manager', 'npm')

        # Validate package manager
        valid_managers = ['npm', 'yarn', 'pnpm']
        if package_manager not in valid_managers:
            logger.warning(
                f"Invalid package_manager '{package_manager}' in {file_path}. "
                f"Valid options: {valid_managers}. Defaulting to 'npm'."
            )
            return 'npm'

        return package_manager

    def _detect_skill_type(self, metadata: Dict[str, Any], body: str) -> str:
        """
        Detect skill type from content.

        Args:
            metadata: Skill metadata
            body: Markdown body

        Returns:
            "prompt_only" or "python_code"
        """
        # Check for ```python fence blocks (case insensitive)
        body_lower = body.lower()
        if "```python" in body_lower:
            return "python_code"

        # Check for explicit Python code indicator in metadata
        if metadata.get("type") == "python" or metadata.get("language") == "python":
            return "python_code"

        # Default to prompt_only
        return "prompt_only"

    def extract_python_code(self, body: str) -> List[str]:
        """
        Extract ```python blocks from markdown body.

        Args:
            body: Markdown body content

        Returns:
            List of Python code blocks (strings)
        """
        code_blocks = []

        lines = body.split('\n')
        in_python_block = False
        current_block = []

        for line in lines:
            if line.strip().startswith('```python') or line.strip().startswith('``` Python'):
                in_python_block = True
                current_block = []
                continue

            if in_python_block and line.strip() == '```':
                # End of code block
                code_blocks.append('\n'.join(current_block))
                in_python_block = False
                current_block = []
                continue

            if in_python_block:
                current_block.append(line)

        # Handle unclosed blocks (graceful degradation)
        if current_block and in_python_block:
            logger.warning("Found unclosed ```python block, treating as complete")
            code_blocks.append('\n'.join(current_block))

        return code_blocks

    def extract_function_signatures(self, code: str) -> List[Dict[str, Any]]:
        """
        Extract function definitions from Python code using AST.

        Args:
            code: Python source code

        Returns:
            List of {"name": str, "args": List[str], "docstring": str}
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            logger.error(f"Invalid Python syntax: {e}")
            return []

        functions = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                args = [arg.arg for arg in node.args.args]
                docstring = ast.get_docstring(node)

                functions.append({
                    "name": node.name,
                    "args": args,
                    "docstring": docstring or ""
                })

        return functions

    def parse_batch(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        Parse multiple SKILL.md files with summary statistics.

        Args:
            file_paths: List of file paths to parse

        Returns:
            Dict with:
                - skills: List of (metadata, body) tuples
                - success_count: Number of successfully parsed files
                - failure_count: Number of failed files
                - errors: List of error messages
        """
        skills = []
        errors = []

        for file_path in file_paths:
            try:
                metadata, body = self.parse_skill_file(file_path)
                skills.append((metadata, body))
            except Exception as e:
                errors.append(f"{file_path}: {str(e)}")
                logger.error(f"Failed to parse {file_path}: {e}")

        return {
            "skills": skills,
            "success_count": len(skills),
            "failure_count": len(errors),
            "errors": errors
        }
