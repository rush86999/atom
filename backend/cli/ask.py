"""Terminal agent-chat journey (round 80t).

`atom-os ask "message"` posts to the live chat orchestrator
(POST /api/chat/message) and prints the agent's reply. Completes the
terminal parity gap left by the placeholder `execute` command.
"""
import os
import sys

import click
import requests

from cli.integrations import _base_url
from cli import integrations as _integ


@click.command("ask")
@click.argument("message", required=False)
@click.option("--session", default=None, help="Conversation session ID")
@click.option("--token", default=None, help="Explicit JWT")
def ask(message: str | None, session: str | None, token: str | None):
    """Send MESSAGE to the Atom agent and print its reply."""
    if not message:
        click.echo(click.style("Error: message required", fg="red"))
        click.echo('Usage: atom-os ask "create a report"')
        sys.exit(1)
    tok = _integ._require_token()
    try:
        resp = _integ._request(
            "POST",
            "/api/chat/message",
            token=token or tok,
            json_body={
                "message": message,
                "user_id": "cli",
                **({"session_id": session} if session else {}),
            },
            timeout=120,
        )
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
        click.echo(click.style(f"Ask failed: {detail or resp.status_code}",
                               fg="red"))
        sys.exit(1)
    data = resp.json()
    reply = data.get("message") or data.get("response") or ""
    session_id = data.get("session_id")
    confidence = data.get("confidence")
    if reply:
        click.echo(reply)
    else:
        click.echo(click.style("(empty response)", fg="yellow"))
    meta = []
    if session_id:
        meta.append(f"session: {session_id}")
    if confidence is not None:
        meta.append(f"confidence: {confidence:.2f}")
    intent = data.get("intent")
    if intent:
        meta.append(f"intent: {intent}")
    if meta:
        click.echo(click.style("  " + " · ".join(meta), fg="bright_black"))
