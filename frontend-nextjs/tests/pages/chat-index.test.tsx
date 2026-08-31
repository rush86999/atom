/**
 * ChatPage tests (pages/chat/index.tsx, was 0% coverage)
 *
 * Covers: session restore from localStorage (saved / "new" / none),
 * agent_id query parsing (string / array / absent), session-created and
 * session-selected persistence rules, and the mobile drawer toggles.
 */

import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react";
import ChatPage from "@/pages/chat";

let mockQuery: Record<string, string | string[] | undefined> = {};
jest.mock("next/router", () => ({
  useRouter: () => ({
    query: mockQuery,
    push: jest.fn(),
  }),
}));

let sidebarInstances: any[] = [];
jest.mock("@/components/chat/ChatHistorySidebar", () => ({
  __esModule: true,
  default: (props: any) => {
    sidebarInstances.push(props);
    return <div data-testid="chat-history-sidebar">History</div>;
  },
}));

let chatInstances: any[] = [];
jest.mock("@/components/chat/ChatInterface", () => ({
  __esModule: true,
  default: (props: any) => {
    chatInstances.push(props);
    return <div data-testid="chat-interface">Chat</div>;
  },
}));

let workspaceInstances: any[] = [];
jest.mock("@/components/chat/AgentWorkspace", () => ({
  __esModule: true,
  default: (props: any) => {
    workspaceInstances.push(props);
    return <div data-testid="agent-workspace">Workspace</div>;
  },
}));

const latest = (instances: any[]) => instances[instances.length - 1];

describe("ChatPage", () => {
  let getItemSpy: jest.SpyInstance;
  let setItemSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    mockQuery = {};
    sidebarInstances = [];
    chatInstances = [];
    workspaceInstances = [];
    getItemSpy = jest.spyOn(Storage.prototype, "getItem").mockReturnValue(undefined);
    setItemSpy = jest.spyOn(Storage.prototype, "setItem");
  });

  test("renders the three panes with no session and no agent by default", () => {
    render(<ChatPage />);
    expect(screen.getByTestId("chat-history-sidebar")).toBeInTheDocument();
    expect(screen.getByTestId("chat-interface")).toBeInTheDocument();
    expect(screen.getByTestId("agent-workspace")).toBeInTheDocument();

    const chat = latest(chatInstances);
    expect(chat.sessionId).toBeNull();
    expect(chat.initialAgentId).toBeNull();
  });

  test("restores the last active session from localStorage", () => {
    getItemSpy.mockReturnValue("sess-9");
    render(<ChatPage />);
    expect(getItemSpy).toHaveBeenCalledWith("atom_chat_session_id");
    expect(latest(chatInstances).sessionId).toBe("sess-9");
  });

  test('treats a saved "new" session as no session', () => {
    getItemSpy.mockReturnValue("new");
    render(<ChatPage />);
    expect(latest(chatInstances).sessionId).toBeNull();
  });

  test("passes a string agent_id query to the chat and workspace panes", () => {
    mockQuery = { agent_id: "agent-1" };
    render(<ChatPage />);
    expect(latest(chatInstances).initialAgentId).toBe("agent-1");
    expect(latest(workspaceInstances).initialAgentId).toBe("agent-1");
  });

  test("uses the first element of an array agent_id query", () => {
    mockQuery = { agent_id: ["agent-1", "agent-2"] };
    render(<ChatPage />);
    expect(latest(chatInstances).initialAgentId).toBe("agent-1");
  });

  test("onSessionCreated persists real session ids", () => {
    render(<ChatPage />);
    act(() => {
      latest(chatInstances).onSessionCreated("sess-5");
    });
    expect(setItemSpy).toHaveBeenCalledWith("atom_chat_session_id", "sess-5");
    expect(latest(chatInstances).sessionId).toBe("sess-5");
  });

  test.each(["new", "unknown"])("onSessionCreated does not persist %s", (id) => {
    render(<ChatPage />);
    act(() => {
      latest(chatInstances).onSessionCreated(id);
    });
    expect(setItemSpy).not.toHaveBeenCalled();
  });

  test("desktop sidebar selection persists the session", () => {
    render(<ChatPage />);
    act(() => {
      latest(sidebarInstances).onSelectSession("sess-7");
    });
    expect(setItemSpy).toHaveBeenCalledWith("atom_chat_session_id", "sess-7");
    expect(latest(chatInstances).sessionId).toBe("sess-7");
  });

  test('selecting "new" in the sidebar does not persist', () => {
    render(<ChatPage />);
    act(() => {
      latest(sidebarInstances).onSelectSession("new");
    });
    expect(setItemSpy).not.toHaveBeenCalled();
  });

  test("mobile history drawer opens, selects a session, and closes", () => {
    render(<ChatPage />);
    expect(screen.getAllByTestId("chat-history-sidebar").length).toBe(1);

    fireEvent.click(screen.getByRole("button", { name: "Toggle history" }));
    expect(screen.getAllByTestId("chat-history-sidebar").length).toBe(2);
    // Opening history also closes the workspace drawer.
    expect(screen.queryByLabelText("Close workspace")).not.toBeInTheDocument();

    act(() => {
      latest(sidebarInstances).onSelectSession("sess-8");
    });
    expect(setItemSpy).toHaveBeenCalledWith("atom_chat_session_id", "sess-8");
    expect(screen.getAllByTestId("chat-history-sidebar").length).toBe(1);

    // Reopen and close via the close button.
    fireEvent.click(screen.getByRole("button", { name: "Toggle history" }));
    fireEvent.click(screen.getByRole("button", { name: "Close history" }));
    expect(screen.getAllByTestId("chat-history-sidebar").length).toBe(1);
  });

  test("mobile workspace drawer opens and closes", () => {
    render(<ChatPage />);
    expect(screen.getAllByTestId("agent-workspace").length).toBe(1);

    fireEvent.click(screen.getByRole("button", { name: "Toggle workspace" }));
    expect(screen.getAllByTestId("agent-workspace").length).toBe(2);
    expect(screen.queryByLabelText("Close history")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Close workspace" }));
    expect(screen.getAllByTestId("agent-workspace").length).toBe(1);
  });
});

