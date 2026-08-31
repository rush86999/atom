/**
 * TeamsIntegration Component Tests
 *
 * Tests verify the real Microsoft Teams integration component:
 * - Health check / connection state (connected + disconnected)
 * - OAuth connect flow
 * - Profile, teams, channels, messages, meetings, and users data loading
 * - Search filtering across tabs
 * - Create team / channel / meeting and send-message flows
 * - Empty states
 * - Crash-safety on partial API data (missing optional description)
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/TeamsIntegration.tsx
 */

import React from 'react';
import {
  render,
  screen,
  fireEvent,
  waitFor,
  within,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import TeamsIntegration from '@/components/TeamsIntegration';
import { useToast } from '@/components/ui/use-toast';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const getToastMock = (): jest.Mock => (useToast as jest.Mock)().toast;

const mockTeams = [
  {
    id: 't1',
    displayName: 'Engineering',
    description: 'Core engineering team',
    createdDateTime: '2026-01-15T10:00:00Z',
    updatedDateTime: '2026-01-15T10:00:00Z',
    visibility: 'public',
    specialization: 'none',
    webUrl: 'https://teams.example.com/eng',
    internalId: 'it1',
    isArchived: false,
  },
  {
    // Deliberately missing `description` — the Graph API returns it as
    // nullable. The card renders without it; the search filter must not crash.
    // (The key is omitted so JSON serialization drops it → undefined client-side.)
    id: 't2',
    displayName: 'Design',
    createdDateTime: '2026-01-16T10:00:00Z',
    updatedDateTime: '2026-01-16T10:00:00Z',
    visibility: 'private',
    specialization: 'educationClass',
    webUrl: 'https://teams.example.com/design',
    internalId: 'it2',
    isArchived: true,
  },
];

const mockChannels: any[] = [
  {
    id: 'c1',
    displayName: 'General',
    description: 'General chat',
    createdDateTime: '2026-01-20T10:00:00Z',
    updatedDateTime: '2026-01-20T10:00:00Z',
    email: 'general@example.com',
    isFavoriteByDefault: true,
    membershipType: 'standard',
    tenant: 'tenant',
    webUrl: 'https://teams.example.com/general',
    tabs: [{ id: 'tab1', displayName: 'Wiki', teamsAppId: 'a', sortorderindex: '1', webUrl: '' }],
    messages: [],
  },
  {
    id: 'c2',
    displayName: 'Frontend',
    description: 'Frontend work',
    createdDateTime: '2026-01-21T10:00:00Z',
    updatedDateTime: '2026-01-21T10:00:00Z',
    email: 'frontend@example.com',
    isFavoriteByDefault: false,
    membershipType: 'private',
    tenant: 'tenant',
    webUrl: 'https://teams.example.com/frontend',
    tabs: [],
    messages: [],
  },
  {
    id: 'c3',
    displayName: 'Shared Links',
    createdDateTime: '2026-01-22T10:00:00Z',
    updatedDateTime: '2026-01-22T10:00:00Z',
    email: 'shared@example.com',
    isFavoriteByDefault: false,
    membershipType: 'shared',
    tenant: 'tenant',
    webUrl: 'https://teams.example.com/shared',
    tabs: [],
    messages: [],
  },
];

const mockMessages = [
  {
    id: 'm1',
    messageType: 'message',
    createdDateTime: '2026-02-01T10:00:00Z',
    lastModifiedDateTime: '2026-02-01T10:00:00Z',
    conversationId: 'c1',
    from: {
      user: { id: 'u1', displayName: 'Alice Johnson' },
    },
    body: { content: 'Hello from Alice', contentType: 'text' },
    importance: 'high',
    reactions: [
      {
        reactionType: '👍',
        createdDateTime: '2026-02-01T10:05:00Z',
        user: { displayName: 'Alice Johnson', id: 'u1' },
      },
    ],
  },
  {
    // Bot/application message: `from.user` is absent — the UI must fall back
    // to the "?" avatar fallback instead of crashing.
    id: 'm2',
    messageType: 'message',
    createdDateTime: '2026-02-01T11:00:00Z',
    lastModifiedDateTime: '2026-02-01T11:00:00Z',
    conversationId: 'c1',
    from: {
      application: { id: 'app1', displayName: 'Deploy Bot' },
    },
    body: { content: 'Deploy completed', contentType: 'text' },
    importance: 'normal',
  },
];

const mockMeetings = [
  {
    id: 'mt1',
    subject: 'Sprint Planning',
    body: {
      contentType: 'text',
      content:
        'Discuss the upcoming sprint goals. ' +
        'This long body exists to exercise the 200-character truncation ' +
        'branch in the meeting card renderer, ensuring the ellipsis is ' +
        'shown when the description is too long to display in full.',
    },
    start: { dateTime: '2026-09-01T09:00:00Z', timeZone: 'UTC' },
    end: { dateTime: '2026-09-01T10:00:00Z', timeZone: 'UTC' },
    location: { displayName: 'Zoom HQ' },
    attendees: [
      {
        type: 'required',
        status: { response: 'accepted', time: '2026-08-01T09:00:00Z' },
        emailAddress: { name: 'Alice Johnson', address: 'alice@example.com' },
      },
      {
        type: 'required',
        status: { response: 'declined', time: '2026-08-01T09:00:00Z' },
        emailAddress: { name: 'Bob Smith', address: 'bob@example.com' },
      },
      {
        type: 'required',
        status: { response: 'tentative', time: '2026-08-01T09:00:00Z' },
        emailAddress: { name: 'Carol Lee', address: 'carol@example.com' },
      },
      {
        type: 'required',
        status: { response: 'notResponded', time: '2026-08-01T09:00:00Z' },
        emailAddress: { name: 'Dave Kim', address: 'dave@example.com' },
      },
    ],
    isOnlineMeeting: true,
    joinUrl: 'https://teams.example.com/join/123',
    createdDateTime: '2026-08-01T09:00:00Z',
    lastModifiedDateTime: '2026-08-01T09:00:00Z',
  },
  {
    id: 'mt2',
    subject: 'Kickoff',
    start: { dateTime: '2026-01-01T09:00:00Z', timeZone: 'UTC' },
    end: { dateTime: '2026-01-01T10:00:00Z', timeZone: 'UTC' },
    isOnlineMeeting: false,
    createdDateTime: '2025-12-01T09:00:00Z',
    lastModifiedDateTime: '2025-12-01T09:00:00Z',
  },
];

const mockUsers = [
  {
    id: 'u1',
    displayName: 'Alice Johnson',
    givenName: 'Alice',
    surname: 'Johnson',
    mail: 'alice@example.com',
    jobTitle: 'Engineer',
    officeLocation: 'San Francisco',
    department: 'Engineering',
    userPrincipalName: 'alice@example.com',
    accountEnabled: true,
  },
  {
    id: 'u2',
    displayName: 'Bob Smith',
    givenName: 'Bob',
    surname: 'Smith',
    jobTitle: 'Designer',
    userPrincipalName: 'bob@example.com',
    accountEnabled: false,
  },
];

const teamsHandlers = [
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ providers: { teams: { connected: true, source: 'user_connection' } } })
    );
  }),
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ providers: { teams: { connected: true, source: 'user_connection' } } }));
  }),

  rest.post('/api/integrations/teams/profile', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          profile: {
            id: 'u1',
            displayName: 'Rushi Parikh',
            mail: 'rushi@example.com',
            jobTitle: 'Platform Engineer',
            userPrincipalName: 'rushi@example.com',
            accountEnabled: true,
          },
        },
      })
    );
  }),

  rest.post('/api/integrations/teams/teams', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { teams: mockTeams } }));
  }),

  rest.post('/api/integrations/teams/channels', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { channels: mockChannels } }));
  }),

  rest.post('/api/integrations/teams/messages', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { messages: mockMessages } }));
  }),

  rest.post('/api/integrations/teams/meetings', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { meetings: mockMeetings } }));
  }),

  rest.post('/api/integrations/teams/users', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { users: mockUsers } }));
  }),

  rest.post('/api/integrations/teams/teams/create', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),

  rest.post('/api/integrations/teams/channels/create', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),

  rest.post('/api/integrations/teams/messages/send', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),

  rest.post('/api/integrations/teams/meetings/create', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),
];

