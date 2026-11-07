"""Security/validity controls for the bounded provider asset receipt."""
from __future__ import annotations

import asyncio
import hashlib
import io

import pytest
from PIL import Image

import core.asset_content_receipt as acr


def _png(size=(2, 3), color="blue"):
    buffer = io.BytesIO()
    Image.new("RGB", size, color=color).save(buffer, format="PNG")
    return buffer.getvalue()


PNG = _png()
TRANSFORMED = _png((4, 5), "red")
DIGEST = hashlib.sha256(PNG).hexdigest()
PUBLIC_IP = "93.184.216.34"


def _resolver(*_args, **_kwargs):
    return [(2, 1, 6, "", (PUBLIC_IP, 443))]


def _response(*, status=200, content_type="image/png", body=PNG, length=None):
    headers = {"content-type": content_type}
    headers["content-length"] = str(len(body) if length is None else length)
    return acr.AssetHttpResponse(
        status=status, headers=headers, body=body, url="")


def _run(url, **kwargs):
    kwargs.setdefault("allowed_hosts", acr.SHOPIFY_IMAGE_CDN_HOSTS)
    kwargs.setdefault("resolver", _resolver)
    return asyncio.run(acr.read_provider_asset(url, **kwargs))


def test_private_resolved_address_is_refused_before_fetch(monkeypatch):
    fetched = []

    def _private(*_args, **_kwargs):
        return [(2, 1, 6, "", ("127.0.0.1", 443))]

    monkeypatch.setattr(
        acr, "_http_get_pinned",
        lambda *a, **k: fetched.append((a, k)))
    with pytest.raises(acr.AssetContentError) as exc:
        _run("https://cdn.shopify.com/a.png", resolver=_private)
    assert exc.value.reason == "blocked_resolved_address"
    assert fetched == []


def test_non_allowlisted_host_is_refused(monkeypatch):
    monkeypatch.setattr(
        acr, "_http_get_pinned",
        lambda *a, **k: pytest.fail("unsafe host reached HTTP leaf"))
    with pytest.raises(acr.AssetContentError) as exc:
        _run("https://evil.example/a.png")
    assert exc.value.reason == "host_not_allowlisted"


def test_https_userinfo_and_nonstandard_port_are_refused(monkeypatch):
    monkeypatch.setattr(
        acr, "_http_get_pinned",
        lambda *a, **k: pytest.fail("unsafe URL reached HTTP leaf"))
    for url in (
        "http://cdn.shopify.com/a.png",
        "https://user:pass@cdn.shopify.com/a.png",
        "https://cdn.shopify.com:8443/a.png",
        "https://cdn.shopify.com/a.png#fragment",
    ):
        with pytest.raises(acr.AssetContentError):
            _run(url)


def test_redirect_is_refused(monkeypatch):
    monkeypatch.setattr(
        acr, "_http_get_pinned",
        lambda *a, **k: _response(status=302))
    with pytest.raises(acr.AssetContentError) as exc:
        _run("https://cdn.shopify.com/a.png")
    assert exc.value.reason == "redirect_refused"


def test_html_json_empty_and_non_image_are_refused(monkeypatch):
    for content_type, body in (
        ("text/html", b"<html>no</html>"),
        ("application/json", b"{}"),
        ("", b"x"),
        ("application/octet-stream", b"not-an-image"),
    ):
        monkeypatch.setattr(
            acr, "_http_get_pinned",
            lambda *a, _ct=content_type, _body=body, **k: _response(
                content_type=_ct, body=_body))
        with pytest.raises(acr.AssetContentError) as exc:
            _run("https://cdn.shopify.com/a.png")
        assert exc.value.reason == "non_image_content"


def test_oversize_body_is_refused(monkeypatch):
    monkeypatch.setattr(
        acr, "_http_get_pinned",
        lambda *a, **k: _response(body=PNG, length=len(PNG)))
    with pytest.raises(acr.AssetContentError) as exc:
        _run("https://cdn.shopify.com/a.png", max_bytes=4)
    assert exc.value.reason == "oversize"


def test_exact_digest_and_bytes_are_verified(monkeypatch):
    fetched = []

    def _fetch(url, host, pinned_ip, **kwargs):
        fetched.append((url, host, pinned_ip, kwargs))
        return _response()

    monkeypatch.setattr(acr, "_http_get_pinned", _fetch)
    result = _run(
        "https://cdn.shopify.com/s/files/a.png",
        expected_sha256=DIGEST,
        expected_bytes=len(PNG),
        resource_id="img-1",
        account_id="shop.myshopify.com",
    )
    assert result["verified"] is True
    assert result["sha256"] == DIGEST
    assert result["bytes"] == len(PNG)
    assert result["read_receipt"]["fields"]["sha256"] == DIGEST
    assert result["image_format"] == "PNG"
    assert result["width"] == 2
    assert result["height"] == 3
    assert result["read_receipt"]["fields"]["width"] == 2
    assert fetched[0][1] == "cdn.shopify.com"
    assert fetched[0][2] == PUBLIC_IP


