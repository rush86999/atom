/**
 * CanvasIndexPage tests (pages/canvas/index.tsx, was 0% coverage)
 *
 * Covers: loading skeleton, canvas grid (titles, type badges, edited/deleted
 * tags, dates), empty state, type-count filter buttons, filtered refetch,
 * and fetch-failure fallback.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import CanvasIndexPage from "@/pages/canvas/index";

jest.mock("@/components/layout/Layout", () => ({
  __esModule: true,
  default: ({ children }: any) => <div data-testid="layout">{children}</div>,
  Layout: ({ children }: any) => <div data-testid="layout">{children}</div>,
}));

const mockGet = jest.fn();
jest.mock("../../lib/api-client", () => ({
  apiClient: {
    get: (...args: any[]) => mockGet(...args),
  },
}));

const CANVASES = [
  {
    canvas_id: "cv1",
    canvas_type: "sheets",
    action_type: "present",
    title: "Q3 Budget",
    deleted: false,
    last_updated: "2026-08-01T10:00:00Z",
  },
  {
    canvas_id: "cv2",
    canvas_type: "docs",
    action_type: "update",
    title: "Meeting Notes",
    deleted: false,
    last_updated: "2026-08-02T10:00:00Z",
  },
  {
    canvas_id: "cv3",
    canvas_type: "email",
    action_type: "delete",
    title: "Old Newsletter",
    deleted: true,
    last_updated: null,
  },
];

describe("CanvasIndexPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGet.mockResolvedValue({ data: { canvases: CANVASES } });
  });

  test("shows loading skeleton while fetching", () => {
    mockGet.mockReturnValue(new Promise(() => {}));
    render(<CanvasIndexPage />);
    expect(document.querySelectorAll(".animate-pulse").length).toBe(3);
  });

  test("renders canvases with titles and badges", async () => {
    render(<CanvasIndexPage />);
    await waitFor(() => expect(screen.getByText("Q3 Budget")).toBeInTheDocument());
    expect(screen.getByText("Meeting Notes")).toBeInTheDocument();
    expect(screen.getAllByText("sheets").length).toBeGreaterThan(0);
    expect(screen.getAllByText("docs").length).toBeGreaterThan(0);
    expect(screen.getByText("Edited")).toBeInTheDocument();
    expect(screen.getByText("Deleted")).toBeInTheDocument();
    expect(screen.getByText("Unknown date")).toBeInTheDocument();
  });

  test("links each canvas to its detail page", async () => {
    render(<CanvasIndexPage />);
    await waitFor(() => expect(screen.getByText("Q3 Budget")).toBeInTheDocument());
    const link = screen.getByText("Q3 Budget").closest("a");
    expect(link?.getAttribute("href")).toBe("/canvas/cv1");
  });

  test("renders empty state when no canvases", async () => {
    mockGet.mockResolvedValue({ data: { canvases: [] } });
    render(<CanvasIndexPage />);
    await waitFor(() => expect(screen.getByText("No canvases yet.")).toBeInTheDocument());
    expect(screen.getByText("All (0)")).toBeInTheDocument();
  });

  test("handles fetch failure gracefully", async () => {
    mockGet.mockRejectedValue(new Error("down"));
    render(<CanvasIndexPage />);
    await waitFor(() => expect(screen.getByText("No canvases yet.")).toBeInTheDocument());
  });

  test("type filter buttons show counts and filter the grid", async () => {
    render(<CanvasIndexPage />);
    await waitFor(() => expect(screen.getByText("Q3 Budget")).toBeInTheDocument());

    expect(screen.getByRole("button", { name: /All \(3\)/ })).toBeInTheDocument();
    const sheetsBtn = screen.getByRole("button", { name: /sheets/ });
    expect(sheetsBtn.textContent).toContain("1");

    fireEvent.click(screen.getByRole("button", { name: /sheets/ }));
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledTimes(2);
    });
    expect(screen.getByText("Q3 Budget")).toBeInTheDocument();
    expect(screen.queryByText("Meeting Notes")).not.toBeInTheDocument();
  });

  test("resetting filter to All restores the full grid", async () => {
    render(<CanvasIndexPage />);
    await waitFor(() => expect(screen.getByText("Q3 Budget")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /sheets/ }));
    await waitFor(() => expect(screen.queryByText("Meeting Notes")).not.toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /All \(3\)/ }));
    await waitFor(() => expect(screen.getByText("Meeting Notes")).toBeInTheDocument());
    expect(screen.getByText("Q3 Budget")).toBeInTheDocument();
  });

  test("renders canvas with unknown type using fallback icon", async () => {
    mockGet.mockResolvedValue({
      data: { canvases: [{ canvas_id: "cv4", canvas_type: "custom", action_type: "present", title: null, deleted: false, last_updated: null }] },
    });
    render(<CanvasIndexPage />);
    await waitFor(() => expect(screen.getByText("cv4")).toBeInTheDocument());
    expect(screen.getAllByText("custom").length).toBeGreaterThan(0);
  });
});
