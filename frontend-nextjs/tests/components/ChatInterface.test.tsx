import React from "react";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  act,
} from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import ChatInterface from "../../components/AI/ChatInterface";
import "@testing-library/jest-dom";

// Mock the Chakra UI icons
jest.mock("@chakra-ui/icons", () => ({
  SettingsIcon: () => "SettingsIcon",
  DownloadIcon: () => "DownloadIcon",
  CopyIcon: () => "CopyIcon",
  DeleteIcon: () => "DeleteIcon",
  ArrowForwardIcon: () => "ArrowForwardIcon",
}));

// Mock the toast functionality
const mockToast = jest.fn();
jest.mock("@chakra-ui/react", () => {
  const originalModule = jest.requireActual("@chakra-ui/react");
  return {
    ...originalModule,
    useToast: () => mockToast,
  };
});

// Mock the clipboard API
Object.assign(navigator, {
  clipboard: {
    writeText: jest.fn(),
  },
});

const renderWithProviders = (component: React.ReactElement) => {
  return render(<ChakraProvider>{component}</ChakraProvider>);
};

const mockSession = {
  id: "1",
  title: "Test Chat",
  messages: [
    {
      id: "1",
      role: "user" as const,
      content: "Hello, how are you?",
      timestamp: new Date("2024-01-01T10:00:00Z"),
    },
    {
      id: "2",
      role: "assistant" as const,
      content: "I am doing well, thank you for asking!",
      timestamp: new Date("2024-01-01T10:00:01Z"),
      model: "gpt-4",
    },
  ],
  createdAt: new Date("2024-01-01T09:00:00Z"),
  updatedAt: new Date("2024-01-01T10:00:01Z"),
};

