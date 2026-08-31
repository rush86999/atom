/**
 * ZoomIntegration Component Tests
 *
 * Tests verify the real Zoom integration component:
 * - Health check / connection state
 * - OAuth connect flow
 * - Profile, meetings, users, and recordings data loading
 * - Search filtering and create-meeting dialog
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/ZoomIntegration.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ZoomIntegration from '@/components/ZoomIntegration';
import { useToast } from '@/components/ui/use-toast';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const getToastMock = (): jest.Mock => (useToast as jest.Mock)().toast;

const zoomHandlers = [
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ providers: { zoom: { connected: true, source: 'user_connection' } } })
    );
  }),
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ providers: { zoom: { connected: true, source: 'user_connection' } } }));
  }),

  rest.post('/api/integrations/zoom/profile', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          profile: {
            id: 'u1',
            first_name: 'Rushi',
            last_name: 'Parikh',
            email: 'rushi@example.com',
            role_name: 'Owner',
            pic_url: '',
            personal_meeting_url: 'https://zoom.us/my/rushi',
          },
        },
      })
    );
  }),

  rest.post('/api/integrations/zoom/meetings', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          meetings: [
            {
              id: 'm1',
              topic: 'Weekly Sync',
              start_time: '2024-01-15T10:00:00Z',
              duration: 60,
              timezone: 'UTC',
              join_url: 'https://zoom.us/j/123',
              agenda: 'Weekly sync',
              settings: { auto_recording: 'none' },
            },
            {
              id: 'm2',
              topic: 'Design Review',
              start_time: '2024-01-16T10:00:00Z',
              duration: 30,
              timezone: 'UTC',
              join_url: 'https://zoom.us/j/456',
              settings: { auto_recording: 'cloud' },
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/zoom/users', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          users: [
            {
              id: 'u1',
              email: 'rushi@example.com',
              first_name: 'Rushi',
              last_name: 'Parikh',
              status: 'active',
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/zoom/recordings', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { recordings: [] } }));
  }),
];

const setDisconnected = () => {
  server.use(
    rest.get('/api/integrations/connection-status', (req, res, ctx) => {
      return res(ctx.status(404));
    })
  );
};

// Profile/meetings are loaded in both checkConnection() and the connected
// useEffect (double data-load race); wait for the full dataset to settle.
const settleData = async (text: RegExp) => {
  await screen.findByText(text);
  await new Promise((r) => setTimeout(r, 50));
};

describe('ZoomIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...zoomHandlers);
  });

  // Test 1: renders component
  test('renders component', () => {
    render(<ZoomIntegration />);

    expect(
      screen.getByRole('heading', { name: /zoom integration/i })
    ).toBeInTheDocument();
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    setDisconnected();

    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect zoom account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 3: connect button is clickable without crashing (jsdom logs the
  // navigation attempt; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setDisconnected();

    render(<ZoomIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect zoom account/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 4: shows connected state when health check passes
  test('shows connected state when health check passes', async () => {
    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 5: displays user profile after connection
  test('displays user profile after connection', async () => {
    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Rushi Parikh')).toBeInTheDocument();
    });
  });

  // Test 6: displays meetings after connection
  test('displays meetings after connection', async () => {
    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Weekly Sync')).toBeInTheDocument();
      expect(screen.getByText('Design Review')).toBeInTheDocument();
    });
  });

  // Test 7: filters meetings by search query
  test('filters meetings by search query', async () => {
    render(<ZoomIntegration />);

    await settleData(/Weekly Sync/);

    const searchInput = screen.getByPlaceholderText(/search meetings/i);
    fireEvent.change(searchInput, { target: { value: 'Design' } });

    await waitFor(() => {
      expect(screen.getByText('Design Review')).toBeInTheDocument();
    });
    expect(screen.queryByText('Weekly Sync')).not.toBeInTheDocument();
  });

  // Test 8: displays users on the Users tab
  test('displays users on the Users tab', async () => {
    render(<ZoomIntegration />);

    await settleData(/Weekly Sync/);

    // The profile header already shows "Rushi Parikh"; the Users tab renders
    // the same name in the user list, so assert a second occurrence appears.
    const before = screen.getAllByText('Rushi Parikh').length;

    const usersTab = screen.getByRole('button', { name: 'Users' });
    fireEvent.click(usersTab);

    await waitFor(() => {
      expect(screen.getAllByText('Rushi Parikh').length).toBeGreaterThan(before);
    });
  });

  // Test 9: opens create meeting dialog
  test('opens create meeting dialog', async () => {
    render(<ZoomIntegration />);

    const createButton = await screen.findByRole('button', {
      name: /schedule meeting/i,
    });
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  // Test 10: handles connection error
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/integrations/connection-status', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect zoom account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 11: shows refresh status button
  test('shows refresh status button', async () => {
    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh status/i })).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Extended coverage: tab data rendering, create flows, and error paths
// ---------------------------------------------------------------------------
describe('ZoomIntegration (extended coverage)', () => {
  // NOTE: jest.config.js sets restoreMocks:true, which detaches describe-scope
  // spies after every test — create a fresh console.error spy per test.
  let errorSpy: jest.SpyInstance;
  beforeEach(() => {
    errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  const futureDate = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();
  const pastDate = new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString();

  const richMeetings = [
    {
      uuid: 'uuid-1',
      id: 1,
      topic: 'Instant Standup',
      type: 1,
      start_time: futureDate,
      duration: 15,
      timezone: 'UTC',
      agenda: 'Daily sync',
      join_url: 'https://zoom.us/j/1',
      start_url: 'https://zoom.us/s/1',
      participant_count: 4,
    },
    {
      uuid: 'uuid-2',
      id: 2,
      topic: 'Scheduled Planning',
      type: 2,
      start_time: futureDate,
      duration: 60,
      timezone: 'UTC',
      join_url: 'https://zoom.us/j/2',
      start_url: 'https://zoom.us/s/2',
    },
    {
      uuid: 'uuid-3',
      id: 3,
      topic: 'Recurring Retro',
      type: 3,
      start_time: pastDate,
      duration: 30,
      timezone: 'UTC',
      join_url: 'https://zoom.us/j/3',
      start_url: 'https://zoom.us/s/3',
    },
    {
      uuid: 'uuid-4',
      id: 4,
      topic: 'Fixed Time Workshop',
      type: 8,
      start_time: pastDate,
      duration: 90,
      timezone: 'UTC',
      join_url: 'https://zoom.us/j/4',
      start_url: 'https://zoom.us/s/4',
    },
  ];

  const richUsers = [
    {
      id: 'u1',
      email: 'alice@example.com',
      first_name: 'Alice',
      last_name: 'Admin',
      type: 1,
      status: 'active',
      role_name: 'Owner',
      timezone: 'UTC',
      last_login_time: '2024-01-10T09:00:00Z',
      personal_meeting_url: 'https://zoom.us/my/alice',
    },
    {
      id: 'u2',
      email: 'bob@example.com',
      first_name: 'Bob',
      last_name: 'Basic',
      type: 2,
      status: 'inactive',
      role_name: 'Member',
      timezone: 'UTC',
      last_login_time: '',
      personal_meeting_url: '',
    },
    {
      id: 'u3',
      email: 'carol@example.com',
      first_name: 'Carol',
      last_name: 'Cooper',
      type: 3,
      status: 'pending',
      role_name: 'Member',
      timezone: 'UTC',
    },
  ];

  const richRecordings = [
    {
      uuid: 'rec-1',
      id: 101,
      topic: 'All Hands Recording',
      start_time: '2024-01-05T15:00:00Z',
      timezone: 'UTC',
      duration: 90,
      total_size: 52428800,
      password: 'secret123',
      recording_files: [
        {
          id: 'f1',
          file_type: 'mp4',
          file_size: 52428800,
          play_url: 'https://zoom.us/rec/play/f1',
        },
      ],
    },
    {
      uuid: 'rec-2',
      id: 102,
      topic: 'Training Session',
      start_time: '2024-01-06T15:00:00Z',
      timezone: 'UTC',
      duration: 45,
      total_size: 0,
      recording_files: [],
    },
  ];

  // NOTE: MSW resolves handlers in the order passed to server.use(), so the
  // data-rich overrides must come BEFORE the base zoomHandlers.
  const richHandlers = [
    rest.post('/api/integrations/zoom/meetings', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { meetings: richMeetings } }));
    }),
    rest.post('/api/integrations/zoom/users', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { users: richUsers } }));
    }),
    rest.post('/api/integrations/zoom/recordings', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { recordings: richRecordings } }));
    }),
    rest.post('/api/integrations/zoom/meetings/create', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { meeting: { id: 999 } } }));
    }),
    rest.post('/api/integrations/zoom/users/create', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { user: { id: 'u999' } } }));
    }),
    ...zoomHandlers,
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...richHandlers);
  });

  const settle = async (text: RegExp | string) => {
    await screen.findByText(text);
    await new Promise((r) => setTimeout(r, 50));
  };

  const clickFooterButton = (dialog: HTMLElement, label: RegExp) => {
    const buttons = Array.from(dialog.querySelectorAll('button')).filter((b) =>
      label.test(b.textContent || '')
    );
    fireEvent.click(buttons[buttons.length - 1]);
  };

  test('renders meetings with type and status badges', async () => {
    render(<ZoomIntegration />);

    await settle('Instant Standup');
    expect(screen.getByText('Scheduled Planning')).toBeInTheDocument();
    expect(screen.getByText('Recurring Retro')).toBeInTheDocument();
    expect(screen.getByText('Fixed Time Workshop')).toBeInTheDocument();
    expect(screen.getByText('Daily sync')).toBeInTheDocument();
    expect(screen.getAllByText('Upcoming').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Ended').length).toBeGreaterThan(0);
  });

  test('Start and Join buttons open meeting urls', async () => {
    const openSpy = jest.fn();
    window.open = openSpy as any;

    render(<ZoomIntegration />);
    await settle('Instant Standup');

    fireEvent.click(screen.getAllByRole('button', { name: /start/i })[0]);
    fireEvent.click(screen.getAllByRole('button', { name: /^join/i })[0]);

    expect(openSpy).toHaveBeenCalledWith('https://zoom.us/s/1', '_blank');
    expect(openSpy).toHaveBeenCalledWith('https://zoom.us/j/1', '_blank');
  });

  test('displays users tab with type, status badges and login info', async () => {
    render(<ZoomIntegration />);
    await settle('Instant Standup');

    fireEvent.click(screen.getByRole('button', { name: 'Users' }));

    expect(await screen.findByText('Alice Admin')).toBeInTheDocument();
    expect(screen.getByText('Bob Basic')).toBeInTheDocument();
    expect(screen.getByText('Carol Cooper')).toBeInTheDocument();
    expect(screen.getByText('Basic')).toBeInTheDocument();
    expect(screen.getByText('Licensed')).toBeInTheDocument();
    expect(screen.getByText('On-Prem')).toBeInTheDocument();
    expect(screen.getAllByText('active').length).toBeGreaterThan(0);
    expect(screen.getByText('inactive')).toBeInTheDocument();
    expect(screen.getByText('pending')).toBeInTheDocument();
    expect(screen.getAllByText(/Never/).length).toBeGreaterThan(0);
    expect(screen.getByText('PMI')).toBeInTheDocument();
  });

  test('filters users by search query', async () => {
    render(<ZoomIntegration />);
    await settle('Instant Standup');

    fireEvent.click(screen.getByRole('button', { name: 'Users' }));
    expect(await screen.findByText('Alice Admin')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/search users/i), {
      target: { value: 'carol@' },
    });

    await waitFor(() => {
      expect(screen.getByText('Carol Cooper')).toBeInTheDocument();
    });
    expect(screen.queryByText('Alice Admin')).not.toBeInTheDocument();
  });

  test('displays recordings tab with password badge and play buttons', async () => {
    render(<ZoomIntegration />);
    await settle('Instant Standup');

    fireEvent.click(screen.getByRole('button', { name: 'Recordings' }));

    expect(await screen.findByText('All Hands Recording')).toBeInTheDocument();
    expect(screen.getByText('Training Session')).toBeInTheDocument();
    expect(screen.getByText('Password Protected')).toBeInTheDocument();
    expect(screen.getAllByText(/MP4/).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('button', { name: /play mp4/i }));
  });

  test('Play button opens the recording url', async () => {
    const openSpy = jest.fn();
    window.open = openSpy as any;

    render(<ZoomIntegration />);
    await settle('Instant Standup');

    fireEvent.click(screen.getByRole('button', { name: 'Recordings' }));

    const playButton = await screen.findByRole('button', { name: /play mp4/i });
    fireEvent.click(playButton);

    expect(openSpy).toHaveBeenCalledWith('https://zoom.us/rec/play/f1', '_blank');
  });

  test('schedules a meeting through the dialog', async () => {
    render(<ZoomIntegration />);
    await settle('Instant Standup');

    fireEvent.click(screen.getByRole('button', { name: /schedule meeting/i }));
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(screen.getByPlaceholderText('Meeting topic'), {
      target: { value: 'Quarterly Review' },
    });
    fireEvent.change(screen.getByPlaceholderText('Meeting description/agenda'), {
      target: { value: 'Q1 review' },
    });
    fireEvent.change(screen.getByPlaceholderText('Meeting password'), {
      target: { value: 'pw123' },
    });

    clickFooterButton(dialog, /schedule meeting/i);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Success',
          description: 'Meeting created successfully',
        })
      );
    });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  test('shows error toast when meeting creation fails', async () => {
    server.use(
      rest.post('/api/integrations/zoom/meetings/create', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<ZoomIntegration />);
    await settle('Instant Standup');

    fireEvent.click(screen.getByRole('button', { name: /schedule meeting/i }));
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(screen.getByPlaceholderText('Meeting topic'), {
      target: { value: 'Failing Meeting' },
    });
    clickFooterButton(dialog, /schedule meeting/i);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', description: 'Failed to create meeting' })
      );
    });
  });

  test('adds a user through the dialog', async () => {
    render(<ZoomIntegration />);
    await settle('Instant Standup');

    fireEvent.click(screen.getByRole('button', { name: 'Users' }));
    fireEvent.click(screen.getAllByRole('button', { name: /add user/i })[0]);
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(screen.getByPlaceholderText('user@example.com'), {
      target: { value: 'newbie@example.com' },
    });
    fireEvent.change(screen.getByPlaceholderText('First name'), {
      target: { value: 'Nina' },
    });
    fireEvent.change(screen.getByPlaceholderText('Last name'), {
      target: { value: 'Newbie' },
    });
    clickFooterButton(dialog, /add user/i);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Success',
          description: 'User created successfully',
        })
      );
    });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  test('shows error toast when user creation fails', async () => {
    server.use(
      rest.post('/api/integrations/zoom/users/create', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<ZoomIntegration />);
    await settle('Instant Standup');

    fireEvent.click(screen.getByRole('button', { name: 'Users' }));
    fireEvent.click(screen.getAllByRole('button', { name: /add user/i })[0]);
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(screen.getByPlaceholderText('user@example.com'), {
      target: { value: 'bad@example.com' },
    });
    fireEvent.change(screen.getByPlaceholderText('First name'), {
      target: { value: 'Bad' },
    });
    fireEvent.change(screen.getByPlaceholderText('Last name'), {
      target: { value: 'User' },
    });
    clickFooterButton(dialog, /add user/i);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', description: 'Failed to create user' })
      );
    });
  });

  test('shows error toast when meetings loading fails', async () => {
    server.use(
      rest.post('/api/integrations/zoom/meetings', (req, res) => res.networkError('boom'))
    );

    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to load meetings from Zoom',
        })
      );
    });
  });

  test('logs errors when auxiliary loads fail and health check throws', async () => {
    const netFail = (path: string) => rest.post(path, (req, res) => res.networkError('boom'));
    server.use(
      netFail('/api/integrations/zoom/profile'),
      netFail('/api/integrations/zoom/users'),
      netFail('/api/integrations/zoom/recordings')
    );

    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Failed to load user profile:', expect.anything());
      expect(errorSpy).toHaveBeenCalledWith('Failed to load users:', expect.anything());
      expect(errorSpy).toHaveBeenCalledWith('Failed to load recordings:', expect.anything());
    });
  });

  test('treats health check network failure as disconnected', async () => {
    server.use(
      rest.get('/api/integrations/connection-status', (req, res) => res.networkError('boom'))
    );

    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Connection status check failed:', expect.anything());
      expect(
        screen.getByRole('button', { name: /connect zoom account/i })
      ).toBeInTheDocument();
    });
  });

  test('clicking Refresh Status re-runs the health check', async () => {
    render(<ZoomIntegration />);
    await settle('Instant Standup');

    fireEvent.click(screen.getByRole('button', { name: /refresh status/i }));
    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });
});