describe("ChatPage workspace auto-show/hide", () => {
  let getItemSpy: jest.SpyInstance;
  let setItemSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    mockQuery = {};
    sidebarInstances = [];
    chatInstances = [];
    workspaceInstances = [];
    getItemSpy = jest.spyOn(Storage.prototype, "getItem").mockReturnValue(undefined);
    setItemSpy = jest.spyOn(Storage.prototype, "setItem");
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test("starts open and toggles between panel and rail", () => {
    render(<ChatPage />);
    expect(latest(workspaceInstances).collapsed).toBe(false);

    act(() => {
      latest(workspaceInstances).onToggleCollapsed();
    });
    expect(latest(workspaceInstances).collapsed).toBe(true);

    act(() => {
      latest(workspaceInstances).onToggleCollapsed();
    });
    expect(latest(workspaceInstances).collapsed).toBe(false);
  });

  test("auto-opens on agent activity while collapsed and auto-hides after settle", () => {
    render(<ChatPage />);
    act(() => {
      latest(workspaceInstances).onToggleCollapsed(); // user closes
    });
    expect(latest(workspaceInstances).collapsed).toBe(true);

    // a new run streams in → panel auto-opens
    act(() => {
      latest(workspaceInstances).onAgentActivity("run_start");
    });
    expect(latest(workspaceInstances).collapsed).toBe(false);

    act(() => {
      latest(workspaceInstances).onAgentActivity("step");
      latest(workspaceInstances).onRunSettled();
    });
    // grace period: still open right after the run settles
    expect(latest(workspaceInstances).collapsed).toBe(false);

    act(() => {
      jest.advanceTimersByTime(8000);
    });
    expect(latest(workspaceInstances).collapsed).toBe(true);
  });

  test("manual close suppresses auto-open for the run; re-armed on run start", () => {
    render(<ChatPage />);
    act(() => {
      latest(workspaceInstances).onToggleCollapsed(); // manual close wins…
    });
    act(() => {
      latest(workspaceInstances).onAgentActivity("step"); // …same run stays closed
    });
    expect(latest(workspaceInstances).collapsed).toBe(true);

    act(() => {
      latest(workspaceInstances).onAgentActivity("run_start"); // new run re-arms
    });
    expect(latest(workspaceInstances).collapsed).toBe(false);
  });

  test("user interaction cancels the pending auto-hide", () => {
    render(<ChatPage />);
    act(() => {
      latest(workspaceInstances).onToggleCollapsed();
      latest(workspaceInstances).onAgentActivity("run_start");
      latest(workspaceInstances).onRunSettled();
      latest(workspaceInstances).onUserInteraction();
      jest.advanceTimersByTime(10000);
    });
    expect(latest(workspaceInstances).collapsed).toBe(false);
  });

  test("auto-hide off keeps the panel open after settle and persists the pref", () => {
    render(<ChatPage />);
    act(() => {
      latest(workspaceInstances).onAutoHideToggle(false);
    });
    expect(setItemSpy).toHaveBeenCalledWith("atom_workspace_autohide", "off");

    // separate act blocks so each callback is read from the latest render
    act(() => {
      latest(workspaceInstances).onToggleCollapsed();
    });
    act(() => {
      latest(workspaceInstances).onAgentActivity("run_start");
    });
    act(() => {
      latest(workspaceInstances).onRunSettled();
    });
    act(() => {
      jest.advanceTimersByTime(10000);
    });
    expect(latest(workspaceInstances).collapsed).toBe(false);
  });
});
