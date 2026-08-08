/**
 * SalesCommandCenter Component Tests
 *
 * Tests verify the real SalesCommandCenter dashboard
 * (components/dashboards/SalesCommandCenter.tsx):
 * - renders KPI cards (Total Pipeline, Active Deals, Win Rate, Avg Deal Size)
 *   with formatted values from useLiveSales stats
 * - renders deals in the table with value formatting, status and platform
 *   badges (salesforce / hubspot color mapping)
 * - fetches insights on mount via apiClient and renders severity-coded cards
 * - insight action button POSTs /api/intelligence/execute and toasts success
 * - workflow escalate_deal_blocker insight navigates to /projects?highlight=
 * - no insights → "No critical anomalies detected" empty state
 * - memory search shows result cards / no-results state
 * - WebSocket status_update refreshes sales data + toasts
 * - deals table and KPIs render with zero data without crashing
 *
 * APIs: GET /api/intelligence/insights (apiClient),
 *       POST /api/intelligence/execute (apiClient)
 */
import React from 'react';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

// --- WS mock: React state so a new lastMessage re-renders the component ---
let _setLastMessage: (m: any) => void = () => {};

jest.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: () => {
    const React = require('react');
    const [lm, setLm] = React.useState(null);
    _setLastMessage = setLm;
    return { lastMessage: lm, isConnected: false };
  },
}));

const refreshSpy = jest.fn();
let liveDeals: any[] = [];
let liveStats: any = {};

jest.mock('@/hooks/useLiveSales', () => ({
  useLiveSales: () => ({
    deals: liveDeals,
    stats: liveStats,
    isLoading: false,
    activeProviders: {},
    refresh: refreshSpy,
  }),
}));

const searchSpy = jest.fn();
let searchResults: any[] = [];
let isSearching = false;

jest.mock('@/hooks/useMemorySearch', () => ({
  useMemorySearch: () => ({
    results: searchResults,
    isSearching,
    searchMemory: searchSpy,
    clearSearch: jest.fn(),
  }),
}));

jest.mock('@/components/shared/CommentSection', () => ({
  CommentSection: () => null,
}));

jest.mock('@/components/shared/PipelineSettingsPanel', () => ({
  PipelineSettingsPanel: () => null,
}));

const mockToast = { success: jest.fn(), error: jest.fn(), info: jest.fn() };
jest.mock('sonner', () => ({
  toast: mockToast,
}));

const mockPush = jest.fn();
let routerQuery: Record<string, string> = {};
jest.mock('next/router', () => ({
  useRouter: () => ({
    route: '/sales',
    pathname: '/sales',
    query: routerQuery,
    asPath: '/sales',
    push: mockPush,
    replace: jest.fn(),
    reload: jest.fn(),
    back: jest.fn(),
    prefetch: jest.fn(),
    beforePopState: jest.fn(),
    events: { on: jest.fn(), off: jest.fn(), emit: jest.fn() },
  }),
}));

const mockApiGet = jest.fn();
const mockApiPost = jest.fn();
jest.mock('@/lib/api', () => ({
  apiClient: { get: mockApiGet, post: mockApiPost },
}));

import { SalesCommandCenter } from '../SalesCommandCenter';

