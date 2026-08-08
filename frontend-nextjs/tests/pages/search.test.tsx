import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import SearchPage from "@/pages/search";
import { useRouter } from "next/router";

const mockPush = jest.fn();

jest.mock("next/router", () => ({
  useRouter: jest.fn(() => ({ push: mockPush })),
}));

const RESULTS = [
  {
    id: "doc-1",
    title: "Q3 Board Deck",
    content: "Financial projections for Q3 with revised revenue targets.",
    doc_type: "document",
    source_uri: "s3://bucket/q3.pdf",
    similarity_score: 0.87,
    combined_score: 0.92,
    metadata: {
      created_at: "2026-07-10T12:00:00Z",
      author: "Ada Lovelace",
      tags: ["finance", "q3"],
    },
  },
  {
    id: "doc-2",
    title: "Customer Feedback Notes",
    content: "Users love the new AI search experience.",
    doc_type: "note",
    source_uri: "s3://bucket/notes.md",
    similarity_score: 0.71,
    metadata: { created_at: "2026-06-01T08:00:00Z" },
  },
];

const okJson = (body: any) => ({ ok: true, json: async () => body });

describe("SearchPage", () => {
  const mockFetch = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (useRouter as jest.Mock).mockReturnValue({ push: mockPush });
    global.fetch = mockFetch;
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/suggestions")) {
        return Promise.resolve(okJson({ success: true, suggestions: ["meeting notes"] }));
      }
      if (url.includes("/hybrid")) {
        return Promise.resolve(okJson({ success: true, results: RESULTS }));
      }
      return Promise.resolve(okJson({ success: false }));
    });
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  const hybridBody = (): any => {
    const call = mockFetch.mock.calls.find(([url]) => String(url).includes("/hybrid"));
    expect(call).toBeTruthy();
    return JSON.parse((call as any[])[1].body);
  };

  it("renders the header, search input and filters", () => {
    render(<SearchPage />);
    expect(
      screen.getByRole("heading", { name: /AI-Powered Search/i })
    ).toBeInTheDocument();
    expect(screen.getByTestId("search-input")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Hybrid Search")).toBeInTheDocument();
    expect(screen.getByText("Filters")).toBeInTheDocument();
    expect(screen.getByText("Document Type")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "document" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "email" })).toBeInTheDocument();
  });

  it("shows popular searches when the input is focused with an empty query", () => {
    render(<SearchPage />);
    fireEvent.focus(screen.getByTestId("search-input"));
    expect(screen.getByText("Popular Searches")).toBeInTheDocument();
    expect(screen.getByText("project requirements")).toBeInTheDocument();
    expect(screen.getByText("customer feedback")).toBeInTheDocument();
  });

  it("debounces typing and performs a hybrid search", async () => {
    jest.useFakeTimers();
    render(<SearchPage />);
    fireEvent.change(screen.getByTestId("search-input"), {
      target: { value: "project requirements" },
    });

    expect(mockFetch).not.toHaveBeenCalledWith(
      "/api/lancedb-search/hybrid",
      expect.anything()
    );

    await act(async () => {
      jest.advanceTimersByTime(300);
    });
    await act(async () => {});

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/lancedb-search/hybrid",
      expect.objectContaining({ method: "POST" })
    );
    const body = hybridBody();
    expect(body.query).toBe("project requirements");
    expect(body.search_type).toBe("hybrid");
    expect(body.limit).toBe(20);

    expect(screen.getByText(/Found 2 results/)).toBeInTheDocument();
    expect(screen.getByText("Q3 Board Deck")).toBeInTheDocument();
    expect(screen.getAllByText("document").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Relevance: 92%")).toBeInTheDocument();
    expect(screen.getByText(/Author: Ada Lovelace/)).toBeInTheDocument();
    expect(screen.getByText("finance")).toBeInTheDocument();
    expect(screen.getAllByText("note").length).toBeGreaterThanOrEqual(1);
  });

  it("searches immediately when the Search button is clicked", async () => {
    render(<SearchPage />);
    fireEvent.change(screen.getByTestId("search-input"), {
      target: { value: "meeting notes" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Search$/ }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/lancedb-search/hybrid",
        expect.objectContaining({ method: "POST" })
      );
    });
    expect(hybridBody().query).toBe("meeting notes");
    await waitFor(() => {
      expect(screen.getByText("Q3 Board Deck")).toBeInTheDocument();
    });
  });

  it("shows a loading spinner while a search is in flight", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/hybrid")) return new Promise(() => {});
      return Promise.resolve(okJson({ success: true, suggestions: [] }));
    });
    render(<SearchPage />);
    fireEvent.change(screen.getByTestId("search-input"), {
      target: { value: "meeting notes" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Search$/ }));
    expect(screen.getByText("Searching...")).toBeInTheDocument();
  });

  it("renders an empty-results message when the search returns nothing", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/hybrid")) {
        return Promise.resolve(okJson({ success: true, results: [] }));
      }
      return Promise.resolve(okJson({ success: true, suggestions: [] }));
    });
    render(<SearchPage />);
    fireEvent.change(screen.getByTestId("search-input"), {
      target: { value: "zzz" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Search$/ }));
    await waitFor(() => {
      expect(screen.getByText(/No results found for "zzz"/)).toBeInTheDocument();
    });
  });

  it("shows the API error message when the backend reports failure", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/hybrid")) {
        return Promise.resolve(
          okJson({ success: false, message: "Vector store unavailable" })
        );
      }
      return Promise.resolve(okJson({ success: true, suggestions: [] }));
    });
    render(<SearchPage />);
    fireEvent.change(screen.getByTestId("search-input"), {
      target: { value: "meeting notes" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Search$/ }));
    await waitFor(() => {
      expect(screen.getByText("Vector store unavailable")).toBeInTheDocument();
    });
  });

  it("shows a friendly message when the network request fails", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/hybrid")) return Promise.reject(new Error("ECONNREFUSED"));
      return Promise.resolve(okJson({ success: true, suggestions: [] }));
    });
    render(<SearchPage />);
    fireEvent.change(screen.getByTestId("search-input"), {
      target: { value: "meeting notes" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Search$/ }));
    await waitFor(() => {
      expect(
        screen.getByText("Failed to perform search. Please try again.")
      ).toBeInTheDocument();
    });
  });

  it("searches when a suggestion is clicked", async () => {
    render(<SearchPage />);
    fireEvent.change(screen.getByTestId("search-input"), {
      target: { value: "meet" },
    });
    await waitFor(() => {
      expect(screen.getByText("meeting notes")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("meeting notes"));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/lancedb-search/hybrid",
        expect.anything()
      );
    });
    expect(hybridBody().query).toBe("meeting notes");
    await waitFor(() => {
      expect(screen.getByText("Q3 Board Deck")).toBeInTheDocument();
    });
  });

  it("includes toggled doc-type filters in the search request", async () => {
    render(<SearchPage />);
    fireEvent.click(screen.getByRole("checkbox", { name: "meeting" }));
    fireEvent.change(screen.getByTestId("search-input"), {
      target: { value: "meeting notes" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Search$/ }));
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/lancedb-search/hybrid",
        expect.anything()
      );
    });
    expect(hybridBody().filters.doc_type).toEqual(["meeting"]);
  });

  it("updates the minimum relevance filter via the slider", () => {
    render(<SearchPage />);
    const slider = document.querySelector(
      'input[type="range"]'
    ) as HTMLInputElement;
    expect(slider).not.toBeNull();
    fireEvent.change(slider, { target: { value: "50" } });
    expect(screen.getByText("50% and above")).toBeInTheDocument();
  });

  it("sends the selected search type in the request", async () => {
    render(<SearchPage />);
    fireEvent.change(screen.getByRole("combobox"), {
      target: { value: "semantic" },
    });
    fireEvent.change(screen.getByTestId("search-input"), {
      target: { value: "meeting notes" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Search$/ }));
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/lancedb-search/hybrid",
        expect.anything()
      );
    });
    expect(hybridBody().search_type).toBe("semantic");
  });

  it("navigates to the document when a result is clicked", async () => {
    render(<SearchPage />);
    fireEvent.change(screen.getByTestId("search-input"), {
      target: { value: "meeting notes" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Search$/ }));
    await waitFor(() => {
      expect(screen.getByText("Q3 Board Deck")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("Q3 Board Deck"));
    expect(mockPush).toHaveBeenCalledWith("/documents/doc-1");
  });

  it("clears results when the query shrinks to 2 characters or fewer", async () => {
    jest.useFakeTimers();
    render(<SearchPage />);
    fireEvent.change(screen.getByTestId("search-input"), {
      target: { value: "abc" },
    });
    await act(async () => {
      jest.advanceTimersByTime(300);
    });
    await act(async () => {});
    expect(screen.getByText(/Found 2 results/)).toBeInTheDocument();

    fireEvent.change(screen.getByTestId("search-input"), {
      target: { value: "a" },
    });
    await act(async () => {});
    expect(screen.queryByText(/Found 2 results/)).not.toBeInTheDocument();
    expect(screen.getByText(/No results found for "a"/)).toBeInTheDocument();
    const hybridCallsForShortQuery = mockFetch.mock.calls.filter(
      ([url, init]: any) =>
        String(url).includes("/hybrid") &&
        init &&
        JSON.parse(init.body).query === "a"
    );
    expect(hybridCallsForShortQuery.length).toBe(0);
  });
});
