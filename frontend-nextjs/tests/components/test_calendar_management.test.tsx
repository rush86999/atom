/**
 * CalendarManagement Component Tests
 *
 * Tests verify the real calendar components:
 * - components/CalendarManagement.tsx (wrapper): fetches events from
 *   GET /api/dashboard/events, creates via POST /api/dashboard/events,
 *   updates via PUT /api/v1/calendar/events/:id, deletes via DELETE
 *   /api/v1/calendar/events/:id
 * - components/shared/CalendarManagement.tsx (rendered UI): week grid,
 *   upcoming events list, event create/edit dialog, conflict detection
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import CalendarManagement from '@/components/CalendarManagement';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

// Events are placed ~10 days in the future so they are always in the
// "Upcoming Events" list but never in the current week grid (which would
// duplicate their title text and break single-element queries).
const inDays = (days: number, hour = 10, minute = 0) => {
  const d = new Date(Date.now() + days * 86400000);
  d.setHours(hour, minute, 0, 0);
  return d;
};

const eventA = {
  id: 'evt-1',
  title: 'Team Sync',
  description: 'Weekly sync',
  start: inDays(10, 10).toISOString(),
  end: inDays(10, 11).toISOString(),
  location: 'Room 1',
  status: 'confirmed',
  platform: 'google',
  color: '#3182CE',
};

const eventB = {
  id: 'evt-2',
  title: 'Project Review',
  start: inDays(11, 14).toISOString(),
  end: inDays(11, 15).toISOString(),
  status: 'tentative',
  platform: 'outlook',
  color: '#E53E3E',
};

const defaultHandlers = [
  rest.get('/api/dashboard/events', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json([eventA]));
  }),

  rest.post('/api/dashboard/events', (req, res, ctx) => {
    const body = req.body as any;
    return res(
      ctx.status(200),
      ctx.json({
        event: {
          id: 'new-1',
          title: body?.title || 'New Event',
          start: body?.start || inDays(1).toISOString(),
          end: body?.end || inDays(1, 11).toISOString(),
        },
      })
    );
  }),

  rest.put('/api/v1/calendar/events/:eventId', (req, res, ctx) => {
    const body = req.body as any;
    return res(
      ctx.status(200),
      ctx.json({
        event: {
          id: req.params.eventId,
          ...body,
          start: body?.start || inDays(1).toISOString(),
          end: body?.end || inDays(1, 11).toISOString(),
        },
      })
    );
  }),

  rest.delete('/api/v1/calendar/events/:eventId', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),
];

const fmtLocal = (d: Date) => {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(
    d.getHours()
  )}:${pad(d.getMinutes())}`;
};

describe('CalendarManagement', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...defaultHandlers);
  });

  // Test 1: renders the calendar with heading and New Event button
  test('renders calendar with heading and New Event button', async () => {
    render(<CalendarManagement />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /calendar management/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /new event/i })
      ).toBeInTheDocument();
    });
  });

  // Test 2: displays loaded events in the Upcoming Events list
  test('displays loaded events in the upcoming list', async () => {
    render(<CalendarManagement />);

    await waitFor(() => {
      expect(screen.getByText('Team Sync')).toBeInTheDocument();
    });
  });

  // Test 3: shows the view controls (Day / Week / Month)
  test('shows view controls', async () => {
    render(<CalendarManagement />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Day' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Week' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Month' })).toBeInTheDocument();
    });
  });

  // Test 4: shows the Schedule and Upcoming Events sections
  test('shows schedule and upcoming sections', async () => {
    render(<CalendarManagement />);

    await waitFor(() => {
      expect(screen.getByText('Schedule')).toBeInTheDocument();
      expect(screen.getByText('Upcoming Events')).toBeInTheDocument();
    });
  });

  // Test 5: renders without crashing when there are no events
  test('renders empty state with no events', async () => {
    server.use(
      rest.get('/api/dashboard/events', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json([]));
      })
    );

    render(<CalendarManagement />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /calendar management/i })
      ).toBeInTheDocument();
    });
  });

  // Test 6: New Event button opens the create dialog
  test('opens the create event dialog', async () => {
    render(<CalendarManagement />);

    await screen.findByText('Team Sync');

    fireEvent.click(screen.getByRole('button', { name: /new event/i }));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(
        screen.getByRole('heading', { name: /create new event/i })
      ).toBeInTheDocument();
    });
  });

  // Test 7: creating an event calls POST /api/dashboard/events
  test('creating an event posts to the dashboard events endpoint', async () => {
    let createdBody: any = null;
    server.use(
      rest.post('/api/dashboard/events', (req, res, ctx) => {
        // MSW pre-parses JSON request bodies into objects
        createdBody = req.body as any;
        return res(
          ctx.status(200),
          ctx.json({
            event: {
              id: 'new-1',
              title: createdBody?.title || 'New Event',
              start: createdBody?.start || inDays(1).toISOString(),
              end: createdBody?.end || inDays(1, 11).toISOString(),
            },
          })
        );
      })
    );

    render(<CalendarManagement />);

    await screen.findByText('Team Sync');

    fireEvent.click(screen.getByRole('button', { name: /new event/i }));

    fireEvent.change(screen.getByPlaceholderText('Event title'), {
      target: { value: 'New Standup' },
    });
    fireEvent.change(screen.getByTestId('event-start'), {
      target: { value: fmtLocal(inDays(1)) },
    });
    fireEvent.change(screen.getByTestId('event-end'), {
      target: { value: fmtLocal(inDays(1, 11)) },
    });

    fireEvent.click(screen.getByTestId('event-submit'));

    await waitFor(() => {
      expect(createdBody).toEqual(
        expect.objectContaining({ title: 'New Standup' })
      );
    });
  });

  // Test 8: clicking an event opens the edit dialog with prefilled title
  test('opens the edit dialog with prefilled data', async () => {
    render(<CalendarManagement />);

    const title = await screen.findByText('Team Sync');
    fireEvent.click(title);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /edit event/i })
      ).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Event title')).toHaveValue(
        'Team Sync'
      );
    });
  });

  // Test 9: updating an event calls PUT /api/v1/calendar/events/:id
  test('updating an event calls the update endpoint', async () => {
    let updateId: string | null = null;
    let updateBody: any = null;
    server.use(
      rest.put('/api/v1/calendar/events/:eventId', (req, res, ctx) => {
        updateId = req.params.eventId as string;
        updateBody = req.body as any;
        return res(
          ctx.status(200),
          ctx.json({
            event: {
              id: req.params.eventId,
              ...(req.body as any),
              start: inDays(1).toISOString(),
              end: inDays(1, 11).toISOString(),
            },
          })
        );
      })
    );

    render(<CalendarManagement />);

    const title = await screen.findByText('Team Sync');
    fireEvent.click(title);

    await screen.findByRole('heading', { name: /edit event/i });

    fireEvent.change(screen.getByPlaceholderText('Event title'), {
      target: { value: 'Team Sync (Updated)' },
    });

    fireEvent.click(screen.getByTestId('event-submit'));

    await waitFor(() => {
      expect(updateId).toBe('evt-1');
      expect(updateBody).toEqual(
        expect.objectContaining({ title: 'Team Sync (Updated)' })
      );
    });
  });

  // Test 10: delete button calls DELETE /api/v1/calendar/events/:id
  test('deleting an event calls the delete endpoint', async () => {
    let deletedId: string | null = null;
    server.use(
      rest.delete('/api/v1/calendar/events/:eventId', (req, res, ctx) => {
        deletedId = req.params.eventId as string;
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );

    render(<CalendarManagement />);

    const title = await screen.findByText('Team Sync');

    // Locate the upcoming-events row containing the title, then the Trash
    // icon button (the second button in the row's action group).
    const row = (title.closest('.flex.justify-between') as HTMLElement) || title.parentElement;
    const actionButtons = within(row).getAllByRole('button');
    const deleteButton = actionButtons[actionButtons.length - 1];

    fireEvent.click(deleteButton);

    await waitFor(() => {
      expect(deletedId).toBe('evt-1');
    });
  });

  // Test 11: detects overlapping events and shows a conflict alert
  test('shows a conflict alert for overlapping events', async () => {
    const overlappingA = {
      id: 'evt-1',
      title: 'Team Sync',
      start: inDays(10, 10).toISOString(),
      end: inDays(10, 11).toISOString(),
      status: 'confirmed',
      platform: 'google',
    };
    const overlappingB = {
      id: 'evt-2',
      title: 'Standup',
      start: inDays(10, 10, 30).toISOString(),
      end: inDays(10, 11, 30).toISOString(),
      status: 'confirmed',
      platform: 'outlook',
    };

    server.use(
      rest.get('/api/dashboard/events', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json([overlappingA, overlappingB]));
      })
    );

    render(<CalendarManagement />);

    await screen.findByText('Team Sync');

    await waitFor(() => {
      expect(screen.getByText('Scheduling Conflicts')).toBeInTheDocument();
      expect(
        screen.getByText('Found 1 scheduling conflict')
      ).toBeInTheDocument();
    });
  });
});
