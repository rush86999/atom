---
phase: 36-npm-package-support
plan: 04
type: execute
wave: 2
depends_on: [36-npm-package-support-01, 36-npm-package-support-03]
files_modified:
  - backend/api/package_routes.py
  - backend/tests/test_npm_package_routes.py
  - backend/core/audit_service.py
  - backend/core/models.py
autonomous: true

must_haves:
  truths:
    - "POST /api/packages/install accepts package_type parameter ('python' or 'npm')"
    - "npm package permission checks use package_type='npm'"
    - "npm packages use NpmPackageInstaller for installation"
    - "npm packages use NpmScriptAnalyzer for pre-install script scanning"
    - "npm package execution uses execute_nodejs via sandbox"
    - "npm package installations, governance decisions, and executions logged to AuditLog"
  artifacts:
    - path: backend/api/package_routes.py
      contains: PackageInstallRequest, NpmPackageInstallRequest, install_packages (npm variant), execute_with_packages (npm variant)
    - path: backend/tests/test_npm_package_routes.py
      contains: test_install_npm_packages, test_npm_permission_check, test_execute_nodejs_code
    - path: backend/core/audit_service.py
      contains: PACKAGE audit type, create_package_audit method
    - path: backend/core/models.py
      contains: PackageAudit model or AuditLog with package_metadata
  key_links:
    - from: backend/api/package_routes.py
      to: backend/core/package_governance_service.py
      via: check_package_permission(package_type="npm")
      pattern: check_package_permission.*package_type
    - from: backend/api/package_routes.py
      to: backend/core/npm_package_installer.py
      via: NpmPackageInstaller.install_packages()
      pattern: NpmPackageInstaller
---

<objective>
Extend REST API endpoints to support npm package installation, governance checks, and execution alongside Python packages.

**Purpose:** Provide unified API for both Python and npm packages with package_type parameter, maintaining backward compatibility with existing Python package endpoints.

**Output:** Extended package_routes.py with npm-specific request models and endpoints, comprehensive test coverage.

</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/phases/36-npm-package-support/36-RESEARCH.md
@backend/api/package_routes.py (existing Python package endpoints)
@backend/core/package_governance_service.py (extended for npm)
@backend/core/npm_package_installer.py (npm installer)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add npm-specific request models to package_routes.py</name>
  <files>backend/api/package_routes.py</files>
  <action>
    Extend package_routes.py with npm request models:

    1. Add after PackageInstallRequest (line 79):
       ```python
       class NpmPackageInstallRequest(BaseModel):
           \"\"\"Request to install npm packages for a skill.\"\"\"
           agent_id: str = Field(..., description="Agent ID requesting package installation")
           skill_id: str = Field(..., description="Skill identifier (for image tagging)")
           packages: list[str] = Field(..., description="List of npm package specifiers (e.g., ['lodash@4.17.21', 'express@^4.18.0'])")
           package_manager: str = Field("npm", description="Package manager: npm, yarn, or pnpm")
           scan_for_vulnerabilities: bool = Field(True, description="Run vulnerability scan before installation")
           base_image: str = Field("node:20-alpine", description="Base Node.js Docker image")
       ```

    2. Add NpmPackageExecuteRequest:
       ```python
       class NpmPackageExecuteRequest(BaseModel):
           \"\"\"Request to execute Node.js skill code with packages.\"\"\"
           agent_id: str = Field(..., description="Agent ID executing skill")
           skill_id: str = Field(..., description="Skill identifier (must have called install first)")
           code: str = Field(..., description="Node.js code to execute")
           inputs: dict[str, Any] = Field(default_factory=dict, description="Input variables for execution")
           timeout_seconds: int = Field(30, description="Maximum execution time")
           memory_limit: str = Field("256m", description="Memory limit for container")
           cpu_limit: float = Field(0.5, description="CPU quota (0.5 = 50% of one core)")
       ```

    3. Add NpmPackageCheckRequest:
       ```python
       class NpmPackageCheckRequest(BaseModel):
           \"\"\"Request to check npm package permission for an agent.\"\"\"
           agent_id: str = Field(..., description="Agent ID requesting package access")
           package_name: str = Field(..., description="npm package name (e.g., 'lodash')")
           version: str = Field(..., description="Package version (e.g., '4.17.21')")
       ```

    CRITICAL: Keep existing Python request models for backward compatibility
  </action>
  <verify>
    grep -n "NpmPackage.*Request" /Users/rushiparikh/projects/atom/backend/api/package_routes.py
  </verify>
  <done>
    NpmPackageInstallRequest, NpmPackageExecuteRequest, NpmPackageCheckRequest models added
  </done>
