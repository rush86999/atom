"""Tests for the ontology/goal gap remediation (RDFS/OWL gap analysis).

Covers: chunker, ontology service (subclass closure, domain/range validation,
alias resolution, JSON-LD export, DB seeding), criterion evaluator,
GoalService state machine + evaluation, HTN planner, shared vocabulary
adapters, action contracts (preconditions/effects), and the objective loop
wiring (objective_from_context with structured criteria).
"""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# SQLite test fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def db_session_factory():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from core.models import Base, GoalObjective, GraphEdge, GraphNode, RelationTypeDefinition, EntityTypeDefinition

    # StaticPool: every connection shares the one in-memory database —
    # otherwise each pooled connection gets its own empty :memory: DB.
    engine = create_engine("sqlite:///:memory:",
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine, tables=[
        GoalObjective.__table__, GraphEdge.__table__, GraphNode.__table__,
        RelationTypeDefinition.__table__, EntityTypeDefinition.__table__,
    ])
    # GraphNode/GraphEdge/GoalObjective FK tenants.id — not enforced on SQLite.
    maker = sessionmaker(bind=engine)

    @contextmanager
    def factory():
        session = maker()
        try:
            yield session
        finally:
            session.close()

    return factory


def _seed_graph_nodes(factory, workspace_id="ws-test"):
    from core.models import GraphEdge, GraphNode
    with factory() as session:
        if session.get(GraphNode, "n-alice") is None:
            alice = GraphNode(id="n-alice", workspace_id=workspace_id, name="Alice", type="Person")
            acme = GraphNode(id="n-acme", workspace_id=workspace_id, name="Acme Project", type="Project")
            session.add_all([alice, acme])
            session.flush()
            session.add(GraphEdge(
                id="e-1", workspace_id=workspace_id, source_node_id="n-alice",
                target_node_id="n-acme", relationship_type="OWNS",
                properties={"verification": "proposed", "occurrence_count": 1},
            ))
            session.commit()


# ---------------------------------------------------------------------------
# Chunker (A3)
# ---------------------------------------------------------------------------

class TestChunker:
    def test_chunks_respect_size(self):
        from core.ontology.chunker import chunk_text
        text = ("This is a sentence. " * 200).strip()
        chunks = chunk_text(text, chunk_size=500, overlap=100)
        assert len(chunks) > 1
        for chunk in chunks[1:]:
            assert len(chunk.text) <= 700  # size + overlap headroom

    def test_empty_text(self):
        from core.ontology.chunker import chunk_text
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_locate_name_chunks(self):
        from core.ontology.chunker import chunk_text, locate_name_chunks
        chunks = chunk_text("Alice owns Acme. " + "Filler sentence here. " * 100,
                            chunk_size=200, overlap=20)
        hits = locate_name_chunks("Alice", chunks)
        assert hits and 0 in hits
        assert locate_name_chunks("Nobody Named This", chunks) == []


# ---------------------------------------------------------------------------
# Ontology service (A1/A2/A4/A5/A9)
# ---------------------------------------------------------------------------

