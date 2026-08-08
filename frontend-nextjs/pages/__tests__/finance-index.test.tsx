import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import FinancePage from "@/pages/finance/index";
import { useToast } from "@/components/ui/use-toast";

jest.mock("@/components/finance/FinanceOverview", () => ({
  __esModule: true,
  default: () => <div data-testid="finance-overview" />,
}));
jest.mock("@/components/finance/TransactionsList", () => ({
  __esModule: true,
  default: () => <div data-testid="transactions-list" />,
}));
jest.mock("@/components/finance/BudgetPlanner", () => ({
  __esModule: true,
  default: () => <div data-testid="budget-planner" />,
}));
jest.mock("@/components/finance/InvoiceManager", () => ({
  __esModule: true,
  default: () => <div data-testid="invoice-manager" />,
}));
jest.mock("@/components/finance/SubscriptionTracker", () => ({
  __esModule: true,
  default: () => <div data-testid="subscription-tracker" />,
}));
jest.mock("@/components/finance/CategorizationReview", () => ({
  __esModule: true,
  default: () => <div data-testid="categorization-review" />,
}));
jest.mock("@/components/finance/AccountantPortal", () => ({
  __esModule: true,
  default: () => <div data-testid="accountant-portal" />,
}));
jest.mock("@/components/finance/ForecastingSandbox", () => ({
  __esModule: true,
  default: () => <div data-testid="forecasting-sandbox" />,
}));

jest.mock("@/components/ui/use-toast", () => ({
  useToast: jest.fn(() => ({ toast: jest.fn() })),
}));

const TRANSACTIONS = {
  data: {
    transactions: [
      {
        id: "tx-1",
        date: "2026-08-01",
        description: 'Coffee with "client"',
        merchant: "Starbucks",
        amount: -12.5,
        suggested_category: "Meals",
        confidence: 0.9,
        reasoning: "Morning coffee",
      },
      {
        id: "tx-2",
        date: "2026-08-02",
        description: "Server hosting",
        merchant: "AWS",
        amount: 250.0,
        suggested_category: "Infrastructure",
        confidence: 0.95,
        reasoning: "",
      },
    ],
  },
};

