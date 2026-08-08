import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react";
import JiraOAuthPage from "@/pages/oauth/jira/callback-fixed";

const mockPush = jest.fn();
const mockClose = jest.fn();

jest.mock("next/router", () => ({
  useRouter: jest.fn(),
}));

import { useRouter } from "next/router";

const setParams = (params: Record<string, string>) => {
  jest.spyOn(URLSearchParams.prototype, "get").mockImplementation(
    (key: string) => params[key] ?? null
  );
};

describe("JiraOAuthPage callback", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useRealTimers();
    (useRouter as jest.Mock).mockReturnValue({ push: mockPush, replace: jest.fn() });
    jest.spyOn(URLSearchParams.prototype, "get").mockImplementation(() => null);
    Object.defineProperty(window, "close", {
      configurable: true,
      value: mockClose,
    });
    Object.defineProperty(window, "opener", {
      configurable: true,
      value: null,
    });
  });

  it("renders the success state and auto-redirects after 3 seconds", () => {
    jest.useFakeTimers();
    setParams({ success: "true", workspace: "acme.atlassian.net" });
    render(<JiraOAuthPage />);

    expect(screen.getByText("Integration Successful!")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Successfully connected to acme.atlassian.net workspace."
      )
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Continue to Dashboard/i })
    ).toBeInTheDocument();
    expect(mockPush).not.toHaveBeenCalled();

    act(() => {
      jest.advanceTimersByTime(3000);
    });
    expect(mockPush).toHaveBeenCalledWith("/integrations/jira?success=true");
  });

  it("falls back to the generic workspace name when none is provided", () => {
    setParams({ success: "true" });
    render(<JiraOAuthPage />);
    expect(
      screen.getByText("Successfully connected to Jira workspace.")
    ).toBeInTheDocument();
  });

  it("renders the error state and closes the window", () => {
    setParams({ error: "access_denied" });
    render(<JiraOAuthPage />);

    expect(screen.getByText("Integration Failed")).toBeInTheDocument();
    expect(
      screen.getByText("Failed to connect to Jira workspace. Please try again.")
    ).toBeInTheDocument();
    expect(screen.queryByText("Integration Successful!")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Close Window/i }));
    expect(mockClose).toHaveBeenCalled();
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("posts a completion message to the opener window and closes", () => {
    const mockPostMessage = jest.fn();
    setParams({ success: "true", workspace: "acme.atlassian.net" });
    Object.defineProperty(window, "opener", {
      configurable: true,
      value: { postMessage: mockPostMessage, close: mockClose },
    });
    render(<JiraOAuthPage />);

    fireEvent.click(screen.getByRole("button", { name: /Continue to Dashboard/i }));
    expect(mockPostMessage).toHaveBeenCalledWith(
      {
        type: "jira-oauth-complete",
        data: expect.objectContaining({
          success: true,
          workspace: "acme.atlassian.net",
        }),
      },
      "*"
    );
    expect(mockClose).toHaveBeenCalled();
  });

  it("navigates to the integrations page when there is no opener", () => {
    setParams({ success: "true", workspace: "acme.atlassian.net" });
    render(<JiraOAuthPage />);

    fireEvent.click(screen.getByRole("button", { name: /Continue to Dashboard/i }));
    expect(mockPush).toHaveBeenCalledWith("/integrations/jira");
  });

  it("does not schedule a redirect in the error state", () => {
    jest.useFakeTimers();
    setParams({ error: "access_denied" });
    render(<JiraOAuthPage />);

    act(() => {
      jest.advanceTimersByTime(5000);
    });
    expect(mockPush).not.toHaveBeenCalled();
  });
});