const setDisconnected = () => {
  server.use(
    rest.get('/api/integrations/connection-status', (req, res, ctx) => {
      return res(ctx.status(404));
    })
  );
};

// Data is loaded in both checkConnection() and the connected useEffect
// (double data-load race); wait for the full dataset to settle.
const settleData = async (text: RegExp) => {
  await screen.findByText(text);
  await new Promise((r) => setTimeout(r, 50));
};

// Select a team by clicking its card in the default Teams tab, which triggers
// the channel load for that team.
const selectTeamByCard = async (user: ReturnType<typeof userEvent.setup>, name: string) => {
  await user.click(screen.getByText(name));
  await new Promise((r) => setTimeout(r, 50));
};

describe('TeamsIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...teamsHandlers);
  });

  describe('Connection flow', () => {
    test('renders component heading', () => {
      render(<TeamsIntegration />);

      expect(
        screen.getByRole('heading', { name: /microsoft teams integration/i })
      ).toBeInTheDocument();
    });

    test('shows connect card when not connected', async () => {
      setDisconnected();

      render(<TeamsIntegration />);

      await waitFor(() => {
        expect(
          screen.getByRole('button', { name: /connect microsoft teams account/i })
        ).toBeInTheDocument();
      });
      expect(screen.getByText('Disconnected')).toBeInTheDocument();
    });

    test('connect button initiates connection flow without crashing', async () => {
      setDisconnected();

      render(<TeamsIntegration />);

      const connectButton = await screen.findByRole('button', {
        name: /connect microsoft teams account/i,
      });
      expect(() => fireEvent.click(connectButton)).not.toThrow();
    });

    test('shows connected state when health check passes', async () => {
      render(<TeamsIntegration />);

      await waitFor(() => {
        expect(screen.getByText('Connected')).toBeInTheDocument();
      });
    });

    test('handles health check server error', async () => {
      server.use(
        rest.get('/api/integrations/connection-status', (req, res, ctx) => {
          return res(ctx.status(500));
        })
      );

      render(<TeamsIntegration />);

      await waitFor(() => {
        expect(
          screen.getByRole('button', { name: /connect microsoft teams account/i })
        ).toBeInTheDocument();
      });
    });

    test('handles health check network failure', async () => {
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      server.use(
        rest.get('/api/integrations/connection-status', (req, res) => {
          return new Promise((resolve, reject) => {
            setTimeout(() => reject(new Error('network error')), 10);
          });
        })
      );

      render(<TeamsIntegration />);

      await waitFor(() => {
        expect(
          screen.getByRole('button', { name: /connect microsoft teams account/i })
        ).toBeInTheDocument();
      });

      consoleErrorSpy.mockRestore();
    });

    test('refresh status button re-runs the health check', async () => {
      const fetchSpy = jest.spyOn(global, 'fetch');

      render(<TeamsIntegration />);

      await waitFor(() => {
        expect(screen.getByText('Connected')).toBeInTheDocument();
      });
      fetchSpy.mockClear();

      await userEvent.click(
        screen.getByRole('button', { name: /refresh status/i })
      );

      // The click must trigger a fresh health check fetch
      // (round 80: the fetch now carries authHeaders options)
      await waitFor(() => {
        expect(fetchSpy).toHaveBeenCalledWith(
          expect.stringContaining('/api/integrations/connection-status'),
          expect.objectContaining({ headers: expect.objectContaining({}) })
        );
      });
    });
  });

  describe('Profile and stats', () => {
    test('displays user profile after connection', async () => {
      render(<TeamsIntegration />);

      await waitFor(() => {
        expect(screen.getByText('Rushi Parikh')).toBeInTheDocument();
      });
      expect(screen.getByText('Platform Engineer')).toBeInTheDocument();
    });

    test('renders stats cards with totals', async () => {
      render(<TeamsIntegration />);

      // teams: 2, meetings: 2 total (1 upcoming), users: 2 total (1 active)
      await settleData(/Communication channels/);

      expect(screen.getByText('Active workspaces')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument(); // Teams stat
      expect(screen.getAllByText('2 total').length).toBe(2); // Meetings + Users
      // Channels stat is 0 until a team is selected (channels load lazily)
      expect(screen.getAllByText('0').length).toBeGreaterThan(0);
    });

    test('channels stat updates after selecting a team', async () => {
      const user = userEvent.setup();
      render(<TeamsIntegration />);

      await settleData(/Engineering/);
      await selectTeamByCard(user, 'Engineering');

      await waitFor(() => {
        expect(screen.getByText('3')).toBeInTheDocument(); // Channels stat
      });
    });
  });

  describe('Teams tab', () => {
    test('displays teams with visibility and specialization badges', async () => {
      render(<TeamsIntegration />);

      await settleData(/Engineering/);

      expect(screen.getByText('Design')).toBeInTheDocument();
      expect(screen.getByText('public')).toBeInTheDocument();
      expect(screen.getByText('private')).toBeInTheDocument();
      expect(screen.getByText('Archived')).toBeInTheDocument();
      expect(screen.getByText('Core engineering team')).toBeInTheDocument();
    });

    test('filters teams by search query', async () => {
      render(<TeamsIntegration />);

      await settleData(/Engineering/);

      fireEvent.change(screen.getByPlaceholderText(/search teams/i), {
        target: { value: 'eng' },
      });

      await waitFor(() => {
        expect(screen.getByText('Engineering')).toBeInTheDocument();
        expect(screen.queryByText('Design')).not.toBeInTheDocument();
      });
    });

    test('does not crash when a team is missing its optional description', async () => {
      // t2 ("Design") deliberately has no description — the filter must not
      // call .toLowerCase() on undefined.
      render(<TeamsIntegration />);

      await settleData(/Engineering/);

      expect(screen.getByText('Design')).toBeInTheDocument();
      fireEvent.change(screen.getByPlaceholderText(/search teams/i), {
        target: { value: 'design' },
      });
      await waitFor(() => {
        expect(screen.getByText('Design')).toBeInTheDocument();
      });
      expect(screen.queryByText('Engineering')).not.toBeInTheDocument();
    });
  });

  describe('Channels tab', () => {
    test('shows empty state when no team is selected', async () => {
      render(<TeamsIntegration />);

      await settleData(/Engineering/);

      await userEvent.click(screen.getByRole('button', { name: /channels/i }));

      expect(screen.getByText('Select a team to view channels')).toBeInTheDocument();
    });

    test('loads and displays channels for the selected team', async () => {
      const user = userEvent.setup();
      render(<TeamsIntegration />);

      await settleData(/Engineering/);
      await selectTeamByCard(user, 'Engineering');

      await user.click(screen.getByRole('button', { name: /channels/i }));

      await waitFor(() => {
        expect(screen.getByText('General')).toBeInTheDocument();
        expect(screen.getByText('Frontend')).toBeInTheDocument();
      });
      // membership type + favorite badges
      expect(screen.getByText('standard')).toBeInTheDocument();
      expect(screen.getByText('private')).toBeInTheDocument();
      expect(screen.getByText('Favorite')).toBeInTheDocument();
      expect(screen.getByText('1 tabs')).toBeInTheDocument();
    });

    test('does not crash when a channel is missing its optional description', async () => {
      const user = userEvent.setup();
      render(<TeamsIntegration />);

      await settleData(/Engineering/);
      await selectTeamByCard(user, 'Engineering');
      await user.click(screen.getByRole('button', { name: /channels/i }));

      await waitFor(() => {
        expect(screen.getByText('Shared Links')).toBeInTheDocument();
      });
      // shared membership badge only renders for the description-less channel
      expect(screen.getByText('shared')).toBeInTheDocument();

      fireEvent.change(screen.getByPlaceholderText(/search channels/i), {
        target: { value: 'shared' },
      });
      await waitFor(() => {
        expect(screen.getByText('Shared Links')).toBeInTheDocument();
        expect(screen.queryByText('General')).not.toBeInTheDocument();
      });
    });

    test('create channel button is disabled without a selected team', async () => {
      render(<TeamsIntegration />);

      await settleData(/Engineering/);
      await userEvent.click(screen.getByRole('button', { name: /channels/i }));

      expect(
        screen.getByRole('button', { name: /create channel/i })
      ).toBeDisabled();
    });
  });

  describe('Messages tab', () => {
    test('shows empty state when no channel is selected', async () => {
      render(<TeamsIntegration />);

      await settleData(/Engineering/);

      await userEvent.click(screen.getByRole('button', { name: /messages/i }));

      expect(
        screen.getByText('Select a team and channel to view messages')
      ).toBeInTheDocument();
    });

    test('loads and displays messages for the selected channel', async () => {
      const user = userEvent.setup();
      render(<TeamsIntegration />);

      await settleData(/Engineering/);
      await selectTeamByCard(user, 'Engineering');
      await user.click(screen.getByRole('button', { name: /messages/i }));

      // Pick the channel from the Messages tab's channel select (the
      // placeholder is aria-hidden, so target the second combobox by index:
      // [team select, channel select])
      const comboboxes = screen.getAllByRole('combobox');
      await user.click(comboboxes[1]);
      const listbox = await screen.findByRole('listbox');
      await user.click(within(listbox).getByText('General'));

      await waitFor(() => {
        expect(screen.getByText('Hello from Alice')).toBeInTheDocument();
        expect(screen.getByText('Deploy completed')).toBeInTheDocument();
      });
      // importance badge + reaction badge + bot-message "?" avatar fallback
      expect(screen.getByText('high')).toBeInTheDocument();
      expect(screen.getByText('👍 Alice Johnson')).toBeInTheDocument();
      expect(screen.getByText('?')).toBeInTheDocument();
    });

    test('send message posts to the API and closes the dialog', async () => {
      const user = userEvent.setup();
      const fetchSpy = jest.spyOn(global, 'fetch');
      render(<TeamsIntegration />);

      await settleData(/Engineering/);
      await selectTeamByCard(user, 'Engineering');
      await user.click(screen.getByRole('button', { name: /messages/i }));
      const comboboxes = screen.getAllByRole('combobox');
      await user.click(comboboxes[1]);
      const listbox = await screen.findByRole('listbox');
      await user.click(within(listbox).getByText('General'));
      await waitFor(() => {
        expect(screen.getByText('Hello from Alice')).toBeInTheDocument();
      });

      await user.click(
        screen.getByRole('button', { name: /send message/i })
      );

      const dialogContent = document.getElementById('dialog-content') as HTMLElement;
      expect(dialogContent).toBeInTheDocument();

      await user.type(
        within(dialogContent).getByPlaceholderText(/type your message/i),
        'Ship it now'
      );

      // Mention Alice via the mentions select
      const dialogComboboxes = within(dialogContent).getAllByRole('combobox');
      await user.click(dialogComboboxes[1]);
      const mentionListbox = await screen.findByRole('listbox');
      await user.click(within(mentionListbox).getByText('Alice Johnson'));

      fetchSpy.mockClear();
      await user.click(
        within(dialogContent).getByRole('button', { name: /send message/i })
      );

      await waitFor(() => {
        expect(fetchSpy).toHaveBeenCalledWith(
          expect.stringContaining('/api/integrations/teams/messages/send'),
          expect.objectContaining({
            method: 'POST',
            body: expect.stringContaining('Ship it now'),
          })
        );
      });
      // mentions are serialized with the user displayName
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/integrations/teams/messages/send'),
        expect.objectContaining({
          body: expect.stringContaining('Alice Johnson'),
        })
      );
      // dialog closes on success
      await waitFor(() => {
        expect(
          screen.queryByRole('dialog')
        ).not.toBeInTheDocument();
      });
    });
  });

  describe('Meetings tab', () => {
    test('displays meetings with attendees, join button, and truncation', async () => {
      render(<TeamsIntegration />);

      await settleData(/Engineering/);
      await userEvent.click(screen.getByRole('button', { name: /meetings/i }));

      await waitFor(() => {
        expect(screen.getByText('Sprint Planning')).toBeInTheDocument();
        expect(screen.getByText('Kickoff')).toBeInTheDocument();
      });
      expect(screen.getByText('Online Meeting')).toBeInTheDocument();
      expect(
        screen.getByText((content) => content.includes('Zoom HQ'))
      ).toBeInTheDocument();
      // 4 attendees → 3 badges + "+1 more" (Dave Kim is the hidden 4th)
      expect(screen.getByText('Alice Johnson')).toBeInTheDocument();
      expect(screen.getByText('Carol Lee')).toBeInTheDocument();
      expect(screen.getByText('+1 more')).toBeInTheDocument();
      // long body is truncated with an ellipsis
      expect(
        screen.getByText((content) => content.includes('...'))
      ).toBeInTheDocument();
      // join button for online meetings
      expect(
        screen.getByRole('button', { name: /join meeting/i })
      ).toBeInTheDocument();
    });

    test('renders empty meetings state without crashing', async () => {
      server.use(
        rest.post('/api/integrations/teams/meetings', (req, res, ctx) => {
          return res(ctx.status(200), ctx.json({ data: { meetings: [] } }));
        })
      );

      render(<TeamsIntegration />);

      await settleData(/Engineering/);
      await userEvent.click(screen.getByRole('button', { name: /meetings/i }));

      expect(
        screen.queryByText('Sprint Planning')
      ).not.toBeInTheDocument();
      // stats reflect the empty list without crashing
      expect(screen.getAllByText('0').length).toBeGreaterThan(0);
    });

    test('schedule meeting posts to the API', async () => {
      const user = userEvent.setup();
      const fetchSpy = jest.spyOn(global, 'fetch');
      render(<TeamsIntegration />);

      await settleData(/Engineering/);
      await user.click(screen.getByRole('button', { name: /meetings/i }));

      await user.click(
        screen.getByRole('button', { name: /schedule meeting/i })
      );
      const dialogContent = document.getElementById('dialog-content') as HTMLElement;

      await user.type(
        within(dialogContent).getByPlaceholderText('Meeting subject'),
        'Sprint Planning'
      );
      await user.type(
        within(dialogContent).getByPlaceholderText(/enter email addresses/i),
        'alice@example.com, bob@example.com'
      );
      const dateInputs = dialogContent.querySelectorAll('input[type="datetime-local"]');
      fireEvent.change(dateInputs[0], { target: { value: '2026-09-01T09:00' } });
      fireEvent.change(dateInputs[1], { target: { value: '2026-09-01T10:00' } });

      fetchSpy.mockClear();
      await user.click(
        within(dialogContent).getByRole('button', { name: /schedule meeting/i })
      );

      await waitFor(() => {
        expect(fetchSpy).toHaveBeenCalledWith(
          expect.stringContaining('/api/integrations/teams/meetings/create'),
          expect.objectContaining({
            method: 'POST',
            body: expect.stringContaining('Sprint Planning'),
          })
        );
      });
      const bodyCall = fetchSpy.mock.calls.find(([url]) =>
        String(url).includes('/api/integrations/teams/meetings/create')
      );
      const body = String(bodyCall![1]!.body);
      expect(body).toContain('alice@example.com');
      expect(body).toContain('"name":"alice"');
      expect(body).toContain('"isOnlineMeeting":true');
    });
  });

  describe('Users tab', () => {
    test('displays users with status badges and details', async () => {
      render(<TeamsIntegration />);

      await settleData(/Engineering/);
      await userEvent.click(screen.getByRole('button', { name: /users/i }));

      await waitFor(() => {
        expect(screen.getByText('Alice Johnson')).toBeInTheDocument();
        expect(screen.getByText('Bob Smith')).toBeInTheDocument();
      });
      expect(screen.getByText('Active')).toBeInTheDocument();
      expect(screen.getByText('Inactive')).toBeInTheDocument();
      expect(screen.getByText('alice@example.com')).toBeInTheDocument();
      expect(screen.getByText('bob@example.com')).toBeInTheDocument(); // UPN fallback
      expect(screen.getByText('Engineer')).toBeInTheDocument();
      expect(screen.getByText('Engineering')).toBeInTheDocument();
      expect(screen.getByText('📍 San Francisco')).toBeInTheDocument();
    });
  });

  describe('Create flows', () => {
    test('creates a team through the create-team dialog', async () => {
      const user = userEvent.setup();
      const fetchSpy = jest.spyOn(global, 'fetch');
      render(<TeamsIntegration />);

      await settleData(/Engineering/);

      await user.click(
        screen.getByRole('button', { name: /create team/i })
      );
      const dialogContent = document.getElementById('dialog-content') as HTMLElement;

      await user.type(
        within(dialogContent).getByPlaceholderText(/enter team name/i),
        'New Project Team'
      );
      await user.type(
        within(dialogContent).getByPlaceholderText(/team description/i),
        'A brand new team'
      );

      fetchSpy.mockClear();
      await user.click(
        within(dialogContent).getByRole('button', { name: /create team/i })
      );

      await waitFor(() => {
        expect(fetchSpy).toHaveBeenCalledWith(
          expect.stringContaining('/api/integrations/teams/teams/create'),
          expect.objectContaining({
            method: 'POST',
            body: expect.stringContaining('New Project Team'),
          })
        );
      });
      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });

    test('create team is disabled until a name is entered', async () => {
      const user = userEvent.setup();
      render(<TeamsIntegration />);

      await settleData(/Engineering/);

      await user.click(
        screen.getByRole('button', { name: /create team/i })
      );
      const dialogContent = document.getElementById('dialog-content') as HTMLElement;

      expect(
        within(dialogContent).getByRole('button', { name: /create team/i })
      ).toBeDisabled();

      await user.type(
        within(dialogContent).getByPlaceholderText(/enter team name/i),
        'X'
      );
      expect(
        within(dialogContent).getByRole('button', { name: /create team/i })
      ).toBeEnabled();
    });

    test('creates a channel for the selected team', async () => {
      const user = userEvent.setup();
      const fetchSpy = jest.spyOn(global, 'fetch');
      render(<TeamsIntegration />);

      await settleData(/Engineering/);
      await selectTeamByCard(user, 'Engineering');
      await user.click(screen.getByRole('button', { name: /channels/i }));

      await user.click(
        screen.getByRole('button', { name: /create channel/i })
      );
      const dialogContent = document.getElementById('dialog-content') as HTMLElement;

      await user.type(
        within(dialogContent).getByPlaceholderText(/enter channel name/i),
        'Backend'
      );

      fetchSpy.mockClear();
      await user.click(
        within(dialogContent).getByRole('button', { name: /create channel/i })
      );

      await waitFor(() => {
        expect(fetchSpy).toHaveBeenCalledWith(
          expect.stringContaining('/api/integrations/teams/channels/create'),
          expect.objectContaining({
            method: 'POST',
            body: expect.stringContaining('Backend'),
          })
        );
      });
    });
  });
});

