/**
 * JiraOAuthPage tests (pages/oauth/jira/callback.tsx, was 0% coverage)
 *
 * Covers: success state (code + state, opener postMessage, auto close),
 * error state (error + description, postMessage, auto close), loading
 * state, no-opener window close, and the router-not-ready guard.
 */

import React from "react";
import { render, screen, act } from "@testing-library/react";
import JiraOAuthPage from "@/pages/oauth/jira/callback";

const mockPush = jest.fn();
let mockIsReady = true;

jest.mock("next/router", () => ({
  useRouter: () => ({
    isReady: mockIsReady,
    push: (...args: any[]) => mockPush(...args),
    query: {},
  }),
}));

const mockClose = jest.fn();
let mockPostMessage: jest.Mock;

describe("JiraOAuthPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    mockIsReady = true;
    mockPostMessage = jest.fn();
    window.history.pushState({}, "", "/oauth/jira/callback");
    Object.defineProperty(window, "close", { configurable: true, value: mockClose });
    Object.defineProperty(window, "opener", { configurable: true, value: null });
  });

  afterEach(() => {
    jest.useRealTimers();
    window.history.pushState({}, "", "/");
  });

  test("success state posts to the opener and closes after 2 seconds", () => {
    window.history.pushState({}, "", "/oauth/jira/callback?code=abc123def&state=st-1");
    Object.defineProperty(window, "opener", {
      configurable: true,
      value: { postMessage: mockPostMessage },
    });

    render(<JiraOAuthPage />);

    expect(screen.getByText("Authorization Successful")).toBeInTheDocument();
    expect(screen.getByText("Your Jira workspace has been successfully connected to ATOM.")).toBeInTheDocument();
    expect(screen.getByText("Code: abc123def...")).toBeInTheDocument();
    expect(screen.getByText("State: st-1")).toBeInTheDocument();
    expect(mockPostMessage).toHaveBeenCalledWith(
      { type: "JIRA_OAUTH_SUCCESS", code: "abc123def", state: "st-1" },
      window.location.origin
    );
    expect(mockClose).not.toHaveBeenCalled();

    act(() => {
      jest.advanceTimersByTime(2000);
    });
    expect(mockClose).toHaveBeenCalled();
  });

  test("success state still closes without an opener window", () => {
    window.history.pushState({}, "", "/oauth/jira/callback?code=noopenercode");
    render(<JiraOAuthPage />);

    expect(mockPostMessage).not.toHaveBeenCalled();
    act(() => {
      jest.advanceTimersByTime(2000);
    });
    expect(mockClose).toHaveBeenCalled();
  });

  test("error state posts the error and renders solutions", () => {
    window.history.pushState(
      {},
      "",
      "/oauth/jira/callback?error=access_denied&description=User+said+no"
    );
    Object.defineProperty(window, "opener", {
      configurable: true,
      value: { postMessage: mockPostMessage },
    });

    render(<JiraOAuthPage />);

    expect(screen.getByText("Authorization Failed")).toBeInTheDocument();
    expect(screen.getByText("Error: access_denied")).toBeInTheDocument();
    expect(screen.getByText("Description: User said no")).toBeInTheDocument();
    expect(screen.getByText("Possible Solutions:")).toBeInTheDocument();
    expect(mockPostMessage).toHaveBeenCalledWith(
      {
        type: "JIRA_OAUTH_ERROR",
        error: "access_denied",
        errorDescription: "User said no",
      },
      window.location.origin
    );

    act(() => {
      jest.advanceTimersByTime(2000);
    });
    expect(mockClose).toHaveBeenCalled();
  });

  test("renders the processing state when no code or error is present", () => {
    render(<JiraOAuthPage />);

    expect(screen.getByText("Processing Authorization")).toBeInTheDocument();
    expect(
      screen.getByText("Please wait while we process your Jira authorization...")
    ).toBeInTheDocument();
    expect(mockPostMessage).not.toHaveBeenCalled();

    act(() => {
      jest.advanceTimersByTime(3000);
    });
    expect(mockClose).not.toHaveBeenCalled();
    expect(mockPush).not.toHaveBeenCalled();
  });

  test("stays in the processing state while the router is not ready", () => {
    mockIsReady = false;
    window.history.pushState({}, "", "/oauth/jira/callback?code=abc123def");
    render(<JiraOAuthPage />);

    expect(screen.getByText("Processing Authorization")).toBeInTheDocument();
    act(() => {
      jest.advanceTimersByTime(3000);
    });
    expect(mockClose).not.toHaveBeenCalled();
  });
});
