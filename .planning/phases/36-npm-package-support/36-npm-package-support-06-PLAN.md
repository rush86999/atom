---
phase: 36-npm-package-support
plan: 06
type: execute
wave: 3
depends_on: [36-npm-package-support-01, 36-npm-package-support-02, 36-npm-package-support-03, 36-npm-package-support-04]
files_modified:
  - backend/core/skill_parser.py
  - backend/core/skill_adapter.py
  - backend/core/skill_registry_service.py
  - backend/tests/test_npm_skill_integration.py
autonomous: true

must_haves:
  truths:
    - "SKILL.md supports node_packages field for npm dependencies"
    - "Skill adapter parses node_packages and distinguishes from python_packages"
    - "npm packages use NpmPackageInstaller for installation"
    - "Node.js skills use execute_nodejs for execution"
    - "npm package governance checks applied during skill activation"
    - "npm package installations and governance decisions logged to AuditLog"
  artifacts:
    - path: backend/core/skill_parser.py
      contains: parse_node_packages, node_packages field parsing
    - path: backend/core/skill_adapter.py
      contains: NodeJsSkillAdapter, install_npm_dependencies
    - path: backend/core/skill_registry_service.py
      contains: npm package installation workflow with audit_service.create_package_audit calls
    - path: backend/tests/test_npm_skill_integration.py
      contains: test_skill_with_npm_packages, test_nodejs_skill_execution, test_audit_logging
  key_links:
    - from: backend/core/skill_adapter.py
      to: backend/core/npm_package_installer.py
      via: NpmPackageInstaller.install_packages()
      pattern: NpmPackageInstaller
    - from: backend/core/skill_adapter.py
      to: backend/core/package_governance_service.py
      via: check_package_permission(package_type="npm")
      pattern: check_package_permission.*npm
    - from: backend/core/skill_registry_service.py
      to: backend/core/audit_service.py
      via: audit_service.create_package_audit()
      pattern: create_package_audit
---

<objective>
Integrate npm package support into the community skills system, enabling SKILL.md files to declare Node.js dependencies and execute Node.js-based skills.

**Purpose:** Allow community skills to specify npm packages in SKILL.md (matching OpenClaw format), install them with governance checks, and execute Node.js skill code.

**Output:** Extended skill parser for node_packages, NodeJsSkillAdapter, updated skill registry workflow, comprehensive integration tests.

</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/phases/36-npm-package-support/36-RESEARCH.md
@backend/core/skill_parser.py (extend for node_packages)
@backend/core/skill_adapter.py (add NodeJsSkillAdapter)
@backend/core/skill_registry_service.py (npm package workflow)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Extend skill parser for node_packages field</name>
  <files>backend/core/skill_parser.py</files>
  <action>
    Extend SkillParser to handle node_packages in SKILL.md files:

    1. Add node_packages parsing after python_packages:
       ```python
       def parse_node_packages(self, skill_content: str) -> List[str]:
           \"\"\"Parse node_packages field from SKILL.md.

           Expected format:
           node_packages:
             - lodash@4.17.21
             - express@^4.18.0
           \"\"\"
           yaml_content = self._extract_yaml_frontmatter(skill_content)
           if not yaml_content:
               return []

           data = yaml.safe_load(yaml_content)
           return data.get('node_packages', [])
       ```

    2. Update parse_skill_metadata to include node_packages:
       ```python
       def parse_skill_metadata(self, skill_content: str) -> Dict[str, Any]:
           # ... existing parsing ...
           metadata['node_packages'] = self.parse_node_packages(skill_content)
           return metadata
       ```

    3. Add validation for package format:
       - Validate npm specifier format (name@version or name@range)
       - Invalid format logged and skipped

    4. Support package_manager field:
       ```python
       def parse_package_manager(self, skill_content: str) -> str:
           \"\"\"Parse package_manager field (npm, yarn, pnpm). Defaults to npm.\"\"\"
           yaml_content = self._extract_yaml_frontmatter(skill_content)
           data = yaml.safe_load(yaml_content) if yaml_content else {}
           return data.get('package_manager', 'npm')
       ```

    CRITICAL: Maintain backward compatibility (node_packages is optional)
  </action>
  <verify>
    grep -n "parse_node_packages\|node_packages" /Users/rushiparikh/projects/atom/backend/core/skill_parser.py
  </verify>
  <done>
    SkillParser parses node_packages and package_manager from SKILL.md YAML frontmatter
  </done>
</task>

