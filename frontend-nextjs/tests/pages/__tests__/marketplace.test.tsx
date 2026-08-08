import React from "react";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import MarketplacePage from "@/pages/marketplace";
import { toast } from "react-hot-toast";

jest.mock("react-hot-toast", () => {
  const success = jest.fn();
  const error = jest.fn();
  const toast = { success, error };
  return {
    __esModule: true,
    default: toast,
    toast,
    success,
    error,
  };
});

const TEMPLATES = [
  {
    template_id: "tpl-1",
    name: "Invoice Auto-Approval",
    description: "Automatically approves invoices under $5k",
    category: "automation",
    author: "ATOM Team",
    version: "1.2.0",
    tags: ["slack", "quickbooks"],
    usage_count: 42,
    rating: 4.5,
    created_at: "2026-01-15T00:00:00Z",
    complexity: "Medium",
    steps: [
      { name: "Send approval request", service: "slack", action: "send_message" },
      { name: "Approve invoice", service: "quickbooks", action: "approve" },
    ],
    input_schema: { invoice_id: { type: "string" } },
  },
  {
    template_id: "tpl-2",
    name: "Daily KPI Digest",
    description: "Sends a daily KPI summary to the team channel",
    category: "reporting",
    author: "Data Team",
    version: "0.9.0",
    tags: ["teams"],
    usage_count: 7,
    rating: 3.2,
    created_at: "2026-02-01T00:00:00Z",
    complexity: "Low",
    steps: [],
    input_schema: {},
  },
];

function okResponse(body: any) {
  return { ok: true, json: async () => body };
}

function errResponse(status: number, body: any = {}) {
  return { ok: false, status, json: async () => body, text: async () => "" };
}

