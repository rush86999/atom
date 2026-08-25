/**
 * Guided agent creation UI tests.
 *
 * Verifies the employee self-serve flow (components/Agents/GuidedAgentCreator.tsx):
 * - goal textarea + optional context
 * - history-mined suggestion chips prefill the goal
 * - success state sets maturity expectations (STUDENT, what comes next)
 * - agent-initiated creations surface the pending-approval state
 * - validation error for too-short goals
 *
 * The API client module is mocked — these are component behavior tests.
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import { GuidedAgentCreator } from '../GuidedAgentCreator';
import * as api from '@/lib/agent-onboarding-api';

jest.mock('@/lib/agent-onboarding-api', () => ({
  createGuidedAgent: jest.fn(),
  getAutomationSuggestions: jest.fn(),
}));

const mockedCreate = api.createGuidedAgent as jest.Mock;
const mockedSuggestions = api.getAutomationSuggestions as jest.Mock;

const renderCreator = (props: any = {}) =>
  render(
    <GuidedAgentCreator
      open
      onOpenChange={jest.fn()}
      onAgentCreated={jest.fn()}
      {...props}
    />
  );

describe('GuidedAgentCreator', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedSuggestions.mockResolvedValue({
      history_summary: {},
      suggestions: [
        {
          title: 'Automate: vendor invoice collection',
          description: 'Vendor invoices have been collected manually 12 times.',
          evidence: 'manual run count: 12',
        },
      ],
    });
  });

  it('renders goal and context inputs', async () => {
    renderCreator();
    expect(screen.getByTestId('guided-goal-input')).toBeInTheDocument();
    expect(screen.getByTestId('guided-context-input')).toBeInTheDocument();
    expect(screen.getByTestId('guided-create-button')).toBeInTheDocument();
  });

  it('shows suggestion chips from workspace history and prefills on click', async () => {
    renderCreator();
    const chip = await screen.findByTestId('guided-suggestion-chip-Automate: ve');
    expect(chip).toBeInTheDocument();

    await userEvent.click(chip);
    const goal = screen.getByTestId('guided-goal-input') as HTMLTextAreaElement;
    expect(goal.value).toContain('Vendor invoices');
  });

  it('rejects too-short goals with a helpful message', async () => {
    renderCreator();
    await userEvent.type(screen.getByTestId('guided-goal-input'), 'hi');
    await userEvent.click(screen.getByTestId('guided-create-button'));
    expect(await screen.findByTestId('guided-error')).toBeInTheDocument();
    expect(mockedCreate).not.toHaveBeenCalled();
  });

  it('shows success state with STUDENT maturity expectations', async () => {
    mockedCreate.mockResolvedValue({
      agent_id: 'agent-1',
      name: 'Invoice Watchdog',
      category: 'Finance',
      maturity: 'student',
      created_by: 'employee',
    });
    renderCreator();

    await userEvent.type(screen.getByTestId('guided-goal-input'), 'watch invoices and flag overdue ones');
    await userEvent.click(screen.getByTestId('guided-create-button'));

    const success = await screen.findByTestId('guided-success');
    expect(success).toBeInTheDocument();
    expect(screen.getByText(/Invoice Watchdog is here/)).toBeInTheDocument();
    expect(success.textContent).toContain('Student');
    expect(success.textContent).toContain('When will it be useful?');
  });

  it('shows pending-approval state for agent-initiated creation', async () => {
    mockedCreate.mockResolvedValue({
      status: 'pending_approval',
      hitl_action_id: 'hitl-1',
      reason: 'Trust policy requires human approval',
    });
    renderCreator();

    await userEvent.type(screen.getByTestId('guided-goal-input'), 'watch invoices and flag overdue ones');
    await userEvent.click(screen.getByTestId('guided-create-button'));

    const pending = await screen.findByTestId('guided-pending');
    expect(pending).toBeInTheDocument();
    expect(pending.textContent).toContain('Trust policy requires human approval');
  });

  it('surfaces API errors instead of failing silently', async () => {
    mockedCreate.mockRejectedValue({
      response: { data: { detail: 'Goal is too short' } },
    });
    renderCreator();

    await userEvent.type(screen.getByTestId('guided-goal-input'), 'a perfectly good longer goal');
    await userEvent.click(screen.getByTestId('guided-create-button'));

    expect(await screen.findByTestId('guided-error')).toHaveTextContent('Goal is too short');
  });

  it('seeds the goal from initialGoal prop (suggestion card hand-off)', async () => {
    renderCreator({ initialGoal: 'Collect vendor invoices every morning' });
    const goal = screen.getByTestId('guided-goal-input') as HTMLTextAreaElement;
    await waitFor(() => expect(goal.value).toBe('Collect vendor invoices every morning'));
  });
});
