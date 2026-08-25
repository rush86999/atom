#!/usr/bin/env python3
"""
Atom OS CLI — Integration commands (round 80r: desktop/CLI parity).

Web and mobile both carry full integration journeys; this module brings the
same read/manage surface to the terminal:

    atom-os login                          POST /api/auth/login, store JWT
    atom-os integrations list              GET /api/integrations
    atom-os integrations status            GET /api/v1/integrations/health
    atom-os integrations connect <prov>    GET initiate?format=json, print URL
    atom-os integrations disconnect <prov> DELETE /api/v1/auth/oauth/tokens/<prov>

All HTTP goes through _request() so tests patch a single seam. Token
resolution order: ATOM_TOKEN env > ~/.atom/token file.
"""
import os
import sys
from pathlib import Path

# Overridable in tests via patch("cli.integrations.CLI_HOME", ...)

from typing import Any, Dict, Optional, Tuple

import click
import requests

CLI_HOME = Path.home() / ".atom"


def _token_file() -> Path:
    """Session token path (dynamic so tests can relocate CLI_HOME)."""
    return CLI_HOME / "token"


def _base_url() -> str:
    port = os.getenv("PORT", "8000")
    return os.getenv("ATOM_BASE_URL", f"http://localhost:{port}")


def _resolve_token() -> Optional[str]:
    """Token resolution order: --token flag > ATOM_TOKEN env > ~/.atom/token."""
    env = os.getenv("ATOM_TOKEN")
    if env:
        return env.strip()
    token_file = _token_file()
    if token_file.exists():
        content = token_file.read_text().strip()
        return content or None
    return None


def _request(method: str, path: str, token: Optional[str] = None,
             json_body: Optional[Dict[str, Any]] = None,
             timeout: int = 15) -> requests.Response:
    headers = {"Content-Type": "application/json"}
    resolved = token or _resolve_token()
    if resolved:
        headers["Authorization"] = f"Bearer {resolved}"
    return requests.request(
        method, f"{_base_url()}{path}",
        headers=headers, json=json_body, timeout=timeout,
    )


def _require_token() -> Optional[str]:
    token = _resolve_token()
    if not token:
        click.echo(click.style(
            "Not authenticated. Run `atom-os login` first "
            "(or set ATOM_TOKEN).", fg="red"))
        sys.exit(1)
    return token


@click.command()
@click.option("--email", prompt=True, help="Account email")
@click.option("--password", prompt=True, hide_input=True,
              help="Account password")
@click.option("--token", default=None, help="Skip login; store an existing JWT")
def login(email: str, password: str, token: Optional[str]):
    """Authenticate against the running Atom server and store the session."""
    if token:
        stored = token
    else:
        try:
            resp = _request("POST", "/api/auth/login",
                            json_body={"username": email, "password": password},
                            timeout=20)
        except requests.ConnectionError:
            click.echo(click.style(
                f"Cannot reach Atom at {_base_url()} — is the server running?",
                fg="red"))
            sys.exit(1)
        if resp.status_code != 200:
            detail = ""
            try:
                detail = resp.json().get("detail", "")
            except ValueError:
                pass
            click.echo(click.style(f"Login failed: {detail or resp.status_code}",
                                   fg="red"))
            sys.exit(1)
        stored = resp.json().get("access_token")
        if not stored:
            click.echo(click.style("Login succeeded but no access_token returned",
                                   fg="red"))
            sys.exit(1)

    CLI_HOME.mkdir(parents=True, exist_ok=True)
    token_file = _token_file()
    token_file.write_text(stored)
    token_file.chmod(0o600)
    click.echo(click.style("Authenticated. Token stored at "
                           f"{token_file} (0600)", fg="green"))


@click.group("integrations")
def integrations_cli():
    """List, inspect, connect and disconnect app integrations."""
    pass


@integrations_cli.command("list")
@click.option("--token", default=None, help="Explicit JWT (overrides stored)")
def list_integrations(token: Optional[str]):
    """List all available integrations."""
    tok = _require_token()
    try:
        resp = _request("GET", "/api/integrations", token=tok)
    except requests.ConnectionError:
        click.echo(click.style(f"Cannot reach Atom at {_base_url()}", fg="red"))
        sys.exit(1)
    if resp.status_code != 200:
        click.echo(click.style(f"Failed: HTTP {resp.status_code}", fg="red"))
        sys.exit(1)
    data = resp.json()
    names = data.get("integrations", [])
    click.echo(f"{data.get('total', len(names))} integrations available:")
    for name in sorted(names):
        loaded = name in (data.get("loaded") or {})
        marker = click.style("●", fg="green") if loaded else click.style("○", fg="bright_black")
        click.echo(f"  {marker} {name}")


