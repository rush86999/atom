"""Fail-closed sandbox for GENERATED mutation code.

`ContainerSandbox` (core/auto_dev/container_sandbox.py) silently falls back
to a HOST subprocess when Docker is unavailable — inherited environment, full
filesystem and network access (see its `_execute_subprocess`). That is
acceptable for its existing auto_dev callers; it is NOT acceptable for
env-curriculum mutation code, which is generated to alter training
environments. Here the contract is fail-closed: no container, no execution.

Plan: docs/architecture/ENV_HARNESS_ADOPTION_PLAN.md §Phase 1a.
"""

import logging
from typing import Any

from core.auto_dev.container_sandbox import ContainerSandbox

logger = logging.getLogger(__name__)


class MutationSandboxUnavailable(Exception):
    """Raised instead of falling back to host execution when Docker is absent."""


class FailClosedMutationSandbox(ContainerSandbox):
    """ContainerSandbox with the subprocess fallback removed.

    Mutations only ever run inside a `--network=none --read-only` container;
    if Docker is unavailable execution is REFUSED (MutationSandboxUnavailable),
    never degraded to a host process.
    """

    def __init__(self, **kwargs: Any):
        # Mutations have no legitimate need for the host network; refuse the
        # foot-gun rather than honouring it.
        if kwargs.get("enable_network"):
            raise ValueError(
                "FailClosedMutationSandbox refuses enable_network=True: "
                "generated mutation code runs network-isolated, always."
            )
        kwargs.setdefault("enable_network", False)
        super().__init__(**kwargs)

    async def execute_raw_python(
        self,
        tenant_id: str,
        code: str,
        input_params: dict[str, Any] | None = None,
        timeout: int | None = None,
        safety_level: str = "MEDIUM_RISK",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Execute mutation code, or raise if container isolation is unavailable.

        Overrides the parent specifically to remove its fallback branch:
        `self.docker_available` is re-verified per call, and a missing Docker
        daemon raises instead of reaching `_execute_subprocess`.
        """
        # Bypass the parent's cached property read: a daemon that died since
        # the last call must fail THIS call closed, not fall open.
        self._docker_available = _probe_docker()
        if not self._docker_available:
            logger.warning(
                "Mutation execution REFUSED (fail-closed): Docker unavailable "
                "for tenant %s — no host fallback exists for env mutations.",
                tenant_id,
            )
            raise MutationSandboxUnavailable(
                "Docker unavailable — mutation code is never executed on the "
                "host (fail-closed policy, ENV_HARNESS_ADOPTION_PLAN §1a)."
            )
        result = await ContainerSandbox.execute_raw_python(
            self,
            tenant_id=tenant_id,
            code=code,
            input_params=input_params,
            timeout=timeout,
            safety_level=safety_level,
            **kwargs,
        )
        # Defence in depth: if a future refactor of the parent reintroduces a
        # fallback, refuse the result instead of silently accepting it.
        if result.get("environment") != "docker":
            raise MutationSandboxUnavailable(
                f"Sandbox returned non-container environment "
                f"{result.get('environment')!r} — refusing result."
            )
        result["isolation"] = "container:network=none:fs=read-only"
        return result


async def execute_mutation(
    sandbox: FailClosedMutationSandbox,
    tenant_id: str,
    code: str,
    input_params: dict[str, Any] | None = None,
    timeout: int | None = None,
) -> dict[str, Any]:
    """Structured-result wrapper: refused executions come back as a payload
    (status "refused") instead of an exception, for callers that batch many
    mutations and want to keep going."""
    try:
        return await sandbox.execute_raw_python(
            tenant_id=tenant_id,
            code=code,
            input_params=input_params,
            timeout=timeout,
        )
    except MutationSandboxUnavailable as exc:
        return {
            "status": "refused",
            "output": str(exc),
            "execution_seconds": 0.0,
            "environment": None,
            "isolation": None,
        }


def _probe_docker() -> bool:
    """Fresh availability probe (parent caches; we need per-call truth)."""
    import subprocess

    try:
        result = subprocess.run(
            ["docker", "info"], capture_output=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False
