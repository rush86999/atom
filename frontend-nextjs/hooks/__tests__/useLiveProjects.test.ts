/**
 * useLiveProjects Hook Unit Tests
 *
 * Tests for useLiveProjects hook managing live project board polling.
 * Verifies data fetching, polling behavior, API response parsing,
 * task data structure validation, and provider tracking.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useLiveProjects } from '../useLiveProjects';
import { rest } from 'msw';
import { overrideHandler } from '@/tests/mocks/server';

describe('useLiveProjects Hook', () => {
  const mockTasks = [
    {
      id: 'task-1',
      name: 'Implement authentication',
      platform: 'jira',
      status: 'In Progress',
      priority: 'High',
      assignee: 'John Doe',
      due_date: '2025-01-20',
      project_name: 'Security Module',
      url: 'https://jira.atlassian.com/browse/SEC-1'
    },
    {
      id: 'task-2',
      name: 'Design database schema',
      platform: 'asana',
      status: 'Completed',
      priority: 'Medium',
      assignee: 'Jane Smith',
      due_date: '2025-01-18',
      project_name: 'Backend API',
      url: 'https://asana.com/task/2'
    },
    {
      id: 'task-3',
      name: 'Write unit tests',
      platform: 'trello',
      status: 'To Do',
      priority: 'Low',
      assignee: 'Bob Johnson',
      due_date: '2025-01-25',
      project_name: 'Testing Suite',
      url: 'https://trello.com/c/abc123'
    }
  ];

  const mockStats = {
    total_active_tasks: 15,
    completed_today: 5,
    overdue_count: 2,
    tasks_by_platform: {
      jira: 8,
      asana: 4,
      trello: 3
    }
  };

  const mockProviders = {
    asana: true,
    jira: true,
    trello: true,
    clickup: false,
    zoho: false,
    planner: false
  };

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  describe('1. Data Fetching Tests', () => {
    test('fetches project board on mount', async () => {
      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              tasks: mockTasks,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveProjects());

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.tasks).toEqual(mockTasks);
      });
    });

    test('sets tasks state', async () => {
      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              tasks: mockTasks,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveProjects());

      await waitFor(() => {
        expect(result.current.tasks).toHaveLength(3);
        expect(result.current.tasks[0].name).toBe('Implement authentication');
      });
    });

    test('sets stats state', async () => {
      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              tasks: mockTasks,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveProjects());

      await waitFor(() => {
        expect(result.current.stats).toEqual(mockStats);
        expect(result.current.stats.total_active_tasks).toBe(15);
        expect(result.current.stats.completed_today).toBe(5);
        expect(result.current.stats.overdue_count).toBe(2);
      });
    });

    test('sets activeProviders state', async () => {
      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              tasks: mockTasks,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveProjects());

      await waitFor(() => {
        expect(result.current.activeProviders).toEqual(mockProviders);
        expect(result.current.activeProviders.jira).toBe(true);
        expect(result.current.activeProviders.clickup).toBe(false);
      });
    });

    test('parses LiveProjectsResponse correctly', async () => {
      const mockResponse = {
        ok: true,
        stats: mockStats,
        tasks: mockTasks,
        providers: mockProviders
      };

      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          return res(ctx.json(mockResponse));
        })
      );

      const { result } = renderHook(() => useLiveProjects());

      await waitFor(() => {
        expect(result.current.tasks).toEqual(mockResponse.tasks);
        expect(result.current.stats).toEqual(mockResponse.stats);
        expect(result.current.activeProviders).toEqual(mockResponse.providers);
      });
    });

    test('sets loading to false after fetch', async () => {
      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              tasks: [],
              providers: {}
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveProjects());

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });
  });

  describe('2. Data Structure Tests', () => {
    test('UnifiedTask interface fields', async () => {
      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              tasks: mockTasks,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveProjects());

      await waitFor(() => {
        result.current.tasks.forEach(task => {
          expect(task).toHaveProperty('id');
          expect(task).toHaveProperty('name');
          expect(task).toHaveProperty('platform');
          expect(task).toHaveProperty('status');
          expect(task).toHaveProperty('priority');
          expect(task).toHaveProperty('assignee');
          expect(task).toHaveProperty('due_date');
          expect(task).toHaveProperty('project_name');
          expect(task).toHaveProperty('url');

          expect(typeof task.id).toBe('string');
          expect(typeof task.name).toBe('string');
          expect(typeof task.platform).toBe('string');
          expect(typeof task.status).toBe('string');
        });
      });
    });

    test('platform types: asana, jira, trello, clickup, zoho, planner', async () => {
      const multiPlatformTasks = [
        { ...mockTasks[0], platform: 'asana' },
        { ...mockTasks[1], platform: 'jira' },
        { ...mockTasks[2], platform: 'trello' },
        {
          id: 'task-4',
          name: 'ClickUp task',
          platform: 'clickup',
          status: 'In Progress',
          priority: 'High',
          assignee: 'Alice',
          due_date: '2025-01-21',
          project_name: 'Project D',
          url: 'https://clickup.com/t/4'
        },
        {
          id: 'task-5',
          name: 'Zoho task',
          platform: 'zoho',
          status: 'To Do',
          priority: 'Medium',
          assignee: 'Bob',
          due_date: '2025-01-22',
          project_name: 'Project E',
          url: 'https://zoho.com/tasks/5'
        },
        {
          id: 'task-6',
          name: 'Planner task',
          platform: 'planner',
          status: 'Completed',
          priority: 'Low',
          assignee: 'Charlie',
          due_date: '2025-01-19',
          project_name: 'Project F',
          url: 'https://planner.microsoft.com/tasks/6'
        }
      ];

      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              tasks: multiPlatformTasks,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveProjects());

      await waitFor(() => {
        const platforms = result.current.tasks.map(t => t.platform);
        expect(platforms).toContain('asana');
        expect(platforms).toContain('jira');
        expect(platforms).toContain('trello');
        expect(platforms).toContain('clickup');
        expect(platforms).toContain('zoho');
        expect(platforms).toContain('planner');
      });
    });

    test('ProjectStats structure', async () => {
      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              tasks: mockTasks,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveProjects());

      await waitFor(() => {
        expect(result.current.stats).toHaveProperty('total_active_tasks');
        expect(result.current.stats).toHaveProperty('completed_today');
        expect(result.current.stats).toHaveProperty('overdue_count');
        expect(result.current.stats).toHaveProperty('tasks_by_platform');

        expect(typeof result.current.stats.total_active_tasks).toBe('number');
        expect(typeof result.current.stats.completed_today).toBe('number');
        expect(typeof result.current.stats.overdue_count).toBe('number');
        expect(typeof result.current.stats.tasks_by_platform).toBe('object');
      });
    });

    test('optional fields in UnifiedTask', async () => {
      const tasksWithOptionals = [
        {
          id: 'task-1',
          name: 'Task without optionals',
          platform: 'jira',
          status: 'In Progress'
          // priority, assignee, due_date, project_name, url are optional
        }
      ];

      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              tasks: tasksWithOptionals,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveProjects());

      await waitFor(() => {
        expect(result.current.tasks[0].priority).toBeUndefined();
        expect(result.current.tasks[0].assignee).toBeUndefined();
        expect(result.current.tasks[0].due_date).toBeUndefined();
      });
    });
  });

  describe('3. Polling Behavior Tests', () => {
    test('sets up 60-second interval', async () => {
      let fetchCount = 0;

      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          fetchCount++;
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              tasks: mockTasks,
              providers: mockProviders
            })
          );
        })
      );

      renderHook(() => useLiveProjects());

      // Wait for initial fetch
      await waitFor(() => {
        expect(fetchCount).toBe(1);
      });

      // Fast-forward 60 seconds
      act(() => {
        jest.advanceTimersByTime(60000);
      });

      // Should have fetched again
      await waitFor(() => {
        expect(fetchCount).toBe(2);
      });
    });

    test('cleans up interval on unmount', async () => {
      let fetchCount = 0;

      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          fetchCount++;
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              tasks: mockTasks,
              providers: mockProviders
            })
          );
        })
      );

      const { unmount } = renderHook(() => useLiveProjects());

      // Wait for initial fetch
      await waitFor(() => {
        expect(fetchCount).toBe(1);
      });

      // Unmount the hook
      unmount();

      // Fast-forward past the interval time
      act(() => {
        jest.advanceTimersByTime(60000);
      });

      // Should not have fetched again after unmount
      expect(fetchCount).toBe(1);
    });

    test('clears interval in cleanup function', async () => {
      const clearIntervalSpy = jest.spyOn(global, 'clearInterval');

      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              tasks: [],
              providers: {}
            })
          );
        })
      );

      const { unmount } = renderHook(() => useLiveProjects());

      unmount();

      expect(clearIntervalSpy).toHaveBeenCalled();
      clearIntervalSpy.mockRestore();
    });

    test('polls multiple times over time', async () => {
      let fetchCount = 0;

      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          fetchCount++;
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              tasks: mockTasks,
              providers: mockProviders
            })
          );
        })
      );

      renderHook(() => useLiveProjects());

      // Wait for initial fetch
      await waitFor(() => {
        expect(fetchCount).toBe(1);
      });

      // Fast-forward through multiple intervals
      act(() => {
        jest.advanceTimersByTime(60000); // 1st interval
      });
      await waitFor(() => {
        expect(fetchCount).toBe(2);
      });

      act(() => {
        jest.advanceTimersByTime(60000); // 2nd interval
      });
      await waitFor(() => {
        expect(fetchCount).toBe(3);
      });

      act(() => {
        jest.advanceTimersByTime(60000); // 3rd interval
      });
      await waitFor(() => {
        expect(fetchCount).toBe(4);
      });
    });
  });

  describe('4. Refresh Function Tests', () => {
    test('re-fetches project data when called', async () => {
      let fetchCount = 0;

      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          fetchCount++;
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              tasks: mockTasks,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveProjects());

      // Wait for initial fetch
      await waitFor(() => {
        expect(fetchCount).toBe(1);
      });

      // Call refresh
      act(() => {
        result.current.refresh();
      });

      // Should have fetched again
      await waitFor(() => {
        expect(fetchCount).toBe(2);
      });
    });

    test('updates all states on refresh', async () => {
      let callCount = 0;

      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          callCount++;
          return res(
            ctx.json({
              ok: true,
              stats: {
                total_active_tasks: callCount * 10,
                completed_today: callCount * 3,
                overdue_count: callCount,
                tasks_by_platform: { jira: callCount * 5 }
              },
              tasks: callCount === 1 ? mockTasks : [],
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveProjects());

      // Initial fetch
      await waitFor(() => {
        expect(result.current.stats.total_active_tasks).toBe(10);
      });

      // Refresh
      act(() => {
        result.current.refresh();
      });

      await waitFor(() => {
        expect(result.current.stats.total_active_tasks).toBe(20);
        expect(result.current.tasks).toEqual([]);
      });
    });
  });

  describe('5. Loading States Tests', () => {
    test('initial isLoading is true', () => {
      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              tasks: [],
              providers: {}
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveProjects());

      expect(result.current.isLoading).toBe(true);
    });

    test('becomes false after fetch', async () => {
      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              tasks: mockTasks,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveProjects());

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    test('handles loading state on error', async () => {
      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          return res.networkError('Failed to connect');
        })
      );

      const { result } = renderHook(() => useLiveProjects());

      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });
  });

  describe('6. Error Handling Tests', () => {
    test('handles fetch errors gracefully', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          return res.networkError('Failed to connect');
        })
      );

      const { result } = renderHook(() => useLiveProjects());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to fetch live project board:',
        expect.any(Error)
      );
      consoleSpy.mockRestore();
    });

    test('console.error called with error', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          throw new Error('Network error');
        })
      );

      renderHook(() => useLiveProjects());

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledWith(
          'Failed to fetch live project board:',
          expect.any(Error)
        );
      });
      consoleSpy.mockRestore();
    });

    test('handles non-OK response', async () => {
      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          return res(ctx.status(500));
        })
      );

      const { result } = renderHook(() => useLiveProjects());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
        expect(result.current.tasks).toEqual([]);
      });
    });
  });

  describe('7. Provider Tracking Tests', () => {
    test('tracks active providers correctly', async () => {
      const customProviders = {
        asana: true,
        jira: true,
        trello: false,
        clickup: true,
        zoho: false,
        planner: true
      };

      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              tasks: mockTasks,
              providers: customProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveProjects());

      await waitFor(() => {
        expect(result.current.activeProviders).toEqual(customProviders);
        expect(Object.keys(result.current.activeProviders)).toHaveLength(6);
      });
    });

    test('updates providers on refresh', async () => {
      let callCount = 0;

      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          callCount++;
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              tasks: mockTasks,
              providers: callCount === 1
                ? { asana: true, jira: false, trello: false, clickup: false, zoho: false, planner: false }
                : { asana: true, jira: true, trello: true, clickup: true, zoho: true, planner: true }
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveProjects());

      // Initial state
      await waitFor(() => {
        expect(result.current.activeProviders.jira).toBe(false);
      });

      // Refresh
      act(() => {
        result.current.refresh();
      });

      // Updated state
      await waitFor(() => {
        expect(result.current.activeProviders.jira).toBe(true);
        expect(result.current.activeProviders.trello).toBe(true);
      });
    });
  });

  describe('8. Task Data Mapping Tests', () => {
    test('maps task priority correctly', async () => {
      const tasksWithPriorities = [
        { ...mockTasks[0], priority: 'High' },
        { ...mockTasks[1], priority: 'Medium' },
        { ...mockTasks[2], priority: 'Low' }
      ];

      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              tasks: tasksWithPriorities,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveProjects());

      await waitFor(() => {
        const priorities = result.current.tasks.map(t => t.priority);
        expect(priorities).toContain('High');
        expect(priorities).toContain('Medium');
        expect(priorities).toContain('Low');
      });
    });

    test('maps task status correctly', async () => {
      const tasksWithStatuses = [
        { ...mockTasks[0], status: 'In Progress' },
        { ...mockTasks[1], status: 'Completed' },
        { ...mockTasks[2], status: 'To Do' }
      ];

      overrideHandler(
        rest.get('/api/atom/projects/live/board', (req, res, ctx) => {
          return res(
            ctx.json({
              ok: true,
              stats: mockStats,
              tasks: tasksWithStatuses,
              providers: mockProviders
            })
          );
        })
      );

      const { result } = renderHook(() => useLiveProjects());

      await waitFor(() => {
        const statuses = result.current.tasks.map(t => t.status);
        expect(statuses).toContain('In Progress');
        expect(statuses).toContain('Completed');
        expect(statuses).toContain('To Do');
      });
    });
  });
});
