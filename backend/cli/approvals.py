"""Atom OS CLI — Approvals commands (round 80t2: HITL parity).

    atom-os approvals list              GET /api/agent-governance/pending-approvals
    atom-os approvals approve <id>      POST /api/agent-governance/approve/{id}
    atom-os approvals reject <id>       POST /api/agent-governance/reject/{id}

RBAC (TEAM_LEAD+) is enforced server-side; the CLI forwards the stored JWT.
"""
import sys

import click
import requests

from cli.integrations import _base_url
from cli import integrations as _integ


@click.group("approvals")
def approvals_cli():
    """Review and decide pending workflow approvals (HITL)."""
    pass


@approvals_cli.command("list")
@click.option("--token", default=None, help="Explicit JWT")
def list_approvals(token: str | None):
    """List pending workflow approvals."""
    tok = _integ._resolve_token()
    if not tok and not token:
        click.echo(click.style(
            "Not authenticated. Run `atom-os login` first.", fg="red"))
        sys.exit(1)
    try:
        resp = _integ._request(
            "GET", "/api/agent-governance/pending-approvals",
            token=token or tok,
        )
    except requests.ConnectionError:
        click.echo(click.style(f"Cannot reach Atom at {_base_url()}", fg="red"))
        sys.exit(1)
    if resp.status_code != 200:
        click.echo(click.style(f"Failed: HTTP {resp.status_code}", fg="red"))
        sys.exit(1)
    data = resp.json()
    rows = data.get("pending_approvals", []) or []
    if not rows:
        click.echo("No pending approvals.")
        return
    click.echo(f"{len(rows)} pending:")
    for r in rows:
        rid = r.get("approval_id") or r.get("id") or "?"
        name = r.get("workflow_name") or r.get("agent_name") or rid
        maturity = r.get("maturity_level", "")
        agent = r.get("agent_name", "")
        line = f"  {rid}: {name}"
        if agent:
            line += f" (agent: {agent})"
        if maturity:
            line += f" [{maturity}]"
        click.echo(line)


def _decide(decision: str, approval_id: str, token: str | None):
    tok = _integ._resolve_token()
    if not tok and not token:
        click.echo(click.style(
            "Not authenticated. Run `atom-os login` first.", fg="red"))
        sys.exit(1)
    try:
        resp = _integ._request(
            "POST",
            f"/api/agent-governance/{decision}/{approval_id}",
            token=token or tok,
        )
    except requests.ConnectionError:
        click.echo(click.style(f"Cannot reach Atom at {_base_url()}", fg="red"))
        sys.exit(1)
    if resp.status_code == 404:
        click.echo(click.style(f"Approval {approval_id} not found.", fg="red"))
        sys.exit(1)
    if resp.status_code != 200:
        click.echo(click.style(
            f"{decision.capitalize()} failed: HTTP {resp.status_code}", fg="red"))
        sys.exit(1)
    message = ""
    try:
        message = resp.json().get("message", "")
    except ValueError:
        pass
    click.echo(click.style(
        message or f"{approval_id} {decision}d.", fg="green"))


@approvals_cli.command("approve")
@click.argument("approval_id")
@click.option("--token", default=None, help="Explicit JWT")
def approve(approval_id: str, token: str | None):
    """Approve a pending workflow submission."""
    _decide("approve", approval_id, token)


@approvals_cli.command("reject")
@click.argument("approval_id")
@click.option("--token", default=None, help="Explicit JWT")
def reject(approval_id: str, token: str | None):
    """Reject a pending workflow submission."""
    _decide("reject", approval_id, token)
