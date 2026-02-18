---
phase: 25-atom-cli-openclaw-skill
plan: 04
type: execute
wave: 2
depends_on: [01, 02, 03]
files_modified:
  - docs/ATOM_CLI_SKILLS_GUIDE.md
  - docs/COMMUNITY_SKILLS.md
  - CLAUDE.md
  - .planning/ROADMAP.md
autonomous: true

must_haves:
  truths:
    - "Users can import CLI skills using documented workflow"
    - "Documentation explains maturity requirements for each skill"
    - "Agents can execute CLI commands through skill interface"
    - "CLI skills integrate with existing Community Skills framework"
    - "All verification criteria from phase goal satisfied"
  artifacts:
    - path: "docs/ATOM_CLI_SKILLS_GUIDE.md"
      provides: "Comprehensive user guide for Atom CLI skills"
      contains: "Import workflow"
      contains: "Skill reference (all 6 commands)"
      contains: "Maturity requirements"
      contains: "Troubleshooting"
    - path: "docs/COMMUNITY_SKILLS.md"
      provides: "Updated community skills documentation with CLI skills section"
      contains: "atom-cli skills"
    - path: "CLAUDE.md"
      provides: "Updated project context with Phase 25 reference"
      contains: "Phase 25"
  key_links:
    - from: "docs/ATOM_CLI_SKILLS_GUIDE.md"
      to: "docs/COMMUNITY_SKILLS.md"
      via: "Community Skills integration reference"
      pattern: "COMMUNITY_SKILLS"
    - from: "docs/ATOM_CLI_SKILLS_GUIDE.md"
      to: "backend/api/skill_routes.py"
      via: "POST /api/skills/import endpoint"
      pattern: "/api/skills/import"
---

<objective>
Create user documentation and verify Phase 25 completion.

Purpose: Document the Atom CLI skills feature for users, update existing documentation with CLI skills section, and verify all phase success criteria are met.

Output: ATOM_CLI_SKILLS_GUIDE.md, updated COMMUNITY_SKILLS.md, CLAUDE.md with Phase 25, ROADMAP.md update.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/25-atom-cli-openclaw-skill/25-RESEARCH.md
@.planning/phases/25-atom-cli-openclaw-skill/25-atom-cli-openclaw-skill-01-SUMMARY.md
@.planning/phases/25-atom-cli-openclaw-skill/25-atom-cli-openclaw-skill-02-SUMMARY.md
@.planning/phases/25-atom-cli-openclaw-skill/25-atom-cli-openclaw-skill-03-SUMMARY.md
@docs/COMMUNITY_SKILLS.md
@docs/PERSONAL_EDITION.md
@CLAUDE.md
@.planning/ROADMAP.md
</context>

<tasks>

<task type="auto">
  <name>Create ATOM_CLI_SKILLS_GUIDE.md documentation</name>
  <files>docs/ATOM_CLI_SKILLS_GUIDE.md</files>
  <action>
    Create docs/ATOM_CLI_SKILLS_GUIDE.md with:

    1. Table of Contents:
       - What are Atom CLI Skills?
       - Why Use CLI Skills?
       - Maturity Requirements
       - Quick Start
       - Skill Reference (all 6 commands)
       - Import Workflow
       - Usage Examples
       - Troubleshooting
       - API Reference

    2. What are Atom CLI Skills?:
       - Convert CLI commands to OpenClaw skills
       - Enable cross-platform agent control
       - Integrate with Community Skills framework

    3. Maturity Requirements table:
       | Skill | Maturity Level | Reason |
       |-------|----------------|--------|
       | atom-daemon | AUTONOMOUS | Daemon control manages background services |
       | atom-status | STUDENT | Read-only status check |
       | atom-start | AUTONOMOUS | Server start manages system resources |
       | atom-stop | AUTONOMOUS | Stopping daemon terminates service |
       | atom-execute | AUTONOMOUS | On-demand execution requires full autonomy |
       | atom-config | STUDENT | Read-only configuration display |

    4. Quick Start:
       - Import: curl -X POST http://localhost:8000/api/skills/import ...
       - Execute: curl -X POST http://localhost:8000/api/skills/execute ...

    5. Skill Reference (detailed docs for each of 6 commands):
       - Usage, Options, Examples, Output format

    6. Troubleshooting:
       - Command not found (atom-os not in PATH)
       - Permission denied (AUTONOMOUS gate)
       - Daemon race conditions (wait for status)
       - PID file errors

    7. Cross-link to COMMUNITY_SKILLS.md and PERSONAL_EDITION.md

    Target: 400+ lines comprehensive guide.
  </action>
  <verify>
    File created with all sections from TOC
    Maturity requirements table complete
    All 6 skills documented with usage/examples
    Troubleshooting section covers common issues
    Cross-references to COMMUNITY_SKILLS.md and PERSONAL_EDITION.md
  </verify>
  <done>
    ATOM_CLI_SKILLS_GUIDE.md created with comprehensive CLI skills documentation
  </done>
