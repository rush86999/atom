/**
 * MaturityApprovalPanel tests
 *
 * Mocks lib/maturity-api and verifies the supervisor journey contract:
 * - Renders pending training + action proposals with Approve/Reject
 * - Approve(training) -> session returned -> "Mark completed" form appears
 * - Completing calls completeTrainingSession and surfaces promotion notice
 * - Reject requires a reason
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';

const mockApi = {
  listTrainingProposals: jest.fn(),
  listActionProposals: jest.fn(),
  approveTrainingProposal: jest.fn(),
  rejectTrainingProposal: jest.fn(),
  completeTrainingSession: jest.fn(),
  approveActionProposal: jest.fn(),
  rejectActionProposal: jest.fn(),
};

jest.mock('../../../lib/maturity-api', () => ({
  __esModule: true,
  ...mockApi,
}));

import { MaturityApprovalPanel } from '../MaturityApprovalPanel';

const trainingProposal = {
  id: 'tp-1',
  title: 'Training Proposal: Email Agent',
  agent_name: 'Email Agent',
  status: 'pending_approval',
  capability_gaps: ['email'],
};

const actionProposal = {
  id: 'ap-1',
  title: 'Create lead at Acme',
  agent_name: 'Sales Agent',
  status: 'pending_approval',
};

beforeEach(() => {
  jest.resetAllMocks();
  mockApi.listTrainingProposals.mockResolvedValue([trainingProposal]);
  mockApi.listActionProposals.mockResolvedValue([actionProposal]);
});

describe('MaturityApprovalPanel', () => {
  test('renders pending proposals from both journeys', async () => {
    render(<MaturityApprovalPanel />);

    await waitFor(() => {
      expect(screen.getByText(/Training Proposal: Email Agent/)).toBeInTheDocument();
      expect(screen.getByText(/Create lead at Acme/)).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: 'Approve' })).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Approve & execute/ })
    ).toBeInTheDocument();
  });

  test('approve training opens completion form; completing surfaces promotion', async () => {
    const user = userEvent.setup();
    mockApi.approveTrainingProposal.mockResolvedValue({
      session_id: 'sess-1',
      proposal_id: 'tp-1',
    });
    mockApi.completeTrainingSession.mockResolvedValue({
      session_id: 'sess-1',
      promoted_to_intern: true,
    });

    render(<MaturityApprovalPanel />);

    // Two "Approve" buttons (one per journey); pick the training one.
    await waitFor(() => screen.getByText(/Training Proposal: Email Agent/));
    await user.click(
      screen.getAllByRole('button', { name: 'Approve' })[0]
    );

    await waitFor(() =>
      expect(screen.getByTestId('complete-training-form')).toBeInTheDocument()
    );

    await user.click(screen.getByRole('button', { name: 'Mark completed' }));

    await waitFor(() =>
      expect(
        screen.getByText(/promoted to INTERN/i)
      ).toBeInTheDocument()
    );
    expect(mockApi.completeTrainingSession).toHaveBeenCalledWith(
      'sess-1',
      expect.objectContaining({ performance_score: 0.9, tasks_completed: 10 })
    );
  });

  test('reject requires a reason before confirming', async () => {
    const user = userEvent.setup();
    render(<MaturityApprovalPanel />);

    await waitFor(() => screen.getByText(/Training Proposal: Email Agent/));
    await user.click(
      screen.getAllByRole('button', { name: 'Reject' })[0]
    );

    const confirm = screen.getByRole('button', { name: 'Confirm' });
    expect(confirm).toBeDisabled();

    await user.type(screen.getByLabelText('Rejection reason'), 'not ready');
    expect(confirm).toBeEnabled();

    await user.click(confirm);
    await waitFor(() =>
      expect(mockApi.rejectTrainingProposal).toHaveBeenCalledWith(
        'tp-1',
        'not ready'
      )
    );
  });

  test('approve action proposal executes via API', async () => {
    const user = userEvent.setup();
    mockApi.approveActionProposal.mockResolvedValue({
      execution_result: { success: true },
    });

    render(<MaturityApprovalPanel />);
    await waitFor(() => screen.getByText(/Create lead at Acme/));

    await user.click(screen.getByRole('button', { name: /Approve & execute/ }));
    await waitFor(() =>
      expect(mockApi.approveActionProposal).toHaveBeenCalledWith('ap-1')
    );
    await waitFor(() =>
      expect(screen.getByText(/approved and executed/i)).toBeInTheDocument()
    );
  });

  test('shows error state when fetch fails', async () => {
    mockApi.listTrainingProposals.mockRejectedValue(new Error('boom'));
    render(<MaturityApprovalPanel />);
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('boom'));
  });
});
