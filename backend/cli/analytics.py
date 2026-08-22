"""Atom OS CLI — Analytics command (round 80x: completes the CLI column).

    atom-os analytics [--window 1h|24h|7d|30d]

GET /api/analytics/dashboard/kpis — same endpoint as the mobile
AnalyticsDashboardScreen and desktop AnalyticsPanel.
"""
import os
import sys

import click
import requests

from cli.integrations import _base_url
from cli import integrations as _integ

WINDOWS = ("1h", "24h", "7d", "30d")


@click.command("analytics")
@click.option("--window", "time_window",
              type=click.Choice(WINDOWS), default="24h",
              help="Aggregation window")
@click.option("--token", default=None, help="Explicit JWT")
def analytics(time_window: str, token: str | None):
    """Print execution KPIs for the selected window."""
    tok = _integ._resolve_token()
    if not tok and not token:
        click.echo(click.style(
            "Not authenticated. Run `atom-os login` first "
            "(or set ATOM_TOKEN).", fg="red"))
        sys.exit(1)
    try:
        resp = _integ._request(
            "GET",
            f"/api/analytics/dashboard/kpis?time_window={time_window}",
            token=token or tok,
        )
    except requests.ConnectionError:
        click.echo(click.style(f"Cannot reach Atom at {_base_url()}", fg="red"))
        sys.exit(1)
    if resp.status_code != 200:
        click.echo(click.style(f"Failed: HTTP {resp.status_code}", fg="red"))
        sys.exit(1)
    k = resp.json()
    rate = k.get("success_rate")
    rate_s = f"{round(rate * 100)}%" if isinstance(rate, (int, float)) else "—"
    dur = k.get("average_duration_seconds")
    dur_s = f"{round(dur)}s avg" if isinstance(dur, (int, float)) else ""
    click.echo(click.style(
        f"Analytics ({time_window})", fg="cyan", bold=True))
    click.echo(f"  Executions:      {k.get('total_executions', '—')}")
    click.echo(f"  Success rate:    {rate_s}")
    click.echo(f"  Failures:        {k.get('failed_executions', '—')}")
    if dur_s:
        click.echo(f"  Avg duration:    {dur_s}")
    users = k.get("unique_users")
    workflows = k.get("unique_workflows")
    if users is not None:
        click.echo(f"  Unique users:    {users}")
    if workflows is not None:
        click.echo(f"  Unique flows:    {workflows}")
