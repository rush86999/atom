# -*- coding: utf-8 -*-
"""Refresh-fetch truthfulness + workspace-scoped credentials (2026-09-30).

Root cause chain behind the 'SOURCE FRESHNESS: read failed' incident,
established live:
1. The chat session ran under a user row that never connected
   WorkDrive; the connected row belongs to the same operator/workspace.
   Strict per-user lookup (correctly no cross-USER fallback) returned
   None -> download refused -> 'read failed' with no reason.
2. The storage read action returned status 'success' for refusals
   (found/served False, reason inside data.message) — the freshness
   check treated top-level status as the outcome.
3. A caller-pinned file_id was subjected to the NAME-resolution gate
   ('unverified candidate') instead of being addressed by id.

Fixes verified live end-to-end (found/served/verified True on the real
resource for the failing user). These tests pin the wiring.
"""
from __future__ import annotations

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")


class TestCallerPinnedRead:
    def test_name_gate_skips_explicit_file_id(self):
        """The 'unverified candidate' refusal is for NAME resolution; a
        caller-pinned file_id (the refresh addressing the conversation's
        own resource) must never be refused by it."""
        import integrations.universal_integration_service as uis

        src = inspect.getsource(uis.UniversalIntegrationService._read_storage_file)
        assert 'and not params.get("file_id")' in src

    def test_download_passes_workspace_context(self):
        import integrations.universal_integration_service as uis

        src = inspect.getsource(uis.UniversalIntegrationService._read_storage_file)
        assert 'workspace_id=(context or {}).get("workspace_id")' in src


class TestFreshnessFetchTruth:
    def test_fetch_ok_requires_served_content(self):
        """status=='success' alone is NOT a fetch outcome — the storage
        read returns success-shaped refusals."""
        import integrations.chat_orchestrator as orch

        src = inspect.getsource(
            orch.ChatOrchestrator._verify_source_freshness)
        assert '(fetch_data or {}).get("found")' in src
        assert 'or (fetch_data or {}).get("served")' in src

    def test_refusal_message_surfaces_from_data(self):
        import integrations.chat_orchestrator as orch

        src = inspect.getsource(
            orch.ChatOrchestrator._verify_source_freshness)
        assert '_fd.get("message")' in src

    def test_timeout_verdict_names_the_timeout(self, monkeypatch):
        """Live 2026-09-30/10-01: TimeoutError stringifies to '' — the
        verdict rendered the nameless '(read failed)' while a 13MB
        WorkDrive download sat behind a 5s floor. The note must say it
        timed out and for how long."""
        import asyncio

        import integrations.chat_orchestrator as orch
        import integrations.universal_integration_service as uis_mod

        class _TimeoutUIS:
            async def execute(self, *a, **k):
                raise asyncio.TimeoutError()

        monkeypatch.setattr(
            uis_mod, "UniversalIntegrationService", _TimeoutUIS)
        orchestrator = object.__new__(orch.ChatOrchestrator)
        verdict = asyncio.run(orchestrator._verify_source_freshness(
            {"identity": {
                "service": "datasets", "source": "zoho_workdrive",
                "resource_id": "wd-77",
                "ingested_at": "2026-09-30T23:18:31"}},
            {"operation": "refresh"}, "u1", "ws", None))
        assert verdict["status"] == "refresh_failed"
        assert "timed out" in verdict["note"]
        assert "read failed" not in verdict["note"]

    def test_refresh_passes_pinned_identity(self):
        import integrations.chat_orchestrator as orch

        src = inspect.getsource(
            orch.ChatOrchestrator._verify_source_freshness)
        assert '"identity_verified": True' in src
        assert '"file_name": (pending_task.get("resolved_file")' in src


class TestWorkspaceScopedCredentials:
    def test_workspace_fallback_exists_and_is_audited(self):
        """No cross-USER fallback (deliberately removed, security) — but
        the WORKSPACE's connected account serves members of that
        workspace (org-connection model), and every resolution is
        logged."""
        import integrations.zoho_workdrive_service as svc

        src = inspect.getsource(
            svc.ZohoWorkDriveService._integration_token_access_token)
        assert "IntegrationToken.workspace_id ==" in src
        assert "workspace-scoped credential used" in src

    def test_download_threads_workspace_to_token_lookup(self):
        import integrations.zoho_workdrive_service as svc

        src = inspect.getsource(
            svc.ZohoWorkDriveService.download_file)
        assert "workspace_id=workspace_id" in src


