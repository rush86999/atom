/**
 * MemoryRecallFeed Component Tests
 *
 * Tests verify the real MemoryRecallFeed component
 * (components/Agents/MemoryRecallFeed.tsx, a NAMED export):
 * - Loading state ("Loading neural events...")
 * - Fetches GET /api/governance/analytics/trajectories?workspace_id=..&agent_id=..
 * - Renders trajectory cards (task type, outcome badge, summary, efficiency,
 *   confidence, learnings, timestamp)
 * - Empty state ("No neural events found")
 * - Client-side search filtering across summary and task type
 * - Handles fetch failures gracefully
 *
 * framer-motion is mocked (animations are irrelevant to behavior).
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import { MemoryRecallFeed } from '../MemoryRecallFeed';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

jest.mock('framer-motion', () => {
  const React = require('react');
  const make = (tag: string) =>
    React.forwardRef((props: any, ref: any) => {
      const { initial, animate, exit, transition, layoutId, ...rest } = props;
      return React.createElement(tag, { ...rest, ref });
    });
  return {
    motion: { div: make('div') },
    AnimatePresence: ({ children }: { children: any }) => children,
  };
});

const trajectories = [
  {
    id: 't1',
    agent_id: 'a1',
    task_type: 'web_research',
    outcome: 'success',
    step_efficiency: 0.2,
    timestamp: '2024-01-15T10:00:00Z',
    summary: 'Found the competitor pricing page',
    learnings: ['Always check the footer for pricing links'],
    confidence_score: 0.9,
  },
  {
    id: 't2',
    agent_id: 'a1',
    task_type: 'data_extraction',
    outcome: 'failure',
    step_efficiency: 0.8,
    timestamp: '2024-01-15T11:00:00Z',
    summary: 'Schema mismatch on the export endpoint',
    confidence_score: 0.5,
  },
];

const trajectoriesUrl = '*/api/episodes/trajectories';

