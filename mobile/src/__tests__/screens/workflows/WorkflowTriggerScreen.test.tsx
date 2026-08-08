/**
 * WorkflowTriggerScreen Component Tests
 *
 * Tests for parameter editing, execution mode selection, trigger payload
 * construction, success/error alerts, and navigation on success.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { WorkflowTriggerScreen } from '../../../screens/workflows/WorkflowTriggerScreen';

const mockNavigation = {
  navigate: jest.fn(),
  goBack: jest.fn(),
  setOptions: jest.fn(),
  reset: jest.fn(),
};

jest.mock('@react-navigation/native', () => ({
  useNavigation: () => mockNavigation,
  useRoute: () => ({
    params: { workflowId: 'wf-1', workflowName: 'Test Workflow' },
  }),
}));

jest.mock('../../../services/workflowService', () => ({
  triggerWorkflow: jest.fn(),
}));

const { triggerWorkflow } = require('../../../services/workflowService');

const Alert = require('react-native/Libraries/Alert/Alert').alert;

describe('WorkflowTriggerScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders workflow name and empty parameter hint', async () => {
      render(<WorkflowTriggerScreen />);

      expect(screen.getAllByText('Trigger Workflow').length).toBe(2);
      expect(getByText('Test Workflow')).toBeTruthy();
      expect(getByText('No parameters configured. Tap + to add parameters.')).toBeTruthy();
      expect(screen.getAllByText('Trigger Workflow').length).toBe(2);
    });

    it('renders async info text by default', async () => {
      render(<WorkflowTriggerScreen />);

      expect(
        getByText('You can track execution progress using the execution ID returned in the response.')
      ).toBeTruthy();
    });
  });

  describe('Parameter Management', () => {
    it('adds a parameter row on + press', async () => {
      render(<WorkflowTriggerScreen />);

      fireEvent.press(screen.getByTestId('icon-add-circle'));

      expect(getByPlaceholderText('Parameter name')).toBeTruthy();
      expect(getByPlaceholderText('Value')).toBeTruthy();
    });

    it('edits parameter key and value', async () => {
      render(<WorkflowTriggerScreen />);

      fireEvent.press(screen.getByTestId('icon-add-circle'));

      fireEvent.changeText(getByPlaceholderText('Parameter name'), 'symbol');
      fireEvent.changeText(getByPlaceholderText('Value'), 'AAPL');

      fireEvent.press(screen.getByTestId('icon-flash'));

      await waitFor(() => {
        expect(triggerWorkflow).toHaveBeenCalledWith({
          workflow_id: 'wf-1',
          parameters: { symbol: 'AAPL' },
          synchronous: false,
        });
      });
    });

    it('removes a parameter row', async () => {
      render(<WorkflowTriggerScreen />);

      fireEvent.press(screen.getByTestId('icon-add-circle'));
      fireEvent.changeText(getByPlaceholderText('Parameter name'), 'foo');
      expect(getByPlaceholderText('Parameter name')).toBeTruthy();

      fireEvent.press(screen.getByTestId('icon-close-circle'));

      expect(queryByPlaceholderText('Parameter name')).toBeNull();
      expect(
        getByText('No parameters configured. Tap + to add parameters.')
      ).toBeTruthy();
    });

    it('omits parameters from payload when none configured', async () => {
      triggerWorkflow.mockResolvedValue({
        execution_id: 'exec-1',
        status: 'running',
        message: 'Workflow started',
      });

      render(<WorkflowTriggerScreen />);

      fireEvent.press(screen.getByTestId('icon-flash'));

      await waitFor(() => {
        expect(triggerWorkflow).toHaveBeenCalledWith({
          workflow_id: 'wf-1',
          parameters: undefined,
          synchronous: false,
        });
      });
    });
  });

  describe('Execution Mode', () => {
    it('switches to synchronous mode and shows the sync info text', async () => {
      render(<WorkflowTriggerScreen />);

      fireEvent.press(getByText('Synchronous'));

      expect(
        getByText(
          'Synchronous mode may timeout for long-running workflows. Use asynchronous mode for workflows that take more than 30 seconds.'
        )
      ).toBeTruthy();
    });

    it('sends synchronous flag when synchronous mode is selected', async () => {
      triggerWorkflow.mockResolvedValue({
        execution_id: 'exec-1',
        status: 'completed',
        message: 'Done',
      });

      render(<WorkflowTriggerScreen />);

      fireEvent.press(getByText('Synchronous'));
      fireEvent.press(screen.getByTestId('icon-flash'));

      await waitFor(() => {
        expect(triggerWorkflow).toHaveBeenCalledWith({
          workflow_id: 'wf-1',
          parameters: undefined,
          synchronous: true,
        });
      });
    });
  });

  describe('Trigger Flow', () => {
    it('shows success alert and navigates back on OK', async () => {
      triggerWorkflow.mockResolvedValue({
        execution_id: 'exec-42',
        status: 'running',
        message: 'Workflow started',
      });

      render(<WorkflowTriggerScreen />);

      fireEvent.press(screen.getByTestId('icon-flash'));

      await waitFor(() => {
        expect(Alert).toHaveBeenCalledWith(
          'Success',
          expect.stringContaining('exec-42'),
          expect.any(Array)
        );
      });

      const buttons = Alert.mock.calls[Alert.mock.calls.length - 1][2];
      buttons[0].onPress();
      expect(mockNavigation.goBack).toHaveBeenCalled();
    });

    it('shows error alert when trigger fails', async () => {
      triggerWorkflow.mockRejectedValue(new Error('Workflow not found'));

      render(<WorkflowTriggerScreen />);

      fireEvent.press(screen.getByTestId('icon-flash'));

      await waitFor(() => {
        expect(Alert).toHaveBeenCalledWith('Error', 'Workflow not found');
      });
    });
  });
});

function getByText(text: string | RegExp) {
  return screen.getByText(text);
}

function getByPlaceholderText(text: string) {
  return screen.getByPlaceholderText(text);
}

function queryByPlaceholderText(text: string) {
  return screen.queryByPlaceholderText(text);
}
