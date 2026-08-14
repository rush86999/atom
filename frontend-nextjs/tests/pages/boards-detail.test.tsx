/**
 * BoardPage tests (pages/boards/[boardId].tsx, was 0% coverage)
 *
 * Covers: loading fallback (loading / missing board), rendering the
 * dynamically imported KanbanBoard with the fetched board, and the
 * websocket subscription wiring for the boardId.
 */

import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import BoardPage from "@/pages/boards/[boardId]";

const mockUseBoard = jest.fn();
const mockUseBoardWebSocket = jest.fn();
let mockQuery: Record<string, string | undefined> = {};

jest.mock("next/router", () => ({
  useRouter: () => ({
    query: mockQuery,
    isReady: true,
    push: jest.fn(),
  }),
}));

jest.mock("@/hooks/useBoard", () => ({
  useBoard: (boardId: string | null) => mockUseBoard(boardId),
}));

jest.mock("@/hooks/useBoardWebSocket", () => ({
  useBoardWebSocket: (boardId: string | null) => mockUseBoardWebSocket(boardId),
}));

let latestKanbanProps: any = null;
jest.mock("@/components/boards/KanbanBoard", () => ({
  KanbanBoard: (props: any) => {
    latestKanbanProps = props;
    return <div data-testid="kanban-board">Board</div>;
  },
}));

const BOARD = {
  id: "b1",
  name: "Sprint 14",
  columns: [],
  tasks: [],
};

describe("BoardPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockQuery = { boardId: "b1" };
    latestKanbanProps = null;
    mockUseBoard.mockReturnValue({ data: BOARD, isLoading: false });
    mockUseBoardWebSocket.mockReturnValue(undefined);
  });

  test("shows the loading fallback while fetching", () => {
    mockUseBoard.mockReturnValue({ data: undefined, isLoading: true });
    render(<BoardPage />);
    expect(screen.getAllByText("Loading board…").length).toBeGreaterThan(0);
    expect(screen.queryByTestId("kanban-board")).not.toBeInTheDocument();
  });

  test("shows the loading fallback when there is no board data", () => {
    mockUseBoard.mockReturnValue({ data: undefined, isLoading: false });
    render(<BoardPage />);
    expect(screen.getAllByText("Loading board…").length).toBeGreaterThan(0);
  });

  test("renders KanbanBoard with the fetched board", async () => {
    render(<BoardPage />);
    await waitFor(() => expect(screen.getByTestId("kanban-board")).toBeInTheDocument());
    expect(latestKanbanProps.board).toEqual(BOARD);
  });

  test("subscribes to the board websocket with the boardId", () => {
    render(<BoardPage />);
    expect(mockUseBoard).toHaveBeenCalledWith("b1");
    expect(mockUseBoardWebSocket).toHaveBeenCalledWith("b1");
  });

  test("passes null when no boardId is in the query", () => {
    mockQuery = {};
    mockUseBoard.mockReturnValue({ data: undefined, isLoading: true });
    render(<BoardPage />);
    expect(mockUseBoard).toHaveBeenCalledWith(null);
    expect(mockUseBoardWebSocket).toHaveBeenCalledWith(null);
  });
});
