"""Communication styling preservation (shared, app-agnostic).

Single mechanism behind "styling must be preserved when ingesting ANY
communication app" (user request, Sept 2026 — generalized from the email
fix in atom_communication_ingestion_pipeline):

- Links: anchors and platform link syntaxes are rewritten to markdown
  `[text](href)` BEFORE any tag-stripping, so hrefs survive FTS/vector
  indexing and every downstream agent view (previously the email path
  deleted `<a href>` entirely and Slack's `<url|text>` syntax was stored
  opaque).
- Raw markup: style-bearing original markup (HTML bodies, rich payloads)
  is kept size-capped in message metadata (`html_body` / `raw_markup`) so
  the exact formatting — signatures, tables, links — stays recoverable for
  reproduction. Plain-text sources (WhatsApp/Discord/SMS: links are already
  plain URLs) store nothing extra.

Every function is never-raise: styling preservation must never break
ingestion.
"""

import html as _html_mod
import re
from typing import Any, Dict, Optional, Tuple

HTML_TAG_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", re.DOTALL | re.IGNORECASE)
HTML_WS_RE = re.compile(r"[ \t]*\n[ \t\n]*")
# <a href> → [text](href) BEFORE tag-stripping: plain tag-stripping deletes
# the href and keeps only the anchor text.
HTML_ANCHOR_RE = re.compile(
    r"<a\s[^>]*?href\s*=\s*[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
    re.DOTALL | re.IGNORECASE,
)
# Slack mrkdwn links: <https://x|label> and bare <https://x>.
SLACK_LINK_RE = re.compile(r"<([a-z][a-z0-9+.-]*://[^|>\s]+)\|([^>]+)>", re.IGNORECASE)
SLACK_BARE_URL_RE = re.compile(r"<((?:https?|mailto|tel|callto|ftp)://[^>\s]+)>", re.IGNORECASE)
# Style-bearing markup worth keeping raw: signatures (styled tables/fonts),
# data tables, images, links. Plain <p>text</p> bodies don't justify size.
STYLE_MARKUP_RE = re.compile(r"<(table|img)\b|style\s*=|\bclass\s*=|<a\s", re.IGNORECASE)
MAX_RAW_CHARS = 64_000

# Keys platforms use for the rich/HTML variant of a message (Teams emits
# html_content, Graph bodies html_body, ad-hoc pollers html).
_HTML_SOURCE_KEYS = ("html_content", "html_body", "html", "rich_content")
_HTML_CONTENT_TYPES = ("html", "text/html")


def _strip_tags(markup: str) -> str:
    return HTML_TAG_RE.sub("", markup or "")


def preserve_links_in_html(html_body: str) -> str:
    """Rewrite HTML anchors to markdown links. Never raises."""
    if not html_body or "<a" not in html_body.lower():
        return html_body

    def _anchor_text(inner: str) -> str:
        text = _strip_tags(inner)
        text = _html_mod.unescape(text)
        return re.sub(r"\s+", " ", text).strip()

    try:
        def _repl(m) -> str:
            href, inner = m.group(1), m.group(2)
            text = _anchor_text(inner)
            if not text or text.lower() in ("click here", "here", "link"):
                text = href
            return f"[{text}]({href})"

        return HTML_ANCHOR_RE.sub(_repl, html_body)
    except Exception:
        return html_body


def slack_links_to_markdown(text: str) -> str:
    """Slack mrkdwn `<url|label>` / `<url>` → markdown links. Never raises."""
    if not text or "<" not in text:
        return text
    try:
        text = SLACK_LINK_RE.sub(lambda m: f"[{m.group(2).strip()}]({m.group(1)})", text)
        return SLACK_BARE_URL_RE.sub(lambda m: m.group(1), text)
    except Exception:
        return text


def has_style_markup(content: Any) -> bool:
    """True when the payload carries style-bearing markup worth keeping raw."""
    if not isinstance(content, str):
        return False
    try:
        return bool(STYLE_MARKUP_RE.search(content))
    except Exception:
        return False


