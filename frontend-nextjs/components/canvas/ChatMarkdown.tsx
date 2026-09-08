import React from "react";
import { renderMarkdownSafe } from "@/lib/sanitize";

/**
 * Markdown renderer for canvas side-panel chat messages.
 *
 * Agent research replies carry GFM tables (spec comparisons) and
 * headings/lists; rendering them as plain text made research answers
 * unreadable pipe-soup. This renders through the shared sanitized
 * markdown pipeline (lib/sanitize — DOMPurify over marked) with table
 * styling tuned for a narrow column: bordered cells, striped rows,
 * compact type, and horizontal scroll when a comparison table is wider
 * than the bubble.
 */
export default function ChatMarkdown({ content }: { content: string }) {
    return (
        <div
            className="prose prose-sm dark:prose-invert max-w-none
                [&_p]:my-1 [&_ul]:my-1 [&_ol]:my-1 [&_li]:my-0
                [&_h1]:text-base [&_h2]:text-sm [&_h3]:text-sm [&_h1]:my-2 [&_h2]:my-2 [&_h3]:my-1
                [&_blockquote]:my-1 [&_blockquote]:text-muted-foreground
                [&_table]:my-2 [&_table]:text-xs [&_table]:border-collapse
                [&_table]:block [&_table]:overflow-x-auto [&_table]:max-w-full
                [&_th]:border [&_th]:border-border [&_th]:bg-muted
                [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_th]:whitespace-nowrap
                [&_td]:border [&_td]:border-border [&_td]:px-2 [&_td]:py-1 [&_td]:align-top
                [&_tr:nth-child(even)]:bg-muted/40
                [&_strong]:font-semibold [&_a]:underline"
            data-testid="chat-markdown"
            dangerouslySetInnerHTML={{ __html: renderMarkdownSafe(content) }}
        />
    );
}
