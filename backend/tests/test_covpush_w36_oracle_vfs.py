"""Coverage wave 36 — oracle verifiers (57/88%) + VFS base/registry/config (66/83/88%) → 90%+.

- oracle: env_bool truthy set, OracleResult.to_dict with claim, validate
  exception tolerance, workflow/task verifier missing-ctx + DB-exception paths
- vfs_base: to_dict helpers, to_line_numbered empty, default grep (bad regex,
  ls failure, non-file skip, cat failure, match), default scan (ls failure at
  root and at depth), ask_image degrade default
- vfs_registry: empty/slash-prefix rejection, empty-path resolve, list_prefixes
- knowledge_vfs_config: env_bool with env set
"""
import os
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import pytest

from core.oracle import (
    OracleResult,
    get_postcondition,
    oracle_verifier_enabled,
    register_postcondition,
    validate,
    verify_before_retry,
)
from core.oracle import postcondition_verifiers as pv  # noqa: F401  (registers verifiers)
from core.vfs_base import (
    VFSNode,
    VFSProvider,
    VFSResource,
    VFSCitation,
    to_line_numbered,
)
from core.vfs_registry import (
    get_provider,
    list_prefixes,
    register_provider,
    resolve_provider,
)


def await_coroutine(coro):
    import asyncio
    return asyncio.get_event_loop().run_until_complete(coro)


class TestOracleCore:
    def test_env_bool_set_truthy(self):
        with patch.dict(os.environ, {"ATOM_ORACLE_VERIFIER_ENABLED": "1"}, clear=True):
            assert oracle_verifier_enabled() is True

    def test_env_bool_set_falsy(self):
        with patch.dict(os.environ, {"ATOM_ORACLE_VERIFIER_ENABLED": "false"}, clear=True):
            assert oracle_verifier_enabled() is False

    def test_env_bool_garbage_falsy(self):
        with patch.dict(os.environ, {"ATOM_ORACLE_VERIFIER_ENABLED": "banana"}, clear=True):
            assert oracle_verifier_enabled() is False

    def test_to_dict_with_claim(self):
        d = OracleResult("a", True, "ev", claim_verified=False).to_dict()
        assert d == {"action": "a", "verified": True, "evidence": "ev", "claim_verified": False}

    def test_validate_unknown_action_returns_none(self):
        assert await_coroutine(validate("no_such_action")) is None

    def test_validate_verifier_exception_returns_unverified(self):
        async def boom(ctx):
            raise RuntimeError("check failed")
        register_postcondition("w36_boom")(boom)
        result = await_coroutine(validate("w36_boom", {"k": 1}))
        assert result is not None and result.verified is False
        assert "errored" in result.evidence

    def test_verify_before_retry_disabled_returns_false(self):
        with patch("core.oracle.oracle_verifier_enabled", return_value=False):
            assert await_coroutine(verify_before_retry("trigger_workflow", {})) is False

    def test_verify_before_retry_met_returns_true(self):
        async def yes(ctx):
            return OracleResult("x", True, "ok")
        register_postcondition("w36_yes")(yes)
        assert await_coroutine(verify_before_retry("w36_yes")) is True

    def test_verify_before_retry_unmet_returns_false(self):
        async def no(ctx):
            return OracleResult("x", False, "no")
        register_postcondition("w36_no")(no)
        assert await_coroutine(verify_before_retry("w36_no")) is False

    def test_get_postcondition_missing(self):
        assert get_postcondition("w36_missing") is None


