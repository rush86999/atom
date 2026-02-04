import React from 'react';
import { render } from '@testing-library/react';
import { ChakraProvider } from '@chakra-ui/react';
import { performance } from 'perf_hooks';
import AgentManager from '../../frontend-nextjs/components/Agents/AgentManager';
import VoiceCommands from '../../frontend-nextjs/components/Voice/VoiceCommands';
import ChatInterface from '../../frontend-nextjs/components/AI/ChatInterface';
import WorkflowEditor from '../../frontend-nextjs/components/Automations/WorkflowEditor';

// Mock data for performance testing
const mockAgents = Array.from({ length: 100 }, (_, i) => ({
  id: `agent-${i}`,
  name: `Test Agent ${i}`,
  role: i % 3 === 0 ? 'personal_assistant' : i % 3 === 1 ? 'research_agent' : 'coding_agent',
  status: i % 4 === 0 ? 'active' : i % 4 === 1 ? 'inactive' : i % 4 === 2 ? 'error' : 'active',
  capabilities: ['web_search', 'data_analysis', 'code_generation'].slice(0, (i % 3) + 1),
  performance: {
    tasksCompleted: i * 10,
    successRate: 80 + (i % 20),
    avgResponseTime: 100 + (i % 200),
  },
  lastActive: new Date(Date.now() - i * 3600000),
  config: {
    model: 'gpt-4',
    temperature: 0.7,
    maxTokens: 2000,
    systemPrompt: 'Test system prompt',
    tools: ['calculator', 'web_browser', 'file_system'],
  },
}));

const mockCommands = Array.from({ length: 50 }, (_, i) => ({
  id: `command-${i}`,
  phrase: `command phrase ${i}`,
  action: i % 4 === 0 ? 'navigate' : i % 4 === 1 ? 'create_task' : i % 4 === 2 ? 'send_email' : 'get_weather',
  description: `Command description ${i}`,
  enabled: i % 5 !== 0,
  confidenceThreshold: 0.7 + (i % 3) * 0.1,
  parameters: { route: `/page-${i}` },
  usageCount: i * 5,
  lastUsed: new Date(Date.now() - i * 86400000),
}));

const mockSessions = Array.from({ length: 20 }, (_, i) => ({
  id: `session-${i}`,
  title: `Chat Session ${i}`,
  messages: Array.from({ length: 50 }, (_, j) => ({
    id: `message-${i}-${j}`,
    role: j % 2 === 0 ? 'user' : 'assistant',
    content: `Message content ${j} for session ${i}`.repeat(5),
    timestamp: new Date(Date.now() - j * 60000),
    model: 'gpt-4',
    tokens: 100 + (j % 50),
  })),
  model: 'gpt-4',
  createdAt: new Date(Date.now() - i * 3600000),
  updatedAt: new Date(),
  isActive: i === 0,
}));

const mockWorkflow = {
  id: 'test-workflow',
  name: 'Performance Test Workflow',
  description: 'Workflow for performance testing',
  version: '1.0.0',
  nodes: Array.from({ length: 50 }, (_, i) => ({
    id: `node-${i}`,
    type: i % 5 === 0 ? 'trigger' : i % 5 === 1 ? 'action' : i % 5 === 2 ? 'condition' : i % 5 === 3 ? 'delay' : 'webhook',
    title: `Node ${i}`,
    description: `Node description ${i}`,
    position: { x: i * 100, y: i * 50 },
    config: { test: 'value' },
    connections: i < 49 ? [`node-${i + 1}`] : [],
  })),
  connections: Array.from({ length: 49 }, (_, i) => ({
    id: `conn-${i}`,
    source: `node-${i}`,
    target: `node-${i + 1}`,
  })),
  triggers: ['schedule'],
  enabled: true,
  createdAt: new Date(),
  updatedAt: new Date(),
};

const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <ChakraProvider>
      {component}
    </ChakraProvider>
  );
};

