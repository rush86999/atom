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

// ---------------------------------------------------------------------------
// Extended coverage: shared component view navigation, grid event clicks,
// full dialog form fields, and time-range validation
// ---------------------------------------------------------------------------
import SharedCalendarManagement from '@/components/shared/CalendarManagement';

const fmtLocal = (d: Date) => {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

describe('SharedCalendarManagement (extended coverage)', () => {
  // R82: the old fixture used "today at 23:00" which is already in the past
  // for late-night runs — the upcoming list filters `start > new Date()`,
  // so the edit-row lookup silently broke after 23:00 local time. Pin the
  // event to tomorrow at 10:00 instead.
  const futureEvent = (hour: number) => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    d.setHours(hour, 0, 0, 0);
    return d;
  };

  const initialEvents = [
    {
      id: 'e1',
      title: 'Today Standup',
      description: 'Daily',
      start: futureEvent(10),
      end: futureEvent(10),
      location: 'Zoom',
      status: 'confirmed',
      platform: 'google',
      color: '#3182CE',
    },
  ];

  beforeEach(() => {
    jest.clearAllMocks();
  });

  const settle = async () => {
    await screen.findAllByText('Today Standup');
  };

  test('switches between Day, Week, and Month views and navigates dates', async () => {
    render(<SharedCalendarManagement initialEvents={initialEvents} />);

    const weekGridVisible = () =>
      document.querySelector('.grid.grid-cols-7') !== null;
    await waitFor(() => expect(weekGridVisible()).toBe(true));

    const navButtons = screen
      .getAllByRole('button')
      .filter((b) =>
        b.querySelector('svg.lucide-chevron-left, svg.lucide-chevron-right'),
      );
    expect(navButtons.length).toBeGreaterThanOrEqual(2);

    // Day view renders the single-day agenda for the current date
    fireEvent.click(screen.getByRole('button', { name: 'Day' }));
    fireEvent.click(navButtons[1]); // next -> tomorrow (where the fixture event lives)
    expect(screen.getByTestId('day-view')).toBeInTheDocument();
    expect(within(screen.getByTestId('day-view')).getByText('Today Standup')).toBeInTheDocument();

    // Month view renders a 6x7 grid with weekday headers and event chips
    fireEvent.click(screen.getByRole('button', { name: 'Month' }));
    fireEvent.click(navButtons[0]);
    fireEvent.click(navButtons[1]);
    expect(screen.getByTestId('month-view')).toBeInTheDocument();
    expect(screen.getByText('Sun')).toBeInTheDocument();
    expect(screen.getByText('Sat')).toBeInTheDocument();
    expect(within(screen.getByTestId('month-view')).getByText('Today Standup')).toBeInTheDocument();

    // Back to Week re-renders the week grid
    fireEvent.click(screen.getByRole('button', { name: 'Week' }));
    fireEvent.click(navButtons[0]);
    fireEvent.click(navButtons[1]);
    await waitFor(() => expect(weekGridVisible()).toBe(true));
  });

  test('Day view shows an empty-state message for a day without events', async () => {
    render(<SharedCalendarManagement initialEvents={initialEvents} />);
    await settle();

    fireEvent.click(screen.getByRole('button', { name: 'Day' }));
    // Navigate to yesterday, which has no events (tomorrow now holds the fixture event)
    const prevButton = screen
      .getAllByRole('button')
      .filter((b) => b.querySelector('svg.lucide-chevron-left'))[0];
    fireEvent.click(prevButton);

    expect(
      screen.getByText('No events scheduled for this day.')
    ).toBeInTheDocument();
  });

  test('Day and Month view event chips open the edit dialog', async () => {
    render(<SharedCalendarManagement initialEvents={initialEvents} />);
    await settle();

    // Day view chip (event lives tomorrow)
    fireEvent.click(screen.getByRole('button', { name: 'Day' }));
    const nextBtn = screen.getAllByRole('button').filter((b) => b.querySelector('svg.lucide-chevron-right'))[0];
    fireEvent.click(nextBtn);
    fireEvent.click(screen.getByTestId('day-view').querySelector('.font-bold.truncate')!);
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    // Month view chip
    fireEvent.click(screen.getByRole('button', { name: 'Month' }));
    fireEvent.click(screen.getByTestId('month-view').querySelector('.font-bold.truncate')!);
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /edit event/i })
    ).toBeInTheDocument();
  });

  test('opens the edit dialog from a grid event chip and from the edit icon', async () => {
    render(<SharedCalendarManagement initialEvents={initialEvents} />);

    await settle();

    // Open the edit dialog by clicking the event in the week grid
    const chip = screen.getAllByText('Today Standup')[0];
    fireEvent.click(chip);
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    // Edit icon button in the upcoming list
    const upcomingTitle = screen
      .getAllByText('Today Standup')
      .find((el) => el.closest('.flex.justify-between'));
    const row = (upcomingTitle!.closest('.flex.justify-between') as HTMLElement);
    const buttons = within(row).getAllByRole('button');
    fireEvent.click(buttons[0]); // edit icon
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
  });

  test('fills every dialog field and submits through the shared component', async () => {
    const onEventCreate = jest.fn();
    render(
      <SharedCalendarManagement
        initialEvents={initialEvents}
        onEventCreate={onEventCreate}
      />,
    );
    await settle();

    fireEvent.click(screen.getByRole('button', { name: /new event/i }));
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(within(dialog).getByPlaceholderText('Event title'), {
      target: { value: 'Full Form Event' },
    });
    fireEvent.change(
      within(dialog).getByPlaceholderText('Event description'),
      { target: { value: 'A description' },
    } as any);
    fireEvent.change(within(dialog).getByPlaceholderText('Event location'), {
      target: { value: 'HQ',
    } } as any);
    fireEvent.change(within(dialog).getByTestId('event-start'), {
      target: { value: fmtLocal(futureEvent(12)) },
    });
    fireEvent.change(within(dialog).getByTestId('event-end'), {
      target: { value: fmtLocal(futureEvent(13)) },
    });

    // Radix selects for status + platform
    const pickOption = async (trigger: Element, label: string) => {
      fireEvent.keyDown(trigger, { key: 'ArrowDown' });
      const option = await waitFor(() => {
        const found = Array.from(document.querySelectorAll('[role="option"]')).find(
          (i) => i.textContent === label
        );
        if (!found) throw new Error(`option ${label} not found`);
        return found as HTMLElement;
      });
      fireEvent.click(option);
    };
    const comboboxes = within(dialog).getAllByRole('combobox');
    await pickOption(comboboxes[0], 'Tentative');
    await pickOption(comboboxes[1], 'Outlook Calendar');

    // Color input
    const colorInput = within(dialog).getByDisplayValue(
      /^#[0-9a-fA-F]{6}$/,
    ) as HTMLInputElement;
    fireEvent.change(colorInput, { target: { value: '#E53E3E' } });

    fireEvent.click(within(dialog).getByTestId('event-submit'));

    await waitFor(() => {
      expect(onEventCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Full Form Event',
          description: 'A description',
          location: 'HQ',
          status: 'tentative',
          platform: 'outlook',
          color: '#e53e3e',
        }),
      );
    });
  });

  test('rejects an event whose end time is before its start time', async () => {
    const onEventCreate = jest.fn();
    render(
      <SharedCalendarManagement
        initialEvents={initialEvents}
        onEventCreate={onEventCreate}
      />,
    );
    await settle();

    fireEvent.click(screen.getByRole('button', { name: /new event/i }));
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(within(dialog).getByPlaceholderText('Event title'), {
      target: { value: 'Inverted Event' },
    });
    fireEvent.change(within(dialog).getByTestId('event-start'), {
      target: { value: fmtLocal(futureEvent(14)) },
    });
    fireEvent.change(within(dialog).getByTestId('event-end'), {
      target: { value: fmtLocal(futureEvent(13)) },
    });
    fireEvent.click(within(dialog).getByTestId('event-submit'));

    // Validation blocks the submit: dialog stays open, no event created.
    await new Promise((r) => setTimeout(r, 150));
    expect(onEventCreate).not.toHaveBeenCalled();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });
});
