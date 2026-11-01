"""MCP egress policy must reject prohibited destinations before connecting."""
import pytest

from core.mcp_client import MCPClient, MCPClientError, validate_server_config


@pytest.fixture(autouse=True)
def _no_allowlist(monkeypatch):
    monkeypatch.delenv("ATOM_MCP_ALLOWED_HOSTS", raising=False)


def test_public_ip_is_allowed_without_allowlist():
    assert validate_server_config(
        "public", {"transport": "http", "url": "http://93.184.216.34/mcp"})


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:59997/mcp",
    "http://10.0.0.1/mcp",
    "http://169.254.169.254/latest/meta-data",
    "http://[::1]/mcp",
    "file:///etc/passwd",
    "http://user:pass@93.184.216.34/mcp",
])
def test_local_private_and_non_http_destinations_are_refused(url):
    with pytest.raises(MCPClientError):
        validate_server_config("bad", {"transport": "http", "url": url})


def test_allowlist_tones_down_the_default_only_for_named_hosts(monkeypatch):
    monkeypatch.setenv("ATOM_MCP_ALLOWED_HOSTS", "127.0.0.1")
    assert validate_server_config(
        "local", {"transport": "http", "url": "http://127.0.0.1:59997/mcp"})
    with pytest.raises(MCPClientError, match="outside ATOM_MCP_ALLOWED_HOSTS"):
        validate_server_config(
            "other", {"transport": "http", "url": "https://example.com/mcp"})


def test_client_refuses_before_constructing_network(monkeypatch):
    called = []
    import httpx

    class NoNetwork:
        def __init__(self, *args, **kwargs):
            called.append(True)
            raise AssertionError("network client constructed")

    monkeypatch.setattr(httpx, "AsyncClient", NoNetwork)
    with pytest.raises(MCPClientError):
        MCPClient("bad", {"transport": "http",
                          "url": "http://169.254.169.254/mcp"})
    assert called == []


def test_stdio_requires_a_command_and_unknown_transport_is_refused():
    with pytest.raises(MCPClientError, match="requires a command"):
        validate_server_config("stdio", {"transport": "stdio"})
    with pytest.raises(MCPClientError, match="unsupported MCP transport"):
        validate_server_config("bad", {"transport": "carrier-pigeon"})