class TestOntologyService:
    def test_subclass_closure(self):
        from core.ontology.ontology_service import OntologyService
        onto = OntologyService()
        assert onto.is_subtype("Invoice", "Transaction")
        assert onto.is_subtype("PurchaseOrder", "Transaction")
        assert onto.is_subtype("Deal", "Opportunity")
        assert not onto.is_subtype("Transaction", "Invoice")

    def test_alias_resolution(self):
        from core.ontology.ontology_service import OntologyService
        onto = OntologyService()
        assert onto.resolve_entity_type("org") == "Organization"
        assert onto.resolve_entity_type("COMPANY") == "Organization"
        assert onto.resolve_entity_type("Person") == "Person"
        assert onto.resolve_entity_type("zzz-unknown") is None

    def test_domain_range_validation(self):
        from core.ontology.ontology_service import OntologyService
        onto = OntologyService()
        ok = onto.validate_relationship("Person", "OWNS", "Deal")
        assert ok.ok and ok.declared  # Deal is-a Opportunity, in OWNS range

        bad = onto.validate_relationship("Task", "OWNS", "Project")
        assert not bad.ok and bad.declared and "domain" in bad.reason

        bad_range = onto.validate_relationship("Person", "OWNS", "Shipment")
        assert not bad_range.ok and "range" in bad_range.reason

    def test_undeclared_relation_passes(self):
        from core.ontology.ontology_service import OntologyService
        onto = OntologyService()
        result = onto.validate_relationship("Person", "FRIENDS_WITH", "Person")
        assert result.ok and not result.declared

    def test_wildcard_relation(self):
        from core.ontology.ontology_service import OntologyService
        onto = OntologyService()
        assert onto.validate_relationship("Widget", "LINKS_TO_EXTERNAL", "Gadget").ok

    def test_jsonld_export(self):
        from core.ontology.ontology_service import OntologyService
        doc = OntologyService().to_jsonld()
        assert doc["@type"] == "owl:Ontology"
        graph = doc["@graph"]
        ids = {node["@id"] for node in graph}
        assert "https://atom.local/ontology/Invoice" in ids
        invoice = next(n for n in graph if n["@id"].endswith("/Invoice"))
        assert invoice["rdfs:subClassOf"]["@id"].endswith("/Transaction")
        owns = next(n for n in graph if n["@id"].endswith("/OWNS"))
        assert any(d["@id"].endswith("/Person") for d in owns["rdfs:domain"])

    def test_db_seeding_and_schema(self, db_session_factory):
        from core.ontology.ontology_service import OntologyService
        onto = OntologyService(tenant_id="t-test", session_factory=db_session_factory)
        created = onto.ensure_seeded()
        assert created["entity_types_created"] > 10
        assert created["relations_created"] >= 10
        # Idempotent
        again = onto.ensure_seeded()
        assert again == {"entity_types_created": 0, "relations_created": 0}
        schema = onto.get_schema()
        slugs = {t["slug"] for t in schema["entity_types"]}
        assert {"Person", "Invoice", "Deal"} <= slugs
        names = {r["name"] for r in schema["relations"]}
        assert {"OWNS", "PARTICIPATED_IN", "INTENT"} <= names


# ---------------------------------------------------------------------------
# Criterion evaluator (B2/B7)
# ---------------------------------------------------------------------------

class TestCriterionEvaluator:
    def test_entity_and_edge_predicates(self, db_session_factory):
        from core.goals.criterion_evaluator import CriterionEvaluator
        _seed_graph_nodes(db_session_factory)
        ev = CriterionEvaluator(workspace_id="ws-test", session_factory=db_session_factory)
        ok = ev.evaluate([{"type": "entity_exists", "name": "Alice", "entity_type": "Person"}])
        assert ok[0].satisfied
        miss = ev.evaluate([{"type": "entity_exists", "name": "Bob"}])
        assert not miss[0].satisfied

        edge = ev.evaluate([{
            "type": "graph_edge_exists",
            "source": {"name": "Alice"}, "relation": "OWNS",
            "target": {"name": "Acme Project"},
        }])
        assert edge[0].satisfied

        no_edge = ev.evaluate([{
            "type": "graph_edge_exists",
            "source": {"name": "Alice"}, "relation": "STAKEHOLDER_OF",
            "target": {"name": "Acme Project"},
        }])
        assert not no_edge[0].satisfied

    def test_state_numeric_combinators(self):
        from core.goals.criterion_evaluator import CriterionEvaluator
        ev = CriterionEvaluator()
        state = {"final_answer": "The report is done", "steps_done": 4}
        results = ev.evaluate([
            {"type": "state_contains", "key": "final_answer", "value": "done"},
            {"type": "numeric_compare", "left": {"$state": "steps_done"}, "op": ">=", "right": 3},
            {"type": "any_of", "criteria": [
                {"type": "state_equals", "key": "final_answer", "value": "nope"},
                {"type": "state_equals", "key": "final_answer", "value": "The report is done"},
            ]},
            {"type": "all_of", "criteria": [
                {"type": "state_equals", "key": "final_answer", "value": "nope"},
            ]},
            {"type": "manual", "note": "human sign-off"},
            {"type": "bogus_type"},
        ], state)
        assert results[0].satisfied
        assert results[1].satisfied
        assert results[2].satisfied
        assert not results[3].satisfied
        assert not results[4].satisfied  # manual never auto-satisfied
        assert results[5].error and "unknown criterion type" in results[5].error
        assert ev.satisfaction_ratio(results) == pytest.approx(3 / 6)


# ---------------------------------------------------------------------------
# GoalService (B1/B8/B9)
# ---------------------------------------------------------------------------