class TestWorkflowVerifier:
    def test_missing_context(self):
        assert await_coroutine(pv._verify_workflow_triggered({})).verified is False

    def test_workflow_not_in_db(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        result = await_coroutine(pv._verify_workflow_triggered(
            {"workflow_id": "w1", "db": db}))
        assert result.verified is False
        assert "not in DB" in result.evidence

    def test_workflow_active(self):
        wf = NS(id="w1", status="active")
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = wf
        result = await_coroutine(pv._verify_workflow_triggered(
            {"workflow_id": "w1", "db": db}))
        assert result.verified is True
        assert "active" in result.evidence

    def test_workflow_inactive(self):
        wf = NS(id="w1", status="paused")
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = wf
        result = await_coroutine(pv._verify_workflow_triggered(
            {"workflow_id": "w1", "db": db}))
        assert result.verified is False

    def test_db_readback_exception(self):
        db = Mock()
        db.query.side_effect = RuntimeError("db down")
        result = await_coroutine(pv._verify_workflow_triggered(
            {"workflow_id": "w1", "db": db}))
        assert result.verified is False
        assert "read-back failed" in result.evidence


class TestTaskVerifier:
    def test_missing_context(self):
        assert await_coroutine(pv._verify_task_created({})).verified is False

    def test_task_exists(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = NS(id="t1")
        result = await_coroutine(pv._verify_task_created({"task_id": "t1", "db": db}))
        assert result.verified is True
        assert "present" in result.evidence

    def test_task_absent(self):
        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        result = await_coroutine(pv._verify_task_created({"task_id": "t1", "db": db}))
        assert result.verified is False
        assert "absent" in result.evidence

    def test_db_readback_exception(self):
        db = Mock()
        db.query.side_effect = RuntimeError("db down")
        result = await_coroutine(pv._verify_task_created({"task_id": "t1", "db": db}))
        assert result.verified is False


class TestVFSBase:
    def test_resource_to_dict(self):
        res = VFSResource(path="/k/d1/content.lines", meta={"id": 1}, lines=["L1: a", "L2: b"])
        d = res.to_dict()
        assert d["content"] == "L1: a\nL2: b"
        assert d["line_count"] == 2

    def test_citation_to_dict(self):
        assert VFSCitation("/a", 3, "s").to_dict() == {
            "path": "/a", "line": 3, "snippet": "s"}

    def test_to_line_numbered_empty(self):
        assert to_line_numbered("") == []

    def test_to_line_numbered_basic(self):
        assert to_line_numbered("a\nb") == ["L1: a", "L2: b"]

    class _FlatProvider(VFSProvider):
        prefix = "flat"

        def __init__(self, nodes=None, contents=None, ls_errors=None, cat_errors=None):
            self.nodes = nodes or []
            self.contents = contents or {}
            self.ls_errors = ls_errors or []
            self.cat_errors = cat_errors or []

        async def ls(self, path, ctx=None):
            if self.ls_errors:
                err = self.ls_errors.pop(0)
                if err:
                    raise err
            return self.nodes

        async def cat(self, path, ctx=None):
            if path in self.cat_errors:
                raise RuntimeError("cat boom")
            return self.contents.get(path, VFSResource(path=path, lines=[]))

    def test_grep_invalid_regex_returns_empty(self):
        p = self._FlatProvider()
        assert await_coroutine(p.grep("[", "x")) == []

    def test_grep_ls_failure_returns_empty(self):
        p = self._FlatProvider(ls_errors=[RuntimeError("ls boom")])
        assert await_coroutine(p.grep("pat", "x")) == []

    def test_grep_skips_dirs_and_cat_failures(self):
        p = self._FlatProvider(
            nodes=[VFSNode("d", "dir", "x/d"), VFSNode("f", "file", "x/f")],
            cat_errors=["x/f"],
        )
        assert await_coroutine(p.grep("pat", "x")) == []

    def test_grep_finds_match_with_line_number(self):
        p = self._FlatProvider(
            nodes=[VFSNode("f", "file", "x/f")],
            contents={"x/f": VFSResource(path="x/f", lines=["L1: hello", "L2: world"])},
        )
        hits = await_coroutine(p.grep("world", "x"))
        assert len(hits) == 1
        assert hits[0].line == 2
        assert hits[0].path == "x/f"

    def test_scan_root_ls_failure(self):
        p = self._FlatProvider(ls_errors=[RuntimeError("boom")])
        assert await_coroutine(p.scan("root")) == []

    def test_scan_nested_with_depth_ls_failure(self):
        p = self._FlatProvider(
            nodes=[VFSNode("d", "dir", "root/d"), VFSNode("f1", "file", "root/f1")],
            ls_errors=[None, RuntimeError("boom")],
        )
        found = await_coroutine(p.scan("root"))
        assert [n.name for n in found] == ["f1"]

    def test_ask_image_default_degrades(self):
        p = self._FlatProvider()
        out = await_coroutine(p.ask_image("/img.png", "what is this"))
        assert out["success"] is False
        assert "vision_unavailable" in out["error"]


class TestVFSRegistry:
    def _cleanup(self):
        for prefix in list_prefixes():
            _REGISTRY.pop(prefix, None)

    def test_register_empty_prefix_raises(self):
        with pytest.raises(ValueError):
            register_provider(NS(prefix=""))

    def test_register_slash_prefix_raises(self):
        with pytest.raises(ValueError):
            register_provider(NS(prefix="a/b"))

    def test_resolve_empty_path_returns_none(self):
        assert resolve_provider("") is None

    def test_register_get_resolve_roundtrip(self):
        from core.vfs_registry import _REGISTRY
        provider = NS(prefix="w36prov")
        register_provider(provider)
        try:
            assert get_provider("w36prov") is provider
            assert resolve_provider("/w36prov/documents/x") is provider
            assert resolve_provider("w36prov") is provider
            assert "w36prov" in list_prefixes()
            assert get_provider("nope") is None
        finally:
            _REGISTRY.pop("w36prov", None)


class TestKnowledgeVfsConfig:
    def test_env_bool_set(self):
        from core.knowledge_vfs_config import _env_bool
        with patch.dict(os.environ, {"X": "1"}, clear=True):
            assert _env_bool("X", False) is True
        with patch.dict(os.environ, {}, clear=True):
            assert _env_bool("X", False) is False
