/** Learning source selection: email and native chat are explicitly typed. */
import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import LearningPage from "@/pages/learning";
import * as learningApi from "@/lib/conversation-learning-api";

const mockReplace = jest.fn();
jest.mock("next/router", () => ({
  useRouter: () => ({
    query: {},
    replace: mockReplace,
    pathname: "/learning",
  }),
}));

jest.mock("@/components/learning/ConversationLearningReview", () => {
  const React = require("react");
  return {
    ConversationLearningReview: (props: any) => React.createElement(
      "div",
      {
        "data-testid": "review",
        "data-thread": props.threadId,
        "data-source": props.sourceKind,
      },
    ),
  };
});

describe("LearningPage source selection", () => {
  beforeEach(() => {
    mockReplace.mockClear();
    jest.spyOn(learningApi, "listLearningThreads").mockResolvedValue([
      { thread_id: "email-1", source_kind: "email", subject: "Email thread",
        message_count: 2, last_at: "2026-01-01T00:00:00Z" },
      { thread_id: "chat-1", source_kind: "native_chat", subject: "Chat thread",
        message_count: 3, last_at: "2026-01-02T00:00:00Z" },
    ]);
  });

  test("labels email and chat, requires explicit selection, and passes typed source", async () => {
    render(<LearningPage />);
    const select = await screen.findByTestId("learning-thread-select");
    expect(screen.getByText(/Email · Email thread/)).toBeInTheDocument();
    expect(screen.getByText(/Chat · Chat thread/)).toBeInTheDocument();
    expect(screen.queryByTestId("review")).not.toBeInTheDocument();

    fireEvent.change(select, {
      target: { value: JSON.stringify(["native_chat", "chat-1"]) },
    });
    await waitFor(() => {
      expect(screen.getByTestId("review")).toHaveAttribute(
        "data-source", "native_chat");
    });
    expect(screen.getByTestId("review")).toHaveAttribute("data-thread", "chat-1");
    expect(mockReplace).toHaveBeenCalledWith(
      { pathname: "/learning", query: { thread: "chat-1", source_kind: "native_chat" } },
      undefined,
      { shallow: true },
    );

    fireEvent.change(select, {
      target: { value: JSON.stringify(["email", "email-1"]) },
    });
    await waitFor(() => {
      expect(screen.getByTestId("review")).toHaveAttribute("data-source", "email");
    });

    fireEvent.change(select, { target: { value: "" } });
    await waitFor(() => {
      expect(screen.queryByTestId("review")).not.toBeInTheDocument();
    });
  });
});
