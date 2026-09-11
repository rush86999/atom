/**
 * useResizablePanel — unit tests.
 *
 * The canvas chat/view split lets the operator shove the vertical border
 * left (small chat) or right (large chat). These tests lock the contract:
 * - drag maps pointer movement to panel width for both dock sides
 * - width is always clamped to [min, min(max, viewport - reserve)]
 * - keyboard resizing (Arrow keys / Home / End) + double-click reset
 * - the chosen width persists through localStorage
 */

import { renderHook, act } from "@testing-library/react";
import {
    useResizablePanel,
    type UseResizablePanelOptions,
} from "@/hooks/useResizablePanel";

/** jsdom lacks PointerEvent; a plain Event with the props we read is enough. */
function pointerEvent(type: string, props: Record<string, any> = {}): Event {
    const event = new Event(type, { bubbles: true, cancelable: true });
    Object.assign(event, props);
    return event;
}

function setup(options: Partial<UseResizablePanelOptions> = {}) {
    const initialProps: UseResizablePanelOptions = {
        defaultWidth: 320,
        minWidth: 200,
        maxWidth: 600,
        ...options,
    };
    return renderHook(
        (props: UseResizablePanelOptions) => useResizablePanel(props),
        { initialProps }
    );
}

function startDrag(result: { current: ReturnType<typeof useResizablePanel> }, clientX: number) {
    act(() => {
        result.current.handleProps.onPointerDown(
            pointerEvent("pointerdown", {
                pointerType: "mouse",
                button: 0,
                clientX,
            }) as any
        );
    });
}

function moveTo(clientX: number) {
    act(() => {
        window.dispatchEvent(pointerEvent("pointermove", { clientX }));
    });
}

const originalInnerWidth = window.innerWidth;

beforeEach(() => {
    window.localStorage.clear();
});

afterEach(() => {
    Object.defineProperty(window, "innerWidth", {
        writable: true,
        configurable: true,
        value: originalInnerWidth,
    });
    act(() => {
        window.dispatchEvent(pointerEvent("pointerup"));
    });
});