describe("FinancePage", () => {
  const mockToast = jest.fn();
  const mockFetch = jest.fn();
  let getItemSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    (useToast as jest.Mock).mockReturnValue({ toast: mockToast });
    getItemSpy = jest.spyOn(Storage.prototype, "getItem").mockReturnValue("tok-123");
    global.fetch = mockFetch;
    mockFetch.mockResolvedValue({ ok: true, json: async () => TRANSACTIONS });
  });

  it("renders the header and all tab triggers", () => {
    render(<FinancePage />);

    expect(screen.getByRole("heading", { name: /finance/i })).toBeInTheDocument();
    for (const tab of [
      "Overview",
      "Transactions",
      "Budgeting",
      "Invoices",
      "Subscriptions",
      "Accounting Review",
      "Accountant Portal",
      "Forecasting",
    ]) {
      expect(screen.getByRole("button", { name: new RegExp(tab, "i") })).toBeInTheDocument();
    }
    expect(screen.getByTestId("finance-overview")).toBeInTheDocument();
  });

  it("switches between tabs to render each panel", () => {
    render(<FinancePage />);

    fireEvent.click(screen.getByRole("button", { name: /transactions/i }));
    expect(screen.getByTestId("transactions-list")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /budgeting/i }));
    expect(screen.getByTestId("budget-planner")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /invoices/i }));
    expect(screen.getByTestId("invoice-manager")).toBeInTheDocument();

    // Subscriptions tab is reachable (was missing a TabsTrigger)
    fireEvent.click(screen.getByRole("button", { name: /subscriptions/i }));
    expect(screen.getByTestId("subscription-tracker")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /accounting review/i }));
    expect(screen.getByTestId("categorization-review")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /accountant portal/i }));
    expect(screen.getByTestId("accountant-portal")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /forecasting/i }));
    expect(screen.getByTestId("forecasting-sandbox")).toBeInTheDocument();
  });

  it("creates a transaction via the dialog and dispatches the refresh event", async () => {
    const dispatchSpy = jest.spyOn(window, "dispatchEvent");
    render(<FinancePage />);

    fireEvent.click(screen.getByRole("button", { name: /new transaction/i }));

    await waitFor(() => {
      expect(screen.getByText("Add Transaction")).toBeInTheDocument();
    });

    fireEvent.change(document.getElementById("tx-desc")!, {
      target: { value: "Office supplies" },
    });
    fireEvent.change(document.getElementById("tx-merchant")!, {
      target: { value: "Staples" },
    });
    fireEvent.change(document.getElementById("tx-amount")!, {
      target: { value: "45.50" },
    });
    fireEvent.change(document.getElementById("tx-date")!, {
      target: { value: "2026-08-05" },
    });

    fireEvent.click(screen.getByRole("button", { name: /save transaction/i }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/accounting/transactions",
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({
            Authorization: "Bearer tok-123",
          }),
        })
      );
    });

    const postCall = mockFetch.mock.calls.find(
      (c: any[]) => c[1]?.method === "POST"
    );
    const body = JSON.parse((postCall as any[])[1].body);
    expect(body.description).toBe("Office supplies");
    expect(body.merchant).toBe("Staples");
    expect(body.amount).toBe(45.5);
    expect(body.source).toBe("manual");

    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Transaction Created" })
    );
    expect(
      dispatchSpy.mock.calls.some((c) => (c[0] as Event).type === "transactionCreated")
    ).toBe(true);
  });

  it("rejects an invalid (non-numeric) amount without posting", async () => {
    render(<FinancePage />);

    fireEvent.click(screen.getByRole("button", { name: /new transaction/i }));
    await waitFor(() => {
      expect(screen.getByText("Add Transaction")).toBeInTheDocument();
    });

    fireEvent.change(document.getElementById("tx-desc")!, {
      target: { value: "Mystery charge" },
    });
    fireEvent.change(document.getElementById("tx-amount")!, {
      target: { value: "abc" },
    });
    fireEvent.submit(document.querySelector("form")!);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Invalid amount" })
      );
    });
    expect(
      mockFetch.mock.calls.filter((c: any[]) => c[1]?.method === "POST")
    ).toHaveLength(0);
  });

  it("surfaces the backend error detail when the create fails", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ detail: "Amount exceeds limit" }),
    });
    render(<FinancePage />);

    fireEvent.click(screen.getByRole("button", { name: /new transaction/i }));
    await waitFor(() => {
      expect(screen.getByText("Add Transaction")).toBeInTheDocument();
    });

    fireEvent.change(document.getElementById("tx-desc")!, {
      target: { value: "Big order" },
    });
    fireEvent.change(document.getElementById("tx-amount")!, {
      target: { value: "99999" },
    });
    fireEvent.click(screen.getByRole("button", { name: /save transaction/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Error",
          description: "Amount exceeds limit",
        })
      );
    });
  });

  it("exports transactions as a CSV download", async () => {
    const clickSpy = jest.fn();
    jest.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(clickSpy);
    render(<FinancePage />);

    fireEvent.click(screen.getByRole("button", { name: /export/i }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/accounting/transactions",
        expect.objectContaining({
          headers: expect.objectContaining({ Authorization: "Bearer tok-123" }),
        })
      );
    });

    expect(clickSpy).toHaveBeenCalled();
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Export Successful" })
    );
  });

  it("refuses to export when there are no transactions", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: async () => ({ data: { transactions: [] as any[] } }),
    });
    render(<FinancePage />);

    fireEvent.click(screen.getByRole("button", { name: /export/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Export Failed" })
      );
    });
  });

  it("shows an export failure toast when the fetch throws", async () => {
    mockFetch.mockRejectedValue(new Error("network down"));
    render(<FinancePage />);

    fireEvent.click(screen.getByRole("button", { name: /export/i }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Export Failed" })
      );
    });
  });
});
