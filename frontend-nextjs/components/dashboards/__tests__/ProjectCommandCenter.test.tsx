/**
 * ProjectCommandCenter Component Tests
 *
 * Tests verify the real ProjectCommandCenter dashboard
 * (components/dashboards/ProjectCommandCenter.tsx):
 * - renders KPI cards (Total Tasks, Active Platforms, Critical Overdue) from
 *   useLiveProjects data
 * - renders tasks in the table with platform badge, status and detail link
 * - Quick Create modal: opens, posts /api/intelligence/execute with the
 *   create_task payload, toasts success, closes, and refreshes
 * - creating with an empty title is impossible (button disabled)
 * - search input filters table rows client-side
 * - memory search (3+ chars) shows result cards / no-results empty state
 * - WebSocket status_update triggers refresh() + toast
 * - highlight task from router.query renders the highlighted row
 */
import React from 'react';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// --- apiClient mock: the component posts create_task via the authenticated
// axios client; MSW does not intercept jsdom's fetch adapter, so assert on the
// mocked client (same pattern as mini-app-harness / SlashCommandBar). ---
import { apiClient } from '@/lib/api-client';

jest.mock('@/lib/api-client', () => ({
  apiClient: { get: jest.fn(), post: jest.fn(), put: jest.fn(), delete: jest.fn() },
}));
const apiClientMock = apiClient as unknown as {
  post: jest.Mock;
  get: jest.Mock;
  put: jest.Mock;
  delete: jest.Mock;
};

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
let liveTasks: any[] = [];
let liveStats: any = {};
let isLoading = false;

