import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react";
import JiraOAuthPage from "@/pages/oauth/jira/callback-fixed";
import { useRouter } from "next/router";

const mockPush = jest.fn(() => Promise.resolve(true));

jest.mock("next/router", () => ({
  useRouter: jest.fn(() => ({
    push: jest.fn(() => Promise.resolve(true)),
  })),
}));

describe("Jira OAuth callback page (pages/oauth/jira/callback-fixed.tsx)", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    (useRouter as jest.Mock).mockReturnValue({ push: mockPush });
    Object.defineProperty(window, "close", {
      value: jest.fn(),
      writable: true,
      configurable: true,
    });
    Object.defineProperty(window, "opener", {
      value: undefined,
      writable: true,
      configurable: true,
    });
    window.history.replaceState(null, "", "/");
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("resolves a successful callback with a workspace and redirects after 3s", () => {
    window.history.replaceState(
      null,
      "",
      "/oauth/jira/callback-fixed?success=true&workspace=Acme"
    );

    render(<JiraOAuthPage />);

    expect(screen.getByText("Integration Successful!")).toBeInTheDocument();
    expect(screen.getByText("Successfully connected to Acme workspace.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /continue to dashboard/i })).toBeInTheDocument();

    // No redirect yet — the 3s delay has not elapsed
    expect(mockPush).not.toHaveBeenCalled();

    act(() => {
      jest.advanceTimersByTime(3000);
    });
    expect(mockPush).toHaveBeenCalledWith("/integrations/jira?success=true");
  });

  it("falls back to a generic workspace name when none is provided", () => {
    window.history.replaceState(null, "", "/oauth/jira/callback-fixed?success=true");

    render(<JiraOAuthPage />);

    expect(screen.getByText("Integration Successful!")).toBeInTheDocument();
    expect(screen.getByText("Successfully connected to Jira workspace.")).toBeInTheDocument();
  });

  it("renders the failure state for an errored callback and closes the window", () => {
    window.history.replaceState(
      null,
      "",
      "/oauth/jira/callback-fixed?success=false&error=access_denied"
    );

    render(<JiraOAuthPage />);

    expect(screen.getByText("Integration Failed")).toBeInTheDocument();
    expect(
      screen.getByText("Failed to connect to Jira workspace. Please try again.")
    ).toBeInTheDocument();
    const closeButton = screen.getByRole("button", { name: /close window/i });
    expect(closeButton).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /continue to dashboard/i })).not.toBeInTheDocument();

    // No success redirect is ever scheduled for the error state
    act(() => {
      jest.advanceTimersByTime(5000);
    });
    expect(mockPush).not.toHaveBeenCalled();

    fireEvent.click(closeButton);
    expect(window.close).toHaveBeenCalled();
  });

  it("navigates to the integrations page when closed without a popup opener", () => {
    window.history.replaceState(null, "", "/oauth/jira/callback-fixed?success=true");

    render(<JiraOAuthPage />);

    fireEvent.click(screen.getByRole("button", { name: /continue to dashboard/i }));
    expect(mockPush).toHaveBeenCalledWith("/integrations/jira");
    expect(window.close).not.toHaveBeenCalled();
  });

  it("posts the callback data to the opener and closes when opened from a popup", () => {
    window.history.replaceState(
      null,
      "",
      "/oauth/jira/callback-fixed?success=true&workspace=Acme"
    );
    const postMessage = jest.fn();
    Object.defineProperty(window, "opener", {
      value: { postMessage },
      writable: true,
      configurable: true,
    });

    render(<JiraOAuthPage />);

    fireEvent.click(screen.getByRole("button", { name: /continue to dashboard/i }));
    expect(postMessage).toHaveBeenCalledWith(
      {
        type: "jira-oauth-complete",
        data: expect.objectContaining({ success: true, workspace: "Acme" }),
      },
      "*"
    );
    expect(window.close).toHaveBeenCalled();
    expect(mockPush).not.toHaveBeenCalled();
  });
});
