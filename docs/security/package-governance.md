# Package Governance - Access Control and Permissions

> **Maturity-based Python package access control with approval workflows and audit trails**

**Last Updated:** February 19, 2026

---

## Table of Contents

1. [Maturity-Based Access](#maturity-based-access)
2. [Approval Workflow](#approval-workflow)
3. [Banning Packages](#banning-packages)
4. [Cache Performance](#cache-performance)
5. [API Reference](#api-reference)
6. [Audit Trail](#audit-trail)

---

## Maturity-Based Access

Atom implements a four-tier maturity system for Python package access control. Each agent maturity level has different package permissions.

### Access Matrix

| Agent Maturity | Package Access | Approval Required | Notes |
|----------------|----------------|-------------------|-------|
| **STUDENT** | ❌ Blocked | N/A | Educational restriction - packages disabled for learning |
| **INTERN** | ⚠️ Request per package | Yes (admin) | Each package version requires explicit approval |
| **SUPERVISED** | ✅ Approved packages only | No | Can use packages approved for SUPERVISED+ |
| **AUTONOMOUS** | ✅ Approved packages only | No | Can use packages approved for AUTONOMOUS |

### Level Details

#### STUDENT (Blocked)

**Purpose:** Educational agents learning system capabilities

**Restrictions:**
- Cannot execute skills with Python packages
- Error message: `STUDENT agents cannot execute Python packages`
- All package requests denied

**Rationale:** Prevents Students from executing code before learning safety basics

**Upgrade Path:** Graduate to INTERN by completing training episodes

#### INTERN (Approval Required)

**Purpose:** Agents with moderate experience requiring oversight

**Workflow:**
1. Agent requests package via `POST /api/packages/request`
2. Admin reviews request (package, version, use case)
3. Admin approves via `POST /api/packages/approve` with maturity gate
4. Agent can now use approved package

**Example Request:**

```bash
curl -X POST http://localhost:8000/api/packages/request \
  -H "Content-Type: application/json" \
  -d '{
    "package_name": "numpy",
    "version": "1.21.0",
    "requested_by": "user-123",
    "reason": "Data processing skill requires numerical arrays"
  }'
```

**Example Approval:**

```bash
curl -X POST http://localhost:8000/api/packages/approve \
  -H "Content-Type: application/json" \
  -d '{
    "package_name": "numpy",
    "version": "1.21.0",
    "min_maturity": "INTERN",
    "approved_by": "admin-456",
    "notes": "Safe package, commonly used for data processing"
  }'
```

#### SUPERVISED (Approved Packages Only)

**Purpose:** Agents trusted to run with real-time monitoring

**Permissions:**
- Can use packages approved for SUPERVISED maturity or higher
- Real-time monitoring during execution
- Audit trail tracks all usage

**Check Permission:**

```bash
curl "http://localhost:8000/api/packages/check?agent_id=agent-123&package_name=pandas&version=1.3.0"
```

**Response (Allowed):**

```json
{
  "allowed": true,
  "maturity_required": "SUPERVISED",
  "reason": null
}
```

**Response (Blocked - Not Approved):**

```json
{
  "allowed": false,
  "maturity_required": "SUPERVISED",
  "reason": "Package not approved for SUPERVISED maturity"
}
```

#### AUTONOMOUS (Approved Packages Only)

**Purpose:** Fully trusted agents with complete autonomy

**Permissions:**
- Can use packages approved for AUTONOMOUS maturity
- Full execution without oversight
- Audit trail still maintained

**Note:** Banned packages block ALL agents regardless of maturity

---

## Approval Workflow

### 1. Request Package Approval

Agents or users request package approval through the API.

**Endpoint:** `POST /api/packages/request`

**Request:**

```bash
curl -X POST http://localhost:8000/api/packages/request \
  -H "Content-Type: application/json" \
  -d '{
    "package_name": "scikit-learn",
    "version": "1.0.0",
    "requested_by": "user-123",
    "reason": "Machine learning skill for text classification"
  }'
```

**Response:**

```json
{
  "success": true,
  "request_id": "req_abc123",
  "status": "pending_approval",
  "package_name": "scikit-learn",
  "version": "1.0.0",
  "requested_at": "2026-02-19T10:00:00Z"
}
```

### 2. Review Package

Admin reviews package before approval:

**Security Checks:**
1. **Vulnerability Scan** - Run `pip-audit` on package
2. **Popularity Check** - Verify download counts on PyPI
3. **Maintainer Verification** - Check package maintainer reputation
4. **Dependency Review** - Check transitive dependencies
5. **Code Review** - Inspect package source code (if applicable)

**Example Local Scan:**

```bash
# Create virtual environment
python -m venv review_env
source review_env/bin/activate

# Install package
pip install scikit-learn==1.0.0

# Scan for vulnerabilities
pip-audit

# View dependencies
pipdeptree -p scikit-learn
```

### 3. Approve Package

Admin approves package for specific maturity level.

**Endpoint:** `POST /api/packages/approve`

**Request:**

```bash
curl -X POST http://localhost:8000/api/packages/approve \
  -H "Content-Type: application/json" \
  -d '{
    "package_name": "scikit-learn",
    "version": "1.0.0",
    "min_maturity": "SUPERVISED",
    "approved_by": "admin-456",
    "notes": "Popular ML library, no known CVEs in this version"
  }'
```

**Response:**

```json
{
  "success": true,
  "package_name": "scikit-learn",
  "version": "1.0.0",
  "min_maturity": "SUPERVISED",
  "approved_at": "2026-02-19T10:05:00Z",
  "approved_by": "admin-456"
}
```

**Maturity Gates:**

- **INTERN** - Package safe for learning agents with supervision
- **SUPERVISED** - Package safe for monitored execution
- **AUTONOMOUS** - Package safe for fully autonomous execution

### 4. Check Permission

Agents check package permission before use.

**Endpoint:** `GET /api/packages/check`

**Request:**

```bash
curl "http://localhost:8000/api/packages/check?agent_id=agent-123&package_name=scikit-learn&version=1.0.0"
```

**Response (Allowed):**

```json
{
  "allowed": true,
  "maturity_required": "SUPERVISED",
  "reason": null
}
```

**Response (Blocked - Wrong Maturity):**

```json
{
  "allowed": false,
  "maturity_required": "SUPERVISED",
  "reason": "Agent maturity (INTERN) insufficient for package maturity (SUPERVISED)"
}
```

### 5. Use Package

Agent executes skill with approved package.

**Request:**

```bash
curl -X POST http://localhost:8000/api/packages/execute \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent-123",
    "skill_id": "ml-classifier",
    "code": "from sklearn.ensemble import RandomForestClassifier; print(RandomForestClassifier())"
  }'
```

**Response:**

```json
{
  "success": true,
  "skill_id": "ml-classifier",
  "output": "RandomForestClassifier()"
}
```

---

## Banning Packages

Packages can be banned to block usage for ALL agents regardless of maturity.

### When to Ban

**Security Reasons:**
- Known CVE with no patch available
- Malicious code discovered
- Data exfiltration risks
- Privacy violations

**Policy Reasons:**
- Deprecated packages
- License violations
- Compliance requirements

### Ban Package

**Endpoint:** `POST /api/packages/ban`

**Request:**

```bash
curl -X POST http://localhost:8000/api/packages/ban \
  -H "Content-Type: application/json" \
  -d '{
    "package_name": "malicious-pkg",
    "version": "1.0.0",
    "reason": "Contains data exfiltration code (CVE-2026-12345)",
    "banned_by": "admin-456"
  }'
```

**Response:**

```json
{
  "success": true,
  "package_name": "malicious-pkg",
  "version": "1.0.0",
  "banned_at": "2026-02-19T10:10:00Z",
  "banned_by": "admin-456",
  "reason": "Contains data exfiltration code (CVE-2026-12345)"
}
```

### Effect of Ban

- **ALL agents** blocked from using package (even AUTONOMOUS)
- Cache invalidated immediately
- Existing skills with package blocked from execution
- Audit trail records ban event

**Check Permission (Banned):**

```json
{
  "allowed": false,
  "maturity_required": "BANNED",
  "reason": "Package banned due to security concerns"
}
```

### Unban Package

To reverse a ban (after security fix):

**Endpoint:** `POST /api/packages/unban`

**Request:**

```bash
curl -X POST http://localhost:8000/api/packages/unban \
  -H "Content-Type: application/json" \
  -d '{
    "package_name": "malicious-pkg",
    "version": "1.0.0",
    "reason": "Security patch released in version 1.0.1",
    "unbanned_by": "admin-456"
  }'
```

---

## Cache Performance

Package governance uses GovernanceCache for <1ms permission lookups.

### Performance Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| Cache hit (P50) | ~0.027ms | 27 microseconds |
| Cache hit (P99) | ~0.1ms | 100 microseconds |
| Cache miss | ~0.084ms average | DB query + cache set |
| Cache hit rate | >95% | Most checks cached |
| Cache throughput | 616k ops/s | Measured on production hardware |

### Cache Configuration

**Environment Variables:**

```bash
# Cache duration (seconds)
PACKAGE_CACHE_TTL=60

# Max cache entries
PACKAGE_CACHE_MAX_SIZE=1000
```

**Default Settings:**
- TTL: 60 seconds (auto-refresh)
- Max Size: 1000 entries
- Eviction: LRU (Least Recently Used)

### Cache Invalidation

Cache is invalidated when:

1. **Manual Invalidation:**
   - Package approved
   - Package banned
   - Package un-banned

2. **Auto Invalidation:**
   - TTL expires (60 seconds)
   - Cache size exceeds max (LRU eviction)

3. **System Events:**
   - Agent maturity changed
   - Agent graduated to new level

### Cache Warming

Pre-populate cache for common packages:

```python
from core.governance_cache import GovernanceCache
from core.package_governance_service import PackageGovernanceService

cache = GovernanceCache()
service = PackageGovernanceService()

# Common packages
packages = [
    ("numpy", "1.21.0"),
    ("pandas", "1.3.0"),
    ("requests", "2.28.0"),
    ("matplotlib", "3.4.0"),
]

for package_name, version in packages:
    service.check_package_permission(
        agent_id="cache-warming",
        package_name=package_name,
        version=version
    )
```

---

## API Reference

### List Package Approvals

Get all approved packages.

**Endpoint:** `GET /api/packages/approvals`

**Query Parameters:**
- `min_maturity` (optional): Filter by maturity level

**Request:**

```bash
curl http://localhost:8000/api/packages/approvals?min_maturity=SUPERVISED
```

**Response:**

```json
{
  "approvals": [
    {
      "package_name": "numpy",
      "version": "1.21.0",
      "min_maturity": "INTERN",
      "approved_at": "2026-02-19T10:00:00Z",
      "approved_by": "admin-456"
    },
    {
      "package_name": "pandas",
      "version": "1.3.0",
      "min_maturity": "INTERN",
      "approved_at": "2026-02-19T10:01:00Z",
      "approved_by": "admin-456"
    }
  ],
  "count": 2
}
```

### List Pending Requests

Get all pending package approval requests.

**Endpoint:** `GET /api/packages/requests`

**Query Parameters:**
- `status` (optional): Filter by status (pending, approved, rejected)

**Request:**

```bash
curl http://localhost:8000/api/packages/requests?status=pending
```

**Response:**

```json
{
  "requests": [
    {
      "request_id": "req_abc123",
      "package_name": "scikit-learn",
      "version": "1.0.0",
      "requested_by": "user-123",
      "reason": "Machine learning skill",
      "requested_at": "2026-02-19T10:00:00Z",
      "status": "pending"
    }
  ],
  "count": 1
}
```

### Reject Request

Reject a package approval request.

**Endpoint:** `POST /api/packages/reject`

**Request:**

```bash
curl -X POST http://localhost:8000/api/packages/reject \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "req_abc123",
    "reason": "Package has known vulnerabilities in this version",
    "rejected_by": "admin-456"
  }'
```

**Response:**

```json
{
  "success": true,
  "request_id": "req_abc123",
  "status": "rejected",
  "rejected_at": "2026-02-19T10:15:00Z",
  "rejected_by": "admin-456"
}
```

---

## Audit Trail

All package operations are logged to the `package_registry` table for compliance and debugging.

### Audit Fields

| Field | Description | Example |
|-------|-------------|---------|
| `id` | Unique identifier | `pkg_123` |
| `package_name` | Python package name | `numpy` |
| `version` | Package version | `1.21.0` |
| `min_maturity` | Required maturity level | `INTERN` |
| `approved_at` | Approval timestamp | `2026-02-19T10:00:00Z` |
| `approved_by` | Admin who approved | `admin-456` |
| `banned` | Ban status | `false` |
| `banned_at` | Ban timestamp (if banned) | `null` |
| `banned_by` | Admin who banned (if banned) | `null` |
| `ban_reason` | Reason for ban (if banned) | `null` |

### Query Audit Trail

**Get package history:**

```bash
curl http://localhost:8000/api/packages/audit?package_name=numpy&version=1.21.0
```

**Get agent operations:**

```bash
curl http://localhost:8000/api/packages/audit?agent_id=agent-123
```

**Get recent bans:**

```bash
curl http://localhost:8000/api/packages/audit?banned_only=true
```

### Compliance Reporting

Export audit data for compliance:

```bash
# Export to CSV
curl http://localhost:8000/api/packages/audit?format=csv > packages_audit.csv

# Export to JSON
curl http://localhost:8000/api/packages/audit?format=json > packages_audit.json
```

---

## Best Practices

### For Administrators

1. **Review all requests** - Don't auto-approve package requests
2. **Scan for vulnerabilities** - Run `pip-audit` before approving
3. **Check popularity** - Prefer packages with high download counts
4. **Verify maintainers** - Check package maintainer reputation
5. **Document decisions** - Add notes when approving/rejecting
6. **Review regularly** - Audit approvals monthly for security

### For Developers

1. **Pin versions** - Use exact versions (`==`) for reproducibility
2. **Minimize packages** - Only add packages you actually need
3. **Check maturity** - Verify agent maturity before using packages
4. **Handle errors** - Gracefully handle permission denials
5. **Test locally** - Verify packages work before requesting approval

### For Security Teams

1. **Monitor bans** - Review banned packages list weekly
2. **Scan CVEs** - Check for new CVEs in approved packages
3. **Audit logs** - Review audit trail for suspicious activity
4. **Test governance** - Verify STUDENT blocking works
5. **Update policies** - Adjust maturity gates as needed

---

## See Also

- **[Python Packages Guide](PYTHON_PACKAGES.md)** - User guide for package installation
- **[Package Security](PACKAGE_SECURITY.md)** - Threat model and defenses
- **[API Documentation](../backend/docs/API_DOCUMENTATION.md#python-package-management)** - Complete API reference
- **[Agent Governance](AGENT_GOVERNANCE.md)** - Overall agent maturity system

---

**Phase 35 Status:** ✅ **COMPLETE** (February 19, 2026)
