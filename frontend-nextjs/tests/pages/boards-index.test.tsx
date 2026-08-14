/**
 * BoardsListPage tests (pages/boards/index.tsx, was 0% coverage)
 *
 * Covers: loading / list / empty states, board card links, and the
 * create-board flow (open, enter key, validation, submit, pending state).
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import BoardsListPage from "@/pages/boards/index";

// pages/boards/index.tsx omits the React default import (fine under Next's
// automatic JSX runtime), but ts-jest compiles classic JSX which expects a
// React identifier in scope. Expose it globally for the page module.
(global as any).React = React;

const mockUseBoards = jest.fn();
const mockUseCreateBoard = jest.fn();
const mockMutateAsync = jest.fn();

jest.mock("@/hooks/useBoard", () => ({
  useBoards: () => mockUseBoards(),
  useCreateBoard: () => mockUseCreateBoard(),
}));

const BOARDS = [
  {
    id: "b1",
    name: "Sprint 14",
    description: "Current sprint board",
    created_at: "2026-08-01T12:00:00Z",
  },
  { id: "b2", name: "Hiring", description: null, created_at: "2026-08-02T12:00:00Z" },
];

describe("BoardsListPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseBoards.mockReturnValue({ data: BOARDS, isLoading: false });
    mockUseCreateBoard.mockReturnValue({ mutateAsync: mockMutateAsync, isPending: false });
    mockMutateAsync.mockResolvedValue({ id: "b3" });
  });

  test("shows the loading state", () => {
    mockUseBoards.mockReturnValue({ data: undefined, isLoading: true });
    render(<BoardsListPage />);
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  test("renders board cards with links and dates", () => {
    render(<BoardsListPage />);
    expect(screen.getByText("Kanban Boards")).toBeInTheDocument();
    expect(screen.getByText("Sprint 14")).toBeInTheDocument();
    expect(screen.getByText("Current sprint board")).toBeInTheDocument();
    expect(screen.getByText("Hiring")).toBeInTheDocument();
    expect(screen.queryByText("null")).not.toBeInTheDocument();

    const link = screen.getByText("Sprint 14").closest("a");
    expect(link?.getAttribute("href")).toBe("/boards/b1");
    expect(screen.getAllByText(/Created /).length).toBe(2);
  });

  test("shows the empty state when there are no boards", () => {
    mockUseBoards.mockReturnValue({ data: [], isLoading: false });
    render(<BoardsListPage />);
    expect(screen.getByText(/No boards yet/)).toBeInTheDocument();
  });

  test("shows the empty state when data is undefined", () => {
    mockUseBoards.mockReturnValue({ data: undefined, isLoading: false });
    render(<BoardsListPage />);
    expect(screen.getByText(/No boards yet/)).toBeInTheDocument();
  });

  test("create flow: opens the form, validates, and submits via button", async () => {
    render(<BoardsListPage />);
    fireEvent.click(screen.getByRole("button", { name: /New Board/ }));

    const input = screen.getByPlaceholderText("Board name (e.g. Sprint 14)");
    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();

    // Empty name → early return, no mutation.
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    expect(mockMutateAsync).not.toHaveBeenCalled();

    fireEvent.change(input, { target: { value: "  Marketing  " } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(mockMutateAsync).toHaveBeenCalledWith({ name: "Marketing" }));
    await waitFor(() => expect(screen.queryByPlaceholderText(/Board name/)).not.toBeInTheDocument());
  });

  test("create flow: Enter key submits the form", async () => {
    render(<BoardsListPage />);
    fireEvent.click(screen.getByRole("button", { name: /New Board/ }));

    const input = screen.getByPlaceholderText("Board name (e.g. Sprint 14)");
    fireEvent.change(input, { target: { value: "Sales" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => expect(mockMutateAsync).toHaveBeenCalledWith({ name: "Sales" }));
  });

  test("Enter key with an empty name does nothing", () => {
    render(<BoardsListPage />);
    fireEvent.click(screen.getByRole("button", { name: /New Board/ }));

    fireEvent.keyDown(screen.getByPlaceholderText(/Board name/), { key: "Enter" });
    expect(mockMutateAsync).not.toHaveBeenCalled();
  });

  test("create button is disabled while the mutation is pending", () => {
    mockUseCreateBoard.mockReturnValue({ mutateAsync: mockMutateAsync, isPending: true });
    render(<BoardsListPage />);
    fireEvent.click(screen.getByRole("button", { name: /New Board/ }));

    fireEvent.change(screen.getByPlaceholderText(/Board name/), { target: { value: "Ops" } });
    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();
  });

  test("cancel closes the create form", () => {
    render(<BoardsListPage />);
    fireEvent.click(screen.getByRole("button", { name: /New Board/ }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByPlaceholderText(/Board name/)).not.toBeInTheDocument();
  });
});
