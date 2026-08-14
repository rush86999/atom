/**
 * AuthErrorPage tests (pages/auth/error.tsx, was 0% coverage)
 *
 * Covers: every error message branch driven by router.query.error,
 * and the Try Again / Return Home navigation buttons.
 */

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import AuthError from "@/pages/auth/error";

const mockPush = jest.fn();
let mockQuery: Record<string, string | undefined> = {};

jest.mock("next/router", () => ({
  useRouter: () => ({
    push: (...args: any[]) => mockPush(...args),
    query: mockQuery,
  }),
}));

describe("AuthErrorPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockQuery = {};
  });

  const renderPage = () => render(<AuthError />);

  test.each([
    ["Configuration", "There is a problem with the server configuration. Please contact support."],
    ["AccessDenied", "Access denied. You do not have permission to sign in."],
    ["Verification", "The verification link has expired or has already been used."],
    ["Default", "An unexpected error occurred during authentication. Please try again."],
    ["SomethingElse", "An unexpected error occurred during authentication. Please try again."],
  ])("shows the mapped message for error=%s", (errorType, expectedMessage) => {
    mockQuery = { error: errorType };
    renderPage();
    expect(screen.getByText("Authentication Error")).toBeInTheDocument();
    expect(screen.getByText("Authentication Failed")).toBeInTheDocument();
    expect(screen.getByText(expectedMessage)).toBeInTheDocument();
  });

  test("falls back to the default message when no error param exists", () => {
    renderPage();
    expect(
      screen.getByText("An unexpected error occurred during authentication. Please try again.")
    ).toBeInTheDocument();
    expect(screen.getByText("If this problem persists, please contact support.")).toBeInTheDocument();
  });

  test("Try Again navigates to signin", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /Try Again/ }));
    expect(mockPush).toHaveBeenCalledWith("/auth/signin");
  });

  test("Return Home navigates to the root", () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: /Return Home/ }));
    expect(mockPush).toHaveBeenCalledWith("/");
  });
});
