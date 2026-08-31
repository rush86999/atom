/**
 * Microsoft365Integration Component Tests
 *
 * Tests verify the real Microsoft 365 integration component:
 * - Health check / connection state
 * - OAuth connect flow
 * - Profile, email, calendar event, and team data loading
 * - Email search filtering and compose-email dialog
 * - Calendar tab flows (render, search, create event, delete event)
 * - Delete flows (email/event) with confirmation
 * - Automation tab actions (Excel / Outlook / OneDrive / Teams)
 * - Webhook subscription flows
 * - Crash-safety on partial API data (draft email without sender, team
 *   without description)
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/Microsoft365Integration.tsx
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
import Microsoft365Integration from '@/components/Microsoft365Integration';
import { useToast } from '@/components/ui/use-toast';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const getToastMock = (): jest.Mock => (useToast as jest.Mock)().toast;

const m365Handlers = [
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ providers: { microsoft365: { connected: true, source: 'user_connection' } } })
    );
  }),
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ providers: { microsoft365: { connected: true, source: 'user_connection' } } }));
  }),

  rest.get('/api/integrations/microsoft365/user', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          profile: {
            id: 'u1',
            displayName: 'Rushi Parikh',
            jobTitle: 'Engineer',
            userPrincipalName: 'rushi@example.com',
          },
        },
      })
    );
  }),

  rest.get('/api/integrations/microsoft365/outlook/messages', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        messages: [
          {
            id: 'e1',
            subject: 'Hello World',
            from: { emailAddress: { name: 'Alice', address: 'alice@example.com' } },
            sender: { emailAddress: { name: 'Alice', address: 'alice@example.com' } },
            bodyPreview: 'Preview of the email',
            isRead: false,
            receivedDateTime: '2024-01-15T10:00:00Z',
          },
          {
            id: 'e2',
            subject: 'Q3 Planning',
            from: { emailAddress: { name: 'Bob', address: 'bob@example.com' } },
            sender: { emailAddress: { name: 'Bob', address: 'bob@example.com' } },
            bodyPreview: 'Planning doc attached',
            isRead: true,
            receivedDateTime: '2024-01-14T10:00:00Z',
          },
          {
            // Draft email: the Graph API leaves `sender` null for drafts.
            // The email list + search filter must not crash on it.
            id: 'e3',
            subject: 'Draft Note',
            from: { emailAddress: { name: '', address: '' } },
            bodyPreview: 'Unsent draft',
            isRead: false,
            receivedDateTime: '2024-01-16T10:00:00Z',
          },
        ],
      })
    );
  }),

  rest.get('/api/integrations/microsoft365/calendar/events', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        events: [
          {
            id: 'ev1',
            subject: 'Team Standup',
            start: { dateTime: '2024-01-15T09:00:00Z' },
            end: { dateTime: '2024-01-15T09:30:00Z' },
          },
          {
            id: 'ev2',
            subject: 'All-hands Sync',
            body: {
              contentType: 'text',
              content: 'Quarterly all-hands with product updates',
            },
            start: { dateTime: '2026-09-15T09:00:00Z' },
            end: { dateTime: '2026-09-15T10:30:00Z' },
            location: { displayName: 'Main Auditorium' },
            attendees: [
              {
                type: 'required',
                status: { response: 'accepted', time: '2026-09-01T09:00:00Z' },
                emailAddress: { name: 'Eve Adams', address: 'eve@example.com' },
              },
              {
                type: 'required',
                status: { response: 'accepted', time: '2026-09-01T09:00:00Z' },
                emailAddress: { name: 'Frank Lee', address: 'frank@example.com' },
              },
              {
                type: 'required',
                status: { response: 'tentative', time: '2026-09-01T09:00:00Z' },
                emailAddress: { name: 'Grace Wu', address: 'grace@example.com' },
              },
              {
                type: 'required',
                status: { response: 'notResponded', time: '2026-09-01T09:00:00Z' },
                emailAddress: { name: 'Hank Ito', address: 'hank@example.com' },
              },
            ],
            organizer: { emailAddress: { name: 'Rushi Parikh', address: 'rushi@example.com' } },
            isOnlineMeeting: true,
            onlineMeetingUrl: 'https://teams.example.com/join/abc',
            createdDateTime: '2026-09-01T09:00:00Z',
            lastModifiedDateTime: '2026-09-01T09:00:00Z',
          },
        ],
      })
    );
  }),

  rest.get('/api/integrations/microsoft365/teams', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        teams: [
          { id: 't1', displayName: 'Engineering', description: 'Core engineering team' },
          { id: 't2', displayName: 'Design', description: 'Design team' },
          // Graph returns `description` as nullable — the search filter must
          // tolerate its absence.
          { id: 't3', displayName: 'Data' },
        ],
      })
    );
  }),

  rest.post('/api/integrations/microsoft365/emails/send', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),

  rest.post('/api/integrations/microsoft365/calendars/create', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),

  rest.post('/api/integrations/microsoft365/subscriptions', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),

  rest.delete('/api/integrations/microsoft365/outlook/messages/:id', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),

  rest.delete('/api/integrations/microsoft365/calendar/events/:id', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),

  rest.post('/api/integrations/microsoft365/excel/execute', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),

  rest.post('/api/integrations/microsoft365/outlook/execute', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),

  rest.post('/api/integrations/microsoft365/onedrive/execute', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),

  rest.post('/api/integrations/microsoft365/teams/execute', (req, res, ctx) => {
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

describe('Microsoft365Integration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...m365Handlers);
  });

  // Test 1: renders component
  test('renders component', () => {
    render(<Microsoft365Integration />);

    expect(
      screen.getByRole('heading', { name: /microsoft 365 integration/i })
    ).toBeInTheDocument();
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    setDisconnected();

    render(<Microsoft365Integration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect microsoft 365 account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 3: connect button is clickable without crashing (jsdom logs the
  // navigation attempt; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setDisconnected();

    render(<Microsoft365Integration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect microsoft 365 account/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 4: shows connected state when health check passes
  test('shows connected state when health check passes', async () => {
    render(<Microsoft365Integration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 5: displays user profile after connection
  test('displays user profile after connection', async () => {
    render(<Microsoft365Integration />);

    await waitFor(() => {
      expect(screen.getByText('Rushi Parikh')).toBeInTheDocument();
    });
  });

  // Test 6: displays emails in the default Outlook tab
  test('displays emails in the default Outlook tab', async () => {
    render(<Microsoft365Integration />);

    await waitFor(() => {
      expect(screen.getByText('Hello World')).toBeInTheDocument();
      expect(screen.getByText('Q3 Planning')).toBeInTheDocument();
    });
  });

  // Test 7: filters emails by search query
  test('filters emails by search query', async () => {
    render(<Microsoft365Integration />);

    await settleData(/Hello World/);

    const searchInput = screen.getByPlaceholderText(/search emails/i);
    fireEvent.change(searchInput, { target: { value: 'Q3' } });

    await waitFor(() => {
      expect(screen.getByText('Q3 Planning')).toBeInTheDocument();
    });
    expect(screen.queryByText('Hello World')).not.toBeInTheDocument();
  });

  // Test 8: opens compose email dialog
  test('opens compose email dialog', async () => {
    render(<Microsoft365Integration />);

    const composeButton = await screen.findByRole('button', {
      name: /compose email/i,
    });
    fireEvent.click(composeButton);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  // Test 9: displays teams on the Teams tab
  test('displays teams on the Teams tab', async () => {
    render(<Microsoft365Integration />);

    await settleData(/Hello World/);

    const teamsTab = screen.getByRole('button', { name: 'Teams' });
    fireEvent.click(teamsTab);

    await waitFor(() => {
      expect(screen.getByText('Engineering')).toBeInTheDocument();
      expect(screen.getByText('Design')).toBeInTheDocument();
    });
  });

  // Test 10: handles connection error
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/integrations/connection-status', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<Microsoft365Integration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect microsoft 365 account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 11: shows refresh status button
  test('shows refresh status button', async () => {
    render(<Microsoft365Integration />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh status/i })).toBeInTheDocument();
    });
  });

  // Test 12: calendar tab renders events with details
  test('displays calendar events on the Calendar tab', async () => {
    render(<Microsoft365Integration />);

    await settleData(/Hello World/);

    fireEvent.click(screen.getByRole('button', { name: /calendar/i }));

    await waitFor(() => {
      expect(screen.getByText('Team Standup')).toBeInTheDocument();
      expect(screen.getByText('All-hands Sync')).toBeInTheDocument();
    });
    expect(screen.getByText('Online Meeting')).toBeInTheDocument();
    expect(
      screen.getByText((content) => content.includes('Main Auditorium'))
    ).toBeInTheDocument();
    // 4 attendees → 3 badges + "+1 more" (Hank Ito is the hidden 4th)
    expect(screen.getByText('Eve Adams')).toBeInTheDocument();
    expect(screen.getByText('Grace Wu')).toBeInTheDocument();
    expect(screen.getByText('+1 more')).toBeInTheDocument();
  });

  // Test 13: filters calendar events by search query
  test('filters calendar events by search query', async () => {
    render(<Microsoft365Integration />);

    await settleData(/Hello World/);

    fireEvent.click(screen.getByRole('button', { name: /calendar/i }));
    await waitFor(() => {
      expect(screen.getByText('Team Standup')).toBeInTheDocument();
    });

    fireEvent.change(
      screen.getByPlaceholderText(/search calendar events/i),
      { target: { value: 'all-hands' } }
    );

    await waitFor(() => {
      expect(screen.getByText('All-hands Sync')).toBeInTheDocument();
    });
    expect(screen.queryByText('Team Standup')).not.toBeInTheDocument();
  });

  // Test 14: filters teams by search query
  test('filters teams by search query', async () => {
    render(<Microsoft365Integration />);

    await settleData(/Hello World/);

    fireEvent.click(screen.getByRole('button', { name: 'Teams' }));
    await waitFor(() => {
      expect(screen.getByText('Engineering')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText(/search teams/i), {
      target: { value: 'eng' },
    });

    await waitFor(() => {
      expect(screen.getByText('Engineering')).toBeInTheDocument();
    });
    expect(screen.queryByText('Design')).not.toBeInTheDocument();
  });

  // Test 15: draft email without a sender does not crash the email list
  test('renders draft emails without a sender without crashing', async () => {
    render(<Microsoft365Integration />);

    // The draft ("Draft Note") has no `sender` — the list and the search
    // filter must tolerate it
    await waitFor(() => {
      expect(screen.getByText('Draft Note')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText(/search emails/i), {
      target: { value: 'zzz' },
    });

    await waitFor(() => {
      expect(screen.queryByText('Hello World')).not.toBeInTheDocument();
    });
  });

  // Test 16: team without a description does not crash team search
  test('does not crash searching teams missing descriptions', async () => {
    render(<Microsoft365Integration />);

    await settleData(/Hello World/);

    fireEvent.click(screen.getByRole('button', { name: 'Teams' }));
    await waitFor(() => {
      expect(screen.getByText('Data')).toBeInTheDocument();
    });

    // 'zzz' matches nothing — the filter must still evaluate the
    // description-less "Data" team without throwing
    fireEvent.change(screen.getByPlaceholderText(/search teams/i), {
      target: { value: 'zzz' },
    });

    await waitFor(() => {
      expect(screen.queryByText('Engineering')).not.toBeInTheDocument();
    });
  });

  // Test 17: composes and sends an email
  test('sends an email through the compose dialog', async () => {
    const user = userEvent.setup();
    const fetchSpy = jest.spyOn(global, 'fetch');

    render(<Microsoft365Integration />);

    const composeButton = await screen.findByRole('button', {
      name: /compose email/i,
    });
    await user.click(composeButton);

    const dialogContent = document.getElementById('dialog-content') as HTMLElement;

    await user.type(
      within(dialogContent).getByPlaceholderText(/recipient@example.com/),
      'bob@example.com'
    );
    await user.type(
      within(dialogContent).getByPlaceholderText(/email subject/i),
      'Hello Bob'
    );
    await user.type(
      within(dialogContent).getByPlaceholderText(/your message/i),
      'Testing the send flow'
    );

    fetchSpy.mockClear();
    await user.click(
      within(dialogContent).getByRole('button', { name: /send email/i })
    );

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/integrations/microsoft365/emails/send'),
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('Hello Bob'),
        })
      );
    });
    const bodyCall = fetchSpy.mock.calls.find(([url]) =>
      String(url).includes('/api/integrations/microsoft365/emails/send')
    );
    expect(String(bodyCall![1]!.body)).toContain('bob@example.com');
    // dialog closes on success
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  // Test 18: send email stays disabled until all fields are filled
  test('send email is disabled until all fields are filled', async () => {
    const user = userEvent.setup();
    render(<Microsoft365Integration />);

    const composeButton = await screen.findByRole('button', {
      name: /compose email/i,
    });
    await user.click(composeButton);
    const dialogContent = document.getElementById('dialog-content') as HTMLElement;

    const sendButton = () =>
      within(dialogContent).getByRole('button', { name: /send email/i });

    expect(sendButton()).toBeDisabled();

    await user.type(
      within(dialogContent).getByPlaceholderText(/recipient@example.com/),
      'bob@example.com'
    );
    expect(sendButton()).toBeDisabled();

    await user.type(
      within(dialogContent).getByPlaceholderText(/email subject/i),
      'Subject'
    );
    expect(sendButton()).toBeDisabled();

    await user.type(
      within(dialogContent).getByPlaceholderText(/your message/i),
      'Body'
    );
    expect(sendButton()).toBeEnabled();
  });

  // Test 19: creates a calendar event
  test('creates a calendar event through the dialog', async () => {
    const user = userEvent.setup();
    const fetchSpy = jest.spyOn(global, 'fetch');

    render(<Microsoft365Integration />);

    await settleData(/Hello World/);
    fireEvent.click(screen.getByRole('button', { name: /calendar/i }));

    await user.click(
      await screen.findByRole('button', { name: /create event/i })
    );
    const dialogContent = document.getElementById('dialog-content') as HTMLElement;

    await user.type(
      within(dialogContent).getByPlaceholderText(/event subject/i),
      'Design Review'
    );
    await user.type(
      within(dialogContent).getByPlaceholderText(/event location/i),
      'Room 42'
    );
    const dateInputs = dialogContent.querySelectorAll('input[type="datetime-local"]');
    fireEvent.change(dateInputs[0], { target: { value: '2026-09-20T09:00' } });
    fireEvent.change(dateInputs[1], { target: { value: '2026-09-20T10:00' } });

    fetchSpy.mockClear();
    await user.click(
      within(dialogContent).getByRole('button', { name: /create event/i })
    );

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/integrations/microsoft365/calendars/create'),
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('Design Review'),
        })
      );
    });
  });

  // Test 20: deletes an email with confirmation
  test('deletes an email when confirmed', async () => {
    const user = userEvent.setup();
    const confirmSpy = jest.spyOn(window, 'confirm').mockReturnValue(true);
    const fetchSpy = jest.spyOn(global, 'fetch');

    render(<Microsoft365Integration />);

    await settleData(/Hello World/);

    const trashButtons = document.querySelectorAll('.lucide-trash-2');
    const trashButton = trashButtons[0].closest('button') as HTMLElement;
    await user.click(trashButton);

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/integrations/microsoft365/outlook/messages/e1'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });
    // list is refreshed after deletion
    await waitFor(() => {
      const refreshCalls = fetchSpy.mock.calls.filter(([url]) =>
        String(url).includes('/outlook/messages')
      );
      expect(refreshCalls.length).toBeGreaterThan(2);
    });

    confirmSpy.mockRestore();
  });

  // Test 21: delete is skipped when confirmation is dismissed
  test('does not delete when confirmation is dismissed', async () => {
    const user = userEvent.setup();
    jest.spyOn(window, 'confirm').mockReturnValue(false);
    const fetchSpy = jest.spyOn(global, 'fetch');

    render(<Microsoft365Integration />);

    await settleData(/Hello World/);
    fetchSpy.mockClear();

    const trashButtons = document.querySelectorAll('.lucide-trash-2');
    const trashButton = trashButtons[0].closest('button') as HTMLElement;
    await user.click(trashButton);

    await new Promise((r) => setTimeout(r, 100));
    expect(
      fetchSpy.mock.calls.some(([url, init]) =>
        String(url).includes('/outlook/messages/e1') &&
        (init as RequestInit)?.method === 'DELETE'
      )
    ).toBe(false);
  });

  // Test 22: deletes a calendar event
  test('deletes a calendar event when confirmed', async () => {
    const user = userEvent.setup();
    jest.spyOn(window, 'confirm').mockReturnValue(true);
    const fetchSpy = jest.spyOn(global, 'fetch');

    render(<Microsoft365Integration />);

    await settleData(/Hello World/);
    fireEvent.click(screen.getByRole('button', { name: /calendar/i }));
    await waitFor(() => {
      expect(screen.getByText('All-hands Sync')).toBeInTheDocument();
    });

    // Outlook tab is unmounted — only calendar rows have trash buttons now.
    // Target the trash button inside the "All-hands Sync" row.
    const allHandsRow = screen
      .getByText('All-hands Sync')
      .closest('.flex.items-start') as HTMLElement;
    const trashButton = allHandsRow
      .querySelector('.lucide-trash-2')!
      .closest('button') as HTMLElement;
    await user.click(trashButton);

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/integrations/microsoft365/calendar/events/ev2'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });
  });

  describe('Automation tab', () => {
    const openAutomation = async () => {
      render(<Microsoft365Integration />);
      await settleData(/Hello World/);
      fireEvent.click(screen.getByRole('button', { name: /automation/i }));
      await waitFor(() => {
        expect(
          screen.getByText(/advanced automation control/i)
        ).toBeInTheDocument();
      });
    };

    test('runs Excel worksheet creation', async () => {
      const fetchSpy = jest.spyOn(global, 'fetch');
      await openAutomation();

      fireEvent.change(document.getElementById('excel-sheet-name')!, {
        target: { value: 'Report_2026' },
      });
      fireEvent.click(screen.getByRole('button', { name: /^run$/i }));

      await waitFor(() => {
        expect(fetchSpy).toHaveBeenCalledWith(
          expect.stringContaining('/api/integrations/microsoft365/excel/execute'),
          expect.objectContaining({
            method: 'POST',
            body: expect.stringContaining('Report_2026'),
          })
        );
      });
    });

    test('runs Excel column mapping test', async () => {
      const fetchSpy = jest.spyOn(global, 'fetch');
      await openAutomation();

      fireEvent.click(
        screen.getByRole('button', { name: /test column mapping/i })
      );

      await waitFor(() => {
        expect(fetchSpy).toHaveBeenCalledWith(
          expect.stringContaining('/api/integrations/microsoft365/excel/execute'),
          expect.objectContaining({
            method: 'POST',
            body: expect.stringContaining('append_row'),
          })
        );
      });
    });

    test('runs Outlook auto-archive action', async () => {
      const fetchSpy = jest.spyOn(global, 'fetch');
      await openAutomation();

      fireEvent.click(screen.getByRole('button', { name: /auto-archive/i }));

      await waitFor(() => {
        expect(fetchSpy).toHaveBeenCalledWith(
          expect.stringContaining('/api/integrations/microsoft365/outlook/execute'),
          expect.objectContaining({
            method: 'POST',
            body: expect.stringContaining('move_email'),
          })
        );
      });
    });

    test('runs OneDrive new-project workflow', async () => {
      const fetchSpy = jest.spyOn(global, 'fetch');
      await openAutomation();

      fireEvent.click(
        screen.getByRole('button', { name: /new project/i })
      );

      await waitFor(() => {
        expect(fetchSpy).toHaveBeenCalledWith(
          expect.stringContaining('/api/integrations/microsoft365/onedrive/execute'),
          expect.objectContaining({
            method: 'POST',
            body: expect.stringContaining('create_folder'),
          })
        );
      });
    });

    test('provisions a team from the Teams automation panel', async () => {
      const fetchSpy = jest.spyOn(global, 'fetch');
      await openAutomation();

      fireEvent.change(document.getElementById('team-name')!, {
        target: { value: 'Project Atlas' },
      });
      fireEvent.click(
        screen.getByRole('button', { name: /provision team/i })
      );

      await waitFor(() => {
        expect(fetchSpy).toHaveBeenCalledWith(
          expect.stringContaining('/api/integrations/microsoft365/teams/execute'),
          expect.objectContaining({
            method: 'POST',
            body: expect.stringContaining('Project Atlas'),
          })
        );
      });
    });
  });

  describe('Webhooks', () => {
    test('webhooks tab is reachable and exposes the subscription form', async () => {
      render(<Microsoft365Integration />);

      await settleData(/Hello World/);

      fireEvent.click(screen.getByRole('button', { name: /webhooks/i }));

      await waitFor(() => {
        expect(
          screen.getByRole('button', { name: /enable notifications/i })
        ).toBeInTheDocument();
      });
      expect(document.getElementById('webhook-url')).toHaveValue(
        'https://api.atom.com/webhook'
      );
      expect(screen.getByLabelText(/notification url/i)).toBeInTheDocument();
    });

    test('creates a webhook subscription', async () => {
      const fetchSpy = jest.spyOn(global, 'fetch');
      render(<Microsoft365Integration />);

      await settleData(/Hello World/);
      fireEvent.click(screen.getByRole('button', { name: /webhooks/i }));
      await screen.findByRole('button', { name: /enable notifications/i });

      fireEvent.change(document.getElementById('webhook-url')!, {
        target: { value: 'https://hooks.example.com/callback' },
      });

      fetchSpy.mockClear();
      fireEvent.click(
        screen.getByRole('button', { name: /enable notifications/i })
      );

      await waitFor(() => {
        expect(fetchSpy).toHaveBeenCalledWith(
          expect.stringContaining('/api/integrations/microsoft365/subscriptions'),
          expect.objectContaining({
            method: 'POST',
            body: expect.stringContaining('https://hooks.example.com/callback'),
          })
        );
      });
      const bodyCall = fetchSpy.mock.calls.find(([url]) =>
        String(url).includes('/subscriptions')
      );
      expect(String(bodyCall![1]!.body)).toContain("me/mailFolders('Inbox')/messages");
    });

    test('handles webhook subscription failure without crashing', async () => {
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      server.use(
        rest.post('/api/integrations/microsoft365/subscriptions', (req, res, ctx) => {
          return res(ctx.status(500), ctx.json({ error: 'boom' }));
        })
      );
      const fetchSpy = jest.spyOn(global, 'fetch');

      render(<Microsoft365Integration />);

      await settleData(/Hello World/);
      fireEvent.click(screen.getByRole('button', { name: /webhooks/i }));
      await screen.findByRole('button', { name: /enable notifications/i });

      fireEvent.click(
        screen.getByRole('button', { name: /enable notifications/i })
      );

      await waitFor(() => {
        expect(consoleErrorSpy).toHaveBeenCalled();
      });
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/integrations/microsoft365/subscriptions'),
        expect.objectContaining({ method: 'POST' })
      );

      consoleErrorSpy.mockRestore();
    });
  });

  describe('Empty states', () => {
    test('renders empty email list without crashing', async () => {
      server.use(
        rest.get('/api/integrations/microsoft365/outlook/messages', (req, res, ctx) => {
          return res(ctx.status(200), ctx.json({ messages: [] }));
        })
      );

      render(<Microsoft365Integration />);

      await waitFor(() => {
        expect(screen.getByText('Connected')).toBeInTheDocument();
      });
      // no email rows, no crash, stats reflect the empty list
      expect(screen.queryByText('Hello World')).not.toBeInTheDocument();
      await waitFor(() => {
        expect(screen.getAllByText('0 unread').length).toBeGreaterThan(0);
      });
    });
  });
});

// ---------------------------------------------------------------------------
// Extended coverage: error paths, rich badges, compose cc/importance, and
// attendees in the event dialog
// ---------------------------------------------------------------------------
describe('Microsoft365Integration (extended coverage)', () => {
  // NOTE: jest.config.js sets restoreMocks:true, which detaches describe-scope
  // spies after every test — create a fresh console.error spy per test.
  let errorSpy: jest.SpyInstance;
  beforeEach(() => {
    errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  const futureDate = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();

  const richMessages = [
    {
      id: 'e1',
      subject: 'Urgent Alert',
      sender: { emailAddress: { name: 'Alice', address: 'alice@example.com' } },
      bodyPreview: 'Needs attention',
      isRead: false,
      importance: 'high',
      hasAttachments: true,
      receivedDateTime: '2024-01-15T10:00:00Z',
      webLink: 'https://outlook.example.com/e1',
    },
    {
      id: 'e2',
      subject: 'FYI Newsletter',
      sender: { emailAddress: { name: 'Bob', address: 'bob@example.com' } },
      bodyPreview: 'Low priority',
      isRead: true,
      importance: 'low',
      receivedDateTime: '2024-01-14T10:00:00Z',
    },
    {
      id: 'e3',
      subject: 'Normal Note',
      sender: { emailAddress: { name: 'Carol', address: 'carol@example.com' } },
      bodyPreview: 'Normal priority',
      isRead: true,
      importance: 'normal',
      receivedDateTime: '2024-01-13T10:00:00Z',
    },
  ];

  const richTeams = [
    {
      id: 't1',
      displayName: 'Private Squad',
      description: 'Confidential team',
      visibility: 'private',
      isArchived: true,
      createdDateTime: '2024-01-01T00:00:00Z',
      webUrl: 'https://teams.example.com/t1',
      channels: [{ id: 'c1' }, { id: 'c2' }, { id: 'c3' }],
    },
    {
      id: 't2',
      displayName: 'Public Crew',
      description: 'Open team',
      visibility: 'public',
      isArchived: false,
      createdDateTime: '2024-01-02T00:00:00Z',
      webUrl: 'https://teams.example.com/t2',
    },
  ];

  const longBody = 'x'.repeat(250);

  const richEvents = [
    {
      id: 'ev1',
      subject: 'Long Meeting',
      body: { contentType: 'text', content: longBody },
      start: { dateTime: futureDate },
      end: { dateTime: futureDate },
      location: { displayName: 'Room 5' },
      isOnlineMeeting: false,
    },
  ];

  // NOTE: MSW resolves handlers in the order passed to server.use(), so the
  // data-rich overrides must come BEFORE the base m365Handlers.
  const richHandlers = [
    rest.get('/api/integrations/microsoft365/outlook/messages', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ messages: richMessages }));
    }),
    rest.get('/api/integrations/microsoft365/teams', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ teams: richTeams }));
    }),
    rest.get('/api/integrations/microsoft365/calendar/events', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ events: richEvents }));
    }),
    ...m365Handlers,
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...richHandlers);
  });

  const settle = async (text: RegExp) => {
    await screen.findByText(text);
    await new Promise((r) => setTimeout(r, 50));
  };

  test('renders email badges (New, importance, attachments) and opens links', async () => {
    const openSpy = jest.fn();
    window.open = openSpy as any;

    render(<Microsoft365Integration />);
    await settle(/Urgent Alert/);

    expect(screen.getByText('New')).toBeInTheDocument();
    expect(screen.getByText('high')).toBeInTheDocument();
    expect(screen.getByText('low')).toBeInTheDocument();
    expect(screen.getByText('normal')).toBeInTheDocument();
    expect(screen.getByText('Has attachments')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Urgent Alert'));
    expect(openSpy).toHaveBeenCalledWith('https://outlook.example.com/e1', '_blank');
  });

  test('renders team visibility, archived badge and channel count', async () => {
    render(<Microsoft365Integration />);
    await settle(/Urgent Alert/);

    fireEvent.click(screen.getByRole('button', { name: 'Teams' }));

    expect(await screen.findByText('Private Squad')).toBeInTheDocument();
    expect(screen.getByText('Public Crew')).toBeInTheDocument();
    expect(screen.getByText('private')).toBeInTheDocument();
    expect(screen.getByText('public')).toBeInTheDocument();
    expect(screen.getByText('Archived')).toBeInTheDocument();
    expect(screen.getByText('3 channels')).toBeInTheDocument();
  });

  test('truncates long event descriptions over 200 chars', async () => {
    render(<Microsoft365Integration />);
    await settle(/Urgent Alert/);

    fireEvent.click(screen.getByRole('button', { name: /calendar/i }));

    expect(await screen.findByText('Long Meeting')).toBeInTheDocument();
    const truncated = screen.getByText((content, element) => {
      return element?.textContent === longBody.substring(0, 200) + '...';
    });
    expect(truncated).toBeInTheDocument();
  });

  test('composes an email with cc and high importance', async () => {
    render(<Microsoft365Integration />);
    await settle(/Urgent Alert/);

    fireEvent.click(screen.getByRole('button', { name: /compose email/i }));
    const dialog = document.getElementById('dialog-content') as HTMLElement;

    fireEvent.change(
      dialog.querySelector('input[placeholder="recipient@example.com, recipient2@example.com"]')!,
      { target: { value: 'to@example.com' } }
    );
    fireEvent.change(dialog.querySelector('input[placeholder="cc@example.com"]')!, {
      target: { value: 'cc@example.com' },
    });
    fireEvent.change(dialog.querySelector('input[placeholder="Email subject"]')!, {
      target: { value: 'Subject line' },
    });
    fireEvent.change(dialog.querySelector('textarea')!, {
      target: { value: 'Body text' },
    });

    // Pick importance = High via the Radix Select (keyboard-opened)
    const importanceTrigger = dialog.querySelector('button[role="combobox"]')!;
    fireEvent.keyDown(importanceTrigger, { key: 'ArrowDown' });
    const highOption = await waitFor(() => {
      const found = Array.from(document.querySelectorAll('[role="option"]')).find(
        (i) => i.textContent === 'High'
      );
      if (!found) throw new Error('High option not found');
      return found as HTMLElement;
    });
    fireEvent.click(highOption);

    const sendButton = Array.from(dialog.querySelectorAll('button')).find((b) =>
      /send email/i.test(b.textContent || '')
    )!;
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Success', description: 'Email sent successfully' })
      );
    });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  test('shows error toast when sending an email fails', async () => {
    server.use(
      rest.post('/api/integrations/microsoft365/emails/send', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<Microsoft365Integration />);
    await settle(/Urgent Alert/);

    fireEvent.click(screen.getByRole('button', { name: /compose email/i }));
    const dialog = document.getElementById('dialog-content') as HTMLElement;

    fireEvent.change(
      dialog.querySelector('input[placeholder="recipient@example.com, recipient2@example.com"]')!,
      { target: { value: 'to@example.com' } }
    );
    fireEvent.change(dialog.querySelector('input[placeholder="Email subject"]')!, {
      target: { value: 'Subject' },
    });
    fireEvent.change(dialog.querySelector('textarea')!, {
      target: { value: 'Body' },
    });
    const sendButton = Array.from(dialog.querySelectorAll('button')).find((b) =>
      /send email/i.test(b.textContent || '')
    )!;
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', description: 'Failed to send email' })
      );
    });
  });

  test('creates an event with attendees and shows failure toast on error', async () => {
    server.use(
      rest.post('/api/integrations/microsoft365/calendars/create', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<Microsoft365Integration />);
    await settle(/Urgent Alert/);

    fireEvent.click(screen.getByRole('button', { name: /calendar/i }));
    fireEvent.click(screen.getAllByRole('button', { name: /create event/i })[0]);
    const dialog = document.getElementById('dialog-content') as HTMLElement;

    fireEvent.change(dialog.querySelector('input[placeholder="Event subject"]')!, {
      target: { value: 'Sync' },
    });
    fireEvent.change(
      dialog.querySelector('input[placeholder="attendee@example.com, attendee2@example.com"]')!,
      { target: { value: 'a@example.com, b@example.com' } }
    );
    const timeInputs = dialog.querySelectorAll('input[type="datetime-local"]');
    fireEvent.change(timeInputs[0], { target: { value: '2026-09-20T09:00' } });
    fireEvent.change(timeInputs[1], { target: { value: '2026-09-20T10:00' } });
    const createButton = Array.from(dialog.querySelectorAll('button')).filter((b) =>
      /create event/i.test(b.textContent || '')
    );
    fireEvent.click(createButton[createButton.length - 1]);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to create calendar event',
        })
      );
    });
  });

  test('shows toasts for delete success and delete failure', async () => {
    jest.spyOn(window, 'confirm').mockReturnValue(true);
    server.use(
      rest.delete('/api/integrations/microsoft365/outlook/messages/:id', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );

    render(<Microsoft365Integration />);
    await settle(/Urgent Alert/);

    const trashButtons = document.querySelectorAll('.lucide-trash-2');
    fireEvent.click(trashButtons[0].closest('button') as HTMLElement);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Success', description: 'Item deleted successfully' })
      );
    });

    // Now a failing delete
    getToastMock().mockClear();
    server.use(
      rest.delete('/api/integrations/microsoft365/outlook/messages/:id', (req, res) =>
        res.networkError('boom')
      )
    );
    const trashButtons2 = document.querySelectorAll('.lucide-trash-2');
    fireEvent.click(trashButtons2[0].closest('button') as HTMLElement);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', description: 'Failed to delete item' })
      );
    });
  });

  test('automation tab: empty worksheet name shows error toast; auto-reply works', async () => {
    render(<Microsoft365Integration />);
    await settle(/Urgent Alert/);

    fireEvent.click(screen.getByRole('button', { name: /automation/i }));
    await screen.findByText(/advanced automation control/i);

    // empty sheet name -> validation toast
    fireEvent.click(screen.getByRole('button', { name: /^run$/i }));
    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', description: 'Name required' })
      );
    });

    // trigger auto-reply
    getToastMock().mockClear();
    fireEvent.click(screen.getByRole('button', { name: /trigger auto-reply/i }));
    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Success', description: 'Bot replied to thread' })
      );
    });
  });

  test('webhooks: selecting a different resource updates the subscription payload', async () => {
    const fetchSpy = jest.spyOn(global, 'fetch');
    render(<Microsoft365Integration />);
    await settle(/Urgent Alert/);

    fireEvent.click(screen.getByRole('button', { name: /webhooks/i }));
    await screen.findByRole('button', { name: /enable notifications/i });

    // Pick "Calendar Events" via the Radix Select (keyboard-opened)
    const resourceTrigger = document
      .getElementById('webhook-resource')
      ?.closest('button') as HTMLElement;
    fireEvent.keyDown(resourceTrigger, { key: 'ArrowDown' });
    const eventsOption = await waitFor(() => {
      const found = Array.from(document.querySelectorAll('[role="option"]')).find(
        (i) => i.textContent === 'Calendar Events'
      );
      if (!found) throw new Error('Calendar Events option not found');
      return found as HTMLElement;
    });
    fireEvent.click(eventsOption);

    fetchSpy.mockClear();
    fireEvent.click(screen.getByRole('button', { name: /enable notifications/i }));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringContaining('/api/integrations/microsoft365/subscriptions'),
        expect.objectContaining({ method: 'POST' })
      );
    });
    const bodyCall = fetchSpy.mock.calls.find(([url]) =>
      String(url).includes('/subscriptions')
    );
    expect(String(bodyCall![1]!.body)).toContain('me/events');
    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Success',
          description: 'Webhook subscription created!',
        })
      );
    });
  });

  test('logs errors when loads fail and health check throws', async () => {
    const netFail = (path: string) => rest.get(path, (req, res) => res.networkError('boom'));
    server.use(
      netFail('/api/integrations/microsoft365/user'),
      netFail('/api/integrations/microsoft365/calendar/events'),
      netFail('/api/integrations/microsoft365/teams')
    );

    render(<Microsoft365Integration />);

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Failed to load user profile:', expect.anything());
      expect(errorSpy).toHaveBeenCalledWith('Failed to load calendars:', expect.anything());
      expect(errorSpy).toHaveBeenCalledWith('Failed to load teams:', expect.anything());
    });
  });

  test('shows error toast when email loading fails', async () => {
    server.use(
      rest.get('/api/integrations/microsoft365/outlook/messages', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<Microsoft365Integration />);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to load emails from Microsoft 365',
        })
      );
    });
  });

  test('treats health check network failure as disconnected', async () => {
    server.use(
      rest.get('/api/integrations/connection-status', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<Microsoft365Integration />);

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Connection status check failed:', expect.anything());
      expect(
        screen.getByRole('button', { name: /connect microsoft 365 account/i })
      ).toBeInTheDocument();
    });
  });

  test('clicking Refresh Status re-runs the health check', async () => {
    render(<Microsoft365Integration />);
    await settle(/Urgent Alert/);

    fireEvent.click(screen.getByRole('button', { name: /refresh status/i }));
    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  test('OneDrive tab renders, tolerates typing in the file search', async () => {
    render(<Microsoft365Integration />);
    await settle(/Urgent Alert/);

    fireEvent.click(screen.getByRole('button', { name: 'OneDrive' }));
    const search = await screen.findByPlaceholderText(/search files/i);
    fireEvent.change(search, { target: { value: 'report' } });
    expect((search as HTMLInputElement).value).toBe('report');
  });

  test('Users tab renders, tolerates typing in the user search', async () => {
    render(<Microsoft365Integration />);
    await settle(/Urgent Alert/);

    fireEvent.click(screen.getByRole('button', { name: 'Users' }));
    const search = await screen.findByPlaceholderText(/search users/i);
    fireEvent.change(search, { target: { value: 'alice' } });
    expect((search as HTMLInputElement).value).toBe('alice');
  });

  test('filters teams by search query', async () => {
    render(<Microsoft365Integration />);
    await settle(/Urgent Alert/);

    fireEvent.click(screen.getByRole('button', { name: 'Teams' }));
    expect(await screen.findByText('Private Squad')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/search teams/i), {
      target: { value: 'public crew' },
    });
    expect(screen.getByText('Public Crew')).toBeInTheDocument();
    expect(screen.queryByText('Private Squad')).not.toBeInTheDocument();
  });

  test('opens the team web url when a team row is clicked', async () => {
    const openSpy = jest.fn();
    window.open = openSpy as any;

    render(<Microsoft365Integration />);
    await settle(/Urgent Alert/);

    fireEvent.click(screen.getByRole('button', { name: 'Teams' }));
    expect(await screen.findByText('Private Squad')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Private Squad'));
    expect(openSpy).toHaveBeenCalledWith('https://teams.example.com/t1', '_blank');
  });

  test('shows an error toast when deleting an email fails', async () => {
    jest.spyOn(window, 'confirm').mockReturnValue(true);
    server.use(
      rest.delete('/api/integrations/microsoft365/outlook/messages/:id', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<Microsoft365Integration />);
    await settle(/Urgent Alert/);

    const trashButton = document
      .querySelectorAll('.lucide-trash-2')[0]
      .closest('button') as HTMLElement;
    fireEvent.click(trashButton);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to delete item',
        })
      );
    });
  });

  test('Automation tab Quick Ack action fires the execute call', async () => {
    const fetchSpy = jest.spyOn(global, 'fetch');
    render(<Microsoft365Integration />);
    await settle(/Urgent Alert/);

    fireEvent.click(screen.getByRole('button', { name: /automation/i }));
    fireEvent.click(await screen.findByRole('button', { name: /quick ack/i }));

    await waitFor(() => {
      const call = fetchSpy.mock.calls.find(
        ([url]) =>
          String(url).includes('/outlook/execute') &&
          String(url).includes('reply_email') === false
      );
      const replyCall = fetchSpy.mock.calls.find(
        ([url, init]) =>
          String(url).includes('/outlook/execute') &&
          String((init as any)?.body).includes('reply_email')
      );
      expect(replyCall).toBeDefined();
      expect(call).toBeDefined();
    });
    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Success',
          description: 'Sent quick acknowledgment',
        })
      );
    });
  });

  test('cancels the compose email dialog without sending', async () => {
    render(<Microsoft365Integration />);
    await settle(/Urgent Alert/);

    fireEvent.click(screen.getByRole('button', { name: /compose email/i }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: /cancel/i }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  test('fills the event description and cancels the create-event dialog', async () => {
    render(<Microsoft365Integration />);
    await settle(/Urgent Alert/);

    fireEvent.click(screen.getByRole('button', { name: /calendar/i }));
    fireEvent.click(
      await screen.findByRole('button', { name: /create event/i })
    );
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(within(dialog).getByPlaceholderText('Event description'), {
      target: { value: 'Detailed notes' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: /cancel/i }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });
});