<task type="auto">
  <name>Task 2: Create NodeJsSkillAdapter for npm-based skills</name>
  <files>backend/core/skill_adapter.py</files>
  <action>
    Create NodeJsSkillAdapter class following PythonSkillAdapter pattern:

    1. Add after PythonSkillAdapter:
       ```python
       class NodeJsSkillAdapter(BaseTool):
           \"\"\"Adapter for Node.js-based community skills with npm packages.\"\"\"

           name: str = "nodejs_skill"
           description: str = "Execute Node.js skill code with npm packages"

           def __init__(
               self,
               skill_id: str,
               code: str,
               node_packages: List[str],
               package_manager: str = "npm",
               agent_id: Optional[str] = None
           ):
               self.skill_id = skill_id
               self.code = code
               self.node_packages = node_packages
               self.package_manager = package_manager
               self.agent_id = agent_id
               self._installer = None

           @property
           def installer(self):
               if self._installer is None:
                   from core.npm_package_installer import NpmPackageInstaller
                   self._installer = NpmPackageInstaller()
               return self._installer
       ```

    2. Implement _run method for LangChain BaseTool:
       ```python
       def _run(self, tool_input: Dict[str, Any], run_manager=None) -> str:
           # Install packages if image doesn't exist
           # Execute Node.js code with packages
           # Return output
       ```

    3. Implement install_npm_dependencies:
       - Check governance permissions for all packages
       - Run NpmPackageInstaller.install_packages
       - Handle script analysis warnings

    4. Implement execute_nodejs_code:
       - Call NpmPackageInstaller.execute_with_packages
       - Handle timeout and error cases

    Reference: PythonSkillAdapter structure for consistency
  </action>
  <verify>
    grep -n "NodeJsSkillAdapter" /Users/rushiparikh/projects/atom/backend/core/skill_adapter.py
  </verify>
  <done>
    NodeJsSkillAdapter created with _run, install_npm_dependencies, execute_nodejs_code methods
  </done>
</task>

<task type="auto">
  <name>Task 3: Update skill registry service for npm packages</name>
  <files>backend/core/skill_registry_service.py</files>
  <action>
    Extend SkillRegistryService to handle npm packages during skill import:

    1. Update import_skill method to detect Node.js skills:
       - Check if skill has node_packages field
       - Check if code language is JavaScript (detect via extension or shebang)

    2. Add npm package installation workflow with audit logging:
       ```python
       def _install_npm_dependencies_for_skill(
           self,
           skill_id: str,
           node_packages: List[str],
           package_manager: str,
           agent_id: str,
           db: Session
       ) -> Dict[str, Any]:
           \"\"\"Install npm packages for skill with governance checks and audit logging.\"\"\"
           from core.npm_package_installer import NpmPackageInstaller
           from core.npm_script_analyzer import NpmScriptAnalyzer
           from core.audit_service import audit_service

           # Check governance permissions with audit logging
           for pkg in node_packages:
               name, version = self._parse_npm_package(pkg)
               permission = self._governance.check_package_permission(
                   agent_id, name, version, package_type="npm", db=db
               )

               # Log governance decision to audit trail
               audit_service.create_package_audit(
                   db=db,
                   agent_id=agent_id,
                   user_id=agent_id,  # Agent as user
                   action="governance_decision",
                   package_name=name,
                   package_version=version,
                   package_type="npm",
                   skill_id=skill_id,
                   governance_decision="approved" if permission["allowed"] else "denied",
                   governance_reason=permission.get("reason", ""),
                   metadata={"package_manager": package_manager}
               )

               if not permission["allowed"]:
                   raise PermissionError(f"npm package {name}@{version} blocked: {permission['reason']}")

           # Scan for postinstall scripts
           script_analyzer = NpmScriptAnalyzer()
           script_warnings = script_analyzer.analyze_package_scripts(
               node_packages, package_manager
           )
           if script_warnings["malicious"]:
               raise SecurityError("Malicious postinstall scripts detected")

           # Install packages with audit logging
           installer = NpmPackageInstaller()
           install_result = installer.install_packages(
               skill_id=skill_id,
               packages=node_packages,
               package_manager=package_manager
           )

           # Log installation attempt to audit trail
           for pkg in node_packages:
               name, version = self._parse_npm_package(pkg)
               audit_service.create_package_audit(
                   db=db,
                   agent_id=agent_id,
                   user_id=agent_id,
                   action="install",
                   package_name=name,
                   package_version=version,
                   package_type="npm",
                   skill_id=skill_id,
                   governance_decision="approved",
                   metadata={
                       "install_success": install_result.get("success", False),
                       "image_tag": install_result.get("image_tag"),
                       "package_manager": package_manager
                   }
               )

           return install_result
       ```

       CRITICAL: Every governance decision and installation must be logged to AuditLog with agent_id, package_name, version, decision, and timestamp

    3. Update skill metadata to store package type:
       - Add package_type field to CommunitySkill model metadata
       - Store "python" or "npm" based on dependencies

    4. Update skill activation workflow:
       - For npm skills: call _install_npm_dependencies_for_skill
       - For Python skills: use existing workflow

    CRITICAL: Governance checks before installation
  </action>
  <verify>
    grep -n "_install_npm_dependencies\|package_type=\"npm\"" /Users/rushiparikh/projects/atom/backend/core/skill_registry_service.py
  </verify>
  <done>
    SkillRegistryService handles npm packages with governance checks, script analysis
  </done>
</task>

