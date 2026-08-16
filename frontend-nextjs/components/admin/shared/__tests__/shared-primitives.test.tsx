import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { LoadingSkeleton } from "@/components/admin/shared/LoadingSkeleton";
import { EmptyState } from "@/components/admin/shared/EmptyState";
import { HelpTooltip } from "@/components/admin/shared/HelpTooltip";

jest.mock("@/components/ui/skeleton", () => ({
  Skeleton: ({ className }: { className?: string }) => (
    <div className={className} data-testid="skeleton" />
  ),
}));

describe("LoadingSkeleton", () => {
  it("renders the stats layout with four cards", () => {
    const { container } = render(<LoadingSkeleton type="stats" />);
    expect(container.querySelectorAll(".grid-cols-4")).toHaveLength(1);
    expect(screen.getAllByTestId("skeleton").length).toBeGreaterThan(8);
  });

  it("renders the table layout honoring count", () => {
    const { container } = render(<LoadingSkeleton type="table" count={3} />);
    expect(container.querySelectorAll(".divide-y, .space-y-3")).toBeTruthy();
    expect(screen.getAllByTestId("skeleton").length).toBe(14);
  });

  it("renders the list layout honoring count", () => {
    const { container } = render(<LoadingSkeleton type="list" count={2} />);
    expect(container.querySelector(".divide-y")).toBeInTheDocument();
    expect(screen.getAllByTestId("skeleton").length).toBe(8);
  });

  it("defaults to the card layout with count cards", () => {
    const { container } = render(<LoadingSkeleton count={2} />);
    expect(container.querySelectorAll(".p-2, .p-6")).toBeTruthy();
    expect(screen.getAllByTestId("skeleton").length).toBe(10);
  });
});

describe("EmptyState", () => {
  it("renders the no-data default", () => {
    render(<EmptyState />);
    expect(screen.getByText("No data available")).toBeInTheDocument();
    expect(
      screen.getByText("There's no data to display yet. Check back later."),
    ).toBeInTheDocument();
  });

  it("renders each type with its defaults", () => {
    const { rerender } = render(<EmptyState type="no-results" />);
    expect(screen.getByText("No results found")).toBeInTheDocument();

    rerender(<EmptyState type="no-issues" />);
    expect(screen.getByText("All clear!")).toBeInTheDocument();

    rerender(<EmptyState type="error" />);
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("renders a custom title and description", () => {
    render(<EmptyState type="no-data" title="Empty" description="Nothing here" />);
    expect(screen.getByText("Empty")).toBeInTheDocument();
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });

  it("renders an action button wired to onClick", () => {
    const onClick = jest.fn();
    render(
      <EmptyState
        type="no-data"
        action={{ label: "Create Agent", onClick }}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Create Agent" }));
    expect(onClick).toHaveBeenCalled();
  });

  it("renders an action as a deep link when href is provided", () => {
    render(
      <EmptyState type="no-data" action={{ label: "New Agent", href: "/agents/new" }} />,
    );
    expect(
      screen.getByRole("link", { name: "New Agent" }),
    ).toBeInTheDocument();
  });
});

describe("HelpTooltip", () => {
  it("renders the info trigger with content", () => {
    render(<HelpTooltip content="Syncs every 5 minutes" />);
    expect(screen.getByRole("button")).toBeInTheDocument();
    expect(document.querySelector(".lucide-info")).toBeInTheDocument();
  });
});
