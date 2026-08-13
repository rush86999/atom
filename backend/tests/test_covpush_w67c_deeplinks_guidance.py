"""Coverage wave 67c — core/deeplinks, core/safe_evaluator,
core/error_guidance_engine, core/monitoring (standalone, zero LLM spend,
no real DB, no network).

- deeplinks: parse edge cases (exception str/repr, urlparse/parse_qs
  failures, short path, empty resource id, invalid JSON params, invalid
  scheme/resource-type, security rejection), all four executors with a
  fully-mocked DB session + governance service (agent not-found / inactive /
  governance-blocked / success ±audit / commit failure; workflow success +
  audit; canvas update success/failure + unsupported action; tool not-found /
  success), router dispatch for all resource types + parse-exception,
  unsupported-type and unexpected-exception paths, generate_deep_link
  validation + JSON params.
- safe_evaluator: full standalone suite — literals/operators/comparisons/
  containers/ternary/subscript, safe aliases, blocked node types (attribute,
  lambda, imports, comprehensions, genexp, starred, named-expr, calls),
  whitelisted call surface incl. pow guards, constant-fold internals (Add/
  Sub/Mult/Pow/UnaryOp/div-failure), execution-time DoS guards (_safe_pow
  negative/overflow/too-large/modular), exception plumbing of both eval
  wrappers, direct visitor rejection of ast.Import/ast.ImportFrom.
- error_guidance_engine: categorize (code + message based, default),
  suggested resolution (unknown/no-history/most-successful/mismatch),
  track_resolution (disabled/success/rollback), historical + success-rate +
  statistics, suggest_fixes_from_history (template/unknown/historical/
  exception), get_error_fix_suggestions, present_error (broadcast, disabled,
  exception), audit creation, module helper — all DB access mocked.
- monitoring: structlog processors/config, RequestContext bind/restore,
  every metric tracker, deployment/smoke context managers (success+failure),
  rollback/canary/prometheus-query helpers, metrics-server init
  (success/OSError) — real prometheus_client, patched module objects.
"""
import ast
import time
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from core.deeplinks import (
    DEEPLINK_ENABLED,
    DeepLink,
    DeepLinkParseException,
    DeepLinkSecurityException,
    execute_agent_deep_link,
    execute_canvas_deep_link,
    execute_deep_link,
    execute_tool_deep_link,
    execute_workflow_deep_link,
    generate_deep_link,
    parse_deep_link,
)
from core.error_guidance_engine import ErrorGuidanceEngine, get_error_guidance_engine
from core.safe_evaluator import SafeEvalError, SafeEvaluator, safe_eval, safe_eval_with_math


# ============================================================================
# core/deeplinks.py — parse edge cases
# ============================================================================


class _FakeQuery:
    """Minimal query double: filter/order_by/limit are no-ops; first/all
    return the injected rows. Enough for the deep-link executors and the
    error-guidance engine, both of which only chain filters."""

    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def limit(self, n):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class TestDeepLinkParseExtras:
    def test_parse_exception_str_with_and_without_url(self):
        with_url = DeepLinkParseException("bad link", url="atom://agent/a1")
        assert str(with_url) == "bad link (URL: atom://agent/a1)"
        assert with_url.url == "atom://agent/a1"
        assert with_url.details == {}
        without = DeepLinkParseException("bad link")
        assert str(without) == "bad link"
        with_details = DeepLinkParseException("bad", url="u", details={"k": 1})
        assert with_details.details == {"k": 1}

    def test_security_exception_str_combinations(self):
        full = DeepLinkSecurityException("denied", url="atom://agent/a1", security_issue="bad id")
        assert str(full) == "denied (URL: atom://agent/a1) (Issue: bad id)"
        url_only = DeepLinkSecurityException("denied", url="atom://agent/a1")
        assert str(url_only) == "denied (URL: atom://agent/a1)"
        issue_only = DeepLinkSecurityException("denied", security_issue="bad id")
        assert str(issue_only) == "denied (Issue: bad id)"
        plain = DeepLinkSecurityException("denied")
        assert str(plain) == "denied"

    def test_deeplink_repr(self):
        link = DeepLink("atom", "agent", "a1", {"message": "hi"}, "atom://agent/a1")
        assert repr(link) == "<DeepLink agent:a1 params={'message': 'hi'}>"

    def test_disabled_flag_raises_security_exception(self, monkeypatch):
        assert DEEPLINK_ENABLED
        monkeypatch.setattr("core.deeplinks.DEEPLINK_ENABLED", False)
        with pytest.raises(DeepLinkSecurityException, match="disabled"):
            parse_deep_link("atom://agent/a1")

    def test_non_string_url_rejected(self):
        with pytest.raises(DeepLinkParseException, match="non-empty string"):
            parse_deep_link(123)  # type: ignore[arg-type]

    def test_urlparse_failure_reported(self, monkeypatch):
        def boom(url):
            raise ValueError("unparseable")

        monkeypatch.setattr("core.deeplinks.urlparse", boom)
        with pytest.raises(DeepLinkParseException, match="Invalid URL format"):
            parse_deep_link("atom://agent/a1")

    def test_invalid_scheme_rejected(self):
        with pytest.raises(DeepLinkParseException, match="Invalid scheme"):
            parse_deep_link("http://example.com/x")

    def test_invalid_resource_type_rejected(self):
        with pytest.raises(DeepLinkParseException, match="Invalid resource type"):
            parse_deep_link("atom://billing/invoice-1")

    def test_invalid_resource_id_security(self):
        with pytest.raises(DeepLinkSecurityException, match="resource ID format"):
            parse_deep_link("atom://agent/../..%2Fetc")

    def test_short_path_rejected(self):
        with pytest.raises(DeepLinkParseException, match="Invalid path format"):
            parse_deep_link("atom://")
        with pytest.raises(DeepLinkParseException, match="Invalid path format"):
            parse_deep_link("atom:agent")

    def test_empty_resource_id_rejected(self):
        with pytest.raises(DeepLinkParseException, match="cannot be empty"):
            parse_deep_link("atom://agent/")

    def test_invalid_json_params_rejected(self):
        with pytest.raises(DeepLinkParseException, match="Invalid JSON in params"):
            parse_deep_link("atom://tool/chart?params={oops")

    def test_parse_qs_failure_reported(self, monkeypatch):
        def boom(qs, keep_blank_values=False):
            raise ValueError("bad qs")

        monkeypatch.setattr("core.deeplinks.parse_qs", boom)
        with pytest.raises(DeepLinkParseException, match="Failed to parse query"):
            parse_deep_link("atom://agent/a1?message=hi")

    def test_multi_value_params_and_blank_values(self):
        link = parse_deep_link("atom://workflow/w1?a=1&a=2&b=")
        assert link.parameters["a"] == ["1", "2"]
        assert link.parameters["b"] == ""


