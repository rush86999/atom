"""Settings catalog — every tunable env var as UI-administrable metadata.

Declarative inventory of the environment variables documented in
CLAUDE.md / docs, grouped by subsystem. The catalog is *metadata only*:
it declares type/default/description/editability. Resolution lives in
``core/runtime_settings.py`` (env wins > DB row > default).

Security posture:

* ``secret=True`` entries (API keys, webhook shared secrets, credential
  files) are **visible** in the UI as "environment-managed" rows but are
  never serialized with a value and never writable through the API.
* Editing a non-secret setting writes a ``runtime_settings`` DB row;
  an explicit env var still overrides it (kill-switch semantics).

This module must stay leaf-safe: stdlib imports only, no side effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class SettingSpec:
    """One administrable setting (mirrors one env var)."""

    key: str
    type: str  # bool | int | float | str | json
    default: Any
    category: str
    description: str
    secret: bool = False  # never returned/writable via the API


def B(key: str, default: bool, category: str, description: str, secret: bool = False) -> SettingSpec:
    return SettingSpec(key, "bool", default, category, description, secret)


def I(key: str, default: int, category: str, description: str, secret: bool = False) -> SettingSpec:
    return SettingSpec(key, "int", default, category, description, secret)


def F(key: str, default: float, category: str, description: str, secret: bool = False) -> SettingSpec:
    return SettingSpec(key, "float", default, category, description, secret)


def S(key: str, default: str, category: str, description: str, secret: bool = False) -> SettingSpec:
    return SettingSpec(key, "str", default, category, description, secret)


def J(key: str, default: Any, category: str, description: str, secret: bool = False) -> SettingSpec:
    return SettingSpec(key, "json", default, category, description, secret)


# ============================================================================
# Category constants
# ============================================================================

C_DB = "Database & Personal Edition"
C_LLM = "LLM Providers & Keys"
C_GOV = "Governance"
C_MON = "Monitoring"
C_MEM = "Memory & Context"
C_HALL = "Hallucination Mitigation"
C_SANDBOX = "Execution Sandbox"
C_AGENT = "Agent Intelligence (W1–W5)"
C_STAGE = "Stage Router"
C_FLEET = "Fleet Router"
C_RADIO = "Agent Radio"
C_TRUST = "Trust Calibration"
C_ORG = "Org Politics"
C_GATEWAY = "LLM Gateway"
C_SEC = "Security & Webhooks"


SETTING_CATALOG: tuple[SettingSpec, ...] = (
    # ------------------------------------------------------------------
    # Database / Personal Edition
    # ------------------------------------------------------------------
    S("DATABASE_URL", "sqlite:///./atom_dev.db", C_DB, "Database connection string", secret=True),
    S("EMBEDDING_PROVIDER", "fastembed", C_DB, "Embedding backend"),
    S("FASTEMBED_MODEL", "BAAI/bge-small-en-v1.5", C_DB, "FastEmbed model id"),
    S("LANCEDB_PATH", "./data/lancedb", C_DB, "Embedded LanceDB path"),
    B("LANCEDB_CLOUD_ENABLED", False, C_DB, "SaaS remote LanceDB (S3/R2)"),
    B("ATOM_HOST_MOUNT_ENABLED", False, C_DB, "AUTONOMOUS host-mount gate"),
    I("PORT", 8000, C_DB, "API server port"),
    S("LOG_LEVEL", "INFO", C_MON, "Log verbosity"),
    B("BROWSER_HEADLESS", True, C_DB, "Run Playwright headless"),
    # ------------------------------------------------------------------
    # LLM provider keys — visible-but-locked in the UI
    # ------------------------------------------------------------------
    S("OPENAI_API_KEY", "", C_LLM, "OpenAI API key", secret=True),
    S("ANTHROPIC_API_KEY", "", C_LLM, "Anthropic API key", secret=True),
    S("MINIMAX_API_KEY", "", C_LLM, "MiniMax API key", secret=True),
    S("OPENCODE_API_KEY", "", C_LLM, "OpenCode Go gateway key (canonical env name)", secret=True),
    S("OPENCODE_BASE_URL", "https://opencode.ai/zen/v1", C_LLM, "OpenCode Go base URL"),
    I("OPENCODE_RPM", 60, C_LLM, "OpenCode requests/min ceiling (routing headroom)"),
    I("OPENCODE_TPM", 2000000, C_LLM, "OpenCode tokens/min ceiling"),
    I("OPENCODE_MAX_CONTEXT", 200000, C_LLM, "Gateway context cap (clamps candidates)"),
    J("OPENCODE_FREE_PAID_FALLBACK", {}, C_LLM, "Per-model free→paid fallback map"),
    S("XAI_API_KEY", "", C_LLM, "xAI API key", secret=True),
    S("CEREBRAS_API_KEY", "", C_LLM, "Cerebras API key", secret=True),
    S("FIREWORKS_API_KEY", "", C_LLM, "Fireworks API key", secret=True),
    S("HUGGINGFACE_API_KEY", "", C_LLM, "HuggingFace API key", secret=True),
    S("NVIDIA_NIM_API_KEY", "", C_LLM, "NVIDIA NIM API key", secret=True),
    S("ZAI_API_KEY", "", C_LLM, "Z.ai API key", secret=True),
    S("OLLAMA_BASE_URL", "", C_LLM, "Local Ollama endpoint (keyless)"),
    S("OLLAMA_MODEL", "llama3:8b", C_LLM, "Default local Ollama model"),
    S("E2B_API_KEY", "", C_LLM, "E2B sandbox key", secret=True),
    # ------------------------------------------------------------------
    # Governance
    # ------------------------------------------------------------------
    B("STREAMING_GOVERNANCE_ENABLED", True, C_GOV, "Govern streaming LLM calls"),
    B("CANVAS_GOVERNANCE_ENABLED", True, C_GOV, "Govern canvas operations"),
    B("FORM_GOVERNANCE_ENABLED", True, C_GOV, "Govern form actions"),
    B("BROWSER_GOVERNANCE_ENABLED", True, C_GOV, "Govern browser automation"),
    B("EMERGENCY_GOVERNANCE_BYPASS", False, C_GOV, "Emergency bypass (dangerous)"),
    # ------------------------------------------------------------------
    # Monitoring
    # ------------------------------------------------------------------
    B("PROMETHEUS_ENABLED", True, C_MON, "Expose Prometheus metrics"),
    S("STRUCTLOG_LEVEL", "INFO", C_MON, "Structlog level"),
    I("HEALTH_CHECK_DISK_THRESHOLD_GB", 1, C_MON, "Disk-free readiness floor (GB)"),
    # ------------------------------------------------------------------
    # Memory & context
    # ------------------------------------------------------------------
    B("ATOM_MEMORY_POISON_TRIPWIRE", True, C_MEM, "Quarantine memory-injection sources"),
    B("ATOM_TEMPORALITY_ENABLED", True, C_MEM, "Bi-temporal graph time travel"),
    B("TURN_FACT_EXTRACTION_ENABLED", True, C_MEM, "Per-turn durable-fact extraction"),
    B("TURN_FACT_PRE_COMPRESS_ENABLED", True, C_MEM, "Pre-truncation extraction queue"),
    B("TURN_FACT_VECTOR_RECALL_ENABLED", True, C_MEM, "LanceDB semantic fact recall"),
    I("TURN_FACT_MAX_PER_TURN", 5, C_MEM, "Max facts extracted per turn"),
    F("TURN_FACT_EXTRACTION_SAMPLE_RATE", 1.0, C_MEM, "Fraction of turns sampled"),
    I("TURN_FACT_QUEUE_MAXSIZE", 100, C_MEM, "Extraction queue depth"),
    # ------------------------------------------------------------------
    # Hallucination mitigation (Phase 2 + R72/R83)
    # ------------------------------------------------------------------
    B("ATOM_CASCADE_ROUTING", False, C_HALL, "Retry schema failures same-provider flagship"),
    B("ATOM_SELF_CONSISTENCY", False, C_HALL, "N-sample majority vote master switch"),
    I("ATOM_SELF_CONSISTENCY_SAMPLES", 3, C_HALL, "Samples drawn per vote"),
    B("ATOM_SELF_CONSISTENCY_FORCE_PROPOSAL", False, C_HALL, "Route partial/ambiguous votes to proposals"),
    F("ATOM_SELF_CONSISTENCY_HIGH_THRESHOLD", 0.85, C_HALL, "Agreement ≥ this is 'high'"),
    F("ATOM_SELF_CONSISTENCY_PARTIAL_THRESHOLD", 0.50, C_HALL, "Agreement ≥ this is 'partial'"),
    B("ATOM_MOA_ENABLED", True, C_HALL, "Mixture-of-Agents on hard structured tasks"),
    I("ATOM_MOA_SAMPLES", 3, C_HALL, "MoA samples (min 2)"),
    B("ATOM_MOA_DIVERSITY_ENABLED", False, C_HALL, "Per-sample perspective overlays"),
    B("ATOM_PARALLEL_TOOLS", True, C_HALL, "In-loop parallel tool execution"),
    I("ATOM_MAX_PARALLEL_TOOLS", 4, C_HALL, "Max tools per parallel batch"),
    B("ATOM_SKILL_INJECTION_ENABLED", True, C_HALL, "Prompt-time skill auto-injection"),
    B("ATOM_TOOL_CACHE_ENABLED", True, C_HALL, "Read-only tool-result memoization"),
    I("ATOM_TOOL_CACHE_TTL", 30, C_HALL, "Tool cache TTL seconds"),
    S("ATOM_SC_HASH_ALGO", "jcs-sha256", C_HALL, "Vote hash algorithm (jcs-sha256|sha256-sortkeys)"),
    B("ATOM_SC_USC_FALLBACK", True, C_HALL, "USC judge on all-distinct votes"),
    B("ATOM_SC_FANOUT", True, C_HALL, "Spread vote samples across providers"),
    B("ATOM_SC_SOFT", True, C_HALL, "Soft (logprob-weighted) SC shadow"),
    # Test/spec fixtures exercising every coercer (documented pattern).
    B("ATOM_SC_TEST_FLAG", False, C_HALL, "Resolver test fixture (bool)"),
    B("ATOM_SC_TEST_BOOL", False, C_HALL, "Resolver test fixture (bool)"),
    I("ATOM_SC_TEST_INT", 3, C_HALL, "Resolver test fixture (int)"),
    F("ATOM_SC_TEST_FLOAT", 0.5, C_HALL, "Resolver test fixture (float)"),
    S("ATOM_SC_TEST_STR", "", C_HALL, "Resolver test fixture (str)"),
    # ------------------------------------------------------------------
    # Execution sandbox
    # ------------------------------------------------------------------
    B("ATOM_SANDBOX_ENABLED", True, C_SANDBOX, "Sandbox layer master switch"),
    B("ATOM_SANDBOX_FORCE_ENFORCE", True, C_SANDBOX, "Enforce, not just audit"),
    B("ATOM_SANDBOX_POLICY_TENANT_OVERRIDE", False, C_SANDBOX, "Allow tenant policy overrides"),
    B("ATOM_SANDBOX_FS_ENABLED", True, C_SANDBOX, "Filesystem scope enforcement"),
    B("ATOM_SANDBOX_WHITELIST_ENABLED", True, C_SANDBOX, "Tool whitelist"),
    B("ATOM_SANDBOX_TRIPWIRES_ENABLED", True, C_SANDBOX, "Tripwire detection"),
    B("ATOM_SANDBOX_CAPS_ENABLED", True, C_SANDBOX, "Resource caps"),
    I("ATOM_SANDBOX_MAX_TOOL_CALLS", 200, C_SANDBOX, "Tool calls per run"),
    I("ATOM_SANDBOX_MAX_EXEC_SECONDS", 600, C_SANDBOX, "Wall-clock run cap"),
    I("ATOM_SANDBOX_MAX_BYTES_WRITTEN", 104857600, C_SANDBOX, "Bytes-written cap"),
    F("ATOM_SANDBOX_MAX_COST_USD", 5.0, C_SANDBOX, "Cost cap per run (USD)"),
    S("ATOM_SANDBOX_RUNTIME", "docker", C_SANDBOX, "docker|firecracker|e2b"),
    B("ATOM_SANDBOX_EGRESS_ENABLED", False, C_SANDBOX, "Network egress isolation"),
    I("ATOM_SANDBOX_VM_MEM_MB", 256, C_SANDBOX, "MicroVM memory (MB)"),
    I("ATOM_SANDBOX_VM_VCPUS", 1, C_SANDBOX, "MicroVM vCPUs"),
    I("ATOM_SANDBOX_VM_BOOT_TIMEOUT_SECONDS", 5, C_SANDBOX, "MicroVM boot timeout"),
    B("ATOM_SANDBOX_PROVENANCE_ENABLED", True, C_SANDBOX, "Provenance tagging"),
    B("ATOM_SANDBOX_JUDGE_ENABLED", False, C_SANDBOX, "LLM ActionJudge (opt-in)"),
    F("ATOM_SANDBOX_JUDGE_TIMEOUT_SECONDS", 2.0, C_SANDBOX, "Judge timeout"),
    I("ATOM_SANDBOX_JUDGE_CIRCUIT_THRESHOLD", 5, C_SANDBOX, "Judge circuit-break trips"),
    I("ATOM_SANDBOX_JUDGE_CIRCUIT_COOLDOWN_SECONDS", 120, C_SANDBOX, "Judge cooldown"),
    # ------------------------------------------------------------------
    # Agent intelligence W1–W5
    # ------------------------------------------------------------------
    B("ATOM_KNOWLEDGE_VFS_ENABLED", True, C_AGENT, "knowledge/ VFS surface"),
    B("ATOM_HYBRID_VECTOR_LEG_ENABLED", True, C_AGENT, "BM25+vector RRF fusion"),
    B("ATOM_ORACLE_VERIFIER_ENABLED", True, C_AGENT, "Postcondition oracle (shadow)"),
    B("ATOM_OBJECTIVE_LOOP_ENABLED", True, C_AGENT, "Goal-driven loop w/ DoD early exit"),
    B("ATOM_MINIAPP_DB_ENABLED", True, C_AGENT, "Mini-app record store"),
    B("ATOM_REVIEWER_LOOP_ENABLED", False, C_AGENT, "REVIEW strategy re-delegation"),
    S("LANCEDB_URI", "./data/atom_memory", C_DB, "Atom memory LanceDB URI"),
    S("LANCEDB_URI_BASE", "./data/atom_memory", C_DB, "Base URI for per-workspace stores"),
    S("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5", C_DB, "Embedding model id"),
    # Doc freshness / memory consolidation
    F("ATOM_DOC_FRESHNESS_TTL_HOURS", 24.0, C_MEM, "Freshness window before re-check"),
    B("ATOM_FRESHNESS_FILTER_ENABLED", True, C_MEM, "Filter stale docs at retrieval"),
    F("ATOM_SUPERSESSION_SIM_THRESHOLD", 0.86, C_MEM, "Supersession similarity floor"),
    F("ATOM_SUPERSESSION_ENTITY_OVERLAP", 0.5, C_MEM, "Supersession entity-overlap floor"),
    B("ATOM_MEMORY_CONSOLIDATION_LLM", False, C_MEM, "LLM-reviewed consolidation"),
    I("ATOM_MEMORY_CONSOLIDATION_LLM_MAX_SUBJECTS", 5, C_MEM, "Subjects per consolidation pass"),
    I("ATOM_MEMORY_CONSOLIDATION_LLM_FACTS_PER_SUBJECT", 6, C_MEM, "Facts reviewed per subject"),
    I("ATOM_MEMORY_CONSOLIDATION_LLM_MAX_OPS", 20, C_MEM, "Max ops per pass"),
    F("ATOM_MEMORY_CONSOLIDATION_LLM_TIMEOUT_S", 20.0, C_MEM, "Consolidation timeout seconds"),
    I("ATOM_MEMORY_CONSOLIDATION_LLM_LOOKBACK_DAYS", 7, C_MEM, "Consolidation lookback days"),
    I("TURN_FACT_RETENTION_DAYS", 0, C_MEM, "Turn-fact retention (0 = forever)"),
    I("TURN_FACT_CB_THRESHOLD", 5, C_MEM, "Turn-fact circuit-break trips"),
    F("TURN_FACT_CB_COOLDOWN_S", 120.0, C_MEM, "Turn-fact circuit cooldown"),
    # Fleet router
    B("ATOM_FLEET_ROUTING_ENABLED", True, C_FLEET, "Governed fleet dispatch (shadow)"),
    B("ATOM_FLEET_ROUTING_FORCE_ENFORCE", False, C_FLEET, "Return fleet results live"),
    S("ATOM_FLEET_ROUTER_AUTO_ENFORCE", "approve", C_FLEET, "off|notify|approve|auto"),
    I("ATOM_FLEET_ROUTER_AUTO_INTERVAL_MIN", 60, C_FLEET, "Certification cadence"),
    F("ATOM_FLEET_ROUTER_AUTO_SUCCESS_GAP", 0.70, C_FLEET, "Baseline success floor"),
    I("ATOM_FLEET_ROUTER_AUTO_MIN_ROWS", 30, C_FLEET, "Min outcome-joined rows"),
    I("ATOM_FLEET_ROUTER_AUTO_NOTIFY_COOLDOWN_HOURS", 24, C_FLEET, "Notify dedupe window"),
    # Agent radio
    B("ATOM_RADIO_ENABLED", True, C_RADIO, "Lateral peer messaging"),
    F("ATOM_RADIO_TEAM_BUDGET_USD", 0.20, C_RADIO, "Team budget cap (USD)"),
    I("ATOM_RADIO_INBOX_CAP", 10, C_RADIO, "Passive inbox cap"),
    I("ATOM_RADIO_BACKLOG_TTL_MIN", 30, C_RADIO, "Backlog TTL minutes"),
    I("ATOM_RADIO_WAIT_TIMEOUT_SECONDS", 30, C_RADIO, "wait_for_mention timeout"),
    B("ATOM_RADIO_BREAKPOINT_GATE", True, C_RADIO, "Breakpoint gating"),
    # ------------------------------------------------------------------
    # Stage router
    # ------------------------------------------------------------------
    B("ATOM_STAGE_ROUTING_ENABLED", True, C_STAGE, "Master switch (on alone = shadow)"),
    B("ATOM_STAGE_ROUTING_FORCE_ENFORCE", False, C_STAGE, "Live tier override"),
    S("ATOM_STAGE_ROUTING_PICKER", "efficient_first", C_STAGE, "efficient_first|capable_first"),
    F("ATOM_STAGE_ROUTING_CONFIDENCE_THRESHOLD", 0.5, C_STAGE, "Signal threshold"),
    I("ATOM_STAGE_ROUTING_WINDOW", 3, C_STAGE, "Recent turns scored"),
    B("ATOM_TRAFFIC_SPLIT", False, C_STAGE, "A/B harness master switch"),
    S("ATOM_STAGE_ROUTING_SPLIT", "", C_STAGE, "JSON split weights"),
    S("ATOM_STAGE_ROUTING_SPLIT_SEED", "", C_STAGE, "Reproducible split seed"),
    S("ATOM_STAGE_ROUTER_AUTO_ENFORCE", "approve", C_STAGE, "off|notify|approve|auto"),
    I("ATOM_STAGE_ROUTER_AUTO_INTERVAL_MIN", 60, C_STAGE, "Certification cadence"),
    F("ATOM_STAGE_ROUTER_AUTO_SUCCESS_GAP", 0.03, C_STAGE, "Capable-arm advantage to certify"),
    F("ATOM_STAGE_ROUTER_AUTO_MAX_COST_RATIO", 8.0, C_STAGE, "Max capable/efficient cost ratio"),
    F("ATOM_STAGE_ROUTER_AUTO_REVOKE_GAP", 0.02, C_STAGE, "Deficit that auto-revokes"),
    I("ATOM_STAGE_ROUTER_AUTO_NOTIFY_COOLDOWN_HOURS", 24, C_STAGE, "Notify dedupe window"),
    # ------------------------------------------------------------------
    # Trust calibration
    # ------------------------------------------------------------------
    B("ATOM_TRUST_CALIBRATION_ENABLED", False, C_TRUST, "GP trust gateway master switch"),
    S("ATOM_TRUST_CALIBRATION_AUTO_ENFORCE", "off", C_TRUST, "off|notify|approve|auto"),
    I("ATOM_TRUST_CALIBRATION_AUTO_INTERVAL_MIN", 60, C_TRUST, "Automation cadence"),
    B("ATOM_TRUST_CALIBRATION_FORCE_ENFORCE", False, C_TRUST, "Env hard-switch override"),
    I("ATOM_TRUST_CALIBRATION_HALF_LIFE_DAYS", 30, C_TRUST, "k_time decay half-life"),
    I("ATOM_TRUST_CALIBRATION_MAX_OBS", 400, C_TRUST, "Observations per refit"),
    I("ATOM_TRUST_CALIBRATION_REFIT_TTL", 300, C_TRUST, "Posterior cache seconds"),
    F("ATOM_TRUST_CALIBRATION_TAU_LOW", 0.35, C_TRUST, "p below → block"),
    F("ATOM_TRUST_CALIBRATION_TAU_UNCERTAIN", 0.15, C_TRUST, "Variance above → ask"),
    # ------------------------------------------------------------------
    # Org politics
    # ------------------------------------------------------------------
    B("ATOM_ORG_TELEMETRY_ENABLED", True, C_ORG, "P0 org-dynamics events"),
    B("ATOM_DELEGATION_CONTRACTS_ENABLED", True, C_ORG, "P1 typed delegation handoffs"),
    S("ATOM_ORG_PRIVILEGES_ENABLED", "", C_ORG, "P2 gates (unset=automation)"),
    S("ATOM_SKILL_SCOPED_TRUST_ENABLED", "", C_ORG, "P3 matcher trust term"),
    B("ATOM_CONTRIBUTION_CREDIT_ENABLED", False, C_ORG, "P4 bucket-brigade credit"),
    S("ATOM_ALLOCATOR_INTEGRITY_ENABLED", "", C_ORG, "P5 integrity gates"),
    B("ATOM_ALIGNMENT_SWEEP_ENABLED", False, C_ORG, "P6 nightly alignment sweep"),
    S("ATOM_ORG_AUTO_ENFORCE", "auto", C_ORG, "off|notify|approve|auto"),
    I("ATOM_ORG_AUTO_INTERVAL_MIN", 1440, C_ORG, "Certification cadence"),
    I("ATOM_ORG_AUTO_NOTIFY_COOLDOWN_HOURS", 24, C_ORG, "Notify dedupe window"),
    # ------------------------------------------------------------------
    # LLM gateway
    # ------------------------------------------------------------------
    B("ATOM_GATEWAY_ENABLED", True, C_GATEWAY, "/v1/* inbound surface master switch"),
    B("ATOM_GATEWAY_PREFER_COST", True, C_GATEWAY, "Cost-aware routing default"),
    B("ATOM_GATEWAY_LOG_BODIES", False, C_GATEWAY, "Persist full (redacted) bodies"),
    I("ATOM_GATEWAY_DEFAULT_MAX_TOKENS", 1000, C_GATEWAY, "Default completion cap"),
    B("ATOM_GATEWAY_BUDGET_ALERTS", False, C_GATEWAY, "Threshold spend alerts"),
    I("ATOM_GATEWAY_LOG_RETENTION_DAYS", 30, C_GATEWAY, "Log sweep retention"),
    # ------------------------------------------------------------------
    # Security & webhooks
    # ------------------------------------------------------------------
    I("MAX_UPLOAD_BYTES", 52428800, C_SEC, "Upload size cap (bytes)"),
    I("MAX_BODY_BYTES", 67108864, C_SEC, "Request body cap (bytes)"),
    S("ATOM_BOOTSTRAP_PASSWORD_FILE", "", C_SEC, "Admin password file path", secret=True),
    S("SHOPIFY_WEBHOOK_SECRET", "", C_SEC, "Shopify HMAC secret", secret=True),
    S("ATOM_WHATSAPP_WEBHOOK_SECRET", "", C_SEC, "WhatsApp webhook secret", secret=True),
    S("ATOM_SLACK_WEBHOOK_SECRET", "", C_SEC, "Slack webhook secret", secret=True),
    S("ATOM_DISCORD_WEBHOOK_SECRET", "", C_SEC, "Discord webhook secret", secret=True),
    S("ATOM_TELEGRAM_WEBHOOK_SECRET", "", C_SEC, "Telegram webhook secret", secret=True),
    S("ATOM_TEAMS_WEBHOOK_SECRET", "", C_SEC, "Teams webhook secret", secret=True),
    S("ATOM_GMAIL_WEBHOOK_SECRET", "", C_SEC, "Gmail webhook secret", secret=True),
    S("ATOM_SCHEDULER_SECRET", "", C_SEC, "Scheduler shared secret", secret=True),
    S("ZENDESK_WEBHOOK_SECRET", "", C_SEC, "Zendesk webhook secret", secret=True),
    B("TRUST_X_FORWARDED_FOR", False, C_SEC, "Honor XFF header (proxy only)"),
    # ------------------------------------------------------------------
    # Internal knobs for this layer itself
    # ------------------------------------------------------------------
    F("ATOM_SETTINGS_CACHE_TTL", 60.0, C_MON, "Runtime-settings cache TTL seconds"),
)

_SPEC_INDEX: dict[str, SettingSpec] = {s.key: s for s in SETTING_CATALOG}


def find_spec(key: str) -> Optional[SettingSpec]:
    """Return the spec for ``key`` or None."""
    return _SPEC_INDEX.get(key)


def serialize_catalog(specs: tuple[SettingSpec, ...], resolved: dict[str, Any]) -> list[dict]:
    """Serialize specs + current values. Secrets never carry a value.

    ``resolved`` maps key → object with ``.value`` / ``.source``
    (i.e. ``runtime_settings.ResolvedSetting``); passed duck-typed to
    keep this module leaf-safe.
    """
    out: list[dict] = []
    for s in specs:
        entry: dict[str, Any] = {
            "key": s.key,
            "type": s.type,
            "default": None if s.secret else s.default,
            "category": s.category,
            "description": s.description,
            "secret": s.secret,
            "editable": not s.secret,
        }
        if not s.secret:
            r = resolved.get(s.key)
            if r is not None:
                entry["value"] = r.value
                entry["source"] = r.source
        out.append(entry)
    return out
