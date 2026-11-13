"""Shared mocks for the ``HazardSandbox`` container lifecycle.

``core.skill_sandbox`` deliberately does **not** call ``containers.run``:

* docker-py's model-level ``run`` has no ``timeout`` keyword (passing one
  raises ``TypeError`` before a container exists -- the #918 outage), and
* ``run`` blocks until the container exits, so it cannot hand back the
  container handle before execution starts (cleanup would have to look the
  container up by name, which a late-starting container can escape).

The sandbox now prepares the image, creates the container, starts/waits on it
under a deadline and removes it explicitly.  Test doubles therefore need a
container object with docker-py's ``wait``/``logs``/``remove`` behaviour and a
client whose ``containers.create`` returns it.

This module is imported by tests only; it is not collected as a test itself.
"""
from __future__ import annotations

from typing import Any, Optional
from unittest.mock import Mock


class MockNotFound(Exception):
    """Stands in for ``docker.errors.NotFound``.

    ``skill_sandbox`` matches docker errors by class name (``NotFound``) so it
    keeps working under the module-mock patterns used across the suite; the
    name is all these doubles need to provide.
    """


MockNotFound.__name__ = "NotFound"


def make_container(
    *,
    stdout: bytes = b"",
    stderr: bytes = b"",
    exit_code: int = 0,
    name: str = "skill_mock0001",
    container_id: str = "0" * 64,
) -> Mock:
    """A container double that exits ``exit_code`` with ``stdout``/``stderr``."""
    container = Mock()
    container.id = container_id
    container.name = name
    container.wait.return_value = {"StatusCode": exit_code}

    def _logs(**kwargs: Any) -> bytes:
        want_stdout = kwargs.get("stdout", True)
        want_stderr = kwargs.get("stderr", True)
        if want_stdout and not want_stderr:
            return stdout
        if want_stderr and not want_stdout:
            return stderr
        return (stdout or b"") + (stderr or b"")

    container.logs.side_effect = _logs
    container.remove.return_value = None
    return container


def install_container(
    client: Any,
    *,
    stdout: bytes = b"",
    stderr: bytes = b"",
    exit_code: int = 0,
    name: str = "skill_mock0001",
    container_id: str = "0" * 64,
    wait_side_effect: Optional[Any] = None,
) -> Mock:
    """Wire ``client.containers.create`` to return a well-behaved container."""
    created = make_container(
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        name=name,
        container_id=container_id,
    )
    if wait_side_effect is not None:
        created.wait.side_effect = wait_side_effect
    client.containers.create.return_value = created
    return created