jest.mock('@/hooks/useLiveProjects', () => ({
  useLiveProjects: () => ({
    tasks: liveTasks,
    stats: liveStats,
    isLoading,
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

let routerQuery: Record<string, string> = {};
jest.mock('next/router', () => ({
  useRouter: () => ({
    route: '/projects',
    pathname: '/projects',
    query: routerQuery,
    asPath: '/projects',
    push: jest.fn(),
    replace: jest.fn(),
    reload: jest.fn(),
    back: jest.fn(),
    prefetch: jest.fn(),
    beforePopState: jest.fn(),
    events: { on: jest.fn(), off: jest.fn(), emit: jest.fn() },
  }),
}));

import { ProjectCommandCenter } from '../ProjectCommandCenter';

const makeTasks = () => [
  { id: 't-101', name: 'Design landing page', platform: 'jira', status: 'To Do', url: 'https://jira/101' },
  { id: 't-102', name: 'Implement auth flow', platform: 'asana', status: 'In Progress', url: 'https://asana/102' },
  { id: 't-103', name: 'Ship v1.0', platform: 'trello', status: 'Done', url: 'https://trello/103' },
];

describe('ProjectCommandCenter', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    liveTasks = makeTasks();
    liveStats = {
      total_active_tasks: 3,
      completed_today: 1,
      overdue_count: 2,
      tasks_by_platform: { jira: 1, asana: 1, trello: 1 },
    };
    isLoading = false;
    searchResults = [];
    isSearching = false;
    routerQuery = {};
    apiClientMock.post.mockResolvedValue({ data: { success: true } });
  });

  it('renders KPI cards with task counts and platform names', async () => {
    render(<ProjectCommandCenter />);

    expect(await screen.findByText('Project Command Center')).toBeInTheDocument();
    expect(screen.getByText('Total Tasks')).toBeInTheDocument();
    expect(screen.getByText('Active Platforms')).toBeInTheDocument();
    // Object.keys(tasks_by_platform).length = 3 (Total Tasks + Active Platforms)
    expect(screen.getAllByText('3')).toHaveLength(2);
    expect(screen.getByText('Critical Overdue')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('jira, asana, trello')).toBeInTheDocument();
  });

  it('renders the task table with platform badges, status and detail link', async () => {
    render(<ProjectCommandCenter />);

    expect(await screen.findByText('Design landing page')).toBeInTheDocument();
    expect(screen.getByText('Implement auth flow')).toBeInTheDocument();
    expect(screen.getByText('Ship v1.0')).toBeInTheDocument();

    // Task IDs rendered in the ID column
    expect(screen.getByText('t-101')).toBeInTheDocument();
    expect(screen.getByText('t-102')).toBeInTheDocument();

    // Done tasks render a green check; others a plain circle — both statuses present
    expect(screen.getByText('To Do')).toBeInTheDocument();
    expect(screen.getByText('In Progress')).toBeInTheDocument();
    expect(screen.getByText('Done')).toBeInTheDocument();

    const links = screen.getAllByRole('link');
    expect(links.some((l) => l.getAttribute('href') === 'https://jira/101')).toBe(true);
  });

  it('creates a task via Quick Create modal posting the create_task tool payload', async () => {
    render(<ProjectCommandCenter />);
    await screen.findByText('Project Command Center');

    fireEvent.click(screen.getByRole('button', { name: /quick create/i }));
    expect(screen.getByText('Quick Create Task')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('Enter task summary...'), {
      target: { value: 'Write release notes' },
    });

    // platform buttons: default jira selected
    fireEvent.click(screen.getByRole('button', { name: 'asana' }));
    fireEvent.click(screen.getByRole('button', { name: 'Create Task' }));

    await waitFor(() => expect(apiClientMock.post).toHaveBeenCalledTimes(1));
    expect(apiClientMock.post).toHaveBeenCalledWith('/api/intelligence/execute', {
      action_type: 'tool',
      action_payload: {
        tool_name: 'create_task',
        arguments: { title: 'Write release notes', platform: 'asana', status: 'To Do' },
      },
    });

    expect(mockToast.success).toHaveBeenCalledWith('Task created successfully in asana');
    expect(refreshSpy).toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.queryByText('Quick Create Task')).not.toBeInTheDocument();
    });
  });

  it('disables Create Task until a title is provided', async () => {
    render(<ProjectCommandCenter />);
    await screen.findByText('Project Command Center');

    fireEvent.click(screen.getByRole('button', { name: /quick create/i }));
    const createBtn = screen.getByRole('button', { name: 'Create Task' });
    expect(createBtn).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText('Enter task summary...'), {
      target: { value: 'A title' },
    });
    expect(screen.getByRole('button', { name: 'Create Task' })).not.toBeDisabled();
  });

  it('cancels the create modal without posting', async () => {
    render(<ProjectCommandCenter />);
    await screen.findByText('Project Command Center');

    fireEvent.click(screen.getByRole('button', { name: /quick create/i }));
    fireEvent.click(screen.getByText('Cancel'));

    await waitFor(() => {
      expect(screen.queryByText('Quick Create Task')).not.toBeInTheDocument();
    });
    expect(apiClientMock.post).not.toHaveBeenCalled();
  });

  it('toasts an error when task creation fails', async () => {
    apiClientMock.post.mockRejectedValue(new Error('boom'));

    render(<ProjectCommandCenter />);
    await screen.findByText('Project Command Center');

    fireEvent.click(screen.getByRole('button', { name: /quick create/i }));
    fireEvent.change(screen.getByPlaceholderText('Enter task summary...'), {
      target: { value: 'Doomed task' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create Task' }));

    await waitFor(() => {
      expect(mockToast.error).toHaveBeenCalledWith('Failed to create task across systems.');
    });
  });

  it('filters table rows client-side by search input', async () => {
    render(<ProjectCommandCenter />);
    await screen.findByText('Design landing page');

    fireEvent.change(screen.getByPlaceholderText('Search tasks...'), {
      target: { value: 'au' },
    });

    expect(screen.queryByText('Design landing page')).not.toBeInTheDocument();
    expect(screen.getByText('Implement auth flow')).toBeInTheDocument();
  });

  it('shows memory search results for 3+ char queries', async () => {
    searchResults = [
      {
        id: 'r1',
        app_type: 'jira',
        subject: 'Sprint 42',
        sender: 'bot',
        content: 'Completed yesterday',
        timestamp: '2026-08-01T10:00:00.000Z',
      },
    ];
    render(<ProjectCommandCenter />);
    await screen.findByText('Project Command Center');

    fireEvent.change(screen.getByPlaceholderText('Search tasks...'), {
      target: { value: 'sprint' },
    });

    expect(searchSpy).toHaveBeenCalledWith('sprint');
    expect(await screen.findByText('Sprint 42')).toBeInTheDocument();
    expect(screen.getByText('Completed yesterday')).toBeInTheDocument();
  });

  it('refreshes project data on a WebSocket status_update', async () => {
    render(<ProjectCommandCenter />);
    await screen.findByText('Project Command Center');

    act(() => {
      _setLastMessage({ type: 'status_update' });
    });

    expect(refreshSpy).toHaveBeenCalled();
    expect(mockToast.info).toHaveBeenCalledWith('Sync complete: Refreshing project data...');
  });

  it('renders the highlighted task row when router.query.highlight matches', async () => {
    routerQuery = { highlight: 't-102' };

    render(<ProjectCommandCenter />);

    expect(await screen.findByText('Implement auth flow')).toBeInTheDocument();
    // highlight task row gets bg-primary/10 class
    const row = screen.getByText('Implement auth flow').closest('tr')!;
    expect(row.className).toContain('bg-primary/10');
    expect(mockToast.info).toHaveBeenCalledWith('Highlighting related task: t-102');
  });

  it('renders loading skeleton rows while the live data is loading', async () => {
    isLoading = true;
    liveTasks = [];

    render(<ProjectCommandCenter />);

    expect(await screen.findByText('Project Command Center')).toBeInTheDocument();
    // skeleton rows render animate-pulse cells
    const rows = document.querySelectorAll('tr.animate-pulse');
    expect(rows.length).toBe(3);
  });

  it('renders an empty table without crashing', async () => {
    liveTasks = [];
    liveStats = { total_active_tasks: 0, completed_today: 0, overdue_count: 0, tasks_by_platform: {} };

    render(<ProjectCommandCenter />);

    expect(await screen.findByText('Project Command Center')).toBeInTheDocument();
    expect(screen.getAllByText('0').length).toBeGreaterThanOrEqual(2);
  });
});
