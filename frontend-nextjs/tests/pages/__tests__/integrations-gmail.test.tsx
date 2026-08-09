import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import GmailIntegrationPage from "@/pages/integrations/gmail";
import { useRouter } from "next/router";

jest.mock("next/router", () => ({
  useRouter: jest.fn(() => ({
    route: "/integrations/gmail",
    pathname: "/integrations/gmail",
    query: {},
    asPath: "/integrations/gmail",
    push: jest.fn(() => Promise.resolve(true)),
    replace: jest.fn(() => Promise.resolve(true)),
    back: jest.fn(),
  })),
}));

const okResponse = (body: any) => ({
  ok: true,
  status: 200,
  json: async () => body,
});
const errResponse = (status: number) => ({
  ok: false,
  status,
  json: async () => ({}),
});

const navigationErrors: string[] = [];
const vc: any = window._virtualConsole;
if (vc && vc.on) {
  vc.on("jsdomError", (error: any) => {
    const message = String(error && (error.message || error));
    if (message.includes("Not implemented: navigation")) {
      navigationErrors.push(message);
    }
  });
}

describe("GmailIntegrationPage", () => {
  const mockFetch = jest.fn();
  const mockPush = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = mockFetch;
    (useRouter as jest.Mock).mockReturnValue({
      push: mockPush,
      replace: jest.fn(),
      prefetch: jest.fn(),
      back: jest.fn(),
    });
    mockFetch.mockImplementation(() =>
      Promise.resolve(errResponse(500)),
    );
  });

  it("shows Checking then Disconnected when the status endpoint is not ok", async () => {
    render(<GmailIntegrationPage />);
    expect(screen.getByText("Checking...")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeInTheDocument();
    });
    expect(mockFetch).toHaveBeenCalledWith("/api/integrations/gmail/status");
  });

  it("shows Connected when the status endpoint reports connected", async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve(okResponse({ connected: true })),
    );
    render(<GmailIntegrationPage />);
    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });
    expect(screen.queryByText("Disconnected")).not.toBeInTheDocument();
  });

  it("switches tabs via quick action buttons", async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve(okResponse({ connected: true })),
    );
    render(<GmailIntegrationPage />);
    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /View Inbox/i }));
    expect(
      screen.getByRole("heading", { name: /Gmail Inbox/i }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Compose/i }));
    expect(
      screen.getByRole("heading", { name: /Compose Email/i }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Calendar/i }));
    expect(
      screen.getByRole("heading", { name: /Google Calendar/i }),
    ).toBeInTheDocument();
  });

  it("switches tabs via the tab navigation bar", async () => {
    render(<GmailIntegrationPage />);
    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Settings/i }));
    expect(
      screen.getByRole("heading", { name: /Gmail Settings/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Connection Status"),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /🧠 Memory/i }));
    expect(
      screen.getByRole("heading", { name: /Gmail Memory \(LanceDB\)/i }),
    ).toBeInTheDocument();
  });

  it("navigates back to the integrations hub", async () => {
    render(<GmailIntegrationPage />);
    fireEvent.click(
      screen.getByRole("button", { name: /← Back to Integrations/i }),
    );
    expect(mockPush).toHaveBeenCalledWith("/integrations");
  });

  it("starts the OAuth flow from the settings tab", async () => {
    navigationErrors.length = 0;

    render(<GmailIntegrationPage />);
    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /Settings/i }));
    fireEvent.click(
      screen.getByRole("button", { name: /Connect Gmail Account/i }),
    );
    expect(navigationErrors).toHaveLength(1);
  });

  it("shows an empty state when no emails are loaded on the overview", async () => {
    mockFetch.mockImplementation(() =>
      Promise.resolve(okResponse({ connected: false })),
    );
    render(<GmailIntegrationPage />);
    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeInTheDocument();
    });

    expect(
      screen.getByText(
        "No emails found. Connect your Gmail account to get started.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("No upcoming events found."),
    ).toBeInTheDocument();
  });

  it("renders GmailSearch with the total count on the inbox tab", async () => {
    render(<GmailIntegrationPage />);
    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /📥 Inbox/i }));
    expect(
      screen.getByPlaceholderText("Search messages..."),
    ).toBeInTheDocument();
    expect(screen.getByText("Showing 0 of 0 items")).toBeInTheDocument();
  });
});
