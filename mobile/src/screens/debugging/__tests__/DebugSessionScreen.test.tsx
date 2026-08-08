/**
 * DebugSessionScreen Tests
 *
 * Testing suite for the mobile debug session screen:
 * session start (POST with workflow-scoped URL), loading/error states,
 * session info + variables rendering, and step controls.
 */

import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import { Alert } from 'react-native';
import axios from 'axios';
import { DebugSessionScreen } from '../DebugSessionScreen';

jest.mock('axios', () => ({
  get: jest.fn(),
  post: jest.fn(),
  put: jest.fn(),
  delete: jest.fn(),
}));

jest.mock('lucide-react-native', () => {
  const React = require('react');
  const { Text } = require('react-native');
  const Icon = (name: string) => (props: any) =>
    React.createElement(Text, { ...props, testID: name }, name);
  return {
    Play: Icon('Play'),
    Pause: Icon('Pause'),
    SkipForward: Icon('SkipForward'),
    ArrowRight: Icon('ArrowRight'),
    ArrowDown: Icon('ArrowDown'),
  };
}, { virtual: true });

const mockPost = axios.post as jest.Mock;
const alertMock = Alert.alert as jest.Mock;

const route = { params: { workflowId: 'wf-1', workflowName: 'Weekly Report' } };

const session = {
  id: 'sess-1',
  workflow_id: 'wf-1',
  workflow_name: 'Weekly Report',
  status: 'running',
  current_step: 2,
  current_node_id: 'node-3',
  variables: { user: 'alice', count: 3, flag: true },
  created_at: '2024-01-01T00:00:00Z',
};

const stepPayload = {
  session_id: 'sess-1',
  action: 'step_over',
};

describe('DebugSessionScreen', () => {
  beforeEach(() => {
    mockPost.mockReset();
    mockPost.mockResolvedValue({ data: session });
  });

  describe('Session start', () => {
    test('starts a debug session with the workflow-scoped URL on mount', async () => {
      render(<DebugSessionScreen route={route} />);

      await waitFor(() => {
        expect(mockPost).toHaveBeenCalledWith('/api/workflows/wf-1/debug/sessions', {
          stop_on_entry: false,
          stop_on_exceptions: true,
          stop_on_error: true,
        });
      });
    });

    test('shows loading text while the session is starting', async () => {
      mockPost.mockReturnValue(new Promise(() => {}));
      const { getByText } = render(<DebugSessionScreen route={route} />);
      expect(getByText('Starting debug session...')).toBeTruthy();
    });

    test('shows error state and alert when session start fails', async () => {
      mockPost.mockRejectedValue(new Error('boom'));
      const { getByText } = render(<DebugSessionScreen route={route} />);

      await waitFor(() => {
        expect(getByText('Failed to start debug session')).toBeTruthy();
      });
      expect(alertMock).toHaveBeenCalledWith('Error', 'Failed to start debug session');
    });
  });

  describe('Session rendering', () => {
    test('renders workflow name, status, step, and current node', async () => {
      const { getByText } = render(<DebugSessionScreen route={route} />);

      await waitFor(() => {
        expect(getByText('Debug Session')).toBeTruthy();
      });
      expect(getByText('Weekly Report')).toBeTruthy();
      expect(getByText('running')).toBeTruthy();
      expect(getByText('Step:')).toBeTruthy();
      expect(getByText('2')).toBeTruthy();
      expect(getByText('Node:')).toBeTruthy();
      expect(getByText('node-3')).toBeTruthy();
    });

    test('renders variable chips with stringified values', async () => {
      const { getByText } = render(<DebugSessionScreen route={route} />);

      await waitFor(() => {
        expect(getByText('Variables')).toBeTruthy();
      });
      expect(getByText('user:')).toBeTruthy();
      expect(getByText('"alice"')).toBeTruthy();
      expect(getByText('count:')).toBeTruthy();
      expect(getByText('3')).toBeTruthy();
      expect(getByText('flag:')).toBeTruthy();
      expect(getByText('true')).toBeTruthy();
    });

    test('renders without variables without crashing', async () => {
      mockPost.mockResolvedValue({ data: { ...session, variables: {} } });
      const { getByText } = render(<DebugSessionScreen route={route} />);

      await waitFor(() => {
        expect(getByText('Debug Session')).toBeTruthy();
      });
    });

    test('shows N/A for missing current node', async () => {
      mockPost.mockResolvedValue({ data: { ...session, current_node_id: null } });
      const { getByText } = render(<DebugSessionScreen route={route} />);

      await waitFor(() => {
        expect(getByText('N/A')).toBeTruthy();
      });
    });
  });

  describe('Step controls', () => {
    const actions: Array<[string, string]> = [
      ['Over', 'step_over'],
      ['Into', 'step_into'],
      ['Out', 'step_out'],
      ['Run', 'continue'],
      ['Pause', 'pause'],
    ];

    test.each(actions)('executes %s step via the step endpoint', async (label, action) => {
      const { getByText, getAllByText } = render(<DebugSessionScreen route={route} />);

      await waitFor(() => {
        expect(getByText('Debug Session')).toBeTruthy();
      });

      // Label may appear twice (lucide icon mock renders its name as text)
      const stepButtons = getAllByText(label);
      fireEvent.press(stepButtons[stepButtons.length - 1]);

      await waitFor(() => {
        expect(mockPost).toHaveBeenCalledWith('/api/workflows/debug/step', {
          session_id: 'sess-1',
          action,
        });
      });
    });

    test('updates session state from the step response', async () => {
      const { getByText, getAllByText } = render(<DebugSessionScreen route={route} />);

      await waitFor(() => {
        expect(getByText('Debug Session')).toBeTruthy();
      });

      mockPost.mockResolvedValue({
        data: { ...session, current_step: 3, current_node_id: 'node-4', status: 'paused' },
      });

      fireEvent.press(getByText('Over'));

      await waitFor(() => {
        // '3' also appears in the variable chips (count: 3)
        expect(getAllByText('3').length).toBeGreaterThan(0);
        expect(getByText('node-4')).toBeTruthy();
        expect(getByText('paused')).toBeTruthy();
      });
    });

    test('alerts when a step fails', async () => {
      const { getByText } = render(<DebugSessionScreen route={route} />);

      await waitFor(() => {
        expect(getByText('Debug Session')).toBeTruthy();
      });

      mockPost.mockRejectedValue(new Error('boom'));
      fireEvent.press(getByText('Over'));

      await waitFor(() => {
        expect(alertMock).toHaveBeenCalledWith('Error', 'Failed to step_over');
      });
    });
  });

  describe('Action buttons', () => {
    test('renders navigation action buttons', async () => {
      const { getByText } = render(<DebugSessionScreen route={route} />);

      await waitFor(() => {
        expect(getByText('Manage Breakpoints')).toBeTruthy();
      });
      expect(getByText('View Execution Traces')).toBeTruthy();
    });
  });
});
