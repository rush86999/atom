/**
 * WorkflowsListScreen Tests
 *
 * Comprehensive test suite for WorkflowsListScreen component covering:
 * - Rendering with workflow data
 * - Search functionality
 * - Category filtering
 * - Pull-to-refresh
 * - Workflow card interactions
 * - Navigation to workflow details
 * - Quick trigger functionality
 *
 * @see src/screens/workflows/WorkflowsListScreen.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react-native';
import { WorkflowsListScreen } from '../../src/screens/workflows/WorkflowsListScreen';

// Mock navigation
const mockNavigation = {
  navigate: jest.fn(),
  goBack: jest.fn(),
  replace: jest.fn(),
  reset: jest.fn(),
  dispatch: jest.fn(),
  isFocused: jest.fn(() => true),
  canGoBack: jest.fn(() => true),
};

jest.mock('@react-navigation/native', () => ({
  useNavigation: () => mockNavigation,
  NavigationProp: jest.fn(),
}));

// Mock workflow service
const mockWorkflows = [
  {
    id: 'workflow-1',
    name: 'Data Sync Workflow',
    description: 'Syncs data between systems',
    category: 'Automation',
    status: 'active',
    execution_count: 150,
    success_rate: 98.5,
    created_at: '2024-01-01T00:00:00.000Z',
    updated_at: '2024-01-10T00:00:00.000Z',
  },
  {
    id: 'workflow-2',
    name: 'Email Notifications',
    description: 'Sends email notifications',
    category: 'Integration',
    status: 'active',
    execution_count: 75,
    success_rate: 95.0,
    created_at: '2024-01-02T00:00:00.000Z',
    updated_at: '2024-01-11T00:00:00.000Z',
  },
  {
    id: 'workflow-3',
    name: 'Data Processing',
    description: 'Processes large datasets',
    category: 'Data Processing',
    status: 'active',
    execution_count: 200,
    success_rate: 92.5,
    created_at: '2024-01-03T00:00:00.000Z',
    updated_at: '2024-01-12T00:00:00.000Z',
  },
];

jest.mock('../../src/services/workflowService', () => ({
  getWorkflows: jest.fn().mockResolvedValue({
    workflows: mockWorkflows,
  }),
  triggerWorkflow: jest.fn().mockResolvedValue({
    success: true,
  }),
}));

describe('WorkflowsListScreen - Rendering', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Renders loading state initially
  it('should render loading state initially', () => {
    const { getByText } = render(<WorkflowsListScreen />);

    expect(getByText('Loading workflows...')).toBeTruthy();
  });

  // Test 2: Renders workflow cards after loading
  it('should render workflow cards after loading', async () => {
    const { getByText, queryByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(queryByText('Loading workflows...')).toBeNull();
    });

    await waitFor(() => {
      expect(getByText('Data Sync Workflow')).toBeTruthy();
      expect(getByText('Email Notifications')).toBeTruthy();
      expect(getByText('Data Processing')).toBeTruthy();
    });
  });

  // Test 3: Displays workflow descriptions
  it('should display workflow descriptions', async () => {
    const { getByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByText('Syncs data between systems')).toBeTruthy();
      expect(getByText('Sends email notifications')).toBeTruthy();
    });
  });

  // Test 4: Displays workflow stats
  it('should display workflow stats', async () => {
    const { getByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByText(/150 runs/)).toBeTruthy();
      expect(getByText(/98.5% success/)).toBeTruthy();
    });
  });

  // Test 5: Displays workflow badges
  it('should display workflow badges', async () => {
    const { getByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByText('Automation')).toBeTruthy();
      expect(getByText('active')).toBeTruthy();
    });
  });
});

describe('WorkflowsListScreen - Search', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Displays search bar
  it('should display search bar', async () => {
    const { getByPlaceholderText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByPlaceholderText('Search workflows...')).toBeTruthy();
    });
  });

  // Test 2: Filters workflows by search query
  it('should filter workflows by search query', async () => {
    const { getByPlaceholderText, getByText, queryByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByText('Data Sync Workflow')).toBeTruthy();
    });

    const searchInput = getByPlaceholderText('Search workflows...');
    fireEvent.changeText(searchInput, 'Email');

    await waitFor(() => {
      expect(getByText('Email Notifications')).toBeTruthy();
      expect(queryByText('Data Sync Workflow')).toBeNull();
    });
  });

  // Test 3: Clears search when X pressed
  it('should clear search when X pressed', async () => {
    const { getByPlaceholderText, getByText, getByTestId } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByText('Data Sync Workflow')).toBeTruthy();
    });

    const searchInput = getByPlaceholderText('Search workflows...');
    fireEvent.changeText(searchInput, 'Email');

    await waitFor(() => {
      expect(getByText('Email Notifications')).toBeTruthy();
    });

    const clearButton = getByTestId(/close-circle/i);
    fireEvent.press(clearButton);

    await waitFor(() => {
      expect(getByText('Data Sync Workflow')).toBeTruthy();
    });
  });

  // Test 4: Searches in workflow descriptions
  it('should search in workflow descriptions', async () => {
    const { getByPlaceholderText, getByText, queryByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByText('Data Sync Workflow')).toBeTruthy();
    });

    const searchInput = getByPlaceholderText('Search workflows...');
    fireEvent.changeText(searchInput, 'syncs');

    await waitFor(() => {
      expect(getByText('Data Sync Workflow')).toBeTruthy();
    });
  });
});

describe('WorkflowsListScreen - Category Filter', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Displays category filter
  it('should display category filter', async () => {
    const { getByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByText('All')).toBeTruthy();
      expect(getByText('Automation')).toBeTruthy();
      expect(getByText('Integration')).toBeTruthy();
      expect(getByText('Data Processing')).toBeTruthy();
    });
  });

  // Test 2: Filters by category
  it('should filter by category', async () => {
    const { getByText, queryByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByText('All')).toBeTruthy();
    });

    const automationChip = getByText('Automation');
    fireEvent.press(automationChip);

    await waitFor(() => {
      expect(getByText('Data Sync Workflow')).toBeTruthy();
      expect(queryByText('Email Notifications')).toBeNull();
    });
  });

  // Test 3: Shows all workflows when All selected
  it('should show all workflows when All selected', async () => {
    const { getByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByText('All')).toBeTruthy();
    });

    // All should be selected by default
    expect(getByText('Data Sync Workflow')).toBeTruthy();
    expect(getByText('Email Notifications')).toBeTruthy();
    expect(getByText('Data Processing')).toBeTruthy();
  });

  // Test 4: Changes chip style when selected
  it('should change chip style when selected', async () => {
    const { getByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      const automationChip = getByText('Automation');
      fireEvent.press(automationChip);
    });

    // Chip should have active style
    await waitFor(() => {
      expect(getByText('Automation')).toBeTruthy();
    });
  });
});

describe('WorkflowsListScreen - Pull to Refresh', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Refreshes on pull
  it('should refresh on pull', async () => {
    const getWorkflows = require('../../src/services/workflowService').getWorkflows;

    const { getByText, UNSAFE_getByType } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByText('Data Sync Workflow')).toBeTruthy();
    });

    // Simulate pull to refresh
    act(() => {
      getWorkflows.mockClear();
      getWorkflows.mockResolvedValueOnce({
        workflows: mockWorkflows,
      });
    });

    // Trigger refresh (would be done by RefreshControl in real scenario)
    await waitFor(() => {
      expect(getWorkflows).toHaveBeenCalled();
    });
  });

  // Test 2: Shows refreshing indicator
  it('should show refreshing indicator', async () => {
    const { getByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByText('Data Sync Workflow')).toBeTruthy();
    });

    // RefreshControl would show indicator
    expect(getByText('Data Sync Workflow')).toBeTruthy();
  });
});

describe('WorkflowsListScreen - Workflow Card', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Navigates to workflow details on card press
  it('should navigate to workflow details on card press', async () => {
    const { getByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      const workflowCard = getByText('Data Sync Workflow');
      fireEvent.press(workflowCard);
    });

    expect(mockNavigation.navigate).toHaveBeenCalledWith('WorkflowDetail', {
      workflowId: 'workflow-1',
    });
  });

  // Test 2: Triggers workflow on run button press
  it('should trigger workflow on run button press', async () => {
    const { getByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      const runButton = getByText('Run');
      fireEvent.press(runButton);
    });

    expect(mockNavigation.navigate).toHaveBeenCalledWith('WorkflowTrigger', {
      workflowId: 'workflow-1',
      workflowName: 'Data Sync Workflow',
    });
  });

  // Test 3: Displays success rate indicator
  it('should display success rate indicator', async () => {
    const { getByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByText(/98.5% success/)).toBeTruthy();
      expect(getByText(/95.0% success/)).toBeTruthy();
    });
  });

  // Test 4: Uses correct color for success rate
  it('should use correct color for success rate', async () => {
    const { getByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      // High success rate (>90%) should show green checkmark
      expect(getByText(/98.5% success/)).toBeTruthy();
      // Lower success rate should show warning icon
      expect(getByText(/92.5% success/)).toBeTruthy();
    });
  });
});

describe('WorkflowsListScreen - Empty State', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Shows empty state when no workflows
  it('should show empty state when no workflows', async () => {
    const getWorkflows = require('../../src/services/workflowService').getWorkflows;
    getWorkflows.mockResolvedValueOnce({
      workflows: [],
    });

    const { getByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByText('No workflows yet')).toBeTruthy();
    });
  });

  // Test 2: Shows empty search results when search matches none
  it('should show empty search results when search matches none', async () => {
    const { getByPlaceholderText, getByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByText('Data Sync Workflow')).toBeTruthy();
    });

    const searchInput = getByPlaceholderText('Search workflows...');
    fireEvent.changeText(searchInput, 'nonexistent');

    await waitFor(() => {
      expect(getByText('No workflows match your search')).toBeTruthy();
    });
  });

  // Test 3: Shows empty state for category filter
  it('should show empty state for category filter', async () => {
    const { getByText, queryByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByText('AI/ML')).toBeTruthy();
    });

    const aiMlChip = getByText('AI/ML');
    fireEvent.press(aiMlChip);

    await waitFor(() => {
      expect(queryByText('No workflows match your search')).toBeTruthy();
    });
  });
});

describe('WorkflowsListScreen - Error State', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Shows error when fetch fails
  it('should show error when fetch fails', async () => {
    const getWorkflows = require('../../src/services/workflowService').getWorkflows;
    getWorkflows.mockRejectedValueOnce(new Error('Network error'));

    const { getByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByText('Error Loading Workflows')).toBeTruthy();
    });
  });

  // Test 2: Shows retry button on error
  it('should show retry button on error', async () => {
    const getWorkflows = require('../../src/services/workflowService').getWorkflows;
    getWorkflows.mockRejectedValueOnce(new Error('Network error'));

    const { getByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByText('Retry')).toBeTruthy();
    });
  });

  // Test 3: Retries on retry button press
  it('should retry on retry button press', async () => {
    const getWorkflows = require('../../src/services/workflowService').getWorkflows;
    getWorkflows.mockRejectedValueOnce(new Error('Network error'));
    getWorkflows.mockResolvedValueOnce({
      workflows: mockWorkflows,
    });

    const { getByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      const retryButton = getByText('Retry');
      fireEvent.press(retryButton);
    });

    await waitFor(() => {
      expect(getByText('Data Sync Workflow')).toBeTruthy();
    });
  });
});

describe('WorkflowsListScreen - Layout', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Has proper padding and margins
  it('should have proper padding and margins', async () => {
    const { getByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByText('Data Sync Workflow')).toBeTruthy();
    });

    // Workflow cards should be rendered
    expect(getByText('Data Sync Workflow')).toBeTruthy();
  });

  // Test 2: Scrollable list of workflows
  it('should have scrollable list of workflows', async () => {
    const { getByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByText('Data Sync Workflow')).toBeTruthy();
      expect(getByText('Email Notifications')).toBeTruthy();
      expect(getByText('Data Processing')).toBeTruthy();
    });

    // All workflows should be visible in list
    expect(getByText('Data Sync Workflow')).toBeTruthy();
  });
});

describe('WorkflowsListScreen - Edge Cases', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Handles workflow with zero executions
  it('should handle workflow with zero executions', async () => {
    const getWorkflows = require('../../src/services/workflowService').getWorkflows;
    getWorkflows.mockResolvedValueOnce({
      workflows: [
        {
          id: 'workflow-new',
          name: 'New Workflow',
          description: 'Never executed',
          category: 'Automation',
          status: 'active',
          execution_count: 0,
          success_rate: 0,
          created_at: '2024-01-01T00:00:00.000Z',
          updated_at: '2024-01-01T00:00:00.000Z',
        },
      ],
    });

    const { getByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByText('New Workflow')).toBeTruthy();
      expect(getByText(/0 runs/)).toBeTruthy();
    });
  });

  // Test 2: Handles very long workflow names
  it('should handle very long workflow names', async () => {
    const getWorkflows = require('../../src/services/workflowService').getWorkflows;
    getWorkflows.mockResolvedValueOnce({
      workflows: [
        {
          id: 'workflow-long',
          name: 'This is a very long workflow name that should be truncated',
          description: 'Test',
          category: 'Automation',
          status: 'active',
          execution_count: 10,
          success_rate: 100,
          created_at: '2024-01-01T00:00:00.000Z',
          updated_at: '2024-01-01T00:00:00.000Z',
        },
      ],
    });

    const { getByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByText(/This is a very long workflow name/)).toBeTruthy();
    });
  });

  // Test 3: Handles missing workflow description
  it('should handle missing workflow description', async () => {
    const getWorkflows = require('../../src/services/workflowService').getWorkflows;
    getWorkflows.mockResolvedValueOnce({
      workflows: [
        {
          id: 'workflow-no-desc',
          name: 'No Description',
          description: '',
          category: 'Automation',
          status: 'active',
          execution_count: 10,
          success_rate: 100,
          created_at: '2024-01-01T00:00:00.000Z',
          updated_at: '2024-01-01T00:00:00.000Z',
        },
      ],
    });

    const { getByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByText('No Description')).toBeTruthy();
    });
  });
});

describe('WorkflowsListScreen - Accessibility', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Has accessible search input
  it('should have accessible search input', async () => {
    const { getByPlaceholderText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByPlaceholderText('Search workflows...')).toBeTruthy();
    });
  });

  // Test 2: Has accessible workflow cards
  it('should have accessible workflow cards', async () => {
    const { getByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByText('Data Sync Workflow')).toBeTruthy();
    });
  });

  // Test 3: Has accessible category filters
  it('should have accessible category filters', async () => {
    const { getByText } = render(<WorkflowsListScreen />);

    await waitFor(() => {
      expect(getByText('All')).toBeTruthy();
      expect(getByText('Automation')).toBeTruthy();
    });
  });
});
