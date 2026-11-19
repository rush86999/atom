#!/usr/bin/env python3
"""Operator-only provisioning for an on-host transcription provider.

Atom's ordinary local-model registration endpoint deliberately rejects
loopback and private addresses (SSRF guard). An operator who runs an
OpenAI-compatible transcription service inside the backend's network namespace
therefore provisions that one provider directly, with this command.

Run from ``backend/`` with the application's ``DATABASE_URL``:

    python -m scripts.register_local_transcription \
        --workspace-id <workspace-id> \
        --name "On-host Whisper" \
        --base-url http://127.0.0.1:9000/v1 \
        --model whisper-1 \
        --audio-input-cost-per-second-usd 0

The command creates exactly one custom local provider and one capability row
with transcription enabled, chat disabled, and the explicit per-second audio
rate. It performs no network I/O, stores no API key, and never updates or
deletes existing rows. Re-running it with the identical configuration is a
no-op; any changed value or collision is refused.
"""
from __future__ import annotations

import argparse
import ipaddress
import math
import os
import sys
import uuid
from urllib.parse import urlsplit, urlunsplit

_PROVIDER_TYPE = "custom"
_MAX_TEXT_LENGTH = 200


class ProvisionError(Exception):
    """The requested configuration conflicts with existing data."""


def _required_text(value: str, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} is required")
    if len(text) > _MAX_TEXT_LENGTH:
        raise ValueError(f"{label} must be at most {_MAX_TEXT_LENGTH} characters")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise ValueError(f"{label} must not contain control characters")
    return text


def parse_loopback_base_url(raw: str) -> str:
    """Validate and canonicalize an on-host OpenAI-compatible base URL.

    Only ``http://<numeric-loopback>:<explicit-port>/v1`` is accepted. No DNS
    aliases, userinfo, query string, fragment, or extra path is allowed.
    """
    value = str(raw or "").strip()
    if not value:
        raise ValueError("base URL is required")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("base URL is not a valid URL") from exc

    if parsed.scheme != "http":
        raise ValueError("base URL must use http")
    if "@" in parsed.netloc or parsed.username is not None or parsed.password is not None:
        raise ValueError("base URL must not contain userinfo")
    if parsed.query or parsed.fragment:
        raise ValueError("base URL must not contain a query string or fragment")
    if parsed.path not in ("/v1", "/v1/"):
        raise ValueError("base URL path must be /v1")

    host = parsed.hostname
    if not host:
        raise ValueError("base URL must include a loopback address")
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("base URL host must be a numeric loopback address") from exc
    if not address.is_loopback:
        raise ValueError("base URL host must be a loopback address")

    if port is None:
        raise ValueError("base URL must include an explicit port")
    if not 1 <= port <= 65535:
        raise ValueError("base URL port must be between 1 and 65535")

    host_text = f"[{address}]" if address.version == 6 else str(address)
    return urlunsplit(("http", f"{host_text}:{port}", "/v1", "", ""))


def parse_audio_rate(raw: object) -> float:
    """Parse the explicit, finite, non-negative USD-per-second rate."""
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("audio cost per second must be a number") from exc
    if not math.isfinite(value):
        raise ValueError("audio cost per second must be finite")
    if value < 0:
        raise ValueError("audio cost per second must be zero or greater")
    return value


