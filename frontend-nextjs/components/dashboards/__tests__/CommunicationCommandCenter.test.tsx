/**
 * CommunicationCommandCenter Component Tests
 *
 * Tests verify the real CommunicationCommandCenter dashboard
 * (components/dashboards/CommunicationCommandCenter.tsx):
 * - loads analytics + configured apps on mount (MSW) and renders the KPI
 *   cards with real values (unread, response rate, avg response, channels)
 * - platform status list renders mapped apps with connected/disconnected
 *   status derived from memory_ingestion_enabled
 * - WebSocket status_update merges new stats into the KPI cards and toasts
 * - WebSocket platform_status_change flips a platform's status
 * - memory search: typing 3+ chars triggers searchMessages and shows results;
 *   clearing shows the empty state; <3 chars never searches
 * - New Message button opens the compose flow (CommunicationHub is mocked;
 *   the isComposeOpen prop is what's asserted)
 * - renders with zero data (empty analytics/apps) without crashing
 *
 * APIs: GET /api/atom/communication/memory/analytics,
 *       GET /api/atom/communication/memory/apps
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

const searchSpy = jest.fn();
let searchResults: any[] = [];
let isSearching = false;

jest.mock('@/hooks/useLiveCommunication', () => ({
  useLiveCommunication: () => ({ messages: [], isLoading: false, activeProviders: {} }),
}));

jest.mock('@/hooks/useCommunicationSearch', () => ({
  useCommunicationSearch: () => ({
    results: searchResults,
    isSearching,
    searchMessages: searchSpy,
  }),
}));

jest.mock('@/hooks/useLiveContacts', () => ({
  useLiveContacts: () => ({
    contacts: [
      { id: 'c1', name: 'Ada Lovelace', provider: 'slack', status: 'online', avatar: '/a.png' },
      { id: 'c2', name: 'Grace Hopper', provider: 'gmail', status: 'offline', avatar: '/b.png' },
    ],
    loading: false,
  }),
}));

jest.mock('@/components/shared/CommentSection', () => ({
  CommentSection: () => null,
}));

jest.mock('@/components/shared/PipelineSettingsPanel', () => ({
  PipelineSettingsPanel: () => null,
}));

let composeOpen: boolean | null = null;
jest.mock('@/components/shared/CommunicationHub', () => ({
  __esModule: true,
  default: ({ isComposeOpen }: { isComposeOpen: boolean }) => {
    composeOpen = isComposeOpen;
    return <div data-testid="communication-hub" />;
  },
}));

const mockToast = { success: jest.fn(), error: jest.fn(), info: jest.fn() };
jest.mock('sonner', () => ({
  toast: mockToast,
}));

import { CommunicationCommandCenter } from '../CommunicationCommandCenter';

const analyticsPayload = {
  success: true,
  analytics: {
    status_distribution: { unread: 7 },
    summary: { unique_apps: 3 },
    performance: { response_rate: 94.5, avg_response_time: '3m' },
  },
};

const appsPayload = {
  apps: [
    { id: 'slack-main', name: 'Slack Workspace', memory_ingestion_enabled: true },
    { id: 'gmail-primary', name: 'Gmail', memory_ingestion_enabled: false },
    { id: 'teams-corp', name: 'Teams', memory_ingestion_enabled: true },
  ],
};

describe('CommunicationCommandCenter', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    searchResults = [];
    isSearching = false;
    composeOpen = null;
    server.resetHandlers();
    server.use(
      rest.get('/api/atom/communication/memory/analytics', (req, res, ctx) =>
        res(ctx.status(200), ctx.json(analyticsPayload))
      ),
      rest.get('/api/atom/communication/memory/apps', (req, res, ctx) =>
        res(ctx.status(200), ctx.json(appsPayload))
      ),
      rest.get('/api/atom/communication/memory/search', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ success: true, results: [] }))
      )
    );
  });

  it('renders the header and KPI cards with values from the analytics API', async () => {
    render(<CommunicationCommandCenter />);

    expect(await screen.findByText('Communication Command Center')).toBeInTheDocument();

    // KPI cards: unread messages, response rate, avg response, active channels
    expect(screen.getByText('Unread Messages')).toBeInTheDocument();
    expect(await screen.findByText('7')).toBeInTheDocument();
    expect(screen.getByText('Response Rate')).toBeInTheDocument();
    expect(screen.getByText('94.5%')).toBeInTheDocument();
    expect(screen.getByText('Avg Response')).toBeInTheDocument();
    expect(screen.getByText('3m')).toBeInTheDocument();
    expect(screen.getByText('Active Channels')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('renders the platform status list from the apps API with mapped status', async () => {
    render(<CommunicationCommandCenter />);

    expect(await screen.findByText('Slack Workspace')).toBeInTheDocument();
    expect(screen.getByText('Gmail')).toBeInTheDocument();
    expect(screen.getByText('Teams')).toBeInTheDocument();

    // memory_ingestion_enabled=true → connected; false → disconnected
    expect(screen.getAllByText('connected')).toHaveLength(2);
    expect(screen.getAllByText('disconnected')).toHaveLength(1);
  });

  it('renders recent contacts with name, provider and online dot', async () => {
    render(<CommunicationCommandCenter />);

    expect(await screen.findByText('Ada Lovelace')).toBeInTheDocument();
    expect(screen.getByText('Grace Hopper')).toBeInTheDocument();
    const imgs = screen.getAllByRole('img');
    expect(imgs.some((i) => i.getAttribute('alt') === 'Ada Lovelace')).toBe(true);
  });

  it('merges WebSocket status_update stats into the KPI cards and toasts', async () => {
    render(<CommunicationCommandCenter />);
    await screen.findByText('Communication Command Center');

    act(() => {
      _setLastMessage({ type: 'status_update', data: { totalUnread: 42, responseRate: 91 } });
    });

    expect(await screen.findByText('42')).toBeInTheDocument();
    expect(screen.getByText('91%')).toBeInTheDocument();
    expect(mockToast.info).toHaveBeenCalledWith('Communication stats updated');
  });

  it('flips a platform status on platform_status_change', async () => {
    render(<CommunicationCommandCenter />);
    await screen.findByText('Slack Workspace');

    expect(screen.getAllByText('connected')).toHaveLength(2);

    act(() => {
      _setLastMessage({
        type: 'platform_status_change',
        data: { platform: 'slack', status: 'degraded' },
      });
    });

    // "slack-main" name contains "slack" → matched via platform.name.toLowerCase()
    expect(await screen.findByText('degraded')).toBeInTheDocument();
  });

  it('ignores non-status WebSocket message types without crashing', async () => {
    render(<CommunicationCommandCenter />);
    await screen.findByText('Communication Command Center');

    act(() => {
      _setLastMessage({ type: 'some_other_event', data: { totalUnread: 99 } });
    });

    // stats unchanged (still from analytics fetch: 7 unread)
    expect(screen.getByText('7')).toBeInTheDocument();
  });

  it('shows memory search results after typing 3+ characters', async () => {
    searchResults = [
      {
        id: 'r1',
        app_type: 'slack',
        sender: 'Alice',
        content: 'Release notes for v2.1',
        timestamp: '2026-08-01T10:00:00.000Z',
      },
    ];
    render(<CommunicationCommandCenter />);
    await screen.findByText('Communication Command Center');

    fireEvent.change(screen.getByPlaceholderText('Search memory...'), {
      target: { value: 'release' },
    });

    expect(searchSpy).toHaveBeenCalledWith('release');
    expect(await screen.findByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Release notes for v2.1')).toBeInTheDocument();
  });

  it('does not trigger memory search for short queries and shows no results view', async () => {
    render(<CommunicationCommandCenter />);
    await screen.findByText('Communication Command Center');

    fireEvent.change(screen.getByPlaceholderText('Search memory...'), {
      target: { value: 're' },
    });

    await waitFor(() => expect(searchSpy).not.toHaveBeenCalled());
    expect(screen.queryByText(/Search Results for/i)).not.toBeInTheDocument();
  });

  it('shows the no-results empty state when a search returns nothing', async () => {
    render(<CommunicationCommandCenter />);
    await screen.findByText('Communication Command Center');

    fireEvent.change(screen.getByPlaceholderText('Search memory...'), {
      target: { value: 'zzz' },
    });

    expect(await screen.findByText('No results found in memory.')).toBeInTheDocument();
  });

  it('clears the search query with the X button', async () => {
    render(<CommunicationCommandCenter />);
    await screen.findByText('Communication Command Center');

    const input = screen.getByPlaceholderText('Search memory...');
    fireEvent.change(input, { target: { value: 'zzz' } });
    expect(await screen.findByText('No results found in memory.')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '' }).closest('button')!);
    await waitFor(() => {
      expect(screen.queryByText('No results found in memory.')).not.toBeInTheDocument();
    });
  });

  it('opens compose mode when New Message is clicked (CommunicationHub prop)', async () => {
    render(<CommunicationCommandCenter />);
    await screen.findByText('Communication Command Center');

    expect(composeOpen).toBe(false);
    fireEvent.click(screen.getByText('New Message'));
    expect(composeOpen).toBe(true);
  });

  it('renders without crashing when the APIs return no data', async () => {
    server.use(
      rest.get('/api/atom/communication/memory/analytics', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ success: false }))
      ),
      rest.get('/api/atom/communication/memory/apps', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ apps: [] }))
      )
    );

    render(<CommunicationCommandCenter />);

    expect(await screen.findByText('Communication Command Center')).toBeInTheDocument();
    // KPI cards fall back to zero defaults
    expect(screen.getAllByText('0').length).toBeGreaterThanOrEqual(2);
    // platform list empty
    expect(screen.queryByText('Slack Workspace')).not.toBeInTheDocument();
  });
});
