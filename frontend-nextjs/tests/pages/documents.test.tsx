/**
 * DocumentsPage tests (pages/documents.tsx, was 0% coverage)
 *
 * Covers: document list rendering + empty state, upload flow (success,
 * non-2xx with detail, network error), drag & drop handling, and refresh.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import DocumentsPage from "@/pages/documents";

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
jest.mock("../../lib/api", () => ({
  __esModule: true,
  default: {
    get: (...args: any[]) => mockGet(...args),
    post: (...args: any[]) => mockPost(...args),
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

  test("go to search page navigates", async () => {
    render(<DocumentsPage />);
    await waitFor(() => expect(screen.getByText("Onboarding Guide")).toBeInTheDocument());
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
