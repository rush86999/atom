# Community Skills Integration Guide

> **Import and use 5,000+ OpenClaw/ClawHub community skills in Atom with enterprise-grade security**

---

## Table of Contents

1. [What are Community Skills?](#what-are-community-skills)
2. [Security & Governance](#security--governance)
3. [Importing Skills](#importing-skills)
4. [Using Skills](#using-skills)
5. [Python Packages for Skills](#python-packages-for-skills)
6. [Managing Skills](#managing-skills)
7. [API Reference](#api-reference)
8. [Troubleshooting](#troubleshooting)

---

## What are Community Skills?

**Community Skills** are reusable automation components created by the OpenClaw/ClawHub community. Atom can import and execute these skills while maintaining enterprise-grade security through:

- **Hazard Sandbox** - Isolated Docker containers prevent skills from accessing your host filesystem
- **LLM Security Scanning** - GPT-4 powered analysis detects malicious patterns before activation
- **Governance Integration** - Skills respect agent maturity levels (Student → Autonomous)
- **Audit Trail** - All skill executions logged with full metadata
- **Episodic Memory Integration** - Skill executions create EpisodeSegments for agent learning (Phase 14)
- **Python Package Support** - Skills can use numpy, pandas, and other packages with dependency isolation (Phase 35)
- **Atom CLI Skills** - 6 built-in skills for controlling the Atom OS CLI (Phase 25)

**Types of Skills:**
- **Prompt Skills** - Natural language instructions (safe for all agents)
- **Python Skills** - Code execution (requires INTERN+ maturity, runs in sandbox)
- **Built-in Skills** - Atom CLI commands (Phase 25)

**Phase 14 Status**: ✅ **COMPLETE** (February 16, 2026)
- All 3 plans executed successfully
- 13/13 verification criteria satisfied (100%)
- 82 tests across 6 test files
- Episodic memory and graduation integration complete

**Phase 25: Atom CLI Skills** (February 18, 2026)
- Converted 6 CLI commands to OpenClaw-compatible skills
- Skills work with Community Skills framework (import, security scan, governance)
- Daemon mode manageable through skill interface
- All 3 plans executed successfully
- 13/13 verification criteria satisfied (100%)
- 82 tests across 6 test files
- Episodic memory and graduation integration complete

---

## Security & Governance

### Skill Lifecycle

```
Import → Untrusted → Security Scan → Active/Banned → Execution
```

1. **Import** - Skills automatically marked as "Untrusted"
2. **Security Scan** - LLM + static analysis for 21+ malicious patterns
3. **Activate** - Promote to "Active" status for agent use
4. **Execute** - Agents run skills in isolated Docker sandbox

### Governance by Agent Level

| Agent Level | Prompt Skills | Python Skills |
|-------------|---------------|---------------|
| **STUDENT** | ✅ Yes | ❌ Blocked (educational) |
| **INTERN** | ✅ Yes | ⚠️ Approval Required |
| **SUPERVISED** | ✅ Yes | ✅ Yes (Real-time monitoring) |
| **AUTONOMOUS** | ✅ Yes | ✅ Yes (Full execution) |

### Security Features

✅ **Network Disabled** - Sandbox containers cannot access external networks
✅ **Read-Only Filesystem** - No persistent storage in container
✅ **5-Minute Timeout** - Skills automatically terminated after 5 minutes
✅ **Memory Limits** - Container memory capped to prevent resource exhaustion
✅ **No Host Mount** - Container cannot access host filesystem
✅ **Audit Logging** - All executions logged to `skill_executions` table

### Security Testing & Validation

Atom includes comprehensive security testing to validate all sandbox constraints and attack prevention mechanisms. The security test suite (`backend/tests/test_package_security.py`) includes 34 tests covering:

**Container Escape Prevention** (4 tests)
- ✅ Privileged mode disabled (prevents CVE-2019-5736, CVE-2025-9074)
- ✅ Docker socket never mounted (prevents Docker-out-of-Docker attacks)
- ✅ Host volumes never mounted (prevents filesystem access)
- ✅ Host PID namespace not shared (prevents process signaling attacks)

**Resource Exhaustion Protection** (4 tests)
- ✅ Memory limits enforced (256m default, prevents DoS)
- ✅ CPU quotas enforced (0.5 cores default, prevents starvation)
- ✅ Timeout enforced (30s default, prevents infinite loops)
- ✅ Auto-remove enabled (prevents disk exhaustion)

**Network Isolation** (2 tests)
- ✅ Network disabled (prevents data exfiltration)
- ✅ No extra hosts (prevents DNS tunneling)

**Filesystem Isolation** (3 tests)
- ✅ Read-only filesystem (prevents malware persistence)
- ✅ Tmpfs only writable (prevents disk writes)
- ✅ No host mounts (prevents container escape)

**Malicious Pattern Detection** (8 tests)
- ✅ Subprocess usage detected (arbitrary command execution)
- ✅ os.system detected (shell injection)
- ✅ eval/exec detected (code injection)
- ✅ Base64 obfuscation detected (payload hiding)
- ✅ Import obfuscation detected (dynamic imports)
- ✅ Pickle unsafe deserialization detected (RCE via deserialization)
- ✅ Network access detected (data exfiltration)
- ✅ Benign code passes (no false positives)

**Vulnerability Scanning** (3 tests)
- ✅ Known CVEs detected via pip-audit
- ✅ Safe packages pass scan
- ✅ Multiple vulnerabilities detected

**Governance Blocking** (4 tests)
- ✅ STUDENT agents blocked from all Python packages
- ✅ STUDENT blocked even from approved packages
- ✅ Banned packages block all agents (even AUTONOMOUS)
- ✅ Unknown packages require approval

**Typosquatting & Dependency Confusion** (4 tests)
- ✅ Typosquatting packages documented (reqeusts, numpyy, panads)
- ✅ Known vulnerable packages with CVE data (5 packages)
- ✅ Dependency confusion packages listed (10 internal-sounding names)

**Integration Tests** (2 tests)
- ✅ Complete security stack validation (static scan + sandbox + governance)
- ✅ Malicious patterns comprehensive coverage

Running Security Tests:

```bash
# Run all security tests
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/test_package_security.py -v

# Run specific test categories
pytest backend/tests/test_package_security.py::TestContainerEscape -v
pytest backend/tests/test_package_security.py::TestResourceExhaustion -v
pytest backend/tests/test_package_security.py::TestMaliciousPatternDetection -v

# With coverage
pytest backend/tests/test_package_security.py --cov=core/skill_sandbox --cov=core/skill_security_scanner --cov=core/package_governance_service --cov-report=term-missing
```

Test Results:
- **Pass Rate:** 100% (34/34 tests)
- **Execution Time:** 1.7 seconds
- **Coverage:** 14.3% (focused on critical security paths)
- **Security Levels:** 8 CRITICAL, 10 HIGH, 6 MEDIUM, 10 LOW

Malicious Package Fixtures:

The test suite includes 450+ lines of malicious package fixtures (`backend/tests/fixtures/malicious_packages.py`) for reproducible testing:

- Container escape scenarios (privileged mode, Docker socket, cgroup)
- Resource exhaustion (fork bomb, memory, CPU, disk)
- Network exfiltration (urllib, sockets, requests, DNS tunneling)
- Filesystem attacks (host write, directory traversal, symlink escape)
- Code execution (subprocess, os.system, eval, exec, pickle)
- Obfuscation techniques (base64, import obfuscation, string concat)

**Security Best Practices:**

1. **Never run untrusted code outside sandbox** - Always use HazardSandbox for Python skills
2. **Validate security constraints before execution** - Check governance, scan for vulnerabilities
3. **Use maturity-based access controls** - STUDENT agents blocked from Python packages
4. **Monitor for suspicious patterns** - Static scanning detects 21+ malicious signatures
5. **Test security defenses** - Run security test suite before deploying to production
6. **Keep packages updated** - pip-audit scans for known CVEs before installation
7. **Review audit logs** - All skill executions logged to `skill_executions` table

---

## Importing Skills

### Via GitHub URL (Recommended)

```bash
curl -X POST http://localhost:8000/api/skills/import \
  -H "Content-Type: application/json" \
  -d '{
    "source": "github_url",
    "url": "https://github.com/openclaw/skills/tree/main/email-sorter"
  }'
```

**Response:**
```json
{
  "success": true,
  "skill_id": "email-sorter",
  "name": "Email Sorter",
  "status": "Untrusted",
  "security_scan_result": "pending",
  "message": "Skill imported successfully. Awaiting security scan."
}
```

### Via File Upload

```bash
curl -X POST http://localhost:8000/api/skills/import \
  -F "file=@/path/to/SKILL.md" \
  -F "source=file_upload"
```

### Via Raw Content

```bash
curl -X POST http://localhost:8000/api/skills/import \
  -H "Content-Type: application/json" \
  -d '{
    "source": "raw_content",
    "content": "---\nname: My Skill\n...\nInstructions here..."
  }'
```

---

## Using Skills

### Check Skill Status

```bash
curl http://localhost:8000/api/skills/email-sorter
```

**Response:**
```json
{
  "skill_id": "email-sorter",
  "name": "Email Sorter",
  "description": "Automatically sorts emails into folders",
  "status": "Active",
  "skill_type": "python",
  "security_scan_result": "LOW",
  "created_at": "2026-02-16T12:00:00Z"
}
```

### Execute a Skill

**Prompt Skill:**
```bash
curl -X POST http://localhost:8000/api/skills/execute \
  -H "Content-Type: application/json" \
  -d '{
    "skill_id": "email-sorter",
    "agent_id": "my-agent",
    "inputs": {
      "mailbox": "inbox",
      "criteria": "urgent"
    }
  }'
```

**Python Skill (in sandbox):**
```bash
curl -X POST http://localhost:8000/api/skills/execute \
  -H "Content-Type: application/json" \
  -d '{
    "skill_id": "data-analyzer",
    "agent_id": "my-agent",
    "inputs": {
      "data_file": "/tmp/data.csv",
      "analysis_type": "sentiment"
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "execution_id": "exec_123",
  "result": {
    "status": "completed",
    "output": "Analysis complete: 85% positive sentiment",
    "duration_seconds": 2.3
  },
  "container_id": "abc123def"
}
```

## Atom CLI Skills

Atom includes 6 built-in skills for controlling the Atom OS CLI:

| Skill | Maturity | Description |
|-------|----------|-------------|
| atom-daemon | AUTONOMOUS | Start background daemon |
| atom-status | STUDENT | Check daemon status (PID, memory, CPU) |
| atom-start | AUTONOMOUS | Start server (foreground) |
| atom-stop | AUTONOMOUS | Stop daemon gracefully |
| atom-execute | AUTONOMOUS | Execute on-demand command |
| atom-config | STUDENT | Show configuration and environment |

**Features:**
- **Governance Gates**: AUTONOMOUS required for daemon control, STUDENT for read-only
- **Natural Language Parsing**: CLI commands understand "port 3000", "dev mode", etc.
- **Structured Output**: JSON responses with stdout, stderr, returncode
- **Error Handling**: 30-second timeout prevents hanging processes
- **Security Integration**: All executions logged to ShellSession table

**Usage Example:**
```bash
# Start daemon (requires AUTONOMOUS agent)
curl -X POST http://localhost:8000/api/skills/execute \
  -H "Content-Type: application/json" \
  -d '{
    "skill_id": "atom-daemon",
    "query": "start daemon on port 3000 with dev mode"
  }'

# Check status (works with STUDENT+)
curl -X POST http://localhost:8000/api/skills/execute \
  -H "Content-Type: application/json" \
  -d '{
    "skill_id": "atom-status",
    "query": "show daemon status"
  }'
```

**See:** [ATOM_CLI_SKILLS_GUIDE.md](./ATOM_CLI_SKILLS_GUIDE.md) for complete documentation.

---

## Python Packages for Skills

Skills can now use Python packages (numpy, pandas, requests, etc.) through per-skill Docker images with dependency isolation.

### Package Dependencies in SKILL.md

Add Python packages to your SKILL.md file using the `packages` field in YAML frontmatter:

```yaml
---
name: "Data Processing Skill"
description: "Analyzes CSV data using pandas and numpy"
skill_type: python_code
packages:
  - pandas==1.3.0      # Exact version (recommended)
  - numpy>=1.21.0      # Minimum version
  - matplotlib~=3.4.0  # Compatible release
---

import pandas as pd
import numpy as np

def process_data(file_path):
    """Process CSV file and return statistics."""
    data = pd.read_csv(file_path)
    return {
        "rows": len(data),
        "columns": len(data.columns),
        "mean": data.mean(numeric_only=True).to_dict()
    }
```

### Package Version Formats

| Format | Example | Description | Recommended |
|--------|---------|-------------|-------------|
| **Exact** | `pandas==1.3.0` | Exactly version 1.3.0 | ✅ Yes (reproducible) |
| **Minimum** | `numpy>=1.21.0` | 1.21.0 or higher | ⚠️ Use with caution |
| **Compatible** | `requests~=2.28.0` | >=2.28.0, <2.29.0 | ✅ Yes for bug fixes |
| **Any** | `scipy` | Latest version | ❌ No (may break) |

**Recommendation:** Use exact versions (`==`) for production skills to ensure reproducibility.

### Installing Packages

**Response:**
```json
{
  "success": true,
  "skill_id": "data-analysis-skill",
  "image_tag": "atom-skill:data-analysis-skill-v1",
  "packages_installed": [
    {"name": "numpy", "version": "==1.21.0"},
    {"name": "pandas", "version": ">=1.3.0"}
  ],
  "vulnerabilities": [],
  "build_logs": ["Successfully built abc123"]
}
```

### Executing with Packages

```bash
curl -X POST http://localhost:8000/api/packages/execute \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_789",
    "skill_id": "data-analysis-skill",
    "code": "import numpy as np; print(np.array([1, 2, 3]))"
  }'
```

**Response:**
```json
{
  "success": true,
  "skill_id": "data-analysis-skill",
  "output": "[1 2 3]"
}
```

### Package Governance

| Agent Level | Package Access |
|-------------|---------------|
| **STUDENT** | ❌ Blocked (educational restriction) |
| **INTERN** | ⚠️ Approval Required for each package |
| **SUPERVISED** | ✅ If package approved for SUPERVISED+ |
| **AUTONOMOUS** | ✅ If package approved for AUTONOMOUS |

### Security Features

- ✅ **Vulnerability Scanning** - pip-audit + Safety DB before installation
- ✅ **Per-Skill Isolation** - No dependency conflicts (Skill A uses numpy 1.21, Skill B uses 1.24)
- ✅ **Read-Only Filesystem** - No persistent storage in containers
- ✅ **Non-Root User** - Skills run as unprivileged user
- ✅ **Resource Limits** - Memory and CPU quotas enforced
- ✅ **Audit Trail** - All package operations logged

### Cleanup

Remove skill image when no longer needed:

```bash
curl -X DELETE http://localhost:8000/api/packages/data-analysis-skill?agent_id=agent_789
```

**See:** [API Documentation](../backend/docs/API_DOCUMENTATION.md#python-package-management) for complete reference.

---

## npm Packages for Skills

Skills can use Node.js/npm packages (lodash, express, axios, etc.) through per-skill Docker images with dependency isolation, matching OpenClaw capabilities.

### Package Dependencies in SKILL.md

Add npm packages to your SKILL.md file using the `node_packages` field in YAML frontmatter:

```yaml
---
name: "Data Processing Skill"
description: "Process data using Lodash"
skill_type: nodejs_code
node_packages:
  - lodash@4.17.21      # Exact version (recommended)
  - axios@^1.6.0        # Compatible version
package_manager: npm    # Optional: npm (default), yarn, or pnpm
---

const _ = require('lodash');
const axios = require('axios');

async function processData(query) {
    const data = _.map(query.split(','), Number);
    return _.sum(data);
}

processData(inputs.query || '1,2,3,4,5');
```

### Package Version Formats

| Format | Example | Description | Recommended |
|--------|---------|-------------|-------------|
| **Exact** | `lodash@4.17.21` | Exactly version 4.17.21 | ✅ Yes (reproducible) |
| **Caret** | `axios@^1.6.0` | Compatible with 1.6.0+ (minor/patch) | ⚠️ Testing only |
| **Tilde** | `express@~4.18.0` | Patch updates only (4.18.x) | ⚠️ Testing only |
| **Greater** | `moment@>=2.29.0` | Minimum version | ❌ Avoid |
| **Wildcard** | `chalk@*` | Latest version | ❌ No (security risk) |

### Package Manager Options

- **npm** (default): Standard Node.js package manager, most compatible
- **yarn**: Faster installs, PnP mode support, selective version resolution
- **pnpm**: Strict dependency isolation, prevents phantom dependencies, highest security

**Recommendation:** Use exact versions (`@4.17.21`) for production skills to ensure reproducibility.

### Scoped Packages

```yaml
node_packages:
  - @babel/core@7.23.0
  - @types/node@^20.0.0
  - @typescript-eslint/parser@^6.0.0
```

### Installing Packages

**Request:**
```bash
curl -X POST http://localhost:8000/api/packages/npm/install \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_789",
    "skill_id": "data-analysis-skill",
    "packages": ["lodash@4.17.21", "axios@^1.6.0"],
    "package_manager": "npm"
  }'
```

**Response:**
```json
{
  "success": true,
  "skill_id": "data-analysis-skill",
  "image_tag": "atom-npm-skill:data-analysis-skill-v1",
  "packages_installed": [
    {"name": "lodash", "version": "4.17.21"},
    {"name": "axios", "version": "1.6.2"}
  ],
  "vulnerabilities": [],
  "build_logs": ["Successfully built abc123"]
}
```

### Executing with Packages

```bash
curl -X POST http://localhost:8000/api/packages/npm/execute \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "agent_789",
    "skill_id": "data-analysis-skill",
    "code": "const _ = require(\"lodash\"); _.sum([1, 2, 3]);"
  }'
```

**Response:**
```json
{
  "success": true,
  "skill_id": "data-analysis-skill",
  "output": "6",
  "execution_time_ms": 234
}
```

### Package Governance

| Agent Level | npm Package Access |
|-------------|-------------------|
| **STUDENT** | ❌ Blocked (educational restriction) |
| **INTERN** | ⚠️ Approval Required for each package |
| **SUPERVISED** | ✅ If package approved for SUPERVISED+ |
| **AUTONOMOUS** | ✅ If package approved for AUTONOMOUS |

**Banned packages block all agents regardless of maturity.**

### Security Features

- ✅ **Postinstall Script Blocking** - --ignore-scripts flag prevents Shai-Hulud attacks
- ✅ **Vulnerability Scanning** - npm audit + Snyk before installation
- ✅ **Per-Skill Isolation** - No dependency conflicts (Skill A uses lodash 4.17, Skill B uses 5.0)
- ✅ **Network Disabled** - Containers cannot access external networks
- ✅ **Read-Only Filesystem** - No persistent storage in containers
- ✅ **Non-Root User** - Skills run as nodejs (UID 1001)
- ✅ **Resource Limits** - Memory and CPU quotas enforced
- ✅ **Audit Trail** - All package operations logged

### Threat Mitigation

**Postinstall Script Malware (Shai-Hulud/Sha1-Hulud Attacks):**
- September/November 2025: 700+ npm packages infected, 25K+ repositories affected
- Mitigation: Automatic --ignore-scripts flag, pre-installation script analysis
- Detection: Malicious patterns (fetch, axios, child_process, process.env, fs.readFile)

**Typosquatting Attacks:**
- Threat: Malicious packages with names similar to popular packages (e.g., `exprss` vs `express`)
- Mitigation: Package metadata validation, download count checks, maintainer verification
- Examples: `exprss`, `lodas`, `nodemailer` (misspelled variants)

**Dependency Confusion:**
- Threat: Attackers publish malicious packages with internal package names
- Mitigation: Exact version pinning, npm scope usage (@scope/package-name), registry priority

### Cleanup

Remove skill image when no longer needed:

```bash
curl -X DELETE http://localhost:8000/api/packages/npm/data-analysis-skill
```

**See:** [npm Package Support](NPM_PACKAGE_SUPPORT.md) for comprehensive user guide.

---

## Managing Skills

### List All Skills

```bash
# All skills
curl http://localhost:8000/api/skills/list

# Filter by status
curl http://localhost:8000/api/skills/list?status=Active
curl http://localhost:8000/api/skills/list?status=Untrusted
curl http://localhost:8000/api/skills/list?status=Banned
```

### Promote Skill to Active

```bash
curl -X POST http://localhost:8000/api/skills/email-sorter/promote \
  -H "Content-Type: application/json" \
  -d '{
    "status": "Active",
    "reason": "Security scan passed, code reviewed"
  }'
```

### Ban a Skill

```bash
curl -X POST http://localhost:8000/api/skills/suspicious-skill/promote \
  -H "Content-Type: application/json" \
  -d '{
    "status": "Banned",
    "reason": "Security scan detected suspicious patterns"
  }'
```

### View Skill Execution History

```bash
curl http://localhost:8000/api/skills/email-sorter/executions
```

---

## API Reference

### Import Skill

**Endpoint:** `POST /api/skills/import`

**Parameters:**
- `source` (string): "github_url", "file_upload", or "raw_content"
- `url` (string, optional): GitHub URL for skill
- `file` (file, optional): SKILL.md file upload
- `content` (string, optional): Raw skill content

**Response:** Skill object with `status: "Untrusted"`

### List Skills

**Endpoint:** `GET /api/skills/list?status={status}`

**Parameters:**
- `status` (optional): "Active", "Untrusted", "Banned", or "All"

**Response:** Array of skill objects

### Get Skill Details

**Endpoint:** `GET /api/skills/{skill_id}`

**Response:** Full skill object with metadata

### Execute Skill

**Endpoint:** `POST /api/skills/execute`

**Parameters:**
- `skill_id` (string): Skill identifier
- `agent_id` (string): Agent executing the skill
- `inputs` (object): Skill input parameters

**Response:** Execution result with output and metadata

### Promote Skill

**Endpoint:** `POST /api/skills/{skill_id}/promote`

**Parameters:**
- `status` (string): "Active" or "Banned"
- `reason` (string): Reason for status change

**Response:** Updated skill object

### Get Skill Episodes

**Endpoint:** `GET /api/skills/{skill_id}/episodes`

**Response:** Array of episodic memories from skill executions

---

## Troubleshooting

### Skill Import Failed

**Error:** `Failed to parse SKILL.md`

**Solution:** Ensure the SKILL.md file has valid YAML frontmatter with `---` delimiters:

```markdown
---
name: My Skill
description: Does something cool
---

Instructions here...
```

### Security Scan Failed

**Error:** `Security scan detected malicious patterns`

**Solution:** Review the security scan results:
```bash
curl http://localhost:8000/api/skills/my-skill | jq '.security_scan_details'
```

Common issues:
- File system access attempts (`os.open`, `open()`)
- Network operations (`requests`, `urllib`)
- Subprocess execution (`subprocess`, `os.system`)
- Data exfiltration patterns

### Skill Execution Timeout

**Error:** `Skill execution exceeded 5-minute timeout`

**Solution:**
1. Optimize skill code for faster execution
2. Break long-running tasks into smaller chunks
3. Check for infinite loops or blocking operations

### Docker Sandbox Not Available

**Error:** `HazardSandbox requires Docker daemon`

**Solution:**
```bash
# Check Docker is running
docker ps

# Start Docker if needed
# macOS: Open Docker Desktop
# Linux: sudo systemctl start docker
```

### STUDENT Agent Blocked from Python Skill

**Error:** `STUDENT agents cannot execute Python skills`

**Solution:** This is by design for safety. Options:
1. Promote agent to INTERN level
2. Use prompt-only version of skill
3. Manually approve execution (INTERN requires approval)

---

## Best Practices

### For Skill Authors

1. **Use prompt skills when possible** - Safer and work for all agents
2. **Document inputs clearly** - Include schema in SKILL.md
3. **Handle errors gracefully** - Return meaningful error messages
4. **Minimize external dependencies** - If using Python packages, declare in SKILL.md `requirements:` field
5. **Test in sandbox first** - Verify skill works in isolated environment
6. **Declare package dependencies** - All Python packages scanned for vulnerabilities before installation (Phase 35)

### For Skill Consumers

1. **Review security scan results** - Check for flagged patterns
2. **Test with low-maturity agents** - Start with INTERN/SUPERVISED
3. **Monitor execution logs** - Review `skill_executions` table
4. **Keep skills updated** - Pull latest versions from GitHub
5. **Ban suspicious skills** - Remove skills that fail security scan

---

## Examples

### Example 1: Import and Use Email Sorter Skill

```bash
# 1. Import skill
curl -X POST http://localhost:8000/api/skills/import \
  -H "Content-Type: application/json" \
  -d '{
    "source": "github_url",
    "url": "https://github.com/openclaw/skills/tree/main/email-sorter"
  }'

# 2. Check security scan results
curl http://localhost:8000/api/skills/email-sorter

# 3. Promote to Active (if scan passed)
curl -X POST http://localhost:8000/api/skills/email-sorter/promote \
  -H "Content-Type: application/json" \
  -d '{"status": "Active", "reason": "Reviewed and safe"}'

# 4. Execute skill
curl -X POST http://localhost:8000/api/skills/execute \
  -H "Content-Type: application/json" \
  -d '{
    "skill_id": "email-sorter",
    "agent_id": "my-assistant",
    "inputs": {
      "mailbox": "inbox",
      "folder": "work"
    }
  }'
```

### Example 2: List All Active Skills

```bash
curl http://localhost:8000/api/skills/list?status=Active | jq '.skills[] | {name: .name, type: .skill_type}'
```

**Output:**
```json
{
  "name": "Email Sorter",
  "type": "python"
}
{
  "name": "Meeting Scheduler",
  "type": "prompt"
}
```

### Example 3: View Skill Execution History

```bash
curl http://localhost:8000/api/skills/email-sorter/executions | jq '.executions[] | {date: .created_at, result: .result}'
```

---

## Next Steps

1. **Browse OpenClaw Skills**: https://github.com/openclaw/skills
2. **Import Your First Skill**: Use the examples above
3. **Review Security Scans**: Check scan results before activation
4. **Monitor Executions**: Review execution logs regularly
5. **Contribute Skills**: Create and share your own skills

---

## Related Documentation

- [Phase 14 Verification →](../.planning/phases/14-community-skills-integration/14-VERIFICATION.md) - Complete with 13/13 success criteria verified ✅
- [Agent Governance →](AGENT_GOVERNANCE.md)
- [Episodic Memory →](EPISODIC_MEMORY_IMPLEMENTATION.md) - Skill executions create EpisodeSegments for learning
- [Agent Graduation →](AGENT_GRADUATION_GUIDE.md) - Community skills count toward graduation readiness
- [API Documentation →](../backend/docs/API_DOCUMENTATION.md)

---

**Last Updated**: February 18, 2026
