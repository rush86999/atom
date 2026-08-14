# -*- coding: utf-8 -*-
"""Coverage wave 103 — core/orchestration/workflow_composer.py to 100%.

Complements tests/test_enhanced_orchestration.py (which exercised the happy
paths) with the error/edge branches: empty primitive list, SEQUENCE/CHOICE/
LOOP child wiring, PARALLEL re-rooting, duration estimation (parallel max /
sequence sum / loop multiply / per-node duration_ms override), validation
(depth exceed, cycle detect incl. cycle-report path + visited-skip, parallel
<2 children, loop without condition), decompose (no-root and pre-order),
get_statistics, and the get_workflow_composer factory (fresh + cached).
Zero LLM/network.
"""
import pytest

from core.orchestration.workflow_composer import (
    ComposedWorkflow,
    ComposerConfig,
    CompositionNode,
    CompositionPrimitive,
    CompositionStrategy,
    get_workflow_composer,
    WorkflowComposer,
)


def _cfg(**kwargs):
    return ComposerConfig(**kwargs)


class TestCompose:
    def test_empty_primitives_raise(self):
        composer = WorkflowComposer()
        with pytest.raises(ValueError, match="No primitives"):
            composer.compose([])

    def test_single_primitive(self):
        composer = WorkflowComposer()
        wf = composer.compose([(CompositionPrimitive.SEQUENCE, {})], name="one")
        assert wf.root.primitive == CompositionPrimitive.SEQUENCE
        assert wf.node_count == 1
        assert wf.validated is True
        assert wf.validation_errors == []
        assert wf.name == "one"
        assert wf.composer_type == CompositionStrategy.DEPENDENCY_AWARE
        assert wf.estimated_duration_ms == 1000.0

    def test_auto_workflow_id_generated(self):
        composer = WorkflowComposer()
        wf = composer.compose([(CompositionPrimitive.SEQUENCE, {})])
        assert wf.workflow_id.startswith("comp_wf_")

    def test_explicit_workflow_id_respected(self):
        composer = WorkflowComposer()
        wf = composer.compose([(CompositionPrimitive.SEQUENCE, {})], workflow_id="my-wf")
        assert wf.workflow_id == "my-wf"

    def test_node_count_counts_tree(self):
        composer = WorkflowComposer()
        wf = composer.compose(
            [
                (CompositionPrimitive.SEQUENCE, {}),
                (CompositionPrimitive.SEQUENCE, {}),
                (CompositionPrimitive.SEQUENCE, {}),
            ]
        )
        # root + 2 appended children
        assert wf.node_count == 3

    def test_validation_disabled_skips(self):
        composer = WorkflowComposer(_cfg(validate_composition=False))
        wf = composer.compose([(CompositionPrimitive.LOOP, {})])
        assert wf.validated is False
        assert wf.validation_errors == []

    def test_validation_error_reported(self):
        # compose() builds depth-0 trees; max_depth=-1 trips the depth check
        composer = WorkflowComposer(_cfg(max_depth=-1))
        wf = composer.compose([(CompositionPrimitive.SEQUENCE, {})])
        assert wf.validated is False
        assert any("depth" in e for e in wf.validation_errors)


