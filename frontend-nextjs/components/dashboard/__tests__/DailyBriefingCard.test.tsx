import React from "react";
import { render, screen } from "@testing-library/react";
import { DailyBriefingCard } from "@/components/dashboard/DailyBriefingCard";

const priorities = [
  {
    id: "p1",
    type: "GROWTH" as const,
    title: "Expand pipeline",
    description: "Two new deals entered prospecting",
    priority: "HIGH" as const,
    action_link: "/sales",
  },
  {
    id: "p2",
    type: "RISK" as const,
    title: "Churn risk",
    description: "Acme Corp usage dropped 40%",
    priority: "MEDIUM" as const,
    action_link: "/accounts/acme",
  },
  {
    id: "p3",
    type: "STRATEGY" as const,
    title: "Q3 plan",
    description: "Review quarterly strategy",
    priority: "LOW" as const,
    action_link: "/strategy",
  },
];

describe("DailyBriefingCard", () => {
  it("renders advice, all priority types with badge colors, and action links", () => {
    render(<DailyBriefingCard advice="Revenue is up 12%" priorities={priorities} />);

    expect(screen.getByText("Daily Briefing")).toBeInTheDocument();
    expect(screen.getByText("Revenue is up 12%")).toBeInTheDocument();

    expect(screen.getByText("GROWTH")).toBeInTheDocument();
    expect(screen.getByText("Expand pipeline")).toBeInTheDocument();
    expect(screen.getByText("Two new deals entered prospecting")).toBeInTheDocument();

    expect(screen.getByText("RISK")).toBeInTheDocument();
    expect(screen.getByText("Churn risk")).toBeInTheDocument();

    expect(screen.getByText("STRATEGY")).toBeInTheDocument();
    expect(screen.getByText("Q3 plan")).toBeInTheDocument();

    const growthBadge = screen.getByText("GROWTH");
    expect(growthBadge.className).toContain("bg-green-100");
    const riskBadge = screen.getByText("RISK");
    expect(riskBadge.className).toContain("bg-red-100");
    const strategyBadge = screen.getByText("STRATEGY");
    expect(strategyBadge.className).toContain("bg-purple-100");

    expect(screen.getAllByRole("link").length).toBe(3);
  });

  it("falls back to the analyzing placeholder when advice is empty", () => {
    render(<DailyBriefingCard advice="" priorities={priorities} />);
    expect(screen.getByText("Analyzing business signals...")).toBeInTheDocument();
  });

  it("shows the empty state when there are no priorities", () => {
    render(<DailyBriefingCard advice="All good" priorities={[]} />);
    expect(
      screen.getByText("No critical items today. Good job!"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
