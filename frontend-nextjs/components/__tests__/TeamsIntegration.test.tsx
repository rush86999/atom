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
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

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
  rest.get('/api/integrations/teams/health', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ status: 'healthy' }));
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
    rest.get('/api/integrations/teams/health', (req, res, ctx) => {
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
        rest.get('/api/integrations/teams/health', (req, res, ctx) => {
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
        rest.get('/api/integrations/teams/health', (req, res) => {
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
      await waitFor(() => {
        expect(fetchSpy).toHaveBeenCalledWith(
          expect.stringContaining('/api/integrations/teams/health')
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
