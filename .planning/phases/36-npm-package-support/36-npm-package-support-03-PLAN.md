---
phase: 36-npm-package-support
plan: 03
type: execute
wave: 2
depends_on: [36-npm-package-support-01, 36-npm-package-support-02]
files_modified:
  - backend/core/npm_package_installer.py
  - backend/core/skill_sandbox.py
  - backend/tests/test_npm_package_installer.py
  - backend/tests/test_npm_sandbox_execution.py
autonomous: true

must_haves:
  truths:
    - "NpmPackageInstaller builds Docker images with node_modules per skill"
    - "--ignore-scripts flag used in npm install to prevent postinstall execution"
    - "HazardSandbox.execute_nodejs method runs Node.js code in isolated containers"
    - "Images tagged atom-npm-skill:{skill_id}-v1 for reusability"
    - "Non-root user (nodejs) runs code in containers"
    - "Different skills can use different versions of the same npm package without conflicts"
  artifacts:
    - path: backend/core/npm_package_installer.py
      contains: class NpmPackageInstaller, install_packages, _build_skill_image, _generate_dockerfile
    - path: backend/core/skill_sandbox.py
      contains: execute_nodejs method
    - path: backend/tests/test_npm_package_installer.py
      contains: test_install_packages, test_build_image, test_cleanup, test_package_version_isolation
    - path: backend/tests/test_npm_sandbox_execution.py
      contains: test_execute_nodejs, test_resource_limits
  key_links:
    - from: backend/core/npm_package_installer.py
      to: docker client
      via: docker.from_env().images.build()
      pattern: client\.images\.build
    - from: backend/core/skill_sandbox.py
      to: Node.js container
      via: containers.run(image=..., command=["node", "-e", ...])
      pattern: containers\.run.*node
---

<objective>
Implement npm package installation in Docker containers and Node.js code execution in HazardSandbox with security constraints.

**Purpose:** Install npm packages in per-skill Docker images (node_modules isolation) and execute Node.js skill code with network disabled, read-only filesystem, and resource limits.

**Output:** NpmPackageInstaller for building npm skill images, extended HazardSandbox with execute_nodejs method, comprehensive test coverage.

</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/phases/36-npm-package-support/36-RESEARCH.md
@backend/core/package_installer.py (reference for Python installer patterns)
@backend/core/skill_sandbox.py (extend with execute_nodejs)
@backend/core/npm_dependency_scanner.py (for pre-install scanning)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create NpmPackageInstaller with Docker image builder</name>
  <files>backend/core/npm_package_installer.py</files>
  <action>
    Create NpmPackageInstaller class following RESEARCH.md Pattern 3:

    1. Create file with imports:
       - docker, logging, shutil, tempfile, json, uuid
       - typing: Any, Dict, List, Optional
       - from pathlib import Path

    2. Implement class structure:
       ```python
       class NpmPackageInstaller:
           \"\"\"Installs npm packages in dedicated Docker images for skill isolation.\"\"\"

           def __init__(self, snyk_api_key: Optional[str] = None):
               self._client = None
               self._scanner = None
               self._snyk_api_key = snyk_api_key
       ```

    3. Implement install_packages method:
       - Accept skill_id, packages (List[str]), package_manager="npm", base_image="node:20-alpine"
       - Create temporary package.json
       - Run NpmDependencyScanner.scan_packages if scan_for_vulnerabilities=True
       - Call _build_skill_image to create Docker image
       - Return {"success": bool, "image_tag": str, "vulnerabilities": List}

    4. Implement _create_package_json method:
       - Parse package specifiers: "lodash@4.17.21" -> {"lodash": "4.17.21"}
       - Return minimal package.json dict

    CRITICAL: Follow package_installer.py patterns but adapt for npm (package.json vs requirements.txt)
  </action>
  <verify>
    python -c "from backend.core.npm_package_installer import NpmPackageInstaller; print('Import success')"
  </verify>
  <done>
    NpmPackageInstaller class with install_packages, _create_package_json methods
  </done>
</task>

<task type="auto">
  <name>Task 2: Implement _generate_dockerfile with --ignore-scripts</name>
  <files>backend/core/npm_package_installer.py</files>
  <action>
    Implement _generate_dockerfile method following RESEARCH.md Pattern 3:

    1. Generate Dockerfile with security constraints:
       ```python
       def _generate_dockerfile(self, package_json: Dict, package_manager: str, base_image: str) -> str:
           deps_json = json.dumps(package_json, indent=2)

           if package_manager == "npm":
               install_cmd = "npm ci --omit=dev --ignore-scripts"
           elif package_manager == "yarn":
               install_cmd = "yarn install --production --ignore-scripts"
           elif package_manager == "pnpm":
               install_cmd = "pnpm install --prod --ignore-scripts"

           dockerfile = f'''FROM {base_image}
       WORKDIR /skill
       RUN echo '{deps_json}' > package.json
       RUN {install_cmd}
       RUN npm cache clean --force
       ENV NODE_ENV=production
       RUN addgroup -g 1001 -S nodejs && adduser -S nodejs -u 1001
       USER nodejs
       WORKDIR /skill
       '''
           return dockerfile
       ```

    2. CRITICAL: Use --ignore-scripts flag to prevent postinstall malware execution
    3. Use npm ci for reproducible installs (if package-lock.json exists)
    4. Create non-root nodejs user (uid 1001)
    5. Set NODE_ENV=production for optimizations

    Reference: RESEARCH.md Pitfall 1 on Shai-Hulud attacks
  </action>
  <verify>
    grep -n "ignore-scripts\|npm ci" /Users/rushiparikh/projects/atom/backend/core/npm_package_installer.py
  </verify>
  <done>
    _generate_dockerfile creates secure Dockerfile with --ignore-scripts, npm ci, non-root user
  </done>