</task>

<task type="auto">
  <name>Task 2: Add npm governance endpoints</name>
  <files>backend/api/package_routes.py</files>
  <action>
    Add npm-specific governance endpoints after line 203 (after Python /request endpoint):

    1. Add POST /api/packages/npm/request:
       ```python
       @router.post("/npm/request")
       def request_npm_package_approval(request: PackageRequest, db: Session = Depends(get_db)):
           \"\"\"Request approval for npm package version.\"\"\"
           package = get_governance().request_package_approval(
               package_name=request.package_name,
               version=request.version,
               requested_by=request.requested_by,
               reason=request.reason,
               db=db
           )
           # Add package_type="npm" metadata
           return {"package_id": package.id, "status": package.status, "package_type": "npm"}
       ```

    2. Add GET /api/packages/npm/check:
       ```python
       @router.get("/npm/check", response_model=PackagePermissionResponse)
       def check_npm_package_permission(
           agent_id: str = Query(...),
           package_name: str = Query(...),
           version: str = Query(...),
           db: Session = Depends(get_db)
       ):
           result = get_governance().check_package_permission(
               agent_id, package_name, version, package_type="npm", db=db
           )
           return result
       ```

    3. Add POST /api/packages/npm/approve:
       ```python
       @router.post("/npm/approve")
       def approve_npm_package(request: PackageApprovalRequest, db: Session = Depends(get_db)):
           package = get_governance().approve_package(
               package_name=request.package_name,
               version=request.version,
               min_maturity=request.min_maturity,
               approved_by=request.approved_by,
               db=db
           )
           # Set package_type to "npm"
           return {"package_id": package.id, "status": package.status, "package_type": "npm"}
       ```

    CRITICAL: Pass package_type="npm" to all governance service calls
  </action>
  <verify>
    grep -n "/npm/\|package_type=\"npm\"" /Users/rushiparikh/projects/atom/backend/api/package_routes.py
  </verify>
  <done>
    npm governance endpoints: /npm/check, /npm/request, /npm/approve, /npm/ban
  </done>
</task>

<task type="auto">
  <name>Task 3: Add npm installation and execution endpoints</name>
  <files>backend/api/package_routes.py</files>
  <action>
    Add npm installation and execution endpoints:

    1. Add POST /api/packages/npm/install:
       ```python
       @router.post("/npm/install", response_model=PackageInstallResponse)
       def install_npm_packages(request: NpmPackageInstallRequest, db: Session = Depends(get_db)):
           \"\"\"Install npm packages for skill in dedicated Docker image.\"\"\"
           from core.npm_package_installer import NpmPackageInstaller

           # Parse packages and check permissions
           for pkg in request.packages:
               if '@' in pkg:
                   name, version = pkg.split('@', 1)
               else:
                   name, version = pkg, "latest"

               permission = get_governance().check_package_permission(
                   request.agent_id, name, version, package_type="npm", db=db
               )

               if not permission["allowed"]:
                   raise HTTPException(status_code=403, detail={
                       "error": "npm package permission denied",
                       "package": name,
                       "version": version,
                       "reason": permission["reason"]
                   })

           # Install packages
           result = NpmPackageInstaller().install_packages(
               skill_id=request.skill_id,
               packages=request.packages,
               package_manager=request.package_manager,
               scan_for_vulnerabilities=request.scan_for_vulnerabilities,
               base_image=request.base_image
           )

           return result
       ```

    2. Add POST /api/packages/npm/execute:
       ```python
       @router.post("/npm/execute", response_model=PackageExecuteResponse)
       def execute_npm_code(request: NpmPackageExecuteRequest, db: Session = Depends(get_db)):
           \"\"\"Execute Node.js skill code using its dedicated image with packages.\"\"\"
           from core.npm_package_installer import NpmPackageInstaller

           try:
               output = NpmPackageInstaller().execute_with_packages(
                   skill_id=request.skill_id,
                   code=request.code,
                   inputs=request.inputs,
                   timeout_seconds=request.timeout_seconds,
                   memory_limit=request.memory_limit,
                   cpu_limit=request.cpu_limit
               )
               return {"success": True, "skill_id": request.skill_id, "output": output}
           except RuntimeError as e:
               raise HTTPException(status_code=404, detail={"error": str(e)})
       ```

    CRITICAL: Use package_type="npm" for all permission checks
  </action>
  <verify>
    grep -n "/npm/install\|/npm/execute" /Users/rushiparikh/projects/atom/backend/api/package_routes.py
  </verify>
  <done>
    npm installation and execution endpoints added with governance checks
  </done>