class TestFetchBudget:
    def test_small_deadline_skips_fetch_with_named_reason(
            self, monkeypatch):
        """2026-10-01 live: the old floor attempted a 5s fetch on a
        13MB workbook — a guaranteed timeout that burned the reply
        budget. Under a 12s-bounded window the fetch is SKIPPED and the
        verdict says why, before any network call."""
        import asyncio

        import integrations.chat_orchestrator as orch
        import integrations.universal_integration_service as uis_mod

        class _MustNotFetch:
            async def execute(self, *a, **k):  # pragma: no cover
                raise AssertionError("fetch must not run on a dead budget")

        class _Deadline:
            def remaining(self):
                return 20.0  # 20 - 15 = 5s window < 12s floor

            def elapsed(self):
                return 95.0

        monkeypatch.setattr(
            uis_mod, "UniversalIntegrationService", _MustNotFetch)
        orchestrator = object.__new__(orch.ChatOrchestrator)
        verdict = asyncio.run(orchestrator._verify_source_freshness(
            {"identity": {
                "service": "datasets", "source": "zoho_workdrive",
                "resource_id": "wd-77",
                "ingested_at": "2026-10-01T15:50:20"}},
            {"operation": "refresh"}, "u1", "ws", _Deadline()))
        assert verdict["status"] == "unverified"
        assert "cannot fit a live re-fetch" in verdict["note"]
        assert verdict["reason"] == "turn budget too small for a live re-fetch"

    def test_ceiling_accommodates_large_workbooks(self):
        """The 40s ceiling was measured too small for the 13MB price
        list (download alone exceeded it; every refresh reported
        'could NOT be re-fetched'). The ceiling must exceed 40s."""
        import inspect

        import integrations.chat_orchestrator as orch

        src = inspect.getsource(
            orch.ChatOrchestrator._verify_source_freshness)
        assert "fetch_ceiling = 75.0" in src


class TestMissHandoffThreading:
    def test_handoff_state_reaches_the_reply_builder(self):
        """2026-10-01 live (e2e turn 1): the miss→narration handoff's
        four levers inside _get_qwen_response read
        ``locals().get("_ask_miss_handoff")`` — a name only assigned in
        process_chat_message's scope — so every read silently returned
        None: no lesson assembly, no evidence re-assert, honest-status
        flags off, and the narrator answered 'I don't have the
        contents' while the read's results sat in the turn record. The
        state must arrive as explicit parameters, and no dead scope
        read may remain."""
        import inspect

        import integrations.chat_orchestrator as orch

        sig = inspect.signature(orch.ChatOrchestrator._get_qwen_response)
        assert "miss_handoff" in sig.parameters
        assert "miss_handoff_block" in sig.parameters
        src = inspect.getsource(orch.ChatOrchestrator._get_qwen_response)
        # all four levers consume the PARAMETERS (the docstring may quote
        # the old bug, so the live forms are pinned):
        assert "or miss_handoff):" in src                        # assembly
        assert "_live_file_lookup_ran = bool(miss_handoff)" in src
        assert "_file_lookup_attempted = bool(miss_handoff)" in src
        assert "if miss_handoff and miss_handoff_block:" in src  # evidence
        # the caller passes the state explicitly
        caller = inspect.getsource(orch.ChatOrchestrator.process_chat_message)
        assert "miss_handoff=bool(locals().get(\"_ask_miss_handoff\"))" in caller
        assert "miss_handoff_block=(" in caller


class TestFreshnessNoteIdempotence:
    def test_final_note_append_is_guarded(self):
        """2026-10-01 live (e2e round 3): the compare/refresh branches
        append the freshness note to the answer, and the unconditional
        final append added it a SECOND time — the SOURCE FRESHNESS
        paragraph shipped twice in one reply. The final append must be
        containment-guarded."""
        import inspect
        import re

        import integrations.chat_orchestrator as orch

        src = inspect.getsource(orch.ChatOrchestrator.process_chat_message)
        # whitespace-normalized so a line-wrap cannot break the pin
        flat = re.sub(r"\s+", " ", src)
        assert '_ask_freshness["note"]) not in _ask_content' in flat
