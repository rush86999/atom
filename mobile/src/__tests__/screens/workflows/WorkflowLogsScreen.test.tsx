/**
 * WorkflowLogsScreen Component Tests
 *
 * Tests for log rendering, level filtering, empty states, metadata
 * display, header title updates, and error handling.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { WorkflowLogsScreen } from '../../../screens/workflows/WorkflowLogsScreen';

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

jest.mock('../../../services/workflowService', () => ({
  getExecutionLogs: jest.fn(),
  getExecutionById: jest.fn(),
}));

const { getExecutionLogs, getExecutionById } = require('../../../services/workflowService');

const execution = {
  id: 'exec-1',
  workflow_id: 'wf-1',
  workflow_name: 'Test Workflow',
  status: 'completed',
  started_at: '2024-01-01T10:00:00Z',
  triggered_by: 'user@example.com',
  duration_seconds: 300,
  progress_percentage: 100,
};

const logs = [
  {
    id: 'log-1',
    level: 'info',
    message: 'Workflow started',
    timestamp: '2024-01-01T10:00:00Z',
  },
  {
    id: 'log-2',
    level: 'warning',
    message: 'Slow step detected',
    timestamp: '2024-01-01T10:00:10Z',
    step_id: 'step-2',
    metadata: { duration_ms: 8000 },
  },
  {
    id: 'log-3',
    level: 'error',
    message: 'Step failed',
    timestamp: '2024-01-01T10:00:20Z',
    step_id: 'step-3',
    metadata: { retry: 2 },
  },
];

describe('WorkflowLogsScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Loading State', () => {
    it('shows loading indicator initially', async () => {
      getExecutionLogs.mockResolvedValue(logs);
      getExecutionById.mockResolvedValue(execution);

      render(<WorkflowLogsScreen />);

      expect(getByText('Loading logs...')).toBeTruthy();
      await waitFor(() => {
        expect(getByText('Workflow started')).toBeTruthy();
      });
    });
  });

  describe('Log Rendering', () => {
    it('renders logs with level badges, messages, and timestamps', async () => {
      getExecutionLogs.mockResolvedValue(logs);
      getExecutionById.mockResolvedValue(execution);

      render(<WorkflowLogsScreen />);

      await waitFor(() => {
        expect(getByText('INFO')).toBeTruthy();
        expect(getByText('Workflow started')).toBeTruthy();
        expect(getByText('WARNING')).toBeTruthy();
        expect(getByText('Slow step detected')).toBeTruthy();
        expect(getByText('ERROR')).toBeTruthy();
        expect(getByText('Step failed')).toBeTruthy();
      });

      // Log count bar
      expect(getByText('Showing 3 of 3 logs')).toBeTruthy();
    });

    it('shows execution summary with status and duration', async () => {
      getExecutionLogs.mockResolvedValue(logs);
      getExecutionById.mockResolvedValue(execution);

      render(<WorkflowLogsScreen />);

      await waitFor(() => {
        expect(getByText('completed')).toBeTruthy();
        expect(getByText('300s')).toBeTruthy();
      });
    });

    it('sets header title from execution workflow name', async () => {
      getExecutionLogs.mockResolvedValue(logs);
      getExecutionById.mockResolvedValue(execution);

      render(<WorkflowLogsScreen />);

      await waitFor(() => {
        expect(mockNavigation.setOptions).toHaveBeenCalledWith({
          title: 'Logs - Test Workflow',
        });
      });
    });

    it('renders step id and metadata entries', async () => {
      getExecutionLogs.mockResolvedValue(logs);
      getExecutionById.mockResolvedValue(execution);

      render(<WorkflowLogsScreen />);

      await waitFor(() => {
        expect(getByText('Step: step-2')).toBeTruthy();
        expect(getAllByText('Metadata:').length).toBe(2);
        expect(getByText('duration_ms: 8000')).toBeTruthy();
        expect(getByText('retry: 2')).toBeTruthy();
      });
    });

    it('omits metadata section when log has empty metadata', async () => {
      getExecutionLogs.mockResolvedValue([{ ...logs[0], metadata: {} }]);
      getExecutionById.mockResolvedValue(execution);

      render(<WorkflowLogsScreen />);

      await waitFor(() => {
        expect(getByText('Workflow started')).toBeTruthy();
      });
      expect(queryByText('Metadata:')).toBeNull();
    });
  });

  describe('Filtering', () => {
    it('filters logs by level when a filter chip is pressed', async () => {
      getExecutionLogs.mockResolvedValue(logs);
      getExecutionById.mockResolvedValue(execution);

      render(<WorkflowLogsScreen />);

      await waitFor(() => {
        expect(getByText('Workflow started')).toBeTruthy();
      });

      fireEvent.press(getByText('Error'));

      await waitFor(() => {
        expect(getByText('Step failed')).toBeTruthy();
        expect(queryByText('Workflow started')).toBeNull();
        expect(getByText('Showing 1 of 3 logs')).toBeTruthy();
      });
    });

    it('renders empty state when filter has no matches', async () => {
      getExecutionLogs.mockResolvedValue(logs);
      getExecutionById.mockResolvedValue(execution);

      render(<WorkflowLogsScreen />);

      await waitFor(() => {
        expect(getByText('Workflow started')).toBeTruthy();
      });

      fireEvent.press(getByText('Debug'));

      await waitFor(() => {
        expect(getByText('No debug logs')).toBeTruthy();
      });
    });

    it('renders "No logs available" when there are no logs at all', async () => {
      getExecutionLogs.mockResolvedValue([]);
      getExecutionById.mockResolvedValue(execution);

      render(<WorkflowLogsScreen />);

      await waitFor(() => {
        expect(getByText('No logs available')).toBeTruthy();
      });
    });
  });

  describe('Error Handling', () => {
    it('does not crash when fetching logs fails', async () => {
      getExecutionLogs.mockRejectedValue(new Error('Network error'));
      getExecutionById.mockRejectedValue(new Error('Network error'));

      render(<WorkflowLogsScreen />);

      await waitFor(() => {
        // Loading ends; empty logs list shown with no logs available
        expect(getByText('No logs available')).toBeTruthy();
      });
    });
  });
});

function getByText(text: string | RegExp) {
  return screen.getByText(text);
}

function getAllByText(text: string | RegExp) {
  return screen.getAllByText(text);
}

function queryByText(text: string | RegExp) {
  return screen.queryByText(text);
}