</task>

<task type="auto">
  <name>Task 3: Implement _build_skill_image with Docker build</name>
  <files>backend/core/npm_package_installer.py</files>
  <action>
    Implement _build_skill_image method following package_installer.py patterns:

    1. Create temporary directory with tempfile.mkdtemp(prefix="atom_npm_skill_build_")

    2. Write package.json and Dockerfile to temp dir

    3. Build Docker image:
       ```python
       image_tag = f"atom-npm-skill:{skill_id.replace('/', '-')}-v1"
       image, build_logs = self.client.images.build(
           path=str(temp_dir),
           tag=image_tag,
           rm=True,
           forcerm=True
       )
       ```

    4. Capture build logs from generator

    5. Clean up temp directory with shutil.rmtree

    6. Return build_logs list

    Use lazy loading for Docker client (property like package_installer.py)
  </action>
  <verify>
    grep -n "_build_skill_image\|atom-npm-skill" /Users/rushiparikh/projects/atom/backend/core/npm_package_installer.py
  </verify>
  <done>
    _build_skill_image creates atom-npm-skill:{skill_id}-v1 image, captures logs, cleans up temp dir
  </done>
</task>

<task type="auto">
  <name>Task 4: Add execute_with_packages and cleanup methods</name>
  <files>backend/core/npm_package_installer.py</files>
  <action>
    Add execution and cleanup methods to NpmPackageInstaller:

    1. Implement execute_with_packages:
       - Accept skill_id, code, inputs, timeout, memory_limit, cpu_limit
       - Use HazardSandbox.execute_nodejs with image_tag
       - Raise RuntimeError if image not found

    2. Implement cleanup_skill_image:
       - Remove image by tag: atom-npm-skill:{skill_id}-v1
       - Return True if removed, False if not found

    3. Implement get_skill_images:
       - List all atom-npm-skill:* images
       - Return list with tags, size, created timestamps

    4. Add lazy-loaded sandbox property:
       ```python
       @property
       def sandbox(self):
           if self._sandbox is None:
               from core.skill_sandbox import HazardSandbox
               self._sandbox = HazardSandbox()
           return self._sandbox
       ```

    Follow package_installer.py patterns for consistency.
  </action>
  <verify>
    grep -n "execute_with_packages\|cleanup_skill_image\|get_skill_images" /Users/rushiparikh/projects/atom/backend/core/npm_package_installer.py
  </verify>
  <done>
    execute_with_packages, cleanup_skill_image, get_skill_images methods implemented
  </done>
</task>

<task type="auto">
  <name>Task 5: Add execute_nodejs method to HazardSandbox</name>
  <files>backend/core/skill_sandbox.py</files>
  <action>
    Extend HazardSandbox class with execute_nodejs method (RESEARCH.md Pattern 5):

    1. Add method after execute_python:
       ```python
       def execute_nodejs(self, code: str, inputs: Dict[str, Any], timeout_seconds: int = 30,
                          memory_limit: str = "256m", cpu_limit: float = 0.5,
                          image: Optional[str] = None) -> str:
       ```

    2. Generate container_id with uuid

    3. Use node:20-alpine as default image (overrideable)

    4. Create wrapper script:
       ```python
       def _create_nodejs_wrapper(self, code: str, inputs: Dict[str, Any]) -> str:
           inputs_json = json.dumps(inputs)
           return f'''// Inject inputs
       const inputs = {inputs_json};

       // User code
       {code}
       '''
       ```

    5. Run container with security constraints:
       - command=["node", "-e", wrapper_script]
       - network_disabled=True
       - read_only=True
       - tmpfs={"/tmp": "size=10m"}
       - mem_limit, cpu_quota, auto_remove

    6. Return output.decode("utf-8") or error message

    CRITICAL: Same security constraints as execute_python (network disabled, read-only)
  </action>
  <verify>
    grep -n "execute_nodejs" /Users/rushiparikh/projects/atom/backend/core/skill_sandbox.py
  </verify>
  <done>
    HazardSandbox.execute_nodejs method runs Node.js code in isolated containers
  </done>
</task>