</task>

<task type="auto">
  <name>Update COMMUNITY_SKILLS.md with CLI skills section</name>
  <files>docs/COMMUNITY_SKILLS.md</files>
  <action>
    Update docs/COMMUNITY_SKILLS.md:

    1. Add to "What are Community Skills?" section:
       - Mention Atom CLI skills as built-in skills
       - Note: "Atom also includes 6 built-in CLI skills for daemon control"

    2. Add new section after "Using Skills":
       ## Atom CLI Skills

       Atom includes 6 built-in skills for controlling the Atom OS CLI:

       | Skill | Maturity | Description |
       |-------|----------|-------------|
       | atom-daemon | AUTONOMOUS | Start background daemon |
       | atom-status | STUDENT | Check daemon status |
       | atom-start | AUTONOMOUS | Start server (foreground) |
       | atom-stop | AUTONOMOUS | Stop daemon |
       | atom-execute | AUTONOMOUS | Execute on-demand command |
       | atom-config | STUDENT | Show configuration |

       **See:** [ATOM_CLI_SKILLS_GUIDE.md](ATOM_CLI_SKILLS_GUIDE.md) for complete documentation.

    3. Update Phase 14 status:
       - Add "Phase 25: Atom CLI Skills" to related work

    4. Add CLI skills to "Types of Skills" section:
       - Built-in Skills: Atom CLI commands (Phase 25)

    5. Update cross-references if needed

    Follow existing COMMUNITY_SKILLS.md format and style.
  </action>
  <verify>
    COMMUNITY_SKILLS.md updated with CLI skills section
    CLI skills table included
    Cross-reference to ATOM_CLI_SKILLS_GUIDE.md
      - Da
      Phase 25 mentioned in related work
  </verify>
  <done>
    COMMUNITY_SKILLS.md updated with CLI skills section, cross-references, Phase 25 mention
  </done>
</task>

<task type="auto">
  <name>Update CLAUDE.md and ROADMAP.md with Phase 25</name>
  <files>CLAUDE.md .planning/ROADMAP.md</files>
  <action>
    Update CLAUDE.md:

    1. Add to "Recent Major Changes" section:
       ### Phase 25: Atom CLI as OpenClaw Skills (Feb 18, 2026)
       - Converted 6 CLI commands to OpenClaw-compatible skills
       - Skills work with Community Skills framework (import, security scan, governance)
       - Daemon mode manageable via skill interface
       - AUTONOMOUS maturity gate for daemon control, STUDENT for status/config
       - See: docs/ATOM_CLI_SKILLS_GUIDE.md

    2. Update Key Services:
       - atom_cli_skill_wrapper.py - Subprocess wrapper for CLI command execution

    3. Update Key Directories:
       - backend/skills/atom-cli/ - OpenClaw skill definitions for CLI commands

    4. Update docs/ATOM_CLI_SKILLS_GUIDE.md in Important File Locations

    5. Update Last Updated date

    Update .planning/ROADMAP.md:

    1. Add Phase 25 entry:
       - [ ] **Phase 25: Atom CLI as OpenClaw Skill** - Convert CLI commands to skills
         - Plan 01: Create 6 SKILL.md files (daemon, status, start, stop, execute, config)
         - Plan 02: Create subprocess wrapper service
         - Plan 03: Test skill import and execution
         - Plan 04: Documentation and verification

    2. Add Phase 25 to planning progress

    Follow existing ROADMAP.md format.
  </action>
  <verify>
    CLAUDE.md updated with Phase 25 section
    Key Services includes atom_cli_skill_wrapper.py
    Key Directories includes backend/skills/atom-cli/
    ROADMAP.md has Phase 25 entry with all 4 plans
    Last Updated date current
  </verify>
  <done>
    CLAUDE.md and ROADMAP.md updated with Phase 25 content
  </done>
