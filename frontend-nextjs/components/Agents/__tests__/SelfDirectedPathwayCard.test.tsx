import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { SelfDirectedPathwayCard } from '../SelfDirectedPathwayCard';

const base = {
  agent_id: 'agent-1',
  agent_name: 'Student Hire',
  category: 'operations',
  tier: 'student',
  confidence: 0.6,
  episode_progress: 1,
  ready_for_review: true,
  completed_sessions: 3,
  evidence: { episodes: 10, successes: 10, success_ratio: 1, required_episodes: 10 },
  readiness: { ready: true, pathway: 'self_directed', reason: null },
  recent_episodes: [],
  guidance: [],
};

describe('SelfDirectedPathwayCard qualification state', () => {
  it('valid assessment has no blocking note and promotes', () => {
    const onPromote = jest.fn();
    render(
      <SelfDirectedPathwayCard
        progress={{ ...base, assessment: { allowed: true, required: true, state: 'valid' } }}
        onPromote={onPromote}
      />,
    );
    expect(screen.queryByText(/Capability qualification review required/)).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId('self-directed-promote-button'));
    expect(onPromote).toHaveBeenCalledTimes(1);
  });

  it('missing assessment shows the blocking review note', () => {
    render(
      <SelfDirectedPathwayCard
        progress={{ ...base, assessment: { allowed: false, required: true, state: 'unknown' } }}
      />,
    );
    expect(screen.getByText(/Capability qualification review required/)).toBeInTheDocument();
  });

  it('failed/stale assessment shows the blocking review note', () => {
    for (const state of ['unresolved_failed', 'unresolved_stale']) {
      const { unmount } = render(
        <SelfDirectedPathwayCard
          progress={{ ...base, assessment: { allowed: false, required: true, state } }}
        />,
      );
      expect(screen.getByText(/Capability qualification review required/)).toBeInTheDocument();
      unmount();
    }
  });

  it('explicit owner exception is not shown as a blocking review', () => {
    render(
      <SelfDirectedPathwayCard
        progress={{
          ...base,
          assessment: {
            allowed: true,
            required: true,
            state: 'legacy_unassessed',
            exception: { kind: 'legacy_unassessed', reason: 'Owner approved' },
          },
        }}
      />,
    );
    expect(screen.queryByText(/Capability qualification review required/)).not.toBeInTheDocument();
  });
});
