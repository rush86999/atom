import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import BusinessFactsPageWrapper from "@/pages/admin/business-facts";
import { businessFactsAPI } from "@/lib/api-admin";
import { useToast } from "@/components/ui/use-toast";

jest.mock("@/lib/api-admin", () => ({
  businessFactsAPI: {
    listFacts: jest.fn(),
    deleteFact: jest.fn(),
    createFact: jest.fn(),
    updateFact: jest.fn(),
  },
  AdminPoller: jest.fn().mockImplementation(() => ({
    start: jest.fn(),
    stop: jest.fn(),
  })),
}));

jest.mock("@/components/ui/use-toast", () => ({
  useToast: jest.fn(() => ({ toast: jest.fn() })),
}));

const mockFacts = [
  {
    id: "fact-1",
    fact: "Acme Corp was founded in 1998",
    citations: ["https://acme.com/about"],
    reason: "Company background",
    domain: "company",
    verification_status: "verified",
    created_at: "2026-01-01T00:00:00Z",
    last_verified: "2026-01-02T00:00:00Z",
  },
  {
    id: "fact-2",
    fact: "Q3 revenue grew 12%",
    citations: ["https://acme.com/financials"],
    reason: "Earnings report",
    domain: "finance",
    verification_status: "unverified",
    created_at: "2026-02-01T00:00:00Z",
    last_verified: "2026-02-02T00:00:00Z",
  },
];