def _url_argument(raw: str) -> str:
    try:
        return parse_loopback_base_url(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def _rate_argument(raw: str) -> float:
    try:
        return parse_audio_rate(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def _stable_id(kind: str, *parts: str) -> str:
    material = ":".join(("atom:local-transcription", kind, *parts))
    return str(uuid.uuid5(uuid.NAMESPACE_URL, material))


def _provider_mismatches(provider, *, workspace_id: str, tenant_id: str,
                         name: str, base_url: str) -> list[str]:
    mismatches: list[str] = []
    if provider.workspace_id != workspace_id:
        mismatches.append("workspace")
    if provider.tenant_id != tenant_id:
        mismatches.append("tenant")
    if provider.name != name:
        mismatches.append("display name")
    if provider.provider_type != _PROVIDER_TYPE:
        mismatches.append("provider type")
    if provider.base_url != base_url:
        mismatches.append("base URL")
    if provider.api_key:
        mismatches.append("API key")
    if not bool(provider.is_active):
        mismatches.append("active state")
    return mismatches


def _capability_mismatches(capability, *, provider_id: str, workspace_id: str,
                           model_id: str, rate: float) -> list[str]:
    mismatches: list[str] = []
    if capability.provider_id != provider_id:
        mismatches.append("provider")
    if capability.workspace_id != workspace_id:
        mismatches.append("workspace")
    if capability.model_id != model_id:
        mismatches.append("model")
    if not bool(capability.supports_transcription):
        mismatches.append("transcription")
    if bool(capability.supports_tools):
        mismatches.append("tools")
    if bool(capability.supports_vision):
        mismatches.append("vision")
    if bool(capability.supports_reasoning):
        mismatches.append("reasoning")
    if not hasattr(capability, "supports_chat") or bool(capability.supports_chat):
        mismatches.append("chat")
    try:
        stored_rate = float(capability.audio_input_cost_per_second_usd)
    except (TypeError, ValueError):
        stored_rate = None
    if (stored_rate is None or not math.isfinite(stored_rate)
            or stored_rate != rate):
        mismatches.append("audio rate")
    return mismatches


def provision_local_transcription(
    db,
    *,
    workspace_id: str,
    name: str,
    base_url: str,
    model_id: str,
    audio_input_cost_per_second_usd: float,
) -> dict:
    """Provision one on-host transcription provider and model capability.

    The caller owns the transaction. No commit is issued here; the CLI uses
    ``get_db_session()``, which commits on success and rolls back on error.
    """
    from sqlalchemy.exc import IntegrityError

    from core.models import (
        LocalModelCapabilities,
        LocalModelProvider,
        Workspace,
    )

    workspace_id = _required_text(workspace_id, "workspace id")
    name = _required_text(name, "display name")
    model_id = _required_text(model_id, "model id")
    base_url = parse_loopback_base_url(base_url)
    rate = parse_audio_rate(audio_input_cost_per_second_usd)

    # The chat flag is required: provisioning on a schema that predates it
    # would silently create an audio-only model while this CLI reports chat
    # disabled, so fail closed instead.
    if not hasattr(LocalModelCapabilities, "supports_chat"):
        raise ProvisionError(
            "this database schema lacks LocalModelCapabilities.supports_chat; "
            "refusing to provision an audio-only model"
        )

    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).one_or_none()
    if workspace is None:
        raise ProvisionError(f"workspace {workspace_id!r} does not exist")
    tenant_id = str(workspace.tenant_id or "").strip()
    if not tenant_id:
        raise ProvisionError(f"workspace {workspace_id!r} has no tenant")

    provider_id = _stable_id("provider", workspace_id, name)
    capability_id = _stable_id("capability", provider_id, model_id)

    provider = db.query(LocalModelProvider).filter(
        LocalModelProvider.id == provider_id,
    ).one_or_none()
    provider_created = False
    if provider is not None:
        mismatches = _provider_mismatches(
            provider,
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            name=name,
            base_url=base_url,
        )
        if mismatches:
            raise ProvisionError(
                "an existing provider with the deterministic identity has a "
                f"different {', '.join(mismatches)}; refusing to change it"
            )
    else:
        name_collision = db.query(LocalModelProvider).filter(
            LocalModelProvider.workspace_id == workspace_id,
            LocalModelProvider.name == name,
        ).first()
        if name_collision is not None:
            raise ProvisionError(
                f"workspace {workspace_id!r} already has a provider named {name!r}"
            )
        url_collision = db.query(LocalModelProvider).filter(
            LocalModelProvider.workspace_id == workspace_id,
            LocalModelProvider.base_url == base_url,
        ).first()
        if url_collision is not None:
            raise ProvisionError(
                f"workspace {workspace_id!r} already has a provider at {base_url!r}"
            )
        provider = LocalModelProvider(
            id=provider_id,
            workspace_id=workspace_id,
            tenant_id=tenant_id,
            name=name,
            provider_type=_PROVIDER_TYPE,
            base_url=base_url,
            api_key=None,
            is_active=True,
        )
        provider_created = True

    capabilities = db.query(LocalModelCapabilities).filter(
        LocalModelCapabilities.provider_id == provider_id,
        LocalModelCapabilities.workspace_id == workspace_id,
    ).all()
    capability = next(
        (row for row in capabilities if row.id == capability_id), None)
    capability_created = False

    if capability is not None:
        if len(capabilities) != 1:
            raise ProvisionError(
                "the provider already has additional model capabilities; "
                "refusing to add or modify models"
            )
        mismatches = _capability_mismatches(
            capability,
            provider_id=provider_id,
            workspace_id=workspace_id,
            model_id=model_id,
            rate=rate,
        )
        if mismatches:
            raise ProvisionError(
                "the existing transcription capability has a different "
                f"{', '.join(mismatches)}; refusing to change it"
            )
    else:
        if capabilities:
            raise ProvisionError(
                "the provider already has a configured model; refusing to add "
                "another model"
            )
        values = {
            "id": capability_id,
            "provider_id": provider_id,
            "workspace_id": workspace_id,
            "model_id": model_id,
            "supports_tools": False,
            "supports_vision": False,
            "supports_reasoning": False,
            "supports_transcription": True,
            "supports_chat": False,
            "audio_input_cost_per_second_usd": rate,
        }
        capability = LocalModelCapabilities(**values)
        capability_created = True

    try:
        if provider_created:
            db.add(provider)
        if capability_created:
            db.add(capability)
        if provider_created or capability_created:
            db.flush()
    except IntegrityError:
        raise ProvisionError(
            "a conflicting provider or capability was created concurrently; "
            "rerun to verify the configuration"
        ) from None

    return {
        "provider_id": provider_id,
        "capability_id": capability_id,
        "workspace_id": workspace_id,
        "tenant_id": tenant_id,
        "name": name,
        "base_url": base_url,
        "model_id": model_id,
        "audio_input_cost_per_second_usd": rate,
        "created_provider": provider_created,
        "created_capability": capability_created,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Provision one operator-managed on-host OpenAI-compatible "
            "transcription provider and model capability."
        )
    )
    parser.add_argument("--workspace-id", required=True,
                        help="Existing workspace id that owns the provider")
    parser.add_argument("--name", required=True,
                        help="Stable provider display name")
    parser.add_argument("--base-url", required=True, type=_url_argument,
                        help="http://<numeric-loopback>:<port>/v1")
    parser.add_argument("--model", required=True,
                        help="Exact model id served by the transcription endpoint")
    parser.add_argument(
        "--audio-input-cost-per-second-usd",
        required=True,
        type=_rate_argument,
        metavar="USD_PER_SECOND",
        help="Explicit finite non-negative rate; 0 is a valid free rate",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Require the operator to supply the target database explicitly. Checking
    # before the DB import prevents the application's implicit development
    # fallback database from being provisioned by accident.
    if not str(os.environ.get("DATABASE_URL") or "").strip():
        print(
            "error: DATABASE_URL is required and must be set explicitly "
            "before running this command",
            file=sys.stderr,
        )
        return 1

    try:
        from core.database import get_db_session
    except Exception as exc:  # noqa: BLE001 - operator-facing import failure
        print(
            "error: could not import backend modules; run from backend/ "
            f"({type(exc).__name__})",
            file=sys.stderr,
        )
        return 1

    try:
        with get_db_session() as db:
            result = provision_local_transcription(
                db,
                workspace_id=args.workspace_id,
                name=args.name,
                base_url=args.base_url,
                model_id=args.model,
                audio_input_cost_per_second_usd=args.audio_input_cost_per_second_usd,
            )
    except ProvisionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - CLI reports and exits non-zero
        print(f"error: provisioning failed ({type(exc).__name__})",
              file=sys.stderr)
        return 1

    action = (
        "Provisioned"
        if result["created_provider"] or result["created_capability"]
        else "Already provisioned with identical configuration"
    )
    print(
        f"{action}: provider {result['provider_id']} ({result['name']}) at "
        f"{result['base_url']} in workspace {result['workspace_id']}.\n"
        f"Model {result['model_id']}: transcription enabled, chat disabled, "
        f"audio input cost {result['audio_input_cost_per_second_usd']} USD/second."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