describe("MarketplacePage", () => {
  const mockFetch = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = mockFetch;
    jest.spyOn(Storage.prototype, "getItem").mockReturnValue("tok-123");
    mockFetch.mockImplementation((url: string, opts?: any) => {
      if ((opts?.method || "GET") === "POST") {
        if (url.includes("/import")) return Promise.resolve(okResponse({ success: true }));
      }
      if (url.includes("category=")) return Promise.resolve(okResponse([]));
      return Promise.resolve(okResponse(TEMPLATES));
    });
  });

  it("shows skeleton cards while loading", () => {
    mockFetch.mockImplementation(() => new Promise(() => {}));
    const { container } = render(<MarketplacePage />);

    expect(container.querySelectorAll('[class*="animate-pulse"]')).toHaveLength(3);
    expect(screen.queryByText("Invoice Auto-Approval")).not.toBeInTheDocument();
    expect(screen.queryByText(/No workflows found/)).not.toBeInTheDocument();
  });

  it("renders template cards with metadata after fetch", async () => {
    render(<MarketplacePage />);

    expect(await screen.findByText("Invoice Auto-Approval")).toBeInTheDocument();
    expect(screen.getByText("Daily KPI Digest")).toBeInTheDocument();
    expect(screen.getByText("Automation")).toBeInTheDocument();
    expect(screen.getByText("Reporting")).toBeInTheDocument();
    expect(screen.getByText("4.5")).toBeInTheDocument();
    expect(screen.getByText("3.2")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("slack")).toBeInTheDocument();
    expect(screen.getByText("quickbooks")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /preview/i })).toBeInTheDocument();

    // Fetch count regression: unstable effect deps previously refetched forever
    const templateCalls = mockFetch.mock.calls.filter((c) =>
      (c[0] as string).startsWith("/api/workflow-templates")
    );
    expect(templateCalls).toHaveLength(1);
    expect((templateCalls[0] as any[])[1]?.headers?.Authorization).toBe("Bearer tok-123");
  });

  it("re-fetches with the selected category and shows the empty state for it", async () => {
    render(<MarketplacePage />);

    await waitFor(() => {
      expect(screen.getByText("Invoice Auto-Approval")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /data processing/i }));

    await waitFor(() => {
      expect(
        screen.getByText("No workflows found matching your criteria.")
      ).toBeInTheDocument();
    });

    const categoryCall = mockFetch.mock.calls.find((c) =>
      (c[0] as string).includes("category=data_processing")
    );
    expect(categoryCall).toBeTruthy();

    // Clear filters refetches the full list
    fireEvent.click(screen.getByRole("button", { name: /clear filters/i }));
    expect(await screen.findByText("Invoice Auto-Approval")).toBeInTheDocument();
  });

  it("filters templates client-side by search query", async () => {
    render(<MarketplacePage />);

    await waitFor(() => {
      expect(screen.getByText("Invoice Auto-Approval")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText("Search workflows..."), {
      target: { value: "KPI" },
    });

    expect(screen.getByText("Daily KPI Digest")).toBeInTheDocument();
    expect(screen.queryByText("Invoice Auto-Approval")).not.toBeInTheDocument();
  });

  it("imports a template via POST and shows a success toast", async () => {
    render(<MarketplacePage />);

    await waitFor(() => {
      expect(screen.getByText("Invoice Auto-Approval")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /import/i }));

    await waitFor(() => {
      expect(
        mockFetch.mock.calls.some(
          (c) =>
            (c[0] as string).includes("/api/workflow-templates/tpl-1/import") &&
            (c[1] as any)?.method === "POST"
        )
      ).toBe(true);
    });
    expect(toast.success).toHaveBeenCalledWith("Workflow imported successfully!");
  });

  it("shows an error toast when the import fails", async () => {
    mockFetch.mockImplementation((url: string, opts?: any) => {
      if ((opts?.method || "GET") === "POST") {
        return Promise.resolve(
          errResponse(500, { detail: "Template version conflict" })
        );
      }
      return Promise.resolve(okResponse(TEMPLATES));
    });
    render(<MarketplacePage />);

    await waitFor(() => {
      expect(screen.getByText("Invoice Auto-Approval")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /import/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Import failed: Template version conflict");
    });
  });

  it("previews a template with steps and inputs, then imports from the dialog", async () => {
    render(<MarketplacePage />);

    await waitFor(() => {
      expect(screen.getByText("Invoice Auto-Approval")).toBeInTheDocument();
    });

    fireEvent.click(screen.getAllByRole("button", { name: /preview/i })[0]);

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Invoice Auto-Approval")).toBeInTheDocument();
    expect(within(dialog).getByText("v1.2.0")).toBeInTheDocument();
    expect(within(dialog).getByText("Medium")).toBeInTheDocument();
    expect(within(dialog).getByText("Send approval request")).toBeInTheDocument();
    expect(
      within(dialog).getByText(/Using slack to send_message/i)
    ).toBeInTheDocument();
    expect(within(dialog).getByText("invoice_id")).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole("button", { name: /import workflow/i }));

    await waitFor(() => {
      expect(
        mockFetch.mock.calls.some(
          (c) =>
            (c[0] as string).includes("/api/workflow-templates/tpl-1/import") &&
            (c[1] as any)?.method === "POST"
        )
      ).toBe(true);
    });
    expect(toast.success).toHaveBeenCalledWith("Workflow imported successfully!");
  });

  it("shows the error banner when fetching templates fails", async () => {
    mockFetch.mockResolvedValue(errResponse(503));
    render(<MarketplacePage />);

    expect(
      await screen.findByText(
        "Could not load workflow templates. Make sure the backend is running on port 8000, then refresh."
      )
    ).toBeInTheDocument();
  });

  it("shows the empty state and clears filters", async () => {
    mockFetch.mockResolvedValue(okResponse([]));
    render(<MarketplacePage />);

    expect(
      await screen.findByText("No workflows found matching your criteria.")
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /clear filters/i }));
    expect(
      mockFetch.mock.calls.filter((c) =>
        (c[0] as string).startsWith("/api/workflow-templates")
      ).length
    ).toBeGreaterThanOrEqual(1);
  });

  it("toggles between grid and list view", async () => {
    const { container } = render(<MarketplacePage />);

    await waitFor(() => {
      expect(screen.getByText("Invoice Auto-Approval")).toBeInTheDocument();
    });

    const gridView = container.querySelector('[class*="grid grid-cols-1"]');
    expect(gridView).toBeTruthy();

    const viewButtons = screen.getAllByRole("button", { name: "" });
    fireEvent.click(viewButtons[1]); // List icon button

    await waitFor(() => {
      expect(container.querySelector('[class*="grid grid-cols-1"]')).toBeNull();
    });
    expect(container.querySelector('[class*="space-y-4"]')).toBeTruthy();
  });
});