# ============================================================================
# core/deeplinks.py — executors (mocked DB, mocked governance, no network)
# ============================================================================


class TestExecuteAgentDeepLink:
    def _link(self, resource_id="a1", **params):
        return DeepLink("atom", "agent", resource_id, params, f"atom://agent/{resource_id}")

    @staticmethod
    def _governance(allowed, reason=""):
        fake = Mock()
        fake.can_perform_action.return_value = {"allowed": allowed, "reason": reason}
        return fake

    @pytest.mark.asyncio
    async def test_wrong_resource_type_raises(self):
        db = MagicMock()
        link = DeepLink("atom", "workflow", "w1", {}, "atom://workflow/w1")
        with pytest.raises(ValueError, match="resource_type='agent'"):
            await execute_agent_deep_link(link, "u1", db)

    @pytest.mark.asyncio
    async def test_agent_not_found(self):
        db = MagicMock()
        db.query.return_value = _FakeQuery([])
        result = await execute_agent_deep_link(self._link("missing"), "u1", db)
        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_agent_inactive(self):
        db = MagicMock()
        agent = SimpleNamespace(id="a1", name="A", status="DISABLED")
        db.query.return_value = _FakeQuery([agent])
        result = await execute_agent_deep_link(self._link(), "u1", db)
        assert result["success"] is False
        assert "not active" in result["error"]

    @pytest.mark.asyncio
    async def test_governance_blocked(self):
        db = MagicMock()
        agent = SimpleNamespace(id="a1", name="A", status="AUTONOMOUS")
        db.query.return_value = _FakeQuery([agent])
        with patch(
            "core.deeplinks.AgentGovernanceService",
            return_value=self._governance(False, "insufficient maturity"),
        ):
            result = await execute_agent_deep_link(self._link(), "u1", db)
        assert result["success"] is False
        assert "insufficient maturity" in result["error"]
        db.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_success_with_audit(self, monkeypatch):
        monkeypatch.setattr("core.deeplinks.DEEPLINK_AUDIT_ENABLED", True)
        db = MagicMock()
        agent = SimpleNamespace(id="a1", name="Agent One", status="AUTONOMOUS")
        db.query.return_value = _FakeQuery([agent])
        with patch(
            "core.deeplinks.AgentGovernanceService",
            return_value=self._governance(True),
        ):
            result = await execute_agent_deep_link(
                self._link(message="Analyze sales", session="sess-1"),
                "u1",
                db,
                source="browser",
            )
        assert result["success"] is True
        assert result["agent_id"] == "a1"
        assert result["agent_name"] == "Agent One"
        assert result["message"] == "Analyze sales"
        assert result["session_id"] == "sess-1"
        assert result["source"] == "browser"
        assert result["execution_id"]
        assert db.commit.call_count == 2  # execution + audit
        db.refresh.assert_called_once()
        execution = db.add.call_args_list[0][0][0]
        assert execution.triggered_by == "deeplink"
        assert execution.workspace_id == "default"
        assert "Analyze sales" in execution.input_summary

    @pytest.mark.asyncio
    async def test_success_without_audit(self, monkeypatch):
        monkeypatch.setattr("core.deeplinks.DEEPLINK_AUDIT_ENABLED", False)
        db = MagicMock()
        agent = SimpleNamespace(id="a1", name="A", status="INTERN")
        db.query.return_value = _FakeQuery([agent])
        with patch(
            "core.deeplinks.AgentGovernanceService",
            return_value=self._governance(True),
        ):
            result = await execute_agent_deep_link(self._link(message="hi"), "u1", db)
        assert result["success"] is True
        assert db.commit.call_count == 1
        assert db.add.call_count == 1

    @pytest.mark.asyncio
    async def test_commit_failure_returns_error(self, monkeypatch):
        monkeypatch.setattr("core.deeplinks.DEEPLINK_AUDIT_ENABLED", False)
        db = MagicMock()
        agent = SimpleNamespace(id="a1", name="A", status="AUTONOMOUS")
        db.query.return_value = _FakeQuery([agent])
        db.commit.side_effect = RuntimeError("db down")
        with patch(
            "core.deeplinks.AgentGovernanceService",
            return_value=self._governance(True),
        ):
            result = await execute_agent_deep_link(self._link(), "u1", db)
        assert result["success"] is False
        assert result["error"] == "Deep link agent execution failed"


class TestExecuteWorkflowDeepLink:
    @pytest.mark.asyncio
    async def test_wrong_resource_type_raises(self):
        db = MagicMock()
        link = DeepLink("atom", "agent", "a1", {}, "atom://agent/a1")
        with pytest.raises(ValueError, match="resource_type='workflow'"):
            await execute_workflow_deep_link(link, "u1", db)

    @pytest.mark.asyncio
    async def test_not_found(self):
        db = MagicMock()
        db.query.return_value = _FakeQuery([])
        link = DeepLink("atom", "workflow", "wf-missing", {}, "atom://workflow/wf-missing")
        result = await execute_workflow_deep_link(link, "u1", db)
        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_success_with_audit(self, monkeypatch):
        monkeypatch.setattr("core.deeplinks.DEEPLINK_AUDIT_ENABLED", True)
        db = MagicMock()
        workflow = SimpleNamespace(id="wf-1")
        db.query.return_value = _FakeQuery([workflow])
        link = DeepLink(
            "atom", "workflow", "wf-1",
            {"action": "start", "params": {"force": True}},
            "atom://workflow/wf-1?action=start",
        )
        result = await execute_workflow_deep_link(link, "u1", db, source="slack")
        assert result["success"] is True
        assert result["workflow_id"] == "wf-1"
        assert result["action"] == "start"
        assert result["params"] == {"force": True}
        assert result["source"] == "slack"
        assert db.add.call_count == 1
        assert db.commit.call_count == 1
        audit = db.add.call_args_list[0][0][0]
        assert audit.resource_type == "workflow"
        assert audit.status == "success"


