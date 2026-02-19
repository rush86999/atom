"""
Group Reflection Service — GEA Phase 2: Domain-Agnostic Reflection Module

Implements the Reflection Module from the Group-Evolving Agents (GEA) paper
(UC Santa Barbara, Feb 2026), refactored to be fully domain-agnostic.

Architecture:
  - DomainProfile: a lightweight config object that teaches the Reflection Module
    how to interpret and surface experience from a given agent category.
  - DomainProfileRegistry: maps AgentRegistry.category → DomainProfile at runtime.
    Ships with built-in profiles for every Atom SaaS domain; falls back to a
    universal generic profile if no match is found.
  - GroupReflectionService: orchestrates gathering, quality-gating, and LLM
    reflection. Calls DomainProfileRegistry.resolve() to get the right prompt
    template and log-excerpt strategy per domain.

Adding a new domain is a single-step operation:
    DOMAIN_PROFILES["my_new_category"] = DomainProfile(...)

Usage:
    from core.group_reflection_service import GroupReflectionService
    from core.database import SessionLocal

    with SessionLocal() as db:
        svc = GroupReflectionService(db)
        pool = svc.gather_group_experience_pool(parent_agent_ids)
        directives = await svc.reflect_and_generate_directives(
            pool, tenant_id="t-123", category="crm"
        )
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from core.models import AgentEvolutionTrace, AgentRegistry
from core.llm_service import LLMService

logger = logging.getLogger(__name__)

# Quality gate: traces below this benchmark score are excluded from pool sharing.
# GEA paper: "blindly sharing outputs may introduce noise" for less-deterministic domains.
MIN_QUALITY_SCORE: float = 0.3

# GEA Performance-Novelty weighting (α, β)
PERF_WEIGHT: float = 0.6
NOVELTY_WEIGHT: float = 0.4


# ─────────────────────────────────────────────────────────────────────────────
# Domain Profile System
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DomainProfile:
    """
    Teaches the Reflection Module how to interpret experience for a specific
    agent category (domain).

    Fields
    ------
    name : str
        Human-readable label used in prompts (e.g. "CRM & Sales Outreach").
    success_label : str
        What does "passing the benchmark" mean in plain language?
        e.g. "deal-to-close conversion" for CRM, "zero-conflict booking" for scheduling.
    failure_label : str
        Plain-language description of a failure signal.
        e.g. "email bounce or no-reply-rate", "double-booked slot".
    experience_fieldname : str
        Which field on AgentEvolutionTrace carries the domain's primary
        experience blob. Defaults to "task_log" but can be "tool_use_log",
        "model_patch", etc.
    extract_signal : Callable[[str], Optional[str]]
        Domain-specific function that extracts the most meaningful excerpt from
        the task_log. Defaults to a generic tail-of-log extractor.
    patch_label : str
        What a "patch" means in this domain (git diff for code, email template
        change for CRM, scheduling rule for calendar, etc.).
    prompt_preamble : str
        Domain-specific context injected at the top of the reflection prompt
        so the LLM understands what kind of agents it is advising.
    tool_vocab : List[str]
        Key tool names the LLM should be aware of in this domain (used to
        focus the tool-pattern summary).
    quality_weight : float
        Relative weight (0-1) applied to quality gate strictness for this domain.
        Subjective domains should use a HIGHER weight (stricter filtering) to
        reduce noise. Objective domains can be lower. Default 1.0 = standard gate.
    """
    name: str
    success_label: str
    failure_label: str
    patch_label: str
    prompt_preamble: str
    experience_fieldname: str = "task_log"
    extract_signal: Optional[Callable[[str], Optional[str]]] = None
    tool_vocab: List[str] = field(default_factory=list)
    quality_weight: float = 1.0  # 1.0 = standard threshold


# ─────────────────────────────────────────────────────────────────────────────
# Built-in Domain Profiles (covers every Atom SaaS agent category)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_error_lines(log: str, keyword: str = "error", max_chars: int = 600) -> Optional[str]:
    """Generic: find lines containing a keyword and return surrounding context."""
    lines = log.splitlines()
    for i, line in enumerate(lines):
        if keyword.lower() in line.lower():
            start = max(0, i - 1)
            end = min(len(lines), i + 5)
            return "\n".join(lines[start:end])[:max_chars]
    return log[-max_chars:].strip() if len(log) > 80 else None


def _extract_traceback(log: str, max_chars: int = 600) -> Optional[str]:
    """Code domain: extract Python/JS traceback."""
    idx = log.lower().find("traceback")
    if idx != -1:
        return log[idx: idx + max_chars].strip()
    return _extract_error_lines(log, "error", max_chars)


def _extract_email_signal(log: str, max_chars: int = 600) -> Optional[str]:
    """CRM domain: extract bounce/no-reply/conversion signal lines."""
    for keyword in ["bounce", "no reply", "unsubscribe", "converted", "opened", "clicked"]:
        result = _extract_error_lines(log, keyword, max_chars)
        if result:
            return result
    return log[-max_chars:].strip() if len(log) > 80 else None


def _extract_conflict_signal(log: str, max_chars: int = 600) -> Optional[str]:
    """Scheduling domain: extract double-booking / conflict warnings."""
    for keyword in ["conflict", "double", "overlap", "declined", "rejected"]:
        result = _extract_error_lines(log, keyword, max_chars)
        if result:
            return result
    return log[-max_chars:].strip() if len(log) > 80 else None


def _extract_financial_signal(log: str, max_chars: int = 600) -> Optional[str]:
    """Financial domain: extract reconciliation errors, rounding issues, mismatches."""
    for keyword in ["mismatch", "discrepancy", "rounding", "exception", "failed"]:
        result = _extract_error_lines(log, keyword, max_chars)
        if result:
            return result
    return log[-max_chars:].strip() if len(log) > 80 else None


def _extract_support_signal(log: str, max_chars: int = 600) -> Optional[str]:
    """Support domain: extract escalations, unresolved tags, CSAT signals."""
    for keyword in ["escalat", "unresolved", "csat", "reopen", "complaint"]:
        result = _extract_error_lines(log, keyword, max_chars)
        if result:
            return result
    return log[-max_chars:].strip() if len(log) > 80 else None


# The built-in domain profile registry.
# Keys are lowercase versions of AgentRegistry.category values.
DOMAIN_PROFILES: Dict[str, DomainProfile] = {

    # ── Coding / Software Engineering ────────────────────────────────────────
    "engineering": DomainProfile(
        name="Software Engineering",
        success_label="task compiled and unit tests passed",
        failure_label="compilation failure, test failure, or traceback",
        patch_label="code diff (git unified diff format)",
        prompt_preamble=(
            "These agents write and refactor code. Their experience logs contain "
            "Python/JS tracebacks, bash tool outputs, and git diffs. Focus directives "
            "on tool retry strategies, error handling patterns, and code structure improvements."
        ),
        extract_signal=_extract_traceback,
        tool_vocab=["bash", "search", "read_file", "write_code_file", "execute"],
        quality_weight=0.8,  # Coding is objective → slightly relaxed gate
    ),

    # ── CRM / Sales Outreach ──────────────────────────────────────────────────
    "crm": DomainProfile(
        name="CRM & Sales Outreach",
        success_label="email opened, reply received, or deal stage advanced",
        failure_label="email bounce, no-reply, or deal stalled",
        patch_label="email template or outreach sequence change",
        prompt_preamble=(
            "These agents manage sales pipelines and email outreach. Their experience logs "
            "contain email send/bounce/open stats and CRM field updates. Focus directives "
            "on subject-line quality, send timing, follow-up cadence, and CRM field accuracy."
        ),
        extract_signal=_extract_email_signal,
        tool_vocab=["hubspot", "send_email", "crm_update", "search_contacts"],
        quality_weight=1.2,  # CRM outcomes are noisy → stricter gate
    ),

    "sales": DomainProfile(
        name="Sales & Pipeline Management",
        success_label="deal closed or pipeline stage advanced",
        failure_label="deal lost or pipeline stalled",
        patch_label="outreach strategy or qualification script change",
        prompt_preamble=(
            "These agents assist with deal qualification, pipeline management, and forecasting. "
            "Focus directives on qualification accuracy, next-step recommendation quality, "
            "and handoff timing to human reps."
        ),
        extract_signal=_extract_email_signal,
        tool_vocab=["hubspot", "salesforce", "crm_update", "calendar"],
        quality_weight=1.2,
    ),

    # ── Scheduling / Calendar ─────────────────────────────────────────────────
    "scheduling": DomainProfile(
        name="Calendar & Scheduling",
        success_label="meeting booked with no conflicts, accepted by all attendees",
        failure_label="double-booking, declined invite, or scheduling conflict",
        patch_label="availability rule or invite-logic change",
        prompt_preamble=(
            "These agents manage calendars and schedule meetings. Their experience logs "
            "contain Calendar API responses, conflict flags, and attendee acceptance rates. "
            "Focus directives on conflict detection, timezone handling, buffer times, and "
            "optimal slot selection heuristics."
        ),
        extract_signal=_extract_conflict_signal,
        tool_vocab=["google_calendar", "outlook_calendar", "create_event", "check_availability"],
        quality_weight=0.9,  # Calendar outcomes are deterministic → slightly relaxed
    ),

    # ── Financial / Accounting / Reconciliation ───────────────────────────────
    "finance": DomainProfile(
        name="Financial Operations",
        success_label="transaction reconciled within tolerance, P&L accurate",
        failure_label="reconciliation mismatch, rounding error, or failed classification",
        patch_label="accounting rule or reconciliation logic change",
        prompt_preamble=(
            "These agents process financial transactions, reconcile ledgers, and manage "
            "AP/AR workflows. Their experience logs contain transaction amounts, balances, "
            "and reconciliation exception messages. Focus directives on classification accuracy, "
            "rounding tolerance handling, and exception escalation thresholds."
        ),
        extract_signal=_extract_financial_signal,
        tool_vocab=["quickbooks", "stripe", "classify_transaction", "reconcile", "post_journal"],
        quality_weight=0.8,  # Financial outcomes are highly objective
    ),

    "accounting": DomainProfile(
        name="AI Accounting",
        success_label="journal entry posted with correct account codes",
        failure_label="incorrect account code, duplicate entry, or unbalanced ledger",
        patch_label="chart-of-accounts mapping or posting rule change",
        prompt_preamble=(
            "These agents automate bookkeeping tasks. Focus directives on chart-of-accounts "
            "accuracy, duplicate detection, and GL posting validation."
        ),
        extract_signal=_extract_financial_signal,
        tool_vocab=["quickbooks", "post_journal", "classify_expense", "reconcile"],
        quality_weight=0.8,
    ),

    # ── Customer Support ─────────────────────────────────────────────────────
    "support": DomainProfile(
        name="Customer Support",
        success_label="ticket resolved, CSAT ≥ 4, no re-open within 48h",
        failure_label="escalation, CSAT ≤ 2, or ticket re-opened",
        patch_label="support playbook or response template change",
        prompt_preamble=(
            "These agents handle customer support tickets. Their experience logs contain "
            "ticket thread summaries, escalation flags, and CSAT scores. Focus directives "
            "on first-contact resolution, de-escalation phrasing, and knowledge-base routing accuracy."
        ),
        extract_signal=_extract_support_signal,
        tool_vocab=["zendesk", "intercom", "lookup_kb", "create_ticket", "escalate"],
        quality_weight=1.3,  # Support is partially subjective → stricter gate
    ),

    # ── Operations / Workflow ─────────────────────────────────────────────────
    "operations": DomainProfile(
        name="Business Operations",
        success_label="workflow completed end-to-end with no human intervention",
        failure_label="workflow blocked, step timed out, or required human override",
        patch_label="workflow step or trigger condition change",
        prompt_preamble=(
            "These agents automate operational workflows across departments. Focus directives "
            "on step dependency ordering, timeout handling, and retry configuration."
        ),
        extract_signal=lambda log: _extract_error_lines(log, "blocked", 500)
            or _extract_error_lines(log, "timeout", 500)
            or log[-400:].strip(),
        tool_vocab=["trigger_workflow", "send_notification", "schedule", "create_task"],
        quality_weight=1.0,
    ),

    # ── Data / Intelligence / Analytics ───────────────────────────────────────
    "analytics": DomainProfile(
        name="Data Analytics & Intelligence",
        success_label="query returned expected result set within SLA",
        failure_label="query error, timeout, or data quality flag",
        patch_label="query logic or aggregation rule change",
        prompt_preamble=(
            "These agents run data queries and produce business intelligence outputs. "
            "Focus directives on query accuracy, latency, and data-quality validation steps."
        ),
        extract_signal=lambda log: _extract_error_lines(log, "error", 500)
            or _extract_error_lines(log, "timeout", 500),
        tool_vocab=["sql_query", "bigquery", "aggregate", "visualize", "export_csv"],
        quality_weight=0.9,
    ),

    # ── Marketing ─────────────────────────────────────────────────────────────
    "marketing": DomainProfile(
        name="Marketing Intelligence",
        success_label="campaign click-through or conversion above baseline",
        failure_label="below-baseline CTR, high unsubscribe rate, or blocked send",
        patch_label="campaign copy or targeting rule change",
        prompt_preamble=(
            "These agents manage marketing campaigns and content strategy. Their experience "
            "contains campaign performance metrics (CTR, CVR, unsub rate). Focus directives "
            "on audience segmentation accuracy, copy quality signals, and send-time optimization."
        ),
        extract_signal=lambda log: _extract_error_lines(log, "unsubscribe", 500)
            or _extract_error_lines(log, "blocked", 500)
            or log[-400:].strip(),
        tool_vocab=["send_campaign", "segment_audience", "track_event", "ab_test"],
        quality_weight=1.3,  # Marketing outcomes are partially subjective
    ),
}

# Alias common variant spellings
DOMAIN_PROFILES["software"] = DOMAIN_PROFILES["engineering"]
DOMAIN_PROFILES["dev"] = DOMAIN_PROFILES["engineering"]
DOMAIN_PROFILES["coding"] = DOMAIN_PROFILES["engineering"]
DOMAIN_PROFILES["financial"] = DOMAIN_PROFILES["finance"]
DOMAIN_PROFILES["customer_support"] = DOMAIN_PROFILES["support"]
DOMAIN_PROFILES["calendar"] = DOMAIN_PROFILES["scheduling"]
DOMAIN_PROFILES["crm_sales"] = DOMAIN_PROFILES["crm"]

# Generic fallback — works for any unlisted domain
_GENERIC_PROFILE = DomainProfile(
    name="General Purpose",
    success_label="task completed successfully with the expected output",
    failure_label="task failed, produced incorrect output, or required human intervention",
    patch_label="agent configuration or behavior change",
    prompt_preamble=(
        "These are general-purpose AI agents. Focus directives on tool usage efficiency, "
        "error recovery, and output quality improvements based on the patterns shown below."
    ),
    extract_signal=lambda log: _extract_error_lines(log, "error", 500) or log[-400:].strip(),
    quality_weight=1.0,
)


class DomainProfileRegistry:
    """Resolves a DomainProfile for a given agent category string."""

    @staticmethod
    def resolve(category: Optional[str]) -> DomainProfile:
        """
        Look up the DomainProfile for the given agent category.
        Case-insensitive. Falls back to the generic profile if not found.
        """
        if not category:
            return _GENERIC_PROFILE
        key = category.lower().replace(" ", "_").replace("-", "_")
        return DOMAIN_PROFILES.get(key, _GENERIC_PROFILE)

    @staticmethod
    def list_domains() -> List[str]:
        """Return all registered domain keys."""
        return sorted(set(DOMAIN_PROFILES.keys()))


# ─────────────────────────────────────────────────────────────────────────────
# Reflection Service
# ─────────────────────────────────────────────────────────────────────────────

class GroupReflectionService:
    """
    GEA Reflection Module: synthesizes collective experience from a parent group
    into natural-language evolution directives.

    Domain-agnostic: the behavior adapts automatically based on the agent
    category via DomainProfileRegistry.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.llm = LLMService()

    # ─────────────────────────────────────────────────────────────────────────
    # Step 1: Gather the shared experience pool
    # ─────────────────────────────────────────────────────────────────────────

    def gather_group_experience_pool(
        self,
        parent_agent_ids: List[str],
        max_traces_per_agent: int = 5,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Build a shared experience pool from a list of parent agent IDs.

        Queries the most recent high-quality evolution traces for each parent,
        applies a domain-adjusted quality gate, and returns a structured pool dict.

        Args:
            parent_agent_ids: IDs of agents selected as the parent group
            max_traces_per_agent: Max traces to pull per agent (most recent first)
            category: Agent category string (e.g. "crm", "finance"). If None,
                      will be auto-detected from the first agent's AgentRegistry row.

        Returns:
            A pool dict including domain-specific experience signals plus
            standard GEA fields (tool patterns, patches, directives, etc.).
        """
        # Auto-detect category from DB if not provided
        resolved_category = category or self._detect_category(parent_agent_ids)
        profile = DomainProfileRegistry.resolve(resolved_category)

        # Effective quality threshold adjusted per domain
        effective_min_score = MIN_QUALITY_SCORE * profile.quality_weight

        pool: Dict[str, Any] = {
            "agent_count": len(parent_agent_ids),
            "trace_count": 0,
            "tool_patterns": [],
            "task_log_excerpts": [],        # Domain-extracted signal snippets
            "successful_patches": [],        # High-quality behavior changes
            "evolving_requirements": [],     # Prior directives from parent traces
            "filtered_count": 0,
            # Domain metadata — passed through to the prompt builder
            "_domain_profile": profile,
            "_category": resolved_category,
        }

        seen_patches: set = set()

        for agent_id in parent_agent_ids:
            traces = (
                self.db.query(AgentEvolutionTrace)
                .filter(AgentEvolutionTrace.agent_id == agent_id)
                .order_by(AgentEvolutionTrace.created_at.desc())
                .limit(max_traces_per_agent)
                .all()
            )

            for trace in traces:
                if not self._passes_quality_gate(trace, effective_min_score):
                    pool["filtered_count"] += 1
                    continue

                pool["trace_count"] += 1

                # Tool usage patterns
                if trace.tool_use_log:
                    for entry in trace.tool_use_log:
                        pool["tool_patterns"].append({
                            "tool_name": entry.get("tool_name"),
                            "success": entry.get("success", False),
                            "agent_id": agent_id,
                        })

                # Domain-adapted signal extraction from task log
                if trace.task_log:
                    extractor = profile.extract_signal or (lambda log: log[-400:].strip())
                    excerpt = extractor(trace.task_log)
                    if excerpt:
                        pool["task_log_excerpts"].append(excerpt)

                # Successful patches (deduped)
                if trace.benchmark_passed and trace.model_patch:
                    patch_hash = hash(trace.model_patch[:200])
                    if patch_hash not in seen_patches:
                        seen_patches.add(patch_hash)
                        pool["successful_patches"].append(trace.model_patch)

                # Prior directives
                if trace.evolving_requirements:
                    pool["evolving_requirements"].append(trace.evolving_requirements)

        logger.info(
            "GEA pool built [%s]: %d traces from %d agents (%d filtered, effective_min=%.2f)",
            profile.name,
            pool["trace_count"],
            pool["agent_count"],
            pool["filtered_count"],
            effective_min_score,
        )
        return pool

    # ─────────────────────────────────────────────────────────────────────────
    # Step 2: LLM Reflection → Evolution Directives
    # ─────────────────────────────────────────────────────────────────────────

    async def reflect_and_generate_directives(
        self,
        pool: Dict[str, Any],
        tenant_id: Optional[str] = None,
        max_directives: int = 5,
        category: Optional[str] = None,
    ) -> List[str]:
        """
        Analyze the collective experience pool using an LLM and generate
        domain-specific evolution directives for the next agent generation.

        Args:
            pool: Output from gather_group_experience_pool()
            tenant_id: For model routing via BYOK
            max_directives: How many directives to generate (default 5)
            category: Override the domain category (auto-resolved from pool if absent)

        Returns:
            List of natural-language evolution directives, e.g.:
            - CRM:    ["Increase email personalization tokens in subject line",
                       "Reduce follow-up cadence to 3 days for cold prospects"]
            - Finance: ["Raise reconciliation tolerance threshold to $0.02",
                        "Add duplicate-invoice guard on PO number match"]
            - Coding:  ["Add retry logic when bash returns non-zero exit code",
                        "Cache search results to avoid re-querying same file"]
        """
        if pool["trace_count"] == 0:
            profile = pool.get("_domain_profile") or DomainProfileRegistry.resolve(category)
            logger.warning("GEA reflection [%s]: empty pool — returning bootstrap directive", profile.name)
            return [f"Improve {profile.success_label} by refining tool selection and error handling."]

        profile: DomainProfile = pool.get("_domain_profile") or DomainProfileRegistry.resolve(
            category or pool.get("_category")
        )
        prompt = self._build_reflection_prompt(pool, profile, max_directives)

        system_prompt = (
            f"You are a GEA Reflection Module advising a group of {profile.name} AI agents. "
            f"A 'success' in this domain means: {profile.success_label}. "
            f"A 'failure' in this domain means: {profile.failure_label}. "
            f"Your job is to analyze the collective group experience and extract the most "
            f"important patterns. Output ONLY a numbered list of concrete, actionable evolution "
            f"directives. Each directive must be a single sentence describing a specific "
            f"configuration, strategy, or workflow change that would improve agent performance "
            f"in the {profile.name} domain."
        )

        try:
            response = await self.llm.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=600,
                temperature=0.3,
                tenant_id=tenant_id,
            )
            directives = self._parse_directives(response, max_directives)
            logger.info("GEA reflection [%s] produced %d directives", profile.name, len(directives))
            return directives
        except Exception as e:
            logger.error("GEA reflection [%s] LLM call failed: %s", profile.name, e)
            return [f"Maintain current behavior while investigating {profile.failure_label}."]

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _detect_category(self, agent_ids: List[str]) -> Optional[str]:
        """Auto-detect the agent category from the first agent's registry entry."""
        if not agent_ids:
            return None
        agent = self.db.query(AgentRegistry).filter(AgentRegistry.id == agent_ids[0]).first()
        return agent.category if agent else None

    def _passes_quality_gate(
        self,
        trace: AgentEvolutionTrace,
        effective_min_score: float = MIN_QUALITY_SCORE,
    ) -> bool:
        """
        Filter out low-quality traces before pool sharing.

        A trace is excluded if:
        - It was already flagged as low-quality
        - Its benchmark score is below the (domain-adjusted) effective_min_score
        """
        if not trace.is_high_quality:
            return False
        if (
            trace.benchmark_score is not None
            and trace.benchmark_score < effective_min_score
        ):
            return False
        return True

    def _build_reflection_prompt(
        self,
        pool: Dict[str, Any],
        profile: DomainProfile,
        max_directives: int,
    ) -> str:
        """Build the domain-specific reflection prompt from the experience pool."""
        tool_summary = self._summarize_tool_patterns(pool["tool_patterns"], profile)
        patches_section = "\n".join(
            f"{profile.patch_label.capitalize()} {i+1}:\n{p[:400]}"
            for i, p in enumerate(pool["successful_patches"][:3])
        ) or f"No successful {profile.patch_label}s yet."

        signals_section = "\n---\n".join(pool["task_log_excerpts"][:3]) or "No failure signals captured."
        prior_directives = "\n".join(
            f"- {r[:250]}" for r in pool["evolving_requirements"][-5:]
        ) or "None — this is the first generation."

        return f"""{profile.prompt_preamble}

You are analyzing the collective experience of {pool['agent_count']} {profile.name} agents
across {pool['trace_count']} evolution traces.

## Tool Usage Patterns
{tool_summary}

## What Worked — Successful {profile.patch_label.title()}s
{patches_section}

## What Failed — Failure Signals ({profile.failure_label})
{signals_section}

## Prior Evolution Directives (previous generation)
{prior_directives}

---
Based on the above, generate exactly {max_directives} concrete evolution directives
specific to {profile.name} agents. Each directive should describe a specific,
actionable improvement the next generation should implement.
Format: numbered list (1. ..., 2. ..., etc.)"""

    def _summarize_tool_patterns(
        self,
        tool_patterns: List[Dict],
        profile: DomainProfile,
    ) -> str:
        """Summarize tool usage patterns with domain-relevant vocabulary awareness."""
        if not tool_patterns:
            return "No tool usage data available."

        counts: Dict[str, Dict[str, int]] = {}
        for entry in tool_patterns:
            name = entry.get("tool_name") or "unknown"
            if name not in counts:
                counts[name] = {"total": 0, "success": 0}
            counts[name]["total"] += 1
            if entry.get("success"):
                counts[name]["success"] += 1

        # Highlight domain-relevant tools
        domain_tools = set(profile.tool_vocab)
        lines = []
        for tool, stats in sorted(counts.items(), key=lambda x: -x[1]["total"]):
            rate = stats["success"] / stats["total"] if stats["total"] else 0
            marker = " ★" if tool in domain_tools else ""
            lines.append(f"- {tool}{marker}: {stats['total']} calls, {rate:.0%} success rate")
        return "\n".join(lines)

    def _parse_directives(self, response: str, max_directives: int) -> List[str]:
        """Parse numbered list directives from LLM response."""
        lines = response.strip().split("\n")
        directives = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Strip leading "1. " or "1) " or "- "
            line = re.sub(r"^(\d+[.)]\s*|[-•]\s*)", "", line).strip()
            if line:
                directives.append(line)
            if len(directives) >= max_directives:
                break
        return directives

    # ─────────────────────────────────────────────────────────────────────────
    # Utility: public access to domain registry
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def list_supported_domains() -> List[str]:
        """Return all domain keys supported by the built-in profile registry."""
        return DomainProfileRegistry.list_domains()

    @staticmethod
    def register_domain(category: str, profile: DomainProfile) -> None:
        """
        Register a new domain profile at runtime.

        Use this in tenant-specific initialization if your deployment has custom
        agent categories not covered by the built-in profiles.

        Example:
            GroupReflectionService.register_domain("legal", DomainProfile(
                name="Legal Document Review",
                success_label="clause correctly extracted and flagged",
                failure_label="missed clause or false positive",
                patch_label="extraction rule change",
                prompt_preamble="These agents review legal contracts...",
                quality_weight=1.5,  # Very subjective — strict gate
            ))
        """
        DOMAIN_PROFILES[category.lower()] = profile
        logger.info("GEA: registered new domain profile '%s'", category)
