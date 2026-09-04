"""DocuSign eSign REST integration — external cryptographic signing (P4).

The internal signature stamp (pdf_engine.stamp_signature) is a visual
approval; legally-weighted external signing runs as a DocuSign ENVELOPE:
the canvas's current version is uploaded as the envelope document, one
signer is attached, and the envelope is sent. The completed, signed PDF is
retrievable from DocuSign by envelope id (fetched on demand by the status
call — like received email attachments, third-party-signed bytes stay
mailbox-authoritative and are never persisted here).

Credentials come from the environment (JWT consent grant):
  DOCUSIGN_INTEGRATION_KEY, DOCUSIGN_USER_ID, DOCUSIGN_ACCOUNT_ID,
  DOCUSIGN_PRIVATE_KEY_B64 (base64 RSA key) or DOCUSIGN_PRIVATE_KEY_PATH,
  DOCUSIGN_BASE_URL (default the demo sandbox),
  DOCUSIGN_OAUTH_BASE_URL (default account-d.docusign.com).

Unconfigured → is_configured() False and send_for_signature returns a clean
"not configured" result — the feature is dormant, never a 500.
"""

from __future__ import annotations

import base64
import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

DEFAULT_REST_BASE = "https://demo.docusign.net/restapi"
DEFAULT_OAUTH_BASE = "https://account-d.docusign.com"
JWT_EXPIRY_SECONDS = 3600
_ENVELOPE_TEMPLATE = (
    "{base}/v2.1/accounts/{account_id}/envelopes"
)


def is_configured() -> bool:
    return bool(
        os.getenv("DOCUSIGN_INTEGRATION_KEY")
        and os.getenv("DOCUSIGN_USER_ID")
        and os.getenv("DOCUSIGN_ACCOUNT_ID")
        and (os.getenv("DOCUSIGN_PRIVATE_KEY_B64") or os.getenv("DOCUSIGN_PRIVATE_KEY_PATH"))
    )


def _private_key() -> Optional[bytes]:
    b64 = os.getenv("DOCUSIGN_PRIVATE_KEY_B64")
    if b64:
        try:
            return base64.b64decode(b64)
        except Exception as e:
            logger.error(f"DOCUSIGN_PRIVATE_KEY_B64 undecodable: {e}")
            return None
    path = os.getenv("DOCUSIGN_PRIVATE_KEY_PATH")
    if path:
        try:
            with open(path, "rb") as f:
                return f.read()
        except OSError as e:
            logger.error(f"DOCUSIGN_PRIVATE_KEY_PATH unreadable: {e}")
    return None


def _config() -> Dict[str, str]:
    return {
        "integration_key": os.getenv("DOCUSIGN_INTEGRATION_KEY", ""),
        "user_id": os.getenv("DOCUSIGN_USER_ID", ""),
        "account_id": os.getenv("DOCUSIGN_ACCOUNT_ID", ""),
        "rest_base": os.getenv("DOCUSIGN_BASE_URL", DEFAULT_REST_BASE).rstrip("/"),
        "oauth_base": os.getenv("DOCUSIGN_OAUTH_BASE_URL", DEFAULT_OAUTH_BASE).rstrip("/"),
    }


def _sign_jwt(cfg: Dict[str, str], private_key: bytes) -> str:
    import jwt

    now = int(time.time())
    return jwt.encode(
        {
            "iss": cfg["integration_key"],
            "sub": cfg["user_id"],
            "aud": cfg["oauth_base"],
            "iat": now,
            "exp": now + JWT_EXPIRY_SECONDS,
            "scope": "signature impersonation",
        },
        private_key,
        algorithm="RS256",
    )


def _exchange_token(cfg: Dict[str, str], assertion: str) -> Dict[str, Any]:
    resp = requests.post(
        f"{cfg['oauth_base']}/oauth/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def get_access_token() -> Dict[str, Any]:
    """JWT-consent grant → access token + the account's real base_uri."""
    if not is_configured():
        return {"success": False, "error": "DocuSign is not configured (missing DOCUSIGN_* env)"}
    key = _private_key()
    if not key:
        return {"success": False, "error": "DocuSign private key unavailable"}
    cfg = _config()
    try:
        assertion = _sign_jwt(cfg, key)
        token = _exchange_token(cfg, assertion)
    except Exception as e:
        logger.error(f"DocuSign token exchange failed: {e}")
        return {"success": False, "error": f"DocuSign authentication failed: {e}"}
    return {
        "success": True,
        "access_token": token.get("access_token"),
        "expires_in": token.get("expires_in"),
        "base_uri": cfg["rest_base"],
        "account_id": cfg["account_id"],
    }


def send_envelope(
    access_token: str,
    base_uri: str,
    account_id: str,
    filename: str,
    pdf_bytes: bytes,
    signer_email: str,
    signer_name: str,
    email_subject: str = "",
) -> Dict[str, Any]:
    """Create + send a signature envelope for one document / one signer."""
    url = _ENVELOPE_TEMPLATE.format(base=base_uri.rstrip("/"), account_id=account_id)
    resp = requests.post(
        url,
        json={
            "emailSubject": (email_subject or f"Please sign: {filename}")[:100],
            "documents": [{
                "documentBase64": base64.b64encode(pdf_bytes).decode("ascii"),
                "name": filename,
                "fileExtension": "pdf",
                "documentId": "1",
            }],
            "recipients": {"signers": [{
                "email": signer_email,
                "name": signer_name,
                "recipientId": "1",
                "routingOrder": "1",
            }]},
            "status": "sent",
        },
        headers={"Authorization": f"Bearer {access_token}",
                 "Content-Type": "application/json"},
        timeout=60,
    )
    if resp.status_code not in (200, 201):
        return {"success": False, "error": f"DocuSign envelope failed ({resp.status_code}): {resp.text[:300]}"}
    data = resp.json()
    return {
        "success": True,
        "envelope_id": data.get("envelopeId"),
        "status": data.get("status", "sent"),
    }


def envelope_status(access_token: str, base_uri: str, account_id: str, envelope_id: str) -> Dict[str, Any]:
    """Poll an envelope (status: sent → delivered → completed/declined)."""
    url = f"{base_uri.rstrip('/')}/v2.1/accounts/{account_id}/envelopes/{envelope_id}"
    resp = requests.get(url, headers={"Authorization": f"Bearer {access_token}"}, timeout=30)
    if resp.status_code != 200:
        return {"success": False, "error": f"DocuSign status failed ({resp.status_code})"}
    data = resp.json()
    return {"success": True, "envelope_id": envelope_id, "status": data.get("status")}


def send_for_signature(
    filename: str,
    pdf_bytes: bytes,
    signer_email: str,
    signer_name: str,
    email_subject: str = "",
) -> Dict[str, Any]:
    """One-call entry for the service/route/tool layers: auth → envelope."""
    auth = get_access_token()
    if not auth.get("success"):
        return auth
    return send_envelope(
        auth["access_token"], auth["base_uri"], auth["account_id"],
        filename, pdf_bytes, signer_email, signer_name, email_subject,
    )