class TestExecuteCanvasDeepLink:
    @pytest.mark.asyncio
    async def test_wrong_resource_type_raises(self):
        db = MagicMock()
        link = DeepLink("atom", "tool", "t1", {}, "atom://tool/t1")
        with pytest.raises(ValueError, match="resource_type='canvas'"):
            await execute_canvas_deep_link(link, "u1", db)

    @pytest.mark.asyncio
    async def test_update_success(self, monkeypatch):
        monkeypatch.setattr("core.deeplinks.DEEPLINK_AUDIT_ENABLED", True)
        db = MagicMock()
        link = DeepLink(
            "atom", "canvas", "c1",
            {"action": "update", "params": {"title": "New"}},
            "atom://canvas/c1?action=update",
        )
        with patch(
            "tools.canvas_tool.update_canvas",
            new=AsyncMock(return_value={"success": True, "canvas_id": "c1"}),
        ):
            result = await execute_canvas_deep_link(link, "u1", db)
        assert result["success"] is True
        assert db.commit.call_count == 1
        audit = db.add.call_args_list[0][0][0]
        assert audit.status == "success"
        assert audit.action == "update"

    @pytest.mark.asyncio
    async def test_update_failure_audits_failed(self, monkeypatch):
        monkeypatch.setattr("core.deeplinks.DEEPLINK_AUDIT_ENABLED", True)
        db = MagicMock()
        link = DeepLink(
            "atom", "canvas", "c1",
            {"action": "update", "params": {}},
            "atom://canvas/c1?action=update",
        )
        with patch(
            "tools.canvas_tool.update_canvas",
            new=AsyncMock(return_value={"success": False, "error": "canvas gone"}),
        ):
            result = await execute_canvas_deep_link(link, "u1", db)
        assert result["success"] is False
        audit = db.add.call_args_list[0][0][0]
        assert audit.status == "failed"

    @pytest.mark.asyncio
    async def test_unsupported_action(self):
        db = MagicMock()
        link = DeepLink(
            "atom", "canvas", "c1",
            {"action": "present", "params": {}},
            "atom://canvas/c1?action=present",
        )
        result = await execute_canvas_deep_link(link, "u1", db)
        assert result["success"] is False
        assert "Unsupported canvas action: present" in result["error"]


class TestExecuteToolDeepLink:
    @pytest.mark.asyncio
    async def test_wrong_resource_type_raises(self):
        db = MagicMock()
        link = DeepLink("atom", "agent", "a1", {}, "atom://agent/a1")
        with pytest.raises(ValueError, match="resource_type='tool'"):
            await execute_tool_deep_link(link, "u1", db)

    @pytest.mark.asyncio
    async def test_tool_not_found(self):
        db = MagicMock()
        registry = Mock()
        registry.get.return_value = None
        with patch("tools.registry.get_tool_registry", return_value=registry):
            link = DeepLink("atom", "tool", "ghost_tool", {}, "atom://tool/ghost_tool")
            result = await execute_tool_deep_link(link, "u1", db)
        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_success_with_audit(self, monkeypatch):
        monkeypatch.setattr("core.deeplinks.DEEPLINK_AUDIT_ENABLED", True)
        db = MagicMock()
        metadata = SimpleNamespace(to_dict=lambda: {"name": "present_chart", "category": "canvas"})
        registry = Mock()
        registry.get.return_value = metadata
        with patch("tools.registry.get_tool_registry", return_value=registry):
            link = DeepLink(
                "atom", "tool", "present_chart",
                {"params": {"data": [1, 2]}},
                "atom://tool/present_chart",
            )
            result = await execute_tool_deep_link(link, "u1", db, source="browser")
        assert result["success"] is True
        assert result["tool_name"] == "present_chart"
        assert result["tool_metadata"] == {"name": "present_chart", "category": "canvas"}
        assert result["source"] == "browser"
        audit = db.add.call_args_list[0][0][0]
        assert audit.resource_type == "tool"
        assert audit.status == "success"


# ============================================================================
# core/deeplinks.py — router dispatch
# ============================================================================


class TestExecuteDeepLinkRouter:
    def _agent_governance(self):
        fake = Mock()
        fake.can_perform_action.return_value = {"allowed": True, "reason": ""}
        return fake

    @pytest.mark.asyncio
    async def test_routes_agent(self, monkeypatch):
        monkeypatch.setattr("core.deeplinks.DEEPLINK_AUDIT_ENABLED", False)
        db = MagicMock()
        agent = SimpleNamespace(id="a1", name="A", status="AUTONOMOUS")
        db.query.return_value = _FakeQuery([agent])
        with patch("core.deeplinks.AgentGovernanceService", return_value=self._agent_governance()):
            result = await execute_deep_link("atom://agent/a1?message=hi", "u1", db)
        assert result["success"] is True
        assert result["agent_id"] == "a1"

    @pytest.mark.asyncio
    async def test_routes_workflow(self, monkeypatch):
        monkeypatch.setattr("core.deeplinks.DEEPLINK_AUDIT_ENABLED", False)
        db = MagicMock()
        workflow = SimpleNamespace(id="wf-1")
        db.query.return_value = _FakeQuery([workflow])
        result = await execute_deep_link("atom://workflow/wf-1?action=start", "u1", db)
        assert result["success"] is True
        assert result["workflow_id"] == "wf-1"

    @pytest.mark.asyncio
    async def test_routes_canvas(self, monkeypatch):
        monkeypatch.setattr("core.deeplinks.DEEPLINK_AUDIT_ENABLED", False)
        db = MagicMock()
        with patch(
            "tools.canvas_tool.update_canvas",
            new=AsyncMock(return_value={"success": True, "canvas_id": "c1"}),
        ):
            result = await execute_deep_link("atom://canvas/c1?action=update", "u1", db)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_routes_tool(self, monkeypatch):
        monkeypatch.setattr("core.deeplinks.DEEPLINK_AUDIT_ENABLED", False)
        db = MagicMock()
        registry = Mock()
        registry.get.return_value = SimpleNamespace(to_dict=lambda: {"name": "t"})
        with patch("tools.registry.get_tool_registry", return_value=registry):
            result = await execute_deep_link("atom://tool/present_chart", "u1", db)
        assert result["success"] is True
        assert result["tool_name"] == "present_chart"

    @pytest.mark.asyncio
    async def test_parse_exception_returns_invalid_url_error(self):
        db = MagicMock()
        result = await execute_deep_link("http://example.com/x", "u1", db)
        assert result["success"] is False
        assert result["error"] == "Invalid deep link URL"

    @pytest.mark.asyncio
    async def test_unsupported_resource_type_after_parse(self, monkeypatch):
        db = MagicMock()
        link = DeepLink("atom", "billing", "b1", {}, "atom://billing/b1")
        monkeypatch.setattr("core.deeplinks.parse_deep_link", lambda url: link)
        result = await execute_deep_link("atom://billing/b1", "u1", db)
        assert result["success"] is False
        assert "Unsupported resource type: billing" in result["error"]

    @pytest.mark.asyncio
    async def test_unexpected_error_returns_failure(self, monkeypatch):
        db = MagicMock()

        def boom(url):
            raise RuntimeError("kaboom")

        monkeypatch.setattr("core.deeplinks.parse_deep_link", boom)
        result = await execute_deep_link("atom://agent/a1", "u1", db)
        assert result["success"] is False
        assert result["error"] == "Deep link execution failed"


# ============================================================================
# core/deeplinks.py — generation gaps
# ============================================================================


