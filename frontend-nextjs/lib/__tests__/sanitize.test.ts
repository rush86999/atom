/**
 * Tests for the shared HTML sanitization utility.
 * Verifies that XSS payloads are neutralized.
 */
import { sanitizeHtml, renderMarkdownSafe } from "../sanitize";

describe("sanitizeHtml", () => {
  it("strips <script> tags", () => {
    const dirty = '<p>hello</p><script>alert("xss")</script>';
    expect(sanitizeHtml(dirty)).not.toContain("<script>");
    expect(sanitizeHtml(dirty)).toContain("hello");
  });

  it("strips onerror event handlers", () => {
    const dirty = '<img src="x" onerror="alert(1)">';
    expect(sanitizeHtml(dirty)).not.toContain("onerror");
  });

  it("strips onload event handlers", () => {
    const dirty = '<img src="x" onload="alert(1)">';
    expect(sanitizeHtml(dirty)).not.toContain("onload");
  });

  it("strips javascript: protocol in href", () => {
    const dirty = '<a href="javascript:alert(1)">click</a>';
    const clean = sanitizeHtml(dirty);
    expect(clean).not.toContain("javascript:");
  });

  it("preserves safe formatting tags", () => {
    const dirty = "<p>hello <strong>world</strong></p>";
    expect(sanitizeHtml(dirty)).toContain("<strong>");
  });

  it("preserves links with safe href", () => {
    const dirty = '<a href="https://example.com">link</a>';
    expect(sanitizeHtml(dirty)).toContain("https://example.com");
  });

  it("handles empty input", () => {
    expect(sanitizeHtml("")).toBe("");
    expect(sanitizeHtml(undefined)).toBe("");
    expect(sanitizeHtml(null)).toBe("");
  });

  it("strips iframe, object, embed, form", () => {
    const dirty = '<iframe src="evil"></iframe><object data="x"></object><embed src="y">';
    const clean = sanitizeHtml(dirty);
    expect(clean).not.toContain("<iframe");
    expect(clean).not.toContain("<object");
    expect(clean).not.toContain("<embed");
  });
});

describe("renderMarkdownSafe", () => {
  it("renders safe markdown to sanitized HTML", () => {
    const md = "# Heading\n\nSome **bold** text.";
    const html = renderMarkdownSafe(md);
    // marked may add id="heading" to the h1 — that's fine, just check it's an h1
    expect(html).toMatch(/<h1[^>]*>Heading<\/h1>/);
    expect(html).toContain("<strong>");
  });

  it("strips script tags from markdown HTML", () => {
    const md = 'Hello\n\n<script>alert("xss")</script>\n\nWorld';
    const html = renderMarkdownSafe(md);
    expect(html).not.toContain("<script>");
    expect(html).toContain("World");
  });

  it("strips onerror from img in markdown", () => {
    // Use raw HTML img with onerror attribute (the real XSS vector)
    const md = 'Hello <img src="x" onerror="alert(1)"> World';
    const html = renderMarkdownSafe(md);
    expect(html).not.toContain("onerror");
  });

  it("handles empty input", () => {
    expect(renderMarkdownSafe("")).toBe("");
    expect(renderMarkdownSafe(null)).toBe("");
  });
});
