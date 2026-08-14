/**
 * DocumentDetailsPage tests (pages/documents/[docId].tsx, was 0% coverage)
 *
 * Covers: loading spinner, error + not-found states, document content
 * rendering, metadata display (author, source fallback, filtered keys,
 * object values), and back navigation.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import DocumentDetailsPage from "@/pages/documents/[docId]";

const mockRouterBack = jest.fn();

jest.mock("next/router", () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    prefetch: jest.fn(),
    back: mockRouterBack,
    reload: jest.fn(),
    pathname: "/documents/d1",
    query: { docId: "d1" },
    asPath: "/documents/d1",
    events: { on: jest.fn(), off: jest.fn(), emit: jest.fn() },
  }),
}));

const mockGet = jest.fn();
jest.mock("../../lib/api", () => ({
  __esModule: true,
  default: {
    get: (...args: any[]) => mockGet(...args),
  },
}));

const DOC = {
  id: "d1",
  title: "Q2 Financial Report",
  content: "Revenue grew 12% this quarter.",
  type: "pdf",
  metadata: {
    title: "Q2 Financial Report",
    source: "uploaded_by_admin",
    doc_id: "x",
    ingested_at: "2026-07-01",
    _internal: "hidden",
    author: "Ada Lovelace",
    department: "Finance",
    tags: ["q2", "finance"],
  },
  ingested_at: "2026-07-01T10:00:00Z",
};

describe("DocumentDetailsPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGet.mockResolvedValue({ data: { success: true, data: DOC } });
  });

  test("shows spinner while loading", () => {
    mockGet.mockReturnValue(new Promise(() => {}));
    render(<DocumentDetailsPage />);
    expect(document.querySelector('[class*="animate-spin"]')).toBeInTheDocument();
    expect(mockGet).toHaveBeenCalledWith("/api/documents/d1");
  });

  test("renders document title, type, date and content", async () => {
    render(<DocumentDetailsPage />);
    await waitFor(() =>
      expect(screen.getByText("Q2 Financial Report")).toBeInTheDocument()
    );
    expect(screen.getByText("Revenue grew 12% this quarter.")).toBeInTheDocument();
    expect(screen.getByText("pdf")).toBeInTheDocument();
  });

  test("renders metadata author and skips filtered keys", async () => {
    render(<DocumentDetailsPage />);
    await waitFor(() => expect(screen.getByText("Q2 Financial Report")).toBeInTheDocument());

    expect(screen.getAllByText("Ada Lovelace").length).toBeGreaterThan(0);
    expect(screen.getByText("uploaded_by_admin")).toBeInTheDocument();
    expect(screen.getByText("d1")).toBeInTheDocument();
    expect(screen.getByText("department")).toBeInTheDocument();
    expect(screen.getByText("tags")).toBeInTheDocument();
    expect(screen.queryByText("_internal")).not.toBeInTheDocument();
    expect(screen.queryByText("Doc Id")).not.toBeInTheDocument();
  });

  test("renders object metadata values as JSON", async () => {
    mockGet.mockResolvedValue({
      data: { success: true, data: { ...DOC, metadata: { department: "Finance", tags: ["a", "b"] } } },
    });
    render(<DocumentDetailsPage />);
    await waitFor(() => expect(screen.getByText("Q2 Financial Report")).toBeInTheDocument());
    expect(screen.getByText('["a","b"]')).toBeInTheDocument();
  });

  test("renders Unknown source when metadata.source missing", async () => {
    mockGet.mockResolvedValue({
      data: { success: true, data: { ...DOC, metadata: { author: "Ada" } } },
    });
    render(<DocumentDetailsPage />);
    await waitFor(() => expect(screen.getByText("Q2 Financial Report")).toBeInTheDocument());
    expect(screen.getByText("Unknown")).toBeInTheDocument();
  });

  test("shows error alert and back button when API returns failure", async () => {
    mockGet.mockResolvedValue({ data: { success: false, message: "Document was removed" } });
    render(<DocumentDetailsPage />);

    await waitFor(() => expect(screen.getByText("Document was removed")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /Go Back/ }));
    expect(mockRouterBack).toHaveBeenCalled();
  });

  test("shows error alert on fetch rejection", async () => {
    mockGet.mockRejectedValue({ response: { data: { message: "Forbidden" } } });
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<DocumentDetailsPage />);

    await waitFor(() => expect(screen.getByText("Forbidden")).toBeInTheDocument());
    consoleSpy.mockRestore();
  });

  test("falls back to generic message when rejection has no detail", async () => {
    mockGet.mockRejectedValue(new Error("network"));
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<DocumentDetailsPage />);

    await waitFor(() =>
      expect(screen.getByText("Failed to fetch document details")).toBeInTheDocument()
    );
    consoleSpy.mockRestore();
  });

  test("shows not found state when data missing", async () => {
    mockGet.mockResolvedValue({ data: { success: true, data: null } });
    render(<DocumentDetailsPage />);

    await waitFor(() => expect(screen.getByText("Document not found")).toBeInTheDocument());
  });

  test("back button in header navigates", async () => {
    render(<DocumentDetailsPage />);
    await waitFor(() => expect(screen.getByText("Q2 Financial Report")).toBeInTheDocument());
    const backButtons = screen.getAllByRole("button", { name: /Go back/i });
    fireEvent.click(backButtons[0]);
    expect(mockRouterBack).toHaveBeenCalled();
  });
});
