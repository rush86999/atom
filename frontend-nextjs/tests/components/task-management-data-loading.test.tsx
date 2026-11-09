import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import TaskManagementWrapper from '@/components/TaskManagement';

const mockFetch = jest.fn();
const mockToast = jest.fn();
jest.mock('@/lib/auth-headers', () => ({ authFetch: (...args: unknown[]) => mockFetch(...args) }));
jest.mock('@/components/ui/use-toast', () => ({ useToast: () => ({ toast: mockToast }) }));
jest.mock('@/components/shared/TaskManagement', () => ({
  __esModule: true,
  default: (props: { initialTasks: unknown[] }) => <div data-testid="visible-task-total">{props.initialTasks.length}</div>,
}));
const rows = Array.from({ length: 150 }, (_, index) => ({
  id: `task-${index}`, title: `Task ${index}`, status: 'todo', priority: 'medium',
  dueDate: '2026-11-09T00:00:00Z', createdAt: '2026-11-09T00:00:00Z', updatedAt: '2026-11-09T00:00:00Z',
}));
const response = (body: unknown, ok = true) => ({ ok, status: ok ? 200 : 503, json: async () => body });

describe('ordinary Tasks page collection boundary', () => {
  beforeEach(() => { mockFetch.mockReset(); mockToast.mockReset(); });
  test('loads every authorized task beyond the default first page', async () => {
    mockFetch.mockImplementation(async (input: string) => {
      const url = new URL(input, 'http://controlled.invalid');
      if (url.pathname === '/api/v1/projects') return response({ projects: [] });
      const limit = Number(url.searchParams.get('limit') || 50);
      const offset = Number(url.searchParams.get('offset') || 0);
      return response({ tasks: rows.slice(offset, offset + limit) });
    });
    render(<TaskManagementWrapper />);
    await waitFor(() => expect(screen.getByTestId('visible-task-total')).toHaveTextContent('150'));
  });
  test('backend failure is an actionable error, not an apparently empty collection', async () => {
    mockFetch.mockImplementation(async (input: string) => input.includes('/projects') ? response({ projects: [] }) : response({ error: 'unavailable' }, false));
    render(<TaskManagementWrapper />);
    await waitFor(() => expect(screen.getByRole('alert')).toBeVisible());
    expect(screen.queryByTestId('visible-task-total')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /try again/i })).toBeEnabled();
  });
  test('a legitimately empty successful collection still renders normally', async () => {
    mockFetch.mockImplementation(async (input: string) => response(input.includes('/projects') ? { projects: [] } : { tasks: [] }));
    render(<TaskManagementWrapper />);
    await waitFor(() => expect(screen.getByTestId('visible-task-total')).toHaveTextContent('0'));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
  test('a failed later page never publishes the first page as complete', async () => {
    mockFetch.mockImplementation(async (input: string) => {
      if (input.includes('/projects')) return response({ projects: [] });
      return input.includes('offset=0') ? response({ tasks: rows.slice(0, 100) }) : response({}, false);
    });
    render(<TaskManagementWrapper />);
    await waitFor(() => expect(screen.getByRole('alert')).toBeVisible());
    expect(screen.queryByTestId('visible-task-total')).not.toBeInTheDocument();
  });
  test('a server repeating the same page is refused rather than looping or duplicating tasks', async () => {
    mockFetch.mockImplementation(async (input: string) => response(input.includes('/projects') ? { projects: [] } : { tasks: rows.slice(0, 100) }));
    render(<TaskManagementWrapper />);
    await waitFor(() => expect(screen.getByRole('alert')).toBeVisible());
    expect(screen.queryByTestId('visible-task-total')).not.toBeInTheDocument();
    expect(mockFetch).toHaveBeenCalledTimes(3);
  });
  test('Try again recovers through a fresh successful collection read', async () => {
    mockFetch.mockImplementation(async () => response({}, false));
    render(<TaskManagementWrapper />);
    await waitFor(() => expect(screen.getByRole('alert')).toBeVisible());
    mockFetch.mockImplementation(async (input: string) => response(input.includes('/projects') ? { projects: [] } : { tasks: [] }));
    fireEvent.click(screen.getByRole('button', { name: /try again/i }));
    await waitFor(() => expect(screen.getByTestId('visible-task-total')).toHaveTextContent('0'));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

});