def test_provider_transform_remains_unknown(monkeypatch):
    monkeypatch.setattr(
        acr, "_http_get_pinned",
        lambda *a, **k: _response(body=TRANSFORMED))
    result = _run(
        "https://cdn.shopify.com/a.png",
        expected_sha256=DIGEST,
        expected_bytes=len(PNG),
    )
    assert result["verified"] is False
    assert result["reason"] == "content_mismatch_or_provider_transform"


def test_dns_is_resolved_once_and_public_ip_is_pinned(monkeypatch):
    calls = []
    pinned = []

    def _resolver(*_args, **_kwargs):
        calls.append(1)
        return [
            (2, 1, 6, "", (PUBLIC_IP, 443)),
            (2, 1, 6, "", ("8.8.8.8", 443)),
        ]

    def _fetch(url, host, pinned_ip, **kwargs):
        pinned.append(pinned_ip)
        return _response()

    monkeypatch.setattr(acr, "_http_get_pinned", _fetch)
    result = _run(
        "https://cdn.shopify.com/a.png",
        expected_sha256=DIGEST,
        resolver=_resolver,
    )
    assert result["verified"] is True
    assert len(calls) == 1
    assert pinned == [PUBLIC_IP]


def test_http_request_carries_no_credentials_or_cookies(monkeypatch):
    captured = {}

    class _FakeResponse:
        status = 200

        def getheaders(self):
            return [("Content-Type", "image/png"),
                    ("Content-Length", str(len(PNG)))]

        def read(self, _n):
            return PNG

    class _FakeConnection:
        def __init__(self, *args, **kwargs):
            pass

        def request(self, method, path, headers=None):
            captured["method"] = method
            captured["path"] = path
            captured["headers"] = dict(headers or {})

        def getresponse(self):
            return _FakeResponse()

        def close(self):
            pass

    monkeypatch.setattr(acr, "_PinnedHTTPSConnection", _FakeConnection)
    result = asyncio.run(acr.read_provider_asset(
        "https://cdn.shopify.com/a.png",
        allowed_hosts=acr.SHOPIFY_IMAGE_CDN_HOSTS,
        expected_sha256=DIGEST,
        resolver=_resolver,
    ))
    assert result["verified"] is True
    headers = {k.lower(): v for k, v in captured["headers"].items()}
    assert headers["host"] == "cdn.shopify.com"
    assert headers["accept-encoding"] == "identity"
    assert "authorization" not in headers
    assert "cookie" not in headers
    assert captured["method"] == "GET"


def test_mime_must_match_decoded_format(monkeypatch):
    monkeypatch.setattr(
        acr, "_http_get_pinned",
        lambda *a, **k: _response(content_type="image/jpeg", body=PNG))
    with pytest.raises(acr.AssetContentError) as exc:
        _run("https://cdn.shopify.com/a.png", expected_sha256=DIGEST)
    assert exc.value.reason == "image_mime_mismatch"


def test_pixel_bound_refuses_before_full_decode(monkeypatch):
    monkeypatch.setattr(acr, "MAX_IMAGE_PIXELS", 1)
    monkeypatch.setattr(
        acr, "_http_get_pinned", lambda *a, **k: _response(body=PNG))
    with pytest.raises(acr.AssetContentError) as exc:
        _run("https://cdn.shopify.com/a.png", expected_sha256=DIGEST)
    assert exc.value.reason == "image_pixel_bound"


def test_real_jpeg_is_supported(monkeypatch):
    buffer = io.BytesIO()
    Image.new("RGB", (4, 2), color="green").save(buffer, format="JPEG")
    jpeg = buffer.getvalue()
    digest = hashlib.sha256(jpeg).hexdigest()
    monkeypatch.setattr(
        acr, "_http_get_pinned",
        lambda *a, **k: _response(content_type="image/jpeg", body=jpeg))
    result = _run(
        "https://cdn.shopify.com/a.jpg", expected_sha256=digest,
        expected_bytes=len(jpeg))
    assert result["verified"] is True
    assert result["image_format"] == "JPEG"
    assert result["width"] == 4 and result["height"] == 2