@integrations_cli.command("status")
@click.option("--unhealthy-only", is_flag=True,
              help="Show only services that are not healthy")
@click.option("--token", default=None, help="Explicit JWT")
def integration_status(unhealthy_only: bool, token: Optional[str]):
    """Aggregate + per-service health summary."""
    tok = _require_token()
    try:
        resp = _request("GET", "/api/v1/integrations/health", token=tok)
    except requests.ConnectionError:
        click.echo(click.style(f"Cannot reach Atom at {_base_url()}", fg="red"))
        sys.exit(1)
    if resp.status_code != 200:
        click.echo(click.style(f"Failed: HTTP {resp.status_code}", fg="red"))
        sys.exit(1)
    data = resp.json()
    healthy = data.get("healthy_integrations", 0)
    total = data.get("total_integrations", 0)
    pct = data.get("overall_health_percentage", 0)
    color = "green" if healthy == total else ("yellow" if healthy else "red")
    click.echo(click.style(f"{healthy} of {total} healthy ({pct:.0f}%)", fg=color))

    rows = data.get("integration_status", []) or []
    if unhealthy_only:
        rows = [r for r in rows if r.get("status") != "healthy"]
    for row in rows:
        status = row.get("status", "unknown")
        mark = "✓" if status == "healthy" else "✗"
        line = f"  {mark} {row.get('service_name')}: {status}"
        err = row.get("error_message")
        if status != "healthy" and err:
            line += f" — {err}"
        style = "green" if status == "healthy" else "red"
        click.echo(click.style(line, fg=style))


@integrations_cli.command("connect")
@click.argument("provider")
@click.option("--open-browser/--no-open-browser", default=False,
              help="Open the authorization URL in the system browser")
@click.option("--token", default=None, help="Explicit JWT")
def connect(provider: str, open_browser: bool, token: Optional[str]):
    """Print (and optionally open) the OAuth authorization URL for PROVIDER."""
    tok = _require_token()
    try:
        resp = _request("GET",
                        f"/api/v1/auth/oauth/{provider}/initiate?format=json",
                        token=tok)
    except requests.ConnectionError:
        click.echo(click.style(f"Cannot reach Atom at {_base_url()}", fg="red"))
        sys.exit(1)
    if resp.status_code != 200:
        detail = ""
        try:
            detail = resp.json().get("detail", "")
        except ValueError:
            pass
        click.echo(click.style(
            f"Connect failed: {detail or f'HTTP {resp.status_code}'}", fg="red"))
        sys.exit(1)
    url = resp.json().get("url")
    if not url:
        click.echo(click.style("Connect failed: no authorization URL returned",
                               fg="red"))
        sys.exit(1)
    click.echo(f"Open this URL to authorize {provider}:")
    click.echo(click.style(url, fg="cyan", bold=True))
    if open_browser:
        import webbrowser
        webbrowser.open(url)


@integrations_cli.command("disconnect")
@click.argument("provider")
@click.option("--token", default=None, help="Explicit JWT")
def disconnect(provider: str, token: Optional[str]):
    """Revoke stored OAuth tokens for PROVIDER."""
    tok = _require_token()
    try:
        resp = _request("DELETE", f"/api/v1/auth/oauth/tokens/{provider}",
                        token=tok)
    except requests.ConnectionError:
        click.echo(click.style(f"Cannot reach Atom at {_base_url()}", fg="red"))
        sys.exit(1)
    if resp.status_code == 404:
        click.echo(f"{provider} is not connected.")
        return
    if resp.status_code != 200:
        click.echo(click.style(
            f"Disconnect failed: HTTP {resp.status_code}", fg="red"))
        sys.exit(1)
    message = ""
    try:
        message = resp.json().get("message", "")
    except ValueError:
        pass
    click.echo(click.style(message or f"{provider} disconnected.", fg="green"))
