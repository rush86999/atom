import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import HubSpotTest from "@/components/integrations/hubspot/HubSpotTest";

jest.mock("@/components/integrations/hubspot/HubSpotSearch", () => {
  return function MockHubSpotSearch(props: any) {
    return (
      <button
        data-testid="mock-hubspot-search"
        onClick={() => props.onSearch?.([{ id: "test-1" }], { status: "all" }, { field: "name" })}
      >
        Mock Search
      </button>
    );
  };
});

describe("HubSpotTest", () => {
  let logSpy: jest.SpyInstance;

  beforeEach(() => {
    logSpy = jest.spyOn(console, "log").mockImplementation(() => {});
  });

  afterEach(() => {
    logSpy.mockRestore();
  });

  it("renders the test harness with mock data wired to HubSpotSearch", () => {
    render(<HubSpotTest />);
    expect(
      screen.getByRole("heading", { name: "HubSpot Integration Test" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/tests the HubSpotSearch functionality with mock data/i),
    ).toBeInTheDocument();

    const search = screen.getByTestId("mock-hubspot-search");
    fireEvent.click(search);
    expect(logSpy).toHaveBeenCalledWith("Test search results:", [{ id: "test-1" }]);
    expect(logSpy).toHaveBeenCalledWith("Test filters:", { status: "all" });
    expect(logSpy).toHaveBeenCalledWith("Test sort:", { field: "name" });
  });

  it("logs on test button click", () => {
    render(<HubSpotTest />);
    fireEvent.click(screen.getByRole("button", { name: "Test Button" }));
    expect(logSpy).toHaveBeenCalledWith("Test button clicked");
  });
});
