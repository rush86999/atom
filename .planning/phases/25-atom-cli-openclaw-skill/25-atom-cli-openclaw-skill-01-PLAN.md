---
phase: 25-atom-cli-openclaw-skill
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/skills/atom-cli/atom-daemon.md
  - backend/skills/atom-cli/atom-status.md
  - backend/skills/atom-cli/atom-start.md
  - backend/skills/atom-cli/atom-stop.md
  - backend/skills/atom-cli/atom-execute.md
  - backend/skills/atom-cli/atom-config.md
autonomous: true

must_haves:
  truths:
    - "Agents can import CLI commands as skills via existing /api/skills/import endpoint"
    - "Each CLI command has a separate SKILL.md file with proper YAML frontmatter"
    - "Daemon control commands (daemon, start, stop) require AUTONOMOUS maturity"
    - "Status and config commands are readable by all maturity levels (STUDENT+)"
    - "Skills follow Phase 14 SKILL.md format (name, description, version, tags, governance)"
  artifacts:
    - path: "backend/skills/atom-cli/atom-daemon.md"
      provides: "Daemon command skill with AUTONOMOUS maturity gate"
      contains: "maturity_requirement: AUTONOMOUS"
    - path: "backend/skills/atom-cli/atom-status.md"
      provides: "Status check skill (read-only, STUDENT+)"
      contains: "maturity_requirement: STUDENT"
    - path: "backend/skills/atom-cli/atom-start.md"
      provides: "Start server command skill with AUTONOMOUS maturity gate"
      contains: "maturity_requirement: AUTONOMOUS"
    - path: "backend/skills/atom-cli/atom-stop.md"
      provides: "Stop daemon command skill with AUTONOMOUS maturity gate"
      contains: "maturity_requirement: AUTONOMOUS"
    - path: "backend/skills/atom-cli/atom-execute.md"
      provides: "Execute on-demand command skill with AUTONOMOUS maturity gate"
      contains: "maturity_requirement: AUTONOMOUS"
    - path: "backend/skills/atom-cli/atom-config.md"
      provides: "Config display skill (read-only, STUDENT+)"
      contains: "maturity_requirement: STUDENT"
  key_links:
    - from: "backend/skills/atom-cli/*.md"
      to: "backend/core/skill_parser.py"
      via: "python-frontmatter YAML parsing"
      pattern: "frontmatter.loads"
    - from: "backend/skills/atom-cli/*.md"
      to: "backend/core/skill_registry_service.py"
      via: "import_skill endpoint"
      pattern: "POST /api/skills/import"
---

<objective>
Create 6 OpenClaw-compatible SKILL.md files for Atom CLI commands.

Purpose: Enable agents to control Atom CLI (daemon, status, start, stop, execute, config) through the existing Community Skills framework. Each CLI command becomes a separate skill with appropriate maturity gates.

Output: 6 SKILL.md files in backend/skills/atom-cli/ directory with YAML frontmatter, prompt bodies, and governance tags.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/25-atom-cli-openclaw-skill/25-RESEARCH.md
@.planning/phases/14-community-skills-integration/14-RESEARCH.md
@backend/core/skill_parser.py
@backend/core/skill_registry_service.py
@backend/cli/main.py
@backend/cli/daemon.py
@docs/COMMUNITY_SKILLS.md
</context>

<tasks>

<task type="auto">
  <name>Create atom-daemon.md SKILL file</name>
  <files>backend/skills/atom-cli/atom-daemon.md</files>
  <action>
    Create backend/skills/atom-cli/atom-daemon.md with:

    1. YAML frontmatter:
       - name: atom-daemon
       - description: "Start Atom OS as background daemon service with PID tracking"
       - version: 1.0.0
       - author: Atom Team
       - tags: [atom, cli, daemon, service-management]
       - maturity_level: AUTONOMOUS
       - governance.maturity_requirement: AUTONOMOUS
       - governance.reason: "Daemon control manages background services"

    2. Prompt body with:
       - Usage: atom-os daemon [options]
       - Options: --port, --host, --workers, --host-mount, --dev, --foreground
       - Examples: default port, custom port with dev mode, host mount
       - Output format description (PID, status, dashboard URL)
       - Warning: AUTONOMOUS maturity required

    3. Use cli/daemon.py as reference (DaemonManager.start_daemon)

    Follow pattern from 25-RESEARCH.md Example 1.
  </action>
  <verify>
    File exists with valid YAML frontmatter (use frontmatter.loads to test)
    Contains maturity_requirement: AUTONOMOUS
    Contains all CLI options from daemon command
  </verify>
  <done>
    atom-daemon.md file created, parses successfully with SkillParser, AUTONOMOUS gate set
  </done>
