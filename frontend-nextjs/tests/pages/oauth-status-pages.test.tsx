/**
 * OAuth status page tests (pages/oauth/error.tsx + pages/oauth/success.tsx,
 * both 0% coverage). The two pages share identical mocks (router query +
 * countdown interval), so they live in one file.
 *
 * Covers: query-driven copy, countdown text, and the automatic
 * redirect to home once the countdown expires.
 */

import React from "react";
import { render, screen, act } from "@testing-library/react";
import OAuthError from "@/pages/oauth/error";
import OAuthSuccess from "@/pages/oauth/success";

// pages/oauth/{error,success}.tsx omit the React import (fine under Next's
// automatic JSX runtime), but ts-jest compiles classic JSX which expects a
// React identifier in scope. Expose it globally for these page modules.
(global as any).React = React;

const mockPush = jest.fn();
let mockQuery: Record<string, string | undefined> = {};

jest.mock("next/router", () => ({
  useRouter: () => ({
    push: (...args: any[]) => mockPush(...args),
    query: mockQuery,
  }),
}));

describe("OAuthErrorPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    mockQuery = {};
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test("renders the failure copy without an error detail box", () => {
    render(<OAuthError />);
    expect(screen.getByText("Authentication Failed")).toBeInTheDocument();
    expect(screen.getByText("There was a problem connecting your account.")).toBeInTheDocument();
    expect(screen.queryByText(/^Error:/)).not.toBeInTheDocument();
    expect(screen.getByText("Redirecting to home in 5 seconds...")).toBeInTheDocument();
    expect(mockPush).not.toHaveBeenCalled();
  });

  test("shows the error detail from the query string", () => {
    mockQuery = { error: "invalid_request" };
    render(<OAuthError />);
    expect(screen.getByText("Error: invalid_request")).toBeInTheDocument();
  });

  test("redirects home when the countdown expires", () => {
    render(<OAuthError />);
    act(() => {
      jest.advanceTimersByTime(5000);
    });
    // The error page routes to the app home ("/"), not the dashboard.
    expect(mockPush).toHaveBeenCalledWith("/");
  });

  test("counts down before redirecting", () => {
    render(<OAuthError />);
    act(() => {
      jest.advanceTimersByTime(1000);
    });
    expect(screen.getByText("Redirecting to home in 4 seconds...")).toBeInTheDocument();
    expect(mockPush).not.toHaveBeenCalled();
  });
});

describe("OAuthSuccessPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    mockQuery = {};
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test("renders the success copy with the provider name", () => {
    mockQuery = { provider: "GitHub" };
    render(<OAuthSuccess />);
    expect(screen.getByText("Authentication Successful!")).toBeInTheDocument();
    expect(screen.getByText("You have successfully connected GitHub to ATOM.")).toBeInTheDocument();
    expect(screen.getByText("Redirecting to home in 3 seconds...")).toBeInTheDocument();
  });

  test("falls back to a generic provider name", () => {
    render(<OAuthSuccess />);
    expect(screen.getByText("You have successfully connected your account to ATOM.")).toBeInTheDocument();
  });

  test("redirects home when the countdown expires", () => {
    render(<OAuthSuccess />);
    act(() => {
      jest.advanceTimersByTime(3000);
    });
    expect(mockPush).toHaveBeenCalledWith("/dashboard");
  });
});
