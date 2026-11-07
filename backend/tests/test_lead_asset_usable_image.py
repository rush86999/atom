"""Matching a digest and an image MIME label is not usable image proof."""
import asyncio
import hashlib
import io
import pytest
from PIL import Image
import core.asset_content_receipt as asset


def _read(monkeypatch, body):
    def fetch(*args, **kwargs):
        return asset.AssetHttpResponse(200, {'content-type':'image/png',
            'content-length':str(len(body))}, body, 'https://cdn.shopify.com/a.png')
    monkeypatch.setattr(asset, '_http_get_pinned', fetch)
    return asyncio.run(asset.read_provider_asset('https://cdn.shopify.com/a.png',
        allowed_hosts=asset.SHOPIFY_IMAGE_CDN_HOSTS,
        expected_sha256=hashlib.sha256(body).hexdigest(), expected_bytes=len(body),
        resolver=lambda *args, **kwargs:[(2,1,6,'',('93.184.216.34',443))]))


@pytest.mark.parametrize('body',[b'', b'<html>not an image</html>', b'\x89PNG\r\n\x1a\ntruncated'])
def test_mime_and_matching_hash_cannot_certify_unusable_image(monkeypatch, body):
    try:
        result = _read(monkeypatch, body)
    except asset.AssetContentError:
        return
    assert result.get('verified') is not True, 'non-image bytes certified as usable image'


def test_real_decodable_png_with_matching_digest_is_supported(monkeypatch):
    buffer = io.BytesIO()
    Image.new('RGB',(2,3),color='blue').save(buffer,format='PNG')
    result = _read(monkeypatch, buffer.getvalue())
    assert result['verified'] is True, result