</task>

<task type="auto">
  <name>Create phase verification summary</name>
  <files>.planning/phases/25-atom-cli-openclaw-skill/25-VERIFICATION.md</files>
  <action>
    Create .planning/phases/25-atom-cli-openclaw-skill/25-VERIFICATION.md with:

    1. Phase Goal Verification:
       - [ ] Atom CLI commands wrapped as OpenClaw skills with SKILL.md metadata
       - [ ] Skills work with Community Skills framework (import, security scan, governance)
       - [ ] CLI commands can be executed by agents through skill system
       - [ ] Daemon mode manageable via skill interface
       - [ ] Skills properly tagged with maturity requirements (AUTONOMOUS for daemon control)
       - [ ] Integration tested and documented

    2. Files Created:
       - backend/skills/atom-cli/ (6 SKILL.md files)
       - backend/tools/atom_cli_skill_wrapper.py
       - backend/tests/test_atom_cli_skills.py
       - docs/ATOM_CLI_SKILLS_GUIDE.md

    3. Test Results:
       - Parse tests: 6/6 skills parse successfully
       - Execution tests: subprocess wrapper works correctly
       - Governance tests: maturity gates enforced
       - Integration tests: full import->execute flow works

    4. Documentation:
       - ATOM_CLI_SKILLS_GUIDE.md comprehensive
       - COMMUNITY_SKILLS.md updated
       - CLAUDE.md updated with Phase 25
       - ROADMAP.md updated with Phase 25

    5. Success Criteria:
       - [ ] 6 SKILL.md files created, all parse successfully
       - [ ] Skills can be imported via /api/skills/import endpoint
       - [ ] AUTONOMOUS maturity gates on daemon/start/stop/execute skills
       - [ ] STUDENT maturity access on status/config skills
       - [ ] Each skill documents CLI usage, options, examples, output format
       - [ ] Test suite passes with 20+ tests
       - [ ] User documentation complete

    6. Deviations: (if any)

    7. Next Steps: (future work recommendations)
  </action>
  <verify>
    25-VERIFICATION.md created with all verification criteria
      - All 6 phase goals listed with checkboxes
      - Files created listed
      - Test results documented
      - Success criteria tracked
      - Deviations section (even if "None")
    All criteria from phase goal covered
  </verify>
  <done>
    Phase 25 verification summary created, all success criteria tracked
  </done>
</task>

</tasks>

<verification>
1. ATOM_CLI_SKILLS_GUIDE.md created with comprehensive documentation
2. COMMUNITY_SKILLS.md updated with CLI skills section
3. CLAUDE.md updated with Phase 25 content
4. ROADMAP.md updated with Phase 25 entry
5. 25-VERIFICATION.md created with all success criteria tracked
6. All documentation cross-references correctly
7. All phase goal verification criteria satisfied
</verification>

<success_criteria>
1. User guide (ATOM_CLI_SKILLS_GUIDE.md) complete with all sections
2. Community skills documentation updated
3. CLAUDE.md and ROADMAP.md reflect Phase 25
4. Verification summary created
5. All 6 phase goals verified as complete
6. Documentation accessible and discoverable
</success_criteria>

<output>
After completion, create `.planning/phases/25-atom-cli-openclaw-skill/25-atom-cli-openclaw-skill-04-SUMMARY.md` with:
- Documentation files created
- Phase verification results
- Success criteria status
- Recommendations for future work
- Phase 25 completion summary
</output>
