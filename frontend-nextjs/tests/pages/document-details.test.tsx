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
const mockRouterPush = jest.fn();

jest.mock("next/router", () => ({
  useRouter: () => ({
    push: mockRouterPush,
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

const mockToastSuccess = jest.fn();
const mockToastError = jest.fn();
jest.mock("sonner", () => ({
  toast: {
    success: (...args: any[]) => mockToastSuccess(...args),
    error: (...args: any[]) => mockToastError(...args),
  },
}));

const mockGet = jest.fn();
const mockDelete = jest.fn();
jest.mock("../../lib/api", () => ({
  __esModule: true,
  default: {
    get: (...args: any[]) => mockGet(...args),
    delete: (...args: any[]) => mockDelete(...args),
  },
  apiClient: {
    delete: (...args: any[]) => mockDelete(...args),
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

// ---------------------------------------------------------------------------
// Document deletion (verified receipt / truthful partial state)
// ---------------------------------------------------------------------------

const verifiedDelete = (id: string) => ({
  status: 200,
  data: {
    success: true,
    data: {
      doc_id: id,
      deleted: true,
      complete: true,
      verification: { status: "verified", effect: "committed" },
    },
    metadata: {
      target_id: id,
      operation_id: `document:delete:${id}`,
      audit_id: `document:delete:${id}`,
      verification: { status: "verified", effect: "committed" },
    },
  },
});

const deleteFailure = (status: number, detail: any) => ({
  response: { status, data: { detail } },
});

describe("DocumentDetailsPage deletion", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGet.mockResolvedValue({ data: { success: true, data: DOC } });
  });

  test("a delete asks for confirmation and a cancelled confirmation does nothing", async () => {
    const confirm = jest.spyOn(window, "confirm").mockReturnValue(false);
    render(<DocumentDetailsPage />);
    await screen.findByText("Q2 Financial Report");

    fireEvent.click(screen.getByTestId("document-delete"));

    expect(confirm).toHaveBeenCalledWith(
      expect.stringContaining('Delete "Q2 Financial Report"'),
    );
    expect(mockDelete).not.toHaveBeenCalled();
    expect(mockRouterPush).not.toHaveBeenCalled();
  });

  test("a verified delete confirms success and returns to the library", async () => {
    mockDelete.mockResolvedValue(verifiedDelete("d1"));
    jest.spyOn(window, "confirm").mockReturnValue(true);

    render(<DocumentDetailsPage />);
    await screen.findByText("Q2 Financial Report");
    fireEvent.click(screen.getByTestId("document-delete"));

    await waitFor(() => expect(mockRouterPush).toHaveBeenCalledWith("/documents"));
    expect(mockDelete).toHaveBeenCalledTimes(1);
    expect(mockDelete.mock.calls[0][0]).toBe("/api/documents/d1");
    expect(mockToastSuccess).toHaveBeenCalledWith("Document deleted.");
  });

  test("a partially verified delete stays on the page, discloses it, and does not retry", async () => {
    mockDelete.mockRejectedValue(
      deleteFailure(503, {
        error: {
          code: "DOCUMENT_DELETE_UNVERIFIED",
          message: "sensitive server detail",
        },
        verification: {
          status: "committed_unverified",
          effect: "partial",
          replay: "do_not_repeat",
        },
      }),
    );
    jest.spyOn(window, "confirm").mockReturnValue(true);

    render(<DocumentDetailsPage />);
    await screen.findByText("Q2 Financial Report");
    fireEvent.click(screen.getByTestId("document-delete"));

    const notice = await screen.findByTestId("document-delete-notice");
    expect(notice).toHaveTextContent(/only partly verified/i);
    expect(notice).toHaveTextContent(/do not repeat/i);
    expect(notice).not.toHaveTextContent(/sensitive/i);
    expect(mockDelete).toHaveBeenCalledTimes(1);
    expect(mockRouterPush).not.toHaveBeenCalled();
    expect(mockToastSuccess).not.toHaveBeenCalled();
    expect(mockToastError).toHaveBeenCalledWith("Deletion not confirmed");
  });

  test("an unknown delete outcome is disclosed without leaving or retrying", async () => {
    mockDelete.mockRejectedValue(
      deleteFailure(503, {
        error: { code: "DOCUMENT_EFFECT_UNKNOWN", message: "sensitive" },
        verification: {
          status: "unavailable",
          effect: "unknown",
          replay: "do_not_repeat",
        },
      }),
    );
    jest.spyOn(window, "confirm").mockReturnValue(true);

    render(<DocumentDetailsPage />);
    await screen.findByText("Q2 Financial Report");
    fireEvent.click(screen.getByTestId("document-delete"));

    const notice = await screen.findByTestId("document-delete-notice");
    expect(notice).toHaveTextContent(/outcome is unknown/i);
    expect(mockDelete).toHaveBeenCalledTimes(1);
    expect(mockRouterPush).not.toHaveBeenCalled();
    expect(mockToastSuccess).not.toHaveBeenCalled();
  });

  test("a not-found delete is disclosed and does not navigate as if deleted", async () => {
    mockDelete.mockRejectedValue(
      deleteFailure(404, { error: { code: "NOT_FOUND", message: "missing" } }),
    );
    jest.spyOn(window, "confirm").mockReturnValue(true);

    render(<DocumentDetailsPage />);
    await screen.findByText("Q2 Financial Report");
    fireEvent.click(screen.getByTestId("document-delete"));

    const notice = await screen.findByTestId("document-delete-notice");
    expect(notice).toHaveTextContent(/not found/i);
    expect(mockRouterPush).not.toHaveBeenCalled();
    expect(mockToastSuccess).not.toHaveBeenCalled();
    expect(mockDelete).toHaveBeenCalledTimes(1);
  });

  test("an already-removed receipt reports that truthfully and returns to the library", async () => {
    mockDelete.mockResolvedValue({
      status: 200,
      data: {
        success: true,
        data: {
          doc_id: "d1",
          deleted: true,
          complete: true,
          verification: { status: "already_applied", effect: "committed" },
        },
        metadata: {
          target_id: "d1",
          verification: { status: "already_applied", effect: "committed" },
        },
      },
    });
    jest.spyOn(window, "confirm").mockReturnValue(true);

    render(<DocumentDetailsPage />);
    await screen.findByText("Q2 Financial Report");
    fireEvent.click(screen.getByTestId("document-delete"));

    await waitFor(() => expect(mockRouterPush).toHaveBeenCalledWith("/documents"));
    expect(mockToastSuccess).toHaveBeenCalledWith("Document was already deleted.");
  });
});