class TestGenerateDeepLinkGaps:
    def test_invalid_resource_type(self):
        with pytest.raises(ValueError, match="Invalid resource_type"):
            generate_deep_link("billing", "b1")

    @pytest.mark.parametrize("bad_id", ["", "has space", "a/b", 123, None])
    def test_invalid_resource_id(self, bad_id):
        with pytest.raises(ValueError, match="Invalid resource_id"):
            generate_deep_link("agent", bad_id)  # type: ignore[arg-type]

    def test_params_dict_serialized_to_json(self):
        url = generate_deep_link("tool", "chart", params={"data": [1, 2]}, theme="dark")
        link = parse_deep_link(url)
        assert link.parameters["params"] == {"data": [1, 2]}
        assert link.parameters["theme"] == "dark"

    def test_no_params_no_query_string(self):
        assert generate_deep_link("canvas", "c1") == "atom://canvas/c1"


# ============================================================================
# core/safe_evaluator.py — full standalone suite
# ============================================================================


class TestSafeEvaluatorExpressions:
    def test_literals_and_arithmetic(self):
        assert safe_eval("42") == 42
        assert safe_eval("3.5") == 3.5
        assert safe_eval("'hello'") == "hello"
        assert safe_eval("b'bytes'") == b"bytes"
        assert safe_eval("True") is True
        assert safe_eval("False") is False
        assert safe_eval("None") is None

    def test_json_aliases(self):
        assert safe_eval("true") is True
        assert safe_eval("false") is False
        assert safe_eval("null") is None

    def test_unary_operators(self):
        assert safe_eval("+5") == 5
        assert safe_eval("-5") == -5
        assert safe_eval("not False") is True
        assert safe_eval("~0") == -1
        assert safe_eval("-x", {"x": 3}) == -3

    def test_binary_operators(self):
        assert safe_eval("1 + 2 * 3") == 7
        assert safe_eval("10 - 4") == 6
        assert safe_eval("7 // 2") == 3
        assert safe_eval("7 % 3") == 1
        assert safe_eval("1 << 3") == 8
        assert safe_eval("16 >> 2") == 4
        assert safe_eval("5 & 3") == 1
        assert safe_eval("5 | 2") == 7
        assert safe_eval("5 ^ 1") == 4
        assert safe_eval("(1 + 2) * (3 + 4)") == 21

    def test_comparisons(self):
        assert safe_eval("1 < 2") is True
        assert safe_eval("2 <= 2") is True
        assert safe_eval("3 > 4") is False
        assert safe_eval("4 >= 4") is True
        assert safe_eval("1 == 1") is True
        assert safe_eval("1 != 2") is True
        assert safe_eval("'a' in ['a']") is True
        assert safe_eval("'b' not in ['a']") is True
        assert safe_eval("1 is 1") is True
        assert safe_eval("None is not 0") is True

    def test_boolean_ops_and_ternary(self):
        assert safe_eval("True and False") is False
        assert safe_eval("True or False") is True
        assert safe_eval("x if y else z", {"x": 1, "y": False, "z": 3}) == 3

    def test_containers(self):
        assert safe_eval("[1, 2][0]") == 1
        assert safe_eval("{'a': 1}['a']") == 1
        assert safe_eval("(1, 2)[1]") == 2
        assert safe_eval("{1, 2} | {3}") == {1, 2, 3}
        assert safe_eval("'abc'[1:]") == "bc"
        assert safe_eval("'abcdef'[1:4]") == "bcd"

    def test_context_variables(self):
        assert safe_eval("x + y", {"x": 1, "y": 2}) == 3
        assert safe_eval("d['k']", {"d": {"k": 9}}) == 9
        assert safe_eval("l[2]", {"l": [5, 6, 7]}) == 7


class TestSafeEvaluatorBlocked:
    @pytest.mark.parametrize("expr,msg", [
        ("obj.__class__", "Attribute access"),
        ("lambda: 1", "Lambda"),
        ("[x for x in [1]]", "List comprehensions"),
        ("{k: v for k, v in [('a', 1)]}", "Dict comprehensions"),
        ("{x for x in [1]}", "Set comprehensions"),
        ("(x for x in [1])", "Generator expressions"),
        ("[*[1]]", "Unpacking"),
        ("(x := 1)", "NamedExpr"),
    ])
    def test_dangerous_nodes_rejected(self, expr, msg):
        with pytest.raises(SafeEvalError, match=msg):
            safe_eval(expr, {})

    def test_function_calls_blocked_without_math(self):
        with pytest.raises(SafeEvalError, match="Function calls are not allowed"):
            safe_eval("sum([1, 2])", {})
        with pytest.raises(SafeEvalError, match="Function calls are not allowed"):
            safe_eval("__import__('os')", {})

    def test_visit_rejects_import_node_directly(self):
        """ast.Import cannot be produced by eval-mode parsing, but the
        visitor API must still reject it (defence in depth for direct
        visitor use)."""
        visitor = SafeEvaluator()
        visitor.visit(ast.Import(names=[ast.alias(name="os", asname=None)]))
        assert visitor._is_safe is False
        assert any("Import statements are not allowed" in e for e in visitor._errors)

    def test_visit_rejects_import_from_node_directly(self):
        visitor = SafeEvaluator()
        visitor.visit(ast.ImportFrom(module="os", names=[ast.alias(name="system", asname=None)], level=0))
        assert visitor._is_safe is False
        assert any("Import statements are not allowed" in e for e in visitor._errors)

    def test_syntax_error_and_empty_expression(self):
        with pytest.raises(SafeEvalError, match="Syntax error"):
            safe_eval("(1 +")
        with pytest.raises(SafeEvalError, match="Syntax error"):
            safe_eval("")
        assert safe_eval("123 # trailing comment") == 123

    def test_validation_error_when_ast_parse_raises(self, monkeypatch):
        def boom(src, mode):
            raise RuntimeError("parser exploded")

        with pytest.raises(SafeEvalError, match="Validation error"):
            monkeypatch.setattr("core.safe_evaluator.ast.parse", boom)
            SafeEvaluator().validate("1 + 1")

    def test_validate_returns_true_for_safe(self):
        assert SafeEvaluator().validate("1 + 2 * 3") is True
        assert SafeEvaluator(allow_function_calls=True).validate("sum([1, 2])") is True

    def test_validate_resets_state_between_calls(self):
        validator = SafeEvaluator()
        with pytest.raises(SafeEvalError):
            validator.validate("obj.x")
        assert validator.validate("1 + 1") is True


