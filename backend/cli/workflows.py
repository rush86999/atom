"""Atom OS CLI — Workflow commands (round 80w: CLI parity with desktop 80u).

    atom-os workflows list        GET /api/mobile/workflows
    atom-os workflows run <id>    POST /api/mobile/workflows/trigger

Same HTTP seam (cli.integrations._request) and auth resolution as the
integrations commands.
"""
import os
import sys
from typing import Optional

import click
import requests

from cli.integrations import _base_url
from cli import integrations as _integ


@click.group("workflows")
def workflows_cli():
    """List and trigger Atom workflows."""
    pass


@workflows_cli.command("list")
@click.option("--token", default=None, help="Explicit JWT")
def list_workflows(token: Optional[str] = None):
    """List available workflows."""
    tok = _integ._require_token()
    try:
        resp = _integ._request("GET", "/api/mobile/workflows", token=token or tok)
    except requests.ConnectionError:
        click.echo(click.style(f"Cannot reach Atom at {_base_url()}", fg="red"))
        sys.exit(1)
    if resp.status_code != 200:
        click.echo(click.style(f"Failed: HTTP {resp.status_code}", fg="red"))
        sys.exit(1)
    rows = resp.json()
    if not rows:
        click.echo("No workflows found.")
        return
    click.echo(f"{len(rows)} workflows:")
    for wf in rows:
        status = wf.get("status") or "—"
        click.echo(f"  {wf.get('id')}: {wf.get('name')} ({status})")


@workflows_cli.command("run")
@click.argument("workflow_id")
@click.option("--token", default=None, help="Explicit JWT")
def run_workflow(workflow_id: str, token: Optional[str] = None):
    """Trigger WORKFLOW_ID and print the execution reference."""
    tok = _integ._require_token()
    try:
        resp = _integ._request(
            "POST",
            "/api/mobile/workflows/trigger",
            token=token or tok,
            json_body={"workflow_id": workflow_id},
            timeout=60,
        )
    except requests.ConnectionError:
        click.echo(click.style(f"Cannot reach Atom at {_base_url()}", fg="red"))
        sys.exit(1)
    if resp.status_code != 200:
        click.echo(click.style(
            f"Trigger failed: HTTP {resp.status_code}", fg="red"))
        sys.exit(1)
    data = resp.json()
    exec_id = data.get("execution_id") or data.get("id") or "(no id)"
    click.echo(click.style(
        f"Triggered {workflow_id} — execution {exec_id} "
        f"({data.get('status', 'running')})", fg="green"))
