import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SessionSettings from "@/pages/settings/sessions";
import { useRouter } from "next/router";

jest.mock("next/router", () => ({
  useRouter: jest.fn(() => ({
    route: "/settings/sessions",
    pathname: "/settings/sessions",
    query: {},
    asPath: "/settings/sessions",
    push: jest.fn(() => Promise.resolve(true)),
    replace: jest.fn(() => Promise.resolve(true)),
    back: jest.fn(),
  })),
}));

const mockPush = jest.fn();

const SESSIONS = {
  sessions: [
    {
      id: "sess-current",
      device_type: "desktop",
      browser: "Chrome",
      os: "macOS",
      ip_address: "192.168.1.10",
      last_active_at: "2026-08-08T09:00:00Z",
      created_at: "2026-08-01T09:00:00Z",
      is_active: true,
      is_current: true,
    },
    {
      id: "sess-phone",
      device_type: "mobile",
      browser: "Safari",
      os: "iOS",
      ip_address: "203.0.113.7",
      last_active_at: "2026-08-07T18:30:00Z",
      created_at: "2026-08-02T09:00:00Z",
      is_active: true,
      is_current: false,
    },
  ],
};

const okResponse = (body: any) => ({ ok: true, status: 200, json: async () => body });
const errResponse = (status: number, body: any) => ({
  ok: false,
  status,
  json: async () => body,
});

describe("SessionSettings", () => {
  const mockFetch = jest.fn();
  let getItemSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    getItemSpy = jest.spyOn(Storage.prototype, "getItem").mockReturnValue("test-token");
    (useRouter as jest.Mock).mockReturnValue({
      route: "/settings/sessions",
      pathname: "/settings/sessions",
      query: {},
      asPath: "/settings/sessions",
      push: mockPush,
      replace: jest.fn(() => Promise.resolve(true)),
      back: jest.fn(),
    });
    global.fetch = mockFetch;
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/auth/sessions") && url !== "/api/auth/sessions") {
        return Promise.resolve(okResponse(SESSIONS));
      }
      return Promise.resolve(okResponse(SESSIONS));
    });
  });

  it("redirects to /login when no auth token exists", async () => {
    getItemSpy.mockReturnValue(null);

    render(<SessionSettings />);

    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/login");
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("shows the loading spinner while sessions are fetched", () => {
    mockFetch.mockReturnValue(new Promise(() => {}));
    render(<SessionSettings />);
    expect(document.querySelector(".animate-spin")).not.toBeNull();
  });

  it("records the current session and renders the session list", async () => {
    render(<SessionSettings />);

    await waitFor(() => {
      expect(screen.getByText("Chrome on macOS")).toBeInTheDocument();
    });

    // Current session is recorded on mount. R82: the page sends the real
    // backend JWT (the old shared 'current-session-token' placeholder
    // collided all users onto one upsert row).
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/auth/sessions",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ token: "test-token" }),
      })
    );

    expect(screen.getByText("Current Device")).toBeInTheDocument();
    expect(screen.getByText("192.168.1.10")).toBeInTheDocument();
    expect(screen.getByText("Safari on iOS")).toBeInTheDocument();
    expect(screen.getByText("203.0.113.7")).toBeInTheDocument();

    // Revoke button only for non-current sessions
    expect(screen.getByRole("button", { name: /revoke/i })).toBeInTheDocument();
    // Multiple sessions -> Sign Out Everywhere available
    expect(screen.getByRole("button", { name: /sign out everywhere/i })).toBeInTheDocument();
  });

  it("shows the empty state when there are no sessions", async () => {
    mockFetch.mockImplementation((url: string) =>
      Promise.resolve(okResponse({ sessions: [] }))
    );

    render(<SessionSettings />);

    await waitFor(() => {
      expect(screen.getByText("No active sessions found.")).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: /sign out everywhere/i })).not.toBeInTheDocument();
  });

  it("shows an error alert when the session fetch fails", async () => {
    mockFetch.mockImplementation((url: string) =>
      Promise.resolve(errResponse(500, {}))
    );

    render(<SessionSettings />);

    await waitFor(() => {
      expect(screen.getByText("Failed to fetch sessions")).toBeInTheDocument();
    });
  });

  it("revokes a single session after confirmation and refetches", async () => {
    const confirmSpy = jest.spyOn(window, "confirm").mockReturnValue(true);
    render(<SessionSettings />);
    await waitFor(() => expect(screen.getByText("Chrome on macOS")).toBeInTheDocument());

    const callsBefore = mockFetch.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: /revoke/i }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/auth/sessions",
        expect.objectContaining({
          method: "DELETE",
          body: JSON.stringify({ sessionId: "sess-phone" }),
        })
      );
    });
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining("revoke this session"));
    // Sessions refetched after revoke
    expect(mockFetch.mock.calls.length).toBeGreaterThan(callsBefore);
  });

  it("does not revoke when the confirmation is cancelled", async () => {
    jest.spyOn(window, "confirm").mockReturnValue(false);
    render(<SessionSettings />);
    await waitFor(() => expect(screen.getByText("Chrome on macOS")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /revoke/i }));

    await waitFor(() => {
      expect(mockFetch).not.toHaveBeenCalledWith(
        "/api/auth/sessions",
        expect.objectContaining({ method: "DELETE" })
      );
    });
  });

  it("shows an error alert when revoking a session fails", async () => {
    jest.spyOn(window, "confirm").mockReturnValue(true);
    mockFetch.mockImplementation((url: string) => {
      if ((mockFetch as any)._deleteMode === true) {
        return Promise.resolve(errResponse(500, {}));
      }
      return Promise.resolve(okResponse(SESSIONS));
    });

    render(<SessionSettings />);
    await waitFor(() => expect(screen.getByText("Chrome on macOS")).toBeInTheDocument());

    (mockFetch as any)._deleteMode = true;
    fireEvent.click(screen.getByRole("button", { name: /revoke/i }));

    await waitFor(() => {
      expect(screen.getByText("Failed to revoke session")).toBeInTheDocument();
    });
  });

  it("signs out everywhere: revokes all and redirects to the signout endpoint", async () => {
    const confirmSpy = jest.spyOn(window, "confirm").mockReturnValue(true);
    render(<SessionSettings />);
    await waitFor(() => expect(screen.getByText("Chrome on macOS")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /sign out everywhere/i }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/auth/sessions",
        expect.objectContaining({
          method: "DELETE",
          body: JSON.stringify({ revokeAll: true }),
        })
      );
      expect(mockPush).toHaveBeenCalledWith("/api/auth/signout");
    });
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining("sign out of all devices"));
  });

  it("keeps the user on the page when revoke-all fails", async () => {
    jest.spyOn(window, "confirm").mockReturnValue(true);
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/auth/sessions") && (mockFetch as any)._revokeAllMode === true) {
        return Promise.resolve(errResponse(500, {}));
      }
      return Promise.resolve(okResponse(SESSIONS));
    });

    render(<SessionSettings />);
    await waitFor(() => expect(screen.getByText("Chrome on macOS")).toBeInTheDocument());

    (mockFetch as any)._revokeAllMode = true;
    fireEvent.click(screen.getByRole("button", { name: /sign out everywhere/i }));

    await waitFor(() => {
      // Page surfaces the thrown error message ('Failed to revoke all sessions')
      expect(screen.getByText("Failed to revoke all sessions")).toBeInTheDocument();
    });
    expect(mockPush).not.toHaveBeenCalledWith("/api/auth/signout");
  });
});
