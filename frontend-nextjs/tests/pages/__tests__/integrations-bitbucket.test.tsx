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

const WORKSPACES = [
  { slug: "acme", name: "Acme Corp", type: "Team", created_on: "2024-01-01T00:00:00Z" },
  { slug: "globex", name: "Globex Industries", type: "Company", created_on: "2023-06-15T00:00:00Z" },
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
  {
    name: "mobile-app",
    description: null,
    language: "TypeScript",
    size: 512,
    workspace: { slug: "globex" },
    updated_on: "2025-02-01T00:00:00Z",
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
  {
    id: 7,
    title: "Fix csv injection",
    state: "MERGED",
    source: { branch: { name: "fix/csv" } },
    destination: { branch: { name: "main" } },
    author: { display_name: "Rushi Parikh" },
    created_on: "2025-01-10T00:00:00Z",
    updated_on: "2025-01-11T00:00:00Z",
  },
];

const PIPELINES = [
  {
    build_number: 7,
    state: { name: "SUCCESSFUL" },
    repository: { name: "atom-core" },
    trigger: { name: "manual" },
    created_on: "2025-03-01T00:00:00Z",
    build_seconds_used: 120,
    target: { commit: { hash: "abc123def456" } },
  },
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
  {
    title: "Add dark mode toggle",
    state: "closed",
    kind: "enhancement",
    priority: "low",
    reporter: { display_name: "Ada Lovelace" },
    content: { raw: "Users want it" },
    created_on: "2025-02-01T00:00:00Z",
  },
];

function okResponse(body: any) {
  return { ok: true, json: async () => body };
}

function errResponse(status: number) {
  return { ok: false, status, json: async () => ({}) };
}

describe("BitbucketIntegrationPage", () => {
  const mockFetch = jest.fn();
  const mockPush = jest.fn();
  let getItemSpy: jest.SpyInstance;
  let removeItemSpy: jest.SpyInstance;

  const setupConnectedMocks = () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/health")) return Promise.resolve(okResponse({ status: "healthy" }));
      if (url.includes("/workspaces")) return Promise.resolve(okResponse({ workspaces: WORKSPACES }));
      if (url.includes("/repositories")) return Promise.resolve(okResponse({ repositories: REPOSITORIES }));
      if (url.includes("/pull-requests")) return Promise.resolve(okResponse({ pull_requests: PULL_REQUESTS }));
      if (url.includes("/pipelines")) return Promise.resolve(okResponse({ pipelines: PIPELINES }));
      if (url.includes("/issues")) return Promise.resolve(okResponse({ issues: ISSUES }));
      if (url.includes("/authorize")) return Promise.resolve(okResponse({ authorization_url: "https://bitbucket.org/site/oauth2/authorize?client=xyz" }));
      return Promise.resolve(errResponse(404));
    });
  };

  beforeEach(() => {
    jest.clearAllMocks();
    (useRouter as jest.Mock).mockReturnValue({
      route: "/integrations/bitbucket",
      pathname: "/integrations/bitbucket",
      query: {},
      asPath: "/integrations/bitbucket",
      push: mockPush,
      replace: jest.fn(() => Promise.resolve(true)),
      back: jest.fn(),
    });
    getItemSpy = jest.spyOn(Storage.prototype, "getItem");
    removeItemSpy = jest.spyOn(Storage.prototype, "removeItem");
    global.fetch = mockFetch;
  });

  it("renders the header and shows Disconnected when no token is stored", async () => {
    getItemSpy.mockReturnValue(null);
    render(<BitbucketIntegrationPage />);

    expect(screen.getByRole("heading", { name: /bitbucket integration/i })).toBeInTheDocument();
    expect(screen.getByText("← Back to Integrations")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeInTheDocument();
    });
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("connects when a stored token exists and the health check is healthy, then loads all datasets", async () => {
    getItemSpy.mockReturnValue("tok-abc");
    setupConnectedMocks();
    render(<BitbucketIntegrationPage />);

    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });

    expect(
      mockFetch.mock.calls.find((c) => (c[0] as string).includes("/health"))
    ).toBeTruthy();
    const healthCall = mockFetch.mock.calls.find((c) => (c[0] as string).includes("/health"));
    expect((healthCall as any[])[1]?.headers?.Authorization).toBe("Bearer tok-abc");

    // Stat cards reflect the loaded data
    const workspaceStat = screen.getByText("Workspaces").previousSibling;
    expect(workspaceStat?.textContent).toBe("2");
    expect(screen.getByText("Open PRs").previousSibling?.textContent).toBe("2");
    expect(screen.getByText("Running Pipelines").previousSibling?.textContent).toBe("1");
    expect(screen.getByText("Open Issues").previousSibling?.textContent).toBe("2");

    // Overview shows recent repositories and pull requests
    expect(screen.getByText("atom-core")).toBeInTheDocument();
    expect(screen.getByText("Add sandbox layer")).toBeInTheDocument();
    expect(screen.getByText("No description")).toBeInTheDocument();
  });

  it("navigates between tabs and renders each dataset", async () => {
    getItemSpy.mockReturnValue("tok-abc");
    setupConnectedMocks();
    render(<BitbucketIntegrationPage />);

    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });

    // Workspaces tab
    fireEvent.click(screen.getByRole("button", { name: /workspaces/i }));
    expect(screen.getByRole("heading", { name: "Bitbucket Workspaces" })).toBeInTheDocument();
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("Type: Team")).toBeInTheDocument();

    // Repositories tab
    fireEvent.click(screen.getByRole("button", { name: /repositories/i }));
    expect(screen.getByRole("heading", { name: "Bitbucket Repositories" })).toBeInTheDocument();
    expect(screen.getByText("No description available")).toBeInTheDocument();
    expect(screen.getByText("Workspace: globex")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /clone/i })).toBeInTheDocument();

    // Pull requests tab
    fireEvent.click(screen.getByRole("button", { name: /pull requests/i }));
    expect(screen.getByRole("heading", { name: "Bitbucket Pull Requests" })).toBeInTheDocument();
    expect(screen.getByText("feat/sandbox → main")).toBeInTheDocument();
    expect(screen.getByText("Rushi Parikh")).toBeInTheDocument();
    expect(screen.getByText("OPEN")).toBeInTheDocument();
    expect(screen.getByText("MERGED")).toBeInTheDocument();

    // Pipelines tab
    fireEvent.click(screen.getByRole("button", { name: /pipelines/i }));
    expect(screen.getByRole("heading", { name: "Bitbucket Pipelines" })).toBeInTheDocument();
    expect(screen.getByText("Pipeline #8")).toBeInTheDocument();
    expect(screen.getByText("IN_PROGRESS")).toBeInTheDocument();
    expect(screen.getByText("Duration: 120s")).toBeInTheDocument();
    expect(screen.getByText("abc123d")).toBeInTheDocument();

    // Issues tab
    fireEvent.click(screen.getByRole("button", { name: /issues/i }));
    expect(screen.getByRole("heading", { name: "Bitbucket Issues" })).toBeInTheDocument();
    expect(screen.getByText("Bug: auth race condition")).toBeInTheDocument();
    expect(screen.getByText("Two logins race on refresh token")).toBeInTheDocument();
    expect(screen.getByText("enhancement")).toBeInTheDocument();
  });

  it("shows workspace/repo counts on the code search tab", async () => {
    getItemSpy.mockReturnValue("tok-abc");
    setupConnectedMocks();
    render(<BitbucketIntegrationPage />);

    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /code search/i }));
    expect(screen.getByRole("heading", { name: "Bitbucket Code Search" })).toBeInTheDocument();
    expect(
      screen.getByText("Search across 2 repositories and 2 workspaces")
    ).toBeInTheDocument();
  });

  it("starts the OAuth flow from the settings tab when disconnected", async () => {
    getItemSpy.mockReturnValue(null);
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/authorize")) {
        return Promise.resolve(
          okResponse({ authorization_url: "https://bitbucket.org/oauth2/authorize?client=xyz" })
        );
      }
      return Promise.resolve(errResponse(404));
    });
    render(<BitbucketIntegrationPage />);

    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /settings/i }));
    expect(screen.getByRole("heading", { name: "Bitbucket Settings" })).toBeInTheDocument();
    expect(screen.getAllByText("Disconnected").length).toBeGreaterThanOrEqual(2);

    fireEvent.click(screen.getByRole("button", { name: /connect bitbucket account/i }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith("/api/integrations/bitbucket/authorize");
    });
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it("disconnects from settings by clearing tokens and resetting state", async () => {
    getItemSpy.mockReturnValue("tok-abc");
    setupConnectedMocks();
    render(<BitbucketIntegrationPage />);

    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /settings/i }));
    fireEvent.click(screen.getByRole("button", { name: /disconnect bitbucket/i }));

    await waitFor(() => {
      expect(removeItemSpy).toHaveBeenCalledWith("bitbucket_access_token");
      expect(removeItemSpy).toHaveBeenCalledWith("bitbucket_refresh_token");
    });
    expect(screen.getAllByText("Disconnected").length).toBeGreaterThanOrEqual(2);

    // Data lists were reset: workspaces tab is empty
    fireEvent.click(screen.getByRole("button", { name: /workspaces/i }));
    expect(screen.queryByText("Acme Corp")).not.toBeInTheDocument();
  });

  it("shows Disconnected when the health check fails and does not load data", async () => {
    getItemSpy.mockReturnValue("tok-abc");
    mockFetch.mockImplementation((url: string) =>
      Promise.resolve(url.includes("/health") ? errResponse(500) : okResponse({}))
    );
    render(<BitbucketIntegrationPage />);

    await waitFor(() => {
      expect(screen.getByText("Disconnected")).toBeInTheDocument();
    });
    expect(
      mockFetch.mock.calls.some((c) => (c[0] as string).includes("/workspaces"))
    ).toBe(false);
  });

  it("uses quick action buttons to jump between tabs", async () => {
    getItemSpy.mockReturnValue("tok-abc");
    setupConnectedMocks();
    render(<BitbucketIntegrationPage />);

    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: /browse repositories/i }));
    expect(screen.getByRole("heading", { name: "Bitbucket Repositories" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /ci\/cd pipelines/i }));
    expect(screen.getByRole("heading", { name: "Bitbucket Pipelines" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /search code/i }));
    expect(screen.getByRole("heading", { name: "Bitbucket Code Search" })).toBeInTheDocument();
  });

  it("navigates back to the integrations hub", async () => {
    getItemSpy.mockReturnValue(null);
    render(<BitbucketIntegrationPage />);

    fireEvent.click(screen.getByRole("button", { name: /back to integrations/i }));
    expect(mockPush).toHaveBeenCalledWith("/integrations");
  });
});
