import React from "react";
import { render, screen } from "@testing-library/react";
import SessionProvider from "@/components/SessionProvider";

jest.mock("next-auth/react", () => {
  const React = require("react");
  return {
    SessionProvider: ({ children }: { children: React.ReactNode }) =>
      React.createElement("div", { "data-testid": "next-auth-provider" }, children),
  };
});

describe("SessionProvider", () => {
  it("wraps children in the NextAuth provider with the session", () => {
    render(
      <SessionProvider session={{ user: { name: "admin" } }}>
        <div>app content</div>
      </SessionProvider>,
    );
    expect(screen.getByTestId("next-auth-provider")).toBeInTheDocument();
    expect(screen.getByText("app content")).toBeInTheDocument();
  });

  it("renders without a session", () => {
    render(
      <SessionProvider>
        <div>anonymous</div>
      </SessionProvider>,
    );
    expect(screen.getByText("anonymous")).toBeInTheDocument();
  });
});
