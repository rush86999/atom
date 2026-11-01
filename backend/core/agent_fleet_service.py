import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from core.models import DelegationChain, ChainLink, AgentRegistry

logger = logging.getLogger(__name__)

class FleetDelegationError(ValueError):
    """A delegation the fleet refuses before creating the link."""

    def __init__(self, code: str, message: str, **extra: Any):
        self.code = code
        self.extra = extra
        super().__init__(message)


class AgentFleetService:
    """
    Service for orchestrating multi-agent fleets (Admiralty model).
    Manages delegation chains, recruitment, and shared blackboard context.
    """

    def __init__(self, db: Session):
        self.db = db

    def initialize_fleet(
        self,
        tenant_id: str,
        root_agent_id: str,
        root_task: str,
        root_execution_id: Optional[str] = None,
        initial_metadata: Optional[Dict[str, Any]] = None
    ) -> DelegationChain:
        """
        Initializes a new delegation chain (a fleet root).
        """
        logger.info(f"Initializing fleet for root agent {root_agent_id}, task: {root_task[:50]}...")
        
        chain = DelegationChain(
            tenant_id=tenant_id,
            root_agent_id=root_agent_id,
            root_task=root_task,
            root_execution_id=root_execution_id,
            status="active",
            metadata_json=initial_metadata or {},
            started_at=datetime.now(timezone.utc)
        )
        
        self.db.add(chain)
        self.db.commit()
        self.db.refresh(chain)
        
        return chain

    def recruit_member(
        self,
        chain_id: str,
        parent_agent_id: str,
        child_agent_id: str,
        task_description: str,
        context_json: Optional[Dict[str, Any]] = None,
        link_order: int = 0,
        optimization_metadata: Optional[Dict[str, Any]] = None
    ) -> ChainLink:
        """
        Adds a new specialized agent to an active fleet.
        """
        logger.info(f"Recruiting fleet member {child_agent_id} for chain {chain_id}")

        chain = self.db.query(DelegationChain).filter(
            DelegationChain.id == chain_id).first()
        # Legacy callers (fault-tolerance recovery) create links without a
        # persisted chain row. There is no chain context to enforce depth or
        # scope against, so only contract validation applies there.
        # Validation needs the persisted chain row. Mocks and partial
        # adapters pose as a chain object but carry no real identity; only a
        # materialized DelegationChain is authoritative. Legacy callers with
        # no chain row keep working (depth/scope have no context to check).
        real_chain = isinstance(chain, DelegationChain)
        links = []
        if real_chain:
            links = list(self.db.query(ChainLink).filter(
                ChainLink.chain_id == chain_id).all())

        if real_chain:
            # --- cycles + graph depth over EVERY edge ---------------------
            adjacency: Dict[str, List[str]] = {}
            for existing in links:
                adjacency.setdefault(existing.parent_agent_id, []).append(
                    existing.child_agent_id)

            def _reachable(start_node: str, target: str) -> bool:
                stack = [start_node]
                seen = set()
                while stack:
                    node = stack.pop()
                    if node == target:
                        return True
                    if node in seen:
                        continue
                    seen.add(node)
                    stack.extend(adjacency.get(node, []))
                return False

            # Adding parent -> child closes a cycle when the child can already
            # reach the parent through ANY edge. The old one-parent map missed
            # the second parent of a DAG node (root->a, root->b, a->b, b->a).
            if (child_agent_id == parent_agent_id
                    or child_agent_id == chain.root_agent_id
                    or _reachable(child_agent_id, parent_agent_id)):
                raise FleetDelegationError(
                    "delegation_cycle",
                    f"Recruiting {child_agent_id} under {parent_agent_id} would "
                    "create a delegation cycle.")

            # Depth is the LONGEST root path to a node, not the shortest:
            # a DAG can reach a node at several depths and the deepest path is
            # the one that breaches the recursion limit. Evaluate the ENTIRE
            # proposed graph, not just the new child: a new edge can deepen an
            # existing descendant even when the immediate child is in range.
            depths: Dict[str, int] = {chain.root_agent_id: 0}

            def _walk(node: str, path: frozenset,
                      edges: Dict[str, List[str]],
                      out: Dict[str, int]) -> None:
                for nxt in edges.get(node, []):
                    if nxt in path:
                        continue  # legacy graph already cyclic; do not loop
                    candidate = out.get(node, 0) + 1
                    if candidate > out.get(nxt, -1):
                        out[nxt] = candidate
                    _walk(nxt, path | {nxt}, edges, out)

            _walk(chain.root_agent_id, frozenset({chain.root_agent_id}),
                  adjacency, depths)
            if parent_agent_id not in depths:
                raise FleetDelegationError(
                    "unknown_parent",
                    f"Parent agent {parent_agent_id} is not part of chain "
                    f"{chain_id}.")

            proposed = {node: list(children)
                        for node, children in adjacency.items()}
            proposed.setdefault(parent_agent_id, []).append(child_agent_id)
            proposed_depths: Dict[str, int] = {chain.root_agent_id: 0}
            _walk(chain.root_agent_id, frozenset({chain.root_agent_id}),
                  proposed, proposed_depths)
            new_depth = depths[parent_agent_id] + 1
            deepest = max(proposed_depths.values(), default=0)
            max_depth = int(chain.max_depth or 5)
            if new_depth > max_depth or deepest > max_depth:
                raise FleetDelegationError(
                    "depth_exceeded",
                    f"Delegation depth {max(new_depth, deepest)} exceeds the "
                    f"chain limit {max_depth}; a wide but shallow fleet is "
                    f"allowed.",
                    depth=max(new_depth, deepest), max_depth=max_depth)

            # --- cross-scope references ---------------------------------
            root_agent = self.db.query(AgentRegistry).filter(
                AgentRegistry.id == chain.root_agent_id).first()
            parent_agent = self.db.query(AgentRegistry).filter(
                AgentRegistry.id == parent_agent_id).first()
            child_agent = self.db.query(AgentRegistry).filter(
                AgentRegistry.id == child_agent_id).first()
            # A cross-tenant parent could recruit a local child into a foreign
            # fleet (the link looks tenant-local while authority came from
            # somewhere else).
            if parent_agent is not None:
                if (chain.tenant_id and parent_agent.tenant_id
                        and parent_agent.tenant_id != chain.tenant_id):
                    raise FleetDelegationError(
                        "cross_scope",
                        f"Parent agent {parent_agent_id} belongs to another "
                        "tenant.")
                if root_agent is not None:
                    if (root_agent.workspace_id and parent_agent.workspace_id
                            and parent_agent.workspace_id
                            != root_agent.workspace_id):
                        raise FleetDelegationError(
                            "cross_scope",
                            f"Parent agent {parent_agent_id} belongs to "
                            "another workspace.")
            if child_agent is not None:
                if (chain.tenant_id and child_agent.tenant_id
                        and child_agent.tenant_id != chain.tenant_id):
                    raise FleetDelegationError(
                        "cross_scope",
                        f"Agent {child_agent_id} belongs to another tenant.")
                if root_agent is not None:
                    if (root_agent.tenant_id and child_agent.tenant_id
                            and child_agent.tenant_id != root_agent.tenant_id):
                        raise FleetDelegationError(
                            "cross_scope",
                            f"Agent {child_agent_id} belongs to another tenant.")
                    if (root_agent.workspace_id and child_agent.workspace_id
                            and child_agent.workspace_id
                            != root_agent.workspace_id):
                        raise FleetDelegationError(
                            "cross_scope",
                            f"Agent {child_agent_id} belongs to another "
                            "workspace.")

        # --- contract accountability -------------------------------------
        merged_context = dict(context_json or {})
        if optimization_metadata:
            merged_context["optimization"] = optimization_metadata
        contract_raw = merged_context.get("delegation_contract")
        if contract_raw is not None:
            from core.fleet_orchestration.delegation_contracts import (
                ContractError, validate_contract_payload,
            )

            try:
                merged_context["delegation_contract"] = (
                    validate_contract_payload(contract_raw))
            except ContractError as exc:
                raise FleetDelegationError(
                    "invalid_contract",
                    f"Delegation contract rejected: {exc}",
                    detail=exc.code,
                    **getattr(exc, "extra", {}),
                )

        final_context = merged_context

        link = ChainLink(
            chain_id=chain_id,
            parent_agent_id=parent_agent_id,
            child_agent_id=child_agent_id,
            task_description=task_description,
            context_json=final_context,
            status="pending",
            link_order=link_order,
            started_at=datetime.now(timezone.utc)
        )
        
        self.db.add(link)
        
        # Increment total links in chain
        if chain is not None:
            chain.total_links = int(chain.total_links or 0) + 1
            
        self.db.commit()
        self.db.refresh(link)
        
        return link

    def update_blackboard(self, chain_id: str, updates: Dict[str, Any]):
        """
        Updates the shared fleet context (blackboard).
        """
        chain = self.db.query(DelegationChain).filter(DelegationChain.id == chain_id).first()
        if not chain:
            logger.error(f"Cannot update blackboard: Chain {chain_id} not found")
            return

        current_metadata = chain.metadata_json or {}
        current_metadata.update(updates)
        chain.metadata_json = current_metadata
        
        self.db.commit()
        logger.info(f"Updated blackboard for chain {chain_id}")

    def get_blackboard(self, chain_id: str) -> Dict[str, Any]:
        """
        Retrieves the shared fleet context.
        """
        chain = self.db.query(DelegationChain).filter(DelegationChain.id == chain_id).first()
        return chain.metadata_json if chain else {}

    def update_link_status(
        self, 
        link_id: str, 
        status: str, 
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        """
        Updates the status and result of a specific delegation link.
        """
        link = self.db.query(ChainLink).filter(ChainLink.id == link_id).first()
        if not link:
            logger.error(f"Link {link_id} not found")
            return

        link.status = status
        if result is not None:
            link.result_json = result
        if error is not None:
            link.error_message = error
            
        if status in ["completed", "failed"]:
            link.completed_at = datetime.now(timezone.utc)
            if link.started_at:
                # started_at comes from the DB (server_default=func.now()) and
                # SQLite stores it NAIVE — subtracting an aware completed_at
                # raised TypeError on every completion. Normalize to UTC.
                started_at = link.started_at
                if started_at.tzinfo is None:
                    started_at = started_at.replace(tzinfo=timezone.utc)
                delta = link.completed_at - started_at
                link.duration_ms = int(delta.total_seconds() * 1000)

        self.db.commit()
        logger.info(f"Link {link_id} updated to {status}")

        # Trigger Self-Healing (Async)
        if status in ["completed", "failed"]:
            try:
                from core.fleet.self_heal_service import SelfHealService
                import asyncio
                
                self_heal = SelfHealService(self.db)
                # In Upstream, we also use background tasks to ensure low latency for the orchestrator
                asyncio.create_task(self_heal.process_link_update(link_id))
            except Exception as e:
                logger.error(f"⚠️ Self-Heal Trigger Failed: {e}")

    def complete_chain(self, chain_id: str, status: str = "completed"):
        """
        Marks a delegation chain as finished.
        """
        chain = self.db.query(DelegationChain).filter(DelegationChain.id == chain_id).first()
        if not chain:
            return

        chain.status = status
        chain.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        logger.info(f"Chain {chain_id} finalized with status: {status}")