class TestBuildCompositionTree:
    def test_sequence_appends_to_root(self):
        composer = WorkflowComposer()
        root = composer._build_composition_tree(
            [(CompositionPrimitive.SEQUENCE, {}), (CompositionPrimitive.SEQUENCE, {"x": 1})],
            CompositionStrategy.SEQUENTIAL,
        )
        assert len(root.children) == 1
        assert root.children[0].config == {"x": 1}
        assert root.children[0].node_id.startswith("node_1_")

    def test_choice_appends_to_root(self):
        composer = WorkflowComposer()
        root = composer._build_composition_tree(
            [(CompositionPrimitive.SEQUENCE, {}), (CompositionPrimitive.CHOICE, {"branches": {}})],
            CompositionStrategy.SEQUENTIAL,
        )
        assert root.primitive == CompositionPrimitive.SEQUENCE
        assert len(root.children) == 1
        assert root.children[0].primitive == CompositionPrimitive.CHOICE

    def test_loop_appends_to_root(self):
        composer = WorkflowComposer()
        root = composer._build_composition_tree(
            [(CompositionPrimitive.SEQUENCE, {}), (CompositionPrimitive.LOOP, {"iterations": 4})],
            CompositionStrategy.SEQUENTIAL,
        )
        assert len(root.children) == 1
        assert root.children[0].primitive == CompositionPrimitive.LOOP

    def test_parallel_re_roots(self):
        composer = WorkflowComposer()
        root = composer._build_composition_tree(
            [
                (CompositionPrimitive.SEQUENCE, {}),
                (CompositionPrimitive.PARALLEL, {}),
                (CompositionPrimitive.SEQUENCE, {}),
            ],
            CompositionStrategy.PARALLEL_FIRST,
        )
        assert root.primitive == CompositionPrimitive.PARALLEL
        # First PARALLEL absorbs the current root + new node; the trailing
        # SEQUENCE then appends to the parallel root
        assert len(root.children) == 3
        assert root.node_id.startswith("par_")


class TestEstimateDuration:
    def test_parallel_takes_max(self):
        composer = WorkflowComposer()
        root = CompositionNode(
            primitive=CompositionPrimitive.PARALLEL,
            children=[
                CompositionNode(primitive=CompositionPrimitive.SEQUENCE),
                CompositionNode(primitive=CompositionPrimitive.SEQUENCE),
            ],
        )
        assert composer._estimate_duration(root) == 1000.0  # max(1000,1000)

    def test_parallel_empty_children_base(self):
        composer = WorkflowComposer()
        root = CompositionNode(primitive=CompositionPrimitive.PARALLEL)
        assert composer._estimate_duration(root) == 1000.0

    def test_sequence_sums_children(self):
        composer = WorkflowComposer()
        root = CompositionNode(
            primitive=CompositionPrimitive.SEQUENCE,
            children=[
                CompositionNode(primitive=CompositionPrimitive.SEQUENCE),
                CompositionNode(primitive=CompositionPrimitive.SEQUENCE),
            ],
        )
        assert composer._estimate_duration(root) == 2000.0

    def test_loop_multiplies_children(self):
        composer = WorkflowComposer()
        root = CompositionNode(
            primitive=CompositionPrimitive.LOOP,
            config={"iterations": 5},
            children=[CompositionNode(primitive=CompositionPrimitive.SEQUENCE)],
        )
        assert composer._estimate_duration(root) == 5000.0

    def test_duration_ms_override(self):
        composer = WorkflowComposer()
        root = CompositionNode(
            primitive=CompositionPrimitive.SEQUENCE,
            config={"duration_ms": 42.0},
        )
        assert composer._estimate_duration(root) == 42.0
        assert root.estimated_duration_ms == 42.0

    def test_duration_stored_on_node(self):
        composer = WorkflowComposer()
        root = CompositionNode(primitive=CompositionPrimitive.SEQUENCE)
        composer._estimate_duration(root)
        assert root.estimated_duration_ms == 1000.0


