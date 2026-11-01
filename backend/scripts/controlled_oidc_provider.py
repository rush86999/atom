"""Controlled, standards-shaped local OpenID Connect provider for acceptance.

This is an acceptance fixture, not a product module. It implements the
authorization-code flow with a real RSA-signed ID token, a published JWKS and
OIDC discovery metadata so the product's login/callback path can be exercised
against an actual HTTP provider instead of mocks:

    GET  /.well-known/openid-configuration
    GET  /jwks
    GET  /authorize          -> 302 redirect_uri?code=...&state=...
    POST /token              -> access_token + RS256 id_token
    GET  /userinfo           -> claims for the bearer access token

Failure modes are selectable per instance (``--mode``): an invalid issuer, a
forged signature, a mismatched nonce, a token-endpoint error, a missing ID
token and a callback error. Tests use those to prove the product fails closed.

Run standalone:
    python -m scripts.controlled_oidc_provider --port 59993
"""
from __future__ import annotations

import argparse
import base64
import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlencode, urlparse

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt as jose_jwt

MODES = {
    "valid",
    "invalid_issuer",
    "invalid_signature",
    "invalid_audience",
    "invalid_nonce",
    "missing_id_token",
    "token_error",
    "userinfo_error",
    "callback_error",
}


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _rsa_key() -> tuple[Any, Dict[str, str]]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = key.public_key().public_numbers()
    jwk = {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": secrets.token_hex(8),
        "n": _b64url_uint(numbers.n),
        "e": _b64url_uint(numbers.e),
    }
    return key, jwk


def _pem(key: Any) -> bytes:
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


