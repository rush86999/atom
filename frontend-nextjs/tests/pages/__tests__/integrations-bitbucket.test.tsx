import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import BitbucketIntegrationPage from "@/pages/integrations/bitbucket";
import { useRouter } from "next/router";

jest.mock("next/router", () => ({
  useRouter: jest.fn(() => ({
    route: "/integrations/bitbucket",
    pathname: "/integrations/bitbucket",
    query: {},
    asPath: "/integrations/bitbucket",
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
const vc = (window as any)._virtualConsole;
if (vc && vc.on) {
  vc.on("jsdomError", (error: any) => {
    const message = String(error && (error.message || error));
    if (message.includes("Not implemented: navigation")) {
      navigationErrors.push(message);
    }
  });
}

const TOKEN = "bb-token-123";

const WORKSPACES = [
  {
    slug: "acme",
    name: "Acme Corp",
    type: "Team",
    created_on: "2024-01-01T00:00:00Z",
  },
  {
    slug: "globex",
    name: "Globex Industries",
    type: "Company",
    created_on: "2023-06-15T00:00:00Z",
  },
];

const REPOSITORIES = [
  {
    name: "atom-core",
    description: "Main platform repository",
    language: "Python",
    size: 2048,
    workspace: { slug: "acme" },
    updated_on: "2025-01-01T00:00:00Z",
  },
];

const PULL_REQUESTS = [
  {
    id: 42,
    title: "Add sandbox layer",
    state: "OPEN",
    source: { branch: { name: "feat/sandbox" } },
    destination: { branch: { name: "main" } },
    author: { display_name: "Rushi Parikh" },
    created_on: "2025-02-01T00:00:00Z",
    updated_on: "2025-02-02T00:00:00Z",
  },
];

const PIPELINES = [
  {
    build_number: 8,
    state: { name: "IN_PROGRESS" },
    repository: { name: "atom-core" },
    trigger: { name: "commit" },
    created_on: "2025-03-02T00:00:00Z",
    build_seconds_used: 15,
    target: { commit: { hash: "deadbeefcafe" } },
  },
];

const ISSUES = [
  {
    title: "Bug: auth race condition",
    state: "open",
    kind: "bug",
    priority: "high",
    reporter: { display_name: "Rushi Parikh" },
    content: { raw: "Two logins race on refresh token" },
    created_on: "2025-03-01T00:00:00Z",
  },
];

describe("BitbucketIntegrationPage", () => {
  const mockFetch = jest.fn();
  const mockPush = jest.fn();
  let getItemSpy: jest.SpyInstance;
  let removeItemSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    global.fetch = mockFetch;
    (useRouter as jest.Mock).mockReturnValue({
      push: mockPush,
      replace: jest.fn(),
      prefetch: jest.fn(),
      back: jest.fn(),
    });
    getItemSpy = jest.spyOn(Storage.prototype, "getItem");
    removeItemSpy = jest.spyOn(Storage.prototype, "removeItem");
    getItemSpy.mockReturnValue(null);
  });

  it("shows Disconnected when no access token is stored", async () => {
    render(<BitbucketIntegrationPage />);
    // The status check is async now, so the badge lands after first paint.
    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeInTheDocument();
    });
    // The page always consults the real connection-status endpoint, but
    // without a stored token it must not send an Authorization header.
    // (The ingestion panel makes its own unrelated call on top.)
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/integrations/connection-status",
      expect.objectContaining({ headers: {} }),
    );
  });

  it("shows Disconnected when the status endpoint fails and no token is stored", async () => {
    getItemSpy.mockReturnValue(null);
    mockFetch.mockImplementation(() =>
      Promise.resolve(errResponse(500)),
    );
    render(<BitbucketIntegrationPage />);
    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeInTheDocument();
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/integrations/connection-status",
      expect.objectContaining({ headers: {} }),
    );
  });

  it("connects, loads all datasets, and renders overview stats", async () => {
    getItemSpy.mockReturnValue(TOKEN);
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/connection-status")) {
        return Promise.resolve(
          okResponse({ providers: { bitbucket: { connected: true, source: "oauth_token" } } }),
        );
      }
      if (url.includes("/workspaces")) {
        return Promise.resolve(okResponse({ workspaces: WORKSPACES }));
      }
      if (url.includes("/repositories")) {
        return Promise.resolve(okResponse({ repositories: REPOSITORIES }));
      }
      if (url.includes("/pull-requests")) {
        return Promise.resolve(okResponse({ pull_requests: PULL_REQUESTS }));
      }
      if (url.includes("/pipelines")) {
        return Promise.resolve(okResponse({ pipelines: PIPELINES }));
      }
      if (url.includes("/issues")) {
        return Promise.resolve(okResponse({ issues: ISSUES }));
      }
      return Promise.resolve(errResponse(404));
    });

    render(<BitbucketIntegrationPage />);
    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });

    const stats = screen
      .getAllByText(/^(2|1)$/)
      .map((el) => el.textContent);
    expect(stats).toContain("2"); // workspaces
    expect(stats).toContain("1"); // repositories / PRs / pipelines / issues
    expect(screen.getByText("atom-core")).toBeInTheDocument();
    expect(screen.getByText("Add sandbox layer")).toBeInTheDocument();
    expect(screen.getByText("Open PRs")).toBeInTheDocument();
    expect(screen.getByText("Running Pipelines")).toBeInTheDocument();
    expect(screen.getByText("Open Issues")).toBeInTheDocument();
  });

  it("switches to the repositories tab via quick actions", async () => {
    getItemSpy.mockReturnValue(TOKEN);
    mockFetch.mockImplementation((url: string) =>
      url.includes("/connection-status")
        ? Promise.resolve(
            okResponse({ providers: { bitbucket: { connected: true, source: "oauth_token" } } }),
          )
        : Promise.resolve(okResponse({})),
    );
    render(<BitbucketIntegrationPage />);
    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });

    fireEvent.click(
      screen.getByRole("button", { name: /Browse Repositories/i }),
    );
    expect(
      screen.getByRole("heading", { name: /Bitbucket Repositories/i }),
    ).toBeInTheDocument();
  });

  it("starts the OAuth connect flow from the settings tab", async () => {
    getItemSpy.mockReturnValue(null);
    mockFetch.mockImplementation((url: string) =>
      url.includes("/connection-status")
        ? Promise.resolve(errResponse(500))
        : url.includes("/authorize")
          ? Promise.resolve(
              okResponse({ authorization_url: "https://auth.example.com/start" }),
            )
          : Promise.resolve(okResponse({})),
    );
    navigationErrors.length = 0;

    render(<BitbucketIntegrationPage />);
    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /⚙️ Settings/i }));
    fireEvent.click(
      screen.getByRole("button", { name: /Connect Bitbucket Account/i }),
    );
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/integrations/bitbucket/authorize",
      );
    });
    await waitFor(() => {
      expect(navigationErrors).toHaveLength(1);
    });
  });

  it("disconnects from the settings tab, clearing stored tokens and data", async () => {
    getItemSpy.mockReturnValue(TOKEN);
    mockFetch.mockImplementation((url: string) =>
      url.includes("/connection-status")
        ? Promise.resolve(
            okResponse({ providers: { bitbucket: { connected: true, source: "oauth_token" } } }),
          )
        : Promise.resolve(okResponse({})),
    );

    render(<BitbucketIntegrationPage />);
    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /⚙️ Settings/i }));
    fireEvent.click(
      screen.getByRole("button", { name: /Disconnect Bitbucket/i }),
    );

    expect(removeItemSpy).toHaveBeenCalledWith("bitbucket_access_token");
    expect(removeItemSpy).toHaveBeenCalledWith("bitbucket_refresh_token");
    expect(screen.getAllByText("Disconnected").length).toBeGreaterThan(0);
    expect(
      screen.getByRole("button", { name: /Connect Bitbucket Account/i }),
    ).toBeInTheDocument();
  });

  it("renders empty datasets without crashing", async () => {
    getItemSpy.mockReturnValue(TOKEN);
    mockFetch.mockImplementation((url: string) =>
      url.includes("/connection-status")
        ? Promise.resolve(
            okResponse({ providers: { bitbucket: { connected: true, source: "oauth_token" } } }),
          )
        : Promise.resolve(okResponse({})),
    );
    render(<BitbucketIntegrationPage />);
    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });
    expect(screen.getAllByText("Workspaces").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Repositories").length).toBeGreaterThan(0);
    expect(screen.queryByText("atom-core")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Extended coverage: connection/data errors, all tabs, rich dataset rendering
// ---------------------------------------------------------------------------
describe("BitbucketIntegrationPage (extended coverage)", () => {
  const mockFetch = jest.fn();
  const mockPush = jest.fn();
  let getItemSpy: jest.SpyInstance;
  let consoleSpy: jest.SpyInstance;

  const dataHandlers = (overrides: Record<string, any> = {}) => (url: string) => {
    const map: Record<string, any> = {
      "/connection-status": okResponse({ providers: { bitbucket: { connected: true, source: "oauth_token" } } }),
      "/workspaces": okResponse({ workspaces: WORKSPACES }),
      "/repositories": okResponse({ repositories: REPOSITORIES }),
      "/pull-requests": okResponse({ pull_requests: PULL_REQUESTS }),
      "/pipelines": okResponse({ pipelines: PIPELINES }),
      "/issues": okResponse({ issues: ISSUES }),
      "/authorize": okResponse({ authorization_url: "https://auth.example.com/start" }),
    };
    for (const key of Object.keys(overrides)) {
      if (url.includes(key)) return overrides[key];
    }
    for (const key of Object.keys(map)) {
      if (url.includes(key)) return map[key];
    }
    return errResponse(404);
  };

  beforeEach(() => {
    jest.clearAllMocks();
    consoleSpy = jest.spyOn(console, "error").mockImplementation(() => {});
    global.fetch = mockFetch;
    (useRouter as jest.Mock).mockReturnValue({
      push: mockPush,
      replace: jest.fn(),
      prefetch: jest.fn(),
      back: jest.fn(),
    });
    getItemSpy = jest.spyOn(Storage.prototype, "getItem");
    getItemSpy.mockReturnValue(TOKEN);
    mockFetch.mockImplementation(dataHandlers());
  });

  afterEach(() => {
    consoleSpy.mockRestore();
    getItemSpy.mockRestore();
  });

  const connected = async () => {
    render(<BitbucketIntegrationPage />);
    // The connection check + ingestion panel update state asynchronously;
    // flush inside act() so the connected UI actually commits to the DOM.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 400));
    });
    await screen.findByText("Connected", {}, { timeout: 4000 });
    // wait for the datasets to land (recent repos render on the overview)
    await screen.findByText("atom-core", {}, { timeout: 4000 });
  };

  it("falls back to disconnected when the status fetch rejects", async () => {
    getItemSpy.mockReturnValue(null);
    mockFetch.mockImplementation(dataHandlers({ "/connection-status": Promise.reject(new Error("offline")) }));
    render(<BitbucketIntegrationPage />);
    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeInTheDocument();
    });
  });

  it("aborts data loading when a data endpoint rejects", async () => {
    mockFetch.mockImplementation(
      dataHandlers({ "/workspaces": Promise.reject(new Error("boom")) }),
    );
    render(<BitbucketIntegrationPage />);
    await act(async () => {
      await new Promise((r) => setTimeout(r, 400));
    });
    console.log("DBG_CALLS:", JSON.stringify(mockFetch.mock.calls.map((c: any) => [c[0], c[1] && JSON.stringify(c[1])])));
    console.log("DBG_ITEM:", getItemSpy.mock.results.slice(-2));
    await screen.findByText("Connected", {}, { timeout: 4000 });
    await waitFor(
      () => {
        expect(consoleSpy).toHaveBeenCalledWith(
          "Failed to load Bitbucket data:",
          expect.any(Error),
        );
      },
      { timeout: 4000 },
    );
    // the try block aborts: no repositories were loaded afterwards
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText("atom-core")).not.toBeInTheDocument();
  });

  it("logs when the OAuth authorize call rejects", async () => {
    getItemSpy.mockReturnValue(null);
    mockFetch.mockImplementation(
      dataHandlers({ "/connection-status": errResponse(500), "/authorize": Promise.reject(new Error("oauth down")) }),
    );
    navigationErrors.length = 0;
    render(<BitbucketIntegrationPage />);
    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /⚙️ Settings/i }));
    fireEvent.click(screen.getByRole("button", { name: /Connect Bitbucket Account/i }));
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        "Failed to start Bitbucket OAuth flow:",
        expect.any(Error),
      );
    });
    expect(navigationErrors).toHaveLength(0);
  });

  it("renders every tab with rich data", async () => {
    await connected();

    const tabs: [RegExp, RegExp][] = [
      [/📊 Overview/i, /Bitbucket Integration Overview/i],
      [/🏢 Workspaces/i, /Bitbucket Workspaces/i],
      [/📁 Repositories/i, /Bitbucket Repositories/i],
      [/🔄 Pull Requests/i, /Bitbucket Pull Requests/i],
      [/⚙️ Pipelines/i, /Bitbucket Pipelines/i],
      [/🐛 Issues/i, /Bitbucket Issues/i],
      [/🔍 Code Search/i, /Bitbucket Code Search/i],
    ];
    for (const [tab, heading] of tabs) {
      fireEvent.click(screen.getByRole("button", { name: tab }));
      expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
    }

    // workspace card details
    fireEvent.click(screen.getByRole("button", { name: /🏢 Workspaces/i }));
    expect(screen.getByText("Globex Industries")).toBeInTheDocument();
    expect(screen.getByText("globex")).toBeInTheDocument();

    // repository card details
    fireEvent.click(screen.getByRole("button", { name: /📁 Repositories/i }));
    expect(screen.getByText("Main platform repository")).toBeInTheDocument();
    expect(screen.getByText(/Size: 2048 KB/)).toBeInTheDocument();

    // pull request details
    fireEvent.click(screen.getByRole("button", { name: /🔄 Pull Requests/i }));
    expect(
      screen.getAllByText((_, el) => (el?.textContent || "").includes("#42 • feat/sandbox")).length,
    ).toBeGreaterThan(0);
    expect(screen.getByText(/feat\/sandbox/)).toBeInTheDocument();
    expect(screen.getByText(/Author: Rushi Parikh/)).toBeInTheDocument();

    // pipeline details
    fireEvent.click(screen.getByRole("button", { name: /⚙️ Pipelines/i }));
    expect(screen.getByText(/Pipeline #8/)).toBeInTheDocument();
    expect(screen.getByText(/Duration: 15s/)).toBeInTheDocument();
    expect(screen.getByText(/deadbee/)).toBeInTheDocument();

    // issue details
    fireEvent.click(screen.getByRole("button", { name: /🐛 Issues/i }));
    expect(screen.getByText("Two logins race on refresh token")).toBeInTheDocument();
    expect(screen.getByText(/Priority: high/)).toBeInTheDocument();

    // search tab
    fireEvent.click(screen.getByRole("button", { name: /🔍 Code Search/i }));
    expect(screen.getByPlaceholderText("Search code...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Search$/ })).toBeInTheDocument();
  });

  it("navigates via the remaining quick action buttons", async () => {
    await connected();

    fireEvent.click(screen.getByRole("button", { name: /View Pull Requests/i }));
    expect(screen.getByRole("heading", { name: /Bitbucket Pull Requests/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /📊 Overview/i }));
    fireEvent.click(screen.getByRole("button", { name: /CI\/CD Pipelines/i }));
    expect(screen.getByRole("heading", { name: /Bitbucket Pipelines/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /📊 Overview/i }));
    fireEvent.click(screen.getByRole("button", { name: /Search Code/i }));
    expect(screen.getByRole("heading", { name: /Bitbucket Code Search/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /← Back to Integrations/i }));
    expect(mockPush).toHaveBeenCalledWith("/integrations");
  });
});
