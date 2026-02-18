# Community Skills Integration Guide

> **Import and use 5,000+ OpenClaw/ClawHub community skills in Atom with enterprise-grade security**

---

## Table of Contents

1. [What are Community Skills?](#what-are-community-skills)
2. [Security & Governance](#security--governance)
3. [Importing Skills](#importing-skills)
4. [Using Skills](#using-skills)
5. [Managing Skills](#managing-skills)
6. [API Reference](#api-reference)
7. [Troubleshooting](#troubleshooting)

---

## What are Community Skills?

**Community Skills** are reusable automation components created by the OpenClaw/ClawHub community. Atom can import and execute these skills while maintaining enterprise-grade security through:

- **Hazard Sandbox** - Isolated Docker containers prevent skills from accessing your host filesystem
- **LLM Security Scanning** - GPT-4 powered analysis detects malicious patterns before activation
- **Governance Integration** - Skills respect agent maturity levels (Student → Autonomous)
- **Audit Trail** - All skill executions logged with full metadata
- **Episodic Memory Integration** - Skill executions create EpisodeSegments for agent learning (Phase 14)
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
4. **Avoid external dependencies** - Use only Python standard library
5. **Test in sandbox first** - Verify skill works in isolated environment

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
