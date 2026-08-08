/**
 * ExecutionProgressScreen Component Tests
 *
 * Tests for real-time execution monitoring: loading/error states, running
 * vs terminal rendering, step rendering, cancel flow, polling behavior,
 * and pull-to-refresh.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react-native';
import { ExecutionProgressScreen } from '../../../screens/workflows/ExecutionProgressScreen';

const mockNavigation = {
  navigate: jest.fn(),
  goBack: jest.fn(),
  setOptions: jest.fn(),
  reset: jest.fn(),
};

jest.mock('@react-navigation/native', () => ({
  useNavigation: () => mockNavigation,
  useRoute: () => ({
    params: { executionId: 'exec-1' },
  }),
}));

jest.mock('@expo/vector-icons', () => ({
  Ionicons: 'Ionicons',
}));

// Mock workflowService
jest.mock('../../../services/workflowService', () => ({
  getExecutionById: jest.fn(),
  getExecutionSteps: jest.fn(),
  cancelExecution: jest.fn(),
}));

const { getExecutionById, getExecutionSteps, cancelExecution } = require('../../../services/workflowService');

const runningExecution = {
  id: 'exec-1',
  workflow_id: 'wf-1',
  workflow_name: 'Test Workflow',
  status: 'running',
  started_at: '2024-01-01T10:00:00Z',
  triggered_by: 'user@example.com',
  current_step: '2',
  total_steps: 4,
  progress_percentage: 50,
};

const completedExecution = {
  ...runningExecution,
  status: 'completed',
  completed_at: '2024-01-01T10:05:00Z',
  duration_seconds: 300,
  progress_percentage: 100,
};

const failedExecution = {
  ...runningExecution,
  status: 'failed',
  completed_at: '2024-01-01T10:02:00Z',
  duration_seconds: 120,
  progress_percentage: 75,
  error_message: 'Step "Process data" failed: timeout',
};

const steps = [
  {
    id: 'step-1',
    name: 'Fetch data',
    type: 'action',
    status: 'completed',
    started_at: '2024-01-01T10:00:00Z',
    completed_at: '2024-01-01T10:00:05Z',
    duration_ms: 1500,
  },
  {
    id: 'step-2',
    name: 'Process data',
    type: 'condition',
    status: 'running',
    started_at: '2024-01-01T10:00:05Z',
  },
  {
    id: 'step-3',
    name: 'Notify user',
    type: 'action',
    status: 'pending',
  },
];

describe('ExecutionProgressScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Loading State', () => {
    it('shows loading indicator while fetching', async () => {
      getExecutionById.mockResolvedValue(runningExecution);
      getExecutionSteps.mockResolvedValue(steps);

      render(<ExecutionProgressScreen />);

      expect(getByText('Loading execution details...')).toBeTruthy();
      await waitFor(() => {
        expect(getByText('Test Workflow')).toBeTruthy();
      });
    });
  });

  describe('Running Execution', () => {
    it('renders workflow header, progress bar, and steps', async () => {
      getExecutionById.mockResolvedValue(runningExecution);
      getExecutionSteps.mockResolvedValue(steps);

      render(<ExecutionProgressScreen />);

      await waitFor(() => {
        expect(getByText('Test Workflow')).toBeTruthy();
        expect(getByText('Execution ID: exec-1')).toBeTruthy();
        expect(getByText('RUNNING')).toBeTruthy();
        expect(getByText('Execution Progress')).toBeTruthy();
        expect(getByText('50%')).toBeTruthy();
        expect(getByText('Step 2 of 4')).toBeTruthy();
        expect(getByText('Cancel Execution')).toBeTruthy();
      });

      // Steps rendered with status metadata
      expect(getByText('Fetch data')).toBeTruthy();
      expect(getByText('Process data')).toBeTruthy();
      expect(getByText('Notify user')).toBeTruthy();
      expect(getByText('Duration: 1.50s')).toBeTruthy();
    });

    it('calls cancelExecution and refreshes data on cancel', async () => {
      getExecutionById.mockResolvedValue(runningExecution);
      getExecutionSteps.mockResolvedValue(steps);
      cancelExecution.mockResolvedValue({ success: true });

      render(<ExecutionProgressScreen />);

      await waitFor(() => {
        expect(getByText('Cancel Execution')).toBeTruthy();
      });

      const callsBefore = getExecutionById.mock.calls.length;
      fireEvent.press(getByText('Cancel Execution'));

      await waitFor(() => {
        expect(cancelExecution).toHaveBeenCalledWith('exec-1');
        expect(getExecutionById.mock.calls.length).toBeGreaterThan(callsBefore);
      });
    });

    it('polls for updates while running', async () => {
      getExecutionById.mockResolvedValue(runningExecution);
      getExecutionSteps.mockResolvedValue(steps);

      render(<ExecutionProgressScreen />);

      await waitFor(() => {
        expect(getExecutionById).toHaveBeenCalledTimes(1);
      });

      act(() => {
        jest.advanceTimersByTime(3000);
      });

      await waitFor(() => {
        expect(getExecutionById.mock.calls.length).toBeGreaterThanOrEqual(2);
      });
    });

    it('shows step error details', async () => {
      const errorSteps = [
        { ...steps[0] },
        {
          ...steps[1],
          status: 'failed',
          completed_at: '2024-01-01T10:00:08Z',
          error: 'Condition evaluation failed',
        },
      ];
      getExecutionById.mockResolvedValue(failedExecution);
      getExecutionSteps.mockResolvedValue(errorSteps);

      render(<ExecutionProgressScreen />);

      await waitFor(() => {
        expect(getByText('Condition evaluation failed')).toBeTruthy();
      });
    });
  });

  describe('Completed Execution', () => {
    it('renders terminal state without progress bar or cancel button', async () => {
      getExecutionById.mockResolvedValue(completedExecution);
      getExecutionSteps.mockResolvedValue(steps);

      render(<ExecutionProgressScreen />);

      await waitFor(() => {
        expect(getByText('COMPLETED')).toBeTruthy();
        expect(getByText('300s')).toBeTruthy();
      });

      expect(queryByText('Execution Progress')).toBeNull();
      expect(queryByText('Cancel Execution')).toBeNull();
      // Completed at row shown
      expect(getByText('Completed At')).toBeTruthy();
    });

    it('renders error message for failed execution', async () => {
      getExecutionById.mockResolvedValue(failedExecution);
      getExecutionSteps.mockResolvedValue([]);

      render(<ExecutionProgressScreen />);

      await waitFor(() => {
        expect(getByText('FAILED')).toBeTruthy();
        expect(getByText('Step "Process data" failed: timeout')).toBeTruthy();
      });
    });

    it('renders empty state when no steps recorded', async () => {
      getExecutionById.mockResolvedValue(completedExecution);
      getExecutionSteps.mockResolvedValue([]);

      render(<ExecutionProgressScreen />);

      await waitFor(() => {
        expect(getByText('No steps recorded yet')).toBeTruthy();
      });
    });
  });

  describe('Error Handling', () => {
    it('renders "Execution not found" when execution is null', async () => {
      getExecutionById.mockResolvedValue(null);
      getExecutionSteps.mockResolvedValue([]);

      render(<ExecutionProgressScreen />);

      await waitFor(() => {
        expect(getByText('Execution not found')).toBeTruthy();
      });
    });

    it('does not crash when fetch fails', async () => {
      getExecutionById.mockRejectedValue(new Error('Network error'));
      getExecutionSteps.mockRejectedValue(new Error('Network error'));

      render(<ExecutionProgressScreen />);

      // Error is logged, loading ends; nothing rendered (execution null)
      await waitFor(() => {
        expect(getByText('Execution not found')).toBeTruthy();
      });
    });
  });

  describe('Pull to Refresh', () => {
    it('refreshes data on pull', async () => {
      const { RefreshControl } = require('react-native');
      getExecutionById.mockResolvedValue(runningExecution);
      getExecutionSteps.mockResolvedValue(steps);

      render(<ExecutionProgressScreen />);

      await waitFor(() => {
        expect(getByText('Test Workflow')).toBeTruthy();
      });

      const callsBefore = getExecutionById.mock.calls.length;
      const refreshControl = screen.UNSAFE_getByType(RefreshControl);
      fireEvent(refreshControl, 'refresh');

      await waitFor(() => {
        expect(getExecutionById.mock.calls.length).toBeGreaterThan(callsBefore);
      });
    });
  });
});

function getByText(text: string | RegExp) {
  return screen.getByText(text);
}

function queryByText(text: string | RegExp) {
  return screen.queryByText(text);
}
