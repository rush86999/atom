/**
 * TracesScreen Tests
 *
 * Testing suite for the mobile execution traces screen:
 * fetch with status filter params, trace row rendering, expand/collapse
 * with details (timings, input/output data, errors), loading/empty states,
 * and filter switching.
 */

import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import axios from 'axios';
import { TracesScreen } from '../TracesScreen';

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
    ChevronRight: Icon('ChevronRight'),
    ChevronDown: Icon('ChevronDown'),
    Search: Icon('Search'),
    CheckCircle: Icon('CheckCircle'),
    XCircle: Icon('XCircle'),
    Clock: Icon('Clock'),
  };
}, { virtual: true });

const mockGet = axios.get as jest.Mock;

const route = { params: { executionId: 'exec-1', workflowId: 'wf-1' } };

const traces = [
  {
    trace_id: 't-1',
    step_number: 1,
    node_id: 'node-start',
    node_type: 'start',
    status: 'completed',
    input_data: { order_id: 'ORD-1' },
    output_data: { ok: true },
    error_message: '',
    duration_ms: 120,
    started_at: '2024-01-01T00:00:00Z',
    completed_at: '2024-01-01T00:00:02Z',
  },
  {
    trace_id: 't-2',
    step_number: 2,
    node_id: 'node-action',
    node_type: 'action',
    status: 'failed',
    input_data: {},
    output_data: {},
    error_message: 'Division by zero',
    duration_ms: 45,
    started_at: '2024-01-01T00:00:03Z',
    completed_at: null,
  },
];

describe('TracesScreen', () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockGet.mockResolvedValue({ data: traces });
  });

  describe('Fetch', () => {
    test('fetches traces for the execution on mount without status params', async () => {
      render(<TracesScreen route={route} />);

      await waitFor(() => {
        expect(mockGet).toHaveBeenCalledWith('/api/workflows/executions/exec-1/traces', { params: {} });
      });
    });

    test('fetches with status params when a filter is selected', async () => {
      const { getByText } = render(<TracesScreen route={route} />);

      await waitFor(() => {
        expect(getByText('Execution Traces')).toBeTruthy();
      });

      fireEvent.press(getByText('Failed'));

      await waitFor(() => {
        expect(mockGet).toHaveBeenLastCalledWith(
          '/api/workflows/executions/exec-1/traces',
          { params: { status: 'failed' } }
        );
      });
    });
  });

  describe('Rendering', () => {
    test('renders trace rows with step, node, status, and duration', async () => {
      const { getByText } = render(<TracesScreen route={route} />);

      await waitFor(() => {
        expect(getByText('Execution Traces')).toBeTruthy();
      });
      expect(getByText('Step 1')).toBeTruthy();
      expect(getByText('node-start')).toBeTruthy();
      expect(getByText('completed')).toBeTruthy();
      expect(getByText('120ms')).toBeTruthy();
      expect(getByText('Step 2')).toBeTruthy();
      expect(getByText('node-action')).toBeTruthy();
      expect(getByText('failed')).toBeTruthy();
    });

    test('renders execution id in the header', async () => {
      const { getByText } = render(<TracesScreen route={route} />);

      await waitFor(() => {
        expect(getByText('exec-1')).toBeTruthy();
      });
    });

    test('shows loading state while fetching', async () => {
      mockGet.mockReturnValue(new Promise(() => {}));
      const { getByText } = render(<TracesScreen route={route} />);
      expect(getByText('Loading traces...')).toBeTruthy();
    });

    test('shows empty state when no traces exist', async () => {
      mockGet.mockResolvedValue({ data: [] });
      const { getByText } = render(<TracesScreen route={route} />);

      await waitFor(() => {
        expect(getByText('No traces found')).toBeTruthy();
      });
    });

    test('handles fetch failure by logging and showing the empty state', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      mockGet.mockRejectedValue(new Error('network'));
      const { getByText } = render(<TracesScreen route={route} />);

      await waitFor(() => {
        expect(getByText('No traces found')).toBeTruthy();
      });
      expect(consoleSpy).toHaveBeenCalled();
      consoleSpy.mockRestore();
    });
  });

  describe('Expand/collapse', () => {
    test('expands a trace to show details', async () => {
      const { getByText, queryByText } = render(<TracesScreen route={route} />);

      await waitFor(() => {
        expect(getByText('Step 1')).toBeTruthy();
      });

      // Details hidden initially
      expect(queryByText('Type:')).toBeNull();

      fireEvent.press(getByText('Step 1'));

      expect(getByText('Type:')).toBeTruthy();
      expect(getByText('start')).toBeTruthy();
      expect(getByText('Input Data:')).toBeTruthy();
      expect(getByText(JSON.stringify({ order_id: 'ORD-1' }, null, 2))).toBeTruthy();
      expect(getByText('Output Data:')).toBeTruthy();
      expect(getByText(JSON.stringify({ ok: true }, null, 2))).toBeTruthy();

      // Collapse again
      fireEvent.press(getByText('Step 1'));
      expect(queryByText('Type:')).toBeNull();
    });

    test('shows error details for failed traces', async () => {
      const { getByText } = render(<TracesScreen route={route} />);

      await waitFor(() => {
        expect(getByText('Step 2')).toBeTruthy();
      });

      fireEvent.press(getByText('Step 2'));

      expect(getByText('Error:')).toBeTruthy();
      expect(getByText('Division by zero')).toBeTruthy();
    });
  });
});
