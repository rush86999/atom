import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
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
const vc: any = window._virtualConsole;
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
    expect(screen.getByText("Disconnected")).toBeInTheDocument();
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("shows Disconnected when the health check fails", async () => {
    getItemSpy.mockReturnValue(TOKEN);
    mockFetch.mockImplementation(() =>
      Promise.resolve(errResponse(500)),
    );
    render(<BitbucketIntegrationPage />);
    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeInTheDocument();
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/integrations/bitbucket/health",
      expect.objectContaining({
        headers: { Authorization: `Bearer ${TOKEN}` },
      }),
    );
  });

  it("connects, loads all datasets, and renders overview stats", async () => {
    getItemSpy.mockReturnValue(TOKEN);
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/health")) {
        return Promise.resolve(okResponse({ status: "healthy" }));
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
      url.includes("/health")
        ? Promise.resolve(okResponse({ status: "healthy" }))
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
    getItemSpy.mockReturnValue(TOKEN);
    mockFetch.mockImplementation((url: string) =>
      url.includes("/health")
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
      url.includes("/health")
        ? Promise.resolve(okResponse({ status: "healthy" }))
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
      url.includes("/health")
        ? Promise.resolve(okResponse({ status: "healthy" }))
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
