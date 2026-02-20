/**
 * Mock Data Fixtures for Atom Mobile Tests
 *
 * This file provides realistic mock data for testing all major entities:
 * - Agents (all maturity levels)
 * - Canvases (all 9 types)
 * - Workflows
 * - Episodes
 * - Users
 * - Conversations
 * - Messages
 * - Device Info
 * - Notifications
 */

// ============================================================================
// User Mocks
// ============================================================================

export const mockUser = {
  id: 'user-123',
  email: 'test@example.com',
  name: 'Test User',
  avatar: 'https://example.com/avatar.jpg',
  createdAt: '2024-01-01T00:00:00Z',
  updatedAt: '2024-01-01T00:00:00Z',
};

export const mockUsers = [mockUser];

// ============================================================================
// Agent Mocks
// ============================================================================

export const mockAgents = [
  {
    id: 'agent-student',
    name: 'Student Agent',
    description: 'Learning agent with limited capabilities',
    maturityLevel: 'STUDENT',
    capabilities: ['presentations'],
    isActive: true,
    prompt: 'You are a helpful assistant.',
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
  },
  {
    id: 'agent-intern',
    name: 'Intern Agent',
    description: 'Junior agent with supervised access',
    maturityLevel: 'INTERN',
    capabilities: ['presentations', 'streaming'],
    isActive: true,
    prompt: 'You are a helpful assistant.',
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
  },
  {
    id: 'agent-supervised',
    name: 'Supervised Agent',
    description: 'Agent with real-time supervision',
    maturityLevel: 'SUPERVISED',
    capabilities: ['presentations', 'streaming', 'stateChanges'],
    isActive: true,
    prompt: 'You are a helpful assistant.',
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
  },
  {
    id: 'agent-autonomous',
    name: 'Autonomous Agent',
    description: 'Fully autonomous agent',
    maturityLevel: 'AUTONOMOUS',
    capabilities: ['presentations', 'streaming', 'stateChanges', 'deletions'],
    isActive: true,
    prompt: 'You are a helpful assistant.',
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
  },
];

// ============================================================================
// Canvas Mocks (All 9 Types)
// ============================================================================

export const mockCanvases = [
  {
    id: 'canvas-generic',
    type: 'generic',
    title: 'Generic Canvas',
    html: '<div>Generic canvas content</div>',
    css: '.canvas { color: black; }',
    metadata: {
      created: '2024-01-01T00:00:00Z',
      agent: 'agent-autonomous',
    },
    isFavorite: false,
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
  },
  {
    id: 'canvas-docs',
    type: 'docs',
    title: 'Documentation Canvas',
    html: '<div>Documentation content</div>',
    css: '.docs { font-family: serif; }',
    metadata: {
      created: '2024-01-01T00:00:00Z',
      agent: 'agent-autonomous',
    },
    isFavorite: true,
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
  },
  {
    id: 'canvas-email',
    type: 'email',
    title: 'Email Canvas',
    html: '<div>Email draft</div>',
    css: '.email { padding: 10px; }',
    metadata: {
      created: '2024-01-01T00:00:00Z',
      agent: 'agent-intern',
    },
    isFavorite: false,
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
  },
  {
    id: 'canvas-sheets',
    type: 'sheets',
    title: 'Data Sheet Canvas',
    html: '<div>Data table</div>',
    css: '.sheets { border: 1px solid gray; }',
    metadata: {
      created: '2024-01-01T00:00:00Z',
      agent: 'agent-supervised',
    },
    isFavorite: false,
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
  },
  {
    id: 'canvas-orchestration',
    type: 'orchestration',
    title: 'Workflow Orchestration Canvas',
    html: '<div>Workflow steps</div>',
    css: '.orchestration { display: flex; }',
    metadata: {
      created: '2024-01-01T00:00:00Z',
      agent: 'agent-autonomous',
    },
    isFavorite: true,
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
  },
  {
    id: 'canvas-terminal',
    type: 'terminal',
    title: 'Terminal Canvas',
    html: '<div>Terminal output</div>',
    css: '.terminal { background: black; color: white; }',
    metadata: {
      created: '2024-01-01T00:00:00Z',
      agent: 'agent-autonomous',
    },
    isFavorite: false,
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
  },
  {
    id: 'canvas-coding',
    type: 'coding',
    title: 'Code Canvas',
    html: '<div>Code snippet</div>',
    css: '.coding { font-family: monospace; }',
    metadata: {
      created: '2024-01-01T00:00:00Z',
      agent: 'agent-supervised',
    },
    isFavorite: false,
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
  },
  {
    id: 'canvas-chart',
    type: 'chart',
    title: 'Chart Canvas',
    html: '<div>Chart visualization</div>',
    css: '.chart { width: 100%; }',
    metadata: {
      created: '2024-01-01T00:00:00Z',
      agent: 'agent-intern',
      chartType: 'line',
    },
    isFavorite: true,
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
  },
  {
    id: 'canvas-form',
    type: 'form',
    title: 'Form Canvas',
    html: '<div><input type="text" /></div>',
    css: '.form { padding: 20px; }',
    metadata: {
      created: '2024-01-01T00:00:00Z',
      agent: 'agent-supervised',
      fields: ['name', 'email', 'message'],
    },
    isFavorite: false,
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
  },
];