class OIDCProvider:
    """One in-process controlled OIDC provider instance."""

    def __init__(
        self,
        *,
        client_id: str = "atom-acceptance-client",
        client_secret: str = "atom-acceptance-secret",
        redirect_uri: str = "http://127.0.0.1:8143/api/auth/sso/oidc/callback",
        mode: str = "valid",
        email: str = "oidc.user@example.com",
        given_name: str = "Oidc",
        family_name: str = "User",
        port: int = 0,
        issuer: Optional[str] = None,
    ) -> None:
        if mode not in MODES:
            raise ValueError(f"unknown controlled OIDC mode: {mode}")
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.mode = mode
        self.email = email
        self.given_name = given_name
        self.family_name = family_name
        self.signing_key, self.jwk = _rsa_key()
        self.other_key, self.other_jwk = _rsa_key()
        self._codes: Dict[str, Dict[str, Any]] = {}
        self._tokens: Dict[str, Dict[str, Any]] = {}
        self.records: List[Dict[str, Any]] = []
        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
        self.httpd.provider = self  # type: ignore[attr-defined]
        self.thread = threading.Thread(
            target=self.httpd.serve_forever, daemon=True)
        bound_port = self.httpd.server_address[1]
        self.issuer = (issuer or f"http://127.0.0.1:{bound_port}").rstrip("/")

    # -- lifecycle -----------------------------------------------------
    def start(self) -> "OIDCProvider":
        self.thread.start()
        return self

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    @property
    def base_url(self) -> str:
        return self.issuer

    @property
    def discovery(self) -> Dict[str, Any]:
        return {
            "issuer": self.issuer,
            "authorization_endpoint": f"{self.issuer}/authorize",
            "token_endpoint": f"{self.issuer}/token",
            "userinfo_endpoint": f"{self.issuer}/userinfo",
            "jwks_uri": f"{self.issuer}/jwks",
            "response_types_supported": ["code"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "scopes_supported": ["openid", "email", "profile"],
            "claims_supported": [
                "sub", "iss", "aud", "exp", "iat", "nonce", "email",
                "email_verified", "given_name", "family_name", "name",
            ],
        }

    @property
    def jwks(self) -> Dict[str, Any]:
        return {"keys": [self.jwk]}

    # -- flow ----------------------------------------------------------
    def authorize(self, query: Dict[str, List[str]]) -> str:
        def one(name: str) -> str:
            return (query.get(name) or [""])[0]

        state = one("state")
        error_location = self.redirect_uri
        if self.mode == "callback_error":
            return (error_location + "?" + urlencode(
                {"error": "access_denied", "state": state}))
        if one("response_type") != "code":
            return error_location + "?" + urlencode(
                {"error": "unsupported_response_type", "state": state})
        if one("client_id") != self.client_id:
            return error_location + "?" + urlencode(
                {"error": "unauthorized_client", "state": state})
        if one("redirect_uri") != self.redirect_uri:
            return error_location + "?" + urlencode(
                {"error": "invalid_request", "state": state})
        if "openid" not in one("scope").split():
            return error_location + "?" + urlencode(
                {"error": "invalid_scope", "state": state})
        nonce = one("nonce")
        if not state or not nonce:
            return error_location + "?" + urlencode(
                {"error": "invalid_request", "state": state})
        code = secrets.token_urlsafe(24)
        self._codes[code] = {
            "nonce": nonce,
            "redirect_uri": one("redirect_uri"),
            "client_id": one("client_id"),
        }
        return self.redirect_uri + "?" + urlencode(
            {"code": code, "state": state})

    def token(self, form: Dict[str, List[str]]) -> tuple[int, Dict[str, Any]]:
        def one(name: str) -> str:
            return (form.get(name) or [""])[0]

        if self.mode == "token_error":
            return 500, {"error": "server_error"}
        code = self._codes.pop(one("code"), None)
        if (not code
                or one("grant_type") != "authorization_code"
                or one("redirect_uri") != code["redirect_uri"]
                or one("client_id") != code["client_id"]
                or one("client_secret") != self.client_secret):
            return 400, {"error": "invalid_grant"}
        now = int(time.time())
        access_token = f"controlled-access-{secrets.token_urlsafe(18)}"
        claims = {
            "iss": (f"{self.issuer}/other" if self.mode == "invalid_issuer"
                    else self.issuer),
            "sub": "controlled-oidc-subject",
            "aud": (f"{self.client_id}-other"
                    if self.mode == "invalid_audience" else self.client_id),
            "iat": now,
            "exp": now + 300,
            "nonce": ("wrong-nonce" if self.mode == "invalid_nonce"
                      else code["nonce"]),
            "email": self.email,
            "email_verified": True,
            "given_name": self.given_name,
            "family_name": self.family_name,
            "name": f"{self.given_name} {self.family_name}",
        }
        signing_key = (self.other_key if self.mode == "invalid_signature"
                       else self.signing_key)
        id_token = jose_jwt.encode(
            claims, _pem(signing_key), algorithm="RS256",
            headers={"kid": self.jwk["kid"], "typ": "JWT"},
        )
        self._tokens[access_token] = claims
        body: Dict[str, Any] = {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 300,
            "scope": "openid email profile",
        }
        if self.mode != "missing_id_token":
            body["id_token"] = id_token
        return 200, body

    def userinfo(self, authorization: str) -> tuple[int, Dict[str, Any]]:
        if self.mode == "userinfo_error":
            return 500, {"error": "server_error"}
        prefix = "Bearer "
        token = authorization[len(prefix):] if authorization.startswith(prefix) else ""
        claims = self._tokens.get(token)
        if not claims:
            return 401, {"error": "invalid_token"}
        return 200, {
            "sub": claims["sub"],
            "email": claims["email"],
            "email_verified": True,
            "given_name": claims["given_name"],
            "family_name": claims["family_name"],
            "name": claims["name"],
        }


class _Handler(BaseHTTPRequestHandler):
    server_version = "AtomControlledOIDC/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:  # silence
        return

    @property
    def provider(self) -> OIDCProvider:
        return self.server.provider  # type: ignore[attr-defined]

    def _json(self, status: int, payload: Dict[str, Any]) -> None:
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _record(self, method: str, body: Optional[Dict[str, List[str]]] = None) -> None:
        self.provider.records.append({
            "method": method,
            "path": self.path,
            "body": {k: v for k, v in (body or {}).items()
                     if k != "client_secret"},
        })

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        self._record("GET")
        if parsed.path.rstrip("/") == "/.well-known/openid-configuration":
            self._json(200, self.provider.discovery)
            return
        if parsed.path.rstrip("/") == "/jwks":
            self._json(200, self.provider.jwks)
            return
        if parsed.path.rstrip("/") == "/authorize":
            location = self.provider.authorize(parse_qs(parsed.query))
            self.send_response(302)
            self.send_header("location", location)
            self.send_header("content-length", "0")
            self.end_headers()
            return
        if parsed.path.rstrip("/") == "/userinfo":
            status, payload = self.provider.userinfo(
                str(self.headers.get("authorization") or ""))
            self._json(status, payload)
            return
        if parsed.path.rstrip("/") == "/health":
            self._json(200, {"ok": True, "mode": self.provider.mode})
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("content-length") or 0)
        raw = self.rfile.read(length) if length else b""
        form = parse_qs(raw.decode("utf-8") or "")
        self._record("POST", form)
        if parsed.path.rstrip("/") == "/token":
            status, payload = self.provider.token(form)
            self._json(status, payload)
            return
        self._json(404, {"error": "not found"})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=59993)
    parser.add_argument("--mode", default="valid", choices=sorted(MODES))
    parser.add_argument("--client-id", default="atom-acceptance-client")
    parser.add_argument("--client-secret", default="atom-acceptance-secret")
    parser.add_argument(
        "--redirect-uri",
        default="http://127.0.0.1:8143/api/auth/sso/oidc/callback")
    parser.add_argument("--email", default="oidc.user@example.com")
    parser.add_argument("--print-config", action="store_true")
    args = parser.parse_args()
    provider = OIDCProvider(
        port=args.port, mode=args.mode, client_id=args.client_id,
        client_secret=args.client_secret, redirect_uri=args.redirect_uri,
        email=args.email,
    ).start()
    payload = {
        "issuer": provider.issuer,
        "client_id": provider.client_id,
        "redirect_uri": provider.redirect_uri,
        "mode": provider.mode,
        "discovery": provider.discovery,
        "jwks": provider.jwks,
    }
    if args.print_config:
        print(json.dumps(payload, indent=2), flush=True)
    else:
        print(provider.issuer, flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        provider.stop()


if __name__ == "__main__":
    main()
