---
phase: 36-npm-package-support
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/core/models.py
  - backend/core/package_governance_service.py
  - backend/alembic/versions/xxx_add_package_type_to_package_registry.py
autonomous: true

must_haves:
  truths:
    - "PackageRegistry model has package_type field distinguishing 'python' vs 'npm'"
    - "Governance cache key format includes package_type (pkg:npm:lodash:4.17.21)"
    - "check_package_permission accepts package_type parameter"
    - "STUDENT agents blocked from npm packages with specific error message"
    - "npm packages filtered separately from Python packages in list endpoint"
  artifacts:
    - path: backend/core/models.py
      contains: class PackageRegistry, package_type
    - path: backend/core/package_governance_service.py
      contains: check_package_permission, PACKAGE_TYPE_NPM, PACKAGE_TYPE_PYTHON
    - path: backend/alembic/versions/xxx_add_package_type_to_package_registry.py
      contains: package_type, Column(String)
  key_links:
    - from: backend/core/package_governance_service.py
      to: backend/core/models.py
      via: PackageRegistry.package_type field
      pattern: filter\(PackageRegistry\.package_type == package_type\)
---

<objective>
Extend PackageGovernanceService and PackageRegistry model to support npm packages alongside Python packages with minimal breaking changes.

**Purpose:** Enable governance system to distinguish between Python and npm packages, applying the same maturity-based access controls while maintaining <1ms cache performance.

**Output:** Extended database model with package_type field, updated governance service with npm-aware cache keys, and Alembic migration for backward compatibility.

</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/phases/36-npm-package-support/36-RESEARCH.md
@backend/core/models.py (PackageRegistry class starting at line 5328)
@backend/core/package_governance_service.py (full file for extension patterns)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add package_type field to PackageRegistry model</name>
  <files>backend/core/models.py</files>
  <action>
    Extend PackageRegistry model (line 5328+) with package_type field:

    1. Add package_type Column after 'version' field:
       ```python
       package_type = Column(String, default="python", nullable=False, index=True)  # 'python' or 'npm'
       ```

    2. Update docstring to mention npm packages:
       - Change "Python package registry" to "Package registry for Python and npm packages"
       - Add npm governance rules to docstring

    3. Add package type constants at class level:
       ```python
       PACKAGE_TYPE_PYTHON = "python"
       PACKAGE_TYPE_NPM = "npm"
       ```

    4. DO NOT modify existing fields (maintain backward compatibility)
    5. DO NOT change id format (keep "{package_name}:{version}")
  </action>
  <verify>
    grep -n "package_type" /Users/rushiparikh/projects/atom/backend/core/models.py | head -5
  </verify>
  <done>
    PackageRegistry has package_type field with default="python", index for fast queries, and constants defined
  </done>
</task>

<task type="auto">
  <name>Task 2: Create Alembic migration for package_type field</name>
  <files>backend/alembic/versions/xxx_add_package_type_to_package_registry.py</files>
  <action>
    Generate Alembic migration to add package_type field:

    1. Run migration generation:
       ```bash
       cd backend && alembic revision -m "add_package_type_to_package_registry"
       ```

    2. Edit generated migration file:
       - Create op.add_column for package_type with default="python"
       - Use op.execute to update existing rows: UPDATE package_registry SET package_type = 'python' WHERE package_type IS NULL
       - Set nullable=False after data migration

    3. Verify migration SQL:
       ```bash
       alembic upgrade head
       ```

    Use filename format: {timestamp}_add_package_type_to_package_registry.py
  </action>
  <verify>
    ls -la backend/alembic/versions/*add_package_type* && grep -l "package_type" backend/alembic/versions/*.py
  </verify>
  <done>
    Migration file created with add_column, data update, and nullable constraint steps
  </done>
</task>

<task type="auto">
  <name>Task 3: Extend PackageGovernanceService for npm packages</name>
  <files>backend/core/package_governance_service.py</files>
  <action>
    Extend PackageGovernanceService class to support npm packages:

    1. Add package type constants after MATURITY_ORDER:
       ```python
       PACKAGE_TYPE_PYTHON = "python"
       PACKAGE_TYPE_NPM = "npm"
       ```

    2. Update check_package_permission signature (line 55):
       - Add package_type: str = PACKAGE_TYPE_PYTHON parameter
       - Update docstring to mention npm packages

    3. Update cache key format (line 77):
       ```python
       cache_key = f"pkg:{package_type}:{package_name}:{version}"
       ```

    4. Update database query (line 94):
       - Add filter: PackageRegistry.package_type == package_type
       - Add log message: f"Cache MISS for {package_type} package {package_name}@{version}"

    5. Update STUDENT blocking message (line 116):
       - Make generic: "STUDENT agents cannot execute {package_type} packages (educational restriction)"

    6. Update request_package_approval to accept package_type parameter

    7. Update approve_package to accept package_type parameter

    8. Update ban_package to accept package_type parameter

    CRITICAL: Maintain backward compatibility by using default package_type="python"
  </action>
  <verify>
    grep -n "PACKAGE_TYPE_NPM\|package_type" /Users/rushiparikh/projects/atom/backend/core/package_governance_service.py
  </verify>
  <done>
    PackageGovernanceService supports npm packages with package_type parameter, cache keys include type, backward compatible
  </done>
</task>

<task type="auto">
  <name>Task 4: Update list_packages to filter by package_type</name>
  <files>backend/core/package_governance_service.py</files>
  <action>
    Extend list_packages method (line 324) to support package_type filtering:

    1. Add package_type: Optional[str] = None parameter
    2. Add filter if package_type provided:
       ```python
       if package_type:
           query = query.filter(PackageRegistry.package_type == package_type)
       ```
    3. Update docstring with package_type parameter documentation

    This allows separate npm and Python package listings in the API.
  </action>
  <verify>
    grep -A5 "def list_packages" /Users/rushiparikh/projects/atom/backend/core/package_governance_service.py | grep "package_type"
  </verify>
  <done>
    list_packages method filters by package_type when provided, returns all packages when None
  </done>
</task>

</tasks>

<verification>
Overall phase verification:
1. Run migration: alembic upgrade head
2. Test governance cache key format: Python packages use "pkg:python:...", npm packages use "pkg:npm:..."
3. Verify STUDENT blocking works for both package types
4. Check database index exists on package_type field for query performance
5. Run existing tests: pytest backend/tests/test_package_governance.py -v
</verification>

<success_criteria>
1. PackageRegistry model has package_type field with "python" default
2. Alembic migration successfully adds column and migrates existing data
3. check_package_permission accepts package_type parameter with backward-compatible default
4. Cache keys include package_type: "pkg:npm:lodash:4.17.21" vs "pkg:python:numpy:1.21.0"
5. list_packages filters by package_type when specified
6. All existing Python package tests pass without modification
</success_criteria>

<output>
After completion, create `.planning/phases/36-npm-package-support/36-npm-package-support-01-SUMMARY.md`
</output>
