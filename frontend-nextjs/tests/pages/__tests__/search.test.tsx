import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SearchPage from "@/pages/search";
import { useRouter } from "next/router";

const mockPush = jest.fn(() => Promise.resolve(true));

jest.mock("next/router", () => ({
  useRouter: jest.fn(() => ({
    push: jest.fn(() => Promise.resolve(true)),
  })),
}));

const okResponse = (body: any) => ({
  ok: true,
  status: 200,
  json: async () => body,
});

const RESULTS = [
  {
    id: "doc-1",
    title: "Project Requirements",
    content: "Requirements document for the Q3 release.",
    doc_type: "document",
    source_uri: "/documents/doc-1",
    similarity_score: 0.92,
    combined_score: 0.94,
    keyword_score: 0.8,
    metadata: {
      created_at: "2026-07-01T00:00:00Z",
      author: "Ada Lovelace",
      tags: ["requirements", "q3"],
    },
  },
  {
    id: "doc-2",
    title: "Customer Feedback",
    content: "Feedback survey results.",
    doc_type: "note",
    source_uri: "/documents/doc-2",
    similarity_score: 0.61,
    metadata: {
      created_at: "2026-07-05T00:00:00Z",
      tags: [],
    },
  },
];

const mockFetch = jest.fn();

describe("Search page (pages/search.tsx)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (useRouter as jest.Mock).mockReturnValue({ push: mockPush });
    mockFetch.mockImplementation((url: string, opts?: any) => {
      if (url === "/api/lancedb-search/hybrid") {
        return Promise.resolve(okResponse({ success: true, results: RESULTS }));
      }
      if (url.startsWith("/api/lancedb-search/suggestions")) {
        return Promise.resolve(
          okResponse({ success: true, suggestions: ["project alpha", "project beta"] })
        );
      }
      return Promise.resolve(okResponse({}));
    });
    global.fetch = mockFetch as any;
  });

  it("renders the search page shell with header, filters and default hybrid type", () => {
    render(<SearchPage />);

    expect(screen.getByText("AI-Powered Search")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Search across documents, meetings, notes...")).toBeInTheDocument();
    expect(screen.getByRole("combobox")).toHaveValue("hybrid");
    expect(screen.getByText("Filters")).toBeInTheDocument();
    for (const type of ["document", "meeting", "note", "email", "pdf"]) {
      expect(screen.getByLabelText(type)).toBeInTheDocument();
    }
    expect(screen.getByText("-100% and above")).toBeInTheDocument();
  });

  it("shows popular searches on focus and runs a search when one is clicked", async () => {
    render(<SearchPage />);

    fireEvent.focus(screen.getByPlaceholderText("Search across documents, meetings, notes..."));

    expect(screen.getByText("Popular Searches")).toBeInTheDocument();
    fireEvent.click(screen.getByText("project requirements"));

    await waitFor(() => {
      const calls = mockFetch.mock.calls.filter(
        ([u]) => u === "/api/lancedb-search/hybrid"
      );
      expect(
        calls.some(([, o]) => {
          const body = JSON.parse((o as any).body);
          return (
            body.query === "project requirements" &&
            body.search_type === "hybrid" &&
            body.limit === 20
          );
        })
      ).toBe(true);
    });
    expect(
      await screen.findByText(/Found 2 results for "project requirements"/)
    ).toBeInTheDocument();
  });

  it("performs a debounced search while typing and renders results with metadata", async () => {
    render(<SearchPage />);

    fireEvent.change(
      screen.getByPlaceholderText("Search across documents, meetings, notes..."),
      { target: { value: "API documentation" } }
    );

    await waitFor(() =>
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/lancedb-search/hybrid",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
        })
      )
    );
    const hybridCall = mockFetch.mock.calls.find(
      ([u]) => u === "/api/lancedb-search/hybrid"
    )!;
    const body = JSON.parse((hybridCall[1] as any).body);
    expect(body.query).toBe("API documentation");
    expect(body.search_type).toBe("hybrid");
    expect(body.limit).toBe(20);

    expect(await screen.findByText("Project Requirements")).toBeInTheDocument();
    expect(screen.getByText("Requirements document for the Q3 release.")).toBeInTheDocument();
    expect(screen.getByText(/Relevance: 94%/)).toBeInTheDocument();
    expect(
      screen.getAllByText("document").length
    ).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Author: Ada Lovelace")).toBeInTheDocument();
    expect(screen.getAllByText(/Created:/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("requirements")).toBeInTheDocument();
    expect(screen.getByText("q3")).toBeInTheDocument();

    // Suggestions endpoint was hit for the partial query too
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/lancedb-search/suggestions?query=API%20documentation&limit=5"
    );
  });

  it("navigates to the document when a result is clicked", async () => {
    render(<SearchPage />);

    fireEvent.change(
      screen.getByPlaceholderText("Search across documents, meetings, notes..."),
      { target: { value: "API documentation" } }
    );
    fireEvent.click(await screen.findByText("Project Requirements"));

    expect(mockPush).toHaveBeenCalledWith("/documents/doc-1");
  });

  it("shows the loading spinner while a search is in flight", async () => {
    let resolveHybrid: (r: any) => void = () => {};
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/lancedb-search/hybrid") {
        return new Promise((resolve) => {
          resolveHybrid = resolve;
        });
      }
      return Promise.resolve(okResponse({ success: true, suggestions: [] }));
    });

    render(<SearchPage />);

    fireEvent.change(
      screen.getByPlaceholderText("Search across documents, meetings, notes..."),
      { target: { value: "abc" } }
    );

    await waitFor(() => expect(screen.getByText("Searching...")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /searching/i })).toBeDisabled();

    resolveHybrid(okResponse({ success: true, results: RESULTS }));
    expect(await screen.findByText("Project Requirements")).toBeInTheDocument();
    expect(screen.queryByText("Searching...")).not.toBeInTheDocument();
  });

  it("renders the empty state when no results are found", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/lancedb-search/hybrid") {
        return Promise.resolve(okResponse({ success: true, results: [] }));
      }
      return Promise.resolve(okResponse({ success: true, suggestions: [] }));
    });

    render(<SearchPage />);

    fireEvent.change(
      screen.getByPlaceholderText("Search across documents, meetings, notes..."),
      { target: { value: "abc" } }
    );

    expect(await screen.findByText(/No results found for "abc"/)).toBeInTheDocument();
    expect(screen.queryByTestId("search-results")).not.toBeInTheDocument();
  });

  it("shows the API error message when the backend reports failure", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/lancedb-search/hybrid") {
        return Promise.resolve(okResponse({ success: false, message: "Backend exploded" }));
      }
      return Promise.resolve(okResponse({ success: true, suggestions: [] }));
    });

    render(<SearchPage />);

    fireEvent.change(
      screen.getByPlaceholderText("Search across documents, meetings, notes..."),
      { target: { value: "abc" } }
    );

    expect(await screen.findByText("Backend exploded")).toBeInTheDocument();
  });

  it("shows a network error message when the search request fails", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/lancedb-search/hybrid") {
        return Promise.reject(new Error("network down"));
      }
      return Promise.resolve(okResponse({ success: true, suggestions: [] }));
    });

    render(<SearchPage />);

    fireEvent.change(
      screen.getByPlaceholderText("Search across documents, meetings, notes..."),
      { target: { value: "abc" } }
    );

    expect(
      await screen.findByText("Failed to perform search. Please try again.")
    ).toBeInTheDocument();
  });

  it("includes toggled document-type filters in the next search", async () => {
    render(<SearchPage />);

    fireEvent.change(
      screen.getByPlaceholderText("Search across documents, meetings, notes..."),
      { target: { value: "abc" } }
    );
    await waitFor(() =>
      expect(
        mockFetch.mock.calls.some(
          ([u]) => u === "/api/lancedb-search/hybrid"
        )
      ).toBe(true)
    );

    fireEvent.click(screen.getByLabelText("document"));

    await waitFor(() => {
      const calls = mockFetch.mock.calls.filter(
        ([u]) => u === "/api/lancedb-search/hybrid"
      );
      expect(
        calls.some(([, o]) =>
          (JSON.parse((o as any).body).filters.doc_type as string[]).includes("document")
        )
      ).toBe(true);
    });
  });

  it("sends the selected search type in the request", async () => {
    render(<SearchPage />);

    fireEvent.change(
      screen.getByPlaceholderText("Search across documents, meetings, notes..."),
      { target: { value: "abc" } }
    );
    await waitFor(() =>
      expect(
        mockFetch.mock.calls.some(([u]) => u === "/api/lancedb-search/hybrid")
      ).toBe(true)
    );

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "semantic" } });

    await waitFor(() => {
      const calls = mockFetch.mock.calls.filter(
        ([u]) => u === "/api/lancedb-search/hybrid"
      );
      expect(
        calls.some(([, o]) => JSON.parse((o as any).body).search_type === "semantic")
      ).toBe(true);
    });
  });

  it("renders live suggestions while typing and clicking one runs that search", async () => {
    render(<SearchPage />);

    fireEvent.change(
      screen.getByPlaceholderText("Search across documents, meetings, notes..."),
      { target: { value: "proj" } }
    );

    expect(await screen.findByText("project alpha")).toBeInTheDocument();
    expect(screen.getByText("project beta")).toBeInTheDocument();

    fireEvent.click(screen.getByText("project alpha"));

    await waitFor(() => {
      const calls = mockFetch.mock.calls.filter(
        ([u]) => u === "/api/lancedb-search/hybrid"
      );
      expect(
        calls.some(([, o]) => JSON.parse((o as any).body).query === "project alpha")
      ).toBe(true);
    });
    expect(await screen.findByText(/Found 2 results for "project alpha"/)).toBeInTheDocument();
    // Suggestions dropdown closes after running the search
    expect(screen.queryByText("project beta")).not.toBeInTheDocument();
  });
});
