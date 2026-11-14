import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SessionSettings from "@/pages/settings/sessions";
import { useRouter } from "next/router";
import { signOut } from "next-auth/react";

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

jest.mock("next-auth/react", () => ({
  signOut: jest.fn(() => Promise.resolve(undefined)),
}));

const mockPush = jest.fn();
const mockSignOut = signOut as unknown as jest.Mock;

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
      revocable: true,
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
      revocable: true,
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
    mockFetch.mockImplementation((url: string, init?: any) => {
      if (init?.method === "POST") {
        return Promise.resolve(okResponse({ tracked: true, registered: false, is_current: true }));
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

  it("sends a bodyless heartbeat and renders the session list", async () => {
    render(<SessionSettings />);

    await waitFor(() => {
      expect(screen.getByText("Chrome on macOS")).toBeInTheDocument();
    });

    const heartbeat = mockFetch.mock.calls.find(([, init]) => init?.method === "POST");
    expect(heartbeat).toBeDefined();
    // WA-075: no client-supplied token may be recorded or later revoked.
    expect(heartbeat?.[1]?.body).toBeUndefined();

    expect(screen.getByText("Current Device")).toBeInTheDocument();
    expect(screen.getByText("192.168.1.10")).toBeInTheDocument();
    expect(screen.getByText("Safari on iOS")).toBeInTheDocument();
    expect(screen.getByText("203.0.113.7")).toBeInTheDocument();

    expect(screen.getByRole("button", { name: /revoke/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign out everywhere/i })).toBeInTheDocument();
  });

  it("shows the untracked-session notice from the heartbeat", async () => {
    mockFetch.mockImplementation((url: string, init?: any) => {
      if (init?.method === "POST") {
        return Promise.resolve(
          okResponse({
            tracked: false,
            registered: false,
            is_current: false,
            message: "This session is not in the device inventory.",
          }),
        );
      }
      return Promise.resolve(okResponse(SESSIONS));
    });

    render(<SessionSettings />);

    await waitFor(() => {
      expect(screen.getByText("This session is not in the device inventory.")).toBeInTheDocument();
    });
  });

  it("shows the empty state when there are no sessions", async () => {
    mockFetch.mockImplementation((url: string, init?: any) =>
      Promise.resolve(init?.method === "POST" ? okResponse({ tracked: true }) : okResponse({ sessions: [] })),
    );

    render(<SessionSettings />);

    await waitFor(() => {
      expect(screen.getByText("No active sessions found.")).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: /sign out everywhere/i })).not.toBeInTheDocument();
  });

  it("shows the backend message when the session fetch fails", async () => {
    mockFetch.mockImplementation((url: string, init?: any) =>
      Promise.resolve(
        init?.method === "POST"
          ? okResponse({ tracked: true })
          : errResponse(401, { message: "Backend session unavailable" }),
      ),
    );

    render(<SessionSettings />);

    await waitFor(() => {
      expect(screen.getByText("Backend session unavailable")).toBeInTheDocument();
    });
  });

  it("does not offer a revoke control for an unverifiable entry", async () => {
    mockFetch.mockImplementation((url: string, init?: any) => {
      if (init?.method === "POST") return Promise.resolve(okResponse({ tracked: true }));
      return Promise.resolve(
        okResponse({
          sessions: [
            SESSIONS.sessions[0],
            { ...SESSIONS.sessions[1], id: "legacy", revocable: false },
          ],
        }),
      );
    });

    render(<SessionSettings />);

    await waitFor(() => expect(screen.getByText("Safari on iOS")).toBeInTheDocument());
    expect(screen.getByText("Cannot be revoked")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /revoke/i })).toBeDisabled();
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
        }),
      );
    });
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining("revoke this session"));
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
        expect.objectContaining({ method: "DELETE" }),
      );
    });
  });

  it("surfaces the backend reason when a revocation is refused", async () => {
    const confirmSpy = jest.spyOn(window, "confirm").mockReturnValue(true);
    mockFetch.mockImplementation((url: string, init?: any) => {
      if (init?.method === "DELETE") {
        return Promise.resolve(
          errResponse(409, { message: "This entry could not be tied to a revocable token." }),
        );
      }
      return Promise.resolve(okResponse(SESSIONS));
    });

    render(<SessionSettings />);
    await waitFor(() => expect(screen.getByText("Chrome on macOS")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /revoke/i }));

    await waitFor(() => {
      expect(
        screen.getByText("This entry could not be tied to a revocable token."),
      ).toBeInTheDocument();
    });
    expect(confirmSpy).toHaveBeenCalled();
  });

  it("signs out everywhere with the NextAuth signOut event, not the signout page", async () => {
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
        }),
      );
      expect(mockSignOut).toHaveBeenCalledWith({ callbackUrl: "/auth/signin" });
    });
    expect(mockPush).not.toHaveBeenCalledWith("/api/auth/signout");
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining("sign out of all devices"));
  });

  it("keeps the user on the page when revoke-all fails", async () => {
    jest.spyOn(window, "confirm").mockReturnValue(true);
    mockFetch.mockImplementation((url: string, init?: any) => {
      if (init?.method === "DELETE") {
        return Promise.resolve(errResponse(503, { message: "Revocation could not be confirmed." }));
      }
      return Promise.resolve(okResponse(SESSIONS));
    });

    render(<SessionSettings />);
    await waitFor(() => expect(screen.getByText("Chrome on macOS")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /sign out everywhere/i }));

    await waitFor(() => {
      expect(screen.getByText("Revocation could not be confirmed.")).toBeInTheDocument();
    });
    expect(mockSignOut).not.toHaveBeenCalled();
    expect(mockPush).not.toHaveBeenCalledWith("/api/auth/signout");
  });
});
