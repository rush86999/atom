import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import Home from "@/pages/index";
import { useRouter } from "next/router";
import { useToast } from "@/components/ui/use-toast";

jest.mock("next/router", () => ({
  useRouter: jest.fn(() => ({
    route: "/",
    pathname: "/",
    query: {},
    asPath: "/",
    isReady: true,
    push: jest.fn(() => Promise.resolve(true)),
    replace: jest.fn(() => Promise.resolve(true)),
    back: jest.fn(),
  })),
}));

jest.mock("@/components/ui/use-toast", () => ({
  useToast: jest.fn(() => ({ toast: jest.fn() })),
}));

const mockToast = jest.fn();
const mockPush = jest.fn(() => Promise.resolve(true));
const mockReplace = jest.fn(() => Promise.resolve(true));

const okResponse = (body: any) => ({
  ok: true,
  status: 200,
  json: async () => body,
});
const badResponse = (status = 401) => ({
  ok: false,
  status,
  json: async () => ({}),
});

const FEED = {
  data: {
    recent_executions: [
      {
        id: "e1",
        agent_id: "a1",
        agent_name: "Sales Intel",
        status: "completed",
        input_summary: "Analyze Q2 pipeline",
        started_at: null,
        duration_seconds: 12,
      },
      {
        id: "e2",
        agent_id: "a2",
        agent_name: "CS Bot",
        status: "failed",
        input_summary: "Draft response",
        started_at: null,
        duration_seconds: 3,
      },
    ],
    recent_canvases: [],
    last_chat_session: { id: "s1", title: "Q3 planning", updated_at: null },
    agents_progress: [
      {
        id: "a1",
        name: "Sales Intel",
        current_tier: "SUPERVISED",
        next_tier: "AUTONOMOUS",
        next_threshold_episodes: 50,
      },
      {
        id: "a2",
        name: "CS Bot",
        current_tier: "AUTONOMOUS",
        next_tier: null,
        next_threshold_episodes: null,
      },
    ],
  },
};

const mockFetch = jest.fn();
const storageStore: Record<string, string> = {};