</task>

<task type="auto">
  <name>Task 4: Add npm-specific list and cleanup endpoints</name>
  <files>backend/api/package_routes.py</files>
  <action>
    Add npm listing and cleanup endpoints:

    1. Add GET /api/packages/npm with package_type filter:
       ```python
       @router.get("/npm", response_model=PackageListResponse)
       def list_npm_packages(
           status: Optional[str] = Query(None),
           db: Session = Depends(get_db)
       ):
           packages = get_governance().list_packages(status=status, db=db)
           # Filter for npm packages only
           npm_packages = [p for p in packages if getattr(p, 'package_type', 'python') == 'npm']

           package_responses = [
               PackageResponse(
                   id=p.id, name=p.name, version=p.version,
                   min_maturity=p.min_maturity, status=p.status,
                   ban_reason=p.ban_reason, approved_by=p.approved_by,
                   approved_at=p.approved_at.isoformat() if p.approved_at else None
               )
               for p in npm_packages
           ]
           return {"packages": package_responses, "count": len(package_responses)}
       ```

    2. Add DELETE /api/packages/npm/{skill_id}:
       ```python
       @router.delete("/npm/{skill_id}")
       def cleanup_npm_skill_image(skill_id: str, agent_id: str = Query(...)):
           from core.npm_package_installer import NpmPackageInstaller
           success = NpmPackageInstaller().cleanup_skill_image(skill_id)
           return {"success": success, "skill_id": skill_id,
                   "message": "Image removed" if success else "Image not found"}
       ```

    3. Add GET /api/packages/npm/{skill_id}/status:
       ```python
       @router.get("/npm/{skill_id}/status")
       def get_npm_skill_image_status(skill_id: str):
           import docker
           image_tag = f"atom-npm-skill:{skill_id.replace('/', '-')}-v1"
           # ... check image existence and return status
       ```

    Reference existing Python endpoints for consistency
  </action>
  <verify>
    grep -n '"/npm/' /Users/rushiparikh/projects/atom/backend/api/package_routes.py
  </verify>
  <done>
    npm list, cleanup, and status endpoints added
  </done>
</task>

<task type="auto">
  <name>Task 5: Add NpmScriptAnalyzer integration to install endpoint</name>
  <files>backend/api/package_routes.py</files>
  <action>
    Integrate NpmScriptAnalyzer into install endpoint for postinstall script detection:

    1. Import NpmScriptAnalyzer at top of file:
       ```python
       from core.npm_script_analyzer import NpmScriptAnalyzer
       ```

    2. Add script analysis before installation in POST /api/packages/npm/install:
       ```python
       # Before calling install_packages
       from core.npm_script_analyzer import NpmScriptAnalyzer
       script_analyzer = NpmScriptAnalyzer()

       script_warnings = script_analyzer.analyze_package_scripts(
           packages=request.packages,
           package_manager=request.package_manager
       )

       if script_warnings["malicious"]:
           raise HTTPException(
               status_code=403,
               detail={
                   "error": "Malicious postinstall/preinstall scripts detected",
                   "warnings": script_warnings["warnings"],
                   "scripts_found": script_warnings["scripts_found"]
               }
           )
       ```

    3. Log warnings if suspicious scripts found but not malicious:
       ```python
       if script_warnings["warnings"]:
           logger.warning(f"Suspicious scripts detected in npm packages: {script_warnings['warnings']}")
       ```

    CRITICAL: Block installation if malicious=True (Shai-Hulud attack prevention)
  </action>
  <verify>
    grep -n "NpmScriptAnalyzer\|analyze_package_scripts" /Users/rushiparikh/projects/atom/backend/api/package_routes.py
  </verify>
  <done>
    NpmScriptAnalyzer integrated into install endpoint with malicious blocking
  </done>
</task>

