/**
 * FinancePage tests (pages/finance/index.tsx, was 0% coverage)
 *
 * Covers: page header + tab layout, CSV export (success / empty / failure),
 * and the create-transaction dialog (validation, success, server error,
 * network error, custom event dispatch).
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import FinancePage from "@/pages/finance";

const mockToast = jest.fn();

jest.mock("../../components/ui/use-toast", () => ({
  useToast: () => ({ toast: mockToast }),
}));

jest.mock("../../components/finance/FinanceOverview", () => ({
  __esModule: true,
  default: () => <div data-testid="finance-overview">Overview</div>,
}));
jest.mock("../../components/finance/TransactionsList", () => ({
  __esModule: true,
  default: () => <div data-testid="transactions-list">Transactions</div>,
}));
jest.mock("../../components/finance/BudgetPlanner", () => ({
  __esModule: true,
  default: () => <div data-testid="budget-planner">Budget</div>,
}));
jest.mock("../../components/finance/InvoiceManager", () => ({
  __esModule: true,
  default: () => <div data-testid="invoice-manager">Invoices</div>,
}));
jest.mock("../../components/finance/SubscriptionTracker", () => ({
  __esModule: true,
  default: () => <div data-testid="subscription-tracker">Subscriptions</div>,
}));
jest.mock("../../components/finance/CategorizationReview", () => ({
  __esModule: true,
  default: () => <div data-testid="categorization-review">Review</div>,
}));
jest.mock("../../components/finance/AccountantPortal", () => ({
  __esModule: true,
  default: () => <div data-testid="accountant-portal">Portal</div>,
}));
jest.mock("../../components/finance/ForecastingSandbox", () => ({
  __esModule: true,
  default: () => <div data-testid="forecasting-sandbox">Forecasting</div>,
}));

const okJson = (body: any) => ({ ok: true, status: 200, json: async () => body });

describe("FinancePage", () => {
  let mockFetch: jest.Mock;
  let dispatchSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    mockFetch = jest.fn();
    global.fetch = mockFetch;
    dispatchSpy = jest.spyOn(window, "dispatchEvent").mockImplementation(() => true);
  });

  afterEach(() => {
    dispatchSpy.mockRestore();
  });

  test("renders header and all tab triggers", () => {
    render(<FinancePage />);
    expect(screen.getByText("Finance")).toBeInTheDocument();
    expect(screen.getAllByText("Overview").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /Transactions/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Budgeting/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Invoices/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Subscriptions/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Accounting Review/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Accountant Portal/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Forecasting/ })).toBeInTheDocument();
  });

  test("renders child panels when switching tabs", () => {
    render(<FinancePage />);
    expect(screen.getByTestId("finance-overview")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Transactions/ }));
    expect(screen.getByTestId("transactions-list")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Budgeting/ }));
    expect(screen.getByTestId("budget-planner")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Invoices/ }));
    expect(screen.getByTestId("invoice-manager")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Subscriptions/ }));
    expect(screen.getByTestId("subscription-tracker")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Accounting Review/ }));
    expect(screen.getByTestId("categorization-review")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Accountant Portal/ }));
    expect(screen.getByTestId("accountant-portal")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Forecasting/ }));
    expect(screen.getByTestId("forecasting-sandbox")).toBeInTheDocument();
  });

  test("export CSV downloads transactions", async () => {
    const clickSpy = jest.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    mockFetch.mockResolvedValue(
      okJson({
        data: {
          transactions: [
            {
              id: "tx1",
              date: "2026-08-01",
              description: 'He said "hi"',
              merchant: "Staples",
              amount: -50,
              suggested_category: "office",
              confidence: 0.9,
              reasoning: "receipt",
            },
          ],
        },
      })
    );

    render(<FinancePage />);
    fireEvent.click(screen.getByRole("button", { name: /Export/ }));

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Export Successful" })
      )
    );
    expect(mockFetch).toHaveBeenCalledWith("/api/accounting/transactions", expect.anything());
    clickSpy.mockRestore();
  });

  test("export CSV shows error when no transactions", async () => {
    mockFetch.mockResolvedValue(okJson({ data: { transactions: [] } }));
    render(<FinancePage />);
    fireEvent.click(screen.getByRole("button", { name: /Export/ }));

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Export Failed", description: "No transactions to export." })
      )
    );
  });

  test("export CSV shows error when fetch fails", async () => {
    mockFetch.mockRejectedValue(new Error("offline"));
    render(<FinancePage />);
    fireEvent.click(screen.getByRole("button", { name: /Export/ }));

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Export Failed", description: "Could not export data." })
      )
    );
  });

  test("export CSV surfaces failed response status", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 500, json: async () => ({}) });
    render(<FinancePage />);
    fireEvent.click(screen.getByRole("button", { name: /Export/ }));

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Export Failed" })
      )
    );
  });

  const openCreateDialog = () => {
    fireEvent.click(screen.getByRole("button", { name: /New Transaction/ }));
  };

  const fillAndSubmit = (amount: string) => {
    fireEvent.change(screen.getByLabelText(/Description/), { target: { value: "Office Supplies" } });
    fireEvent.change(screen.getByLabelText(/Merchant/), { target: { value: "Staples" } });
    fireEvent.change(screen.getByLabelText(/Amount/), { target: { value: amount } });
    fireEvent.change(screen.getByLabelText(/Date/), { target: { value: "2026-08-01" } });
    const form = screen.getByRole("button", { name: /Save Transaction/ }).closest("form");
    fireEvent.submit(form!);
  };

  test("create transaction shows submitting state while in flight", async () => {
    let resolveFetch: (v: any) => void;
    mockFetch.mockReturnValue(
      new Promise((resolve) => {
        resolveFetch = resolve;
      })
    );
    render(<FinancePage />);
    openCreateDialog();
    fillAndSubmit("100");
    expect(screen.getByRole("button", { name: /Save Transaction/ })).toBeDisabled();

    resolveFetch!({ ok: true, status: 200, json: async () => ({}) });
    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Transaction Created" })
      )
    );
  });

  test("create transaction rejects invalid amount", async () => {
    render(<FinancePage />);
    openCreateDialog();
    // jsdom coerces non-numeric input on type=number to "" → parseFloat("") = NaN
    fillAndSubmit("");

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Invalid amount" })
      )
    );
    expect(mockFetch).not.toHaveBeenCalled();
  });

  test("create transaction succeeds and dispatches refresh event", async () => {
    mockFetch.mockResolvedValue(okJson({ success: true }));
    render(<FinancePage />);
    openCreateDialog();
    fillAndSubmit("1500.00");

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Transaction Created" })
      )
    );
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/accounting/transactions",
      expect.objectContaining({ method: "POST" })
    );
    expect(dispatchSpy).toHaveBeenCalledWith(expect.objectContaining({ type: "transactionCreated" }));
    expect(screen.queryByRole("button", { name: /Save Transaction/ })).not.toBeInTheDocument();
  });

  test("create transaction surfaces server error detail", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ detail: "Amount exceeds limit" }),
    });
    render(<FinancePage />);
    openCreateDialog();
    fillAndSubmit("10");

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Error", description: "Amount exceeds limit" })
      )
    );
  });

  test("create transaction falls back to status when error body is not JSON", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 502,
      json: async () => {
        throw new Error("bad json");
      },
    });
    render(<FinancePage />);
    openCreateDialog();
    fillAndSubmit("10");

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Error", description: expect.stringContaining("502") })
      )
    );
  });

  test("create transaction falls back to status when no detail", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 500, json: async () => ({} as any) });
    render(<FinancePage />);
    openCreateDialog();
    fillAndSubmit("10");

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Error", description: expect.stringContaining("500") })
      )
    );
  });

  test("create transaction shows network error toast", async () => {
    mockFetch.mockRejectedValue(new Error("offline"));
    render(<FinancePage />);
    openCreateDialog();
    fillAndSubmit("10");

    await waitFor(() =>
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Error", description: "offline" })
      )
    );
  });
});
