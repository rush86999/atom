from __future__ import annotations
"""
Webhook Security Utilities
Verify webhook signatures for security
"""

import hashlib
import hmac
import logging
import os

logger = logging.getLogger(__name__)


def get_environment() -> str:
    """Get current environment (development, staging, production)"""
    return os.getenv("ENVIRONMENT", "development")


def verify_webhook_signature(
    payload: bytes, signature: str, secret: str, algorithm: str = "sha256"
) -> bool:
    """
    Verify webhook signature using HMAC.

    Args:
        payload: Raw request body as bytes
        signature: Signature from request header (e.g., X-Slack-Signature)
        secret: Webhook secret for verification
        algorithm: Hash algorithm (default: sha256)

    Returns:
        True if signature valid, False otherwise
    """
    environment = get_environment()
    logger.debug(f"[SEC-DEBUG] Environment: {environment}, Signature present: {bool(signature)}")

    # Bypass verification in development ONLY if explicitly requested
    if environment == "development" and os.getenv("BYPASS_WEBHOOK_SIGNATURE") == "true":
        logger.warning("DEVELOPMENT ONLY: Bypassing webhook signature verification via explicit override")
        return True

    if not signature or not secret:
        logger.warning("Missing signature or secret for webhook verification")
        return False

    try:
        # Remove algorithm prefix if present (e.g., "sha256=")
        signature_clean = signature.replace(f"{algorithm}=", "")

        # Calculate expected signature
        expected = hmac.new(
            secret.encode("utf-8"), payload, getattr(hashlib, algorithm)
        ).hexdigest()

        # Use constant-time comparison to prevent timing attacks
        is_valid = hmac.compare_digest(signature_clean, expected)

        if not is_valid:
            logger.warning("Webhook signature verification failed")

        return is_valid

    except Exception as e:
        logger.error(f"Webhook signature verification error: {e}")
        return False


def verify_slack_webhook(
    payload: bytes, signature: str, timestamp: str, signing_secret: str
) -> bool:
    """
    Verify Slack webhook signature.

    Slack uses a special format: signature = hmac.join(timestamp, payload)

    Args:
        payload: Raw request body as bytes
        signature: X-Slack-Signature header value
        timestamp: X-Slack-Request-Timestamp header value
        signing_secret: Slack app signing secret

    Returns:
        True if signature valid, False otherwise
    """
    environment = get_environment()

    if environment == "development" and os.getenv("BYPASS_WEBHOOK_SIGNATURE") == "true":
        logger.warning("DEVELOPMENT ONLY: Bypassing Slack webhook verification via explicit override")
        return True

    if not signature or not timestamp or not signing_secret:
        logger.warning("Missing Slack webhook verification parameters")
        return False

    try:
        # Check for replay attacks (timestamp should be within 5 minutes)
        import time

        request_time = int(timestamp)
        current_time = int(time.time())

        if abs(current_time - request_time) > 300:  # 5 minutes
            logger.warning(f"Slack webhook timestamp too old: {timestamp}")
            return False

        # Create signature base string
        signature_base = f"v0:{timestamp}:".encode() + payload

        # Calculate expected signature
        expected_signature = (
            "v0="
            + hmac.new(signing_secret.encode("utf-8"), signature_base, hashlib.sha256).hexdigest()
        )

        # Compare signatures
        is_valid = hmac.compare_digest(signature, expected_signature)

        if not is_valid:
            logger.warning("Slack webhook signature verification failed")

        return is_valid

    except Exception as e:
        logger.error(f"Slack webhook verification error: {e}")
        return False


def verify_stripe_webhook(payload: bytes, signature: str, webhook_secret: str) -> bool:
    """
    Verify Stripe webhook signature.

    Args:
        payload: Raw request body as bytes
        signature: Stripe-Signature header value
        webhook_secret: Stripe webhook secret

    Returns:
        True if signature valid, False otherwise
    """
    environment = get_environment()

    if environment == "development" and os.getenv("BYPASS_WEBHOOK_SIGNATURE") == "true":
        logger.warning("DEVELOPMENT ONLY: Bypassing Stripe webhook verification via explicit override")
        return True

    if not signature or not webhook_secret:
        logger.warning("Missing Stripe webhook verification parameters")
        return False

    try:
        import stripe

        # Verify using Stripe's official library
        event = stripe.Webhook.construct_event(payload, signature, webhook_secret)

        logger.info(f"Stripe webhook verified: {event.type}")
        return True

    except Exception as e:
        logger.error(f"Stripe webhook verification error: {e}")
        return False