describe("ChatInterface", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test("renders with initial session", () => {
    renderWithProviders(<ChatInterface initialSession={mockSession} />);

    expect(screen.getByText("Test Chat")).toBeInTheDocument();
    expect(screen.getByText("2 messages")).toBeInTheDocument();
    expect(screen.getByText("Hello, how are you?")).toBeInTheDocument();
    expect(
      screen.getByText("I am doing well, thank you for asking!"),
    ).toBeInTheDocument();
    expect(screen.getByText("gpt-4")).toBeInTheDocument();
  });

  test("renders empty state when no messages", () => {
    const emptySession = {
      id: "1",
      title: "New Chat",
      messages: [],
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    renderWithProviders(<ChatInterface initialSession={emptySession} />);

    expect(screen.getByText("New Chat")).toBeInTheDocument();
    expect(screen.getByText("0 messages")).toBeInTheDocument();
    expect(screen.getByText("Start a conversation")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Type a message below to begin chatting with the AI assistant.",
      ),
    ).toBeInTheDocument();
  });

  test("sends message when send button is clicked", async () => {
    const mockOnSessionUpdate = jest.fn();
    renderWithProviders(
      <ChatInterface
        initialSession={mockSession}
        onSessionUpdate={mockOnSessionUpdate}
      />,
    );

    const input = screen.getByPlaceholderText("Type your message...");
    const sendButton = screen.getByLabelText("Send message");

    // Type a message
    fireEvent.change(input, { target: { value: "Test message" } });
    expect(input).toHaveValue("Test message");

    // Send the message
    await act(async () => {
      fireEvent.click(sendButton);
    });

    // Should show loading state
    expect(sendButton).toBeDisabled();
    expect(screen.getByText("AI is thinking...")).toBeInTheDocument();

    // Advance timers and wait for AI response
    await act(async () => {
      jest.advanceTimersByTime(2000);
    });

    await waitFor(() => {
      expect(mockOnSessionUpdate).toHaveBeenCalled();
    });
  });

  test("sends message when Enter key is pressed", async () => {
    const mockOnSessionUpdate = jest.fn();
    renderWithProviders(
      <ChatInterface
        initialSession={mockSession}
        onSessionUpdate={mockOnSessionUpdate}
      />,
    );

    const input = screen.getByPlaceholderText("Type your message...");
    fireEvent.change(input, { target: { value: "Test message" } });

    // Press Enter without Shift
    await act(async () => {
      fireEvent.keyPress(input, { key: "Enter", code: "Enter", charCode: 13 });
    });

    // Should show loading state
    await waitFor(() => {
      expect(screen.getByText("AI is thinking...")).toBeInTheDocument();
    });
  });

  test("does not send message when Shift+Enter is pressed", () => {
    const mockOnSessionUpdate = jest.fn();
    renderWithProviders(
      <ChatInterface
        initialSession={mockSession}
        onSessionUpdate={mockOnSessionUpdate}
      />,
    );

    const input = screen.getByPlaceholderText("Type your message...");
    fireEvent.change(input, { target: { value: "Test message" } });

    // Press Shift+Enter
    fireEvent.keyPress(input, {
      key: "Enter",
      code: "Enter",
      charCode: 13,
      shiftKey: true,
    });

    expect(mockOnSessionUpdate).not.toHaveBeenCalled();
  });

  test("disables send button when input is empty", () => {
    renderWithProviders(<ChatInterface initialSession={mockSession} />);

    const input = screen.getByPlaceholderText("Type your message...");
    const sendButton = screen.getByLabelText("Send message");

    // Initially should be disabled if no message
    fireEvent.change(input, { target: { value: "" } });
    expect(sendButton).toBeDisabled();

    // Should be enabled when there's a message
    fireEvent.change(input, { target: { value: "Test message" } });
    expect(sendButton).not.toBeDisabled();
  });

  test("copies message content", () => {
    renderWithProviders(<ChatInterface initialSession={mockSession} />);

    const copyButtons = screen.getAllByLabelText("Copy message");
    fireEvent.click(copyButtons[0]); // Copy first message

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      "Hello, how are you?",
    );
    expect(mockToast).toHaveBeenCalledWith({
      title: "Message copied",
      status: "success",
      duration: 2000,
      isClosable: true,
    });
  });

  test("opens settings modal", () => {
    renderWithProviders(<ChatInterface initialSession={mockSession} />);

    const settingsButton = screen.getByText("Settings");
    fireEvent.click(settingsButton);

    expect(screen.getByText("Chat Settings")).toBeInTheDocument();
  });

  test("changes model in settings", () => {
    renderWithProviders(<ChatInterface initialSession={mockSession} />);

    const settingsButton = screen.getByText("Settings");
    fireEvent.click(settingsButton);

    const modelSelect = screen.getByDisplayValue("gpt-4");
    fireEvent.change(modelSelect, { target: { value: "gpt-3.5-turbo" } });

    expect(modelSelect).toHaveValue("gpt-3.5-turbo");
  });

  test("adjusts temperature setting", () => {
    renderWithProviders(<ChatInterface initialSession={mockSession} />);

    const settingsButton = screen.getByText("Settings");
    fireEvent.click(settingsButton);

    const temperatureSlider = screen.getByDisplayValue("0.7");
    fireEvent.change(temperatureSlider, { target: { value: "0.5" } });

    expect(temperatureSlider).toHaveValue("0.5");
  });

  test("adjusts max tokens setting", () => {
    renderWithProviders(<ChatInterface initialSession={mockSession} />);

    const settingsButton = screen.getByText("Settings");
    fireEvent.click(settingsButton);

    const maxTokensSlider = screen.getByDisplayValue("1000");
    fireEvent.change(maxTokensSlider, { target: { value: "2000" } });

    expect(maxTokensSlider).toHaveValue("2000");
  });

  test("exports chat session", () => {
    // Mock URL.createObjectURL and URL.revokeObjectURL
    global.URL.createObjectURL = jest.fn();
    global.URL.revokeObjectURL = jest.fn();

    renderWithProviders(<ChatInterface initialSession={mockSession} />);

    const exportButton = screen.getByText("Export");
    fireEvent.click(exportButton);

    expect(global.URL.createObjectURL).toHaveBeenCalled();
  });

  test("clears chat session", () => {
    renderWithProviders(<ChatInterface initialSession={mockSession} />);

    const clearButton = screen.getByText("Clear");
    fireEvent.click(clearButton);

    expect(screen.getByText("New Chat")).toBeInTheDocument();
    expect(screen.getByText("0 messages")).toBeInTheDocument();
    expect(mockToast).toHaveBeenCalledWith({
      title: "Chat cleared",
      status: "info",
      duration: 2000,
      isClosable: true,
    });
  });

  test("handles file attachment", () => {
    renderWithProviders(<ChatInterface initialSession={mockSession} />);

    const attachButton = screen.getByText("Attach File");
    fireEvent.click(attachButton);

    // The file input should be triggered - look for file input specifically
    const fileInputs = screen.getAllByDisplayValue("");
    const fileInput = fileInputs.find(
      (input) => input.getAttribute("type") === "file",
    );
    expect(fileInput).toBeInTheDocument();
  });

  test("displays different styling for user and assistant messages", () => {
    renderWithProviders(<ChatInterface initialSession={mockSession} />);

    const userMessages = screen.getAllByText("user");
    const assistantMessages = screen.getAllByText("assistant");

    expect(userMessages).toHaveLength(1);
    expect(assistantMessages).toHaveLength(1);
  });

  test("handles tool calls display", () => {
    const sessionWithTools = {
      ...mockSession,
      messages: [
        {
          id: "3",
          role: "assistant" as const,
          content: "I used some tools to help with your request",
          timestamp: new Date("2024-01-01T10:00:02Z"),
          model: "gpt-4",
          toolCalls: [
            {
              id: "tool-1",
              name: "calculator",
              arguments: { expression: "2+2" },
              result: 4,
            },
          ],
        },
      ],
    };

    renderWithProviders(<ChatInterface initialSession={sessionWithTools} />);

    expect(screen.getByText("Tool Calls (1)")).toBeInTheDocument();
  });

  test("scrolls to bottom when new messages are added", () => {
    const mockScrollIntoView = jest.fn();
    Element.prototype.scrollIntoView = mockScrollIntoView;

    renderWithProviders(<ChatInterface initialSession={mockSession} />);

    expect(mockScrollIntoView).toHaveBeenCalled();
  });
});
