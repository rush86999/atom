/**
 * KnowledgeCommandCenter Component Tests
 *
 * Tests verify the real KnowledgeCommandCenter dashboard
 * (components/dashboards/KnowledgeCommandCenter.tsx):
 * - renders knowledge items from useLiveKnowledge in the table with type
 *   icon, platform badge, and status/value column
 * - computed stats (Global Objects, Active Tasks, Critical Alerts) reflect
 *   item counts and insight severity
 * - type filter buttons filter the table rows
 * - search input filters rows client-side; deep search (3+ chars) routes to
 *   useMemorySearch and renders result cards
 * - WebSocket status_update calls refresh(); urgent_alert toasts an error
 * - tab navigation switches to Entity Types / Graph View
 * - smart insights panel renders severity badges + recommendations
 * - empty data renders "No intelligence found" without crashing
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

jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: { user: { name: 'Rushi' } }, status: 'authenticated' }),
}));

const refreshSpy = jest.fn();
let items: any[] = [];
let insights: any[] = [];

jest.mock('@/hooks/useLiveKnowledge', () => ({
  useLiveKnowledge: () => ({
    items,
    insights,
    loading: false,
    insightsLoading: false,
    refresh: refreshSpy,
  }),
}));

const searchSpy = jest.fn();
const clearSearchSpy = jest.fn();
let searchResults: any[] = [];
let isSearching = false;

jest.mock('@/hooks/useMemorySearch', () => ({
  useMemorySearch: () => ({
    results: searchResults,
    isSearching,
    searchMemory: searchSpy,
    clearSearch: clearSearchSpy,
  }),
}));

jest.mock('@/components/shared/CommentSection', () => ({
  CommentSection: () => null,
}));

jest.mock('@/components/shared/PipelineSettingsPanel', () => ({
  PipelineSettingsPanel: () => null,
}));

jest.mock('@/components/entity/EntityTypeList', () => ({
  EntityTypeList: () => <div data-testid="entity-type-list" />,
}));

jest.mock('@/components/entity/EntityTypeGraphView', () => ({
  EntityTypeGraphView: () => <div data-testid="entity-type-graph" />,
}));

jest.mock('@/src/components/Graph/GraphVisualization', () => ({
  __esModule: true,
  default: () => <div data-testid="graph-visualization" />,
}));

const mockToast = { success: jest.fn(), error: jest.fn(), info: jest.fn() };
jest.mock('sonner', () => ({
  toast: mockToast,
}));

const mockUiToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockUiToast,
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

import { KnowledgeCommandCenter } from '../KnowledgeCommandCenter';

const makeItems = () => [
  {
    id: 'k1',
    name: 'Q3 Sales Report',
    platform: 'gdrive',
    type: 'file',
    modified_at: '2026-07-30',
    status: 'Synced',
  },
  {
    id: 'k2',
    name: 'Fix login bug',
    platform: 'jira',
    type: 'task',
    status: 'In Progress',
    priority: 'High',
  },
  {
    id: 'k3',
    name: 'Acme renewal',
    platform: 'salesforce',
    type: 'deal',
    value: 125000,
    status: 'Open',
  },
];

const makeInsights = () => [
  {
    anomaly_id: 'i1',
    severity: 'critical',
    title: 'Churn risk rising',
    description: '3 accounts idle for 60 days',
    recommendation: 'Reach out this week',
    platforms: ['salesforce'],
  },
];

describe('KnowledgeCommandCenter', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    items = makeItems();
    insights = makeInsights();
    searchResults = [];
    isSearching = false;
    server.resetHandlers();
  });

  it('renders the header, stat cards and knowledge table rows', async () => {
    render(<KnowledgeCommandCenter />);

    expect(await screen.findByText('Global Intelligence Hub')).toBeInTheDocument();

    // Stats: 3 items total, 1 task, critical = 1 (High priority) + 1 critical insight
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();

    // Table rows
    expect(screen.getByText('Q3 Sales Report')).toBeInTheDocument();
    expect(screen.getByText('Fix login bug')).toBeInTheDocument();
    expect(screen.getByText('Acme renewal')).toBeInTheDocument();

    // Deal value rendered with $ and toLocaleString
    expect(screen.getByText('$125,000')).toBeInTheDocument();
  });

  it('renders platform badges for known platforms', async () => {
    render(<KnowledgeCommandCenter />);

    expect(await screen.findByText('gdrive')).toBeInTheDocument();
    expect(screen.getByText('jira')).toBeInTheDocument();
    // salesforce renders as the table badge AND in the insight platform chips
    expect(screen.getAllByText('salesforce').length).toBeGreaterThanOrEqual(1);
  });

  it('filters the table by type using the filter buttons', async () => {
    render(<KnowledgeCommandCenter />);
    await screen.findByText('Fix login bug');

    fireEvent.click(screen.getByText('tasks'));
    expect(screen.queryByText('Q3 Sales Report')).not.toBeInTheDocument();
    expect(screen.getByText('Fix login bug')).toBeInTheDocument();

    fireEvent.click(screen.getByText('files'));
    expect(screen.getByText('Q3 Sales Report')).toBeInTheDocument();
    expect(screen.queryByText('Fix login bug')).not.toBeInTheDocument();
  });

  it('filters the table client-side by the search input', async () => {
    render(<KnowledgeCommandCenter />);
    await screen.findByText('Fix login bug');

    fireEvent.change(screen.getByPlaceholderText('Deep search across all systems...'), {
      target: { value: 'Ac' },
    });

    expect(screen.getByText('Acme renewal')).toBeInTheDocument();
    expect(screen.queryByText('Fix login bug')).not.toBeInTheDocument();
    expect(screen.queryByText('Q3 Sales Report')).not.toBeInTheDocument();
  });

  it('routes deep search (3+ chars) to memory search and renders result cards', async () => {
    searchResults = [
      {
        id: 'r1',
        app_type: 'slack',
        subject: 'Release notes',
        sender: 'alice',
        content: 'v2.1 shipped',
        timestamp: '2026-08-01T10:00:00.000Z',
      },
    ];
    render(<KnowledgeCommandCenter />);
    await screen.findByText('Global Intelligence Hub');

    fireEvent.change(screen.getByPlaceholderText('Deep search across all systems...'), {
      target: { value: 'release' },
    });

    expect(searchSpy).toHaveBeenCalledWith('release');
    expect(await screen.findByText('Release notes')).toBeInTheDocument();
    expect(screen.getByText('v2.1 shipped')).toBeInTheDocument();
  });

  it('shows the no-results state when memory search returns nothing', async () => {
    render(<KnowledgeCommandCenter />);
    await screen.findByText('Global Intelligence Hub');

    fireEvent.change(screen.getByPlaceholderText('Deep search across all systems...'), {
      target: { value: 'nothing' },
    });

    expect(
      await screen.findByText(/No historical intelligence found/i)
    ).toBeInTheDocument();
  });

  it('refreshes knowledge data on a status_update and toasts an error on urgent_alert', async () => {
    render(<KnowledgeCommandCenter />);
    await screen.findByText('Global Intelligence Hub');

    act(() => {
      _setLastMessage({ type: 'urgent_alert', data: { message: 'DB partition failed' } });
    });

    expect(mockToast.error).toHaveBeenCalledWith('DB partition failed', { duration: 5000 });
    expect(refreshSpy).toHaveBeenCalled();

    act(() => {
      _setLastMessage({ type: 'status_update' });
    });

    expect(mockToast.info).toHaveBeenCalledWith('Intelligence sync complete. Refreshing data...');
  });

  it('renders the Smart Insights panel with severity badge and recommendation', async () => {
    render(<KnowledgeCommandCenter />);

    expect(await screen.findByText('Smart Intelligence Insights')).toBeInTheDocument();
    expect(screen.getByText('Churn risk rising')).toBeInTheDocument();
    expect(screen.getByText(/Recommendation: Reach out this week/)).toBeInTheDocument();
    expect(screen.getByText('critical')).toBeInTheDocument();
    expect(screen.getAllByText('salesforce').length).toBeGreaterThanOrEqual(1);
  });

  it('switches to the Entity Types tab and shows the entity type list', async () => {
    render(<KnowledgeCommandCenter />);
    await screen.findByText('Global Intelligence Hub');

    fireEvent.click(screen.getByText('Entity Types'));

    expect(await screen.findByTestId('entity-type-list')).toBeInTheDocument();
  });

  it('switches to the Graph View tab', async () => {
    render(<KnowledgeCommandCenter />);
    await screen.findByText('Global Intelligence Hub');

    fireEvent.click(screen.getByText('Graph View'));

    expect(await screen.findByTestId('graph-visualization')).toBeInTheDocument();
  });

  it('toasts when Ask Atom is clicked', async () => {
    render(<KnowledgeCommandCenter />);
    await screen.findByText('Global Intelligence Hub');

    fireEvent.click(screen.getByText('Ask Atom'));
    expect(mockToast.success).toHaveBeenCalledWith(
      'Redirecting to Atom Agent for knowledge query...'
    );
  });

  it('renders the empty state when there are no items and no insights', async () => {
    items = [];
    insights = [];

    render(<KnowledgeCommandCenter />);

    expect(
      await screen.findByText('No intelligence found matching your criteria.')
    ).toBeInTheDocument();
    expect(screen.queryByText('Smart Intelligence Insights')).not.toBeInTheDocument();
  });

  it('resets filters via the Reset button', async () => {
    render(<KnowledgeCommandCenter />);
    await screen.findByText('Fix login bug');

    fireEvent.change(screen.getByPlaceholderText('Deep search across all systems...'), {
      target: { value: 'Ac' },
    });
    expect(screen.queryByText('Fix login bug')).not.toBeInTheDocument();

    fireEvent.click(screen.getByText('Reset'));

    expect(screen.getByText('Fix login bug')).toBeInTheDocument();
    expect(screen.getByText('Q3 Sales Report')).toBeInTheDocument();
  });
});
