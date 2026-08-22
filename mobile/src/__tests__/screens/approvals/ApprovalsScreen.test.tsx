/**
 * ApprovalsService + ApprovalsScreen tests
 *
 * Round 80s — mobile parity for the HITL approval journey.
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react-native';
import ApprovalsScreen from '../../../screens/approvals/ApprovalsScreen';
import {
  getPendingApprovals,
  approveWorkflow,
  rejectWorkflow,
} from '../../../services/approvalsService';

jest.mock('../../../services/approvalsService', () => ({
  ...jest.requireActual('../../../services/approvalsService'),
  getPendingApprovals: jest.fn(),
  approveWorkflow: jest.fn(),
  rejectWorkflow: jest.fn(),
}));

const mockedGet = getPendingApprovals as jest.Mock;
const mockedApprove = approveWorkflow as jest.Mock;
const mockedReject = rejectWorkflow as jest.Mock;

const pending = [
  {
    id: 'apr-1',
    workflow_name: 'CI/CD Pipeline',
    agent_name: 'Engineering Agent',
    maturity_level: 'student',
    requested_by: 'alex@atom.dev',
  },
  {
    id: 'apr-2',
    workflow_name: 'Invoice Export',
    agent_name: 'Finance Agent',
    maturity_level: 'intern',
  },
];

beforeEach(() => {
  jest.clearAllMocks();
});

describe('ApprovalsScreen', () => {
  it('renders pending approvals from the governance API', async () => {
    mockedGet.mockResolvedValue(pending);
    render(<ApprovalsScreen />);

    await waitFor(() => {
      expect(screen.getByTestId('approval-card-apr-1')).toBeTruthy();
    });
    expect(screen.getByText('CI/CD Pipeline')).toBeTruthy();
    expect(screen.getByText('Invoice Export')).toBeTruthy();
  });

  it('shows the empty state when nothing is pending', async () => {
    mockedGet.mockResolvedValue([]);
    render(<ApprovalsScreen />);
    await waitFor(() =>
      expect(screen.getByTestId('approvals-empty')).toBeTruthy()
    );
  });

  it('surfaces load errors', async () => {
    mockedGet.mockRejectedValue(new Error('backend down'));
    render(<ApprovalsScreen />);
    await waitFor(() =>
      expect(screen.getByText(/backend down/i)).toBeTruthy()
    );
  });

  it('approves inline and removes the card', async () => {
    mockedGet.mockResolvedValue(pending);
    mockedApprove.mockResolvedValue(undefined);
    render(<ApprovalsScreen />);
    const btn = await screen.findByTestId('approve-apr-1');
    fireEvent.press(btn);
    await waitFor(() => expect(mockedApprove).toHaveBeenCalledWith('apr-1'));
    await waitFor(() =>
      expect(screen.queryByTestId('approval-card-apr-1')).toBeNull()
    );
    // apr-2 remains
    expect(screen.getByTestId('approval-card-apr-2')).toBeTruthy();
  });

  it('rejects inline and removes the card', async () => {
    mockedGet.mockResolvedValue(pending);
    mockedReject.mockResolvedValue(undefined);
    render(<ApprovalsScreen />);
    const btn = await screen.findByTestId('reject-apr-2');
    fireEvent.press(btn);
    await waitFor(() => expect(mockedReject).toHaveBeenCalledWith('apr-2'));
    await waitFor(() =>
      expect(screen.queryByTestId('approval-card-apr-2')).toBeNull()
    );
  });

  it('surfaces action errors without removing the card', async () => {
    mockedGet.mockResolvedValue(pending);
    mockedApprove.mockRejectedValue(new Error('TEAM_LEAD required'));
    render(<ApprovalsScreen />);
    fireEvent.press(await screen.findByTestId('approve-apr-1'));
    await waitFor(() =>
      expect(screen.getByText(/TEAM_LEAD required/i)).toBeTruthy()
    );
    expect(screen.getByTestId('approval-card-apr-1')).toBeTruthy();
  });
});
