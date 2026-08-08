import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import DocumentsPage from "@/pages/documents";
import api from "@/lib/api";
import { useRouter } from "next/router";

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
  },
}));

jest.mock("sonner", () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));

jest.mock("next/router", () => ({
  useRouter: jest.fn(() => ({
    route: "/",
    pathname: "/",
    query: {},
    asPath: "/",
    push: jest.fn(() => Promise.resolve(true)),
    replace: jest.fn(() => Promise.resolve(true)),
    back: jest.fn(),
  })),
}));

const mockApi = api as jest.Mocked<typeof api>;

const MOCK_DOCS = [
  {
    id: "doc-1",
    title: "Q3 Financial Report",
    text_preview: "Revenue grew 12% in Q3...",
    created_at: "2026-07-01T00:00:00Z",
  },
  {
    id: "doc-2",
    title: "Onboarding Guide",
    text_preview: "Welcome to the team...",
    created_at: "2026-07-15T00:00:00Z",
  },
];

describe("DocumentsPage", () => {
  const mockPush = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (mockApi.get as jest.Mock).mockResolvedValue({
      status: 200,
      data: { success: true, data: MOCK_DOCS },
    });
    (mockApi.post as jest.Mock).mockResolvedValue({
      status: 201,
      data: { success: true },
    });
    (useRouter as jest.Mock).mockReturnValue({ push: mockPush, query: {} });
  });

  it("fetches and renders the documents list", async () => {
    render(<DocumentsPage />);

    expect(mockApi.get).toHaveBeenCalledWith(
      "/api/documents",
      expect.objectContaining({ validateStatus: expect.any(Function) })
    );

    await waitFor(() => {
      expect(screen.getByText("Q3 Financial Report")).toBeInTheDocument();
    });
    expect(screen.getByText("Onboarding Guide")).toBeInTheDocument();
    expect(screen.getByText("Revenue grew 12% in Q3...")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /knowledge base/i })).toBeInTheDocument();
  });

  it("shows the empty state when no documents exist", async () => {
    (mockApi.get as jest.Mock).mockResolvedValue({
      status: 200,
      data: { success: true, data: [] },
    });

    render(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText("No documents uploaded yet.")).toBeInTheDocument();
    });
  });

  it("does not crash when the list fetch fails", async () => {
    (mockApi.get as jest.Mock).mockRejectedValue(new Error("network down"));

    render(<DocumentsPage />);

    await waitFor(() => {
      expect(screen.getByText("No documents uploaded yet.")).toBeInTheDocument();
    });
  });

  it("uploads a file and shows the success status", async () => {
    render(<DocumentsPage />);
    await waitFor(() => {
      expect(screen.getByText("Q3 Financial Report")).toBeInTheDocument();
    });

    const file = new File(["report content"], "report.pdf", { type: "application/pdf" });
    const input = document.getElementById("file-upload") as HTMLInputElement;

    await act(async () => {
      fireEvent.change(input, { target: { files: [file] } });
    });

    await waitFor(() => {
      expect(screen.getByText(/Successfully uploaded "report\.pdf"/)).toBeInTheDocument();
    });
    expect(mockApi.post).toHaveBeenCalledWith(
      "/api/documents/upload",
      expect.any(FormData),
      expect.objectContaining({ validateStatus: expect.any(Function) })
    );
    // List is refreshed after a successful upload
    expect(mockApi.get).toHaveBeenCalledTimes(2);
  });

  it("shows an error status when the upload response is not successful", async () => {
    (mockApi.post as jest.Mock).mockResolvedValue({
      status: 400,
      data: { success: false, detail: "Unsupported file type" },
    });

    render(<DocumentsPage />);
    await waitFor(() => {
      expect(screen.getByText("Q3 Financial Report")).toBeInTheDocument();
    });

    const file = new File(["x"], "virus.exe", { type: "application/x-msdownload" });
    const input = document.getElementById("file-upload") as HTMLInputElement;

    await act(async () => {
      fireEvent.change(input, { target: { files: [file] } });
    });

    await waitFor(() => {
      expect(screen.getByText("Unsupported file type")).toBeInTheDocument();
    });
  });

  it("shows an error status when the upload throws", async () => {
    (mockApi.post as jest.Mock).mockRejectedValue({
      response: { data: { detail: "Backend unreachable" } },
    });

    render(<DocumentsPage />);
    await waitFor(() => {
      expect(screen.getByText("Q3 Financial Report")).toBeInTheDocument();
    });

    const file = new File(["x"], "a.txt", { type: "text/plain" });
    const input = document.getElementById("file-upload") as HTMLInputElement;

    await act(async () => {
      fireEvent.change(input, { target: { files: [file] } });
    });

    await waitFor(() => {
      expect(screen.getByText("Backend unreachable")).toBeInTheDocument();
    });
  });

  it("uploads a dropped file via drag and drop", async () => {
    render(<DocumentsPage />);
    await waitFor(() => {
      expect(screen.getByText("Q3 Financial Report")).toBeInTheDocument();
    });

    const dropZone = screen.getByText(/click to upload or drag and drop/i).closest("div")!;
    const file = new File(["md"], "notes.md", { type: "text/markdown" });

    fireEvent.dragEnter(dropZone);
    await act(async () => {
      fireEvent.drop(dropZone, { dataTransfer: { files: [file] } });
    });

    await waitFor(() => {
      expect(screen.getByText(/Successfully uploaded "notes\.md"/)).toBeInTheDocument();
    });
  });

  it("navigates to a document detail page when a document card is clicked", async () => {
    render(<DocumentsPage />);
    await waitFor(() => {
      expect(screen.getByText("Q3 Financial Report")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText("Q3 Financial Report"));

    expect(mockPush).toHaveBeenCalledWith("/documents/doc-1");
  });

  it("navigates to the search page", async () => {
    render(<DocumentsPage />);

    fireEvent.click(screen.getByRole("button", { name: /go to search page/i }));

    expect(mockPush).toHaveBeenCalledWith("/search");
  });

  it("reloads the document list when Refresh is clicked", async () => {
    render(<DocumentsPage />);
    await waitFor(() => {
      expect(screen.getByText("Q3 Financial Report")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /refresh/i }));

    await waitFor(() => {
      expect(mockApi.get).toHaveBeenCalledTimes(2);
    });
  });
});