def html_to_text(html_body: str) -> str:
    """Tag-stripping text conversion with links preserved. Never raises."""
    if not html_body:
        return ""
    try:
        text = HTML_TAG_RE.sub("\n", preserve_links_in_html(html_body))
        text = _html_mod.unescape(text)
        return HTML_WS_RE.sub("\n", text).strip()
    except Exception:
        return html_body


def preserve_links(content: str) -> str:
    """Source-agnostic link recovery for already-decoded message text:
    Slack mrkdwn links and HTML anchors become markdown links; plain text
    (WhatsApp/Discord URLs) passes through untouched. Never raises."""
    if not content:
        return content
    if "<a" in content.lower():
        content = preserve_links_in_html(content)
    return slack_links_to_markdown(content)


def pick_raw_html_source(content: Any, message_data: Dict[str, Any],
                         content_type: Any = None) -> Optional[str]:
    """The rich variant of a message, if any: an explicit html/rich key on
    the payload, or the content itself when declared/looking like HTML.
    Returns None for plain-text messages."""
    for key in _HTML_SOURCE_KEYS:
        val = message_data.get(key)
        if isinstance(val, str) and val.strip():
            return val
    ctype = str(content_type or "").lower()
    if isinstance(content, str) and (
        ctype in _HTML_CONTENT_TYPES or "<html" in content.lower()
        or (has_style_markup(content) and "<" in content)
    ):
        return content
    return None


def extract_raw_markup(content: Any, message_data: Dict[str, Any],
                       content_type: Any = None,
                       key: str = "html_body") -> Tuple[Optional[str], Optional[str]]:
    """(metadata_key, capped_raw) for style-bearing messages, else (None, None).

    HTML sources land under ``html_body``; non-HTML rich payloads (e.g.
    Slack block JSON) under ``raw_markup``.
    """
    raw = pick_raw_html_source(content, message_data, content_type)
    if raw is None:
        rich = _non_html_rich_payload(message_data)
        if rich is None:
            return None, None
        return "raw_markup", rich[:MAX_RAW_CHARS]
    if not has_style_markup(raw):
        return None, None
    return key, raw[:MAX_RAW_CHARS]


def _non_html_rich_payload(message_data: Dict[str, Any]) -> Optional[str]:
    """Structured rich payloads (Slack blocks/attachments) as JSON — kept so
    block-styled links/buttons stay reconstructable."""
    try:
        blocks = message_data.get("blocks") or (
            (message_data.get("metadata") or {}).get("blocks")
            if isinstance(message_data.get("metadata"), dict) else None
        )
        if blocks:
            import json as _json
            return _json.dumps(blocks)
    except Exception:
        return None
    return None


def apply_styling_preservation(
    content: Any, metadata: Optional[Dict[str, Any]]
) -> Tuple[str, Dict[str, Any]]:
    """Final safety net for the store choke point: ANY producer reaching the
    store with style-bearing markup gets the normalized treatment even if it
    bypassed the per-app normalizers (projects/sales pipelines, API/webhook
    ingests).

    - Content already normalized upstream (metadata carries html_body /
      raw_markup) → idempotent link sweep only; raw is never duplicated.
    - Content is style-bearing HTML → stored text becomes the link-preserving
      conversion and the original lands in metadata.html_body (capped).
    - Anything else → link sweep (no-op for plain text). Never raises.
    """
    meta = metadata if isinstance(metadata, dict) else {}
    text = content if isinstance(content, str) else str(content or "")
    try:
        if meta.get("html_body") or meta.get("raw_markup"):
            return preserve_links(text), meta
        key, raw = extract_raw_markup(text, {}, None)
        if key and raw:
            return html_to_text(text), {**meta, key: raw}
        return preserve_links(text), meta
    except Exception:
        return text, meta
