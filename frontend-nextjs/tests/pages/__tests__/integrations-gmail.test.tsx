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


// Wrap the real GmailSearch with a trigger button so the page's onSearch
// callbacks can be exercised (the real component never calls onSearch).
jest.mock("@/components/GmailSearch", () => {
  const React = require("react");
  const real = jest.requireActual("@/components/GmailSearch").default;
  return {
    __esModule: true,
    default: (props: any) => (
      <div>
        {React.createElement(real, props)}
        <button
          data-testid="trigger-on-search"
          onClick={() => props.onSearch([1], { filter: true }, { sort: "asc" })}
        >
          Trigger Search
        </button>
      </div>
    ),
  };
});

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
const vc: any = (window as any)._virtualConsole;
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
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/integrations/gmail/status",
      expect.anything(),
    );
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

// ---------------------------------------------------------------------------
// Extended coverage: connection error, all tabs, quick actions, onSearch
// ---------------------------------------------------------------------------
describe("GmailIntegrationPage (extended coverage)", () => {
  const mockFetch = jest.fn();
  let consoleSpy: jest.SpyInstance;
  let logSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    logSpy = jest.spyOn(console, "log").mockImplementation(() => {});
    global.fetch = mockFetch;
    mockFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, status: 200, json: async () => ({ connected: true }) }),
    );
  });

  afterEach(() => {
    consoleSpy.mockRestore();
    logSpy.mockRestore();
  });

  const settled = async () => {
    render(<GmailIntegrationPage />);
    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });
  };

  it("falls back to disconnected when the status fetch rejects", async () => {
    mockFetch.mockImplementation(() => Promise.reject(new Error("offline")));
    render(<GmailIntegrationPage />);
    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeInTheDocument();
    });
    expect(consoleSpy).toHaveBeenCalledWith(
      "Failed to check Gmail connection:",
      expect.any(Error),
    );
  });

  it("visits every tab from the tab bar", async () => {
    await settled();

    const tabNames = [
      ["📊 Overview", /Gmail Integration Overview/i],
      ["📥 Inbox", /Gmail Inbox/i],
      ["📅 Calendar", /Google Calendar/i],
      ["👥 Contacts", /Google Contacts/i],
      ["✅ Tasks", /Google Tasks/i],
      ["✏️ Compose", /Compose Email/i],
      ["🏷️ Labels", /Gmail Labels/i],
      ["🧠 Memory", /Gmail Memory \(LanceDB\)/i],
      ["⚙️ Settings", /Gmail Settings/i],
    ] as const;

    for (const [tab, heading] of tabNames) {
      fireEvent.click(screen.getByRole("button", { name: new RegExp(tab) }));
      expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
    }
  });

  it("navigates via the remaining quick action buttons", async () => {
    await settled();

    const openSpy = jest.fn();
    window.open = openSpy as any;

    const backToOverview = () =>
      fireEvent.click(screen.getByRole("button", { name: /📊 Overview/i }));

    fireEvent.click(screen.getByRole("button", { name: /Compose Email/i }));
    expect(screen.getByRole("heading", { name: /Compose Email/i })).toBeInTheDocument();
    backToOverview();

    fireEvent.click(screen.getByRole("button", { name: /Manage Contacts/i }));
    expect(screen.getByRole("heading", { name: /Google Contacts/i })).toBeInTheDocument();
    backToOverview();

    fireEvent.click(screen.getByRole("button", { name: /View Tasks/i }));
    expect(screen.getByRole("heading", { name: /Google Tasks/i })).toBeInTheDocument();
    backToOverview();

    fireEvent.click(screen.getByRole("button", { name: /View Calendar/i }));
    expect(screen.getByRole("heading", { name: /Google Calendar/i })).toBeInTheDocument();
    backToOverview();

    fireEvent.click(screen.getByRole("button", { name: /Open Gmail/i }));
    expect(openSpy).toHaveBeenCalledWith("https://mail.google.com", "_blank");
  });

  it("sets search results from the inbox and contacts onSearch callbacks", async () => {
    await settled();

    fireEvent.click(screen.getByRole("button", { name: /📥 Inbox/i }));
    fireEvent.click(screen.getByTestId("trigger-on-search"));
    // onSearch([1], ...) now setEmails([1]) — GmailSearch reflects it
    expect(screen.getByText("Showing 1 of 1 items")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /👥 Contacts/i }));
    fireEvent.click(screen.getByTestId("trigger-on-search"));
    expect(screen.getByText("Showing 1 of 1 items")).toBeInTheDocument();
  });

  it("renders static content on the labels and memory tabs", async () => {
    await settled();

    fireEvent.click(screen.getByRole("button", { name: /🏷️ Labels/i }));
    expect(
      screen.getByRole("heading", { name: /Gmail Labels/i }),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /🧠 Memory/i }));
    expect(
      screen.getByRole("heading", { name: /Gmail Memory/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("Memory Search")).toBeInTheDocument();
    expect(screen.getByText("Memory Features")).toBeInTheDocument();
  });

  it("renders the compose form fields and buttons", async () => {
    await settled();

    fireEvent.click(screen.getByRole("button", { name: /✏️ Compose/i }));
    expect(screen.getByPlaceholderText("recipient@example.com")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Email subject")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Write your email message here..."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Send Email/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Save Draft/i })).toBeInTheDocument();
  });

  it("renders calendar and tasks controls", async () => {
    await settled();

    fireEvent.click(screen.getByRole("button", { name: /📅 Calendar/i }));
    expect(screen.getByPlaceholderText("Search events...")).toBeInTheDocument();
    expect(screen.getByText("Upcoming")).toBeInTheDocument();
    expect(screen.getByRole("combobox")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /✅ Tasks/i }));
    expect(screen.getByPlaceholderText("Search tasks...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Add Task/i })).toBeInTheDocument();
    expect(screen.getByText("Due Today")).toBeInTheDocument();
  });
});