// ---------------------------------------------------------------------------
// Extended coverage: error paths, external links, badges, dialog selects
// ---------------------------------------------------------------------------
describe('TeamsIntegration (extended coverage)', () => {
  const user = userEvent.setup();
  // NOTE: jest.config.js sets restoreMocks:true, which detaches describe-scope
  // spies after every test — create a fresh console.error spy per test.
  let errorSpy: jest.SpyInstance;
  beforeEach(() => {
    errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...teamsHandlers);
  });
  afterEach(() => {
    errorSpy.mockRestore();
  });

  test('opens a team in Teams via the card button', async () => {
    const openSpy = jest.fn();
    window.open = openSpy as any;

    render(<TeamsIntegration />);
    await settleData(/Engineering/);

    const buttons = screen.getAllByRole('button', { name: /open in teams/i });
    fireEvent.click(buttons[0]);

    expect(openSpy).toHaveBeenCalledWith('https://teams.example.com/eng', '_blank');
  });

  test('joins a meeting via the Join Meeting button', async () => {
    const openSpy = jest.fn();
    window.open = openSpy as any;

    render(<TeamsIntegration />);
    await settleData(/Engineering/);

    await user.click(screen.getByRole('button', { name: /meetings/i }));
    const joinButtons = await screen.findAllByRole('button', { name: /join meeting/i });
    fireEvent.click(joinButtons[0]);

    expect(openSpy).toHaveBeenCalledWith('https://teams.example.com/join/123', '_blank');
  });

  test('channels tab renders membership badges and selects a channel', async () => {
    render(<TeamsIntegration />);
    await settleData(/Engineering/);
    await selectTeamByCard(user, 'Engineering');

    await user.click(screen.getByRole('button', { name: /channels/i }));

    expect(await screen.findByText('General')).toBeInTheDocument();
    expect(screen.getByText('Frontend')).toBeInTheDocument();
    expect(screen.getByText('Shared Links')).toBeInTheDocument();
    expect(screen.getAllByText('standard').length).toBeGreaterThan(0);
    expect(screen.getAllByText('private').length).toBeGreaterThan(0);
    expect(screen.getByText('shared')).toBeInTheDocument();
    expect(screen.getByText('Favorite')).toBeInTheDocument();

    // clicking a channel card selects it (Messages tab becomes usable)
    await user.click(screen.getByText('Frontend'));
    await user.click(screen.getByRole('button', { name: /messages/i }));
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /send message/i })
      ).toBeInTheDocument();
    });
  });

  test('renders specialization badges for education teams', async () => {
    server.use(
      rest.post('/api/integrations/teams/teams', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            data: {
              teams: [
                {
                  id: 't1',
                  displayName: 'Science Class',
                  createdDateTime: '2026-01-15T10:00:00Z',
                  visibility: 'public',
                  specialization: 'educationStandard',
                  webUrl: 'https://teams.example.com/science',
                },
                {
                  id: 't2',
                  displayName: 'Teacher Training',
                  createdDateTime: '2026-01-16T10:00:00Z',
                  visibility: 'public',
                  specialization: 'educationProfessionalLearning',
                  webUrl: 'https://teams.example.com/training',
                },
              ],
            },
          })
        );
      })
    );

    render(<TeamsIntegration />);
    await settleData(/Science Class/);

    expect(screen.getByText('Teacher Training')).toBeInTheDocument();
    expect(screen.getAllByText(/educationStandard/i).length).toBeGreaterThan(0);
    expect(
      screen.getAllByText(/educationProfessionalLearning/i).length
    ).toBeGreaterThan(0);
  });

  test('shows error toast when team creation fails', async () => {
    server.use(
      rest.post('/api/integrations/teams/teams/create', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<TeamsIntegration />);
    await settleData(/Engineering/);

    await user.click(screen.getByRole('button', { name: /create team/i }));
    const dialogContent = document.getElementById('dialog-content') as HTMLElement;
    await user.type(within(dialogContent).getByPlaceholderText(/team name/i), 'Fail Team');
    await user.click(within(dialogContent).getByRole('button', { name: /create team/i }));

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', description: 'Failed to create team' })
      );
    });
  });

  test('shows error toast when channel creation fails', async () => {
    server.use(
      rest.post('/api/integrations/teams/channels/create', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<TeamsIntegration />);
    await settleData(/Engineering/);
    await selectTeamByCard(user, 'Engineering');
    await user.click(screen.getByRole('button', { name: /channels/i }));

    await user.click(screen.getByRole('button', { name: /create channel/i }));
    const dialogContent = document.getElementById('dialog-content') as HTMLElement;
    await user.type(
      within(dialogContent).getByPlaceholderText(/enter channel name/i),
      'Fail Channel'
    );
    await user.click(
      within(dialogContent).getByRole('button', { name: /create channel/i })
    );

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', description: 'Failed to create channel' })
      );
    });
  });

  test('shows error toast when sending a message fails', async () => {
    server.use(
      rest.post('/api/integrations/teams/messages/send', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<TeamsIntegration />);
    await settleData(/Engineering/);
    await selectTeamByCard(user, 'Engineering');
    await user.click(screen.getByRole('button', { name: /messages/i }));
    const comboboxes = screen.getAllByRole('combobox');
    await user.click(comboboxes[1]);
    const listbox = await screen.findByRole('listbox');
    await user.click(within(listbox).getByText('General'));

    await user.click(screen.getByRole('button', { name: /send message/i }));
    const dialogContent = document.getElementById('dialog-content') as HTMLElement;
    await user.type(
      within(dialogContent).getByPlaceholderText(/type your message/i),
      'Doomed message'
    );
    await user.click(
      within(dialogContent).getByRole('button', { name: /send message/i })
    );

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', description: 'Failed to send message' })
      );
    });
  });

  test('shows error toast when meeting creation fails', async () => {
    server.use(
      rest.post('/api/integrations/teams/meetings/create', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<TeamsIntegration />);
    await settleData(/Engineering/);
    await user.click(screen.getByRole('button', { name: /meetings/i }));

    await user.click(screen.getByRole('button', { name: /schedule meeting/i }));
    const dialogContent = document.getElementById('dialog-content') as HTMLElement;
    await user.type(
      within(dialogContent).getByPlaceholderText('Meeting subject'),
      'Doomed Meeting'
    );
    const dateInputs = dialogContent.querySelectorAll('input[type="datetime-local"]');
    fireEvent.change(dateInputs[0], { target: { value: '2026-09-01T09:00' } });
    fireEvent.change(dateInputs[1], { target: { value: '2026-09-01T10:00' } });
    await user.click(
      within(dialogContent).getByRole('button', { name: /schedule meeting/i })
    );

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', description: 'Failed to create meeting' })
      );
    });
  });

  test('shows error toast when team loading fails and logs auxiliary errors', async () => {
    const netFail = (path: string) => rest.post(path, (req, res) => res.networkError('boom'));
    server.use(
      netFail('/api/integrations/teams/teams'),
      netFail('/api/integrations/teams/profile'),
      netFail('/api/integrations/teams/meetings'),
      netFail('/api/integrations/teams/users')
    );

    render(<TeamsIntegration />);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', description: 'Failed to load teams from Microsoft Teams' })
      );
    });
    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Failed to load user profile:', expect.anything());
      expect(errorSpy).toHaveBeenCalledWith('Failed to load meetings:', expect.anything());
      expect(errorSpy).toHaveBeenCalledWith('Failed to load users:', expect.anything());
    });
  });

  test('logs an error when messages fail to load for a selected channel', async () => {
    server.use(
      rest.post('/api/integrations/teams/messages', (req, res) => res.networkError('boom'))
    );

    render(<TeamsIntegration />);
    await settleData(/Engineering/);
    await selectTeamByCard(user, 'Engineering');

    await user.click(screen.getByRole('button', { name: /channels/i }));
    // messages only load after a channel is selected
    await user.click(await screen.findByText('General'));

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Failed to load messages:', expect.anything());
    });
  });

  test('dialog selects update visibility, specialization, and membership type', async () => {
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

    // --- Create Team dialog: visibility + specialization selects ---
    render(<TeamsIntegration />);
    await settleData(/Engineering/);

    await user.click(screen.getByRole('button', { name: /create team/i }));
    let dialogContent = document.getElementById('dialog-content') as HTMLElement;
    await user.type(within(dialogContent).getByPlaceholderText(/team name/i), 'Selects Team');

    const teamComboboxes = within(dialogContent).getAllByRole('combobox');
    await pickOption(teamComboboxes[0], 'Private');
    await pickOption(teamComboboxes[1], 'None');

    await user.click(within(dialogContent).getByRole('button', { name: /create team/i }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    // --- Create Channel dialog: description + membership type ---
    await selectTeamByCard(user, 'Engineering');
    await user.click(screen.getByRole('button', { name: /channels/i }));
    await user.click(screen.getByRole('button', { name: /create channel/i }));
    dialogContent = document.getElementById('dialog-content') as HTMLElement;
    await user.type(
      within(dialogContent).getByPlaceholderText(/enter channel name/i),
      'Selects Channel'
    );
    fireEvent.change(within(dialogContent).getByPlaceholderText('Channel description'), {
      target: { value: 'A very select channel' },
    });
    const channelComboboxes = within(dialogContent).getAllByRole('combobox');
    await pickOption(channelComboboxes[channelComboboxes.length - 1], 'Private');

    await user.click(
      within(dialogContent).getByRole('button', { name: /create channel/i })
    );
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Extended coverage part 2: full dialog fields, tab searches, variant
// defaults, empty-form guards, and channel load errors
// ---------------------------------------------------------------------------
describe('TeamsIntegration (extended coverage 2)', () => {
  const user = userEvent.setup();
  let errorSpy: jest.SpyInstance;
  let openSpy: jest.Mock;

  beforeEach(() => {
    errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    openSpy = jest.fn();
    window.open = openSpy as any;
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...teamsHandlers);
  });
  afterEach(() => {
    errorSpy.mockRestore();
  });

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

  const dialogEl = () => document.getElementById('dialog-content') as HTMLElement;

  test('fills every create-team dialog field and submits', async () => {
    render(<TeamsIntegration />);
    await settleData(/Engineering/);

    await user.click(screen.getByRole('button', { name: /create team/i }));
    const dialog = dialogEl();

    await user.type(within(dialog).getByPlaceholderText(/enter team name/i), 'Full Form Team');
    fireEvent.change(within(dialog).getByPlaceholderText('Team description'), {
      target: { value: 'Description text' },
    });
    const comboboxes = within(dialog).getAllByRole('combobox');
    await pickOption(comboboxes[0], 'Public');
    await pickOption(comboboxes[1], 'Education Staff');
    fireEvent.change(within(dialog).getByPlaceholderText('Team classification'), {
      target: { value: 'Confidential',
      },
    } as any);

    await user.click(within(dialog).getByRole('button', { name: /create team/i }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  test('cancels the create-team dialog', async () => {
    render(<TeamsIntegration />);
    await settleData(/Engineering/);

    await user.click(screen.getByRole('button', { name: /create team/i }));
    const dialog = dialogEl();
    await user.click(within(dialog).getByRole('button', { name: /cancel/i }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  test('toggles favorite-by-default and cancels the create-channel dialog', async () => {
    render(<TeamsIntegration />);
    await settleData(/Engineering/);
    await selectTeamByCard(user, 'Engineering');

    await user.click(screen.getByRole('button', { name: /channels/i }));
    await user.click(screen.getByRole('button', { name: /create channel/i }));
    const dialog = dialogEl();

    await user.type(within(dialog).getByPlaceholderText(/enter channel name/i), 'Fav Channel');
    fireEvent.click(within(dialog).getByLabelText(/favorite by default/i));

    await user.click(within(dialog).getByRole('button', { name: /cancel/i }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  test('opens the channel web url from the channels tab', async () => {
    render(<TeamsIntegration />);
    await settleData(/Engineering/);
    await selectTeamByCard(user, 'Engineering');

    await user.click(screen.getByRole('button', { name: /channels/i }));
    const openButtons = await screen.findAllByRole('button', { name: /open in teams/i });
    fireEvent.click(openButtons[0]);
    expect(openSpy).toHaveBeenCalled();
  });

  test('switches teams via the channels tab team select', async () => {
    render(<TeamsIntegration />);
    await settleData(/Engineering/);
    await selectTeamByCard(user, 'Engineering');

    await user.click(screen.getByRole('button', { name: /channels/i }));
    expect(await screen.findByText('General')).toBeInTheDocument();

    // The team select in the Channels tab re-runs the channel load.
    const fetchSpy = jest.spyOn(global, 'fetch');
    fetchSpy.mockClear();
    const trigger = screen.getAllByRole('combobox')[0];
    await pickOption(trigger, 'Design');
    await waitFor(() => {
      const call = fetchSpy.mock.calls.find(([u]: any) =>
        String(u).includes('/api/integrations/teams/channels')
      );
      expect(call).toBeDefined();
      expect(String((call as any)[1].body)).toContain('"team_id":"t2"');
    });
  });

  test('search inputs on messages, meetings, and users tabs accept typing', async () => {
    render(<TeamsIntegration />);
    await settleData(/Engineering/);
    await selectTeamByCard(user, 'Engineering');

    // Messages tab
    await user.click(screen.getByRole('button', { name: /messages/i }));
    const msgSearch = screen.getByPlaceholderText(/search messages/i);
    fireEvent.change(msgSearch, { target: { value: 'standup' } });
    expect((msgSearch as HTMLInputElement).value).toBe('standup');

    // Meetings tab
    await user.click(screen.getByRole('button', { name: /meetings/i }));
    const mtgSearch = screen.getByPlaceholderText(/search meetings/i);
    fireEvent.change(mtgSearch, { target: { value: 'sync' } });
    expect((mtgSearch as HTMLInputElement).value).toBe('sync');

    // Users tab
    await user.click(screen.getByRole('button', { name: /users/i }));
    const userSearch = screen.getByPlaceholderText(/search users/i);
    fireEvent.change(userSearch, { target: { value: 'rushi' } });
    expect((userSearch as HTMLInputElement).value).toBe('rushi');
  });

  test('meeting dialog: fills description, toggles online meeting, cancels; empty submit posts nothing', async () => {
    const fetchSpy = jest.spyOn(global, 'fetch');
    render(<TeamsIntegration />);
    await settleData(/Engineering/);

    await user.click(screen.getByRole('button', { name: /meetings/i }));
    await user.click(screen.getByRole('button', { name: /schedule meeting|create meeting/i }));

    const dialog = dialogEl();
    // Empty form: submit is a no-op
    await user.click(within(dialog).getAllByRole('button').slice(-1)[0]);
    expect(
      fetchSpy.mock.calls.some(([u, i]: any) => String(u).includes('/meetings/create'))
    ).toBe(false);

    fireEvent.change(within(dialog).getByPlaceholderText('Meeting subject'), {
      target: { value: 'Subject' },
    });
    fireEvent.change(within(dialog).getByPlaceholderText('Meeting description'), {
      target: { value: 'Desc' },
    });
    fireEvent.click(within(dialog).getByLabelText(/online meeting/i));

    await user.click(within(dialog).getByRole('button', { name: /cancel/i }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  test('message dialog: picks importance and mentions, then cancels', async () => {
    render(<TeamsIntegration />);
    await settleData(/Engineering/);
    await selectTeamByCard(user, 'Engineering');

    await user.click(screen.getByRole('button', { name: /channels/i }));
    await user.click(await screen.findByText('General'));
    await user.click(screen.getByRole('button', { name: /messages/i }));
    await user.click(screen.getByRole('button', { name: /send message/i }));

    const dialog = dialogEl();
    fireEvent.change(within(dialog).getByPlaceholderText(/type your message/i), {
      target: { value: 'Hello' },
    });
    const comboboxes = within(dialog).getAllByRole('combobox');
    await pickOption(comboboxes[0], 'Low');

    await user.click(within(dialog).getByRole('button', { name: /cancel/i }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  test('renders default visibility/membership variants and low-importance messages', async () => {
    server.use(
      rest.post('/api/integrations/teams/teams', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            data: {
              teams: [
                {
                  id: 't1',
                  displayName: 'Odd Visibility Team',
                  createdDateTime: '2026-01-15T10:00:00Z',
                  visibility: 'unknownMode',
                  webUrl: 'https://teams.example.com/odd',
                },
              ],
            },
          })
        );
      }),
      rest.post('/api/integrations/teams/channels', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            data: {
              channels: [
                {
                  id: 'ch1',
                  displayName: 'Odd Channel',
                  description: 'd',
                  membershipType: 'otherType',
                  isFavoriteByDefault: false,
                  webUrl: 'https://teams.example.com/ch1',
                },
              ],
            },
          })
        );
      }),
      rest.post('/api/integrations/teams/messages', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            data: {
              messages: [
                {
                  id: 'msg1',
                  body: { content: 'Low importance note' },
                  importance: 'low',
                  createdDateTime: '2026-01-15T10:00:00Z',
                  from: { user: { displayName: 'Rushi' } },
                },
                {
                  id: 'msg2',
                  body: { content: 'No importance note' },
                  createdDateTime: '2026-01-15T11:00:00Z',
                  from: { user: { displayName: 'Rushi' } },
                },
              ],
            },
          })
        );
      })
    );

    render(<TeamsIntegration />);
    await settleData(/Odd Visibility Team/);
    await selectTeamByCard(user, 'Odd Visibility Team');

    await user.click(screen.getByRole('button', { name: /channels/i }));
    expect(await screen.findByText('Odd Channel')).toBeInTheDocument();

    await user.click(screen.getByText('Odd Channel'));
    await user.click(screen.getByRole('button', { name: /messages/i }));
    expect(await screen.findByText('Low importance note')).toBeInTheDocument();
    expect(screen.getByText('No importance note')).toBeInTheDocument();
  });

  test('logs an error when channel loading fails', async () => {
    server.use(
      rest.post('/api/integrations/teams/channels', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<TeamsIntegration />);
    await settleData(/Engineering/);
    await selectTeamByCard(user, 'Engineering');

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Failed to load channels:', expect.anything());
    });
  });
});

describe('TeamsIntegration (extended coverage 3)', () => {
  const user = userEvent.setup();
  let errorSpy: jest.SpyInstance;

  beforeEach(() => {
    errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...teamsHandlers);
  });
  afterEach(() => {
    errorSpy.mockRestore();
  });

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

  test('renders notResponded/default attendee statuses and unknown importance', async () => {
    server.use(
      rest.post('/api/integrations/teams/meetings', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            data: {
              meetings: [
                {
                  id: 'mx1',
                  subject: 'Status Meeting',
                  body: { contentType: 'text', content: 'd' },
                  start: { dateTime: '2026-09-01T09:00:00Z', timeZone: 'UTC' },
                  end: { dateTime: '2026-09-01T10:00:00Z', timeZone: 'UTC' },
                  attendees: [
                    {
                      type: 'required',
                      status: { response: 'notResponded', time: '2026-08-01T09:00:00Z' },
                      emailAddress: { name: 'Dan Pate', address: 'dan@example.com' },
                    },
                    {
                      type: 'required',
                      status: { response: 'none', time: '2026-08-01T09:00:00Z' },
                      emailAddress: { name: 'Eve Quant', address: 'eve@example.com' },
                    },
                  ],
                },
              ],
            },
          })
        );
      }),
      rest.post('/api/integrations/teams/messages', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            data: {
              messages: [
                {
                  id: 'msgx',
                  body: { content: 'Urgent flag message' },
                  importance: 'urgent',
                  createdDateTime: '2026-01-15T10:00:00Z',
                  from: { user: { displayName: 'Rushi' } },
                },
              ],
            },
          })
        );
      })
    );

    render(<TeamsIntegration />);
    await screen.findByText('Connected', {}, { timeout: 3000 });

    await user.click(screen.getByRole('button', { name: /meetings/i }));
    expect(await screen.findByText('Status Meeting', {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getByText('Dan Pate')).toBeInTheDocument();
    expect(screen.getByText('Eve Quant')).toBeInTheDocument();

    // Messages: unknown importance falls through to the default badge variant.
    // `exact: true` is the role-query default; cast options since the installed
    // @testing-library/dom types predate the `exact` flag.
    await user.click(screen.getByRole('button', { name: 'Teams', exact: true } as any));
    await selectTeamByCard(user, 'Engineering');
    await user.click(screen.getByRole('button', { name: /channels/i }));
    await user.click(await screen.findByText('General'));
    await user.click(screen.getByRole('button', { name: /messages/i }));
    expect(await screen.findByText('Urgent flag message')).toBeInTheDocument();
    expect(screen.getByText('urgent')).toBeInTheDocument();

    // Messages tab team select resets the current channel.
    const trigger = screen.getAllByRole('combobox')[0];
    await pickOption(trigger, 'Design');
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /send message/i })
      ).toBeInTheDocument();
    });
  });
});
