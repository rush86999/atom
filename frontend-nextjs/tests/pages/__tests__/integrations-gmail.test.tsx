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

function okResponse(body: any) {
  return { ok: true, json: async () => body };
}

function errResponse(status: number) {
  return { ok: false, status, json: async () => ({}) };
}

describe("GmailIntegrationPage", () => {
  const mockFetch = jest.fn();
  const mockPush = jest.fn();
  const openSpy = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (useRouter as jest.Mock).mockReturnValue({
      route: "/integrations/gmail",
      pathname: "/integrations/gmail",
      query: {},
      asPath: "/integrations/gmail",
      push: mockPush,
      replace: jest.fn(() => Promise.resolve(true)),
      back: jest.fn(),
    });
    global.fetch = mockFetch;
    openSpy.mockReturnValue(null);
    jest.spyOn(window, "open").mockImplementation(openSpy);
  });

  it("renders the header and shows Disconnected when the status endpoint is not ok", async () => {
    mockFetch.mockResolvedValue(errResponse(500));
    render(<GmailIntegrationPage />);

    expect(screen.getByRole("heading", { name: /gmail integration/i })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeInTheDocument();
    });
    expect(mockFetch).toHaveBeenCalledWith("/api/integrations/gmail/status");
  });

  it("shows Connected when the status endpoint reports connected", async () => {
    mockFetch.mockResolvedValue(okResponse({ connected: true }));
    render(<GmailIntegrationPage />);

    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });
  });

  it("renders empty-state messages on the overview tab", async () => {
    mockFetch.mockResolvedValue(okResponse({ connected: false }));
    render(<GmailIntegrationPage />);

    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeInTheDocument();
    });

    // Stats start at zero
    expect(screen.getByText("Total Emails").previousSibling?.textContent).toBe("0");
    expect(screen.getByText("Unread").previousSibling?.textContent).toBe("0");

    expect(
      screen.getByText(/No emails found\. Connect your Gmail account to get started\./)
    ).toBeInTheDocument();
    expect(screen.getByText("No upcoming events found.")).toBeInTheDocument();
  });

  it("switches tabs via quick action buttons", async () => {
    mockFetch.mockResolvedValue(okResponse({ connected: false }));
    render(<GmailIntegrationPage />);

    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeInTheDocument();
    });

    // View Inbox → GmailSearch with messages dataType
    fireEvent.click(screen.getByRole("button", { name: /view inbox/i }));
    expect(screen.getByRole("heading", { name: "Gmail Inbox" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Search messages...")).toBeInTheDocument();
    expect(screen.getByText("Showing 0 of 0 items")).toBeInTheDocument();

    // Compose Email
    fireEvent.click(screen.getByRole("button", { name: /compose email/i }));
    expect(screen.getByRole("heading", { name: "Compose Email" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("recipient@example.com")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send email/i })).toBeInTheDocument();

    // Calendar
    fireEvent.click(screen.getByRole("button", { name: /view calendar/i }));
    expect(screen.getByRole("heading", { name: "Google Calendar" })).toBeInTheDocument();
    expect(screen.getByText(/Calendar integration coming soon\./)).toBeInTheDocument();

    // Contacts
    fireEvent.click(screen.getByRole("button", { name: /manage contacts/i }));
    expect(screen.getByRole("heading", { name: "Google Contacts" })).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Search contacts...")).toBeInTheDocument();

    // Tasks
    fireEvent.click(screen.getByRole("button", { name: /view tasks/i }));
    expect(screen.getByRole("heading", { name: "Google Tasks" })).toBeInTheDocument();
    expect(screen.getByText(/Tasks integration coming soon\./)).toBeInTheDocument();
    expect(screen.getByText("Total Tasks").previousSibling?.textContent).toBe("0");
  });

  it("renders the labels and memory tabs", async () => {
    mockFetch.mockResolvedValue(okResponse({ connected: false }));
    render(<GmailIntegrationPage />);

    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /labels/i }));
    expect(screen.getByRole("heading", { name: "Gmail Labels" })).toBeInTheDocument();
    expect(screen.getByText("Promotions")).toBeInTheDocument();
    expect(screen.getByText("1,234 emails")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /memory/i }));
    expect(screen.getByRole("heading", { name: /Gmail Memory/ })).toBeInTheDocument();
    expect(screen.getByText("Semantic Search")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sync memory now/i })).toBeInTheDocument();
  });

  it("renders the OAuth connect button in settings", async () => {
    mockFetch.mockResolvedValue(okResponse({ connected: false }));
    render(<GmailIntegrationPage />);

    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /settings/i }));
    expect(screen.getByRole("heading", { name: "Gmail Settings" })).toBeInTheDocument();
    expect(screen.getByText("Disconnected")).toBeInTheDocument();
    // OAuth flow is started by a hardcoded redirect; the button must be wired
    expect(
      screen.getByRole("button", { name: /connect gmail account/i })
    ).toBeInTheDocument();
    expect(() =>
      fireEvent.click(screen.getByRole("button", { name: /connect gmail account/i }))
    ).not.toThrow();
  });

  it("opens Gmail in a new tab from the overview", async () => {
    mockFetch.mockResolvedValue(okResponse({ connected: false }));
    render(<GmailIntegrationPage />);

    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /open gmail/i }));
    expect(openSpy).toHaveBeenCalledWith("https://mail.google.com", "_blank");
  });

  it("navigates back to the integrations hub", async () => {
    mockFetch.mockResolvedValue(okResponse({ connected: false }));
    render(<GmailIntegrationPage />);

    fireEvent.click(screen.getByRole("button", { name: /back to integrations/i }));
    expect(mockPush).toHaveBeenCalledWith("/integrations");
  });
});
