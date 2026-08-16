import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import OptimizationPanel, {
  OptimizationSuggestion,
} from "@/components/Automations/OptimizationPanel";

const suggestions: OptimizationSuggestion[] = [
  {
    type: "parallelization",
    description: "Run the two API calls in parallel",
    affected_nodes: ["n1", "n2"],
    savings_estimate_ms: 800,
    action: "parallelize",
  },
  {
    type: "caching",
    description: "Cache repeated lookups",
    affected_nodes: ["n3"],
    savings_estimate_ms: 120,
    action: "add_cache",
  },
];

describe("OptimizationPanel", () => {
  it("shows the loading state while analyzing", () => {
    render(
      <OptimizationPanel
        open
        onOpenChange={jest.fn()}
        isLoading
        suggestions={[]}
        onApply={jest.fn()}
      />,
    );
    expect(screen.getByText("Workflow Optimizer")).toBeInTheDocument();
    expect(
      screen.getByText("Analyzing workflow dependencies..."),
    ).toBeInTheDocument();
  });

  it("shows the all-optimized state when there are no suggestions", () => {
    render(
      <OptimizationPanel
        open
        onOpenChange={jest.fn()}
        isLoading={false}
        suggestions={[]}
        onApply={jest.fn()}
      />,
    );
    expect(screen.getByText("All Optimized!")).toBeInTheDocument();
    expect(
      screen.getByText("No optimization opportunities detected."),
    ).toBeInTheDocument();
  });

  it("renders suggestions and applies them on click", () => {
    const onApply = jest.fn();
    render(
      <OptimizationPanel
        open
        onOpenChange={jest.fn()}
        isLoading={false}
        suggestions={suggestions}
        onApply={onApply}
      />,
    );

    expect(screen.getByText("Parallelization")).toBeInTheDocument();
    expect(screen.getByText("-800ms")).toBeInTheDocument();
    expect(
      screen.getByText("Run the two API calls in parallel"),
    ).toBeInTheDocument();
    expect(screen.getByText("Affected Steps: n1, n2")).toBeInTheDocument();

    expect(screen.getByText("caching")).toBeInTheDocument();
    expect(screen.getByText("-120ms")).toBeInTheDocument();

    const applyButtons = screen.getAllByRole("button", { name: /Apply Fix/i });
    expect(applyButtons.length).toBe(2);
    fireEvent.click(applyButtons[0]);
    expect(onApply).toHaveBeenCalledWith(suggestions[0]);
  });
});
