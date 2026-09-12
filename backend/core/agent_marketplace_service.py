"""
Agent Marketplace Service (Upstream Client)

Handles discovery and installation of agents from the Atom Agent OS Marketplace.
Syncs with the SaaS backend and records local installation metadata.

MANAGED-AGENT MODEL (IP protection): installed agents store a *reference*
configuration (template_id/version/tunables) — never the publisher's prompts
or experience memory. Those live in the AgentTemplate manifest (local row for
local publishes; server-side on the SaaS for marketplace installs) and are
resolved at execution time by ``core.marketplace_runtime``.
"""

import hashlib
import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_

from core.atom_saas_client import AtomAgentOSMarketplaceClient
from core.models import (
    AgentRegistry,
    AgentTemplate,
    AgentInstallation,
    GoalRun,
    OperationErrorResolution,
    Playbook,
    AgentSkill,
    Skill,
    Tenant
)
from core.marketplace_usage_tracker import MarketplaceUsageTracker

logger = logging.getLogger(__name__)

# Packaging caps — the runtime guidance injector reads at most 10
# heuristics / 3 golden paths (core.marketplace_runtime); pack a small
# surplus so a buyer-side re-publish keeps choice.
_MAX_PACKAGED_HEURISTICS = 10
_MAX_PACKAGED_GOLDEN_PATHS = 5
_MAX_PATH_STEPS = 20
_MAX_PACKAGED_PLAYBOOKS = 20
_MAX_REGISTERED_ENTITY_NAMES = 500
# A PAID listing must rest on at least one verified achieved goal run —
# "verified credibility, not marketing claims" (EXPERIENCE_MARKETPLACE.md).
_PAID_MIN_ACHIEVED_RUNS = 1


