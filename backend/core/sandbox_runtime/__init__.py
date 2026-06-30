"""SandboxRuntime package — Phase D backends.

Public API:
    SandboxRuntime, SandboxExecResult, get_runtime, NullRuntime
    (from .base)
    DockerRuntime (from .docker_runner)
    FirecrackerRuntime (from .firecracker_runner, lazy)
    E2BRuntime (from .e2b_runner, lazy)
"""
from core.sandbox_runtime.base import (  # noqa: F401
    NullRuntime,
    SandboxExecResult,
    SandboxRuntime,
    get_runtime,
)