def verify_github_webhook(payload: bytes, signature: str, webhook_secret: str) -> bool:
    """
    Verify GitHub webhook signature.

    Args:
        payload: Raw request body as bytes
        signature: X-Hub-Signature-256 header value
        webhook_secret: GitHub webhook secret

    Returns:
        True if signature valid, False otherwise
    """
    environment = get_environment()

    if environment == "development" and os.getenv("BYPASS_WEBHOOK_SIGNATURE") == "true":
        logger.warning("DEVELOPMENT ONLY: Bypassing GitHub webhook verification via explicit override")
        return True

    if not signature or not webhook_secret:
        logger.warning("Missing GitHub webhook verification parameters")
        return False

    try:
        # GitHub uses SHA-256 HMAC
        return verify_webhook_signature(payload, signature, webhook_secret, "sha256")
    except Exception as e:
        logger.error(f"GitHub webhook verification error: {e}")
        return False


def verify_whatsapp_webhook(payload: bytes, signature: str, app_secret: str) -> bool:
    """
    Verify WhatsApp webhook signature.

    Args:
        payload: Raw request body as bytes
        signature: X-Hub-Signature-256 header value
        app_secret: WhatsApp App Secret

    Returns:
        True if signature valid, False otherwise
    """
    # Meta uses SHA-256 HMAC for WhatsApp Business API
    return verify_webhook_signature(payload, signature, app_secret, "sha256")


def _get_webhook_secret() -> str:
    """Resolve the webhook signing secret.

    SECURITY: prefer WEBHOOK_CLIENT_STATE_SECRET, then JWT_SECRET.
    Never fall back to a hardcoded constant — generate a random
    per-process secret instead (and warn) so signed data cannot
    be forged by attackers who know the historical default.
    """
    secret = os.getenv("WEBHOOK_CLIENT_STATE_SECRET") or os.getenv("JWT_SECRET")
    if secret:
        return secret
    # Per-process fallback — signed data won't survive restart, but
    # cannot be predicted by an attacker.
    import secrets as _secrets
    if not hasattr(_get_webhook_secret, "_fallback"):
        _get_webhook_secret._fallback = _secrets.token_urlsafe(32)
        import logging
        logging.getLogger(__name__).warning(
            "WEBHOOK_CLIENT_STATE_SECRET and JWT_SECRET both unset. "
            "Using random per-process secret — signed client state "
            "will not survive restart."
        )
    return _get_webhook_secret._fallback


def sign_client_state(data: str) -> str:
    """
    Sign a clientState string to prevent spoofing.
    Format: data::signature (double colon to avoid conflict with JSON content)
    """
    secret = _get_webhook_secret()
    signature = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()
    return f"{data}::{signature}"


def verify_client_state(signed_data: str) -> bool:
    """
    Verify a signed clientState string.
    """
    environment = get_environment()
    if environment == "development" and os.getenv("BYPASS_WEBHOOK_SIGNATURE") == "true":
        return True

    if not signed_data or "::" not in signed_data:
        return False

    try:
        data, signature = signed_data.rsplit("::", 1)
        secret = _get_webhook_secret()
        expected = hmac.new(secret.encode(), data.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
    except Exception:
        return False


def get_client_state_data(signed_data: str) -> str:
    """
    Extract the data part from a signed clientState.
    """
    if "::" not in signed_data:
        return signed_data
    return signed_data.rsplit("::", 1)[0]


def sign_client_state_with_connection(tenant_id: str, connection_id: str) -> str:
    """
    Sign a clientState containing tenant_id and connection_id.

    Encodes both IDs as JSON before signing for comprehensive routing.
    """
    import json
    data = json.dumps({"tenant_id": tenant_id, "connection_id": connection_id})
    return sign_client_state(data)
