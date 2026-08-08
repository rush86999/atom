import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import Home from "@/pages/index";
import { useRouter } from "next/router";

const mockPush = jest.fn();
const mockReplace = jest.fn();

jest.mock("next/router", () => ({
  useRouter: jest.fn(),
}));

jest.mock("@/components/Onboarding/OnboardingWizard", () => ({
  OnboardingWizard: ({ isOpen, user }: any) =>
    isOpen ? (
      <div data-testid="onboarding-wizard">{user ? user.name : "no-user"}</div>
    ) : null,
}));

jest.mock("next/link", () => ({ children, href }: any) => (
  <a href={href}>{children}</a>
));

const okJson = (body: any) => ({ ok: true, json: async () => body });
const errJson = { ok: false, status: 404, json: async () => ({}) };

describe("Home landing page", () => {
  const mockFetch = jest.fn();
  let getItemSpy: jest.SpyInstance;
  let setItemSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    (useRouter as jest.Mock).mockReturnValue({
      push: mockPush,
      replace: mockReplace,
      prefetch: jest.fn(),
      back: jest.fn(),
    });
    global.fetch = mockFetch;
    getItemSpy = jest
      .spyOn(Storage.prototype, "getItem")
      .mockImplementation(() => null);
    setItemSpy = jest
      .spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => {});
    jest.spyOn(Storage.prototype, "removeItem");
    document.cookie.split(";").forEach((c) => {
      document.cookie = c
        .replace(/^ +/, "")
        .replace(/=.*/, "=;expires=" + new Date(0).toUTCString() + ";path=/");
    });
    mockFetch.mockImplementation(() => Promise.resolve(errJson));
  });

  it("renders the landing header and feature grid when unauthenticated", () => {
    render(<Home />);
    expect(screen.getByRole("heading", { name: /Welcome to ATOM/i })).toBeInTheDocument();
    expect(screen.getByText("AI-powered search across all your documents, meetings, and notes")).toBeInTheDocument();
    expect(screen.getByText("Workflow Automation")).toBeInTheDocument();
    expect(screen.getByText("Calendar")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Get Started with Automation/i })
    ).toBeInTheDocument();
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("redirects to /dashboard when a token exists", async () => {
    getItemSpy.mockImplementation((key: string) =>
      key === "token" ? "test-token" : null
    );
    render(<Home />);
    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/dashboard");
    });
  });

  it("redirects to /login when the user explicitly logged out", async () => {
    getItemSpy.mockImplementation((key: string) =>
      key === "atom_explicit_logout" ? "1" : null
    );
    render(<Home />);
    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/login");
    });
  });

  it("bootstraps a dev session on localhost and redirects to /dashboard", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/dev/bootstrap-session")) {
        return Promise.resolve(okJson({ access_token: "dev-token" }));
      }
      return Promise.resolve(errJson);
    });
    render(<Home />);
    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/dashboard");
    });
    expect(setItemSpy).toHaveBeenCalledWith("auth_token", "dev-token");
    expect(Storage.prototype.removeItem).toHaveBeenCalledWith("atom_explicit_logout");
    expect(document.cookie).toContain("auth_token=dev-token");
  });

  it("stays on the landing page when the dev bootstrap returns no token", async () => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/dev/bootstrap-session")) {
        return Promise.resolve(okJson({}));
      }
      return Promise.resolve(errJson);
    });
    render(<Home />);
    expect(
      screen.getByRole("heading", { name: /Welcome to ATOM/i })
    ).toBeInTheDocument();
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("opens the onboarding wizard when onboarding is incomplete", async () => {
    getItemSpy.mockImplementation((key: string) =>
      key === "token" ? "test-token" : null
    );
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/onboarding/status")) {
        return Promise.resolve(okJson({ onboarding_completed: false }));
      }
      if (url.includes("/api/users/me")) {
        return Promise.resolve(okJson({ name: "Dr. Ada Lovelace" }));
      }
      return Promise.resolve(errJson);
    });
    render(<Home />);
    await waitFor(() => {
      expect(screen.getByTestId("onboarding-wizard")).toBeInTheDocument();
    });
    expect(screen.getByText("Dr. Ada Lovelace")).toBeInTheDocument();
  });

  it("renders the activity feed with executions, chat session and agent progress", async () => {
    getItemSpy.mockImplementation((key: string) =>
      key === "token" ? "test-token" : null
    );
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/onboarding/status")) {
        return Promise.resolve(okJson({ onboarding_completed: true }));
      }
      if (url.includes("/api/dashboard/feed")) {
        return Promise.resolve(
          okJson({
            data: {
              recent_executions: [
                {
                  id: "e1",
                  agent_id: null,
                  agent_name: "Sales Assistant",
                  status: "completed",
                  input_summary: "Follow up with Northwind on Q3 renewal",
                  started_at: null,
                  duration_seconds: 12,
                },
              ],
              recent_canvases: [],
              last_chat_session: {
                id: "sess-1",
                title: "Q3 planning",
                updated_at: "2026-08-01T10:00:00Z",
              },
              agents_progress: [
                {
                  id: "a1",
                  name: "Reconciler",
                  current_tier: "INTERN",
                  next_tier: "SUPERVISED",
                  next_threshold_episodes: 10,
                },
              ],
            },
          })
        );
      }
      return Promise.resolve(errJson);
    });
    render(<Home />);

    await waitFor(() => {
      expect(screen.getByText("Recent activity")).toBeInTheDocument();
    });
    expect(screen.getByText("Pick up where you left off")).toBeInTheDocument();
    expect(screen.getByText("Q3 planning")).toBeInTheDocument();
    expect(screen.getByText("Sales Assistant")).toBeInTheDocument();
    expect(screen.getByText("completed")).toBeInTheDocument();
    expect(screen.getByText("Your agents' progress")).toBeInTheDocument();
    expect(screen.getByText("INTERN")).toBeInTheDocument();
    expect(screen.getByText("10 eps → SUPERVISED")).toBeInTheDocument();

    fireEvent.click(screen.getByText("Q3 planning"));
    expect(mockPush).toHaveBeenCalledWith("/chat?session=sess-1");
  });

  it("falls back to the static grid when the feed has no activity", async () => {
    getItemSpy.mockImplementation((key: string) =>
      key === "token" ? "test-token" : null
    );
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("/api/onboarding/status")) {
        return Promise.resolve(okJson({ onboarding_completed: true }));
      }
      if (url.includes("/api/dashboard/feed")) {
        return Promise.resolve(
          okJson({
            data: {
              recent_executions: [],
              recent_canvases: [],
              last_chat_session: null,
              agents_progress: [],
            },
          })
        );
      }
      return Promise.resolve(errJson);
    });
    render(<Home />);
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Welcome to ATOM/i })).toBeInTheDocument();
    });
    expect(screen.queryByText("Recent activity")).not.toBeInTheDocument();
    expect(screen.queryByText("Pick up where you left off")).not.toBeInTheDocument();
    expect(screen.getByText("Dev Studio")).toBeInTheDocument();
  });

  it("navigates when a feature card is clicked", () => {
    render(<Home />);
    fireEvent.click(screen.getByText("Search"));
    expect(mockPush).toHaveBeenCalledWith("/search");
    fireEvent.click(screen.getByText("Finance"));
    expect(mockPush).toHaveBeenCalledWith("/finance");
  });

  it("navigates to /automations from the CTA button", () => {
    render(<Home />);
    fireEvent.click(screen.getByRole("button", { name: /Get Started with Automation/i }));
    expect(mockPush).toHaveBeenCalledWith("/automations");
  });
});
