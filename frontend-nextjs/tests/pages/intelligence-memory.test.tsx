/**
 * MemoryDashboardPage tests (pages/intelligence/memory.tsx, was 0% coverage)
 *
 * Covers: header + nav links, the recall feed wiring (workspaceId),
 * security feature list, confidence distribution bars, and the
 * world-model sync card.
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import MemoryDashboardPage from "@/pages/intelligence/memory";

let latestFeedProps: any = null;
jest.mock("@/components/Agents/MemoryRecallFeed", () => ({
  MemoryRecallFeed: (props: any) => {
    latestFeedProps = props;
    return <div data-testid="memory-recall-feed">Feed</div>;
  },
}));

describe("MemoryDashboardPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    latestFeedProps = null;
  });

  test("renders header, nav links, and actions", () => {
    render(<MemoryDashboardPage />);
    expect(screen.getByText("Episodic Intelligence")).toBeInTheDocument();

    const agentsLinks = screen.getAllByText("Agents");
    expect(agentsLinks.length).toBeGreaterThan(0);
    expect(agentsLinks[0].closest("a")?.getAttribute("href")).toBe("/agents");
    expect(screen.getByText("Neural Memory")).toBeInTheDocument();

    expect(screen.getByText("Control Center").closest("a")?.getAttribute("href")).toBe("/agents");
    expect(screen.getByRole("button", { name: /Archive Session/ })).toBeInTheDocument();
  });

  test("renders the recall feed with the default workspace", () => {
    render(<MemoryDashboardPage />);
    expect(screen.getByTestId("memory-recall-feed")).toBeInTheDocument();
    expect(latestFeedProps.workspaceId).toBe("default");
  });

  test("renders the neural security panel features", () => {
    render(<MemoryDashboardPage />);
    expect(screen.getByText("Neural Security")).toBeInTheDocument();
    expect(screen.getByText("Zero-leak Vector Isolation")).toBeInTheDocument();
    expect(screen.getByText("Feedback-driven Confidence")).toBeInTheDocument();
    expect(screen.getByText("Episodic Pattern Recognition")).toBeInTheDocument();
  });

  test("renders the confidence distribution and world model sync cards", () => {
    render(<MemoryDashboardPage />);
    expect(screen.getByText("Confidence Distribution")).toBeInTheDocument();
    expect(screen.getByText("High Confidence")).toBeInTheDocument();
    expect(screen.getByText("72%")).toBeInTheDocument();
    expect(screen.getByText("Needs Supervision")).toBeInTheDocument();
    expect(screen.getByText("18%")).toBeInTheDocument();
    expect(screen.getByText("Critical Failure")).toBeInTheDocument();
    expect(screen.getByText("10%")).toBeInTheDocument();
    expect(screen.getByText("World Model Sync")).toBeInTheDocument();
  });
});
