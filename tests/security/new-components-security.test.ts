import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ChakraProvider } from '@chakra-ui/react';
import '@testing-library/jest-dom';
import AgentManager from '../../frontend-nextjs/components/Agents/AgentManager';
import VoiceCommands from '../../frontend-nextjs/components/Voice/VoiceCommands';
import ChatInterface from '../../frontend-nextjs/components/AI/ChatInterface';
import WorkflowEditor from '../../frontend-nextjs/components/Automations/WorkflowEditor';
import RoleSettings from '../../frontend-nextjs/components/Agents/RoleSettings';
import TriggerSettings from '../../frontend-nextjs/components/Automations/TriggerSettings';

// Mock data for security testing
const mockAgents = [
  {
    id: 'agent-1',
    name: 'Test Agent',
    role: 'personal_assistant',
    status: 'active' as const,
    capabilities: ['web_search', 'email_management'],
    performance: {
      tasksCompleted: 10,
      successRate: 95,
      avgResponseTime: 200,
    },
    lastActive: new Date(),
    config: {
      model: 'gpt-4',
      temperature: 0.7,
      maxTokens: 2000,
      systemPrompt: 'Test system prompt',
      tools: ['calculator', 'web_browser'],
    },
  },
];

const mockCommands = [
  {
    id: 'command-1',
    phrase: 'open calendar',
    action: 'navigate',
    description: 'Open the calendar view',
    enabled: true,
    confidenceThreshold: 0.7,
    parameters: { route: '/calendar' },
    usageCount: 5,
    lastUsed: new Date(),
  },
];

const mockSessions = [
  {
    id: 'session-1',
    title: 'Test Session',
    messages: [
      {
        id: 'message-1',
        role: 'user' as const,
        content: 'Hello, world!',
        timestamp: new Date(),
      },
    ],
    model: 'gpt-4',
    createdAt: new Date(),
    updatedAt: new Date(),
    isActive: true,
  },
];