describe("Home landing page (pages/index.tsx)", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    for (const key of Object.keys(storageStore)) delete storageStore[key];
    localStorage.clear();
    document.cookie = "auth_token=; Max-Age=0; path=/";
    document.cookie = "next-auth.session-token=; Max-Age=0; path=/";
    jest.spyOn(Storage.prototype, "getItem").mockImplementation((key: string) => storageStore[key] ?? null);
    jest.spyOn(Storage.prototype, "setItem").mockImplementation((key: string, value: string) => {
      storageStore[key] = value;
    });
    jest.spyOn(Storage.prototype, "removeItem").mockImplementation((key: string) => {
      delete storageStore[key];
    });
    (useRouter as jest.Mock).mockReturnValue({
      route: "/",
      pathname: "/",
      query: {},
      asPath: "/",
      isReady: true,
      push: mockPush,
      replace: mockReplace,
      back: jest.fn(),
    });
    (useToast as jest.Mock).mockReturnValue({ toast: mockToast });
    mockFetch.mockImplementation((url: string, opts?: any) => {
      if (url === "/api/dev/bootstrap-session") {
        return Promise.resolve(okResponse({ access_token: "dev-token" }));
      }
      if (url.includes("/api/onboarding/status")) {
        return Promise.resolve(okResponse({ onboarding_completed: true }));
      }
      if (url.includes("/api/users/me")) {
        return Promise.resolve(okResponse({ first_name: "Ada", specialty: "Ops" }));
      }
      if (url.includes("/api/dashboard/feed")) {
        return Promise.resolve(okResponse(FEED));
      }
      return Promise.resolve(okResponse({}));
    });
    global.fetch = mockFetch as any;
  });

  it("redirects to /dashboard when an auth token already exists", async () => {
    storageStore["token"] = "test-token";

    render(<Home />);

    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/dashboard"));
    expect(mockFetch).not.toHaveBeenCalledWith(
      "/api/dev/bootstrap-session",
      expect.anything()
    );
  });

  it("redirects to /login after an explicit logout", async () => {
    storageStore["atom_explicit_logout"] = "1";

    render(<Home />);

    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/login"));
    expect(mockFetch).not.toHaveBeenCalledWith(
      "/api/dev/bootstrap-session",
      expect.anything()
    );
  });

  it("bootstraps a dev session on localhost when unauthenticated", async () => {
    render(<Home />);

    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/dashboard"));
    expect(mockFetch).toHaveBeenCalledWith("/api/dev/bootstrap-session");
    expect(storageStore["auth_token"]).toBe("dev-token");
    expect(storageStore["atom_explicit_logout"]).toBeUndefined();
    expect(document.cookie).toContain("auth_token=dev-token");
    expect(document.cookie).toContain("next-auth.session-token=dev-token");
  });

  it("does not bootstrap or redirect when the dev bootstrap endpoint fails", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/dev/bootstrap-session") return Promise.resolve(badResponse(404));
      return Promise.resolve(okResponse({}));
    });

    render(<Home />);

    await waitFor(() => expect(mockFetch).toHaveBeenCalledWith("/api/dev/bootstrap-session"));
    expect(mockReplace).not.toHaveBeenCalled();
    expect(storageStore["auth_token"]).toBeUndefined();
    expect(screen.getByText("Welcome to ATOM")).toBeInTheDocument();
  });

  it("logs and stays put when the dev bootstrap request throws", async () => {
    const consoleErrorSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/dev/bootstrap-session") return Promise.reject(new Error("boom"));
      return Promise.resolve(okResponse({}));
    });

    render(<Home />);

    await waitFor(() => expect(mockReplace).not.toHaveBeenCalled());
    expect(storageStore["auth_token"]).toBeUndefined();
    expect(screen.getByText("Welcome to ATOM")).toBeInTheDocument();
    expect(consoleErrorSpy).toHaveBeenCalled();
    consoleErrorSpy.mockRestore();
  });

  it("survives an onboarding status request failure without opening the wizard", async () => {
    storageStore["token"] = "test-token";
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/dev/bootstrap-session") return Promise.resolve(badResponse(404));
      if (url.includes("/api/onboarding/status")) {
        return Promise.reject(new Error("boom"));
      }
      return Promise.resolve(okResponse({}));
    });

    render(<Home />);

    await waitFor(() => expect(screen.getByText("Welcome to ATOM")).toBeInTheDocument());
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("opens the onboarding wizard when onboarding is incomplete and greets the user", async () => {
    storageStore["token"] = "test-token";
    mockFetch.mockImplementation((url: string, opts?: any) => {
      if (url === "/api/dev/bootstrap-session") return Promise.resolve(badResponse(404));
      if (url.includes("/api/onboarding/status")) {
        return Promise.resolve(okResponse({ onboarding_completed: false }));
      }
      if (url.includes("/api/users/me")) {
        return Promise.resolve(okResponse({ first_name: "Ada", specialty: "Ops" }));
      }
      if (url.includes("/api/dashboard/feed")) {
        return Promise.resolve(okResponse({ data: FEED.data }));
      }
      return Promise.resolve(okResponse({}));
    });

    render(<Home />);

    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    expect(screen.getByText("Hello, Ada!")).toBeInTheDocument();
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/onboarding/status"),
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
      })
    );
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/users/me"),
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
      })
    );
  });

  it("does not open the wizard when onboarding is completed", async () => {
    storageStore["token"] = "test-token";

    render(<Home />);

    await waitFor(() => expect(screen.getByText("Welcome to ATOM")).toBeInTheDocument());
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes the wizard when onboarding is completed through the flow", async () => {
    storageStore["token"] = "test-token";
    mockFetch.mockImplementation((url: string, opts?: any) => {
      if (url === "/api/dev/bootstrap-session") return Promise.resolve(badResponse(404));
      if (url.includes("/api/onboarding/status")) {
        return Promise.resolve(okResponse({ onboarding_completed: false }));
      }
      if (url.includes("/api/onboarding/update")) {
        return Promise.resolve(okResponse({ success: true }));
      }
      return Promise.resolve(okResponse({}));
    });

    render(<Home />);
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /next/i })); // step 1
    fireEvent.click(screen.getByRole("button", { name: /next/i })); // step 2
    fireEvent.click(screen.getByRole("button", { name: /next/i })); // step 3

    expect(screen.getByText("You're Ready!")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /start automating/i }));

    await waitFor(() =>
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/onboarding/update"),
        expect.objectContaining({ method: "POST" })
      )
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: "You're all set!" })
    );
  });

  it("renders the activity feed and navigates to the last chat session", async () => {
    storageStore["token"] = "test-token";

    render(<Home />);

    expect(await screen.findByText("Pick up where you left off")).toBeInTheDocument();
    expect(screen.getByText("Q3 planning")).toBeInTheDocument();
    expect(screen.getByText("Continue this conversation →")).toBeInTheDocument();

    // Recent executions with status chips
    expect(screen.getByText("Recent activity")).toBeInTheDocument();
    expect(screen.getAllByText("Sales Intel").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Analyze Q2 pipeline/)).toBeInTheDocument();
    expect(screen.getByText("failed")).toBeInTheDocument();

    // Agent progress
    expect(screen.getByText("Your agents' progress")).toBeInTheDocument();
    expect(screen.getByText(/50 eps → AUTONOMOUS/)).toBeInTheDocument();
    expect(screen.getByText("max tier")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Q3 planning"));
    expect(mockPush).toHaveBeenCalledWith("/chat?session=s1");
  });

  it("shows a formatted update time when the last chat session has updated_at", async () => {
    storageStore["token"] = "test-token";
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/dev/bootstrap-session") return Promise.resolve(badResponse(404));
      if (url.includes("/api/onboarding/status")) {
        return Promise.resolve(okResponse({ onboarding_completed: true }));
      }
      if (url.includes("/api/dashboard/feed")) {
        return Promise.resolve(
          okResponse({
            data: {
              recent_executions: [],
              recent_canvases: [],
              last_chat_session: { id: "s1", title: "Q3 planning", updated_at: "2026-08-01T12:00:00Z" },
              agents_progress: [],
            },
          })
        );
      }
      return Promise.resolve(okResponse({}));
    });

    render(<Home />);

    expect(await screen.findByText("Pick up where you left off")).toBeInTheDocument();
    expect(screen.getByText("No agent runs yet.")).toBeInTheDocument();
    expect(screen.getByText(/Updated /)).toBeInTheDocument();
  });

  it("falls back to the static feature grid when there is no activity feed", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url === "/api/dev/bootstrap-session") return Promise.resolve(badResponse(404));
      if (url.includes("/api/onboarding/status")) {
        return Promise.resolve(okResponse({ onboarding_completed: true }));
      }
      if (url.includes("/api/dashboard/feed")) {
        return Promise.resolve(
          okResponse({
            data: { recent_executions: [], recent_canvases: [], last_chat_session: null, agents_progress: [] },
          })
        );
      }
      return Promise.resolve(okResponse({}));
    });

    render(<Home />);

    await waitFor(() => expect(screen.getByText("Welcome to ATOM")).toBeInTheDocument());
    expect(screen.getByText("Your AI-powered personal automation platform")).toBeInTheDocument();
    expect(screen.queryByText("Pick up where you left off")).not.toBeInTheDocument();
    expect(screen.queryByText("Recent activity")).not.toBeInTheDocument();

    // Feature cards navigate
    fireEvent.click(screen.getByText("Search"));
    expect(mockPush).toHaveBeenCalledWith("/search");

    fireEvent.click(screen.getByRole("button", { name: /get started with automation/i }));
    expect(mockPush).toHaveBeenCalledWith("/automations");
  });

  it("still renders the static grid when the feed request fails", async () => {
    storageStore["token"] = "test-token";
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/dashboard/feed")) {
        return Promise.reject(new Error("network down"));
      }
      return Promise.resolve(okResponse({}));
    });

    render(<Home />);

    await waitFor(() => expect(screen.getByText("Welcome to ATOM")).toBeInTheDocument());
    expect(screen.getByText("AI-powered search across all your documents, meetings, and notes"))
      .toBeInTheDocument();
  });
});
