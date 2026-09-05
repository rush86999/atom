/**
 * CanvasDataSection tests — canvas journey step 3 (load data), gated on the
 * attached hire.
 *
 * Covers: the gate (everything disabled with a hint until a hire is
 * attached), upload success/failure surfacing (including the backend's 409
 * NO_AGENT_ON_CANVAS), the Zoho folder picker, and the gated folder-load
 * call carrying canvas_id.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import { CanvasDataSection } from "@/components/canvas/CanvasDataSection";
import { uploadCanvasData } from "@/lib/canvas-api";

jest.mock("@/lib/canvas-api", () => ({
  __esModule: true,
  uploadCanvasData: jest.fn(),
}));

const mockedUpload = uploadCanvasData as jest.Mock;

// apiClient is imported dynamically inside the drive pickers.
const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("@/lib/api", () => ({
  __esModule: true,
  apiClient: {
    get: (...args: any[]) => mockGet(...args),
    post: (...args: any[]) => mockPost(...args),
  },
}));

function renderSection(hireAttached: boolean) {
  const utils = render(<CanvasDataSection canvasId="c-1" hireAttached={hireAttached} />);
  const fileInput = utils.container.querySelector('input[type="file"]') as HTMLInputElement;
  return { ...utils, fileInput };
}

function uploadFile(fileInput: HTMLInputElement, name: string) {
  fireEvent.change(fileInput, {
    target: { files: [new File(["hello"], name, { type: "text/plain" })] },
  });
}

describe("CanvasDataSection", () => {
  beforeEach(() => {
    jest.resetAllMocks();
  });

  it("gates everything with a hint when no hire is attached", () => {
    renderSection(false);
    expect(screen.getByTestId("canvas-upload-data-button")).toBeDisabled();
    expect(screen.getByTestId("data-gated-hint")).toHaveTextContent(
      "Attach an agent to load data.",
    );
    expect(screen.queryByTestId("drive-tab-zoho")).not.toBeInTheDocument();
  });

  it("enables upload and drive tabs once a hire is attached", () => {
    renderSection(true);
    expect(screen.getByTestId("canvas-upload-data-button")).toBeEnabled();
    expect(screen.queryByTestId("data-gated-hint")).not.toBeInTheDocument();
    expect(screen.getByTestId("drive-tab-zoho")).toBeEnabled();
    expect(screen.getByTestId("drive-tab-gdrive")).toBeEnabled();
    expect(screen.getByTestId("drive-tab-onedrive")).toBeEnabled();
  });

  it("reports a successful upload with the hire's role", async () => {
    mockedUpload.mockResolvedValue({
      ingestion: { status: "ingested" },
      role: "finance",
    });
    const { fileInput } = renderSection(true);
    uploadFile(fileInput, "notes.txt");

    await waitFor(() => expect(mockedUpload).toHaveBeenCalledWith("c-1", expect.any(File)));
    expect(await screen.findByTestId("canvas-data-notice")).toHaveTextContent(
      /Loaded “notes.txt”/,
    );
  });

  it("surfaces the backend 409 gate message if it races", async () => {
    mockedUpload.mockRejectedValue({
      response: { data: { error: { message: "This canvas has no agent attached — add an agent before loading data." } } },
    });
    const { fileInput } = renderSection(true);
    uploadFile(fileInput, "notes.txt");
    expect(await screen.findByTestId("canvas-data-notice")).toHaveTextContent(
      /no agent attached/,
    );
  });

  it("reports unsupported parses instead of pretending success", async () => {
    mockedUpload.mockResolvedValue({
      ingestion: { status: "skipped", reason: "no_text" },
    });
    const { fileInput } = renderSection(true);
    uploadFile(fileInput, "scan.png");
    expect(await screen.findByTestId("canvas-data-notice")).toHaveTextContent(
      /not ingested/,
    );
  });

  it("lists Zoho folders and loads selected ones with canvas_id", async () => {
    mockPost.mockImplementation(async (url: string) => {
      if (url.includes("/files/list")) {
        return { data: { data: [
          { id: "fld-1", name: "Invoices", type: "folder" },
          { id: "doc-1", name: "q3.xlsx", type: "file" },
        ] } };
      }
      if (url.includes("/ingest-folder")) {
        return { data: { job_id: "job-1", status: "started" } };
      }
      throw new Error(`unexpected POST ${url}`);
    });

    renderSection(true);
    fireEvent.click(screen.getByTestId("drive-tab-zoho"));

    await waitFor(() => expect(mockPost).toHaveBeenCalledWith(
      "/api/zoho-workdrive/files/list",
      { parent_id: "root", recursive: false },
    ));
    expect(await screen.findByText("Invoices")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("select-folder-fld-1"));
    fireEvent.click(screen.getByTestId("load-selected-folders"));

    await waitFor(() => expect(mockPost).toHaveBeenCalledWith(
      "/api/zoho-workdrive/ingest-folder",
      { folder_ids: ["fld-1"], canvas_id: "c-1" },
    ));
  });

  it("surfaces not-connected drives as guidance, not a dead picker", async () => {
    mockGet.mockResolvedValueOnce({
      data: { files: [], nextPageToken: null, error: "not_connected" },
    });
    renderSection(true);
    fireEvent.click(screen.getByTestId("drive-tab-gdrive"));
    expect(await screen.findByTestId("canvas-data-notice")).toHaveTextContent(
      /Google Drive isn't connected/,
    );
  });
});
