"""Bounded, unauthenticated content receipt for provider-returned assets.

Why this module
---------------
Existing authorized file reads (``brennan.workdrive.read_file`` /
``brennan.onedrive.read_file``) return the shared ``read_receipt`` shape with
resource/account/coverage fields and a SHA-256.  Shopify product images are
different: the provider returns a CDN URL, not caller bytes, and there is no
content hash in the REST product-image resource.  This helper adds only the
missing read: a bounded, DNS-pinned HTTPS GET of an allowlisted provider CDN
URL, recorded in the same receipt shape.

Security boundary
-----------------
* Only provider-returned URLs from an explicit host allowlist are accepted.
* HTTPS only; no userinfo, fragment, non-443 port or redirects.
* DNS is resolved once and the chosen public IP is pinned for the connection;
  the original host is used for the Host header and TLS SNI.  Private,
  loopback, link-local, reserved and encoded-IP destinations are refused.
* No Authorization, cookie or provider token is sent.  Content is bounded,
  must be ``image/*``, and must not be gzip/br encoded.
* Failures raise :class:`AssetContentError`; they are never empty successes.
* Exact SHA-256/byte comparison is preserved.  A provider byte transform
  therefore remains an unverified content mismatch, never a success.
"""
from __future__ import annotations

import asyncio
import hashlib
import http.client
import io
import ipaddress
import socket
import ssl
import warnings
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlparse

DEFAULT_MAX_BYTES = 8 * 1024 * 1024
#: Decode bound for the image-usability sub-contract.  Dimensions are checked
#: before a full load, so a compressed decompression bomb is refused before it
#: allocates the decoded buffer.  This is a proof-read bound, not a product API
#: image-count cap.
MAX_IMAGE_PIXELS = 40_000_000
_IMAGE_FORMAT_MIME = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
    "GIF": "image/gif",
}
SHOPIFY_IMAGE_CDN_HOSTS: Tuple[str, ...] = (
    "cdn.shopify.com",
    "*.shopifycdn.com",
)


class AssetContentError(ValueError):
    """A fail-closed asset read refusal or transport/content error."""

    def __init__(self, reason: str, message: str = ""):
        self.reason = str(reason or "asset_content_error")
        super().__init__(message or self.reason)