<task type="auto">
  <name>Task 6: Create comprehensive tests for npm package routes</name>
  <files>backend/tests/test_npm_package_routes.py</files>
  <action>
    Create comprehensive test file for npm package endpoints:

    1. Test file setup:
       - Import pytest, TestClient from fastapi.testclient
       - Import package_routes router
       - Mock database session

    2. Test cases for governance endpoints:
       - test_check_npm_package_permission_student_blocked: STUDENT agents blocked
       - test_check_npm_package_permission_intern_requires_approval: INTERN needs approval
       - test_check_npm_package_permission_autonomous_allowed: AUTONOMOUS allowed if approved
       - test_request_npm_package_approval: Creates pending request
       - test_approve_npm_package: Sets status=active, package_type="npm"
       - test_ban_npm_package: Sets status=banned, blocks all agents

    3. Test cases for installation endpoints:
       - test_install_npm_packages_success: Valid packages install successfully
       - test_install_npm_packages_permission_denied: 403 when STUDENT agent
       - test_install_npm_packages_malicious_scripts: 403 when postinstall threats detected
       - test_install_npm_packages_vulnerabilities: 400 when vulnerabilities found
       - test_install_npm_yarn_manager: Works with yarn package manager
       - test_install_npm_pnpm_manager: Works with pnpm package manager

    4. Test cases for execution endpoints:
       - test_execute_npm_code_success: Node.js code executes
       - test_execute_npm_code_image_not_found: 404 when image not built
       - test_execute_npm_code_timeout: Timeout enforced
       - test_execute_npm_code_with_inputs: Inputs injected correctly

    5. Test cases for utility endpoints:
       - test_list_npm_packages: Returns only npm packages
       - test_cleanup_npm_skill_image: Removes Docker image
       - test_get_npm_skill_image_status: Returns image metadata

    Use pytest fixtures for client, db session, and governance service.
  </action>
  <verify>
    pytest backend/tests/test_npm_package_routes.py -v --collect-only | grep "test_" | wc -l
  </verify>
  <done>
    15+ test cases covering all npm governance, installation, execution, and utility endpoints
  </done>
</task>

<task type="auto">
  <name>Task 7: Add audit logging for npm package operations</name>
  <files>backend/core/audit_service.py, backend/core/models.py</files>
  <action>
    Extend audit service to track npm package installations, governance decisions, and executions:

    1. Add PACKAGE audit type to AuditType enum:
       ```python
       class AuditType(str, Enum):
           CANVAS = "canvas"
           BROWSER = "browser"
           DEVICE = "device"
           AGENT = "agent"
           PACKAGE = "package"
           GENERIC = "generic"
       ```

    2. Add create_package_audit method to AuditService:
       ```python
       def create_package_audit(
           self,
           db: Session,
           agent_id: Optional[str],
           agent_execution_id: Optional[str],
           user_id: str,
           action: str,  # "install", "execute", "permission_check", "governance_decision"
           package_name: str,
           package_version: str,
           package_type: str,  # "python" or "npm"
           skill_id: Optional[str] = None,
           governance_decision: Optional[str] = None,  # "approved", "denied"
           governance_reason: Optional[str] = None,
           metadata: Optional[Dict[str, Any]] = None,
           request: Optional[Request] = None
       ) -> Optional[str]:
       ```

    3. Log to AuditLog (not a new PackageAudit model - reuse existing AuditLog):
       - Set event_type="package_operation"
       - Include package_name, package_version, package_type in metadata
       - Include governance_decision and governance_reason in metadata
       - Store skill_id in metadata if present

    4. For audit entries, track:
       - Installation attempts (success/failure)
       - Governance permission checks (allowed/denied with reason)
       - Execution attempts (success/failure)
       - Agent ID and maturity level for all operations

    CRITICAL: Use existing AuditLog model with metadata field, don't create new PackageAudit model
  </action>
  <verify>
    grep -n "PACKAGE\|create_package_audit" /Users/rushiparikh/projects/atom/backend/core/audit_service.py
  </verify>
  <done>
    AuditType.PACKAGE added, create_package_audit method implemented, audit logging for npm operations
  </done>
</task>

</tasks>

<verification>
Overall phase verification:
1. All npm endpoints respond correctly (200, 403, 404, 500)
2. package_type="npm" passed to all governance service calls
3. NpmScriptAnalyzer blocks malicious postinstall scripts
4. npm packages listed separately from Python packages
5. All npm operations (install, execute, governance) logged to AuditLog
6. All tests pass: pytest backend/tests/test_npm_package_routes.py -v
</verification>

<success_criteria>
1. 8 new npm endpoints: /npm/check, /npm/request, /npm/approve, /npm/ban, /npm/install, /npm/execute, /npm, /npm/{skill_id}
2. NpmPackageCheckRequest, NpmPackageInstallRequest, NpmPackageExecuteRequest models
3. NpmScriptAnalyzer blocks malicious packages before installation
4. npm packages use package_type="npm" in governance checks
5. AuditType.PACKAGE added to audit_service.py with create_package_audit method
6. All npm package operations logged to AuditLog with agent_id, package_name, version, decision
7. Backward compatible with existing Python package endpoints
8. 15+ tests covering all npm endpoints with permission scenarios
</success_criteria>

<output>
After completion, create `.planning/phases/36-npm-package-support/36-npm-package-support-04-SUMMARY.md`
</output>
