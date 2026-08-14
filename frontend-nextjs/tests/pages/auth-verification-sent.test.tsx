/**
 * VerificationSentPage tests (pages/auth/verification-sent.tsx, was 0% coverage)
 *
 * Covers: header content, email display (present / absent), the
 * verification-code navigation (button + resend link), and the back-to-signin link.
 */

import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import VerificationSentPage from "@/pages/auth/verification-sent";

const mockPush = jest.fn();
let mockQuery: Record<string, string | undefined> = {};

jest.mock("next/router", () => ({
  useRouter: () => ({
    push: (...args: any[]) => mockPush(...args),
    query: mockQuery,
  }),
}));

describe("VerificationSentPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockQuery = {};
  });

  test("renders instructions and hides the email line when no email query", () => {
    render(<VerificationSentPage />);
    expect(screen.getByText("Check Your Email")).toBeInTheDocument();
    expect(screen.getByText("We've sent a verification code to")).toBeInTheDocument();
    expect(screen.queryByText("user@example.com")).not.toBeInTheDocument();
    expect(
      screen.getByText("Check your email inbox for a message from us")
    ).toBeInTheDocument();
    expect(screen.getByText("Copy the 6-digit verification code")).toBeInTheDocument();
    expect(screen.getByText("Didn't receive the email?")).toBeInTheDocument();
  });

  test("shows the email from the query string", () => {
    mockQuery = { email: "user@example.com" };
    render(<VerificationSentPage />);
    expect(screen.getByText("user@example.com")).toBeInTheDocument();
  });

  test("Enter Verification Code navigates with the encoded email", () => {
    mockQuery = { email: "user@example.com" };
    render(<VerificationSentPage />);
    fireEvent.click(screen.getByRole("button", { name: /Enter Verification Code/ }));
    expect(mockPush).toHaveBeenCalledWith("/auth/verify-email?email=user%40example.com");
  });

  test("button navigates with an empty email when none was provided", () => {
    render(<VerificationSentPage />);
    fireEvent.click(screen.getByRole("button", { name: /Enter Verification Code/ }));
    expect(mockPush).toHaveBeenCalledWith("/auth/verify-email?email=");
  });

  test("resend and back-to-signin links point at the right hrefs", () => {
    mockQuery = { email: "user@example.com" };
    render(<VerificationSentPage />);

    const resend = screen.getByText("Resend verification email").closest("a");
    expect(resend?.getAttribute("href")).toBe("/auth/verify-email?email=user%40example.com");

    const back = screen.getByText("← Back to Sign In").closest("a");
    expect(back?.getAttribute("href")).toBe("/auth/signin");
  });
});