class TestGoalService:
    def test_create_evaluate_achieve(self, db_session_factory):
        from core.goals.goal_service import GoalService
        _seed_graph_nodes(db_session_factory)
        svc = GoalService(workspace_id="ws-test", session_factory=db_session_factory)
        goal = svc.create_goal(
            title="Alice owns Acme",
            criteria=[
                {"type": "entity_exists", "name": "Alice"},
                {"type": "graph_edge_exists", "source": {"name": "Alice"},
                 "relation": "OWNS", "target": {"name": "Acme Project"}},
            ],
            key_results=[{"description": "Ownership recorded", "metric": "graph_edge_count", "target": 1}],
        )
        assert goal["status"] == "active"
        result = svc.evaluate(goal["id"])
        assert result["progress"] == 100.0
        assert result["status"] == "achieved"

    def test_partial_progress(self, db_session_factory):
        from core.goals.goal_service import GoalService
        svc = GoalService(workspace_id="ws-test2", session_factory=db_session_factory)
        goal = svc.create_goal(title="Impossible", criteria=[
            {"type": "entity_exists", "name": "Alice"},   # ws-test2 has no nodes
            {"type": "state_equals", "key": "x", "value": 1},
        ])
        result = svc.evaluate(goal["id"])
        assert result["status"] != "achieved"

    def test_state_machine_guards(self, db_session_factory):
        from core.goals.goal_service import GoalService, GoalTransitionError
        svc = GoalService(workspace_id="ws-test3", session_factory=db_session_factory)
        goal = svc.create_goal(title="Guarded")
        svc.transition(goal["id"], "achieved")
        with pytest.raises(GoalTransitionError):
            svc.transition(goal["id"], "active")  # terminal
        with pytest.raises(GoalTransitionError):
            svc.transition(goal["id"], "bogus_status")

    def test_to_objective_satisfaction(self, db_session_factory):
        from core.goals.goal_service import GoalService
        _seed_graph_nodes(db_session_factory)
        svc = GoalService(workspace_id="ws-test", session_factory=db_session_factory)
        goal = svc.create_goal(title="Obj", criteria=[{"type": "entity_exists", "name": "Alice"}])
        objective = svc.to_objective(goal["id"])
        assert objective is not None
        assert objective.is_satisfied({"final_answer": "anything"})

        goal2 = svc.create_goal(title="Obj2", criteria=[{"type": "entity_exists", "name": "Ghost"}])
        assert not svc.to_objective(goal2["id"]).is_satisfied({})


# ---------------------------------------------------------------------------
# HTN planner (B5/B6)
# ---------------------------------------------------------------------------

class TestHTNPlanner:
    def test_methods_loaded_from_templates(self):
        from core.goals.htn_planner import HTNPlanner
        methods = HTNPlanner().list_methods()
        names = {m["template_id"] for m in methods}
        assert {"htn_content_publish", "htn_invoice_followup"} <= names

    def test_select_and_decompose(self):
        from core.goals.htn_planner import HTNPlanner
        plan = HTNPlanner().decompose("Publish a blog article about invoice best practices")
        assert plan["matched"]
        assert plan["method"] == "Content Publish Pipeline"
        assert plan["subtasks"] and not plan["cycles"]
        assert plan["execution_groups"]  # topological parallel groups present
        ids = {t["id"] for t in plan["subtasks"]}
        for task in plan["subtasks"]:
            assert set(task["depends_on"]) <= ids  # no dangling deps

    def test_generic_fallback_still_dag(self):
        from core.goals.htn_planner import HTNPlanner
        plan = HTNPlanner().decompose("something with no matching method keywords xyzzy")
        assert not plan["matched"]
        assert plan["subtasks"] and not plan["cycles"]

    def test_cycle_detection(self):
        from core.goals.htn_planner import HTNPlanner
        cycles = HTNPlanner._validate_dag([
            {"id": "a", "title": "a", "depends_on": ["b"]},
            {"id": "b", "title": "b", "depends_on": ["a"]},
        ])
        assert cycles


# ---------------------------------------------------------------------------
# Shared vocabulary (B3)
# ---------------------------------------------------------------------------