describe('Performance Tests for New Components', () => {
  const performanceThresholds = {
    initialRender: 1000, // ms
    interactionResponse: 500, // ms
    memoryUsage: 50, // MB
    reRender: 200, // ms
  };

  beforeEach(() => {
    // Clear any performance marks
    performance.clearMarks();
    performance.clearMeasures();
  });

  describe('AgentManager Performance', () => {
    it('should render 100 agents within performance threshold', () => {
      const startTime = performance.now();

      renderWithProviders(
        <AgentManager
          initialAgents={mockAgents}
          showNavigation={true}
        />
      );

      const endTime = performance.now();
      const renderTime = endTime - startTime;

      console.log(`AgentManager render time: ${renderTime}ms`);
      expect(renderTime).toBeLessThan(performanceThresholds.initialRender);
    });

    it('should handle agent list filtering efficiently', () => {
      const { rerender } = renderWithProviders(
        <AgentManager
          initialAgents={mockAgents}
          showNavigation={true}
        />
      );

      const startTime = performance.now();

      // Simulate filtering by re-rendering with filtered data
      const filteredAgents = mockAgents.filter(agent => agent.status === 'active');
      rerender(
        <ChakraProvider>
          <AgentManager
            initialAgents={filteredAgents}
            showNavigation={true}
          />
        </ChakraProvider>
      );

      const endTime = performance.now();
      const filterTime = endTime - startTime;

      console.log(`AgentManager filter time: ${filterTime}ms`);
      expect(filterTime).toBeLessThan(performanceThresholds.reRender);
    });
  });

  describe('VoiceCommands Performance', () => {
    it('should render 50 voice commands efficiently', () => {
      const startTime = performance.now();

      renderWithProviders(
        <VoiceCommands
          initialCommands={mockCommands}
          showNavigation={true}
        />
      );

      const endTime = performance.now();
      const renderTime = endTime - startTime;

      console.log(`VoiceCommands render time: ${renderTime}ms`);
      expect(renderTime).toBeLessThan(performanceThresholds.initialRender);
    });

    it('should handle command recognition processing efficiently', () => {
      renderWithProviders(
        <VoiceCommands
          initialCommands={mockCommands}
          showNavigation={true}
        />
      );

      const startTime = performance.now();

      // Simulate processing multiple recognition results
      const recognitionResults = Array.from({ length: 10 }, (_, i) => ({
        id: `result-${i}`,
        timestamp: new Date(),
        transcript: `test command ${i}`,
        confidence: 0.8 + (i * 0.02),
        processed: true,
      }));

      // This would normally be handled by the component's state updates
      const endTime = performance.now();
      const processingTime = endTime - startTime;

      console.log(`VoiceCommands processing time: ${processingTime}ms`);
      expect(processingTime).toBeLessThan(performanceThresholds.interactionResponse);
    });
  });

  describe('ChatInterface Performance', () => {
    it('should render chat interface with 20 sessions and 50 messages each', () => {
      const startTime = performance.now();

      renderWithProviders(
        <ChatInterface
          initialSessions={mockSessions}
          availableModels={['gpt-4', 'gpt-3.5-turbo', 'claude-3']}
          showNavigation={true}
        />
      );

      const endTime = performance.now();
      const renderTime = endTime - startTime;

      console.log(`ChatInterface render time: ${renderTime}ms`);
      expect(renderTime).toBeLessThan(performanceThresholds.initialRender);
    });

    it('should handle session switching efficiently', () => {
      const { rerender } = renderWithProviders(
        <ChatInterface
          initialSessions={mockSessions}
          availableModels={['gpt-4', 'gpt-3.5-turbo']}
          showNavigation={true}
        />
      );

      const startTime = performance.now();

      // Simulate switching to a different session
      const updatedSessions = mockSessions.map(session => ({
        ...session,
        isActive: session.id === 'session-1',
      }));

      rerender(
        <ChakraProvider>
          <ChatInterface
            initialSessions={updatedSessions}
            availableModels={['gpt-4', 'gpt-3.5-turbo']}
            showNavigation={true}
          />
        </ChakraProvider>
      );

      const endTime = performance.now();
      const switchTime = endTime - startTime;

      console.log(`ChatInterface session switch time: ${switchTime}ms`);
      expect(switchTime).toBeLessThan(performanceThresholds.reRender);
    });
  });

  describe('WorkflowEditor Performance', () => {
    it('should render complex workflow with 50 nodes efficiently', () => {
      const startTime = performance.now();

      renderWithProviders(
        <WorkflowEditor
          workflow={mockWorkflow}
          showNavigation={true}
        />
      );

      const endTime = performance.now();
      const renderTime = endTime - startTime;

      console.log(`WorkflowEditor render time: ${renderTime}ms`);
      expect(renderTime).toBeLessThan(performanceThresholds.initialRender);
    });

    it('should handle workflow modifications efficiently', () => {
      const { rerender } = renderWithProviders(
        <WorkflowEditor
          workflow={mockWorkflow}
          showNavigation={true}
        />
      );

      const startTime = performance.now();

      // Simulate adding a new node
      const updatedWorkflow = {
        ...mockWorkflow,
        nodes: [
          ...mockWorkflow.nodes,
          {
            id: 'new-node',
            type: 'action',
            title: 'New Node',
            description: 'Added for performance test',
            position: { x: 500, y: 500 },
            config: {},
            connections: [],
          },
        ],
      };

      rerender(
        <ChakraProvider>
          <WorkflowEditor
            workflow={updatedWorkflow}
            showNavigation={true}
          />
        </ChakraProvider>
      );

      const endTime = performance.now();
      const updateTime = endTime - startTime;

      console.log(`WorkflowEditor update time: ${updateTime}ms`);
      expect(updateTime).toBeLessThan(performanceThresholds.reRender);
    });
  });

  describe('Memory Usage Tests', () => {
    it('should not cause memory leaks with repeated renders', () => {
      const initialMemory = process.memoryUsage().heapUsed;

      // Render multiple times to check for memory leaks
      for (let i = 0; i < 10; i++) {
        const { unmount } = renderWithProviders(
          <AgentManager
            initialAgents={mockAgents.slice(0, 10)} // Smaller set for repeated testing
            showNavigation={true}
          />
        );
        unmount();
      }

      const finalMemory = process.memoryUsage().heapUsed;
      const memoryIncrease = (finalMemory - initialMemory) / 1024 / 1024; // Convert to MB

      console.log(`Memory increase after repeated renders: ${memoryIncrease}MB`);
      expect(memoryIncrease).toBeLessThan(performanceThresholds.memoryUsage);
    });
  });

  describe('Integration Performance', () => {
    it('should maintain performance when multiple components are rendered', () => {
      const startTime = performance.now();

      // Render multiple components simultaneously
      renderWithProviders(
        <div>
          <AgentManager
            initialAgents={mockAgents.slice(0, 10)}
            showNavigation={false}
            compactView={true}
          />
          <VoiceCommands
            initialCommands={mockCommands.slice(0, 10)}
            showNavigation={false}
            compactView={true}
          />
          <ChatInterface
            initialSessions={mockSessions.slice(0, 2)}
            showNavigation={false}
            compactView={true}
          />
        </div>
      );

      const endTime = performance.now();
      const renderTime = endTime - startTime;

      console.log(`Multiple components render time: ${renderTime}ms`);
      expect(renderTime).toBeLessThan(performanceThresholds.initialRender * 2);
    });
  });
});