<task type="auto">
  <name>Task 6: Create tests for NpmPackageInstaller</name>
  <files>backend/tests/test_npm_package_installer.py</files>
  <action>
    Create comprehensive test file for NpmPackageInstaller:

    1. Test file setup:
       - Import pytest, NpmPackageInstaller
       - Mock Docker client, scanner

    2. Test cases:
       - test_install_packages_simple: Install single package
       - test_install_with_vulnerabilities: Blocked when vulnerabilities found
       - test_create_package_json: Validates package.json structure
       - test_generate_dockerfile_npm: Uses --ignore-scripts flag
       - test_generate_dockerfile_yarn: Uses yarn --ignore-scripts
       - test_generate_dockerfile_pnpm: Uses pnpm --ignore-scripts
       - test_build_skill_image: Creates atom-npm-skill tag
       - test_cleanup_skill_image: Removes image
       - test_get_skill_images: Lists npm skill images
       - test_execute_with_packages: Runs Node.js code in custom image

    3. Mock patterns:
       - Mock docker.from_env() for client
       - Mock client.images.build() for image building
       - Mock NpmDependencyScanner for vulnerability scanning

    4. Security assertions:
       - --ignore-scripts always in Dockerfile
       - Non-root user created
       - NODE_ENV=production set

    5. Package version isolation test (CRITICAL for success criterion 5):
       - test_package_version_isolation: Install skill A with lodash@4.17.21 and skill B with lodash@5.0.0
       - Verify each skill has its own Docker image: atom-npm-skill:skill-a-v1 and atom-npm-skill:skill-b-v1
       - Verify each image contains its own node_modules directory
       - Execute code in skill A that uses lodash@4.17.21 API (e.g., _.forEach)
       - Execute code in skill B that uses lodash@5.0.0 API
       - Verify no conflicts: skill A doesn't see lodash@5.0.0, skill B doesn't see lodash@4.17.21
       - Test uses mock Docker client to simulate separate images

    Use pytest fixtures for installer instance and mocks.
  </action>
  <verify>
    pytest backend/tests/test_npm_package_installer.py -v --collect-only | grep "test_"
  </verify>
  <done>
    11+ test cases covering install, build, cleanup, Dockerfile security, execution, and package version isolation
  </done>
</task>

<task type="auto">
  <name>Task 7: Create tests for Node.js sandbox execution</name>
  <files>backend/tests/test_npm_sandbox_execution.py</files>
  <action>
    Create comprehensive test file for Node.js execution:

    1. Test file setup:
       - Import pytest, HazardSandbox
       - Mock Docker client

    2. Test cases:
       - test_execute_nodejs_basic: Simple console.log executes
       - test_execute_nodejs_with_inputs: Inputs injected correctly
       - test_execute_nodejs_network_disabled: Network requests fail
       - test_execute_nodejs_readonly_fs: Filesystem writes fail
       - test_execute_nodejs_resource_limits: Memory/CPU limits enforced
       - test_execute_nodejs_timeout: Timeout enforced
       - test_create_nodejs_wrapper: Wrapper script format correct
       - test_execute_nodejs_custom_image: Custom image with node_modules
       - test_execute_nodejs_error_handling: Errors caught and returned

    3. Mock data:
       - Mock container output for successful execution
       - Mock ContainerError for execution failures

    4. Security assertions:
       - network_disabled=True always set
       - read_only=True always set
       - tmpfs mounted for /tmp only
       - auto_remove=True for ephemeral containers

    Reference: test_package_governance.py for test patterns
  </action>
  <verify>
    pytest backend/tests/test_npm_sandbox_execution.py -v --collect-only | grep "test_"
  </verify>
  <done>
    9+ test cases covering basic execution, inputs, security constraints, error handling
  </done>
</task>

</tasks>

<verification>
Overall phase verification:
1. NpmPackageInstaller builds atom-npm-skill:{skill_id}-v1 images
2. --ignore-scripts flag in all Dockerfiles (npm, yarn, pnpm)
3. HazardSandbox.execute_nodejs runs code with network disabled, read-only filesystem
4. execute_with_packages uses custom image with pre-installed node_modules
5. Different skills can use different versions of the same npm package (verified by test_package_version_isolation)
6. All tests pass: pytest backend/tests/test_npm_package_installer.py backend/tests/test_npm_sandbox_execution.py -v
</verification>

<success_criteria>
1. NpmPackageInstaller.install_packages creates Docker image with npm packages
2. _generate_dockerfile uses --ignore-scripts flag (prevents postinstall malware)
3. HazardSandbox.execute_nodejs executes Node.js code in isolated container
4. Resource limits enforced (memory, CPU, timeout)
5. Package version isolation: skill A with lodash@4.17.21 and skill B with lodash@5.0.0 don't conflict
6. 20+ tests covering all installer and sandbox execution methods including version isolation
7. Backward compatible with HazardSandbox.execute_python (no changes to existing method)
</success_criteria>

<output>
After completion, create `.planning/phases/36-npm-package-support/36-npm-package-support-03-SUMMARY.md`
</output>
