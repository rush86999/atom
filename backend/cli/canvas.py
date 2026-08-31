"""Atom OS CLI — Canvas commands (round 80v2: completes the CLI column).

    atom-os canvas list            GET /api/canvas/
    atom-os canvas view <id>       GET /api/canvas/<id>

Same HTTP seam (cli.integrations._request) and auth resolution as all
CLI commands.
"""
import json
import sys

import click
import requests

from cli.integrations import _base_url
from cli import integrations as _integ


@click.group("canvas")
def canvas_cli():
    """List and inspect Atom canvases."""
    pass


@canvas_cli.command("list")
@click.option("--token", default=None, help="Explicit JWT")
def list_canvases(token: str | None):
    """List available canvases."""
    tok = _integ._resolve_token()
    if not tok and not token:
        click.echo(click.style(
            "Not authenticated. Run `atom-os login` first.", fg="red"))
        sys.exit(1)
    try:
        resp = _integ._request("GET", "/api/canvas/", token=token or tok)
    except requests.ConnectionError:
        click.echo(click.style(f"Cannot reach Atom at {_base_url()}", fg="red"))
        sys.exit(1)
    if resp.status_code != 200:
        click.echo(click.style(f"Failed: HTTP {resp.status_code}", fg="red"))
        sys.exit(1)
    payload = resp.json()
    # GET /api/canvas/ returns {"success", "canvases", "count", "total"} —
    # the old code iterated the dict itself (crashing on str.get) and read
    # `id` where items carry `canvas_id`. Prefer the server-derived
    # display_title (never a raw UUID).
    rows = payload.get("canvases") if isinstance(payload, dict) else payload
    if not rows:
        click.echo("No canvases found.")
        return
    click.echo(f"{len(rows)} canvases:")
    for c in rows:
        ctype = c.get("canvas_type") or c.get("type") or ""
        cid = c.get("canvas_id") or c.get("id")
        title = (c.get("display_title") or c.get("title")
                 or c.get("name") or cid or "—")
        line = f"  {cid}: {title}"
        if ctype:
            line += f" ({ctype})"
        click.echo(line)


@canvas_cli.command("view")
@click.argument("canvas_id")
@click.option("--token", default=None, help="Explicit JWT")
def view_canvas(canvas_id: str, token: str | None):
    """View a canvas's metadata and components."""
    tok = _integ._resolve_token()
    if not tok and not token:
        click.echo(click.style(
            "Not authenticated. Run `atom-os login` first.", fg="red"))
        sys.exit(1)
    try:
        resp = _integ._request("GET", f"/api/canvas/{canvas_id}", token=token or tok)
    except requests.ConnectionError:
        click.echo(click.style(f"Cannot reach Atom at {_base_url()}", fg="red"))
        sys.exit(1)
    if resp.status_code == 404:
        click.echo(click.style(f"Canvas {canvas_id} not found.", fg="red"))
        sys.exit(1)
    if resp.status_code != 200:
        click.echo(click.style(f"Failed: HTTP {resp.status_code}", fg="red"))
        sys.exit(1)
    data = resp.json()
    click.echo(click.style(data.get("title") or canvas_id, fg="cyan", bold=True))
    if data.get("description"):
        click.echo(f"  {data['description']}")
    components = data.get("components") or []
    if components:
        click.echo(f"\n  {len(components)} component(s):")
        for comp in components:
            comp_type = comp.get("type", "unknown")
            label = comp.get("title") or comp.get("label") or comp_type
            click.echo(f"    · [{comp_type}] {label}")