</task>

<task type="auto">
  <name>Create atom-status.md and atom-config.md SKILL files</name>
  <files>backend/skills/atom-cli/atom-status.md backend/skills/atom-cli/atom-config.md</files>
  <action>
    Create two read-only skill files with STUDENT maturity level:

    1. atom-status.md:
       - name: atom-status
       - description: "Check Atom OS daemon status (running state, PID, uptime, memory, CPU)"
       - maturity_level: STUDENT
       - governance.maturity_requirement: STUDENT
       - governance.reason: "Read-only status check"
       - Usage: atom-os status
       - Output: running status, PID, memory, CPU, uptime, dashboard URL

    2. atom-config.md:
       - name: atom-config
       - description: "Show Atom OS configuration and environment variables"
       - maturity_level: STUDENT
       - governance.maturity_requirement: STUDENT
       - governance.reason: "Read-only configuration display"
       - Usage: atom-os config [--show-daemon]
       - Sections: Server, Daemon, Host Mount, Database, LLM Providers

    Both commands are read-only, safe for all maturity levels.
  </action>
  <verify>
    Both files exist with maturity_requirement: STUDENT
    Both files parse successfully with SkillParser
    Status file includes all output fields (PID, memory, CPU, uptime)
    Config file includes all environment variable sections
  </verify>
  <done>
    atom-status.md and atom-config.md created, STUDENT maturity gates, read-only operations documented
  </done>
</task>

<task type="auto">
  <name>Create atom-start.md, atom-stop.md, atom-execute.md SKILL files</name>
  <files>backend/skills/atom-cli/atom-start.md backend/skills/atom-cli/atom-stop.md backend/skills/atom-cli/atom-execute.md</files>
  <action>
    Create three AUTONOMOUS-gated skill files for daemon control:

    1. atom-start.md:
       - name: atom-start
       - description: "Start Atom OS server (foreground, not daemon)"
       - maturity_level: AUTONOMOUS
       - governance.maturity_requirement: AUTONOMOUS
       - governance.reason: "Server start manages system resources"
       - Options: --port, --host, --workers, --host-mount, --dev
       - Note: Runs in foreground (use atom-daemon for background)

    2. atom-stop.md:
       - name: atom-stop
       - description: "Stop Atom OS background daemon gracefully"
       - maturity_level: AUTONOMOUS
       - governance.maturity_requirement: AUTONOMOUS
       - governance.reason: "Stopping daemon terminates service"
       - Usage: atom-os stop
       - Behavior: SIGTERM then SIGKILL after 10s timeout

    3. atom-execute.md:
       - name: atom-execute
       - description: "Execute Atom command on-demand (temporary startup)"
       - maturity_level: AUTONOMOUS
       - governance.maturity_requirement: AUTONOMOUS
       - governance.reason: "On-demand execution requires full autonomy"
       - Usage: atom-os execute <command>
       - Note: Command routing not yet implemented, use REST API
       - API reference: POST /api/agent/start, POST /api/agent/execute
  </action>
  <verify>
    All three files exist with maturity_requirement: AUTONOMOUS
    All files parse successfully with SkillParser
    atom-start.md has all CLI options
    atom-stop.md describes SIGTERM/SIGKILL behavior
    atom-execute.md mentions REST API workaround
  </verify>
  <done>
    atom-start.md, atom-stop.md, atom-execute.md created, all AUTONOMOUS gates, all options documented
  </done>
</task>

</tasks>

<verification>
1. All 6 SKILL.md files exist in backend/skills/atom-cli/
2. Each file parses successfully with python-frontmatter (no YAML errors)
3. Each file has required frontmatter fields: name, description, version, author, tags
4. Governance maturity requirements set correctly (AUTONOMOUS for daemon control, STUDENT for read-only)
5. CLI options match cli/main.py command definitions
6. Skills follow Phase 14 SKILL.md format (compatible with SkillParser)
</verification>

<success_criteria>
1. 6 SKILL.md files created, all parse successfully
2. Skills can be imported via existing /api/skills/import endpoint
3. AUTONOMOUS maturity gates on daemon/start/stop/execute skills
4. STUDENT maturity access on status/config skills
5. Each skill documents CLI usage, options, examples, and output format
</success_criteria>

<output>
After completion, create `.planning/phases/25-atom-cli-openclaw-skill/25-atom-cli-openclaw-skill-01-SUMMARY.md` with:
- Files created (6 SKILL.md files)
- Governance maturity assignments
- CLI options coverage
- Parse verification results
- Next steps (Plan 02: subprocess wrapper)
</output>