// ============================================================================
// Workflow Mocks
// ============================================================================

export const mockWorkflows = [
  {
    id: 'workflow-1',
    name: 'Daily Report Workflow',
    description: 'Generate daily analytics report',
    schema: {
      steps: [
        { id: 'step1', action: 'fetchData' },
        { id: 'step2', action: 'generateReport' },
        { id: 'step3', action: 'sendEmail' },
      ],
    },
    isActive: true,
    triggers: ['cron:0 9 * * *'],
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
  },
  {
    id: 'workflow-2',
    name: 'Onboarding Workflow',
    description: 'New user onboarding process',
    schema: {
      steps: [
        { id: 'step1', action: 'sendWelcomeEmail' },
        { id: 'step2', action: 'createProfile' },
        { id: 'step3', action: 'scheduleTraining' },
      ],
    },
    isActive: true,
    triggers: ['event:user.created'],
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
  },
];

export const mockWorkflowExecutions = [
  {
    id: 'execution-1',
    workflowId: 'workflow-1',
    status: 'completed',
    startedAt: '2024-01-01T09:00:00Z',
    completedAt: '2024-01-01T09:05:00Z',
    logs: [
      { timestamp: '2024-01-01T09:00:00Z', level: 'info', message: 'Starting workflow' },
      { timestamp: '2024-01-01T09:05:00Z', level: 'info', message: 'Workflow completed' },
    ],
  },
  {
    id: 'execution-2',
    workflowId: 'workflow-2',
    status: 'running',
    startedAt: '2024-01-01T10:00:00Z',
    completedAt: null,
    logs: [
      { timestamp: '2024-01-01T10:00:00Z', level: 'info', message: 'Starting workflow' },
    ],
  },
];

// ============================================================================
// Episode Mocks
// ============================================================================

export const mockEpisodes = [
  {
    id: 'episode-1',
    agentId: 'agent-autonomous',
    title: 'Customer Support Episode',
    summary: 'Resolved customer query about billing',
    segments: [
      {
        id: 'segment-1',
        timestamp: '2024-01-01T10:00:00Z',
        action: 'user_message',
        content: 'How do I view my bill?',
      },
      {
        id: 'segment-2',
        timestamp: '2024-01-01T10:00:30Z',
        action: 'agent_response',
        content: 'You can view your bill in Settings > Billing',
      },
    ],
    feedback: {
      rating: 0.8,
      helpful: true,
    },
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
  },
  {
    id: 'episode-2',
    agentId: 'agent-supervised',
    title: 'Data Analysis Episode',
    summary: 'Analyzed sales data for Q4',
    segments: [
      {
        id: 'segment-1',
        timestamp: '2024-01-01T11:00:00Z',
        action: 'user_message',
        content: 'Analyze Q4 sales',
      },
    ],
    feedback: {
      rating: 0.6,
      helpful: false,
    },
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T00:00:00Z',
  },
];

// ============================================================================
// Conversation Mocks
// ============================================================================

export const mockConversations = [
  {
    id: 'conversation-1',
    agentId: 'agent-autonomous',
    title: 'Customer Support Chat',
    lastMessage: 'How can I help you today?',
    lastMessageAt: '2024-01-01T10:00:00Z',
    messageCount: 15,
    isFavorite: true,
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T10:00:00Z',
  },
  {
    id: 'conversation-2',
    agentId: 'agent-supervised',
    title: 'Data Analysis',
    lastMessage: 'Here is the analysis report',
    lastMessageAt: '2024-01-01T09:00:00Z',
    messageCount: 8,
    isFavorite: false,
    createdAt: '2024-01-01T00:00:00Z',
    updatedAt: '2024-01-01T09:00:00Z',
  },
];

