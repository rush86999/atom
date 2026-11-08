/**
 * Documents detail export control (NEXT03).
 * Real detail component; only the shared API client is mocked.
 */
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import DocumentDetailsPage from "@/pages/documents/[docId]";
import { FALLBACK_PROFILE } from "@/lib/product-profile";

const mockGet = jest.fn();

jest.mock("next/router", () => ({
  useRouter: () => ({
    query: { docId: "doc-1" },
    push: jest.fn(),
    replace: jest.fn(),
    prefetch: jest.fn(),
    back: jest.fn(),
    reload: jest.fn(),
    pathname: "/documents/doc-1",
    asPath: "/documents/doc-1",
    events: { on: jest.fn(), off: jest.fn(), emit: jest.fn() },
  }),
}));

jest.mock("../../lib/api", () => ({
  __esModule: true,
  default: {
    get: (...args: any[]) => mockGet(...args),
  },
}));

const DOCUMENT = {
  id: "doc-1",
  title: "Onboarding Guide",
  content: "Stored extracted text for the onboarding guide.",
  type: "txt",
  metadata: { source: "manual_upload", file_name: "onboarding.txt" },
  ingested_at: "2026-11-07T00:00:00Z",
};

const originalCreateObjectURL = window.URL.createObjectURL;
const originalRevokeObjectURL = window.URL.revokeObjectURL;

function mockRead() {
  mockGet.mockImplementation(async (url: string) => {
    if (url.includes("/export")) {
      return {
        data: new Blob(["exported"], { type: "text/plain" }),
        headers: { "content-type": "text/plain" },
      };
    }
    return { data: { success: true, data: DOCUMENT } };
  });
}

describe("DocumentDetailsPage export", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockRead();
    (window.URL as any).createObjectURL = jest.fn(() => "blob:next03");
    (window.URL as any).revokeObjectURL = jest.fn();
  });

  afterEach(() => {
    (window.URL as any).createObjectURL = originalCreateObjectURL;
    (window.URL as any).revokeObjectURL = originalRevokeObjectURL;
  });

  test("renders one Export stored text control over the enabled Data profile", async () => {
    expect(FALLBACK_PROFILE.capabilities.documents.enabled).toBe(true);
    expect(Boolean(FALLBACK_PROFILE.capabilities.search?.enabled)).toBe(false);

    render(<DocumentDetailsPage />);
    await waitFor(() => expect(screen.getByText("Onboarding Guide")).toBeInTheDocument());

    expect(screen.getByTestId("document-export")).toBeInTheDocument();
    expect(screen.getByText("Export stored text")).toBeInTheDocument();
    expect(screen.getByTestId("document-export-format")).toHaveValue("text");
    expect(screen.getByTestId("document-export-submit")).toHaveTextContent("Download");
    expect(screen.getByRole("option", { name: "Text (.txt)" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Markdown (.md)" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "JSON (.json)" })).toBeInTheDocument();
  });

  test("download uses the existing API client, blob and auth-compatible request", async () => {
    let clicked: HTMLAnchorElement | null = null;
    const clickSpy = jest
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(function (this: HTMLAnchorElement) {
        clicked = this;
      });

    render(<DocumentDetailsPage />);
    await waitFor(() => expect(screen.getByTestId("document-export-submit")).toBeInTheDocument());

    fireEvent.change(screen.getByTestId("document-export-format"), {
      target: { value: "json" },
    });
    fireEvent.click(screen.getByTestId("document-export-submit"));

    await waitFor(() =>
      expect(mockGet).toHaveBeenCalledWith(
        "/api/documents/doc-1/export",
        expect.objectContaining({
          params: { format: "json" },
          responseType: "blob",
        }),
      ),
    );
    await waitFor(() => expect(clickSpy).toHaveBeenCalled());
    expect(clicked).not.toBeNull();
    expect(clicked!.download).toBe("Onboarding Guide.json");
    expect((window.URL as any).createObjectURL).toHaveBeenCalled();
    expect((window.URL as any).revokeObjectURL).toHaveBeenCalled();
    expect(screen.queryByTestId("document-export-error")).not.toBeInTheDocument();

    clickSpy.mockRestore();
  });

  test("export failure shows inline bounded error and does not download", async () => {
    let clicked = false;
    const clickSpy = jest
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {
        clicked = true;
      });
    mockGet.mockImplementation(async (url: string) => {
      if (url.includes("/export")) {
        const error: any = new Error("conflict");
        error.response = {
          data: {
            detail: {
              error: {
                message: "The authoritative document is not current.",
              },
            },
          },
        };
        throw error;
      }
      return { data: { success: true, data: DOCUMENT } };
    });

    render(<DocumentDetailsPage />);
    await waitFor(() => expect(screen.getByTestId("document-export-submit")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("document-export-submit"));

    await waitFor(() =>
      expect(screen.getByTestId("document-export-error")).toHaveTextContent(
        "The authoritative document is not current.",
      ),
    );
    expect(clicked).toBe(false);
    expect((window.URL as any).createObjectURL).not.toHaveBeenCalled();
    clickSpy.mockRestore();
  });
});
