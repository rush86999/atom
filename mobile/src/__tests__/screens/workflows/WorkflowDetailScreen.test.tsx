/**
 * WorkflowDetailScreen Component Tests
 *
 * Tests for workflow detail rendering, quick trigger flow, navigation to
 * trigger/logs screens, recent executions, and error states.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { WorkflowDetailScreen } from '../../../screens/workflows/WorkflowDetailScreen';

const mockNavigation = {
  navigate: jest.fn(),
  goBack: jest.fn(),
  setOptions: jest.fn(),
  reset: jest.fn(),
};

jest.mock('@react-navigation/native', () => ({
  useNavigation: () => mockNavigation,
  useRoute: () => ({
    params: { workflowId: 'wf-1' },
  }),
}));

jest.mock('@expo/vector-icons', () => ({
  Ionicons: 'Ionicons',
}));

jest.mock('../../../services/workflowService', () => ({
  getWorkflowById: jest.fn(),
  getWorkflowExecutions: jest.fn(),
  triggerWorkflow: jest.fn(),
}));

const { getWorkflowById, getWorkflowExecutions, triggerWorkflow } = require('../../../services/workflowService');

const Alert = require('react-native/Libraries/Alert/Alert').alert;

const workflow = {
  id: 'wf-1',
  name: 'Test Workflow',
  description: 'A test workflow for automation',
  category: 'automation',
  status: 'active',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-02T00:00:00Z',
  last_execution: '2024-01-03T12:00:00Z',
  execution_count: 42,
  success_rate: 95.5,
  tags: ['sales', 'nightly'],
};

const executions = [
  {
    id: 'exec-1',
    workflow_id: 'wf-1',
    workflow_name: 'Test Workflow',
    status: 'completed',
    started_at: '2024-01-03T12:00:00Z',
    duration_seconds: 300,
    progress_percentage: 100,
    triggered_by: 'user@example.com',
  },
  {
    id: 'exec-2',
    workflow_id: 'wf-1',
    workflow_name: 'Test Workflow',
    status: 'failed',
    started_at: '2024-01-02T12:00:00Z',
    duration_seconds: 30,
    error_message: 'Integration timeout',
    progress_percentage: 50,
    triggered_by: 'user@example.com',
  },
];

describe('WorkflowDetailScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Loading State', () => {
    it('shows loading indicator initially', async () => {
      getWorkflowById.mockResolvedValue(workflow);
      getWorkflowExecutions.mockResolvedValue(executions);

      render(<WorkflowDetailScreen />);

      expect(getByText('Loading workflow details...')).toBeTruthy();
      await waitFor(() => {
        expect(getByText('Test Workflow')).toBeTruthy();
      });
    });
  });

  describe('Workflow Rendering', () => {
    it('renders workflow details, stats, and badges', async () => {
      getWorkflowById.mockResolvedValue(workflow);
      getWorkflowExecutions.mockResolvedValue(executions);

      render(<WorkflowDetailScreen />);

      await waitFor(() => {
        expect(getByText('Test Workflow')).toBeTruthy();
        expect(getByText('A test workflow for automation')).toBeTruthy();
        expect(getByText('42 executions')).toBeTruthy();
        expect(getByText('95.5% success')).toBeTruthy();
        expect(getByText('automation')).toBeTruthy();
        expect(getByText('active')).toBeTruthy();
        expect(getByText('Run Now')).toBeTruthy();
        expect(getByText('Configure')).toBeTruthy();
      });
    });

    it('renders tags and recent executions', async () => {
      getWorkflowById.mockResolvedValue(workflow);
      getWorkflowExecutions.mockResolvedValue(executions);

      render(<WorkflowDetailScreen />);

      await waitFor(() => {
        expect(getByText('sales')).toBeTruthy();
        expect(getByText('nightly')).toBeTruthy();
        expect(getByText('Recent Executions')).toBeTruthy();
        expect(getByText('completed')).toBeTruthy();
        expect(getByText('failed')).toBeTruthy();
        expect(getByText('Integration timeout')).toBeTruthy();
        expect(getByText('Duration: 300s')).toBeTruthy();
      });
    });

    it('renders empty state when there are no recent executions', async () => {
      getWorkflowById.mockResolvedValue(workflow);
      getWorkflowExecutions.mockResolvedValue([]);

      render(<WorkflowDetailScreen />);

      await waitFor(() => {
        expect(getByText('No executions yet')).toBeTruthy();
      });
    });
  });

  describe('Actions', () => {
    it('navigates to trigger screen on Configure press', async () => {
      getWorkflowById.mockResolvedValue(workflow);
      getWorkflowExecutions.mockResolvedValue(executions);

      render(<WorkflowDetailScreen />);

      await waitFor(() => {
        expect(getByText('Configure')).toBeTruthy();
      });

      fireEvent.press(getByText('Configure'));

      expect(mockNavigation.navigate).toHaveBeenCalledWith('WorkflowTrigger', {
        workflowId: 'wf-1',
        workflowName: 'Test Workflow',
      });
    });

    it('triggers workflow with synchronous=false on Run Now', async () => {
      getWorkflowById.mockResolvedValue(workflow);
      getWorkflowExecutions.mockResolvedValue(executions);
      triggerWorkflow.mockResolvedValue({
        execution_id: 'exec-99',
        status: 'running',
        message: 'Workflow started',
      });

      render(<WorkflowDetailScreen />);

      await waitFor(() => {
        expect(getByText('Run Now')).toBeTruthy();
      });

      fireEvent.press(getByText('Run Now'));

      await waitFor(() => {
        expect(triggerWorkflow).toHaveBeenCalledWith({
          workflow_id: 'wf-1',
          synchronous: false,
        });
        expect(Alert).toHaveBeenCalledWith(
          'Workflow Triggered',
          expect.stringContaining('exec-99'),
          expect.any(Array)
        );
      });

      // Press "View Progress" button from the alert
      const buttons = Alert.mock.calls[Alert.mock.calls.length - 1][2];
      const viewProgress = buttons.find((b: any) => b.text === 'View Progress');
      viewProgress.onPress();

      expect(mockNavigation.navigate).toHaveBeenCalledWith('ExecutionProgress', {
        executionId: 'exec-99',
      });
    });

    it('shows error alert when trigger fails', async () => {
      getWorkflowById.mockResolvedValue(workflow);
      getWorkflowExecutions.mockResolvedValue(executions);
      triggerWorkflow.mockRejectedValue(new Error('Trigger failed'));

      render(<WorkflowDetailScreen />);

      await waitFor(() => {
        expect(getByText('Run Now')).toBeTruthy();
      });

      fireEvent.press(getByText('Run Now'));

      await waitFor(() => {
        expect(Alert).toHaveBeenCalledWith('Error', 'Trigger failed');
      });
    });

    it('navigates to logs when an execution card is pressed', async () => {
      getWorkflowById.mockResolvedValue(workflow);
      getWorkflowExecutions.mockResolvedValue(executions);

      render(<WorkflowDetailScreen />);

      await waitFor(() => {
        expect(getByText('completed')).toBeTruthy();
      });

      fireEvent.press(getByText('completed'));

      expect(mockNavigation.navigate).toHaveBeenCalledWith('WorkflowLogs', {
        executionId: 'exec-1',
      });
    });
  });

  describe('Error Handling', () => {
    it('shows alert and "Workflow not found" when load fails', async () => {
      getWorkflowById.mockRejectedValue(new Error('Network error'));
      getWorkflowExecutions.mockRejectedValue(new Error('Network error'));

      render(<WorkflowDetailScreen />);

      await waitFor(() => {
        expect(Alert).toHaveBeenCalledWith('Error', 'Network error');
        expect(getByText('Workflow not found')).toBeTruthy();
      });
    });
  });
});

function getByText(text: string | RegExp) {
  return screen.getByText(text);
}
