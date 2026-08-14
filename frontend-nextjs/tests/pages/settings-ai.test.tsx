/**
 * AISettingsPage tests (pages/settings/ai.tsx, was 0% coverage)
 *
 * Covers: heading, provider settings wiring, and the three
 * dashboard links (routing / harness evolution / local models).
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import AISettingsPage from "@/pages/settings/ai";

jest.mock("@/components/layout/Layout", () => ({
  __esModule: true,
  default: ({ children }: any) => <div data-testid="layout">{children}</div>,
}));

let latestProviderProps: any = null;
jest.mock("@/src/components/AIProviders/AIProviderSettings", () => ({
  __esModule: true,
  default: (props: any) => {
    latestProviderProps = props;
    return <div data-testid="ai-provider-settings">Providers</div>;
  },
}));

jest.mock("@chakra-ui/react", () => ({
  Box: ({ children }: any) => <div>{children}</div>,
  Heading: ({ children }: any) => <h1>{children}</h1>,
  Container: ({ children }: any) => <div>{children}</div>,
  Text: ({ children }: any) => <span>{children}</span>,
}));

describe("AISettingsPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    latestProviderProps = null;
  });

  test("renders the heading and provider settings with the api base url", () => {
    render(<AISettingsPage />);
    expect(screen.getByRole("heading", { name: "AI Provider Settings" })).toBeInTheDocument();
    expect(screen.getByTestId("ai-provider-settings")).toBeInTheDocument();
    expect(latestProviderProps.baseApiUrl).toBe("/api");
  });

  test("renders links to the routing, harness, and local model dashboards", () => {
    render(<AISettingsPage />);

    const routing = screen.getByText("Routing & Learning Dashboard →").closest("a");
    expect(routing?.getAttribute("href")).toBe("/settings/routing");

    const harness = screen.getByText("Self-Evolving Harness Dashboard →").closest("a");
    expect(harness?.getAttribute("href")).toBe("/settings/harness-evolution");

    const local = screen.getByText("Local Models (Ollama, LM Studio, vLLM) →").closest("a");
    expect(local?.getAttribute("href")).toBe("/settings/local-models");
  });
});