describe("BusinessFactsPage", () => {
  const mockToast = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (useToast as jest.Mock).mockReturnValue({ toast: mockToast });
    (businessFactsAPI.listFacts as jest.Mock).mockResolvedValue({
      data: { facts: mockFacts },
    });
    (businessFactsAPI.deleteFact as jest.Mock).mockResolvedValue({
      data: { success: true },
    });
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({}),
    }) as any;
    window.confirm = jest.fn(() => true) as any;
  });

  describe("Component Import/Export", () => {
    it("should import and render the page with a loading state", () => {
      render(<BusinessFactsPageWrapper />);
      expect(
        document.querySelector(".animate-spin")
      ).toBeInTheDocument();
    });
  });

  describe("Fact fetching and display", () => {
    it("should fetch and display facts with stats", async () => {
      render(<BusinessFactsPageWrapper />);

      await waitFor(() => {
        expect(
          screen.getByRole("heading", { name: /business facts/i })
        ).toBeInTheDocument();
      });

      expect(businessFactsAPI.listFacts).toHaveBeenCalledWith({
        status: "all",
        domain: "",
        limit: 100,
      });

      // Table rows render fact content
      expect(screen.getByText("Acme Corp was founded in 1998")).toBeInTheDocument();
      expect(screen.getByText("Q3 revenue grew 12%")).toBeInTheDocument();

      // Stats cards
      expect(screen.getByText("Total Facts")).toBeInTheDocument();
      expect(screen.getByText("Verified")).toBeInTheDocument();
      expect(screen.getByText("Unverified")).toBeInTheDocument();
      expect(screen.getByText("Outdated")).toBeInTheDocument();
    });

    it("should handle empty fact list response", async () => {
      (businessFactsAPI.listFacts as jest.Mock).mockResolvedValue({
        data: { facts: [] },
      });
      render(<BusinessFactsPageWrapper />);

      await waitFor(() => {
        expect(
          screen.getByRole("heading", { name: /business facts/i })
        ).toBeInTheDocument();
      });
      expect(screen.getByText("Total Facts")).toBeInTheDocument();
      expect(screen.getAllByText("0")).toHaveLength(4);
    });

    it("should handle fetch failure by showing an empty table", async () => {
      (businessFactsAPI.listFacts as jest.Mock).mockRejectedValue(
        new Error("network down")
      );
      render(<BusinessFactsPageWrapper />);

      await waitFor(() => {
        expect(
          screen.getByRole("heading", { name: /business facts/i })
        ).toBeInTheDocument();
      });
      expect(screen.getByText("Total Facts")).toBeInTheDocument();
    });
  });

  describe("Search filtering", () => {
    it("should filter facts by search query", async () => {
      render(<BusinessFactsPageWrapper />);

      await waitFor(() => {
        expect(screen.getByText("Q3 revenue grew 12%")).toBeInTheDocument();
      });

      fireEvent.change(
        screen.getByPlaceholderText("Search facts, domains, or reasons..."),
        { target: { value: "revenue" } }
      );

      expect(screen.getByText("Q3 revenue grew 12%")).toBeInTheDocument();
      expect(screen.queryByText("Acme Corp was founded in 1998")).not.toBeInTheDocument();
    });

    it("should clear filter when query is emptied", async () => {
      render(<BusinessFactsPageWrapper />);

      await waitFor(() => {
        expect(screen.getByText("Q3 revenue grew 12%")).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText("Search facts, domains, or reasons...");
      fireEvent.change(searchInput, { target: { value: "revenue" } });
      expect(screen.queryByText("Acme Corp was founded in 1998")).not.toBeInTheDocument();

      fireEvent.change(searchInput, { target: { value: "" } });
      expect(screen.getByText("Acme Corp was founded in 1998")).toBeInTheDocument();
    });
  });

  describe("Refresh", () => {
    it("should refetch facts when refresh button is clicked", async () => {
      render(<BusinessFactsPageWrapper />);

      await waitFor(() => {
        expect(
          screen.getByRole("heading", { name: /business facts/i })
        ).toBeInTheDocument();
      });

      const callsBefore = (businessFactsAPI.listFacts as jest.Mock).mock.calls.length;
      fireEvent.click(screen.getByRole("button", { name: /refresh/i }));

      await waitFor(() => {
        expect((businessFactsAPI.listFacts as jest.Mock).mock.calls.length).toBeGreaterThan(callsBefore);
      });
    });
  });

  const clickDeleteButton = () => {
    const deleteIcon = document.querySelector(
      "table button svg.lucide-trash-2"
    );
    const button = deleteIcon?.closest("button");
    expect(button).not.toBeNull();
    fireEvent.click(button as HTMLButtonElement);
  };

  describe("Delete fact", () => {
    it("should delete a fact after confirmation and refetch", async () => {
      render(<BusinessFactsPageWrapper />);

      await waitFor(() => {
        expect(screen.getByText("Acme Corp was founded in 1998")).toBeInTheDocument();
      });

      clickDeleteButton();

      await waitFor(() => {
        expect(businessFactsAPI.deleteFact).toHaveBeenCalledWith("fact-1");
      });
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Fact deleted" })
      );
    });

    it("should not delete when confirmation is declined", async () => {
      window.confirm = jest.fn(() => false) as any;
      render(<BusinessFactsPageWrapper />);

      await waitFor(() => {
        expect(screen.getByText("Acme Corp was founded in 1998")).toBeInTheDocument();
      });

      clickDeleteButton();

      expect(businessFactsAPI.deleteFact).not.toHaveBeenCalled();
    });

    it("should show error toast when delete fails", async () => {
      (businessFactsAPI.deleteFact as jest.Mock).mockRejectedValue({
        userMessage: "Permission denied",
      });
      render(<BusinessFactsPageWrapper />);

      await waitFor(() => {
        expect(screen.getByText("Acme Corp was founded in 1998")).toBeInTheDocument();
      });

      clickDeleteButton();

      await waitFor(() => {
        expect(mockToast).toHaveBeenCalledWith(
          expect.objectContaining({
            title: "Delete failed",
            variant: "destructive",
          })
        );
      });
    });
  });

  describe("Create/Edit dialog", () => {
    it("should open create dialog when New Fact is clicked", async () => {
      render(<BusinessFactsPageWrapper />);

      await waitFor(() => {
        expect(
          screen.getByRole("heading", { name: /business facts/i })
        ).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole("button", { name: /new fact/i }));

      await waitFor(() => {
        expect(screen.getByText("Create Business Fact")).toBeInTheDocument();
      });
    });
  });

  describe("Keyboard shortcuts", () => {
    it("should open create dialog when 'n' is pressed", async () => {
      render(<BusinessFactsPageWrapper />);

      await waitFor(() => {
        expect(
          screen.getByRole("heading", { name: /business facts/i })
        ).toBeInTheDocument();
      });

      fireEvent.keyDown(window, { key: "n" });

      await waitFor(() => {
        expect(screen.getByText("Create Business Fact")).toBeInTheDocument();
      });
    });

    it("should open shortcuts help when '?' is pressed", async () => {
      render(<BusinessFactsPageWrapper />);

      await waitFor(() => {
        expect(
          screen.getByRole("heading", { name: /business facts/i })
        ).toBeInTheDocument();
      });

      fireEvent.keyDown(window, { key: "?" });

      await waitFor(() => {
        expect(screen.getByText("Keyboard Shortcuts")).toBeInTheDocument();
      });
    });

    it("should open shortcuts help via the Shortcuts button", async () => {
      render(<BusinessFactsPageWrapper />);

      await waitFor(() => {
        expect(
          screen.getByRole("heading", { name: /business facts/i })
        ).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole("button", { name: /shortcuts/i }));

      await waitFor(() => {
        expect(screen.getByText("Keyboard Shortcuts")).toBeInTheDocument();
      });
    });
  });
});
