/**
 * Canvases gallery page tests — the journey's step 1 entry point.
 *
 * Covers: the "New canvas" button creating a blank canvas and routing to it,
 * the same CTA in the empty state, and create-failure surfacing.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import CanvasIndexPage from "@/pages/canvas/index";

const mockRouterPush = jest.fn();

jest.mock("next/router", () => ({
  useRouter: () => ({
    push: mockRouterPush,
    replace: jest.fn(),
    prefetch: jest.fn(),
    back: jest.fn(),
    pathname: "/canvas",
    query: {},
    asPath: "/canvas",
    events: { on: jest.fn(), off: jest.fn(), emit: jest.fn() },
  }),
}));

jest.mock("@/lib/canvas-api", () => ({
  __esModule: true,
  createBlankCanvas: jest.fn(),
}));

jest.mock("@/lib/pdf-canvas-api", () => ({
  __esModule: true,
  createPdfFromUpload: jest.fn(),
}));

// The gallery lists canvases through the shared api-client.
const mockGet = jest.fn();
jest.mock("@/lib/api-client", () => ({
  __esModule: true,
  apiClient: { get: (...args: any[]) => mockGet(...args) },
}));

import { createBlankCanvas } from "@/lib/canvas-api";
const mockedCreate = createBlankCanvas as jest.Mock;

describe("CanvasIndexPage — blank canvas creation", () => {
  beforeEach(() => {
    jest.resetAllMocks();
    window.alert = jest.fn();
    mockGet.mockResolvedValue({
      data: { canvases: [], total: 0 },
    });
  });

  it("creates a blank canvas and routes to it", async () => {
    mockedCreate.mockResolvedValue({ canvas_id: "c-9", url: "/canvas/c-9" });
    render(<CanvasIndexPage />);

    // The list fetch resolves empty → gallery shows the empty state.
    await waitFor(() => expect(screen.getByTestId("new-blank-canvas-button")).toBeEnabled());
    fireEvent.click(screen.getByTestId("new-blank-canvas-button"));

    await waitFor(() => expect(mockedCreate).toHaveBeenCalledWith());
    await waitFor(() => expect(mockRouterPush).toHaveBeenCalledWith("/canvas/c-9"));
  });

  it("offers the same creation path from the empty state", async () => {
    mockedCreate.mockResolvedValue({ canvas_id: "c-10", url: "/canvas/c-10" });
    render(<CanvasIndexPage />);

    const emptyCta = await screen.findByTestId("new-blank-canvas-empty-state");
    fireEvent.click(emptyCta);

    await waitFor(() => expect(mockRouterPush).toHaveBeenCalledWith("/canvas/c-10"));
  });

  it("surfaces creation failures instead of routing", async () => {
    mockedCreate.mockRejectedValue({
      response: { data: { error: { message: "boom" } } },
    });
    render(<CanvasIndexPage />);

    fireEvent.click(await screen.findByTestId("new-blank-canvas-button"));
    await waitFor(() => expect(mockedCreate).toHaveBeenCalled());
    expect(mockRouterPush).not.toHaveBeenCalled();
    // window.alert carried the message (page-level convention).
    await waitFor(() =>
      expect((window.alert as jest.Mock).mock.calls.some(c =>
        String(c[0]).includes("boom"),
      )).toBe(true),
    );
  });
});