<task type="auto">
  <name>Task 4: Add skill type detection to registry</name>
  <files>backend/core/skill_registry_service.py</files>
  <action>
    Add skill type detection to determine if skill uses Python or npm packages:

    1. Implement detect_skill_type method:
       ```python
       def detect_skill_type(self, skill_content: str) -> str:
           \"\"\"Detect if skill is Python or Node.js based on content.

           Rules:
           - Has node_packages field -> 'npm'
           - Has python_packages field -> 'python'
           - Code extension .js/.mjs/.cjs -> 'npm'
           - Code extension .py -> 'python'
           - Shebang #!/usr/bin/env node -> 'npm'
           - Shebang #!/usr/bin/env python -> 'python'
           - Default: 'python'
           \"\"\"
           # Check for explicit package declarations first
           if 'node_packages:' in skill_content:
               return 'npm'
           if 'python_packages:' in skill_content:
               return 'python'

           # Check code file extension
           code_file = self._extract_code_file(skill_content)
           if code_file:
               if code_file.endswith(('.js', '.mjs', '.cjs')):
                   return 'npm'
               if code_file.endswith('.py'):
                   return 'python'

           # Check shebang
           code = self._extract_code(skill_content)
           if code:
               if code.strip().startswith('#!/usr/bin/env node'):
                   return 'npm'
               if code.strip().startswith('#!/usr/bin/env python'):
                   return 'python'

           # Default to Python for backward compatibility
           return 'python'
       ```

    2. Use detect_skill_type in import_skill workflow

    3. Store detected type in skill metadata for future reference

    This enables automatic skill type detection without explicit declaration.
  </action>
  <verify>
    grep -n "detect_skill_type" /Users/rushiparikh/projects/atom/backend/core/skill_registry_service.py
  </verify>
  <done>
    detect_skill_type method identifies Python vs Node.js skills from SKILL.md content
  </done>
</task>

<task type="auto">
  <name>Task 5: Create comprehensive integration tests</name>
  <files>backend/tests/test_npm_skill_integration.py</files>
  <action>
    Create comprehensive integration test file for npm skill support:

    1. Test file setup:
       - Import pytest, SkillParser, NodeJsSkillAdapter, SkillRegistryService
       - Mock npm installer, governance service

    2. Test cases for skill parser:
       - test_parse_node_packages_simple: Parse "lodash@4.17.21"
       - test_parse_node_packages_with_version_ranges: Parse "express@^4.18.0"
       - test_parse_package_manager_npm: Default npm
       - test_parse_package_manager_yarn: yarn package_manager
       - test_parse_package_manager_pnpm: pnpm package_manager
       - test_parse_mixed_packages: Both python_packages and node_packages

    3. Test cases for skill adapter:
       - test_nodejs_skill_adapter_install: npm packages installed
       - test_nodejs_skill_adapter_execute: Node.js code executes
       - test_nodejs_skill_adapter_governance: STUDENT blocked from npm
       - test_nodejs_skill_adapter_scripts_blocked: Malicious postinstall blocked

    4. Test cases for skill registry:
       - test_import_nodejs_skill: Skill with node_packages imported
       - test_import_nodejs_skill_governance: Approval required for npm
       - test_skill_type_detection_js_file: .js file detected as npm
       - test_skill_type_detection_node_shebang: #!/usr/bin/env node detected
       - test_mixed_python_npm_skill: Both package types supported

    5. End-to-end test:
       - test_full_npm_skill_workflow: Import -> Install -> Execute
       - test_npm_skill_with_vulnerabilities: Blocked on npm audit results
       - test_audit_logging_for_npm_install: Verify AuditLog entries created for governance decisions and installations

    Use pytest fixtures for test skills, mock services.
  </action>
  <verify>
    pytest backend/tests/test_npm_skill_integration.py -v --collect-only | grep "test_" | wc -l
  </verify>
  <done>
    16+ integration tests covering parser, adapter, registry, end-to-end workflow, and audit logging
  </done>
</task>

</tasks>

<verification>
Overall phase verification:
1. SKILL.md files with node_packages field parse correctly
2. NodeJsSkillAdapter installs npm packages and executes code
3. SkillRegistryService detects skill type (Python vs Node.js)
4. Governance checks applied before npm installation
5. All npm governance decisions and installations logged to AuditLog with agent_id, package_name, version, decision
6. All integration tests pass: pytest backend/tests/test_npm_skill_integration.py -v
</verification>

<success_criteria>
1. SkillParser.parse_node_packages extracts npm packages from SKILL.md
2. NodeJsSkillAdapter implements BaseTool._run for LangChain integration
3. SkillRegistryService._install_npm_dependencies_for_skill calls audit_service.create_package_audit for each governance decision
4. detect_skill_type identifies Python vs Node.js from code extension/shebang
5. AuditLog contains entries for all npm package operations (governance_decision, install actions)
6. 16+ integration tests covering full npm skill workflow including audit logging
7. Backward compatible with existing Python-only skills
</success_criteria>

<output>
After completion, create `.planning/phases/36-npm-package-support/36-npm-package-support-06-SUMMARY.md`
</output>
