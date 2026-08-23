import React from "react";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import MarketplacePage from "@/pages/marketplace";
import { toast } from "react-hot-toast";

jest.mock("react-hot-toast", () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));

const okResponse = (body: any) => ({
  ok: true,
  status: 200,
  json: async () => body,
});
const errResponse = (status: number, body?: any) => ({
  ok: false,
  status,
  json: async () => body || {},
  text: async () => JSON.stringify(body || {}),
});

const TEMPLATES = [
  {
    template_id: "tpl-1",
    name: "Lead Enrichment",
    description: "Enrich leads with public data",
    category: "data_processing",
    author: "atom",
    version: "1.2.0",
    tags: ["salesforce", "hubspot"],
    usage_count: 342,
    rating: 4.5,
    created_at: "2026-01-10T00:00:00Z",
    complexity: "medium",
    steps: [
      { name: "Fetch lead", service: "salesforce", action: "query" },
      { name: "Enrich", service: "clearbit", action: "enrich" },
    ],
    input_schema: { lead_id: { type: "string" }, limit: { type: "number" } },
  },
  {
    template_id: "tpl-2",
    name: "Daily Report",
    description: "Send a daily summary report",
    category: "reporting",
    author: "atom",
    version: "0.9.0",
    tags: ["slack"],
    usage_count: 12,
    rating: 0,
    created_at: "2026-02-01T00:00:00Z",
    complexity: "low",
    steps: [],
    input_schema: {},
  },
];