class AgentMarketplaceService:
    """
    Client-side service for managing marketplace agents in a self-hosted instance.
    Communicates with Atom SaaS to fetch templates and report installations.
    """

    def __init__(self, db: Session, saas_client: Optional[AtomAgentOSMarketplaceClient] = None):
        self.db = db
        self.saas_client = saas_client or AtomAgentOSMarketplaceClient()

    def publish_agent(self, template_data: Dict[str, Any]) -> Dict[str, Any]:
        """Publish an agent to the marketplace, stripping credentials.

        P5 Blueprint Security: sharing never leaks credentials. The published
        payload is run through ``strip_credentials`` so any nested secret keys
        (api_key / access_token / refresh_token / secret / password) are
        removed before the agent is shared with other tenants.

        Args:
            template_data: The agent payload to publish (configuration,
                capabilities, canvas UI schemas, etc.).

        Returns:
            A deep copy of ``template_data`` with credential keys removed —
            suitable for publishing to the marketplace.
        """
        from core.blueprint_sanitizer import strip_credentials
        return strip_credentials(template_data)

    # ------------------------------------------------- goal-run evidence
    #
    # Selling an agent sells its TRACK RECORD: the goal runs it worked are
    # platform-verified outcome data (docs/architecture/
    # AGENT_MARKETPLACE_GOAL_RUNS.md). Everything below is COMPUTED from
    # GoalRun/Playbook rows by the packaging service — the publisher cannot
    # author any of it.

    def _sanitizer(self, workspace_id: Optional[str]):
        """Entity-token + PII sanitizer over the publisher's workspace.

        Reuses the Experience Marketplace sanitizer: GraphNode entity names
        are pre-registered as role tokens so customer/company names in step
        titles and lessons export as ``person_012``-style tokens, never as
        identities. Fault-isolated — on any failure packaging still runs
        with plain PII redaction.
        """
        try:
            from core.experience_marketplace.sanitizer import (
                RoleRegistry, sanitize_text,
            )
            from core.models import GraphNode

            registry = RoleRegistry(self.db, workspace_id or "default")
            names = [
                row.name for row in self.db.query(GraphNode).filter(
                    GraphNode.workspace_id == (workspace_id or "default"),
                ).limit(_MAX_REGISTERED_ENTITY_NAMES).all()
                if (row.name or "").strip()
            ]
            for name in names:
                registry.token_for(name)
            return lambda text: sanitize_text(text or "", registry)
        except Exception as exc:
            logger.warning(f"entity-token sanitization unavailable: {exc}")
            from core.experience_marketplace.sanitizer import redact_pii
            return lambda text: redact_pii(str(text or ""))

    def _goal_run_evidence(self, agent: AgentRegistry) -> Dict[str, Any]:
        """The agent's verified track record + transferable guidance.

        Returns {record, golden_paths, heuristics}: ``record`` is the
        platform-computed counts for the listing's verified_record; the
        golden paths (plan sequences of ACHIEVED runs) and heuristics
        (supervisor corrections from decision logs) feed the runtime
        guidance injector buyers already get.
        """
        sanitize = self._sanitizer(getattr(agent, "workspace_id", None))

        runs = self.db.query(GoalRun).filter(
            GoalRun.agent_id == agent.id).all()
        counts = {"achieved": 0, "failed": 0, "cancelled": 0, "active": 0}
        steps_executed = human_interventions = decisions = 0
        modes: set = set()
        roles: set = set()
        golden_paths: List[Dict[str, Any]] = []
        heuristics: List[Dict[str, Any]] = []

        for run in runs:
            status = run.status if run.status in counts else "active"
            counts[status] += 1
            steps_executed += int(run.steps_executed or 0)
            human_interventions += int(run.human_interventions or 0)
            log = run.decision_log or []
            decisions += sum(1 for d in log if (d or {}).get("kind") == "decision")
            if run.supervision_mode:
                modes.add(run.supervision_mode)
            if run.role:
                roles.add(run.role)

            if (status == "achieved" and len(golden_paths) < _MAX_PACKAGED_GOLDEN_PATHS):
                titles = [
                    str((s or {}).get("title") or "").strip()
                    for s in (run.plan or [])[:_MAX_PATH_STEPS]
                ]
                titles = [sanitize(t)[:160] for t in titles if t]
                if titles:
                    golden_paths.append({"sequence": titles})

            for entry in log:
                if len(heuristics) >= _MAX_PACKAGED_HEURISTICS:
                    break
                if (entry or {}).get("kind") != "override":
                    continue  # human corrections are the transferable lesson
                resolution = sanitize(entry.get("rationale") or "")[:500]
                if len(resolution) >= 12:
                    heuristics.append({
                        "error_type": "goal-run correction",
                        "error_code": "",
                        "resolution": resolution,
                    })

        judged = counts["achieved"] + counts["failed"]
        record = {
            "maturity_at_publish": getattr(agent, "status", None) or "unknown",
            "runs": {**counts, "total": len(runs)},
            "achieved_rate": (
                round(counts["achieved"] / judged, 3) if judged else None),
            "steps_executed": steps_executed,
            "human_interventions": human_interventions,
            "decisions": decisions,
            "supervision_modes": sorted(modes),
            "roles": sorted(roles),
        }
        return {"record": record, "golden_paths": golden_paths,
                "heuristics": heuristics}

    def _package_playbooks(self, agent: AgentRegistry,
                           sanitize) -> List[Dict[str, Any]]:
        """The agent's APPROVED playbooks — the process a buyer's
        goal_runs.start will seed plans from (seed_plan_for_run matches
        them by keywords). Drafts never ship."""
        query = self.db.query(Playbook).filter(
            Playbook.approval_state == "approved")
        if agent.tenant_id:
            query = query.filter(Playbook.tenant_id == agent.tenant_id)
        rows = query.limit(_MAX_PACKAGED_PLAYBOOKS).all()
        return [
            {
                "name": sanitize(p.name or "")[:255],
                "description": sanitize(p.description or "")[:1000],
                "trigger_canvas_type": p.trigger_canvas_type,
                "trigger_keywords": [sanitize(k)[:80]
                                     for k in (p.trigger_keywords or [])[:20]],
                "steps": [sanitize(s)[:300] for s in (p.steps or [])[:30]],
                "template_questions": [sanitize(q)[:300]
                                       for q in (p.template_questions or [])[:15]],
            }
            for p in rows
        ]

    def sale_readiness(self, agent_id: str) -> Dict[str, Any]:
        """Advisory pre-publish view: the evidence a listing would carry and
        what (if anything) blocks a paid listing."""
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id).first()
        if not agent:
            return {"success": False, "error": "agent not found"}
        evidence = self._goal_run_evidence(agent)
        record = evidence["record"]
        blockers: List[str] = []
        if record["runs"]["achieved"] < _PAID_MIN_ACHIEVED_RUNS:
            blockers.append(
                f"no achieved goal run yet — a PAID listing needs at least "
                f"{_PAID_MIN_ACHIEVED_RUNS} verified achieved run (free "
                f"listings are fine)")
        if (agent.configuration or {}).get("marketplace_managed"):
            blockers.append(
                "this agent is itself a marketplace install — re-publishing "
                "someone else's listing is not allowed")
        return {
            "success": True,
            "agent_id": agent_id,
            "evidence": record,
            "guidance": {
                "golden_paths": len(evidence["golden_paths"]),
                "heuristics": len(evidence["heuristics"]),
                "playbooks": len(self._package_playbooks(
                    agent, self._sanitizer(
                        getattr(agent, "workspace_id", None)))),
            },
            "paid_listing_blockers": blockers,
        }

    def package_agent_for_sale(
        self,
        agent_id: str,
        price: float = 0.0,
        description: Optional[str] = None,
        author_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Package a TRAINED agent into a sellable AgentTemplate.

        The listing carries the agent's manifest (persona, role), its
        approved playbooks, runtime guidance (golden paths from achieved
        runs, correction heuristics) and the platform-computed
        verified_record — the goal-run track record buyers judge it by.
        Credentials are stripped and entity identities tokenized.
        """
        from core.blueprint_sanitizer import strip_credentials

        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id).first()
        if not agent:
            return {"success": False, "error": "agent not found"}
        if (agent.configuration or {}).get("marketplace_managed"):
            return {"success": False,
                    "error": "marketplace-managed agents cannot be "
                             "re-published"}

        sanitize = self._sanitizer(getattr(agent, "workspace_id", None))
        evidence = self._goal_run_evidence(agent)
        record = evidence["record"]

        if float(price or 0) > 0 and record["runs"]["achieved"] < _PAID_MIN_ACHIEVED_RUNS:
            return {"success": False,
                    "error": f"a paid listing requires at least "
                             f"{_PAID_MIN_ACHIEVED_RUNS} verified achieved "
                             f"goal run — this agent has "
                             f"{record['runs']['achieved']} (free listings "
                             f"are always allowed)"}

        role = ((getattr(agent, "specialty", None)
                 or getattr(agent, "category", None) or "")).strip()
        system_prompt = (agent.configuration or {}).get("system_prompt") or (
            f"You are {agent.name}, a {role or 'specialist'} agent.")
        playbooks = self._package_playbooks(agent, sanitize)

        manifest = strip_credentials({
            "system_prompt": sanitize(str(system_prompt))[:4000],
            "role": role or None,
            "tools": "*",
            "playbooks": playbooks,
        })
        memory_bundle = strip_credentials({
            "heuristics": evidence["heuristics"],
            "golden_paths": evidence["golden_paths"],
        })

        template = AgentTemplate(
            tenant_id=agent.tenant_id,
            author_id=author_id or getattr(agent, "user_id", None),
            name=str(agent.name)[:100],
            description=str(description or agent.description or "")[:500],
            category=agent.category or role or "General",
            version="1.0.0",
            price=float(price or 0.0),
            configuration=manifest,
            capabilities=[],
            canvas_ui_schemas=[],
            anonymized_memory_bundle=memory_bundle,
            tunable_keys=[],
            permission_profile={},
            # Local listing: live immediately on this instance; the SaaS
            # approval queue applies when marketplace_sync_worker pushes it.
            is_public=True,
            is_approved=True,
            is_active=True,
            verified_record=record,
        )
        self.db.add(template)
        try:
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            logger.error(f"packaging agent {agent_id} for sale failed: {exc}")
            return {"success": False, "error": str(exc)}
        self.db.refresh(template)
        logger.info(f"packaged agent {agent_id} as template {template.id} "
                    f"(achieved={record['runs']['achieved']}, "
                    f"steps={record['steps_executed']})")
        return {"success": True, "template_id": template.id,
                "verified_record": record}

    def browse_agents(
        self,
        query: str = "",
        category: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Browse public agents available in the Atom SaaS Marketplace.
        """
        try:
            logger.info(f"Browsing marketplace agents: query={query}, category={category}")
            result = self.saas_client.fetch_agents_sync(
                query=query,
                category=category,
                page=page,
                page_size=page_size
            )
            return result
        except Exception as e:
            logger.error(f"Failed to fetch agents from Atom SaaS: {e}")
            return {
                "agents": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
                "source": "error",
                "error": str(e)
            }

    def get_template_details(self, template_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch full details for an agent template from the SaaS marketplace.
        The SaaS serves the LISTING only — configuration and memory stay
        server-side under the managed-agent model.
        """
        try:
            return self.saas_client.get_agent_template_sync(template_id)
        except Exception as e:
            logger.error(f"Failed to fetch template details for {template_id}: {e}")
            return None

    def install_agent(self, template_id: str, tenant_id: str, user_id: str) -> Dict[str, Any]:
        """
        Install an agent from the marketplace as a MANAGED agent.

        1. Fetches listing data from SaaS.
        2. If the payload carries manifest data (local publish / legacy
           backend), upserts a local AgentTemplate manifest row.
        3. Creates a local AgentRegistry record whose configuration is a
           reference — prompts/memory are resolved at execution time.
        4. Connects skills that exist locally (never dangling links).
        5. Records installation locally and with SaaS.
        """
        # 1. Fetch listing from SaaS — or serve a LOCAL listing (a
        #    self-hosted sale packaged by package_agent_for_sale).
        template_data = self.get_template_details(template_id)
        if not template_data:
            local_listing = self.db.query(AgentTemplate).filter(
                AgentTemplate.id == template_id).first()
            if not local_listing or not getattr(local_listing, "is_active", True):
                return {"success": False, "error": "Agent template not found in marketplace"}
            template_data = {
                "name": local_listing.name,
                "description": local_listing.description,
                "category": local_listing.category,
                "version": local_listing.version,
                "price": local_listing.price,
                "configuration": local_listing.configuration or {},
                "capabilities": [],
                "canvas_ui_schemas": [],
                "anonymized_memory_bundle": local_listing.anonymized_memory_bundle or {},
                "tunable_keys": getattr(local_listing, "tunable_keys", None) or [],
                "permission_profile": local_listing.permission_profile or {},
                "verified_record": getattr(local_listing, "verified_record", None) or {},
            }

        try:
            # 2. Local manifest (only when the payload actually carries one)
            payload_config = template_data.get("configuration") or {}
            memory_bundle = template_data.get("anonymized_memory_bundle") or {}
            if payload_config or memory_bundle:
                local_template = (
                    self.db.query(AgentTemplate)
                    .filter(AgentTemplate.id == template_id)
                    .first()
                )
                if local_template:
                    if payload_config:
                        local_template.configuration = payload_config
                    if memory_bundle:
                        local_template.anonymized_memory_bundle = memory_bundle
                    local_template.is_active = True
                else:
                    local_template = AgentTemplate(
                        id=template_id,
                        tenant_id=None,
                        author_id=None,
                        name=str(template_data.get("name", ""))[:100],
                        description=str(template_data.get("description", ""))[:500],
                        category=template_data.get("category", "General"),
                        version=template_data.get("version", "1.0.0"),
                        price=template_data.get("price", 0.0),
                        configuration=payload_config,
                        capabilities=template_data.get("capabilities", []),
                        canvas_ui_schemas=template_data.get("canvas_ui_schemas", []),
                        anonymized_memory_bundle=memory_bundle,
                        tunable_keys=template_data.get("tunable_keys", []),
                        permission_profile=template_data.get("permission_profile", {}),
                        is_public=True,
                        is_approved=True,
                        is_active=True,
                    )
                    self.db.add(local_template)

            # 3. Instantiate local MANAGED agent — configuration is a
            # reference, not a copy of the manifest.
            # #10 fix: validate/truncate remote data before writing to
            # fixed-width VARCHAR columns (name=String(100), description=String(500)).
            _name = str(template_data.get("name", ""))[:100]
            _desc = str(template_data.get("description", ""))[:500]
            _display = f"{_name} (Marketplace)"[:100]
            _version = template_data.get("version", "1.0.0")
            # Evidence-honest seeding: the tier stays INTERN (marketplace
            # convention — trust is re-earned from LOCAL outcomes), but the
            # starting confidence inside the intern band scales with the
            # publisher's verified goal-run record instead of a flat 0.55.
            _record = template_data.get("verified_record") or {}
            _achieved = int(((_record.get("runs") or {}).get("achieved")) or 0)
            _vsteps = int(_record.get("steps_executed") or 0)
            _confidence = 0.55
            if _record:
                _confidence = min(0.69, 0.55
                                   + _achieved * 0.03 + _vsteps * 0.001)
            new_agent = AgentRegistry(
                name=_name,
                display_name=_display,
                description=_desc,
                category=template_data.get("category", "General"),
                role="agent",
                type="marketplace",
                # module_path/class_name are NOT NULL columns — omitting them
                # made every install fail with IntegrityError on a real DB
                # (mock-session tests masked it). Marketplace agents run the
                # generic agent, mirroring atom_meta_agent's convention.
                module_path="core.generic_agent",
                class_name="GenericAgent",
                user_id=user_id,
                tenant_id=tenant_id,
                status="intern",  # Marketplace agents start as internship level
                # Status/quota consistency: tier is recomputed from
                # confidence on every update — a declared intern needs a
                # score inside the INTERN band (>= 0.5), or the first
                # outcome drip would demote the install to student.
                confidence_score=_confidence,
                configuration={
                    "marketplace_managed": True,
                    "template_id": str(template_id),
                    "managed_version": _version,
                    "capabilities": [],
                    "tunables": {},
                },
            )
            self.db.add(new_agent)
            self.db.flush()

            # 4. Connect skills that exist locally — dangling AgentSkill
            # links 500 the skills API, so missing ones are skipped.
            warnings: List[str] = []
            linked_names: List[str] = []
            for skill_id in template_data.get("capabilities", []):
                skill = self.db.query(Skill).filter(Skill.id == skill_id).first()
                if not skill:
                    warnings.append(f"Skill {skill_id} not available locally; skipped")
                    continue
                agent_skill = AgentSkill(
                    agent_id=new_agent.id,
                    skill_id=skill_id,
                    enabled=True
                )
                self.db.add(agent_skill)
                linked_names.append(getattr(skill, "name", None) or str(skill_id))

            # Rebuild the config as a NEW dict: mutating the existing JSON
            # object in place and reassigning it is invisible to SQLAlchemy
            # (same-identity assignment records no change), so neither the
            # capabilities link names nor the seed evidence ever persisted.
            config = dict(new_agent.configuration or {})
            config["capabilities"] = linked_names
            if _record:
                # Transparency for the buyer + graduation evidence: what
                # the publisher's agent had VERIFIED before this install.
                config["seed_evidence"] = {
                    "source_template_id": str(template_id),
                    "verified_record": _record,
                }
            new_agent.configuration = config

            # 4b. Materialize the publisher's APPROVED playbooks so the
            # buyer's goal_runs.start seeds plans from them immediately
            # (seed_plan_for_run matches playbooks by keywords). Idempotent
            # by fingerprint — drafts never shipped, so these land approved.
            installed_playbooks = 0
            for pb in (template_data.get("configuration") or {}).get("playbooks") or []:
                pb_name = str(pb.get("name") or "").strip()
                pb_steps = [str(s) for s in (pb.get("steps") or [])
                            if str(s).strip()]
                if not pb_name or not pb_steps:
                    continue
                fingerprint = hashlib.sha256(
                    f"marketplace:{template_id}:{pb_name}".encode()
                ).hexdigest()[:64]
                if self.db.query(Playbook).filter(
                        Playbook.tenant_id == tenant_id,
                        Playbook.fingerprint == fingerprint).first():
                    continue
                self.db.add(Playbook(
                    tenant_id=tenant_id,
                    name=pb_name[:255],
                    description=str(pb.get("description") or "")[:1000] or None,
                    trigger_canvas_type=pb.get("trigger_canvas_type"),
                    trigger_keywords=[str(k) for k in
                                      (pb.get("trigger_keywords") or [])],
                    steps=pb_steps,
                    template_questions=[str(q) for q in
                                        (pb.get("template_questions") or [])],
                    source="authored",  # the publisher's authored process
                    approval_state="approved",
                    fingerprint=fingerprint,
                    origin_ids=["marketplace:" + str(template_id)],
                ))
                installed_playbooks += 1

            # 5. Create local installation record
            installation = AgentInstallation(
                tenant_id=tenant_id,
                template_id=template_id,
                instantiated_agent_id=new_agent.id,
                installed_version=_version,
                is_active=True,
                last_synced_version=_version,
            )
            self.db.add(installation)

            # 6. Notify SaaS of installation (for stats)
            self.saas_client.install_agent_sync(template_id, tenant_id)

            # 7. Track usage locally
            MarketplaceUsageTracker.track_usage(
                item_type="agent",
                item_id=template_id,
                success=True
            )

            self.db.commit()
            logger.info(f"Successfully installed marketplace agent {template_id} as managed agent {new_agent.id}")

            result = {
                "success": True,
                "agent_id": new_agent.id,
                "managed": True,
                "message": f"Installed {template_data['name']} successfully",
                "verified_record": _record or None,
                "playbooks_installed": installed_playbooks,
            }
            if warnings:
                result["skill_warnings"] = warnings
            return result

        except Exception as e:
            logger.error(f"Failed to install marketplace agent {template_id}: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def uninstall_agent(self, tenant_id: str, agent_id: str) -> Dict[str, Any]:
        """
        Uninstall a marketplace agent.
        Removes the agent registry and installation record. Legacy installs
        (pre-managed model) also drop their pre-loaded memory rows.
        """
        try:
            # 1. Find installation
            installation = self.db.query(AgentInstallation).filter(
                and_(
                    AgentInstallation.tenant_id == tenant_id,
                    AgentInstallation.instantiated_agent_id == agent_id
                )
            ).first()

            if not installation:
                return {"success": False, "error": "Agent was not installed from marketplace"}

            template_id = installation.template_id

            # 2. Cleanup linked memory — only for LEGACY installs; managed
            # agents never had memory copied into tenant tables.
            agent = self.db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
            config = (agent.configuration if agent else None) or {}
            if not config.get("marketplace_managed"):
                # SQLite (default Personal Edition DB) does not support the
                # PostgreSQL-only `.astext` on JSON index access — it raised
                # AttributeError on every uninstall. The plain JSON index op
                # compiles to json_extract() on SQLite and works everywhere.
                self.db.query(OperationErrorResolution).filter(
                    and_(
                        OperationErrorResolution.tenant_id == tenant_id,
                        OperationErrorResolution.resolution_metadata["source_template_id"] == template_id
                    )
                ).delete(synchronize_session=False)

            # 3. Cleanup skills
            self.db.query(AgentSkill).filter(AgentSkill.agent_id == agent_id).delete()

            # 4. Remove installation and agent
            self.db.delete(installation)

            if agent:
                self.db.delete(agent)

            self.db.commit()
            logger.info(f"Uninstalled marketplace agent {agent_id} (Template: {template_id})")

            return {"success": True, "message": "Agent uninstalled successfully"}

        except Exception as e:
            logger.error(f"Failed to uninstall agent {agent_id}: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}