class TestSafeEvaluatorWithMath:
    def test_whitelisted_functions(self):
        assert safe_eval_with_math("sum([1, 2, 3])") == 6
        assert safe_eval_with_math("min(3, 1, 2)") == 1
        assert safe_eval_with_math("max(3, 1, 2)") == 3
        assert safe_eval_with_math("abs(-4)") == 4
        assert safe_eval_with_math("round(2.567, 1)") == 2.6
        assert safe_eval_with_math("len('abc')") == 3
        assert safe_eval_with_math("sqrt(16)") == 4.0
        assert safe_eval_with_math("log(100, 10)") == pytest.approx(2.0)
        assert safe_eval_with_math("log10(1000)") == pytest.approx(3.0)
        assert safe_eval_with_math("exp(0)") == pytest.approx(1.0)
        assert safe_eval_with_math("sin(0)") == pytest.approx(0.0)
        assert safe_eval_with_math("cos(0)") == pytest.approx(1.0)
        assert safe_eval_with_math("tan(0)") == pytest.approx(0.0)

    def test_conversions_and_aliases(self):
        assert safe_eval_with_math("int('5')") == 5
        assert safe_eval_with_math("float('1.5')") == 1.5
        assert safe_eval_with_math("str(123)") == "123"
        assert safe_eval_with_math("bool(0)") is False
        assert safe_eval_with_math("pi") == pytest.approx(3.141592653589793)
        assert safe_eval_with_math("e") == pytest.approx(2.718281828459045)

    def test_inputs_context(self):
        assert safe_eval_with_math("total + tax", {"total": 10, "tax": 2}) == 12

    def test_call_with_keyword_arg(self):
        assert safe_eval_with_math("int('ff', base=16)") == 255

    def test_call_with_subscript_arg(self):
        assert safe_eval_with_math("sum(l[0])", {"l": [[1, 2]]}) == 3

    @pytest.mark.parametrize("expr", [
        "obj.method()",
        "s.upper()",
        "f[0]()",
        "d['k']()",
        "open('/etc/passwd')",
    ])
    def test_dangerous_calls_rejected(self, expr):
        with pytest.raises(SafeEvalError):
            safe_eval_with_math(expr, {"obj": object(), "s": "x", "f": [lambda: 1], "d": {"k": lambda: 1}})


class TestSafeEvaluatorDoS:
    def test_constant_huge_pow_blocked(self):
        with pytest.raises(SafeEvalError, match="[Ee]xponent too large"):
            safe_eval("2 ** (10**18)", {})

    def test_folded_mult_huge_pow_blocked(self):
        with pytest.raises(SafeEvalError, match="[Ee]xponent too large"):
            safe_eval("2 ** (2 * 10**9)", {})

    def test_negative_huge_pow_blocked(self):
        with pytest.raises(SafeEvalError, match="[Ee]xponent too large"):
            safe_eval("2 ** -(10**18)", {})

    def test_math_pow_huge_exponent_blocked(self):
        with pytest.raises(SafeEvalError, match="[Ee]xponent too large"):
            safe_eval_with_math("pow(2, 10**18)")

    def test_math_pow_three_arg_modular_allowed(self):
        assert safe_eval_with_math("pow(2, 10**18, 7)") == pow(2, 10**18, 7)

    def test_just_under_cap_allowed(self):
        assert safe_eval("2 ** 100000") == 2 ** 100000

    def test_fold_failure_on_nested_non_constant_exponent(self):
        """The static DoS guard's folding must fail cleanly (return False,
        no exception) when the exponent subtree mixes constants with Names:
        ``2 ** (x + 2)`` is not provably-huge, so it validates and evaluates
        normally."""
        assert safe_eval("2 ** (x + 2)", {"x": 0}) == 4
        assert safe_eval_with_math("2 ** (x * 1)", {"x": 3}) == 8

    def test_fold_division_operator_returns_unknown(self):
        # Div is not foldable → exponent treated as non-constant → allowed.
        assert safe_eval("2 ** (4 / 2)", {}) == 4

    def test_nested_fold_guard_prevents_unbounded_computation(self):
        """2 ** (2 ** 10**9): the inner fold guard refuses to materialise
        the huge power, and the execution-time _safe_pow bound converts the
        result to SafeEvalError instead of hanging."""
        start = time.time()
        with pytest.raises(SafeEvalError):
            safe_eval("2 ** (2 ** (10**9))", {})
        assert time.time() - start < 3.0

    def test_non_constant_huge_exponent_rejected_at_runtime(self):
        start = time.time()
        with pytest.raises(SafeEvalError):
            safe_eval("2 ** e", {"e": 10 ** 18})
        assert time.time() - start < 3.0

    def test_negative_int_exponent_returns_float(self):
        assert safe_eval("2 ** -1", {}) == 0.5

    def test_float_base_pow_overflow_rejected(self):
        with pytest.raises(SafeEvalError):
            safe_eval("2.0 ** e", {"e": 10 ** 400})

    def test_float_base_small_pow(self):
        assert safe_eval("2.5 ** 2", {}) == 6.25

    def test_reasonable_non_constant_exponent_works(self):
        assert safe_eval("2 ** e", {"e": 8}) == 256

    def test_pow_call_small(self):
        assert safe_eval_with_math("pow(2, 8)") == 256


class TestSafeEvaluatorFoldBranches:
    def test_fold_add_sub_and_negate(self):
        """Constant folding of ``**``-exponent subtrees: Add and Sub both
        fold to a concrete int; a negated Name folds to unknown."""
        assert safe_eval("2 ** (1 + 1)", {}) == 4
        assert safe_eval("2 ** (5 - 3)", {}) == 4
        assert safe_eval("2 ** -x", {"x": 3}) == 0.125


class TestSafeEvaluatorErrors:
    def test_eval_value_error_surfaces(self):
        with pytest.raises(SafeEvalError, match="Evaluation failed"):
            safe_eval("2 ** e", {"e": 10 ** 18})

    def test_eval_generic_exception_surfaces(self):
        with pytest.raises(SafeEvalError, match="Evaluation failed"):
            safe_eval("x / y", {"x": 1, "y": 0})

    def test_math_eval_value_error_surfaces(self):
        with pytest.raises(SafeEvalError, match="Evaluation failed"):
            safe_eval_with_math("sqrt(-1)")

    def test_math_eval_generic_exception_surfaces(self):
        with pytest.raises(SafeEvalError, match="Evaluation failed"):
            safe_eval_with_math("1 / 0")


# ============================================================================
# core/error_guidance_engine.py — full mock-based suite
# ============================================================================


def _resolution_row(**over):
    base = {
        "resolution_attempted": "Let Agent Reconnect",
        "success": True,
        "agent_suggested": True,
        "user_feedback": "worked",
        "timestamp": datetime(2026, 8, 1, tzinfo=timezone.utc),
        "error_type": "auth_expired",
    }
    base.update(over)
    return SimpleNamespace(**base)