describe("MarketplacePage", () => {
  const mockFetch = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = mockFetch;
    mockFetch.mockImplementation(() =>
      Promise.resolve(okResponse(TEMPLATES)),
    );
  });

  it("shows skeleton cards while templates are loading", () => {
    mockFetch.mockImplementation(() => new Promise(() => {}));
    const { container } = render(<MarketplacePage />);
    expect(
      screen.getByRole("heading", { name: /Workflow Marketplace/i }),
    ).toBeInTheDocument();
    expect(container.querySelectorAll(".animate-pulse").length).toBe(3);
  });

  it("renders template cards with mapped metadata", async () => {
    render(<MarketplacePage />);
    expect(await screen.findByText("Lead Enrichment")).toBeInTheDocument();
    expect(screen.getByText("Enrich leads with public data")).toBeInTheDocument();

    expect(screen.getAllByText("Data Processing").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Reporting").length).toBeGreaterThan(0);
    expect(screen.getByText("salesforce")).toBeInTheDocument();
    expect(screen.getByText("hubspot")).toBeInTheDocument();
    expect(screen.getByText("4.5")).toBeInTheDocument();
    expect(screen.getByText("342")).toBeInTheDocument();
    expect(screen.getByText("Daily Report")).toBeInTheDocument();
    expect(screen.getByText("0.0")).toBeInTheDocument();
  });

  it("shows the error banner when fetching templates fails", async () => {
    mockFetch.mockImplementation(() => Promise.resolve(errResponse(500)));
    render(<MarketplacePage />);
    await waitFor(() => {
      expect(
        screen.getByText(
          "Could not load workflow templates. Make sure the backend is running on port 8000, then refresh.",
        ),
      ).toBeInTheDocument();
    });
  });

  it("shows the empty state and clears filters", async () => {
    mockFetch.mockImplementation((url: string) =>
      url.includes("category=automation")
        ? Promise.resolve(okResponse([]))
        : Promise.resolve(okResponse(TEMPLATES)),
    );
    render(<MarketplacePage />);
    await screen.findByText("Lead Enrichment");

    fireEvent.click(screen.getByRole("button", { name: /Automation/i }));
    await waitFor(() => {
      expect(
        screen.getByText("No workflows found matching your criteria."),
      ).toBeInTheDocument();
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/workflow-templates?category=automation",
      expect.objectContaining({ headers: {} }),
    );

    fireEvent.click(screen.getByRole("button", { name: /Clear filters/i }));
    await waitFor(() => {
      expect(screen.getByText("Lead Enrichment")).toBeInTheDocument();
    });
    const plainCalls = mockFetch.mock.calls.filter(
      ([url]: [string]) => url === "/api/workflow-templates",
    );
    expect(plainCalls.length).toBeGreaterThanOrEqual(2);
  });

  it("filters templates client-side by search query", async () => {
    render(<MarketplacePage />);
    await screen.findByText("Lead Enrichment");

    fireEvent.change(
      screen.getByPlaceholderText("Search workflows..."),
      { target: { value: "daily" } },
    );
    expect(screen.getByText("Daily Report")).toBeInTheDocument();
    expect(screen.queryByText("Lead Enrichment")).not.toBeInTheDocument();

    fireEvent.change(
      screen.getByPlaceholderText("Search workflows..."),
      { target: { value: "zzz" } },
    );
    expect(
      screen.getByText("No workflows found matching your criteria."),
    ).toBeInTheDocument();
  });

  it("re-fetches with the selected category and renders category results", async () => {
    mockFetch.mockImplementation((url: string) =>
      url.includes("category=ai_ml")
        ? Promise.resolve(
            okResponse([
              {
                template_id: "tpl-ml",
                name: "ML Pipeline",
                description: "Train and evaluate a model",
                category: "ai_ml",
                author: "atom",
                version: "1.0.0",
                tags: ["python"],
                usage_count: 7,
                rating: 4.0,
                created_at: "2026-03-01T00:00:00Z",
                complexity: "high",
                steps: [],
                input_schema: {},
              },
            ]),
          )
        : Promise.resolve(okResponse(TEMPLATES)),
    );
    render(<MarketplacePage />);
    await screen.findByText("Lead Enrichment");

    fireEvent.click(screen.getByRole("button", { name: /AI\/ML/i }));
    await waitFor(() => {
      expect(screen.getByText("ML Pipeline")).toBeInTheDocument();
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/workflow-templates?category=ai_ml",
      expect.objectContaining({ headers: {} }),
    );
    expect(screen.queryByText("Lead Enrichment")).not.toBeInTheDocument();
  });

  it("imports a template via POST and shows a success toast", async () => {
    render(<MarketplacePage />);
    await screen.findByText("Lead Enrichment");

    fireEvent.click(screen.getAllByRole("button", { name: /^Import$/i })[0]);
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/workflow-templates/tpl-1/import",
        expect.objectContaining({ method: "POST" }),
      );
      expect(toast.success).toHaveBeenCalledWith(
        "Workflow imported successfully!",
      );
    });
  });

  it("shows an error toast when the import fails", async () => {
    mockFetch.mockImplementation((url: string) =>
      url.includes("/import")
        ? Promise.resolve(errResponse(403, { detail: "Not authorized" }))
        : Promise.resolve(okResponse(TEMPLATES)),
    );
    render(<MarketplacePage />);
    await screen.findByText("Lead Enrichment");

    fireEvent.click(screen.getAllByRole("button", { name: /^Import$/i })[0]);
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "Import failed: Not authorized",
      );
    });
  });

  it("shows a connection error toast when the import request throws", async () => {
    mockFetch.mockImplementation((url: string) =>
      url.includes("/import")
        ? Promise.reject(new Error("network down"))
        : Promise.resolve(okResponse(TEMPLATES)),
    );
    render(<MarketplacePage />);
    await screen.findByText("Lead Enrichment");

    fireEvent.click(screen.getAllByRole("button", { name: /^Import$/i })[0]);
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        "Failed to connect to server",
      );
    });
  });

  it("previews a template with steps and inputs, then imports from the dialog", async () => {
    render(<MarketplacePage />);
    await screen.findByText("Lead Enrichment");

    fireEvent.click(screen.getAllByRole("button", { name: /Preview/i })[0]);

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Lead Enrichment")).toBeInTheDocument();
    expect(within(dialog).getByText("medium")).toBeInTheDocument();
    expect(within(dialog).getByText("Fetch lead")).toBeInTheDocument();
    expect(within(dialog).getByText("Enrich")).toBeInTheDocument();
    expect(within(dialog).getByText("lead_id")).toBeInTheDocument();
    expect(within(dialog).getByText("limit")).toBeInTheDocument();

    fireEvent.click(
      within(dialog).getByRole("button", { name: /Import Workflow/i }),
    );
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/workflow-templates/tpl-1/import",
        expect.objectContaining({ method: "POST" }),
      );
      expect(toast.success).toHaveBeenCalledWith(
        "Workflow imported successfully!",
      );
    });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("toggles between grid and list view", async () => {
    render(<MarketplacePage />);
    await screen.findByText("Lead Enrichment");

    const toggleButtons = screen
      .getAllByRole("button")
      .filter(
        (button) =>
          !!button.querySelector('svg[class*="lucide-layout-grid"]') ||
          !!button.querySelector('svg[class*="lucide-list"]'),
      );
    expect(toggleButtons).toHaveLength(2);

    const [gridToggle, listToggle] = toggleButtons;
    expect(gridToggle.className).toContain("bg-secondary");
    expect(listToggle.className).not.toContain("bg-secondary");

    fireEvent.click(listToggle);

    await waitFor(() => {
      expect(listToggle.className).toContain("bg-secondary");
      expect(gridToggle.className).not.toContain("bg-secondary");
    });

    fireEvent.click(gridToggle);
    await waitFor(() => {
      expect(gridToggle.className).toContain("bg-secondary");
      expect(listToggle.className).not.toContain("bg-secondary");
    });
  });

  describe("personal starter readiness", () => {
    const PERSONAL_TEMPLATES = [
      {
        template_id: "template_personal_invoice_chase",
        name: "Personal: Invoice Chase (Freelancer)",
        description: "Chase unpaid invoices with approval gates",
        category: "business",
        author: "Atom",
        version: "1.0.0",
        tags: ["gmail"],
        usage_count: 0,
        rating: 0,
        complexity: "beginner",
        steps: [],
        input_schema: {},
      },
    ];

    it("shows a Connect CTA when an integration is missing", async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes("/readiness")) {
          return Promise.resolve(
            okResponse({
              success: true,
              ready: false,
              connected: [],
              missing: ["gmail"],
              connect_urls: ["/settings/integrations?connect=gmail"],
            }),
          );
        }
        return Promise.resolve(okResponse(PERSONAL_TEMPLATES));
      });

      render(<MarketplacePage />);
      expect(
        await screen.findByText("Personal: Invoice Chase (Freelancer)"),
      ).toBeInTheDocument();

      const cta = await screen.findByText(
        "Setup needed: connect gmail",
      );
      expect(cta.closest("a")).toHaveAttribute(
        "href",
        "/settings/integrations?connect=gmail",
      );
    });

    it("shows no setup badge when readiness reports ready", async () => {
      mockFetch.mockImplementation((url: string) => {
        if (url.includes("/readiness")) {
          return Promise.resolve(
            okResponse({
              success: true,
              ready: true,
              connected: ["gmail"],
              missing: [],
              connect_urls: [],
            }),
          );
        }
        return Promise.resolve(okResponse(PERSONAL_TEMPLATES));
      });

      render(<MarketplacePage />);
      await screen.findByText("Personal: Invoice Chase (Freelancer)");
      await waitFor(() => {
        expect(screen.queryByText(/Setup needed/i)).not.toBeInTheDocument();
      });
    });
  });
});
