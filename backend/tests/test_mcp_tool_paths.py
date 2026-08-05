"""
Tests for MCP tool path safety (integrations/mcp_service.py).

Two path-safety bugs:
- verify_citation: the whitelist included /Users (every home dir), letting an
  agent read ~/.ssh/id_rsa, .env, etc.
- generate_pdf_report: os.path.join("/tmp", filename) discards /tmp when
  filename is absolute or contains traversal → arbitrary file write.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def mcp_service():
    """Minimal MCPService for direct execute_tool calls."""
    from integrations.mcp_service import MCPService
    svc = MCPService.__new__(MCPService)
    # execute_tool reads context but not svc state for these tools; minimal init.
    return svc


class TestVerifyCitationPathSafety:
    @pytest.mark.asyncio
    async def test_rejects_ssh_key_path(self, mcp_service):
        """A path under ~/.ssh MUST be denied — the old whitelist allowed /Users."""
        ctx = {"workspace_id": "ws"}
        result = await mcp_service.execute_tool("local-tools", "verify_citation", {"path": "/Users/someone/.ssh/id_rsa"}, ctx)
        assert "Snippet:" not in str(result), (
            "verify_citation returned file contents for a .ssh path — arbitrary file read."
        )
        assert "denied" in str(result).lower() or "error" in str(result).lower()

    @pytest.mark.asyncio
    async def test_rejects_env_file(self, mcp_service):
        """A .env file path MUST be denied."""
        ctx = {"workspace_id": "ws"}
        result = await mcp_service.execute_tool("local-tools", "verify_citation", {"path": "/app/.env"}, ctx)
        assert "Snippet:" not in str(result), ".env contents were disclosed"


class TestGeneratePdfReportPathSafety:
    @pytest.mark.asyncio
    async def test_rejects_absolute_filename(self, mcp_service):
        """An absolute filename MUST NOT escape /tmp."""
        ctx = {"workspace_id": "ws"}
        result = await mcp_service.execute_tool(
            "local-tools", "generate_pdf_report",
            {"content": "test", "filename": "/etc/cron.d/evil_report"},
            ctx,
        )
        # The returned file_path must be under /tmp, not the absolute path.
        file_path = result.get("file_path", "") if isinstance(result, dict) else ""
        assert file_path.startswith("/tmp/"), (
            f"generate_pdf_report wrote to {file_path} — absolute filename escaped /tmp"
        )