describe("useResizablePanel", () => {
    it("starts at the default width", () => {
        const { result } = setup();
        expect(result.current.width).toBe(320);
        expect(result.current.isResizing).toBe(false);
    });

    it("clamps a default outside the allowed range", () => {
        expect(setup({ defaultWidth: 50 }).result.current.width).toBe(200);
        expect(setup({ defaultWidth: 5000 }).result.current.width).toBe(600);
    });

    it("exposes an accessible vertical separator handle", () => {
        const { result } = setup();
        expect(result.current.handleProps.role).toBe("separator");
        expect(result.current.handleProps["aria-orientation"]).toBe("vertical");
        expect(result.current.handleProps["aria-valuenow"]).toBe(320);
        expect(result.current.handleProps["aria-valuemin"]).toBe(200);
        expect(result.current.handleProps["aria-valuemax"]).toBe(600);
        expect(result.current.handleProps.tabIndex).toBe(0);
    });

    it("grows a right-docked panel when the border is dragged left", () => {
        const { result } = setup();
        startDrag(result, 500);
        expect(result.current.isResizing).toBe(true);

        moveTo(450);
        expect(result.current.width).toBe(370);

        moveTo(300);
        expect(result.current.width).toBe(520);

        // Releasing the drag freezes the width.
        act(() => {
            window.dispatchEvent(pointerEvent("pointerup"));
        });
        expect(result.current.isResizing).toBe(false);
        moveTo(100);
        expect(result.current.width).toBe(520);
    });

    it("shrinks a right-docked panel when the border is dragged right", () => {
        const { result } = setup();
        startDrag(result, 500);
        moveTo(620);
        expect(result.current.width).toBe(200); // clamped at the minimum
        act(() => {
            window.dispatchEvent(pointerEvent("pointerup"));
        });
    });

    it("clamps the drag to the max (and the viewport cap)", () => {
        const { result } = setup();
        startDrag(result, 500);
        moveTo(-5000);
        expect(result.current.width).toBe(600);
        act(() => {
            window.dispatchEvent(pointerEvent("pointerup"));
        });
    });

    it("caps the max so the other pane keeps room on a narrow viewport", () => {
        Object.defineProperty(window, "innerWidth", {
            writable: true,
            configurable: true,
            value: 800,
        });
        const { result } = setup({ maxWidth: 900, viewportReserve: 320 });
        expect(result.current.maxWidth).toBe(480);
        startDrag(result, 500);
        moveTo(-5000);
        expect(result.current.width).toBe(480);
        act(() => {
            window.dispatchEvent(pointerEvent("pointerup"));
        });
    });

    it("re-clamps the stored width when the window shrinks", () => {
        const { result } = setup({ defaultWidth: 600 });
        expect(result.current.width).toBe(600);

        Object.defineProperty(window, "innerWidth", {
            writable: true,
            configurable: true,
            value: 700,
        });
        act(() => {
            window.dispatchEvent(new Event("resize"));
        });
        expect(result.current.width).toBe(380); // 700 - 320 reserve
    });

    it("resizes with the keyboard and resets on double-click", () => {
        const { result } = setup();
        const key = (k: string) =>
            act(() => {
                result.current.handleProps.onKeyDown({
                    key: k,
                    preventDefault: jest.fn(),
                } as any);
            });

        key("ArrowLeft"); // border left → larger
        expect(result.current.width).toBe(336);
        key("ArrowRight");
        expect(result.current.width).toBe(320);
        key("Home");
        expect(result.current.width).toBe(200);
        key("End");
        expect(result.current.width).toBe(600);
        key("a"); // unrelated keys are ignored
        expect(result.current.width).toBe(600);

        act(() => {
            result.current.handleProps.onDoubleClick({
                preventDefault: jest.fn(),
            } as any);
        });
        expect(result.current.width).toBe(320);
    });

    it("inverts drag + arrow direction for a left-docked panel", () => {
        const { result } = setup({ side: "left" });
        startDrag(result, 500);
        moveTo(450); // border left → smaller for a left panel
        expect(result.current.width).toBe(270);
        act(() => {
            window.dispatchEvent(pointerEvent("pointerup"));
        });

        act(() => {
            result.current.handleProps.onKeyDown({
                key: "ArrowLeft",
                preventDefault: jest.fn(),
            } as any);
        });
        expect(result.current.width).toBe(254);
    });

    it("sets the width programmatically through setWidth/reset", () => {
        const { result } = setup();
        act(() => result.current.setWidth(410));
        expect(result.current.width).toBe(410);
        act(() => result.current.setWidth(9999));
        expect(result.current.width).toBe(600);
        act(() => result.current.reset());
        expect(result.current.width).toBe(320);
    });

    it("restores a persisted width and writes changes back", () => {
        window.localStorage.setItem("atom.canvas.sidePanelWidth", "480");

        const { result } = setup({ storageKey: "atom.canvas.sidePanelWidth" });
        expect(result.current.width).toBe(480);

        act(() => result.current.setWidth(360));
        expect(window.localStorage.getItem("atom.canvas.sidePanelWidth")).toBe("360");
    });

    it("ignores a corrupt or out-of-range persisted width", () => {
        window.localStorage.setItem("k", "not-a-number");
        const { result } = setup({ storageKey: "k" });
        expect(result.current.width).toBe(320);

        window.localStorage.setItem("k2", "99999");
        const { result: clamped } = setup({ storageKey: "k2" });
        expect(clamped.current.width).toBe(600);
    });

    it("survives localStorage being unavailable", () => {
        // jsdom's Storage is not spy-able; swap the whole object out.
        const original = window.localStorage;
        Object.defineProperty(window, "localStorage", {
            configurable: true,
            value: {
                getItem: () => {
                    throw new Error("blocked");
                },
                setItem: () => {
                    throw new Error("blocked");
                },
                removeItem: () => {},
                clear: () => {},
            },
        });
        try {
            const { result } = setup({ storageKey: "k" });
            expect(result.current.width).toBe(320);
            act(() => result.current.setWidth(400));
            expect(result.current.width).toBe(400);
        } finally {
            Object.defineProperty(window, "localStorage", {
                configurable: true,
                value: original,
            });
        }
    });
});
