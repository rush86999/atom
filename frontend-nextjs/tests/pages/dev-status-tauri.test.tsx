/**
 * DevStatus page tests (pages/dev-status.tsx) — Tauri mode
 *
 * With the Tauri `invoke` available, system status loads and the System Info
 * tab renders platform details + capability toggles.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import DevStatus from "@/pages/dev-status";

const mockToast = jest.fn();

jest.mock("@/components/ui/use-toast", () => ({
  useToast: () => ({ toast: mockToast }),
}));

const mockInvoke = jest.fn();
jest.mock("@tauri-apps/api", () => ({ invoke: (...args: any[]) => mockInvoke(...args) }));

const SYSTEM_INFO = {
  platform: "darwin",
  architecture: "arm64",
  uptime: 7200,
  features: { mcp_support: true, sandbox: false },
};

describe("DevStatus (Tauri mode)", () => {
  let mockFetch: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    mockInvoke.mockResolvedValue(SYSTEM_INFO);
    mockFetch = jest.fn().mockResolvedValue({ ok: true, status: 200 });
    global.fetch = mockFetch;
  });

  test("loads system info via invoke and shows platform", async () => {
    render(<DevStatus />);
    await waitFor(() => expect(screen.getByText("DARWIN")).toBeInTheDocument());
    expect(mockInvoke).toHaveBeenCalledWith("get_system_info");
    expect(screen.getByText("arm64")).toBeInTheDocument();
  });

  test("system info tab renders platform details and capabilities", async () => {
    render(<DevStatus />);
    await waitFor(() => expect(screen.getByText("DARWIN")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /System Info/ }));
    expect(screen.getByText("7200")).toBeInTheDocument();
    expect(screen.getByText("Mcp Support")).toBeInTheDocument();
    expect(screen.getByText("Enabled")).toBeInTheDocument();
    expect(screen.getByText("Sandbox")).toBeInTheDocument();
    expect(screen.getByText("Disabled")).toBeInTheDocument();
  });

  test("system info invoke failure falls back to web environment", async () => {
    mockInvoke.mockRejectedValue(new Error("no desktop"));
    const consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    render(<DevStatus />);
    await waitFor(() => expect(screen.getByText("Web")).toBeInTheDocument());
    consoleSpy.mockRestore();
  });
});