class TestCategorizeError:
    @pytest.fixture
    def engine(self):
        return ErrorGuidanceEngine(MagicMock())

    @pytest.mark.parametrize("code,msg,expected", [
        ("401", "token has expired", "auth_expired"),
        ("401", "unauthorized", "permission_denied"),
        ("403", "forbidden", "permission_denied"),
        ("429", "rate limit hit", "rate_limit"),
        ("404", "missing", "resource_not_found"),
        ("400", "bad input", "invalid_input"),
        ("500", "server error", "unknown"),
        (None, "no code", "unknown"),
    ])
    def test_code_first(self, engine, code, msg, expected):
        assert engine.categorize_error(code, msg) == expected

    @pytest.mark.parametrize("msg,expected", [
        ("permission denied", "permission_denied"),
        ("unauthorized access", "permission_denied"),
        ("token expired", "auth_expired"),
        ("rate limit exceeded", "rate_limit"),
        ("too many requests", "rate_limit"),
        ("network unreachable", "network_error"),
        ("connection refused", "network_error"),
        ("request timeout", "network_error"),
        ("resource not found", "resource_not_found"),
        ("invalid payload", "invalid_input"),
        ("malformed request", "invalid_input"),
        ("something else", "unknown"),
    ])
    def test_message_based(self, engine, msg, expected):
        assert engine.categorize_error(None, msg) == expected


class TestGetSuggestedResolution:
    @pytest.fixture
    def engine(self):
        return ErrorGuidanceEngine(MagicMock())

    def test_unknown_type_defaults_zero(self, engine):
        assert engine.get_suggested_resolution("nonsense") == 0

    def test_no_history_defaults_zero(self, engine):
        engine.db.query.return_value = _FakeQuery([])
        assert engine.get_suggested_resolution("auth_expired") == 0

    def test_most_successful_maps_to_template_index(self, engine):
        rows = [
            _resolution_row(resolution_attempted="Let Agent Reconnect"),
            _resolution_row(resolution_attempted="Let Agent Reconnect"),
            _resolution_row(resolution_attempted="Reconnect Manually", success=False),
        ]
        engine.db.query.return_value = _FakeQuery(rows)
        idx = engine.get_suggested_resolution("auth_expired")
        template = engine.ERROR_RESOLUTIONS["auth_expired"]["resolutions"]
        assert template[idx]["title"] == "Let Agent Reconnect"

    def test_historical_title_missing_from_template_falls_back(self, engine):
        engine.db.query.return_value = _FakeQuery(
            [_resolution_row(resolution_attempted="Ghost Resolution")]
        )
        assert engine.get_suggested_resolution("auth_expired") == 0


class TestTrackResolution:
    @pytest.mark.asyncio
    async def test_disabled_flag_does_nothing(self):
        engine = ErrorGuidanceEngine(MagicMock())
        with patch("core.error_guidance_engine.ERROR_GUIDANCE_ENABLED", False):
            await engine.track_resolution("auth_expired", "401", "Reconnect", True)
        engine.db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_success_records_row(self):
        db = MagicMock()
        engine = ErrorGuidanceEngine(db)
        await engine.track_resolution(
            "auth_expired", "401", "Reconnect", True,
            user_feedback="worked", agent_suggested=False,
        )
        db.add.assert_called_once()
        row = db.add.call_args_list[0][0][0]
        assert row.error_type == "auth_expired"
        assert row.error_code == "401"
        assert row.success is True
        assert row.user_feedback == "worked"
        assert row.agent_suggested is False
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_failure_rolls_back(self):
        db = MagicMock()
        db.add.side_effect = RuntimeError("boom")
        engine = ErrorGuidanceEngine(db)
        await engine.track_resolution("auth_expired", "401", "Reconnect", True)
        db.rollback.assert_called_once()


class TestHistorical:
    @pytest.fixture
    def engine(self):
        return ErrorGuidanceEngine(MagicMock())

    def test_get_historical(self, engine):
        engine.db.query.return_value = _FakeQuery([
            _resolution_row(),
            _resolution_row(timestamp=None, resolution_attempted="Other"),
        ])
        rows = engine.get_historical_resolutions("auth_expired", limit=5)
        assert len(rows) == 2
        assert rows[0]["resolution"] == "Let Agent Reconnect"
        assert rows[0]["user_feedback"] == "worked"
        assert rows[1]["timestamp"] is None

    def test_get_historical_exception(self, engine):
        engine.db.query.side_effect = RuntimeError("boom")
        assert engine.get_historical_resolutions("auth_expired") == []

    def test_success_rate_none(self, engine):
        engine.db.query.return_value = _FakeQuery([])
        stats = engine.get_resolution_success_rate("auth_expired", "Reconnect")
        assert stats == {
            "resolution": "Reconnect",
            "success_rate": 0.0,
            "total_attempts": 0,
            "successful_attempts": 0,
            "failed_attempts": 0,
        }

    def test_success_rate_mixed(self, engine):
        engine.db.query.return_value = _FakeQuery([
            _resolution_row(resolution_attempted="Reconnect", success=True),
            _resolution_row(resolution_attempted="Reconnect", success=True),
            _resolution_row(resolution_attempted="Reconnect", success=False),
        ])
        stats = engine.get_resolution_success_rate("auth_expired", "Reconnect")
        assert stats["total_attempts"] == 3
        assert stats["successful_attempts"] == 2
        assert stats["failed_attempts"] == 1
        assert stats["success_rate"] == round(2 / 3 * 100, 2)

    def test_success_rate_exception(self, engine):
        engine.db.query.side_effect = RuntimeError("boom")
        stats = engine.get_resolution_success_rate("auth_expired", "Reconnect")
        assert stats["success_rate"] == 0.0
        assert "error" in stats

    def test_statistics_empty(self, engine):
        engine.db.query.return_value = _FakeQuery([])
        stats = engine.get_resolution_statistics()
        assert stats["total_resolutions"] == 0
        assert stats["by_error_type"] == {}
        assert stats["overall_success_rate"] == 0.0

    def test_statistics_grouped(self, engine):
        rows = [
            _resolution_row(error_type="auth_expired", resolution_attempted="Reconnect", success=True),
            _resolution_row(error_type="auth_expired", resolution_attempted="Reconnect", success=False),
            _resolution_row(error_type="rate_limit", resolution_attempted="Wait", success=True),
        ]
        engine.db.query.return_value = _FakeQuery(rows)
        stats = engine.get_resolution_statistics()
        assert stats["total_resolutions"] == 3
        assert stats["overall_success_rate"] == round(2 / 3 * 100, 2)
        assert stats["by_error_type"]["auth_expired"]["total"] == 2
        assert stats["by_error_type"]["auth_expired"]["successful"] == 1
        detailed = {d["resolution"]: d for d in stats["detailed_stats"]}
        assert detailed["Reconnect"]["total"] == 2
        assert detailed["Reconnect"]["success_rate"] == 50.0
        assert detailed["Wait"]["success_rate"] == 100.0

    def test_statistics_filtered_by_type(self, engine):
        engine.db.query.return_value = _FakeQuery([_resolution_row(success=True)])
        stats = engine.get_resolution_statistics(error_type="auth_expired")
        assert stats["total_resolutions"] == 1

    def test_statistics_exception(self, engine):
        engine.db.query.side_effect = RuntimeError("boom")
        stats = engine.get_resolution_statistics()
        assert stats["total_resolutions"] == 0
        assert "error" in stats


