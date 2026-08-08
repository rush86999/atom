/**
 * SupportCommandCenter Component Tests
 *
 * Tests verify the real SupportCommandCenter dashboard
 * (components/dashboards/SupportCommandCenter.tsx):
 * - renders SLA stat cards (SLA Warning, 18m Resp, 4.9 CSAT)
 * - renders the ticket queue with id, subject, customer, priority badge and
 *   platform badge
 * - renders the staff thread using the session user's name
 * - memory search shows result cards / no-results empty state
 * - WebSocket status_update triggers refresh() + toast
 * - empty ticket list renders without crashing
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
  useSession: () => ({ data: { user: { name: 'Rushi Patel' } }, status: 'authenticated' }),
}));

const refreshSpy = jest.fn();
let tickets: any[] = [];

jest.mock('@/hooks/useLiveSupport', () => ({
  useLiveSupport: () => ({
    tickets,
    isLoading: false,
    error: null,
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

import { SupportCommandCenter } from '../SupportCommandCenter';

describe('SupportCommandCenter', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    tickets = [
      { id: 'T-1001', subject: 'Cannot login after update', customer: 'Jane Doe', priority: 'High', platform: 'zendesk', status: 'Open' },
      { id: 'T-1002', subject: 'Billing question', customer: 'John Smith', priority: 'Low', platform: 'freshdesk', status: 'Pending' },
    ];
    searchResults = [];
    isSearching = false;
    server.resetHandlers();
  });

  it('renders the header and SLA stat cards', async () => {
    render(<SupportCommandCenter />);

    expect(await screen.findByText('Support Command Center')).toBeInTheDocument();
    expect(screen.getByText('SLA Warning')).toBeInTheDocument();
    expect(screen.getByText('2 tickets near breach')).toBeInTheDocument();
    expect(screen.getByText('18m Resp')).toBeInTheDocument();
    expect(screen.getByText('4.9 CSAT')).toBeInTheDocument();
  });

  it('renders the ticket queue with priority badges and customer names', async () => {
    render(<SupportCommandCenter />);

    expect(await screen.findByText('Cannot login after update')).toBeInTheDocument();
    expect(screen.getByText('T-1001')).toBeInTheDocument();
    expect(screen.getByText('Jane Doe')).toBeInTheDocument();
    expect(screen.getByText('High')).toBeInTheDocument();
    expect(screen.getByText('Billing question')).toBeInTheDocument();
    expect(screen.getByText('John Smith')).toBeInTheDocument();
    expect(screen.getByText('Low')).toBeInTheDocument();
    expect(screen.getByText('zendesk')).toBeInTheDocument();
    expect(screen.getByText('freshdesk')).toBeInTheDocument();
  });

  it('renders the staff thread with the signed-in user name', async () => {
    render(<SupportCommandCenter />);

    expect(await screen.findByText('Cloud Sync Failed for Org #55')).toBeInTheDocument();
    expect(screen.getByText(/Acme Corp • Assigned to Rushi Patel/)).toBeInTheDocument();
    expect(screen.getByText('John Doe')).toBeInTheDocument();
    // user avatar initials from session name
    expect(screen.getByText('RP')).toBeInTheDocument();
  });

  it('shows memory search results and the no-results state', async () => {
    searchResults = [
      {
        id: 'r1',
        app_type: 'zendesk',
        subject: 'Login timeout',
        sender: 'support-bot',
        content: 'Resolved with token refresh',
        timestamp: '2026-08-01T10:00:00.000Z',
      },
    ];
    render(<SupportCommandCenter />);
    await screen.findByText('Support Command Center');

    fireEvent.change(screen.getByPlaceholderText('Search tickets...'), {
      target: { value: 'login' },
    });

    expect(searchSpy).toHaveBeenCalledWith('login');
    expect(await screen.findByText('Login timeout')).toBeInTheDocument();
    expect(screen.getByText('Resolved with token refresh')).toBeInTheDocument();
  });

  it('shows the no-results state when memory search returns nothing', async () => {
    render(<SupportCommandCenter />);
    await screen.findByText('Support Command Center');

    fireEvent.change(screen.getByPlaceholderText('Search tickets...'), {
      target: { value: 'zzz' },
    });

    expect(await screen.findByText(/No historical tickets found/i)).toBeInTheDocument();
  });

  it('refreshes tickets and toasts on a WebSocket status_update', async () => {
    render(<SupportCommandCenter />);
    await screen.findByText('Support Command Center');

    act(() => {
      _setLastMessage({ type: 'status_update' });
    });

    expect(refreshSpy).toHaveBeenCalled();
    expect(mockToast.info).toHaveBeenCalledWith('Support sync complete. Refreshing tickets...');
  });

  it('renders with an empty ticket queue without crashing', async () => {
    tickets = [];

    render(<SupportCommandCenter />);

    expect(await screen.findByText('Support Command Center')).toBeInTheDocument();
    expect(screen.queryByText('T-1001')).not.toBeInTheDocument();
  });
});