// ============================================================================
// Message Mocks
// ============================================================================

export const mockMessages = [
  {
    id: 'message-1',
    conversationId: 'conversation-1',
    role: 'user',
    content: 'How can I view my billing history?',
    timestamp: '2024-01-01T10:00:00Z',
    isStreaming: false,
  },
  {
    id: 'message-2',
    conversationId: 'conversation-1',
    role: 'assistant',
    content: 'You can view your billing history in the Settings > Billing section.',
    timestamp: '2024-01-01T10:00:30Z',
    isStreaming: false,
  },
  {
    id: 'message-3',
    conversationId: 'conversation-1',
    role: 'assistant',
    content: 'Is there anything else I can help with?',
    timestamp: '2024-01-01T10:01:00Z',
    isStreaming: false,
  },
];

// ============================================================================
// Device Info Mocks
// ============================================================================

export const mockDeviceInfo = {
  id: 'device-test-123',
  name: 'Test Device',
  platform: 'ios' as const,
  osVersion: '16.0',
  appVersion: '1.0.0',
  model: 'iPhone 14',
  manufacturer: 'Apple',
  totalMemory: 6 * 1024 * 1024 * 1024, // 6GB
  supportedCpuArchitectures: ['arm64'],
  deviceYearClass: 2022,
};

export const mockDevicePermissions = {
  camera: 'granted' as const,
  location: 'granted' as const,
  notifications: 'granted' as const,
  biometric: 'granted' as const,
};

// ============================================================================
// Notification Mocks
// ============================================================================

export const mockNotifications = [
  {
    id: 'notification-1',
    title: 'New Message',
    body: 'You have a new message from Agent',
    data: {
      conversationId: 'conversation-1',
      messageId: 'message-1',
    },
    timestamp: '2024-01-01T10:00:00Z',
    read: false,
  },
  {
    id: 'notification-2',
    title: 'Workflow Completed',
    body: 'Daily Report Workflow has completed',
    data: {
      workflowId: 'workflow-1',
      executionId: 'execution-1',
    },
    timestamp: '2024-01-01T09:05:00Z',
    read: true,
  },
];

// ============================================================================
// Form Data Mocks
// ============================================================================

export const mockFormData = {
  name: 'John Doe',
  email: 'john@example.com',
  message: 'This is a test message',
  terms: true,
};

// ============================================================================
// Chart Data Mocks
// ============================================================================

export const mockChartData = {
  line: {
    labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
    datasets: [{
      label: 'Sales',
      data: [100, 200, 150, 300, 250, 400],
    }],
  },
  bar: {
    labels: ['Q1', 'Q2', 'Q3', 'Q4'],
    datasets: [{
      label: 'Revenue',
      data: [1000, 1500, 1200, 1800],
    }],
  },
  pie: {
    labels: ['Product A', 'Product B', 'Product C'],
    datasets: [{
      data: [30, 45, 25],
    }],
  },
};

// ============================================================================
// Offline Sync Mocks
// ============================================================================

export const mockPendingActions = [
  {
    id: 'action-1',
    type: 'sendMessage',
    priority: 'high',
    payload: {
      conversationId: 'conversation-1',
      content: 'Offline message',
    },
    retryCount: 0,
    createdAt: '2024-01-01T10:00:00Z',
  },
  {
    id: 'action-2',
    type: 'submitForm',
    priority: 'normal',
    payload: {
      canvasId: 'canvas-form',
      formData: mockFormData,
    },
    retryCount: 2,
    createdAt: '2024-01-01T09:00:00Z',
  },
];

// ============================================================================
// Export All Mocks
// ============================================================================

export default {
  user: mockUser,
  users: mockUsers,
  agents: mockAgents,
  canvases: mockCanvases,
  workflows: mockWorkflows,
  workflowExecutions: mockWorkflowExecutions,
  episodes: mockEpisodes,
  conversations: mockConversations,
  messages: mockMessages,
  deviceInfo: mockDeviceInfo,
  devicePermissions: mockDevicePermissions,
  notifications: mockNotifications,
  formData: mockFormData,
  chartData: mockChartData,
  pendingActions: mockPendingActions,
};
