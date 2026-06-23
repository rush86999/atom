/**
 * Shared HTML sanitization utility.
 *
 * All dangerouslySetInnerHTML consumers MUST route through sanitizeHtml to
 * prevent XSS via agent output, user messages, or markdown-rendered content.
 * marked.parse() does not strip inline HTML by default, so any <script>,
 * onerror=, or onload= payload in the source survives into the DOM.
 */
import DOMPurify from "dompurify";

// Allow a reasonable subset of formatting + semantic tags, block scripts
// and event handlers entirely.
const ALLOWED_TAGS = [
  // Text formatting
  "p", "br", "hr", "strong", "b", "em", "i", "u", "s", "del", "ins", "mark",
  "small", "sub", "sup",
  // Headings
  "h1", "h2", "h3", "h4", "h5", "h6",
  // Lists
  "ul", "ol", "li", "dl", "dt", "dd",
  // Links & media
  "a", "img", "figure", "figcaption", "picture", "source", "video", "audio",
  // Code
  "code", "pre", "kbd", "samp", "var",
  // Quotes & blocks
  "blockquote", "q", "cite", "abbr", "address",
  // Tables
  "table", "thead", "tbody", "tfoot", "tr", "th", "td", "caption", "colgroup", "col",
  // Layout
  "div", "span", "section", "article", "aside", "header", "footer", "nav",
  "details", "summary",
];

const ALLOWED_ATTR = [
  "href", "src", "alt", "title", "width", "height", "class", "id",
  "colspan", "rowspan", "target", "rel", "controls", "loop", "muted",
  "autoplay", "preload", "poster", "datetime", "open", "start", "reversed",
  "type", "name", "value", "lang", "dir",
];

export function sanitizeHtml(dirty: string | undefined | null): string {
  if (!dirty) return "";
  return DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS,
    ALLOWED_ATTR,
    // Strip protocol handlers (javascript:, data: on links/images)
    ALLOW_DATA_ATTR: false,
    FORBID_TAGS: ["script", "style", "iframe", "object", "embed", "form", "input", "button"],
    FORBID_ATTR: ["onerror", "onload", "onclick", "onmouseover", "onmouseenter", "onmouseleave", "onsubmit", "onchange", "oninput", "onfocus", "onblur"],
  });
}

/**
 * Render markdown to sanitized HTML.
 * Convenience wrapper combining marked + DOMPurify.
 */
export function renderMarkdownSafe(markdown: string | undefined | null): string {
  if (!markdown) return "";
  // marked is imported lazily so this module stays DOMPurify-only in tests.
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const { marked } = require("marked");
  const rawHtml = marked.parse(markdown) as string;
  return sanitizeHtml(rawHtml);
}