describe('MemoryRecallFeed', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.use(
      rest.get(trajectoriesUrl, (req, res, ctx) =>
        res(ctx.status(200), ctx.json(trajectories))
      )
    );
  });

  it('shows the loading state on mount', () => {
    render(<MemoryRecallFeed workspaceId="ws-1" />);
    expect(screen.getByText('Loading neural events...')).toBeInTheDocument();
  });

  it('renders the feed header', async () => {
    render(<MemoryRecallFeed workspaceId="ws-1" />);

    await waitFor(() => {
      expect(screen.getByText('Episodic Memory Feed')).toBeInTheDocument();
    });
    expect(
      screen.getByText('Live stream of agent experiences and neural recalls.')
    ).toBeInTheDocument();
  });

  it('renders trajectory cards with task type, outcome, summary and metrics', async () => {
    render(<MemoryRecallFeed workspaceId="ws-1" />);

    await waitFor(() => {
      expect(screen.getByText('web research')).toBeInTheDocument();
    });

    // task_type underscores → spaces
    expect(screen.getByText('data extraction')).toBeInTheDocument();

    // Outcome badges
    expect(screen.getByText('success')).toBeInTheDocument();
    expect(screen.getByText('failure')).toBeInTheDocument();

    // Summaries
    expect(screen.getByText('Found the competitor pricing page')).toBeInTheDocument();
    expect(screen.getByText('Schema mismatch on the export endpoint')).toBeInTheDocument();

    // Efficiency = (1 - step_efficiency) * 100
    expect(screen.getByText('80%')).toBeInTheDocument();
    expect(screen.getByText('20%')).toBeInTheDocument();

    // Confidence
    expect(screen.getByText('Confidence: 90%')).toBeInTheDocument();
    expect(screen.getByText('Confidence: 50%')).toBeInTheDocument();

    // Learnings are quoted
    expect(screen.getByText('"Always check the footer for pricing links"')).toBeInTheDocument();

    // Timestamps
    expect(screen.getByText(new Date('2024-01-15T10:00:00Z').toLocaleString())).toBeInTheDocument();
  });

  it('renders the empty state when no trajectories exist', async () => {
    server.use(
      rest.get(trajectoriesUrl, (req, res, ctx) => res(ctx.status(200), ctx.json([])))
    );
    render(<MemoryRecallFeed workspaceId="ws-1" />);

    await waitFor(() => {
      expect(screen.getByText('No neural events found')).toBeInTheDocument();
    });
    expect(
      screen.getByText("Agents haven't generated any episodic traces yet.")
    ).toBeInTheDocument();
  });

  it('requests the workspace_id query parameter', async () => {
    let workspaceParam: string | null = null;
    server.use(
      rest.get(trajectoriesUrl, (req, res, ctx) => {
        workspaceParam = req.url.searchParams.get('workspace_id');
        return res(ctx.status(200), ctx.json(trajectories));
      })
    );
    render(<MemoryRecallFeed workspaceId="ws-42" />);

    await waitFor(() => {
      expect(workspaceParam).toBe('ws-42');
    });
  });

  it('adds the agent_id query parameter when provided', async () => {
    let agentParam: string | null = null;
    server.use(
      rest.get(trajectoriesUrl, (req, res, ctx) => {
        agentParam = req.url.searchParams.get('agent_id');
        return res(ctx.status(200), ctx.json(trajectories));
      })
    );
    render(<MemoryRecallFeed workspaceId="ws-1" agentId="agent-9" />);

    await waitFor(() => {
      expect(agentParam).toBe('agent-9');
    });
  });

  it('filters trajectories by search query across summary and task type', async () => {
    const user = userEvent.setup();
    render(<MemoryRecallFeed workspaceId="ws-1" />);

    await screen.findByText('web research');

    await user.type(screen.getByPlaceholderText('Search experiences...'), 'schema');

    expect(screen.getByText('data extraction')).toBeInTheDocument();
    expect(screen.queryByText('web research')).not.toBeInTheDocument();

    await user.clear(screen.getByPlaceholderText('Search experiences...'));
    await user.type(screen.getByPlaceholderText('Search experiences...'), 'research');

    expect(screen.getByText('web research')).toBeInTheDocument();
    expect(screen.queryByText('data extraction')).not.toBeInTheDocument();
  });

  it('shows the empty state when the search matches nothing', async () => {
    const user = userEvent.setup();
    render(<MemoryRecallFeed workspaceId="ws-1" />);

    await screen.findByText('web research');
    await user.type(screen.getByPlaceholderText('Search experiences...'), 'zzz-nope');

    expect(screen.getByText('No neural events found')).toBeInTheDocument();
  });

  it('defaults confidence to 85% when confidence_score is missing', async () => {
    const [{ confidence_score, ...t1 }, t2] = trajectories;
    server.use(
      rest.get(trajectoriesUrl, (req, res, ctx) =>
        res(ctx.status(200), ctx.json([{ ...t1, confidence_score: undefined }, t2]))
      )
    );
    render(<MemoryRecallFeed workspaceId="ws-1" />);

    await waitFor(() => {
      expect(screen.getByText('Confidence: 85%')).toBeInTheDocument();
    });
  });

  it('renders the empty state when the fetch returns a server error', async () => {
    server.use(
      rest.get(trajectoriesUrl, (req, res, ctx) => res(ctx.status(500), ctx.json({})))
    );
    render(<MemoryRecallFeed workspaceId="ws-1" />);

    await waitFor(() => {
      expect(screen.getByText('No neural events found')).toBeInTheDocument();
    });
  });

  it('logs the error when the request fails at the network level', async () => {
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    server.use(
      rest.get(trajectoriesUrl, (req, res, ctx) => res.networkError('boom'))
    );
    render(<MemoryRecallFeed workspaceId="ws-1" />);

    await waitFor(() => {
      expect(screen.getByText('No neural events found')).toBeInTheDocument();
    });
    expect(consoleErrorSpy).toHaveBeenCalled();
    consoleErrorSpy.mockRestore();
  });
});
