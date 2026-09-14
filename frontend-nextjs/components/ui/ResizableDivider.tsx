"use client";

/**
 * ResizableDivider — the draggable vertical border between two panes.
 *
 * Renders the border line itself (so the pane split stays visually a border,
 * just movable) plus an accessible `role="separator"` hit target that is
 * wider than the 1px line. Pair it with `useResizablePanel` and place it
 * between the two flex children:
 *
 *   <div className="flex">
 *     <div className="flex-1 min-w-0">view</div>
 *     <ResizableDivider {...panel.handleProps} isResizing={panel.isResizing} />
 *     <div style={{ width: panel.width }} className="shrink-0">chat</div>
 *   </div>
 */

import * as React from "react";

import { cn } from "@/lib/utils";
import type { ResizablePanelHandleProps } from "@/hooks/useResizablePanel";

export interface ResizableDividerProps
    extends Omit<ResizablePanelHandleProps, "aria-label"> {
    /** Accessible name for the separator. */
    label?: string;
    /** True while a drag is in flight (highlights the border). */
    isResizing?: boolean;
    className?: string;
    "data-testid"?: string;
}

export function ResizableDivider({
    label = "Resize panel",
    isResizing = false,
    className,
    "data-testid": testId = "panel-resizer",
    ...handleProps
}: ResizableDividerProps) {
    return (
        <div
            {...handleProps}
            aria-label={label}
            data-testid={testId}
            data-resizing={isResizing ? "true" : undefined}
            title="Drag to resize · double-click to reset"
            className={cn(
                // w-1.5 hit target; the border-l is the visible divider line.
                "group relative flex w-1.5 shrink-0 cursor-col-resize touch-none select-none",
                "items-center justify-center border-l border-border bg-muted/40",
                "transition-colors hover:bg-primary/20 focus-visible:outline-none",
                "focus-visible:ring-1 focus-visible:ring-ring focus-visible:ring-offset-1",
                isResizing && "bg-primary/30",
                className
            )}
        >
            <span
                aria-hidden="true"
                className={cn(
                    "pointer-events-none absolute top-1/2 left-1/2 h-8 w-1 -translate-x-1/2 -translate-y-1/2",
                    "rounded-full bg-muted-foreground/40 opacity-0 transition-opacity",
                    "group-hover:opacity-100 group-focus-visible:opacity-100",
                    isResizing && "opacity-100 bg-primary/60"
                )}
            />
        </div>
    );
}

export default ResizableDivider;
