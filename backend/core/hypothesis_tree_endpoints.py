"""
Arbor Hypothesis Tree Refinement (HTR) — REST API

Exposes the HypothesisTree / OptimizationTree data structures via HTTP so that
callers (frontend, agents, CI pipelines) can create and drive tree-based
optimisation sessions without importing the library directly.

Trees are stored in an in-memory registry keyed by tree-id.  They are
intentionally ephemeral: once the process restarts the session is gone.  A
future migration can add a hypothesis_trees table if persistence is needed.

Mounted at:  /api/v1/hypothesis-tree
Tags:        arbor
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.auto_dev.models import HypothesisTreeRecord
from core.database import get_db
from core.hypothesis_tree import (
    HypothesisNode,
    HypothesisTree,
    NodeMetrics,
    NodeStatus,
    OptimizationTree,
    PruningReason,
    TaskType,
    TreeSearchParams,
)
from core.rbac_service import Permission
from core.security_dependencies import require_permission

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory session registry  (tree_id → HypothesisTree)
# ---------------------------------------------------------------------------
_TREE_REGISTRY: Dict[str, HypothesisTree] = {}


def _get_tree(tree_id: str) -> HypothesisTree:
    tree = _TREE_REGISTRY.get(tree_id)
    if tree is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hypothesis tree '{tree_id}' not found.  "
                   "Trees are ephemeral; create a new one via POST /create.",
        )
    return tree


def _persist_tree(
    db: Session,
    tree_id: str,
    tree: HypothesisTree,
    tenant_id: str,
    task_type: str,
) -> HypothesisTreeRecord:
    """
    Write (or update) a HypothesisTreeRecord in the database.

    Called on success (mark_node_success) and on deletion so that completed
    or abandoned sessions survive process restarts.  An existing row with the
    same ID is upserted; a new row is inserted if none exists.
    """
    stats = tree.get_statistics()

    record = db.query(HypothesisTreeRecord).filter(HypothesisTreeRecord.id == tree_id).first()
    if record is None:
        record = HypothesisTreeRecord(id=tree_id)
        db.add(record)

    record.tenant_id = tenant_id
    record.task_description = tree.task_description
    record.task_type = task_type
    record.tier = tree.tier
    record.session_id = tree.session_id
    record.total_nodes = stats.get("total_nodes", 0)
    record.successful_nodes = stats.get("successful_nodes", 0)
    record.pruned_nodes = stats.get("pruned_nodes", 0)
    record.total_tokens_used = tree.total_tokens_used
    record.total_cost_usd = tree.total_cost_usd
    record.winning_path = tree.winning_path or []
    record.negative_constraints = tree.negative_constraints or []
    record.optimization_score = stats.get("avg_promise_score")
    record.tree_snapshot = tree.to_dict()
    record.completed_at = tree.completed_at or datetime.now(timezone.utc)

    db.commit()
    db.refresh(record)
    logger.info(
        "[Arbor] Tree persisted to DB: id=%s tenant=%s nodes=%d",
        tree_id, tenant_id, record.total_nodes,
    )
    return record


def _get_tree(tree_id: str) -> HypothesisTree:
    tree = _TREE_REGISTRY.get(tree_id)
    if tree is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hypothesis tree '{tree_id}' not found.  "
                   "Trees are ephemeral; create a new one via POST /create.",
        )
    return tree


# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------

class CreateTreeRequest(BaseModel):
    task_description: str = Field(..., description="Natural-language description of the problem to solve")
    tier: str = Field("solo", description="Pricing tier: free | solo | enterprise")
    task_type: str = Field("coding", description="Optimisation domain: coding | workflow | routing")
    complexity_level: str = Field("standard", description="standard | high | critical")
    session_id: Optional[str] = None
    negative_constraints: List[str] = Field(default_factory=list)
    learning_insights: List[str] = Field(default_factory=list)


class CreateTreeResponse(BaseModel):
    tree_id: str
    tier: str
    max_nodes: int
    max_tokens: int
    max_cost_usd: float
    task_type: str
    created_at: str


class NodeMetricsRequest(BaseModel):
    execution_time_ms: float = 0.0
    tokens_used: int = 0
    test_pass_rate: float = 0.0
    lint_errors: int = 0
    lint_warnings: int = 0
    lines_changed: int = 0


class AddNodeRequest(BaseModel):
    hypothesis: str = Field(..., description="The proposed code diff, config change, or routing sequence")
    description: str = ""
    parent_id: Optional[str] = None
    file_path: Optional[str] = None
    promise_score: float = Field(0.5, ge=0.0, le=1.0)
    metrics: NodeMetricsRequest = Field(default_factory=NodeMetricsRequest)
    learning_tags: List[str] = Field(default_factory=list)


class AddNodeResponse(BaseModel):
    node_id: str
    added: bool
    reason: Optional[str] = None
    tree_stats: Dict[str, Any]


class PruneNodeRequest(BaseModel):
    reason: str = Field("manual", description="PruningReason value: lint_failed | test_failed | latency_regression | resource_exceeded | negative_constraint | budget_exceeded | duplicate_hypothesis | low_promise | manual")


class SearchRequest(BaseModel):
    algorithm: str = Field("best_first", description="best_first | mcts | beam_search")
    max_depth: int = 5
    beam_width: int = 3
    exploration_constant: float = 1.41
    promise_threshold: float = 0.3
    prune_on_lint_error: bool = True
    prune_on_test_failure: bool = True
    use_historical_insights: bool = True


class AddConstraintRequest(BaseModel):
    constraint: str = Field(..., description="Pattern to avoid in future hypotheses")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/create", response_model=CreateTreeResponse, status_code=status.HTTP_201_CREATED)
async def create_tree(
    request: CreateTreeRequest,
    _user=Depends(require_permission(Permission.WORKFLOW_VIEW)),
) -> CreateTreeResponse:
    """
    Create a new Hypothesis Tree for an optimisation session.

    The tree is initialised with the budget limits for the requested pricing
    tier and stored in-memory under a fresh UUID.
    """
    try:
        task_type_enum = TaskType(request.task_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid task_type '{request.task_type}'. Must be one of: coding, workflow, routing",
        )

    tree_id = str(uuid.uuid4())

    if request.task_type != "coding":
        tree: HypothesisTree = OptimizationTree(
            id=tree_id,
            task_description=request.task_description,
            tier=request.tier,
            complexity_level=request.complexity_level,
            session_id=request.session_id,
            negative_constraints=list(request.negative_constraints),
            learning_insights=list(request.learning_insights),
            task_type=task_type_enum,
        )
    else:
        tree = HypothesisTree(
            id=tree_id,
            task_description=request.task_description,
            tier=request.tier,
            complexity_level=request.complexity_level,
            session_id=request.session_id,
            negative_constraints=list(request.negative_constraints),
            learning_insights=list(request.learning_insights),
        )

    _TREE_REGISTRY[tree_id] = tree

    logger.info(
        "[Arbor] Tree created: id=%s tier=%s task_type=%s max_nodes=%d",
        tree_id, request.tier, request.task_type, tree.max_nodes,
    )

    return CreateTreeResponse(
        tree_id=tree_id,
        tier=tree.tier,
        max_nodes=tree.max_nodes,
        max_tokens=tree.max_tokens,
        max_cost_usd=tree.max_cost_usd,
        task_type=request.task_type,
        created_at=tree.created_at.isoformat(),
    )


@router.post("/{tree_id}/add-node", response_model=AddNodeResponse)
async def add_node(
    tree_id: str,
    request: AddNodeRequest,
    _user=Depends(require_permission(Permission.WORKFLOW_VIEW)),
) -> AddNodeResponse:
    """
    Add a hypothesis node to an existing tree.

    Returns ``added=False`` (HTTP 200, not 4xx) when the tree budget is
    exhausted so callers can inspect the reason without exception handling.
    """
    tree = _get_tree(tree_id)

    # Reject hypotheses that violate learned constraints
    if tree.violates_constraint(request.hypothesis):
        return AddNodeResponse(
            node_id="",
            added=False,
            reason="Hypothesis violates a negative constraint learned from previous failures.",
            tree_stats=tree.get_statistics(),
        )

    metrics = NodeMetrics(
        execution_time_ms=request.metrics.execution_time_ms,
        tokens_used=request.metrics.tokens_used,
        test_pass_rate=request.metrics.test_pass_rate,
        lint_errors=request.metrics.lint_errors,
        lint_warnings=request.metrics.lint_warnings,
        lines_changed=request.metrics.lines_changed,
    )

    depth = 0
    if request.parent_id:
        parent = tree.nodes.get(request.parent_id)
        if parent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Parent node '{request.parent_id}' not found in tree '{tree_id}'.",
            )
        depth = parent.depth + 1

    node = HypothesisNode(
        parent_id=request.parent_id,
        depth=depth,
        hypothesis=request.hypothesis,
        description=request.description,
        file_path=request.file_path,
        promise_score=request.promise_score,
        metrics=metrics,
        session_id=tree.session_id,
        learning_tags=list(request.learning_tags),
    )

    added = tree.add_node(node)
    reason: Optional[str] = None
    if not added:
        reason = (
            f"Budget exceeded: nodes={len(tree.nodes)}/{tree.max_nodes}, "
            f"tokens={tree.total_tokens_used}/{tree.max_tokens}, "
            f"cost=${tree.total_cost_usd:.4f}/${tree.max_cost_usd}"
        )
        logger.warning("[Arbor] Node rejected — %s (tree=%s)", reason, tree_id)

    return AddNodeResponse(
        node_id=node.id if added else "",
        added=added,
        reason=reason,
        tree_stats=tree.get_statistics(),
    )


@router.post("/{tree_id}/nodes/{node_id}/succeed")
async def mark_node_success(
    tree_id: str,
    node_id: str,
    tenant_id: str = Query("", description="Tenant ID for DB persistence"),
    task_type: str = Query("coding", description="Task type for DB record"),
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.WORKFLOW_VIEW)),
) -> Dict[str, Any]:
    """Mark a node as the winning hypothesis, record the winning path, and persist the tree to DB."""
    tree = _get_tree(tree_id)
    node = tree.nodes.get(node_id)
    if node is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node '{node_id}' not found in tree '{tree_id}'.",
        )

    node.status = NodeStatus.SUCCESS
    node.updated_at = datetime.now(timezone.utc)
    tree.winning_path = tree.get_path_to_root(node_id)
    tree.completed_at = datetime.now(timezone.utc)
    tree.updated_at = datetime.now(timezone.utc)

    logger.info(
        "[Arbor] Winning node set: tree=%s node=%s path_length=%d",
        tree_id, node_id, len(tree.winning_path),
    )

    # Persist to DB
    record = None
    if tenant_id:
        try:
            record = _persist_tree(db, tree_id, tree, tenant_id, task_type)
        except Exception as exc:
            logger.warning("[Arbor] DB persist failed (non-fatal): %s", exc)

    return {
        "node_id": node_id,
        "winning_path": tree.winning_path,
        "persisted": record is not None,
        "statistics": tree.get_statistics(),
    }


@router.post("/{tree_id}/nodes/{node_id}/prune")
async def prune_node(
    tree_id: str,
    node_id: str,
    request: PruneNodeRequest,
    _user=Depends(require_permission(Permission.WORKFLOW_VIEW)),
) -> Dict[str, Any]:
    """Prune a node and all its descendants from the tree."""
    tree = _get_tree(tree_id)

    try:
        reason_enum = PruningReason(request.reason)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid pruning reason '{request.reason}'.",
        )

    pruned_count = tree.prune_branch(node_id, reason_enum)
    if pruned_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node '{node_id}' not found in tree '{tree_id}'.",
        )

    logger.info(
        "[Arbor] Pruned %d node(s): tree=%s root_node=%s reason=%s",
        pruned_count, tree_id, node_id, request.reason,
    )
    return {
        "pruned_count": pruned_count,
        "reason": request.reason,
        "statistics": tree.get_statistics(),
    }


@router.post("/{tree_id}/constraints")
async def add_constraint(
    tree_id: str,
    request: AddConstraintRequest,
    _user=Depends(require_permission(Permission.WORKFLOW_VIEW)),
) -> Dict[str, Any]:
    """Teach the tree a negative constraint to avoid in future hypotheses."""
    tree = _get_tree(tree_id)
    tree.add_negative_constraint(request.constraint)
    return {
        "constraint": request.constraint,
        "total_constraints": len(tree.negative_constraints),
    }


@router.get("/{tree_id}/statistics")
async def get_statistics(
    tree_id: str,
    _user=Depends(require_permission(Permission.WORKFLOW_VIEW)),
) -> Dict[str, Any]:
    """
    Return aggregated statistics for a hypothesis tree.

    Matches the response shape documented in ARBOR_FRAMEWORK.md:
    total_nodes, successful_nodes, pruned_nodes, total_tokens_used,
    total_cost_usd, winning_path.
    """
    tree = _get_tree(tree_id)
    stats = tree.get_statistics()
    stats["winning_path"] = tree.winning_path
    stats["negative_constraints"] = tree.negative_constraints
    stats["learning_insights"] = tree.learning_insights
    return stats


@router.get("/{tree_id}")
async def get_tree(
    tree_id: str,
    _user=Depends(require_permission(Permission.WORKFLOW_VIEW)),
) -> Dict[str, Any]:
    """Return the full serialised tree including all nodes."""
    return _get_tree(tree_id).to_dict()


@router.post("/{tree_id}/search")
async def run_search(
    tree_id: str,
    request: SearchRequest,
    _user=Depends(require_permission(Permission.WORKFLOW_VIEW)),
) -> Dict[str, Any]:
    """
    Run a search pass over the existing nodes using the specified algorithm.

    Returns the best-ranked pending node (the next hypothesis to evaluate)
    based on promise scores, UCB1 (MCTS) or beam selection.
    """
    tree = _get_tree(tree_id)

    pending = [n for n in tree.nodes.values() if n.status == NodeStatus.PENDING]
    if not pending:
        return {
            "algorithm": request.algorithm,
            "next_node": None,
            "reason": "No pending nodes remain in the tree.",
            "statistics": tree.get_statistics(),
        }

    # Filter by minimum promise threshold
    candidates = [n for n in pending if n.promise_score >= request.promise_threshold]
    if not candidates:
        candidates = pending  # fall back to all pending if threshold too high

    if request.algorithm == "best_first":
        best = max(candidates, key=lambda n: n.promise_score)

    elif request.algorithm == "mcts":
        best = max(candidates, key=lambda n: n.get_ucb1_score(request.exploration_constant))

    elif request.algorithm == "beam_search":
        sorted_candidates = sorted(candidates, key=lambda n: n.promise_score, reverse=True)
        beam = sorted_candidates[: request.beam_width]
        best = beam[0]

    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown algorithm '{request.algorithm}'. Use: best_first, mcts, beam_search",
        )

    logger.info(
        "[Arbor] Search (%s): selected node=%s promise=%.3f (tree=%s)",
        request.algorithm, best.id, best.promise_score, tree_id,
    )

    # Mark as EXPANDING
    best.status = NodeStatus.EXPANDING
    best.visit_count += 1
    tree.total_nodes_expanded += 1
    tree.updated_at = datetime.now(timezone.utc)

    return {
        "algorithm": request.algorithm,
        "next_node": best.to_dict(),
        "candidates_evaluated": len(candidates),
        "statistics": tree.get_statistics(),
    }


@router.delete("/{tree_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tree(
    tree_id: str,
    tenant_id: str = Query("", description="Tenant ID for DB persistence before deletion"),
    task_type: str = Query("coding", description="Task type for DB record"),
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.WORKFLOW_MANAGE)),
) -> None:
    """Persist the tree to DB then remove it from the in-memory registry."""
    tree = _get_tree(tree_id)  # raises 404 if missing
    if tenant_id:
        try:
            _persist_tree(db, tree_id, tree, tenant_id, task_type)
        except Exception as exc:
            logger.warning("[Arbor] DB persist on delete failed (non-fatal): %s", exc)
    del _TREE_REGISTRY[tree_id]
    logger.info("[Arbor] Tree deleted from memory: id=%s", tree_id)


@router.get("/", include_in_schema=True)
async def list_trees(
    _user=Depends(require_permission(Permission.WORKFLOW_VIEW)),
) -> Dict[str, Any]:
    """List all active (in-memory) hypothesis trees."""
    return {
        "trees": [
            {
                "tree_id": tid,
                "task_description": t.task_description,
                "tier": t.tier,
                "total_nodes": len(t.nodes),
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for tid, t in _TREE_REGISTRY.items()
        ],
        "total": len(_TREE_REGISTRY),
    }


@router.get("/history")
async def list_tree_history(
    tenant_id: str = Query(..., description="Tenant ID to scope history query"),
    task_type: Optional[str] = Query(None, description="Filter by task_type: coding|workflow|routing"),
    tier: Optional[str] = Query(None, description="Filter by pricing tier"),
    limit: int = Query(20, ge=1, le=100, description="Max rows to return"),
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.WORKFLOW_VIEW)),
) -> Dict[str, Any]:
    """
    Query persisted (completed) hypothesis trees from the database.

    Useful for:
    - Finding the winning_path of past sessions to seed new trees
    - Analytics on pruning rates and budget utilisation per tier
    - Surfacing negative_constraints from failed sessions
    """
    query = db.query(HypothesisTreeRecord).filter(
        HypothesisTreeRecord.tenant_id == tenant_id
    )
    if task_type:
        query = query.filter(HypothesisTreeRecord.task_type == task_type)
    if tier:
        query = query.filter(HypothesisTreeRecord.tier == tier)

    records = query.order_by(HypothesisTreeRecord.created_at.desc()).limit(limit).all()

    return {
        "tenant_id": tenant_id,
        "total": len(records),
        "trees": [
            {
                "tree_id": r.id,
                "task_description": r.task_description,
                "task_type": r.task_type,
                "tier": r.tier,
                "total_nodes": r.total_nodes,
                "successful_nodes": r.successful_nodes,
                "pruned_nodes": r.pruned_nodes,
                "total_tokens_used": r.total_tokens_used,
                "optimization_score": r.optimization_score,
                "winning_path": r.winning_path,
                "negative_constraints": r.negative_constraints,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in records
        ],
    }


@router.get("/history/{tree_id}")
async def get_tree_history(
    tree_id: str,
    db: Session = Depends(get_db),
    _user=Depends(require_permission(Permission.WORKFLOW_VIEW)),
) -> Dict[str, Any]:
    """
    Retrieve the full persisted snapshot of a completed tree from DB.

    Returns the complete ``tree_snapshot`` (all nodes + metadata) so callers
    can replay or inspect a session that is no longer in memory.
    """
    record = db.query(HypothesisTreeRecord).filter(HypothesisTreeRecord.id == tree_id).first()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No persisted tree found with id '{tree_id}'.",
        )
    return {
        "tree_id": record.id,
        "task_description": record.task_description,
        "task_type": record.task_type,
        "tier": record.tier,
        "session_id": record.session_id,
        "winning_path": record.winning_path,
        "negative_constraints": record.negative_constraints,
        "optimization_score": record.optimization_score,
        "tree_snapshot": record.tree_snapshot,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "completed_at": record.completed_at.isoformat() if record.completed_at else None,
    }
