import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import CanvasIndexPage from "@/pages/canvas/index";
import { apiClient } from "@/lib/api-client";

jest.mock("@/lib/api-client", () => ({
  apiClient: {
    get: jest.fn(),
  },
}));

jest.mock("@/components/layout/Layout", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

const mockApiClient = apiClient as jest.Mocked<typeof apiClient>;

const CANVASES = [
  {
    canvas_id: "canvas-1",
    canvas_type: "sheets",
    action_type: "create",
    title: "Q3 Budget Spreadsheet",
    deleted: false,
    last_updated: "2026-07-10T00:00:00Z",
  },
  {
    canvas_id: "canvas-2",
    canvas_type: "email",
    action_type: "update",
    title: "Welcome Email Draft",
    deleted: false,
    last_updated: null,
  },
  {
    canvas_id: "canvas-3",
    canvas_type: "sheets",
    action_type: "delete",
    title: "Old Inventory Sheet",
    deleted: true,
    last_updated: "2026-07-01T00:00:00Z",
  },
];

describe("CanvasIndexPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (mockApiClient.get as jest.Mock).mockResolvedValue({
      data: { canvases: CANVASES },
    });
  });

  it("shows skeleton loading cards while fetching", () => {
    (mockApiClient.get as jest.Mock).mockReturnValue(new Promise(() => {}));
    const { container } = render(<CanvasIndexPage />);
    expect(container.querySelectorAll(".animate-pulse").length).toBe(3);
  });

  it("renders the canvas grid with titles, types and badges", async () => {
    render(<CanvasIndexPage />);

    await waitFor(() => {
      expect(screen.getByText("Q3 Budget Spreadsheet")).toBeInTheDocument();
    });

    expect(mockApiClient.get).toHaveBeenCalledWith("/api/canvas/");
    expect(screen.getByText("Welcome Email Draft")).toBeInTheDocument();
    expect(screen.getByText("Old Inventory Sheet")).toBeInTheDocument();

    // Type badges (2 card badges + 1 filter button label)
    expect(screen.getAllByText("sheets")).toHaveLength(3);
    // Type badges (filter button label + card badge)
    expect(screen.getAllByText("email")).toHaveLength(2);

    // Action badges
    expect(screen.getByText("Edited")).toBeInTheDocument();
    expect(screen.getByText("Deleted")).toBeInTheDocument();

    // Unknown date fallback for canvases without last_updated
    expect(screen.getByText("Unknown date")).toBeInTheDocument();
  });

  it("renders type filter buttons with counts derived from all canvases", async () => {
    render(<CanvasIndexPage />);

    await waitFor(() => {
      expect(screen.getByText("Q3 Budget Spreadsheet")).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: /all \(3\)/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sheets/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /email/i })).toBeInTheDocument();
  });

  it("filters the grid by canvas type and preserves type-count buttons", async () => {
    render(<CanvasIndexPage />);

    await waitFor(() => {
      expect(screen.getByText("Q3 Budget Spreadsheet")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /sheets/i }));

    await waitFor(() => {
      expect(screen.queryByText("Welcome Email Draft")).not.toBeInTheDocument();
    });
    expect(screen.getByText("Q3 Budget Spreadsheet")).toBeInTheDocument();
    expect(screen.getByText("Old Inventory Sheet")).toBeInTheDocument();

    // Other type buttons remain visible while a filter is active (BUG-073)
    expect(screen.getByRole("button", { name: /email/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /all \(3\)/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /all \(3\)/i }));

    await waitFor(() => {
      expect(screen.getByText("Welcome Email Draft")).toBeInTheDocument();
    });
  });

  it("shows the empty state when no canvases exist", async () => {
    (mockApiClient.get as jest.Mock).mockResolvedValue({
      data: { canvases: [] },
    });

    render(<CanvasIndexPage />);

    await waitFor(() => {
      expect(screen.getByText("No canvases yet.")).toBeInTheDocument();
    });
  });

  it("shows the empty state when the fetch fails", async () => {
    (mockApiClient.get as jest.Mock).mockRejectedValue(new Error("network down"));

    render(<CanvasIndexPage />);

    await waitFor(() => {
      expect(screen.getByText("No canvases yet.")).toBeInTheDocument();
    });
  });

  it("links each canvas card to its detail page", async () => {
    render(<CanvasIndexPage />);

    await waitFor(() => {
      expect(screen.getByText("Q3 Budget Spreadsheet")).toBeInTheDocument();
    });

    const link = screen.getByText("Q3 Budget Spreadsheet").closest("a");
    expect(link).toHaveAttribute("href", "/canvas/canvas-1");
  });
});
