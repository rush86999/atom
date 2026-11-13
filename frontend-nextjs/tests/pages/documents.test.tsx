/**
 * DocumentsPage tests (pages/documents.tsx, was 0% coverage)
 *
 * Covers: document list rendering + empty state, upload flow (success,
 * non-2xx with detail, network error), drag & drop handling, and refresh.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import DocumentsPage from "@/pages/documents";
import { ProductProfileProvider } from "@/lib/product-profile";

const originalFetch = global.fetch;

const mockRouterPush = jest.fn();

jest.mock("next/router", () => ({
  useRouter: () => ({
    push: mockRouterPush,
    replace: jest.fn(),
    prefetch: jest.fn(),
    back: jest.fn(),
    reload: jest.fn(),
    pathname: "/documents",
    query: {},
    asPath: "/documents",
    events: { on: jest.fn(), off: jest.fn(), emit: jest.fn() },
  }),
}));

const mockToastError = jest.fn();
const mockToastSuccess = jest.fn();
jest.mock("sonner", () => ({
  toast: {
    error: (...args: any[]) => mockToastError(...args),
    success: (...args: any[]) => mockToastSuccess(...args),
  },
}));

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockDelete = jest.fn();
jest.mock("../../lib/api", () => ({
  __esModule: true,
  default: {
    get: (...args: any[]) => mockGet(...args),
    post: (...args: any[]) => mockPost(...args),
    delete: (...args: any[]) => mockDelete(...args),
  },
  apiClient: {
    delete: (...args: any[]) => mockDelete(...args),
  },
}));

const apiImpl = (base: jest.Mock, responder: (url: string) => any) => {
  base.mockImplementation(async (url: string, opts?: any) => {
    const resp = responder(url);
    if (opts?.validateStatus && !opts.validateStatus(resp.status)) {
      const err: any = new Error(`Request failed with status code ${resp.status}`);
      err.response = { data: resp.data, status: resp.status };
      throw err;
    }
    return resp;
  });
};

const DOCS = [
  { id: "d1", title: "Onboarding Guide", text_preview: "How to onboard...", created_at: "2026-07-15T10:00:00Z" },
  { id: "d2", title: "Pricing Deck", text_preview: "Tiers and plans...", created_at: "2026-08-01T10:00:00Z" },
];

const makeFile = (name: string) => new File(["content"], name, { type: "text/plain" });

const uploadInput = (container: HTMLElement) =>
  container.querySelector("#file-upload") as HTMLInputElement;

const dropZone = (container: HTMLElement) =>
  container.querySelector('div[class*="border-dashed"]') as HTMLElement;

describe("DocumentsPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    apiImpl(mockGet, () => ({ status: 200, data: { success: true, data: DOCS } }));
    apiImpl(mockPost, () => ({ status: 200, data: { success: true } }));
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  test("renders page header and upload area", async () => {
    render(<DocumentsPage />);
    expect(screen.getByText("Knowledge Base")).toBeInTheDocument();
    expect(screen.getByText("Upload Document")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Onboarding Guide")).toBeInTheDocument());
    expect(mockGet).toHaveBeenCalledWith("/api/documents", expect.anything());
  });

  test("renders empty state when no documents", async () => {
    apiImpl(mockGet, () => ({ status: 200, data: { success: true, data: [] } }));
    render(<DocumentsPage />);
    await waitFor(() =>
      expect(screen.getByText("No documents uploaded yet.")).toBeInTheDocument()
    );
  });

  test("clicking a document navigates to its detail page", async () => {
    render(<DocumentsPage />);
    await waitFor(() => expect(screen.getByText("Onboarding Guide")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Onboarding Guide"));
    expect(mockRouterPush).toHaveBeenCalledWith("/documents/d1");
  });

  test("fetch failure logs error without crashing", async () => {
    mockGet.mockRejectedValue(new Error("network"));
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<DocumentsPage />);
    await waitFor(() => expect(consoleSpy).toHaveBeenCalled());
    consoleSpy.mockRestore();
  });

  test("deferred search profile shows unavailable copy and a supported next action", async () => {
    render(<DocumentsPage />);
    await waitFor(() => expect(screen.getByText("Onboarding Guide")).toBeInTheDocument());

    expect(screen.getByText("Search is not part of this release.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Go to Search Page/ })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Ask in Chat/ }));
    expect(mockRouterPush).toHaveBeenCalledWith("/chat");
  });

  test("supported search profile keeps the search card and navigates", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        profile: "full",
        version: "test",
        statement: "Full test profile",
        capabilities: {
          documents: { label: "Data", enabled: true },
          search: { label: "Search", enabled: true },
        },
        enabled_capabilities: ["documents", "search"],
        deferred_capabilities: [],
        routes: { "/documents": "documents", "/search": "search" },
      }),
    }) as any;

    render(
      <ProductProfileProvider>
        <DocumentsPage />
      </ProductProfileProvider>
    );
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Go to Search Page/ })).toBeInTheDocument()
    );

    fireEvent.click(screen.getByRole("button", { name: /Go to Search Page/ }));
    expect(mockRouterPush).toHaveBeenCalledWith("/search");
  });

  test("clicking the drop zone triggers the hidden file input", async () => {
    render(<DocumentsPage />);
    await waitFor(() => expect(screen.getByText("Onboarding Guide")).toBeInTheDocument());
    const input = uploadInput(document.body);
    const clickSpy = jest.spyOn(input, "click").mockImplementation(() => {});
    fireEvent.click(dropZone(document.body));
    expect(clickSpy).toHaveBeenCalled();
    clickSpy.mockRestore();
  });

  test("refresh button refetches documents", async () => {
    render(<DocumentsPage />);
    await waitFor(() => expect(screen.getByText("Onboarding Guide")).toBeInTheDocument());
    const before = mockGet.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: /Refresh/ }));
    await waitFor(() => expect(mockGet.mock.calls.length).toBeGreaterThan(before));
  });

  test("uploading a file succeeds and refreshes the list", async () => {
    render(<DocumentsPage />);
    await waitFor(() => expect(screen.getByText("Onboarding Guide")).toBeInTheDocument());
    const before = mockGet.mock.calls.length;

    const input = uploadInput(document.body);
    fireEvent.change(input, { target: { files: [makeFile("q4-report.txt")] } });

    await waitFor(() =>
      expect(screen.getByText(/Successfully uploaded "q4-report.txt"/)).toBeInTheDocument()
    );
    expect(mockToastSuccess).toHaveBeenCalledWith("Document uploaded successfully");
    expect(mockGet.mock.calls.length).toBeGreaterThan(before);
    expect(mockPost).toHaveBeenCalledWith("/api/documents/upload", expect.any(FormData), expect.anything());
  });

  test("upload failure surfaces backend detail and error toast", async () => {
    apiImpl(mockPost, () => ({ status: 422, data: { detail: "Unsupported file type" } }));
    render(<DocumentsPage />);
    await waitFor(() => expect(screen.getByText("Onboarding Guide")).toBeInTheDocument());

    const input = uploadInput(document.body);
    fireEvent.change(input, { target: { files: [makeFile("x.exe")] } });

    await waitFor(() =>
      expect(screen.getByText("Unsupported file type")).toBeInTheDocument()
    );
    expect(mockToastError).toHaveBeenCalledWith("Upload failed");
  });

  test("upload network error shows generic message", async () => {
    mockPost.mockRejectedValue({ response: { data: { detail: "server exploded" } } });
    render(<DocumentsPage />);
    await waitFor(() => expect(screen.getByText("Onboarding Guide")).toBeInTheDocument());

    const input = uploadInput(document.body);
    fireEvent.change(input, { target: { files: [makeFile("x.txt")] } });

    await waitFor(() => expect(screen.getByText("server exploded")).toBeInTheDocument());
    expect(mockToastError).toHaveBeenCalledWith("Upload failed");
  });

  test("upload network error without response detail shows fallback message", async () => {
    mockPost.mockRejectedValue(new Error("offline"));
    render(<DocumentsPage />);
    await waitFor(() => expect(screen.getByText("Onboarding Guide")).toBeInTheDocument());

    const input = uploadInput(document.body);
    fireEvent.change(input, { target: { files: [makeFile("x.txt")] } });

    await waitFor(() =>
      expect(screen.getByText("Failed to upload document.")).toBeInTheDocument()
    );
  });

  test("drag enter activates the drop zone", async () => {
    render(<DocumentsPage />);
    await waitFor(() => expect(screen.getByText("Onboarding Guide")).toBeInTheDocument());
    const zone = dropZone(document.body);

    fireEvent.dragEnter(zone, {});
    expect(zone.className).toContain("border-primary");
  });

  test("drag leave deactivates the drop zone", async () => {
    render(<DocumentsPage />);
    await waitFor(() => expect(screen.getByText("Onboarding Guide")).toBeInTheDocument());
    const zone = dropZone(document.body);

    fireEvent.dragEnter(zone, {});
    expect(zone.className).toContain("bg-primary/5");
    fireEvent.dragLeave(zone, {});
    expect(zone.className).not.toContain("bg-primary/5");
  });

  test("dropping a file uploads it", async () => {
    render(<DocumentsPage />);
    await waitFor(() => expect(screen.getByText("Onboarding Guide")).toBeInTheDocument());

    const zone = dropZone(document.body);
    fireEvent.drop(zone, { dataTransfer: { files: [makeFile("drop.txt")] } });

    await waitFor(() =>
      expect(screen.getByText(/Successfully uploaded "drop.txt"/)).toBeInTheDocument()
    );
  });

  test("drop without files does nothing", async () => {
    render(<DocumentsPage />);
    await waitFor(() => expect(screen.getByText("Onboarding Guide")).toBeInTheDocument());

    const zone = dropZone(document.body);
    fireEvent.drop(zone, { dataTransfer: { files: [] } });
    expect(mockPost).not.toHaveBeenCalled();
  });

  test("uploading state shows spinner and disables interactions", async () => {
    let resolvePost: (v: any) => void;
    mockPost.mockReturnValue(
      new Promise((resolve) => {
        resolvePost = resolve;
      })
    );
    render(<DocumentsPage />);
    await waitFor(() => expect(screen.getByText("Onboarding Guide")).toBeInTheDocument());

    const input = uploadInput(document.body);
    fireEvent.change(input, { target: { files: [makeFile("slow.txt")] } });

    expect(screen.getByText("Uploading...")).toBeInTheDocument();
    resolvePost!({ status: 200, data: { success: true } });
    await waitFor(() =>
      expect(screen.getByText("Click to upload or drag and drop")).toBeInTheDocument()
    );
  });
});

// ---------------------------------------------------------------------------
// Pagination / invalidation / stale-response controls
// ---------------------------------------------------------------------------

const pagedDoc = (id: string, index: number) => ({
  id,
  title: id,
  text_preview: `${id} preview`,
  created_at: `2026-01-${String(index + 1).padStart(2, "0")}T10:00:00Z`,
});

const pageResponse = (
  ids: string[],
  offset: number,
  total: number,
  hasMore: boolean,
) => ({
  status: 200,
  data: {
    success: true,
    data: ids.map((id, i) => pagedDoc(id, offset + i)),
    metadata: {
      total,
      count: ids.length,
      limit: 100,
      offset,
      has_more: hasMore,
      ...(hasMore ? { next_offset: offset + ids.length } : {}),
      ...(offset > 0 ? { previous_offset: Math.max(0, offset - 100) } : {}),
    },
  },
});

const mockPagedGet = (
  first: string[] = ["newest", "older"],
  second: string[] = ["oldest"],
  total = 130,
) => {
  mockGet.mockImplementation(async (_url: string, opts?: any) => {
    const offset = opts?.params?.offset ?? 0;
    return offset === 0
      ? pageResponse(first, 0, total, total > first.length)
      : pageResponse(second, 100, total, false);
  });
};

describe("DocumentsPage pagination", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    apiImpl(mockPost, () => ({ status: 200, data: { success: true } }));
  });

  test("next and previous reach older and newest documents with range/page controls", async () => {
    mockPagedGet();
    render(<DocumentsPage />);

    await screen.findByText("newest");
    expect(screen.getByTestId("documents-range")).toHaveTextContent("Showing 1–2 of 130");
    expect(screen.getByTestId("documents-page")).toHaveTextContent("Page 1 of 2");
    expect(screen.getByTestId("documents-previous")).toBeDisabled();
    expect(screen.getByTestId("documents-next")).toBeEnabled();

    fireEvent.click(screen.getByTestId("documents-next"));
    await screen.findByText("oldest");
    expect(mockGet).toHaveBeenLastCalledWith(
      "/api/documents",
      expect.objectContaining({ params: { limit: 100, offset: 100 } }),
    );
    expect(screen.getByTestId("documents-range")).toHaveTextContent("Showing 101–101 of 130");
    expect(screen.getByTestId("documents-page")).toHaveTextContent("Page 2 of 2");
    expect(screen.getByTestId("documents-next")).toBeDisabled();
    expect(screen.getByTestId("documents-previous")).toBeEnabled();

    fireEvent.click(screen.getByTestId("documents-previous"));
    await screen.findByText("newest");
    expect(mockGet).toHaveBeenLastCalledWith(
      "/api/documents",
      expect.objectContaining({ params: { limit: 100, offset: 0 } }),
    );
  });

  test("upload resets a later page to the first page", async () => {
    mockPagedGet();
    render(<DocumentsPage />);
    await screen.findByText("newest");
    fireEvent.click(screen.getByTestId("documents-next"));
    await screen.findByText("oldest");

    mockGet.mockImplementation(async (_url: string, opts?: any) => {
      const offset = opts?.params?.offset ?? 0;
      if (offset === 0) {
        return pageResponse(["uploaded", "newest"], 0, 131, true);
      }
      return pageResponse(["oldest"], 100, 131, false);
    });

    const input = uploadInput(document.body);
    fireEvent.change(input, { target: { files: [makeFile("fresh.txt")] } });
    await screen.findByText("uploaded");
    expect(mockGet).toHaveBeenLastCalledWith(
      "/api/documents",
      expect.objectContaining({ params: { limit: 100, offset: 0 } }),
    );
    expect(screen.getByTestId("documents-page")).toHaveTextContent("Page 1 of 2");
  });

  test("deleting elsewhere empties a later page and falls back to the previous page", async () => {
    mockPagedGet();
    render(<DocumentsPage />);
    await screen.findByText("newest");
    fireEvent.click(screen.getByTestId("documents-next"));
    await screen.findByText("oldest");

    mockGet.mockImplementation(async (_url: string, opts?: any) => {
      const offset = opts?.params?.offset ?? 0;
      if (offset === 0) {
        return pageResponse(["remaining"], 0, 100, false);
      }
      return pageResponse([], 100, 100, false);
    });

    fireEvent.click(screen.getByRole("button", { name: /Refresh/ }));
    await screen.findByText("remaining");
    expect(mockGet).toHaveBeenLastCalledWith(
      "/api/documents",
      expect.objectContaining({ params: { limit: 100, offset: 0 } }),
    );
    expect(screen.getByTestId("documents-page")).toHaveTextContent("Page 1 of 1");
    expect(screen.getByTestId("documents-next")).toBeDisabled();
  });

  test("a stale later-page response cannot overwrite a fresh upload refresh", async () => {
    let resolveStale: ((value: any) => void) | undefined;
    const stalePromise = new Promise((resolve) => {
      resolveStale = resolve;
    });
    let firstPageCalls = 0;
    mockGet.mockImplementation(async (_url: string, opts?: any) => {
      const offset = opts?.params?.offset ?? 0;
      if (offset === 100) {
        return stalePromise as any;
      }
      firstPageCalls += 1;
      return firstPageCalls === 1
        ? pageResponse(["newest"], 0, 130, true)
        : pageResponse(["fresh-upload"], 0, 131, true);
    });

    render(<DocumentsPage />);
    await screen.findByText("newest");
    fireEvent.click(screen.getByTestId("documents-next"));

    const input = uploadInput(document.body);
    fireEvent.change(input, { target: { files: [makeFile("race.txt")] } });
    await screen.findByText("fresh-upload");

    resolveStale?.(pageResponse(["stale-page"], 100, 130, false));
    await waitFor(() =>
      expect(screen.queryByText("stale-page")).not.toBeInTheDocument(),
    );
    expect(screen.getByText("fresh-upload")).toBeInTheDocument();
  });

  test("a listing error is shown with retry instead of a false empty library", async () => {
    mockGet.mockResolvedValue({
      status: 503,
      data: {
        detail: {
          error: "DOCUMENT_LISTING_UNAVAILABLE",
          message: "Document listing is temporarily unavailable. Retry shortly.",
        },
      },
    });
    render(<DocumentsPage />);
    await screen.findByTestId("documents-error");
    expect(screen.getByText(/temporarily unavailable/i)).toBeInTheDocument();
    expect(screen.queryByText("No documents uploaded yet.")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Retry/ })).toBeInTheDocument();
  });

  test("empty libraries do not render pagination controls", async () => {
    mockGet.mockResolvedValue(pageResponse([], 0, 0, false));
    render(<DocumentsPage />);
    await screen.findByText("No documents uploaded yet.");
    expect(screen.queryByTestId("documents-pagination")).not.toBeInTheDocument();
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

describe("DocumentsPage deletion", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGet.mockImplementation(async () => ({
      status: 200,
      data: { success: true, data: DOCS, metadata: { total: DOCS.length } },
    }));
  });

  test("a delete asks for confirmation and a cancelled confirmation does nothing", async () => {
    const confirm = jest.spyOn(window, "confirm").mockReturnValue(false);
    render(<DocumentsPage />);
    await screen.findByText("Onboarding Guide");

    fireEvent.click(screen.getByTestId("delete-document-d1"));

    expect(confirm).toHaveBeenCalledWith(
      expect.stringContaining('Delete "Onboarding Guide"'),
    );
    expect(mockDelete).not.toHaveBeenCalled();
    expect(screen.getByText("Onboarding Guide")).toBeInTheDocument();
    expect(screen.queryByTestId("documents-delete-notice")).not.toBeInTheDocument();
    // The card's own click (open the document) must not fire.
    expect(mockRouterPush).not.toHaveBeenCalled();
  });

  test("a verified delete removes the row, confirms success, and refreshes the page", async () => {
    let list = DOCS;
    mockGet.mockImplementation(async () => ({
      status: 200,
      data: { success: true, data: list, metadata: { total: list.length } },
    }));
    mockDelete.mockImplementation(async () => {
      list = [DOCS[1]];
      return verifiedDelete("d1");
    });
    jest.spyOn(window, "confirm").mockReturnValue(true);

    render(<DocumentsPage />);
    await screen.findByText("Onboarding Guide");
    const beforeGet = mockGet.mock.calls.length;

    fireEvent.click(screen.getByTestId("delete-document-d1"));

    await waitFor(() =>
      expect(screen.queryByText("Onboarding Guide")).not.toBeInTheDocument(),
    );
    expect(mockDelete).toHaveBeenCalledTimes(1);
    expect(mockDelete.mock.calls[0][0]).toBe("/api/documents/d1");
    expect(mockToastSuccess).toHaveBeenCalledWith("Document deleted.");
    expect(screen.getByTestId("documents-delete-notice")).toHaveTextContent(
      "Document deleted.",
    );
    expect(screen.getByText("Pricing Deck")).toBeInTheDocument();
    // The current page is re-read so shifted rows appear.
    await waitFor(() =>
      expect(mockGet.mock.calls.length).toBeGreaterThan(beforeGet),
    );
  });

  test("a partially verified delete keeps the row, discloses it, and does not retry", async () => {
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
        operation_id: "document:delete:partial",
      }),
    );
    jest.spyOn(window, "confirm").mockReturnValue(true);

    render(<DocumentsPage />);
    await screen.findByText("Onboarding Guide");
    const beforeGet = mockGet.mock.calls.length;

    fireEvent.click(screen.getByTestId("delete-document-d1"));

    const notice = await screen.findByTestId("documents-delete-notice");
    expect(notice).toHaveTextContent(/only partly verified/i);
    expect(notice).toHaveTextContent(/do not repeat/i);
    expect(notice).not.toHaveTextContent(/sensitive server detail/i);

    // Nothing is removed, the delete is not repeated, and the list is not
    // silently re-fetched as if the outcome were known.
    expect(screen.getByText("Onboarding Guide")).toBeInTheDocument();
    expect(mockDelete).toHaveBeenCalledTimes(1);
    expect(mockGet.mock.calls.length).toBe(beforeGet);
    expect(screen.getByTestId("delete-document-d1")).toBeDisabled();
    expect(mockToastSuccess).not.toHaveBeenCalled();
    expect(mockToastError).toHaveBeenCalledWith("Deletion not confirmed");
  });

  test("an unknown delete outcome keeps the row and tells the user to refresh", async () => {
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

    render(<DocumentsPage />);
    await screen.findByText("Onboarding Guide");
    fireEvent.click(screen.getByTestId("delete-document-d1"));

    const notice = await screen.findByTestId("documents-delete-notice");
    expect(notice).toHaveTextContent(/outcome is unknown/i);
    expect(notice).not.toHaveTextContent(/sensitive/i);
    expect(screen.getByText("Onboarding Guide")).toBeInTheDocument();
    expect(mockDelete).toHaveBeenCalledTimes(1);
    expect(mockToastSuccess).not.toHaveBeenCalled();
  });

  test("a stale row reported not found is dropped without claiming a deletion", async () => {
    mockDelete.mockRejectedValue(
      deleteFailure(404, { error: { code: "NOT_FOUND", message: "missing" } }),
    );
    jest.spyOn(window, "confirm").mockReturnValue(true);

    render(<DocumentsPage />);
    await screen.findByText("Onboarding Guide");
    fireEvent.click(screen.getByTestId("delete-document-d1"));

    const notice = await screen.findByTestId("documents-delete-notice");
    expect(notice).toHaveTextContent(/not found/i);
    await waitFor(() =>
      expect(screen.queryByText("Onboarding Guide")).not.toBeInTheDocument(),
    );
    expect(mockToastSuccess).not.toHaveBeenCalled();
    expect(mockDelete).toHaveBeenCalledTimes(1);
  });
});