describe('SalesCommandCenter', () => {
  let postedActions: any[];

  beforeEach(() => {
    jest.clearAllMocks();
    liveDeals = [
      { id: 'd1', deal_name: 'Acme renewal', company: 'Acme Corp', value: 250000, status: 'Open', platform: 'salesforce' },
      { id: 'd2', deal_name: 'Globex expansion', company: 'Globex', value: 75000, status: 'Won', platform: 'hubspot' },
    ];
    liveStats = {
      total_pipeline_value: 1000000,
      active_deal_count: 12,
      win_rate: 44.4,
      avg_deal_size: 83333,
    };
    searchResults = [];
    isSearching = false;
    routerQuery = {};
    postedActions = [];
    server.resetHandlers();
    mockApiGet.mockResolvedValue({ data: { insights: [] } });
    mockApiPost.mockResolvedValue({ data: { success: true } });
  });

  it('renders KPI cards with formatted pipeline values', async () => {
    render(<SalesCommandCenter />);

    expect(await screen.findByText('Sales Command Center')).toBeInTheDocument();

    expect(screen.getByText('Total Pipeline')).toBeInTheDocument();
    expect(screen.getByText('$1000.0k')).toBeInTheDocument();
    expect(screen.getByText('Active Deals')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('Win Rate')).toBeInTheDocument();
    expect(screen.getByText('44.4%')).toBeInTheDocument();
    expect(screen.getByText('Avg Deal Size')).toBeInTheDocument();
    expect(screen.getByText('$83.3k')).toBeInTheDocument();
  });

  it('renders deals in the table with formatted values and platform badges', async () => {
    render(<SalesCommandCenter />);

    expect(await screen.findByText('Acme renewal')).toBeInTheDocument();
    expect(screen.getByText('Acme Corp')).toBeInTheDocument();
    expect(screen.getByText('Globex expansion')).toBeInTheDocument();
    expect(screen.getByText('$250,000')).toBeInTheDocument();
    expect(screen.getByText('$75,000')).toBeInTheDocument();
    expect(screen.getByText('salesforce')).toBeInTheDocument();
    expect(screen.getByText('hubspot')).toBeInTheDocument();
    expect(screen.getByText('Open')).toBeInTheDocument();
    expect(screen.getByText('Won')).toBeInTheDocument();
  });

  it('renders insights with severity and executes the action', async () => {
    mockApiGet.mockResolvedValueOnce({
      data: {
        insights: [
          {
            anomaly_id: 'a1',
            severity: 'critical',
            title: 'Deal stalled 30 days',
            description: 'No activity on Acme renewal',
            recommendation: 'Schedule a follow-up',
            action_type: 'tool',
            action_payload: { tool_name: 'send_email' },
          },
        ],
      },
    });

    render(<SalesCommandCenter />);

    expect(await screen.findByText('Deal stalled 30 days')).toBeInTheDocument();
    expect(screen.getByText('No activity on Acme renewal')).toBeInTheDocument();

    // action_type 'tool' → "Run Auto-Fix" button
    fireEvent.click(screen.getByRole('button', { name: /run auto-fix/i }));

    await waitFor(() => expect(mockApiPost).toHaveBeenCalled());
    expect(mockApiPost).toHaveBeenCalledWith('/api/intelligence/execute', {
      action_type: 'tool',
      action_payload: { tool_name: 'send_email' },
    });
    expect(mockToast.success).toHaveBeenCalledWith('Action executed: Deal stalled 30 days');
  });

  it('navigates to the highlighted project for escalate_deal_blocker workflows', async () => {
    mockApiGet.mockResolvedValueOnce({
      data: {
        insights: [
          {
            anomaly_id: 'a2',
            severity: 'warning',
            title: 'Deal blocker',
            description: 'Task 7 pending',
            recommendation: 'Unblock',
            action_type: 'workflow',
            action_payload: { workflow_id: 'escalate_deal_blocker', inputs: { task_id: 't-7' } },
          },
        ],
      },
    });

    render(<SalesCommandCenter />);

    const btn = await screen.findByRole('button', { name: /resolve via workflow/i });
    fireEvent.click(btn);

    expect(mockToast.info).toHaveBeenCalledWith(
      'Navigating to blocking task in Project Command Center...'
    );
    expect(mockPush).toHaveBeenCalledWith('/projects?highlight=t-7');
    expect(mockApiPost).not.toHaveBeenCalled();
  });

  it('shows the empty state when there are no insights', async () => {
    render(<SalesCommandCenter />);

    expect(await screen.findByText('No critical anomalies detected')).toBeInTheDocument();
  });

  it('shows memory search results and the no-results state', async () => {
    searchResults = [
      {
        id: 'r1',
        app_type: 'salesforce',
        subject: 'Acme call notes',
        sender: 'sarah',
        content: 'Budget approved',
        timestamp: '2026-08-01T10:00:00.000Z',
      },
    ];
    render(<SalesCommandCenter />);
    await screen.findByText('Sales Command Center');

    fireEvent.change(screen.getByPlaceholderText('Search deals...'), {
      target: { value: 'acme' },
    });

    expect(searchSpy).toHaveBeenCalledWith('acme');
    expect(await screen.findByText('Acme call notes')).toBeInTheDocument();
    expect(screen.getByText('Budget approved')).toBeInTheDocument();

    // clear the query → search results disappear
    fireEvent.click(screen.getByText('Clear Search'));
    await waitFor(() => {
      expect(screen.queryByText('Acme call notes')).not.toBeInTheDocument();
    });
  });

  it('shows no-results empty state when memory search returns nothing', async () => {
    render(<SalesCommandCenter />);
    await screen.findByText('Sales Command Center');

    fireEvent.change(screen.getByPlaceholderText('Search deals...'), {
      target: { value: 'nope' },
    });

    expect(await screen.findByText(/No historical records found/i)).toBeInTheDocument();
  });

  it('refreshes sales data and toasts on a WebSocket status_update', async () => {
    render(<SalesCommandCenter />);
    await screen.findByText('Sales Command Center');

    act(() => {
      _setLastMessage({ type: 'status_update' });
    });

    expect(refreshSpy).toHaveBeenCalled();
    expect(mockToast.info).toHaveBeenCalledWith('Sync complete: Refreshing sales data...');
  });

  it('toasts an error when executing an insight action fails', async () => {
    mockApiGet.mockResolvedValueOnce({
      data: {
        insights: [
          {
            anomaly_id: 'a3',
            severity: 'info',
            title: 'Low activity',
            description: 'd',
            recommendation: 'r',
            action_type: 'tool',
            action_payload: { tool_name: 'x' },
          },
        ],
      },
    });
    mockApiPost.mockRejectedValueOnce(new Error('boom'));

    render(<SalesCommandCenter />);

    const btn = await screen.findByRole('button', { name: /run auto-fix/i });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(mockToast.error).toHaveBeenCalledWith('Failed to execute resolution.');
    });
  });

  it('renders with zero deals and zero stats without crashing', async () => {
    liveDeals = [];
    liveStats = { total_pipeline_value: 0, active_deal_count: 0, win_rate: 0, avg_deal_size: 0 };

    render(<SalesCommandCenter />);

    expect(await screen.findByText('Sales Command Center')).toBeInTheDocument();
    expect(screen.getAllByText('$0.0k')).toHaveLength(2);
    expect(screen.getByText('0.0%')).toBeInTheDocument();
    expect(screen.getByText('No critical anomalies detected')).toBeInTheDocument();
  });
});
