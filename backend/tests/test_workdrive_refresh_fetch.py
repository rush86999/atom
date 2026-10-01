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