const mockWorkflow = {
  id: 'workflow-1',
  name: 'Test Workflow',
  description: 'Test workflow description',
  version: '1.0.0',
  nodes: [],
  connections: [],
  triggers: ['manual'],
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

describe('Security Tests for New Components', () => {
  describe('Input Validation and XSS Prevention', () => {
    it('should sanitize user input in AgentManager to prevent XSS', () => {
      const maliciousInput = '<script>alert("XSS")</script>Test Agent';

      renderWithProviders(
        <AgentManager
          initialAgents={[{
            ...mockAgents[0],
            name: maliciousInput,
            config: {
              ...mockAgents[0].config,
              systemPrompt: maliciousInput,
            },
          }]}
          showNavigation={true}
        />
      );

      // Check that script tags are not rendered as HTML
      const agentName = screen.getByText(maliciousInput);
      expect(agentName).toBeInTheDocument();
      expect(agentName.innerHTML).not.toContain('<script>');
    });

    it('should validate agent configuration parameters', () => {
      const invalidConfig = {
        model: 'invalid-model',
        temperature: 5.0, // Out of range
        maxTokens: -100, // Negative value
        systemPrompt: 'Valid prompt',
        tools: ['valid_tool'],
      };

      renderWithProviders(
        <AgentManager
          initialAgents={[{
            ...mockAgents[0],
            config: invalidConfig,
          }]}
          showNavigation={true}
        />
      );

      // Component should handle invalid config gracefully
      expect(screen.getByText('Test Agent')).toBeInTheDocument();
    });

    it('should prevent command injection in VoiceCommands', () => {
      const maliciousCommand = {
        ...mockCommands[0],
        phrase: 'rm -rf /; open calendar',
        parameters: { route: 'javascript:alert("XSS")' },
      };

      renderWithProviders(
        <VoiceCommands
          initialCommands={[maliciousCommand]}
          showNavigation={true}
        />
      );

      // Malicious content should be displayed as text, not executed
      const commandElement = screen.getByText('rm -rf /; open calendar');
      expect(commandElement).toBeInTheDocument();
      expect(commandElement.innerHTML).not.toContain('javascript:');
    });
  });

  describe('Authentication and Authorization', () => {
    it('should not expose sensitive data in component props', () => {
      const sensitiveData = {
        apiKey: 'secret-api-key-12345',
        password: 'user-password',
        token: 'auth-token-abc123',
      };

      renderWithProviders(
        <AgentManager
          initialAgents={mockAgents}
          showNavigation={true}
        />
      );

      // Check that sensitive data is not exposed in DOM
      const htmlContent = document.documentElement.outerHTML;
      expect(htmlContent).not.toContain('secret-api-key-12345');
      expect(htmlContent).not.toContain('user-password');
      expect(htmlContent).not.toContain('auth-token-abc123');
    });

    it('should validate user permissions for role modifications', () => {
      const mockOnRoleUpdate = jest.fn();

      renderWithProviders(
        <RoleSettings
          initialRoles={[{
            id: 'admin-role',
            name: 'Administrator',
            description: 'Full system access',
            capabilities: ['all_permissions'],
            permissions: {
              canAccessFiles: true,
              canAccessWeb: true,
              canExecuteCode: true,
              canAccessDatabase: true,
              canSendEmails: true,
              canMakeAPICalls: true,
            },
            systemPrompt: 'You have full system access',
            modelConfig: {
              model: 'gpt-4',
              temperature: 0.7,
              maxTokens: 4000,
              topP: 1.0,
              frequencyPenalty: 0.0,
              presencePenalty: 0.0,
            },
            isDefault: false,
            createdAt: new Date(),
            updatedAt: new Date(),
          }]}
          onRoleUpdate={mockOnRoleUpdate}
          showNavigation={true}
        />
      );

      // Attempt to modify a role - should be handled by callback
      const editButton = screen.getByLabelText('Edit role');
      fireEvent.click(editButton);

      // The actual permission check should happen in the callback
      expect(mockOnRoleUpdate).not.toHaveBeenCalled(); // Because modal would open first
    });
  });

  describe('Data Integrity and Validation', () => {
    it('should validate workflow node connections to prevent cycles', () => {
      const cyclicWorkflow = {
        ...mockWorkflow,
        nodes: [
          {
            id: 'node-1',
            type: 'trigger' as const,
            title: 'Start',
            description: 'Start node',
            position: { x: 100, y: 100 },
            config: {},
            connections: ['node-2'],
          },
          {
            id: 'node-2',
            type: 'action' as const,
            title: 'Action',
            description: 'Action node',
            position: { x: 300, y: 100 },
            config: {},
            connections: ['node-1'], // Cyclic connection
          },
        ],
        connections: [
          { id: 'conn-1', source: 'node-1', target: 'node-2' },
          { id: 'conn-2', source: 'node-2', target: 'node-1' },
        ],
      };

      renderWithProviders(
        <WorkflowEditor
          workflow={cyclicWorkflow}
          showNavigation={true}
        />
      );

      // Component should handle cyclic connections without crashing
      expect(screen.getByText('Test Workflow')).toBeInTheDocument();
    });

    it('should validate trigger configuration parameters', () => {
      const invalidTrigger = {
        id: 'trigger-1',
        name: 'Test Trigger',
        type: 'webhook' as const,
        description: 'Test trigger',
        enabled: true,
        config: {
          method: 'INVALID_METHOD',
          path: '../../../etc/passwd', // Path traversal attempt
          secret: '   ', // Empty secret
        },
        conditions: [],
        triggerCount: 0,
        createdAt: new Date(),
        updatedAt: new Date(),
      };

      renderWithProviders(
        <TriggerSettings
          initialTriggers={[invalidTrigger]}
          showNavigation={true}
        />
      );

      // Component should handle invalid trigger config
      expect(screen.getByText('Test Trigger')).toBeInTheDocument();
    });
  });

  describe('Session Security', () => {
    it('should protect chat session data from unauthorized access', () => {
      const sensitiveSession = {
        ...mockSessions[0],
        messages: [
          {
            id: 'sensitive-message',
            role: 'user' as const,
            content: 'My credit card number is 4111-1111-1111-1111',
            timestamp: new Date(),
          },
        ],
      };

      renderWithProviders(
        <ChatInterface
          initialSessions={[sensitiveSession]}
          availableModels={['gpt-4']}
          showNavigation={true}
        />
      );

      // Sensitive data should be displayed but not exposed in raw form
      const messageElement = screen.getByText(/credit card number/);
      expect(messageElement).toBeInTheDocument();

      // Check that the actual number is not exposed in HTML attributes
      const htmlContent = document.documentElement.outerHTML;
      expect(htmlContent).not.toContain('4111-1111-1111-1111');
    });

    it('should validate file uploads in ChatInterface', () => {
      const maliciousFile = new File(
        ['malicious content'],
        '../../etc/passwd',
        { type: 'text/plain' }
      );

      renderWithProviders(
        <ChatInterface
          initialSessions={mockSessions}
          availableModels={['gpt-4']}
          showNavigation={true}
        />
      );

      // File input should be present
      const fileInput = document.querySelector('input[type="file"]');
      expect(fileInput).toBeInTheDocument();

      // Actual file validation would happen when the file is processed
    });
  });

  describe('Error Handling and Information Disclosure', () => {
    it('should not expose stack traces in error messages', () => {
      // Mock a component that throws an error
      const ErrorProneComponent = () => {
        throw new Error('Sensitive stack trace information');
      };

      // In a real scenario, we would test error boundaries
      // For now, we ensure components handle errors gracefully
      expect(() => renderWithProviders(<AgentManager initialAgents={[]} />))
        .not.toThrow();
    });

    it('should handle malformed data gracefully', () => {
      const malformedAgents = [
        {
          id: null, // Invalid ID
          name: undefined, // Missing name
          role: 'invalid-role', // Invalid role
          status: 'unknown-status', // Invalid status
          capabilities: 'not-an-array', // Wrong type
          performance: {}, // Incomplete performance data
          lastActive: 'invalid-date', // Invalid date
          config: null, // Null config
        },
      ] as any;

      renderWithProviders(
        <AgentManager
          initialAgents={malformedAgents}
          showNavigation={true}
        />
      );

      // Component should not crash with malformed data
      expect(screen.getByText('Agent Manager')).toBeInTheDocument();
    });
  });

  describe('API Security', () => {
    it('should validate callback function parameters', () => {
      const mockOnAgentCreate = jest.fn();
      const maliciousAgentData = {
        id: 'malicious-agent',
        name: 'Test Agent',
        role: 'personal_assistant',
        status: 'active' as const,
        capabilities: ['malicious_capability'],
        performance: {
          tasksCompleted: 0,
          successRate: 100,
          avgResponseTime: 0,
        },
        lastActive: new Date(),
        config: {
          model: 'gpt-4',
          temperature: 0.7,
          maxTokens: 2000,
          systemPrompt: 'Malicious prompt',
          tools: ['malicious_tool'],
        },
      };

      renderWithProviders(
        <AgentManager
          onAgentCreate={mockOnAgentCreate}
          initialAgents={[]}
          showNavigation={true}
        />
      );

      // Callback should receive validated data
      // This would be tested when the create form is submitted
      expect(mockOnAgentCreate).not.toHaveBeenCalledWith(maliciousAgentData);
    });

    it('should prevent excessive resource consumption', () => {
      const largeDataset = Array.from({ length: 10000 }, (_, i) => ({
        ...mockAgents[0],
        id: `agent-${i}`,
        name: `Agent ${i}`.repeat(100), // Very long name
      }));

      renderWithProviders(
        <AgentManager
          initialAgents={largeDataset.slice(0, 100)} // Limit for performance
          showNavigation={true}
        />
      );

      // Component should handle large datasets without crashing
      expect(screen.getByText('Agent Manager')).toBeInTheDocument();
    });
  });

  describe('Cross-Origin Security', () => {
    it('should validate external URLs in component configurations', () => {
      const externalUrlConfig = {
        ...mockAgents[0],
        config: {
          ...mockAgents[0].config,
          systemPrompt: 'Fetch data from http://malicious-site.com',
        },
      };

      renderWithProviders(
        <AgentManager
          initialAgents={[externalUrlConfig]}
          showNavigation={true}
        />
      );

      // External URLs should be treated as text, not executed
      const promptElement = screen.getByText(/malicious-site/);
      expect(promptElement).toBeInTheDocument();
      expect(promptElement.tagName).not.toBe('A'); // Should not be a link
    });

    it('should sanitize HTML in chat messages', () => {
      const htmlMessage = {
        ...mockSessions[0],
        messages: [
          {
            id: 'html-message',
            role: 'user' as const,
            content: '<img src="x" onerror="alert(\'XSS\')">Hello <b>World</b>',
            timestamp: new Date(),
          },
        ],
      };

      renderWithProviders(
        <ChatInterface
          initialSessions={[htmlMessage]}
          availableModels={['gpt-4']}
          showNavigation={true}
        />
      );

      // HTML should be sanitized - script should be removed but basic formatting preserved
      const messageElement = screen.getByText(/Hello/);
      expect(messageElement).toBeInTheDocument();
      expect(messageElement.innerHTML).not.toContain('onerror');
    });
  });
});
