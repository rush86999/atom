import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ChakraProvider } from "@chakra-ui/react";
import AgentManager from "../../components/Agents/AgentManager";
import "@testing-library/jest-dom";

// Mock the Chakra UI icons
jest.mock("@chakra-ui/icons", () => ({
  AddIcon: () => "AddIcon",
  EditIcon: () => "EditIcon",
  DeleteIcon: () => "DeleteIcon",
  SettingsIcon: () => "SettingsIcon",
  TriangleUpIcon: () => "TriangleUpIcon",
  TriangleDownIcon: () => "TriangleDownIcon",
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

const renderWithProviders = (component: React.ReactElement) => {
  return render(<ChakraProvider>{component}</ChakraProvider>);
};

const mockAgents = [
  {
    id: "1",
    name: "Research Agent",
    role: "Research Specialist",
    status: "active" as const,
    capabilities: ["web_search", "document_analysis"],
    performance: {
      tasksCompleted: 45,
      successRate: 92,
      avgResponseTime: 1200,
    },
    config: {
      model: "gpt-4",
      temperature: 0.7,
      maxTokens: 1000,
    },
  },
  {
    id: "2",
    name: "Data Analyst",
    role: "Data Processing",
    status: "inactive" as const,
    capabilities: ["data_analysis", "financial_analysis"],
    performance: {
      tasksCompleted: 23,
      successRate: 87,
      avgResponseTime: 1800,
    },
    config: {
      model: "gpt-3.5-turbo",
      temperature: 0.5,
      maxTokens: 800,
    },
  },
];

describe("AgentManager", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test("renders without agents", () => {
    renderWithProviders(<AgentManager initialAgents={[]} />);

    expect(screen.getByText("Agent Manager")).toBeInTheDocument();
    expect(
      screen.getByText("Manage and monitor your AI agents"),
    ).toBeInTheDocument();
    expect(screen.getByText("No Agents Created")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Create your first agent to get started with multi-agent automation",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Create Agent")).toBeInTheDocument();
  });

  test("renders with agents", () => {
    renderWithProviders(<AgentManager initialAgents={mockAgents} />);

    expect(screen.getByText("Agent Manager")).toBeInTheDocument();
    expect(screen.getByText("Research Agent")).toBeInTheDocument();
    expect(screen.getByText("Data Analyst")).toBeInTheDocument();
    expect(screen.getByText("Research Specialist")).toBeInTheDocument();
    expect(screen.getByText("Data Processing")).toBeInTheDocument();
  });

  test("displays agent status correctly", () => {
    renderWithProviders(<AgentManager initialAgents={mockAgents} />);

    const activeBadge = screen.getByText("active");
    const inactiveBadge = screen.getByText("inactive");

    expect(activeBadge).toBeInTheDocument();
    expect(inactiveBadge).toBeInTheDocument();
  });

  test("displays agent capabilities", () => {
    renderWithProviders(<AgentManager initialAgents={mockAgents} />);

    expect(screen.getByText("web search")).toBeInTheDocument();
    expect(screen.getByText("document analysis")).toBeInTheDocument();
    expect(screen.getByText("data analysis")).toBeInTheDocument();
    expect(screen.getByText("financial analysis")).toBeInTheDocument();
  });

  test("displays performance metrics", () => {
    renderWithProviders(<AgentManager initialAgents={mockAgents} />);

    expect(screen.getByText("45")).toBeInTheDocument(); // tasks completed
    expect(screen.getByText("92%")).toBeInTheDocument(); // success rate
    expect(screen.getByText("1200ms")).toBeInTheDocument(); // avg response time
    expect(screen.getByText("23")).toBeInTheDocument(); // tasks completed
    expect(screen.getByText("87%")).toBeInTheDocument(); // success rate
    expect(screen.getByText("1800ms")).toBeInTheDocument(); // avg response time
  });

  test("opens create agent modal", async () => {
    renderWithProviders(<AgentManager initialAgents={[]} />);

    const createButton = screen.getByText("Create Agent");
    fireEvent.click(createButton);

    // Modal should open - check for modal content
    await waitFor(() => {
      expect(screen.getByText("Create New Agent")).toBeInTheDocument();
    });
  });

  test("starts and stops agents", () => {
    const mockOnAgentStart = jest.fn();
    const mockOnAgentStop = jest.fn();

    renderWithProviders(
      <AgentManager
        initialAgents={mockAgents}
        onAgentStart={mockOnAgentStart}
        onAgentStop={mockOnAgentStop}
      />,
    );

    // Find start button for inactive agent
    const startButtons = screen.getAllByLabelText("Start agent");
    fireEvent.click(startButtons[0]); // Should be the inactive agent

    expect(mockOnAgentStart).toHaveBeenCalledWith("2");

    // Find stop button for active agent
    const stopButtons = screen.getAllByLabelText("Stop agent");
    fireEvent.click(stopButtons[0]); // Should be the active agent

    expect(mockOnAgentStop).toHaveBeenCalledWith("1");
  });

  test("deletes agent", () => {
    const mockOnAgentDelete = jest.fn();

    renderWithProviders(
      <AgentManager
        initialAgents={mockAgents}
        onAgentDelete={mockOnAgentDelete}
      />,
    );

    const deleteButtons = screen.getAllByLabelText("Delete agent");
    fireEvent.click(deleteButtons[0]);

    expect(mockOnAgentDelete).toHaveBeenCalledWith("1");
    expect(mockToast).toHaveBeenCalledWith({
      title: "Agent Deleted",
      status: "success",
      duration: 2000,
      isClosable: true,
    });
  });

  test("handles empty agent list", () => {
    renderWithProviders(<AgentManager initialAgents={[]} />);

    expect(screen.getByText("No Agents Created")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Create your first agent to get started with multi-agent automation",
      ),
    ).toBeInTheDocument();
  });

  test("handles agent configuration changes", () => {
    renderWithProviders(<AgentManager initialAgents={mockAgents} />);

    const editButtons = screen.getAllByLabelText("Edit agent");
    fireEvent.click(editButtons[0]);

    // Should open edit modal
    expect(screen.getByText("Edit Agent")).toBeInTheDocument();
  });
});