class TestSuggestFixesFromHistory:
    @pytest.fixture
    def engine(self):
        return ErrorGuidanceEngine(MagicMock())

    def test_template_fallback_for_known_type(self, engine):
        engine.db.query.return_value = _FakeQuery([])
        suggestions = engine.suggest_fixes_from_history("permission_denied", "denied", limit=1)
        assert len(suggestions) == 1
        assert suggestions[0]["source"] == "template"
        assert suggestions[0]["resolution"] == "Let Agent Request Permission"
        assert suggestions[0]["agent_can_fix"] is True
        assert suggestions[0]["success_rate"] is None

    def test_unknown_type_without_history_returns_empty(self, engine):
        engine.db.query.return_value = _FakeQuery([])
        assert engine.suggest_fixes_from_history("nonsense", "x") == []

    def test_historical_suggestions(self, engine):
        engine.db.query.side_effect = [
            _FakeQuery([  # successful resolutions
                _resolution_row(resolution_attempted="Let Agent Reconnect"),
                _resolution_row(resolution_attempted="Let Agent Reconnect"),
                _resolution_row(resolution_attempted="Reconnect Manually"),
            ]),
            _FakeQuery([  # all resolutions for totals
                _resolution_row(resolution_attempted="Let Agent Reconnect"),
                _resolution_row(resolution_attempted="Let Agent Reconnect"),
                _resolution_row(resolution_attempted="Reconnect Manually", success=False),
            ]),
        ]
        suggestions = engine.suggest_fixes_from_history("auth_expired", "expired")
        assert len(suggestions) == 2
        best = suggestions[0]
        assert best["source"] == "historical"
        assert best["resolution"] == "Let Agent Reconnect"
        assert best["successful_attempts"] == 2
        assert best["total_attempts"] == 2
        assert best["success_rate"] == 100.0
        assert best["description"] == "I'll guide you through re-authentication"
        assert best["agent_can_fix"] is True

    def test_exception_returns_empty(self, engine):
        engine.db.query.side_effect = RuntimeError("boom")
        assert engine.suggest_fixes_from_history("auth_expired", "x") == []


class TestGetErrorFixSuggestions:
    @pytest.mark.asyncio
    async def test_full(self):
        engine = ErrorGuidanceEngine(MagicMock())
        engine.db.query.return_value = _FakeQuery([])
        result = await engine.get_error_fix_suggestions("429", "rate limit exceeded")
        assert result["error_type"] == "rate_limit"
        assert result["error_message"] == "rate limit exceeded"
        assert len(result["template_resolutions"]) == 2
        assert len(result["historical_suggestions"]) == 2  # template fallback
        assert result["recommended_resolution"] == 0
        assert result["statistics"]["total_resolutions"] == 0

    @pytest.mark.asyncio
    async def test_include_historical_false(self):
        engine = ErrorGuidanceEngine(MagicMock())
        engine.db.query.return_value = _FakeQuery([])
        result = await engine.get_error_fix_suggestions(
            None, "unknown problem", include_historical=False
        )
        assert result["error_type"] == "unknown"
        assert result["historical_suggestions"] == []

    @pytest.mark.asyncio
    async def test_exception_returns_error_dict(self):
        engine = ErrorGuidanceEngine(MagicMock())
        with patch.object(engine, "categorize_error", side_effect=RuntimeError("boom")):
            result = await engine.get_error_fix_suggestions("500", "x")
        assert result["error_type"] == "unknown"
        assert "error" in result


class TestExplainHelpers:
    @pytest.fixture
    def engine(self):
        return ErrorGuidanceEngine(MagicMock())

    def test_what_happened_known_and_unknown(self, engine):
        for etype in engine.ERROR_RESOLUTIONS:
            assert engine._explain_what_happened(etype, {})
        assert engine._explain_what_happened("nonsense", {}) == engine._explain_what_happened(
            "unknown", {}
        )

    def test_why_known_and_unknown(self, engine):
        for etype in engine.ERROR_RESOLUTIONS:
            assert engine._explain_why(etype, {})
        assert engine._explain_why("nonsense", {}) == engine._explain_why("unknown", {})

    def test_impact_known_and_unknown(self, engine):
        for etype in engine.ERROR_RESOLUTIONS:
            assert engine._explain_impact(etype)
        assert engine._explain_impact("nonsense") == engine._explain_impact("unknown")


class TestPresentError:
    @pytest.mark.asyncio
    async def test_broadcasts_with_guidance(self):
        db = MagicMock()
        engine = ErrorGuidanceEngine(db)
        with patch("core.error_guidance_engine.ws_manager") as ws:
            ws.broadcast = AsyncMock()
            await engine.present_error(
                "u1", "op-1",
                {"code": "403", "message": "permission denied", "technical_details": "td"},
                agent_id="a1",
            )
        ws.broadcast.assert_awaited_once()
        channel, payload = ws.broadcast.await_args.args
        assert channel == "user:u1"
        assert payload["type"] == "operation:error"
        data = payload["data"]
        assert data["operation_id"] == "op-1"
        assert data["error"]["type"] == "permission_denied"
        assert data["error"]["code"] == "403"
        assert data["error"]["technical_details"] == "td"
        assert data["suggested_resolution"] == 0
        assert len(data["resolutions"]) == 2
        analysis = data["agent_analysis"]
        assert analysis["what_happened"]
        assert analysis["why_it_happened"]
        assert analysis["impact"]
        assert db.commit.call_count == 1  # audit
        audit = db.add.call_args_list[0][0][0]
        assert audit.action_type == "present_error"
        assert audit.agent_id == "a1"
        assert audit.user_id == "u1"
        assert audit.details_json["error_type"] == "permission_denied"

    @pytest.mark.asyncio
    async def test_disabled_flag_returns_early(self):
        engine = ErrorGuidanceEngine(MagicMock())
        with patch("core.error_guidance_engine.ERROR_GUIDANCE_ENABLED", False):
            with patch("core.error_guidance_engine.ws_manager") as ws:
                ws.broadcast = AsyncMock()
                await engine.present_error("u1", "op-1", {"code": "500", "message": "x"})
        ws.broadcast.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_broadcast_failure_swallowed(self):
        engine = ErrorGuidanceEngine(MagicMock())
        with patch("core.error_guidance_engine.ws_manager") as ws:
            ws.broadcast = AsyncMock(side_effect=RuntimeError("ws down"))
            await engine.present_error("u1", "op-1", {"code": "404", "message": "not found"})
        assert not engine.db.commit.called

    @pytest.mark.asyncio
    async def test_create_audit_failure_rolls_back(self):
        db = MagicMock()
        db.add.side_effect = RuntimeError("boom")
        engine = ErrorGuidanceEngine(db)
        await engine._create_audit(agent_id="a1", user_id="u1", error_type="unknown", action="x")
        db.rollback.assert_called_once()


