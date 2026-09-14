/**
 * ResizableDivider — the draggable vertical border between the canvas view
 * and its chat panel. Locks the a11y contract (vertical separator with
 * value bounds) and that pointer/keyboard handlers reach the element.
 */

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { ResizableDivider } from "../ResizableDivider";
import type { ResizablePanelHandleProps } from "@/hooks/useResizablePanel";

function makeHandleProps(overrides: Partial<ResizablePanelHandleProps> = {}): ResizablePanelHandleProps {
    return {
        role: "separator",
        "aria-orientation": "vertical",
        "aria-label": "Resize panel",
        "aria-valuenow": 320,
        "aria-valuemin": 260,
        "aria-valuemax": 900,
        tabIndex: 0,
        onPointerDown: jest.fn(),
        onKeyDown: jest.fn(),
        onDoubleClick: jest.fn(),
        ...overrides,
    };
}

describe("ResizableDivider", () => {
    it("renders an accessible vertical separator", () => {
        render(<ResizableDivider {...makeHandleProps()} />);

        const handle = screen.getByTestId("panel-resizer");
        expect(handle).toHaveAttribute("role", "separator");
        expect(handle).toHaveAttribute("aria-orientation", "vertical");
        expect(handle).toHaveAttribute("aria-valuenow", "320");
        expect(handle).toHaveAttribute("aria-valuemin", "260");
        expect(handle).toHaveAttribute("aria-valuemax", "900");
        expect(handle).toHaveAttribute("tabindex", "0");
    });

    it("uses a custom label, test id and marks the drag state", () => {
        render(
            <ResizableDivider
                {...makeHandleProps()}
                label="Resize canvas chat panel"
                data-testid="canvas-panel-resizer"
                isResizing
            />
        );

        const handle = screen.getByTestId("canvas-panel-resizer");
        expect(handle).toHaveAttribute("aria-label", "Resize canvas chat panel");
        expect(handle).toHaveAttribute("data-resizing", "true");
    });

    it("forwards pointer, keyboard and double-click events", () => {
        const onPointerDown = jest.fn();
        const onKeyDown = jest.fn();
        const onDoubleClick = jest.fn();
        render(
            <ResizableDivider
                {...makeHandleProps({ onPointerDown, onKeyDown, onDoubleClick })}
            />
        );

        const handle = screen.getByTestId("panel-resizer");
        fireEvent.pointerDown(handle, { clientX: 100 });
        fireEvent.keyDown(handle, { key: "ArrowLeft" });
        fireEvent.doubleClick(handle);

        expect(onPointerDown).toHaveBeenCalledTimes(1);
        expect(onKeyDown).toHaveBeenCalledTimes(1);
        expect(onDoubleClick).toHaveBeenCalledTimes(1);
    });
});
