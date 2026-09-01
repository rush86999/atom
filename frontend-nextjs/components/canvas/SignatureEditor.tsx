"use client";

/**
 * Rich signature editor for the canvas email composer — a Signature-flavored
 * wrapper around the shared RichTextEditor (same toolbar, <br> line breaks).
 *
 * The value is an HTML STRING: styled signatures (bold/italic, links,
 * colors, rules) are a supported feature and render in outgoing mail via
 * integrations/outlook_service._body_to_html. sanitizeSignatureHtml is the
 * dedicated DOMPurify profile (inline style + href allowed for colors and
 * links; scripts/handlers/images/forms forbidden).
 */

import React from "react";
import RichTextEditor, { sanitizeEmailHtml } from "./RichTextEditor";

export function sanitizeSignatureHtml(dirty: string | undefined | null): string {
  return sanitizeEmailHtml(dirty);
}

export default function SignatureEditor({
  value,
  onChange,
}: {
  value: string;
  onChange: (html: string) => void;
}) {
  return (
    <RichTextEditor
      value={value}
      onChange={onChange}
      testIdPrefix="canvas-signature"
      minHeight="72px"
    />
  );
}
