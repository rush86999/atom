"""Mini-app runtime factory — fail-closed Firecracker selection.

Mini apps execute ONLY in Firecracker microVMs. Unlike the generic
``core.sandbox_runtime.base.get_runtime()`` (which falls back to Docker or a
Null runtime when Firecracker isn't provisioned), ``get_miniapp_runtime()``
**fails closed**: it raises ``RuntimeError`` unless a real Firecracker microVM
runtime is available.

Availability requires (all of):
  * Linux host (KVM-enabled — `/dev/kvm` present),
  * the ``firecracker`` binary on PATH,
  * ``FIRECRACKER_KERNEL_IMAGE`` resolving to a real ``vmlinux`` file,
  * ``FIRECRACKER_ROOTFS_TEMPLATE`` resolving to the base ext4 rootfs,
  * ``ATOM_MINIAAP_RUNTIME`` == ``firecracker`` (anything else → fail closed).

There is NO Docker/E2B fallback for mini apps.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


# Mini-app runtime selector. Anything other than "firecracker" fails closed.
ATOM_MINIAAP_RUNTIME = "ATOM_MINIAAP_RUNTIME"
REQUIRED_RUNTIME = "firecracker"

# Rootfs directory for operator-built per-app rootfs images.
MINIAPP_ROOTFS_DIR_ENV = "MINIAPP_ROOTFS_DIR"
DEFAULT_MINIAPP_ROOTFS_DIR = os.path.join("data", "mini_app_rootfs")


def get_miniapp_rootfs_dir() -> str:
    """Directory holding per-app rootfs images (``miniapp-{app_id}.ext4``)."""
    return os.getenv(MINIAPP_ROOTFS_DIR_ENV, DEFAULT_MINIAPP_ROOTFS_DIR)


def _env_runtime() -> str:
    return os.getenv(ATOM_MINIAAP_RUNTIME, REQUIRED_RUNTIME).strip().lower()


def get_miniapp_runtime():
    """Build a ``FirecrackerRuntime`` or raise ``RuntimeError`` (fail closed).

    Never returns a Docker/Null fallback. Raises with an actionable message
    pointing at ``docs/deployment/FIRECRACKER_HOST_SETUP.md`` / the operator
    script when the host isn't provisioned.

    Uses the STRICT ``is_provisioned_for()`` probe (requires the base rootfs
    template when no per-app image is given), NOT the cheap ``is_available()``
    probe used by the generic ``get_runtime()`` factory.
    """
    from core.sandbox_runtime.firecracker_runner import (
        FirecrackerRuntime,
        get_kernel_image,
        get_rootfs_template,
        is_available,
        is_provisioned_for,
    )

    runtime = _env_runtime()
    if runtime != REQUIRED_RUNTIME:
        raise RuntimeError(
            f"Mini apps require the Firecracker runtime, but "
            f"{ATOM_MINIAAP_RUNTIME}={runtime!r}. Set {ATOM_MINIAAP_RUNTIME}=firecracker."
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
            "scripts/build_miniapp_rootfs.sh --base to provision the host."
        )

    logger.debug("Mini-app Firecracker runtime available")
    return FirecrackerRuntime()
