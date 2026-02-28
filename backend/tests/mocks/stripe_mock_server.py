"""
Stripe Mock Server Wrapper

Provides Docker container management for stripe/stripe-mock server.
This enables deterministic testing without network calls or rate limits.
"""

import logging
import time
from typing import Optional

import docker
import requests
from docker.errors import DockerException
from docker.models.containers import Container

logger = logging.getLogger(__name__)

# Configuration
STRIPE_MOCK_IMAGE = "stripe/stripe-mock:latest"
STRIPE_MOCK_PORT = 12111
STRIPE_MOCK_HOST = "localhost"
STRIPE_MOCK_URL = f"http://{STRIPE_MOCK_HOST}:{STRIPE_MOCK_PORT}"


class StripeMockError(Exception):
    """Custom exception for stripe-mock errors"""
    pass


def start_stripe_mock() -> Container:
    """
    Start the stripe-mock Docker container.

    Spawns stripe/stripe-mock:latest container with port 12111 exposed.
    The container will automatically start stripe-mock server listening on port 12111.

    Returns:
        Container: Docker container object

    Raises:
        StripeMockError: If container fails to start or Docker is unavailable

    Example:
        >>> container = start_stripe_mock()
        >>> # Container is now running on http://localhost:12111
        >>> stop_stripe_mock(container)
    """
    try:
        client = docker.from_env()

        # Check if container is already running
        try:
            existing = client.containers.get("atom-stripe-mock")
            if existing.status == "running":
                logger.info(f"stripe-mock container already running (id: {existing.id[:12]})")
                return existing
            else:
                # Remove stopped container
                existing.remove(force=True)
                logger.info("Removed existing stopped stripe-mock container")
        except docker.errors.NotFound:
            pass  # No existing container, proceed to create new one

        # Pull latest image if not present
        try:
            logger.info(f"Pulling {STRIPE_MOCK_IMAGE} (this may take a moment on first run)...")
            client.images.pull(STRIPE_MOCK_IMAGE.split(":")[0], STRIPE_MOCK_IMAGE.split(":")[1])
            logger.info("Image pull complete")
        except DockerException as e:
            logger.warning(f"Failed to pull image (may already exist): {e}")

        # Start container with port mapping
        # Format: {container_port: host_port}
        container = client.containers.run(
            STRIPE_MOCK_IMAGE,
            name="atom-stripe-mock",
            ports={f"{STRIPE_MOCK_PORT}/tcp": STRIPE_MOCK_PORT},
            detach=True,
            remove=True,  # Auto-remove on stop
        )

        logger.info(f"Started stripe-mock container (id: {container.id[:12]})")

        # Wait for server to be ready
        # stripe-mock returns 401 with error message when ready (requires auth)
        max_wait = 30  # seconds
        for i in range(max_wait):
            try:
                response = requests.get(f"{STRIPE_MOCK_URL}/", timeout=1)
                # Any response means server is up
                if response.status_code in [200, 401]:
                    logger.info(f"stripe-mock server ready after {i+1}s")
                    break
            except requests.exceptions.RequestException:
                if i < max_wait - 1:
                    time.sleep(1)
        else:
            raise StripeMockError(
                f"stripe-mock server did not become ready after {max_wait}s"
            )

        return container

    except DockerException as e:
        raise StripeMockError(f"Docker error starting stripe-mock: {e}")
    except Exception as e:
        raise StripeMockError(f"Unexpected error starting stripe-mock: {e}")


def stop_stripe_mock(container: Container) -> None:
    """
    Stop and remove the stripe-mock container.

    Args:
        container: Docker container object from start_stripe_mock()

    Raises:
        StripeMockError: If container fails to stop

    Example:
        >>> container = start_stripe_mock()
        >>> stop_stripe_mock(container)
    """
    try:
        if container:
            logger.info(f"Stopping stripe-mock container (id: {container.id[:12]})...")
            container.stop(timeout=5)
            logger.info("stripe-mock container stopped")
    except DockerException as e:
        raise StripeMockError(f"Docker error stopping stripe-mock: {e}")
    except Exception as e:
        raise StripeMockError(f"Unexpected error stopping stripe-mock: {e}")


def get_stripe_mock_url() -> str:
    """
    Get the URL for the stripe-mock server.

    Returns:
        str: stripe-mock server URL (http://localhost:12111)

    Example:
        >>> url = get_stripe_mock_url()
        >>> print(url)
        'http://localhost:12111'
    """
    return STRIPE_MOCK_URL


def is_stripe_mock_running() -> bool:
    """
    Check if stripe-mock server is running and accessible.

    Makes a simple HTTP GET request to the stripe-mock server.

    Returns:
        bool: True if server is responding, False otherwise

    Example:
        >>> if is_stripe_mock_running():
        ...     print("stripe-mock is available")
        ... else:
        ...     print("stripe-mock is not running")
    """
    try:
        # stripe-mock returns 401 when ready (requires auth)
        response = requests.get(f"{STRIPE_MOCK_URL}/", timeout=1)
        return response.status_code in [200, 401]
    except requests.exceptions.RequestException:
        return False


__all__ = [
    "start_stripe_mock",
    "stop_stripe_mock",
    "get_stripe_mock_url",
    "is_stripe_mock_running",
    "StripeMockError",
    "STRIPE_MOCK_URL",
]
