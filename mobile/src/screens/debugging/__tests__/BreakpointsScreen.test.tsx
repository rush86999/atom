/**
 * BreakpointsScreen Tests
 *
 * Testing suite for the mobile breakpoints management screen:
 * fetch/render, empty & loading states, add-breakpoint modal flow,
 * remove (with confirmation), toggle, and error alerts.
 */

import React from 'react';
import { render, fireEvent, waitFor, act } from '@testing-library/react-native';
import { Alert } from 'react-native';
import axios from 'axios';
import { BreakpointsScreen } from '../BreakpointsScreen';

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
    Plus: Icon('Plus'),
    Trash2: Icon('Trash2'),
    X: Icon('X'),
    Check: Icon('Check'),
  };
}, { virtual: true });

const mockGet = axios.get as jest.Mock;
const mockPost = axios.post as jest.Mock;
const mockPut = axios.put as jest.Mock;
const mockDelete = axios.delete as jest.Mock;
const alertMock = Alert.alert as jest.Mock;

const route = { params: { workflowId: 'wf-1' } };

const breakpoints = [
  {
    id: 'bp-1',
    node_id: 'node-action-1',
    condition: 'count > 5',
    hit_count: 3,
    hit_limit: 10,
    is_disabled: false,
  },
  {
    id: 'bp-2',
    node_id: 'node-action-2',
    condition: null,
    hit_count: 0,
    hit_limit: null,
    is_disabled: true,
  },
];

