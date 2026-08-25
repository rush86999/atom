/**
 * Agent maturity guide dialog tests.
 *
 * Verifies the user-facing readiness report
 * (components/Agents/AgentMaturityGuide.tsx): current level, plain-language
 * can/cannot/useful-for guidance, readiness progress, pathway counts, and
 * how-to-advance — everything a user needs to know when the agent becomes
 * useful.
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { AgentMaturityGuideDialog } from '../AgentMaturityGuide';
import * as api from '@/lib/agent-onboarding-api';

jest.mock('@/lib/agent-onboarding-api', () => ({
  getAgentMaturityGuide: jest.fn(),
}));

const mockedGuide = api.getAgentMaturityGuide as jest.Mock;

const SAMPLE_GUIDE = {
  agent_id: 'agent-1',
  agent_name: 'Invoice Watchdog',
  current_level: 'student',
  level_guide: {
    level: 'student',
    title: 'Student — learning the ropes',
    what_it_can_do: 'Watch, search, read, and summarize.',
    what_it_cannot_do: 'Nothing that changes anything.',
    useful_for: 'Not directly useful yet — it is building context.',
  },
  what_it_can_do_today: { complexity_band: 1, example_actions: ['search', 'read'] },
  learning_progress: {
    role: 'finance_analyst',
    curriculum: ['invoices'],
    lessons_from_teacher: 3,
    observations: 12,
    pathways_used: ['observation', 'teacher'],
  },
  mastery: { mastered: ['invoices'], in_progress: { reconciliation: 1 }, threshold: 3 },
  readiness: {
    ready_for_graduation_review: false,
    confidence: 0.22,
    confidence_needed_for_training_review: 0.45,
    note: '23 more observations roughly reach the review threshold.',
  },
  next_level: 'intern',
  how_to_advance: 'Complete training sessions and pass the graduation exam.',
};

describe('AgentMaturityGuideDialog', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedGuide.mockResolvedValue(SAMPLE_GUIDE);
  });

  it('renders current level, next level, and role', async () => {
    render(<AgentMaturityGuideDialog agentId="agent-1" open onOpenChange={jest.fn()} />);
    const content = await screen.findByTestId('agent-maturity-guide-content');
    expect(content.textContent).toContain('student');
    expect(content.textContent).toContain('intern');
    expect(content.textContent).toContain('finance_analyst');
  });

  it('answers when the agent is useful in plain language', async () => {
    render(<AgentMaturityGuideDialog agentId="agent-1" open onOpenChange={jest.fn()} />);
    const content = await screen.findByTestId('agent-maturity-guide-content');
    expect(content.textContent).toContain('Watch, search, read, and summarize.');
    expect(content.textContent).toContain('Not directly useful yet');
  });

  it('shows learning pathway counts (lessons vs observations)', async () => {
    render(<AgentMaturityGuideDialog agentId="agent-1" open onOpenChange={jest.fn()} />);
    expect(await screen.findByTestId('maturity-lessons')).toHaveTextContent('3');
    expect(screen.getByTestId('maturity-observations')).toHaveTextContent('12');
  });

  it('shows mastery topics with progress toward the threshold', async () => {
    render(<AgentMaturityGuideDialog agentId="agent-1" open onOpenChange={jest.fn()} />);
    const content = await screen.findByTestId('agent-maturity-guide-content');
    expect(content.textContent).toContain('invoices');
    expect(content.textContent).toContain('reconciliation 1/3');
  });

  it('shows the readiness note and how to advance', async () => {
    render(<AgentMaturityGuideDialog agentId="agent-1" open onOpenChange={jest.fn()} />);
    expect(await screen.findByTestId('maturity-readiness-note')).toHaveTextContent('23 more observations');
    expect(screen.getByTestId('maturity-advance').textContent).toContain('graduation exam');
  });

  it('shows an error message when the API fails', async () => {
    mockedGuide.mockRejectedValue(new Error('network'));
    render(<AgentMaturityGuideDialog agentId="agent-1" open onOpenChange={jest.fn()} />);
    await waitFor(() =>
      expect(screen.getByText(/could not load the maturity guide/i)).toBeInTheDocument()
    );
  });
});
