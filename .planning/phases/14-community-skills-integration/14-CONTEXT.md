# Phase 14: Community Skills Integration - Context

**Gathered:** 2026-02-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Enable Atom agents to use 5,000+ OpenClaw/ClawHub community skills by parsing SKILL.md files (Markdown + YAML), executing them in isolated Docker sandbox, and managing them through a governed registry—while maintaining Atom's enterprise security model.

**Three major components:**
1. **Skill Adapter** - Parse OpenClaw skills and wrap them as Atom BaseTools
2. **Hazard Sandbox** - Isolated Docker container for safe skill execution
3. **Skills Registry** - Import UI, LLM security scanning, and governance

**Out of scope:** Creating new skills (that's OpenClaw's job), modifying ClawHub skills, enterprise-only features (multi-user, SSO).

</domain>

<decisions>
## Implementation Decisions

### Skill Parsing & Adapter
- **Lenient parsing** - Best effort to extract skill data even from malformed SKILL.md files
- **Auto-detect skill type** - Support both prompt-only skills (natural language) and Python code skills (```python blocks), detect automatically
- **Auto-fix when possible** - Try common fixes for missing required fields:
  - Missing `name:` → Use "Unnamed Skill"
  - Missing `description:` → Auto-generate from first line of instructions
  - Invalid YAML → Log specific error, skip file with clear message
- **Version-agnostic parsing** - Don't validate `openclaw_version` field, try to parse any skill regardless of version
- **Error handling** - Log warnings with file paths, skip unparseable skills, show summary of successes/failures at import end
- **YAML frontmatter required** - Must have `---` delimiters, but be flexible about field presence

### Claude's Discretion
- Exact Pydantic schema design for skill inputs (match OpenClaw structure vs. adapt to Atom patterns)
- Prompt template format for prompt-only skills (string interpolation vs. structured templates)
- How to handle Python skills with no clear function entry point (look for `def execute()`? `def run()`? main block?)
- Granularity of parsing error messages (technical YAML errors vs. user-friendly summaries)
- Metadata extraction strategy (what to preserve vs. what to transform)

</decisions>

<specifics>
## Specific Ideas

From your architectural blueprint:
- "Parse SKILL.md files: Split YAML frontmatter from body, extract metadata (name, description, input_schema)"
- "If skill contains ```python block, extract code and create sandboxed tool; otherwise map to PromptTemplate"
- "Wrap in BaseTool with Pydantic validation for inputs"
- OpenClaw skills use `@tool` decorator pattern - need to extract function signature from Python code

</specifics>

<deferred>
## Deferred Ideas

- Skill marketplace/voting/ratings - belongs in future phase (registry evolution)
- Skill versioning and updates - out of scope for initial implementation
- Skill dependencies (one skill importing another) - deferred to later phase
- Custom skill editor/creator UI - that's OpenClaw's domain, not Atom's

</deferred>

---

*Phase: 14-community-skills-integration*
*Context gathered: 2026-02-16*
