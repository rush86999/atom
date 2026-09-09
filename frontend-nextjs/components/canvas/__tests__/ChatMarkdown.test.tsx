/**
 * ChatMarkdown — the canvas side-panel's research-reply renderer.
 *
 * Agent research replies are GFM markdown (spec comparison tables,
 * headings, lists). This pins: proper <table> rendering (the raw
 * pipe-text problem this component exists to fix), heading/list
 * conversion, and sanitization (scripts stripped — lib/sanitize
 * contract).
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import ChatMarkdown from "@/components/canvas/ChatMarkdown";

const COMPARISON_REPLY = [
    "Web research done — draft untouched.",
    "",
    "| Spec | Hydmech DM-10 | Linmac WG-350DSAV |",
    "|---|---|---|",
    "| Round @ 90° | 254 mm | **270 mm** |",
    "| Operation | Manual | Semi-auto |",
].join("\n");

describe("ChatMarkdown", () => {
    it("renders a GFM comparison table as a real table, not pipe text", () => {
        const { container } = render(<ChatMarkdown content={COMPARISON_REPLY} />);
        const table = container.querySelector("table");
        expect(table).not.toBeNull();
        // header cells for both machines
        expect(screen.getByText("Hydmech DM-10")).toBeInTheDocument();
        expect(screen.getByText("Linmac WG-350DSAV")).toBeInTheDocument();
        // bold spec value converted, not literal asterisks
        const strong = container.querySelector("strong");
        expect(strong?.textContent).toBe("270 mm");
        expect(container.textContent).not.toContain("|---");
    });

    it("renders headings and keeps the sanitized-markdown contract", () => {
        const { container } = render(<ChatMarkdown
            content={"## Findings\n\n- 10\" round capacity\n\n<script>alert(1)</script>"}
        />);
        expect(container.querySelector("h2")?.textContent).toBe("Findings");
        expect(container.querySelector("li")?.textContent).toContain("10\" round capacity");
        expect(container.querySelector("script")).toBeNull();
    });

    it("exposes a testid hook for UI tests", () => {
        render(<ChatMarkdown content="plain" />);
        expect(screen.getByTestId("chat-markdown")).toBeInTheDocument();
    });
});