describe('BreakpointsScreen', () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPost.mockReset();
    mockPut.mockReset();
    mockDelete.mockReset();
    mockGet.mockResolvedValue({ data: breakpoints });
    mockPost.mockResolvedValue({ data: {} });
    mockPut.mockResolvedValue({ data: {} });
    mockDelete.mockResolvedValue({ data: {} });
  });

  describe('Fetch and render', () => {
    test('fetches breakpoints for the workflow on mount', async () => {
      render(<BreakpointsScreen route={route} />);

      await waitFor(() => {
        expect(mockGet).toHaveBeenCalledWith('/api/workflows/wf-1/debug/breakpoints');
      });
    });

    test('renders breakpoint details', async () => {
      const { getByText } = render(<BreakpointsScreen route={route} />);

      await waitFor(() => {
        expect(getByText('node-action-1')).toBeTruthy();
      });
      expect(getByText('Condition: count > 5')).toBeTruthy();
      expect(getByText('Hit count: 3')).toBeTruthy();
      expect(getByText('Limit: 10')).toBeTruthy();
      expect(getByText('Enabled')).toBeTruthy();
      expect(getByText('node-action-2')).toBeTruthy();
      expect(getByText('Disabled')).toBeTruthy();
    });

    test('renders empty state when no breakpoints exist', async () => {
      mockGet.mockResolvedValue({ data: [] });
      const { getByText } = render(<BreakpointsScreen route={route} />);

      await waitFor(() => {
        expect(getByText('No breakpoints set')).toBeTruthy();
      });
      expect(getByText('Tap "Add Breakpoint" to get started')).toBeTruthy();
    });

    test('shows loading text while the request is pending', async () => {
      mockGet.mockReturnValue(new Promise(() => {}));
      const { getByText } = render(<BreakpointsScreen route={route} />);
      expect(getByText('Loading breakpoints...')).toBeTruthy();
    });

    test('alerts on fetch failure', async () => {
      mockGet.mockRejectedValue(new Error('network'));
      render(<BreakpointsScreen route={route} />);

      await waitFor(() => {
        expect(alertMock).toHaveBeenCalledWith('Error', 'Failed to fetch breakpoints');
      });
    });
  });

  describe('Add breakpoint', () => {
    test('opens modal and submits a new breakpoint', async () => {
      const { getByText, getAllByText, getByPlaceholderText } =
        render(<BreakpointsScreen route={route} />);

      await waitFor(() => {
        expect(getByText('Breakpoints')).toBeTruthy();
      });

      fireEvent.press(getByText('Add Breakpoint'));

      fireEvent.changeText(getByPlaceholderText('e.g., node-action-1'), 'node-action-9');
      fireEvent.changeText(getByPlaceholderText('e.g., count > 5'), 'x > 2');
      // Two "Add Breakpoint" labels now: header button + modal confirm button
      const confirmButtons = getAllByText('Add Breakpoint');
      fireEvent.press(confirmButtons[confirmButtons.length - 1]);

      await waitFor(() => {
        expect(mockPost).toHaveBeenCalledWith('/api/workflows/wf-1/debug/breakpoints', {
          node_id: 'node-action-9',
          condition: 'x > 2',
        });
      });

      // Modal closed and inputs reset; header button still present
      await waitFor(() => {
        expect(mockGet).toHaveBeenCalledTimes(2); // initial + refetch after add
      });
    });

    test('opens modal via the header button and closes with X', async () => {
      const { getByText, getByTestId, queryByText } = render(<BreakpointsScreen route={route} />);

      await waitFor(() => {
        expect(getByText('Breakpoints')).toBeTruthy();
      });

      fireEvent.press(getByText('Add Breakpoint'));
      expect(getByText('Node ID')).toBeTruthy();

      fireEvent.press(getByTestId('X'));
      expect(queryByText('Node ID')).toBeNull();
    });

    test('alerts when node ID is empty', async () => {
      const { getByText, getAllByText } = render(<BreakpointsScreen route={route} />);

      await waitFor(() => {
        expect(getByText('Breakpoints')).toBeTruthy();
      });

      fireEvent.press(getByText('Add Breakpoint'));
      // The confirm button is the last "Add Breakpoint" label (inside the modal)
      const confirmButtons = getAllByText('Add Breakpoint');
      fireEvent.press(confirmButtons[confirmButtons.length - 1]);

      await waitFor(() => {
        expect(alertMock).toHaveBeenCalledWith('Error', 'Please enter a node ID');
      });
      expect(mockPost).not.toHaveBeenCalled();
    });

    test('submits with null condition when left blank', async () => {
      const { getByText, getAllByText, getByPlaceholderText } = render(<BreakpointsScreen route={route} />);

      await waitFor(() => {
        expect(getByText('Breakpoints')).toBeTruthy();
      });

      fireEvent.press(getByText('Add Breakpoint'));
      fireEvent.changeText(getByPlaceholderText('e.g., node-action-1'), 'node-7');
      const confirmButtons = getAllByText('Add Breakpoint');
      fireEvent.press(confirmButtons[confirmButtons.length - 1]);

      await waitFor(() => {
        expect(mockPost).toHaveBeenCalledWith('/api/workflows/wf-1/debug/breakpoints', {
          node_id: 'node-7',
          condition: null,
        });
      });
    });

    test('alerts when add fails', async () => {
      mockPost.mockRejectedValue(new Error('boom'));
      const { getByText, getAllByText, getByPlaceholderText } = render(<BreakpointsScreen route={route} />);

      await waitFor(() => {
        expect(getByText('Breakpoints')).toBeTruthy();
      });

      fireEvent.press(getByText('Add Breakpoint'));
      fireEvent.changeText(getByPlaceholderText('e.g., node-action-1'), 'node-7');
      const confirmButtons = getAllByText('Add Breakpoint');
      fireEvent.press(confirmButtons[confirmButtons.length - 1]);

      await waitFor(() => {
        expect(alertMock).toHaveBeenCalledWith('Error', 'Failed to add breakpoint');
      });
    });
  });

  describe('Remove breakpoint', () => {
    test('asks for confirmation then deletes', async () => {
      const { getByText, getAllByText } = render(<BreakpointsScreen route={route} />);

      await waitFor(() => {
        expect(getByText('node-action-1')).toBeTruthy();
      });

      const removeButtons = getAllByText('Remove');
      fireEvent.press(removeButtons[0]);

      expect(alertMock).toHaveBeenCalledWith(
        'Remove Breakpoint',
        'Are you sure you want to remove this breakpoint?',
        expect.any(Array)
      );

      const buttons = alertMock.mock.calls[0][2];
      await act(async () => { await buttons[1].onPress(); });

      expect(mockDelete).toHaveBeenCalledWith('/api/workflows/debug/breakpoints/bp-1');
      // Refetch after deletion
      await waitFor(() => {
        expect(mockGet).toHaveBeenCalledTimes(2);
      });
    });

    test('alerts when delete fails', async () => {
      mockDelete.mockRejectedValue(new Error('boom'));
      const { getByText, getAllByText } = render(<BreakpointsScreen route={route} />);

      await waitFor(() => {
        expect(getByText('node-action-1')).toBeTruthy();
      });

      const removeButtons = getAllByText('Remove');
      fireEvent.press(removeButtons[0]);
      const buttons = alertMock.mock.calls[0][2];
      await act(async () => { await buttons[1].onPress(); });

      await waitFor(() => {
        expect(alertMock).toHaveBeenCalledWith('Error', 'Failed to remove breakpoint');
      });
    });
  });

  describe('Toggle breakpoint', () => {
    test('toggles via the enable/disable button', async () => {
      const { getByText } = render(<BreakpointsScreen route={route} />);

      await waitFor(() => {
        expect(getByText('Enabled')).toBeTruthy();
      });

      fireEvent.press(getByText('Enabled'));

      await waitFor(() => {
        expect(mockPut).toHaveBeenCalledWith('/api/workflows/debug/breakpoints/bp-1/toggle');
      });
      // Refetch after toggle
      await waitFor(() => {
        expect(mockGet).toHaveBeenCalledTimes(2);
      });
    });

    test('alerts when toggle fails', async () => {
      mockPut.mockRejectedValue(new Error('boom'));
      const { getByText } = render(<BreakpointsScreen route={route} />);

      await waitFor(() => {
        expect(getByText('Enabled')).toBeTruthy();
      });

      fireEvent.press(getByText('Enabled'));

      await waitFor(() => {
        expect(alertMock).toHaveBeenCalledWith('Error', 'Failed to toggle breakpoint');
      });
    });
  });
});