class TestValidation:
    def test_depth_exceeded_reported(self):
        composer = WorkflowComposer(_cfg(max_depth=1))
        root = CompositionNode(depth=0, children=[CompositionNode(depth=1, children=[CompositionNode(depth=2)])])
        valid, errors = composer._validate_composition(root)
        assert valid is False
        assert any("depth" in e for e in errors)

    def test_cycle_detected(self):
        composer = WorkflowComposer()
        root = CompositionNode(node_id="a", children=[CompositionNode(node_id="b", children=[])])
        root.children[0].children.append(root)  # b -> a cycle
        valid, errors = composer._validate_composition(root)
        assert valid is False
        assert any("Cyclic" in e for e in errors)

    def test_parallel_requires_two_children(self):
        composer = WorkflowComposer()
        root = CompositionNode(node_id="p", primitive=CompositionPrimitive.PARALLEL, children=[CompositionNode(node_id="c")])
        valid, errors = composer._validate_composition(root)
        assert valid is False
        assert any("at least 2 children" in e for e in errors)

    def test_loop_requires_condition(self):
        composer = WorkflowComposer()
        root = CompositionNode(node_id="l", primitive=CompositionPrimitive.LOOP)
        valid, errors = composer._validate_composition(root)
        assert valid is False
        assert any("requires condition" in e for e in errors)

    def test_loop_with_condition_valid(self):
        composer = WorkflowComposer()
        root = CompositionNode(node_id="l", primitive=CompositionPrimitive.LOOP, loop_condition="i < 10")
        valid, errors = composer._validate_composition(root)
        assert valid is True
        assert errors == []

    def test_get_max_depth_bfs(self):
        composer = WorkflowComposer()
        root = CompositionNode(depth=0, children=[CompositionNode(depth=5, children=[CompositionNode(depth=7)])])
        assert composer._get_max_depth(root) == 7

    def test_detect_cycles_reports_cycle_string(self):
        composer = WorkflowComposer()
        a = CompositionNode(node_id="a")
        b = CompositionNode(node_id="b")
        a.children.append(b)
        b.children.append(a)
        cycles = composer._detect_cycles(a)
        assert cycles == ["a -> b -> a"]

    def test_detect_cycles_visited_skip(self):
        composer = WorkflowComposer()
        shared = CompositionNode(node_id="shared")
        root = CompositionNode(node_id="root", children=[shared, shared])
        cycles = composer._detect_cycles(root)
        assert cycles == []

    def test_detect_cycles_no_cycle(self):
        composer = WorkflowComposer()
        root = CompositionNode(node_id="a", children=[CompositionNode(node_id="b")])
        assert composer._detect_cycles(root) == []

    def test_validate_primitives_recursion(self):
        composer = WorkflowComposer()
        errors = []
        inner = CompositionNode(node_id="inner", primitive=CompositionPrimitive.PARALLEL, children=[CompositionNode(node_id="only")])
        root = CompositionNode(node_id="outer", primitive=CompositionPrimitive.SEQUENCE, children=[inner])
        composer._validate_primitives(root, errors)
        assert any("at least 2 children" in e for e in errors)


class TestDecompose:
    def test_no_root_returns_empty(self):
        composer = WorkflowComposer()
        assert composer.decompose(ComposedWorkflow()) == []

    def test_pre_order_extraction(self):
        composer = WorkflowComposer()
        child = CompositionNode(primitive=CompositionPrimitive.SEQUENCE, config={"a": 1})
        root = CompositionNode(primitive=CompositionPrimitive.SEQUENCE, config={"b": 2}, children=[child])
        wf = ComposedWorkflow(root=root)
        prims = composer.decompose(wf)
        assert prims == [
            (CompositionPrimitive.SEQUENCE, {"b": 2}),
            (CompositionPrimitive.SEQUENCE, {"a": 1}),
        ]


class TestMisc:
    def test_get_statistics(self):
        composer = WorkflowComposer(_cfg(max_depth=7, max_parallel_branches=9))
        stats = composer.get_statistics()
        assert stats["config"]["max_depth"] == 7
        assert stats["config"]["max_parallel_branches"] == 9
        assert stats["validation_enabled"] is True
        assert stats["optimization_enabled"] is True

    def test_composer_default_config(self):
        composer = WorkflowComposer()
        assert composer.config.max_depth == 10
        assert composer.config.validate_composition is True

    def test_factory_creates_and_caches(self):
        # Reset module singleton state
        import core.orchestration.workflow_composer as wc_mod
        wc_mod._composer_instance = None
        try:
            c1 = get_workflow_composer()
            c2 = get_workflow_composer()
            assert c1 is c2
            # config only honored on first creation
            wc_mod._composer_instance = None
            c3 = get_workflow_composer(_cfg(max_depth=3))
            assert c3.config.max_depth == 3
        finally:
            wc_mod._composer_instance = None
