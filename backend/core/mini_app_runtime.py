"""Mini-app runtime factory — fail-closed Firecracker selection (+ DEV docker).

Mini apps execute ONLY in Firecracker microVMs in production. Unlike the
generic ``core.sandbox_runtime.base.get_runtime()`` (which falls back to
Docker or a Null runtime when Firecracker isn't provisioned),
``get_miniapp_runtime()`` **fails closed**: it raises ``RuntimeError`` unless
a real Firecracker microVM runtime is available.

Availability requires (all of):
  * Linux host (KVM-enabled — ``/dev/kvm`` present),
  * the ``firecracker`` binary on PATH,
  * ``FIRECRACKER_KERNEL_IMAGE`` resolving to a real ``vmlinux`` file,
  * ``FIRECRACKER_ROOTFS_TEMPLATE`` resolving to the base ext4 rootfs,
  * ``ATOM_MINIAAP_RUNTIME`` == ``firecracker`` (default).

There is NO Docker/E2B fallback for mini apps — with one, explicitly opt-in
exception for local development: ``ATOM_MINIAAP_RUNTIME=docker-dev`` selects
``MiniAppDevRuntime`` (same guest agent + JSON-line protocol in a Docker
container) for hosts where Firecracker cannot run (macOS). It is refused
outright when ``ENVIRONMENT=production`` — production mini apps always run
in microVMs. See ``docs/deployment/MINIAPP_LOCAL_DEV.md``.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


# Mini-app runtime selector. "firecracker" (default) is the production path;
# "docker-dev" is the DEV-ONLY local execution mode. Anything else fails
# closed.
ATOM_MINIAAP_RUNTIME = "ATOM_MINIAAP_RUNTIME"
REQUIRED_RUNTIME = "firecracker"
DEV_RUNTIME = "docker-dev"

# Rootfs directory for operator-built per-app rootfs images.
MINIAPP_ROOTFS_DIR_ENV = "MINIAPP_ROOTFS_DIR"
DEFAULT_MINIAPP_ROOTFS_DIR = os.path.join("data", "mini_app_rootfs")


def get_miniapp_rootfs_dir() -> str:
    """Directory holding per-app rootfs images (``miniapp-{app_id}.ext4``)."""
    return os.getenv(MINIAPP_ROOTFS_DIR_ENV, DEFAULT_MINIAPP_ROOTFS_DIR)


def _env_runtime() -> str:
    return os.getenv(ATOM_MINIAAP_RUNTIME, REQUIRED_RUNTIME).strip().lower()


def _is_production() -> bool:
    # Canonical production signal for this repo (core/config.py is_production).
    return str(os.getenv("ENVIRONMENT", "development") or "development").strip().lower() == "production"


def is_docker_dev_selected() -> bool:
    """True when the DEV-only docker runtime is selected (and permissible).

    ``ATOM_MINIAAP_RUNTIME=docker-dev`` AND not production. Callers use this
    to skip Firecracker-specific provisioning gates (e.g. the ext4 rootfs
    check in ``prepare_runtime`` — a macOS dev host can't build ext4); the
    docker daemon itself is probed later by ``get_miniapp_runtime``.
    """
    return _env_runtime() == DEV_RUNTIME and not _is_production()


def _dev_hint() -> str:
    if _is_production():
        return ""
    return (
        " For local development on a non-Linux host (e.g. macOS), set "
        f"{ATOM_MINIAAP_RUNTIME}=docker-dev (Docker required) — see "
        "docs/deployment/MINIAPP_LOCAL_DEV.md."
    )


def get_miniapp_runtime():
    """Build a mini-app runtime or raise ``RuntimeError`` (fail closed).

    Never silently falls back: ``firecracker`` returns a ``FirecrackerRuntime``
    only when the host is fully provisioned; ``docker-dev`` returns a
    ``MiniAppDevRuntime`` only when the Docker daemon is reachable AND the
    process is not production; anything else raises with an actionable
    message.

    The Firecracker path uses the STRICT ``is_provisioned_for()`` probe
    (requires the base rootfs template when no per-app image is given), NOT
    the cheap ``is_available()`` probe used by the generic ``get_runtime()``
    factory.
    """
    runtime = _env_runtime()

    if runtime == DEV_RUNTIME:
        if _is_production():
            raise RuntimeError(
                f"{ATOM_MINIAAP_RUNTIME}={DEV_RUNTIME!r} is a DEV-ONLY local "
                "execution mode and is refused when ENVIRONMENT=production. "
                "Mini apps must run in Firecracker microVMs in production."
            )
        from core.sandbox_runtime.miniapp_dev_runner import (
            MiniAppDevRuntime,
            is_available as dev_available,
        )

        if not dev_available():
            raise RuntimeError(
                "docker-dev runtime unavailable: the Docker daemon is not "
                "reachable. Start Docker Desktop (macOS) or the docker "
                "daemon, then retry. Dev images are built locally — see "
                "docs/deployment/MINIAPP_LOCAL_DEV.md."
            )
        logger.debug("Mini-app docker-dev runtime available")
        return MiniAppDevRuntime()

    if runtime != REQUIRED_RUNTIME:
        raise RuntimeError(
            f"Mini apps require {ATOM_MINIAAP_RUNTIME}="
            f"'{REQUIRED_RUNTIME}' (production) or '{DEV_RUNTIME}' (local "
            f"development), but got {runtime!r}.{_dev_hint()}"
        )

    from core.sandbox_runtime.firecracker_runner import (
        FirecrackerRuntime,
        get_kernel_image,
        get_rootfs_template,
        is_available,
        is_provisioned_for,
    )

    # The mini-app factory must verify the base rootfs template resolves (apps
    # without dependencies boot from it). is_provisioned_for() composes
    # is_available() (Linux + binary + kernel) with the template check.
    if not is_provisioned_for(None):
        kernel = get_kernel_image()
        template = get_rootfs_template()
        missing = []
        if not is_available():
            missing.append("Linux host with the 'firecracker' binary")
            if not kernel or not os.path.isfile(kernel):
                missing.append(f"FIRECRACKER_KERNEL_IMAGE={kernel!r} (vmlinux)")
        if not template or not os.path.isfile(template):
            missing.append(f"FIRECRACKER_ROOTFS_TEMPLATE={template!r}")
        raise RuntimeError(
            "Firecracker runtime unavailable for mini apps "
            f"(missing: {', '.join(missing) or 'unknown'}). "
            "See docs/deployment/FIRECRACKER_HOST_SETUP.md and run "
            f"scripts/build_miniapp_rootfs.sh --base to provision the host.{_dev_hint()}"
        )

    logger.debug("Mini-app Firecracker runtime available")
    return FirecrackerRuntime()