@dataclass
class AssetHttpResponse:
    status: int
    headers: Dict[str, str]
    body: bytes
    url: str


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS connection to a vetted IP, preserving Host and TLS SNI."""

    def __init__(self, host: str, pinned_ip: str, *, timeout: float):
        super().__init__(
            host, 443, timeout=timeout,
            context=ssl.create_default_context())
        self._pinned_ip = pinned_ip

    def connect(self) -> None:  # noqa: D401 - stdlib hook
        self.sock = socket.create_connection(
            (self._pinned_ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(
            self.sock, server_hostname=self.host)


def _normalized_host(host: str) -> str:
    from core.sandbox_egress_proxy import normalize_host

    return normalize_host(host)


def _host_allowed(host: str, allowed_hosts: Sequence[str]) -> bool:
    from core.sandbox_egress_proxy import host_matches

    return host_matches(_normalized_host(host), tuple(allowed_hosts))


def _assert_public_ip(ip: str) -> None:
    from core.ssrf_guard import _is_blocked_ip

    try:
        ipaddress.ip_address(ip)
    except ValueError as exc:
        raise AssetContentError(
            "invalid_resolved_address", f"invalid resolved address {ip!r}") from exc
    if _is_blocked_ip(ip):
        raise AssetContentError(
            "blocked_resolved_address",
            f"resolved address {ip!r} is private/loopback/link-local/reserved")


def resolve_public_addresses(
    host: str, port: int = 443, *, resolver=None,
) -> Tuple[str, ...]:
    """Resolve once and return only public addresses; fail closed otherwise."""
    resolver = resolver or socket.getaddrinfo
    try:
        infos = resolver(host, port, type=socket.SOCK_STREAM)
    except Exception as exc:  # noqa: BLE001 - fail closed on DNS failure
        raise AssetContentError(
            "dns_resolution_failed",
            f"could not resolve {host!r}: {type(exc).__name__}") from exc
    addresses = []
    for info in infos:
        try:
            ip = str(info[4][0])
        except (IndexError, TypeError):
            continue
        _assert_public_ip(ip)
        if ip not in addresses:
            addresses.append(ip)
    if not addresses:
        raise AssetContentError(
            "no_public_address", f"{host!r} resolved to no usable address")
    return tuple(addresses)


def _http_get_pinned(
    url: str, host: str, pinned_ip: str, *,
    timeout: float = 10.0, max_bytes: int = DEFAULT_MAX_BYTES,
) -> AssetHttpResponse:
    """Bounded GET through the pinned IP; tests double this HTTP leaf."""
    parsed = urlparse(url)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    connection = _PinnedHTTPSConnection(host, pinned_ip, timeout=timeout)
    try:
        connection.request(
            "GET", path,
            headers={
                "Host": host,
                "Accept-Encoding": "identity",
                "Connection": "close",
                "User-Agent": "atom-asset-receipt/1",
            })
        response = connection.getresponse()
        headers = {
            str(name).lower(): str(value)
            for name, value in response.getheaders()
        }
        declared = headers.get("content-length")
        if declared:
            try:
                if int(declared) > int(max_bytes):
                    raise AssetContentError(
                        "oversize", f"declared content-length {declared} exceeds limit")
            except ValueError:
                raise AssetContentError(
                    "invalid_content_length", f"invalid content-length {declared!r}")
        body = response.read(int(max_bytes) + 1)
        if len(body) > int(max_bytes):
            raise AssetContentError("oversize", "asset body exceeds byte bound")
        return AssetHttpResponse(
            status=int(response.status), headers=headers, body=body, url=url)
    finally:
        connection.close()


def _decode_supported_image(body: bytes, content_type: str) -> Dict[str, Any]:
    """Fully decode one supported image with bounded pixels/decompression.

    MIME labels and digests are not usability proof.  ``Image.open`` alone may
    accept a header-only/truncated file, so this verifies integrity and then
    reopens/loads the bytes, checking the declared dimensions against a pixel
    cap before decode.  Animated images are refused in this sub-contract rather
    than claiming first-frame usability.
    """
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:  # pragma: no cover - Pillow is a requirement
        raise AssetContentError(
            "image_decoder_unavailable", "Pillow is required for image proof") from exc
    declared_mime = content_type.split(";", 1)[0].strip().lower()
    if declared_mime == "image/jpg":
        declared_mime = "image/jpeg"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(body)) as probe:
                width, height = int(probe.width), int(probe.height)
                image_format = str(probe.format or "").upper()
                frames = int(getattr(probe, "n_frames", 1) or 1)
                if width <= 0 or height <= 0:
                    raise AssetContentError(
                        "unusable_image", "image has non-positive dimensions")
                if width * height > MAX_IMAGE_PIXELS:
                    raise AssetContentError(
                        "image_pixel_bound",
                        f"image dimensions {width}x{height} exceed the pixel bound")
                if frames > 1:
                    raise AssetContentError(
                        "unsupported_animated_image",
                        "animated images are unsupported by the content sub-contract")
                probe.verify()
            with Image.open(io.BytesIO(body)) as decoded:
                if int(decoded.width) != width or int(decoded.height) != height:
                    raise AssetContentError(
                        "unusable_image", "image dimensions changed while decoding")
                decoded.load()
    except AssetContentError:
        raise
    except Image.DecompressionBombError as exc:
        raise AssetContentError(
            "image_pixel_bound", "image decoder rejected a decompression bomb") from exc
    except (UnidentifiedImageError, OSError, ValueError, EOFError) as exc:
        raise AssetContentError(
            "unusable_image", f"image bytes are not decodable: {type(exc).__name__}") from exc
    expected_mime = _IMAGE_FORMAT_MIME.get(image_format)
    if expected_mime is None:
        raise AssetContentError(
            "unsupported_image_format",
            f"image format {image_format!r} is not supported")
    if declared_mime != expected_mime:
        raise AssetContentError(
            "image_mime_mismatch",
            f"declared {declared_mime!r} does not match decoded {expected_mime!r}")
    return {
        "format": image_format,
        "mime": expected_mime,
        "width": width,
        "height": height,
    }


def _content_type(headers: Mapping[str, str]) -> str:
    return str(headers.get("content-type") or "").split(";", 1)[0].strip().lower()


def _receipt_shape(
    *, provider: str, resource_id: str, account_id: str,
    digest: str, size: int, content_type: str, host: str,
    image_format: str, width: int, height: int,
) -> Dict[str, Any]:
    """Reuse the existing authorized-read receipt builder."""
    from core.connected_actions import _receipt

    return _receipt(
        provider or "provider_asset", "read_asset",
        resource_id=str(resource_id or ""),
        coverage="single",
        account_id=str(account_id or ""),
        fields={
            "sha256": digest,
            "bytes": size,
            "content_type": content_type,
            "url_host": host,
            "image_format": image_format,
            "width": width,
            "height": height,
        },
        evidence=[{
            "kind": "asset_content",
            "resource_id": str(resource_id or ""),
            "sha256": digest,
            "bytes": size,
            "host": host,
            "image_format": image_format,
            "width": width,
            "height": height,
        }],
    )


async def read_provider_asset(
    url: str,
    *,
    allowed_hosts: Sequence[str],
    max_bytes: int = DEFAULT_MAX_BYTES,
    expected_sha256: str = "",
    expected_bytes: Optional[int] = None,
    provider: str = "provider_asset",
    resource_id: str = "",
    account_id: str = "",
    resolver=None,
) -> Dict[str, Any]:
    """Read one provider-returned asset and build the shared receipt shape."""
    if not isinstance(url, str) or not url.strip():
        raise AssetContentError("missing_url", "asset URL is required")
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise AssetContentError("https_required", "asset URL must use https")
    if parsed.username or parsed.password:
        raise AssetContentError("userinfo_refused", "asset URL carries userinfo")
    if parsed.fragment:
        raise AssetContentError("fragment_refused", "asset URL carries a fragment")
    if parsed.port not in (None, 443):
        raise AssetContentError("port_refused", "asset URL must use port 443")
    host = parsed.hostname or ""
    if not host or not _host_allowed(host, allowed_hosts):
        raise AssetContentError(
            "host_not_allowlisted", f"asset host {host!r} is not allowlisted")
    if not isinstance(max_bytes, int) or max_bytes <= 0:
        raise AssetContentError("invalid_byte_bound", "byte bound must be positive")
    expected_digest = str(expected_sha256 or "").strip().lower()
    if expected_digest and (
            len(expected_digest) != 64
            or any(ch not in "0123456789abcdef" for ch in expected_digest)):
        raise AssetContentError(
            "invalid_expected_sha256", "expected SHA-256 is malformed")
    if expected_bytes is not None and (
            not isinstance(expected_bytes, int) or expected_bytes < 0):
        raise AssetContentError(
            "invalid_expected_bytes", "expected byte count is malformed")
    from core.ssrf_guard import validate_url

    validate_url(url, resolve_dns=False)
    addresses = resolve_public_addresses(host, 443, resolver=resolver)
    pinned_ip = addresses[0]
    response = await asyncio.to_thread(
        _http_get_pinned, url, host, pinned_ip,
        timeout=10.0, max_bytes=int(max_bytes))
    if 300 <= response.status < 400:
        raise AssetContentError(
            "redirect_refused", f"asset URL redirected ({response.status})")
    if response.status != 200:
        raise AssetContentError(
            "http_status", f"asset URL returned HTTP {response.status}")
    content_encoding = str(
        response.headers.get("content-encoding") or "").strip().lower()
    if content_encoding not in ("", "identity"):
        raise AssetContentError(
            "content_encoding_refused",
            f"asset response uses content-encoding {content_encoding!r}")
    content_type = _content_type(response.headers)
    if not content_type.startswith("image/"):
        raise AssetContentError(
            "non_image_content",
            f"asset content-type {content_type!r} is not an image")
    body = response.body or b""
    if len(body) > int(max_bytes):
        raise AssetContentError("oversize", "asset body exceeds byte bound")
    decoded = _decode_supported_image(body, content_type)
    digest = hashlib.sha256(body).hexdigest()
    verified = True
    reason = ""
    if expected_digest and digest != expected_digest:
        verified = False
        reason = "content_mismatch_or_provider_transform"
    if expected_bytes is not None and len(body) != expected_bytes:
        verified = False
        reason = reason or "byte_count_mismatch"
    receipt = _receipt_shape(
        provider=provider, resource_id=resource_id, account_id=account_id,
        digest=digest, size=len(body), content_type=content_type, host=host,
        image_format=decoded["format"], width=decoded["width"],
        height=decoded["height"])
    return {
        "verified": verified,
        "reason": reason,
        "sha256": digest,
        "bytes": len(body),
        "content_type": content_type,
        "image_format": decoded["format"],
        "width": decoded["width"],
        "height": decoded["height"],
        "host": host,
        "read_receipt": receipt,
    }
