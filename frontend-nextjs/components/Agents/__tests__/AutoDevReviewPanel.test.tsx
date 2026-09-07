/**
 * AutoDevReviewPanel tests — the supervisor journey for the evolution
 * harness: pending fix proposals (Memento skills / AlphaEvolver tool
 * mutations) render with approve/reject, tool-error patterns surface for
 * the selected agent, and empty states explain the contract.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

const mockGet = jest.fn();
const mockPost = jest.fn();

jest.mock('@/hooks/useWebSocket', () => ({
  __esModule: true,
  useWebSocket: () => ({ lastMessage: null }),
}));

jest.mock('@/lib/api', () => ({
  __esModule: true,
  apiClient: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
  },
}));

import { AutoDevReviewPanel } from '../AutoDevReviewPanel';

const CANDIDATES_RESPONSE = {
  data: {
    candidates: [
      {
        kind: 'mutation',
        id: 'mut-1',
        agent_id: null,
        name: 'outlook.search_emails',
        description: 'Proposed fix for recurring tool failure in outlook.search_emails',
        failure: "tool_error: 400 Syntax error: character '@' is not valid",
        code: 'def search_emails(...): ...',
        status: 'pending',
        created_at: '2026-09-02T12:00:00Z',
      },
    ],
    count: 1,
  },
};

const TOOL_ERRORS_RESPONSE = {
  data: {
    tool_errors: [
      {
        signature: 'outlook.search_emails',
        count: 3,
        last_error: "tool_error: 400 Syntax error: character '@' is not valid",
        last_seen: '2026-09-02T12:00:00+00:00',
      },
    ],
    count: 1,
  },
};

describe('AutoDevReviewPanel', () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPost.mockReset();
  });

  it('renders pending fix proposals and approves them', async () => {
    mockGet.mockImplementation((url: string) => {
      if (String(url).includes('/candidates')) {
        return Promise.resolve({ data: CANDIDATES_RESPONSE });
      }
      if (String(url).includes('/guidance')) {
        return Promise.resolve({
          data: {
            data: {
              guidance: [
                {
                  id: 'g1',
                  agent_id: 'agent-1',
                  kind: 'tool_error_pattern',
                  title: 'outlook.search_emails has failed 3× recently',
                  detail: "tool_error: 400 Syntax error: character '@' is not valid",
                  importance: 2,
                  timestamp: '2026-09-02T12:00:00Z',
                },
              ],
              count: 1,
            },
          },
        });
      }
      return Promise.resolve({ data: TOOL_ERRORS_RESPONSE });
    });
    mockPost.mockResolvedValue({ data: { success: true } });

    render(<AutoDevReviewPanel agentId="agent-1" />);

    await waitFor(() => {
      expect(screen.getAllByText('outlook.search_emails').length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText(/400 Syntax error/).length).toBeGreaterThan(0);
    expect(screen.getByText(/has failed 3/)).toBeInTheDocument();

    fireEvent.click(screen.getByText('Approve'));
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/autodev/mutations/mut-1/approve');
    });
  });

  it('surfaces recent tool errors for the selected agent', async () => {
    mockGet.mockImplementation((url: string) => {
      if (String(url).includes('/candidates')) {
        return Promise.resolve({ data: { data: { candidates: [], count: 0 } } });
      }
      return Promise.resolve({ data: TOOL_ERRORS_RESPONSE });
    });

    render(<AutoDevReviewPanel agentId="agent-1" />);

    await waitFor(() => {
      expect(screen.getByText('outlook.search_emails')).toBeInTheDocument();
      expect(screen.getByText('3×')).toBeInTheDocument();
    });
  });

  it('shows the nothing-pending contract when empty', async () => {
    mockGet.mockImplementation((url: string) =>
      Promise.resolve({ data: { data: [], count: 0 } })
    );

    render(<AutoDevReviewPanel />);

    await waitFor(() => {
      expect(
        screen.getByText(/No pending fixes/)
      ).toBeInTheDocument();
    });
    expect(screen.queryByText('Recent tool errors')).not.toBeInTheDocument();
  });
});