class TestModuleHelper:
    def test_get_error_guidance_engine(self):
        db = MagicMock()
        engine = get_error_guidance_engine(db)
        assert isinstance(engine, ErrorGuidanceEngine)
        assert engine.db is db


# ============================================================================
# core/monitoring.py — full standalone suite (real prometheus, patched objects)
# ============================================================================


class TestMonitoringStructlog:
    def test_add_log_level(self):
        import core.monitoring as mon

        event = mon.add_log_level(Mock(), "info", {})
        assert event["level"] == "INFO"

    def test_add_logger_name(self):
        import core.monitoring as mon

        logger = Mock()
        logger.name = "my.logger"
        assert mon.add_logger_name(logger, "info", {})["logger"] == "my.logger"

    def test_configure_structlog(self):
        import core.monitoring as mon

        with patch("structlog.configure") as cfg, patch("logging.basicConfig") as bc:
            mon.configure_structlog()
        cfg.assert_called_once()
        bc.assert_called_once()

    def test_get_logger(self):
        import core.monitoring as mon

        with patch("structlog.get_logger", return_value="lg") as gl:
            assert mon.get_logger("name") == "lg"
        gl.assert_called_once_with("name")

    def test_request_context_binds_and_restores(self):
        import core.monitoring as mon

        base = Mock()
        base._context = {"k": "v"}
        bound = Mock()
        bound._context = {"k": "v", "req": "1"}
        base.bind.return_value = bound
        with patch("structlog.get_logger", return_value=base):
            with mon.RequestContext(req="1") as log:
                assert log is bound
            base.bind.assert_called_once_with(req="1")
        assert base._context == {"k": "v"}


class TestMonitoringTrackers:
    def test_track_http_request(self):
        import core.monitoring as mon

        with patch.object(mon, "http_requests_total") as total, \
                patch.object(mon, "http_request_duration_seconds") as dur:
            mon.track_http_request("POST", "/api/x", 201, 0.5)
        total.labels.return_value.inc.assert_called_once()
        dur.labels.return_value.observe.assert_called_once_with(0.5)

    def test_track_agent_execution(self):
        import core.monitoring as mon

        with patch.object(mon, "agent_executions_total") as total, \
                patch.object(mon, "agent_execution_duration_seconds") as dur:
            mon.track_agent_execution("a1", "success", 1.2)
        total.labels.return_value.inc.assert_called_once()
        dur.labels.return_value.observe.assert_called_once_with(1.2)

    def test_track_skill_execution(self):
        import core.monitoring as mon

        with patch.object(mon, "skill_executions_total") as total, \
                patch.object(mon, "skill_execution_duration_seconds") as dur:
            mon.track_skill_execution("s1", "failure", 0.3)
        total.labels.return_value.inc.assert_called_once()
        dur.labels.return_value.observe.assert_called_once_with(0.3)

    def test_track_db_query(self):
        import core.monitoring as mon

        with patch.object(mon, "db_query_duration_seconds") as dur:
            mon.track_db_query("select", 0.01)
        dur.labels.return_value.observe.assert_called_once_with(0.01)

    def test_set_active_agents(self):
        import core.monitoring as mon

        with patch.object(mon, "active_agents") as gauge:
            mon.set_active_agents(7)
        gauge.set.assert_called_once_with(7)

    def test_set_db_connections(self):
        import core.monitoring as mon

        with patch.object(mon, "db_connections_active") as act, \
                patch.object(mon, "db_connections_idle") as idle:
            mon.set_db_connections(3, 5)
        act.set.assert_called_once_with(3)
        idle.set.assert_called_once_with(5)


class TestMonitoringDeployment:
    def test_track_deployment_success(self):
        import core.monitoring as mon

        with patch.object(mon, "deployment_total") as total, \
                patch.object(mon, "deployment_duration_seconds") as dur:
            with mon.track_deployment("staging"):
                pass
        total.labels.assert_called_once_with(environment="staging", status="success")
        dur.labels.return_value.observe.assert_called_once()

    def test_track_deployment_failure(self):
        import core.monitoring as mon

        with patch.object(mon, "deployment_total") as total, \
                patch.object(mon, "deployment_duration_seconds") as dur:
            with pytest.raises(RuntimeError):
                with mon.track_deployment("prod"):
                    raise RuntimeError("boom")
        total.labels.assert_called_once_with(environment="prod", status="failed")

    def test_track_smoke_test_success_and_failure(self):
        import core.monitoring as mon

        with patch.object(mon, "smoke_test_total") as total, \
                patch.object(mon, "smoke_test_duration_seconds") as dur:
            with mon.track_smoke_test("staging"):
                pass
            total.labels.assert_called_once_with(environment="staging", result="passed")
            with pytest.raises(RuntimeError):
                with mon.track_smoke_test("prod"):
                    raise RuntimeError("boom")
            total.labels.assert_called_with(environment="prod", result="failed")

    def test_record_rollback(self):
        import core.monitoring as mon

        with patch.object(mon, "deployment_rollback_total") as total:
            mon.record_rollback("prod", "smoke_test_failed")
        total.labels.assert_called_once_with(environment="prod", reason="smoke_test_failed")
        total.labels.return_value.inc.assert_called_once()

    def test_update_canary_traffic(self):
        import core.monitoring as mon

        with patch.object(mon, "canary_traffic_percentage") as gauge:
            mon.update_canary_traffic("prod", "sha1", 25)
        gauge.labels.assert_called_once_with(environment="prod", deployment_id="sha1")
        gauge.labels.return_value.set.assert_called_once_with(25)

    def test_record_prometheus_query(self):
        import core.monitoring as mon

        with patch.object(mon, "prometheus_query_total") as total, \
                patch.object(mon, "prometheus_query_duration_seconds") as dur:
            mon.record_prometheus_query("deploy-staging", True, 0.4)
            mon.record_prometheus_query("deploy-staging", False, 0.6)
        total.labels.assert_called_with(workflow="deploy-staging", result="failed")
        assert dur.labels.return_value.observe.call_count == 2

    def test_initialize_metrics_success(self):
        import core.monitoring as mon

        with patch("prometheus_client.start_http_server") as start, \
                patch.object(mon, "get_logger") as gl:
            mon.initialize_metrics()
        start.assert_called_once_with(8001)
        gl.return_value.info.assert_called_once()

    def test_initialize_metrics_oserror(self):
        import core.monitoring as mon

        with patch("prometheus_client.start_http_server", side_effect=OSError("in use")) as start, \
                patch.object(mon, "get_logger") as gl:
            mon.initialize_metrics()
        start.assert_called_once_with(8001)
        gl.return_value.warning.assert_called_once()
