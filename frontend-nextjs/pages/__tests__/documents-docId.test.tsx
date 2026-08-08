import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import DocumentDetailsPage from "@/pages/documents/[docId]";
import api from "@/lib/api";
import { useRouter } from "next/router";

jest.mock("@/lib/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
  },
}));

jest.mock("next/router", () => ({
  useRouter: jest.fn(() => ({
    route: "/documents/[docId]",
    pathname: "/documents/[docId]",
    query: { docId: "doc-1" },
    asPath: "/documents/doc-1",
    push: jest.fn(() => Promise.resolve(true)),
    replace: jest.fn(() => Promise.resolve(true)),
    back: jest.fn(),
  })),
}));

const mockApi = api as jest.Mocked<typeof api>;

const DOC = {
  id: "doc-1",
  title: "Q3 Financial Report",
  content: "Revenue grew 12% this quarter.",
  type: "pdf",
  metadata: {
    author: "Jane Doe",
    source: "uploaded/2026/report.pdf",
    pages: 12,
    tags: ["finance", "q3"],
    title: "ignored-title",
    _internal: "hidden",
  },
  ingested_at: "2026-07-01T00:00:00Z",
};

describe("DocumentDetailsPage", () => {
  const mockBack = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (useRouter as jest.Mock).mockReturnValue({
      route: "/documents/[docId]",
      pathname: "/documents/[docId]",
      query: { docId: "doc-1" },
      asPath: "/documents/doc-1",
      push: jest.fn(() => Promise.resolve(true)),
      replace: jest.fn(() => Promise.resolve(true)),
      back: mockBack,
    });
    (mockApi.get as jest.Mock).mockResolvedValue({
      data: { success: true, data: DOC },
    });
  });

  it("shows a spinner while loading", () => {
    mockApi.get.mockReturnValue(new Promise(() => {}));
    const { container } = render(<DocumentDetailsPage />);
    expect(container.querySelector(".animate-spin")).toBeInTheDocument();
  });

  it("renders document content and metadata", async () => {
    render(<DocumentDetailsPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Q3 Financial Report" })
      ).toBeInTheDocument();
    });

    expect(mockApi.get).toHaveBeenCalledWith("/api/documents/doc-1");

    expect(screen.getByText("Revenue grew 12% this quarter.")).toBeInTheDocument();
    expect(screen.getByText("pdf")).toBeInTheDocument();
    expect(screen.getAllByText("Jane Doe").length).toBeGreaterThan(0);
    expect(screen.getByText("uploaded/2026/report.pdf")).toBeInTheDocument();
    expect(screen.getByText("doc-1")).toBeInTheDocument();

    // Extra metadata keys are rendered, reserved/internal keys are skipped
    expect(screen.getByText("pages")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("tags")).toBeInTheDocument();
    expect(screen.queryByText("ignored-title")).not.toBeInTheDocument();
    expect(screen.queryByText("hidden")).not.toBeInTheDocument();
  });

  it("does not crash when the document has no metadata", async () => {
    (mockApi.get as jest.Mock).mockResolvedValue({
      data: {
        success: true,
        data: { ...DOC, metadata: null },
      },
    });

    render(<DocumentDetailsPage />);

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "Q3 Financial Report" })
      ).toBeInTheDocument();
    });
    expect(screen.getByText("Unknown")).toBeInTheDocument();
    expect(screen.getByText("Document Content")).toBeInTheDocument();
  });

  it("shows the error alert when the response reports failure", async () => {
    (mockApi.get as jest.Mock).mockResolvedValue({
      data: { success: false, message: "Document was deleted" },
    });

    render(<DocumentDetailsPage />);

    await waitFor(() => {
      expect(screen.getByText("Document was deleted")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /go back/i }));
    expect(mockBack).toHaveBeenCalled();
  });

  it("shows the error alert when the request throws", async () => {
    (mockApi.get as jest.Mock).mockRejectedValue({
      response: { data: { message: "Backend unavailable" } },
    });

    render(<DocumentDetailsPage />);

    await waitFor(() => {
      expect(screen.getByText("Backend unavailable")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /go back/i })).toBeInTheDocument();
  });

  it("renders the not-found alert when the document is null", async () => {
    (mockApi.get as jest.Mock).mockResolvedValue({
      data: { success: true, data: null },
    });

    render(<DocumentDetailsPage />);

    await waitFor(() => {
      expect(screen.getByText("Document not found")).toBeInTheDocument();
    });
  });
});