class TestVocabulary:
    def test_adapters(self):
        from core.ontology.vocabulary import (
            NodeKind, from_board_task, from_fleet_subtask, from_goal_objective,
            from_goal_subtask, from_workflow_step,
        )
        board = from_board_task({"id": "bt1", "title": "Ship it", "status": "in_progress",
                                 "parent_task_id": "bt0"})
        assert board.kind == NodeKind.TASK and board.source_system == "board"
        assert board.status == "IN_PROGRESS" and board.parent_id == "bt0"

        step = from_workflow_step({"step_id": "s1", "name": "Fetch", "depends_on": ["s0"]}, "wf9")
        assert step.depends_on == ["s0"] and step.parent_id == "wf9"

        fleet = from_fleet_subtask({"id": "f1", "description": "do things",
                                    "depends_on": ["f0"], "required_domain": "engineering"})
        assert fleet.source_system == "fleet"

        legacy = from_goal_subtask({"id": "g1", "title": "Outreach", "status": "PENDING"})
        assert legacy.status == "PENDING"

        goal = from_goal_objective({"id": "go1", "title": "Grow", "status": "active",
                                    "criteria": [{"type": "entity_exists"}]})
        assert goal.kind == NodeKind.GOAL

    def test_relation_triple(self):
        from core.ontology.vocabulary import (
            NodeKind, RelationName, VocabularyNode, relation,
        )
        goal = VocabularyNode(NodeKind.GOAL, "Grow revenue")
        task = VocabularyNode(NodeKind.TASK, "Run outreach")
        rel = relation(goal, RelationName.DECOMPOSES_INTO, task)
        assert rel["predicate"] == "DECOMPOSES_INTO"
        assert rel["subject"]["kind"] == "Goal" and rel["object"]["kind"] == "Task"


# ---------------------------------------------------------------------------
# Action contracts (B4)
# ---------------------------------------------------------------------------

class TestActionContracts:
    def test_preconditions(self):
        from core.action_registry import ActionDefinition

        async def handler(args, context):
            return {"ok": True}

        action = ActionDefinition(
            "test.contracted", handler,
            preconditions=[
                {"fact": "workspace_id", "op": "exists"},
                {"fact": "user.role", "op": "eq", "value": "admin"},
            ],
            effects=[{"effect": "graph_updated"}],
        )
        failures = action.check_preconditions({"workspace_id": "ws1", "user": {"role": "member"}})
        assert len(failures) == 1 and failures[0]["precondition"]["fact"] == "user.role"
        assert not action.check_preconditions({"workspace_id": "ws1", "user": {"role": "admin"}})
        assert action.effects == [{"effect": "graph_updated"}]

    def test_registry_accepts_contracts(self):
        from core.action_registry import action_registry

        async def handler(args, context):
            return {}

        action_registry.register(
            "test.contract.registered", handler,
            preconditions=[{"fact": "x", "op": "true"}],
            effects=[{"effect": "tested"}],
        )
        registered = action_registry.get_action("test.contract.registered")
        assert registered.preconditions and registered.effects

    def test_knowledge_and_goal_actions_registered(self):
        from core.action_registry import action_registry
        for name in ("knowledge.query", "goals.create", "goals.evaluate",
                     "goals.decompose", "ontology.inspect"):
            assert action_registry.get_action(name) is not None, name


# ---------------------------------------------------------------------------
# Objective loop wiring (B2 production injector)
# ---------------------------------------------------------------------------

class TestObjectiveLoop:
    def test_objective_from_context_structured_criteria(self, monkeypatch, db_session_factory):
        import core.database as database_module
        monkeypatch.setattr(database_module, "get_db_session", db_session_factory)
        _seed_graph_nodes(db_session_factory)

        from core.agent_objective import objective_from_context
        objective = objective_from_context({
            "objective_goal": "Alice must exist in the graph",
            "objective_criteria": [{"type": "entity_exists", "name": "Alice"}],
            "workspace_id": "ws-test",
        })
        assert objective is not None
        assert objective.is_satisfied({"final_answer": "x"})

        unsatisfiable = objective_from_context({
            "objective_goal": "Ghost must exist",
            "objective_criteria": [{"type": "entity_exists", "name": "Ghost"}],
            "workspace_id": "ws-test",
        })
        assert unsatisfiable is not None and not unsatisfiable.is_satisfied({})

    def test_objective_from_context_goal_id(self, monkeypatch, db_session_factory):
        import core.database as database_module
        monkeypatch.setattr(database_module, "get_db_session", db_session_factory)
        _seed_graph_nodes(db_session_factory)

        from core.agent_objective import objective_from_context
        from core.goals.goal_service import GoalService
        goal = GoalService(workspace_id="ws-test").create_goal(
            title="From persisted goal",
            criteria=[{"type": "entity_exists", "name": "Alice"}],
        )
        objective = objective_from_context({"goal_id": goal["id"], "workspace_id": "ws-test"})
        assert objective is not None
        assert objective.constraints.get("goal_id") == goal["id"]
        assert objective.is_satisfied({})

    def test_no_objective_still_none(self):
        from core.agent_objective import objective_from_context
        assert objective_from_context({"objective_goal": "no predicate"}) is None
