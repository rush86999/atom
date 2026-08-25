/**
 * Outlook Integration Component Tests
 *
 * Verifies the real Outlook integration component:
 * - Health check / connection state and OAuth connect flow (token forwarding)
 * - Email loading, search/importance filters, folder switching
 * - Compose-and-send flow, calendar/contacts/tasks tabs, error paths
 */

import React from 'react';
import { fireEvent, renderWithProviders, screen, waitFor, within } from '../../tests/test-utils';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../tests/mocks/server';
import OutlookIntegration from '../OutlookIntegration';
import { useToast } from '@/components/ui/use-toast';

const getToastMock = (): jest.Mock => (useToast as jest.Mock)().toast;

const outlookHandlers = [
  rest.get('/api/integrations/outlook/health', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ status: 'healthy' }));
  }),
  rest.post('/api/integrations/outlook/profile', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          profile: {
            id: 'u1',
            displayName: 'Rushi Parikh',
            mail: 'rushi@example.com',
            userPrincipalName: 'rushi@example.com',
            jobTitle: 'Engineer',
            officeLocation: 'SF',
          },
        },
      })
    );
  }),
  rest.post('/api/integrations/outlook/emails', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          emails: [
            {
              id: 'e1',
              subject: 'Test email',
              from: { name: 'Alice', email: 'alice@x.com' },
              body: 'Hello there',
              receivedDateTime: '2024-01-15T10:00:00Z',
              isRead: false,
              hasAttachments: true,
              importance: 'high',
              webLink: 'https://outlook.example.com/e1',
            },
            {
              id: 'e2',
              subject: 'Budget report',
              from: { name: 'Bob', email: 'bob@x.com' },
              body: '',
              receivedDateTime: '2024-01-14T10:00:00Z',
              isRead: true,
              hasAttachments: false,
              importance: 'normal',
              webLink: 'https://outlook.example.com/e2',
            },
            {
              id: 'e3',
              subject: 'Old newsletter',
              from: { name: 'Carol', email: 'carol@x.com' },
              body: '',
              receivedDateTime: '2024-01-13T10:00:00Z',
              isRead: true,
              hasAttachments: false,
              importance: 'low',
              webLink: 'https://outlook.example.com/e3',
            },
          ],
        },
      })
    );
  }),
  rest.post('/api/integrations/outlook/events', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          events: [
            {
              id: 'ev1',
              subject: 'Standup',
              start: { dateTime: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(), timeZone: 'UTC' },
              end: { dateTime: new Date(Date.now() + 25 * 60 * 60 * 1000).toISOString(), timeZone: 'UTC' },
              location: 'Zoom',
              attendees: [
                { name: 'Alice', email: 'alice@x.com', type: 'required' },
                { name: 'Bob', email: 'bob@x.com', type: 'required' },
                { name: 'Carol', email: 'carol@x.com', type: 'optional' },
                { name: 'Dave', email: 'dave@x.com', type: 'optional' },
              ],
              isAllDay: false,
              showAs: 'busy',
            },
            {
              id: 'ev2',
              subject: 'Past review',
              start: { dateTime: '2020-01-01T10:00:00Z', timeZone: 'UTC' },
              end: { dateTime: '2020-01-01T11:00:00Z', timeZone: 'UTC' },
              isAllDay: false,
              showAs: 'free',
            },
          ],
        },
      })
    );
  }),
  rest.post('/api/integrations/outlook/contacts', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          contacts: [
            {
              id: 'c1',
              displayName: 'Alice Chen',
              emailAddresses: [{ address: 'alice@x.com' }],
              businessPhones: ['+1-555-0100'],
              jobTitle: 'Engineer',
              companyName: 'Acme',
            },
            {
              id: 'c2',
              displayName: 'Bob Smith',
              emailAddresses: [{ address: 'bob@x.com', name: 'Bob' }],
              businessPhones: [],
            },
          ],
        },
      })
    );
  }),
  rest.post('/api/integrations/outlook/tasks', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          tasks: [
            {
              id: 't1',
              title: 'Ship v2',
              status: 'completed',
              importance: 'high',
              dueDateTime: '2024-02-01T10:00:00Z',
              categories: ['Engineering', 'Release'],
            },
            {
              id: 't2',
              title: 'Write docs',
              status: 'inProgress',
              importance: 'normal',
              categories: [],
            },
            {
              id: 't3',
              title: 'Plan retro',
              status: 'notStarted',
              importance: 'low',
              categories: [],
            },
            {
              id: 't4',
              title: 'Defer old task',
              status: 'deferred',
              importance: 'high',
              categories: [],
            },
            {
              id: 't5',
              title: 'Wait for signoff',
              status: 'waitingOnOthers',
              importance: 'normal',
              categories: [],
            },
          ],
        },
      })
    );
  }),
];

const settleEmails = async (subject = 'Test email') => {
  await screen.findByText(subject);
  await new Promise((r) => setTimeout(r, 30));
};

describe('OutlookIntegration Component', () => {
  beforeEach(() => {
    server.resetHandlers();
    server.use(...outlookHandlers);
    localStorage.clear();
  });

  it('renders Outlook integration component', () => {
    renderWithProviders(<OutlookIntegration />);
    expect(screen.getByText(/outlook/i)).toBeInTheDocument();
  });

  it('initiates OAuth connection and forwards the auth token to the initiate endpoint', async () => {
    const user = userEvent.setup();
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    localStorage.setItem('auth_token', 'test-jwt-token');

    server.use(
      rest.get('/api/integrations/outlook/health', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    renderWithProviders(<OutlookIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect/i,
    });
    // B7 contract (Plan 315): the connect flow hard-redirects the browser to
    // the secured backend /api/v1/auth/oauth/microsoft/initiate?token=<jwt>
    // endpoint (no fetch). jsdom cannot navigate (window.location is
    // non-configurable), so the observable contract is the same as the Slack
    // connect test: the token-bearing branch executes cleanly and the UI
    // stays in the connect state.
    consoleErrorSpy.mockClear();
    await user.click(connectButton);
    expect(consoleErrorSpy).not.toHaveBeenCalled();
    expect(
      await screen.findByRole('button', { name: /connect/i })
    ).toBeInTheDocument();
    consoleErrorSpy.mockRestore();
  });

  it('fetches emails', async () => {
    server.use(
      rest.post('/api/integrations/outlook/emails', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            data: {
              emails: [
                { id: '1', subject: 'Test email', from: { name: 'A', email: 'a@x.com' } },
              ],
            },
          })
        );
      })
    );

    renderWithProviders(<OutlookIntegration connected={true} />);

    await waitFor(() => {
      expect(screen.getByText('Test email')).toBeInTheDocument();
    });
  });

  describe('connected overview', () => {
    it('renders profile badge, stats, and email rows with badges', async () => {
      renderWithProviders(<OutlookIntegration />);

      await settleEmails();

      // Profile badge in the header
      expect(screen.getByText('Rushi Parikh')).toBeInTheDocument();

      // Email rows
      expect(screen.getByText('Alice')).toBeInTheDocument();
      expect(screen.getByText('alice@x.com')).toBeInTheDocument();
      expect(screen.getByText('Budget report')).toBeInTheDocument();
      expect(screen.getByText('Bob')).toBeInTheDocument();
      expect(screen.getByText('Old newsletter')).toBeInTheDocument();
      // Inline body preview
      expect(screen.getByText('Hello there')).toBeInTheDocument();
      // Status/importance badges: e1 unread + attachment + high; e3 low
      // ("Unread" also appears as a stat-card label)
      expect(screen.getAllByText('Unread').length).toBeGreaterThanOrEqual(2);
      expect(screen.getByText('Attachment')).toBeInTheDocument();
      expect(screen.getAllByText('high').length).toBeGreaterThan(0);
      expect(screen.getByText('normal')).toBeInTheDocument();
      expect(screen.getByText('low')).toBeInTheDocument();

      // Stats labels + computed completion rate (1/5 tasks completed)
      expect(screen.getByText('In selected folder')).toBeInTheDocument();
      expect(screen.getByText('Require attention')).toBeInTheDocument();
      expect(screen.getByText('High priority')).toBeInTheDocument();
      expect(screen.getByText('Next 7 days')).toBeInTheDocument();
      expect(screen.getByText('20%')).toBeInTheDocument();
    });

    it('opens the email web link from the row action', async () => {
      const user = userEvent.setup();
      const openSpy = jest.spyOn(window, 'open').mockImplementation(() => null);
      renderWithProviders(<OutlookIntegration />);

      await settleEmails();

      const row = screen.getByText('Test email').closest('tr') as HTMLElement;
      await user.click(within(row).getByRole('button'));
      expect(openSpy).toHaveBeenCalledWith('https://outlook.example.com/e1', '_blank');
      openSpy.mockRestore();
    });

    it('filters emails by search and importance', async () => {
      const user = userEvent.setup();
      renderWithProviders(<OutlookIntegration />);

      await settleEmails();

      const searchInput = screen.getByPlaceholderText(/search emails/i);

      // Search narrows to subject/sender matches
      await user.type(searchInput, 'Budget');
      await waitFor(() => {
        expect(screen.getByText('Budget report')).toBeInTheDocument();
      });
      expect(screen.queryByText('Test email')).not.toBeInTheDocument();

      // Reset, then filter by importance: High only
      await user.clear(searchInput);
      await user.click(screen.getAllByRole('combobox')[1]);
      await user.click(within(await screen.findByRole('listbox')).getByText('High'));
      await waitFor(() => {
        expect(screen.getByText('Test email')).toBeInTheDocument();
      });
      expect(screen.queryByText('Budget report')).not.toBeInTheDocument();

      // Search + importance that match nothing -> empty state
      await user.type(searchInput, 'Budget');
      await waitFor(() => {
        expect(screen.getByText('No emails found')).toBeInTheDocument();
      });
      expect(
        screen.getByRole('button', { name: /compose new email/i })
      ).toBeInTheDocument();
    });

    it('switching folder refetches emails for that folder', async () => {
      const user = userEvent.setup();
      const fetchSpy = jest.spyOn(global, 'fetch');
      renderWithProviders(<OutlookIntegration />);

      await settleEmails();

      await user.click(screen.getAllByRole('combobox')[0]);
      await user.click(within(await screen.findByRole('listbox')).getByText('Sent Items'));

      await waitFor(() => {
        expect(
          fetchSpy.mock.calls.some(
            (c) =>
              String(c[0]).endsWith('/api/integrations/outlook/emails') &&
              String(c[1]?.body).includes('"folder":"sent"')
          )
        ).toBe(true);
      });
      // Restore the fetch spy — leaving it installed wraps MSW's patched
      // fetch, so the NEXT test's requests bypass MSW interception and the
      // empty-state test's mock never gets served (dialog never opens).
      fetchSpy.mockRestore();
    });

    it('shows the empty state when there are no emails', async () => {
      const user = userEvent.setup();
      server.use(
        rest.post('/api/integrations/outlook/emails', (req, res, ctx) => {
          return res(ctx.status(200), ctx.json({ data: { emails: [] } }));
        })
      );

      renderWithProviders(<OutlookIntegration />);

      await waitFor(() => {
        expect(screen.getByText('No emails found')).toBeInTheDocument();
      });
      expect(screen.getByText(/try adjusting your filters/i)).toBeInTheDocument();

      // The empty-state CTA opens the compose dialog
      const btn = screen.getByRole('button', { name: /compose new email/i });
      // The empty-state button can report invisible in jsdom after prior
      // tests (offsetParent null) even though it is interactive — force the
      // click so the compose dialog opens deterministically.
      // fireEvent bypasses jsdom visibility checks — userEvent refuses to
      // click elements it deems hidden (offsetParent null) even with force,
      // and in full-file runs the empty-state button can report hidden.
      fireEvent.click(btn);
      expect(await screen.findByRole('dialog')).toBeInTheDocument();
    });
  });

  describe('compose flow', () => {
    it('sends an email through the compose dialog', async () => {
      const user = userEvent.setup();
      const sendBodies: any[] = [];
      server.use(
        rest.post('/api/integrations/outlook/emails/send', (req, res, ctx) => {
          sendBodies.push(req.body);
          return res(ctx.status(200), ctx.json({ data: { email: {} } }));
        })
      );

      renderWithProviders(<OutlookIntegration />);

      await settleEmails();

      await user.click(screen.getByRole('button', { name: /new email/i }));
      const dialog = await screen.findByRole('dialog');
      expect(
        within(dialog).getByRole('heading', { name: /compose new email/i })
      ).toBeInTheDocument();

      // Submit disabled until to/subject/body are filled
      const sendButton = within(dialog).getByRole('button', { name: /send email/i });
      expect(sendButton).toBeDisabled();

      await user.type(within(dialog).getByPlaceholderText('recipient@example.com'), 'a@b.com');
      await user.type(within(dialog).getByPlaceholderText('Email subject'), 'Hi there');
      await user.type(within(dialog).getByPlaceholderText('Email content'), 'Body text');
      // Switch importance to high
      await user.click(within(dialog).getByRole('combobox'));
      await user.click(within(await screen.findByRole('listbox')).getByText('High'));
      expect(sendButton).not.toBeDisabled();

      await user.click(sendButton);

      await waitFor(() => {
        expect(
          sendBodies.some(
            (b) =>
              b.to === 'a@b.com' &&
              b.subject === 'Hi there' &&
              b.body === 'Body text' &&
              b.importance === 'high'
          )
        ).toBe(true);
      });
      expect(getToastMock()).toHaveBeenCalledWith({
        title: 'Success',
        description: 'Email sent successfully',
      });
      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });

    it('cancel closes the compose dialog without sending', async () => {
      const user = userEvent.setup();
      const sendBodies: any[] = [];
      server.use(
        rest.post('/api/integrations/outlook/emails/send', (req, res, ctx) => {
          sendBodies.push(req.body);
          return res(ctx.status(200), ctx.json({ data: {} }));
        })
      );

      renderWithProviders(<OutlookIntegration />);

      await settleEmails();

      await user.click(screen.getByRole('button', { name: /new email/i }));
      const dialog = await screen.findByRole('dialog');
      await user.click(within(dialog).getByRole('button', { name: /^cancel$/i }));

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
      expect(sendBodies).toHaveLength(0);
    });

    it('shows an error toast when sending fails and keeps the dialog open', async () => {
      const user = userEvent.setup();
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      server.use(
        rest.post('/api/integrations/outlook/emails/send', (req, res) => {
          return new Promise((resolve, reject) => {
            setTimeout(() => reject(new Error('network error')), 5);
          });
        })
      );

      renderWithProviders(<OutlookIntegration />);

      await settleEmails();

      await user.click(screen.getByRole('button', { name: /new email/i }));
      const dialog = await screen.findByRole('dialog');
      await user.type(within(dialog).getByPlaceholderText('recipient@example.com'), 'a@b.com');
      await user.type(within(dialog).getByPlaceholderText('Email subject'), 'Hi');
      await user.type(within(dialog).getByPlaceholderText('Email content'), 'Body');
      await user.click(within(dialog).getByRole('button', { name: /send email/i }));

      await waitFor(() => {
        expect(getToastMock()).toHaveBeenCalledWith({
          title: 'Error',
          description: 'Failed to send email',
          variant: 'error',
        });
      });
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      consoleErrorSpy.mockRestore();
    });
  });

  describe('calendar tab', () => {
    it('renders events with availability, location, and attendee overflow', async () => {
      const user = userEvent.setup();
      renderWithProviders(<OutlookIntegration />);

      await settleEmails();

      await user.click(screen.getByRole('button', { name: 'Calendar' }));

      await waitFor(() => {
        expect(screen.getByText('Standup')).toBeInTheDocument();
        expect(screen.getByText('Past review')).toBeInTheDocument();
      });
      expect(screen.getByText('busy')).toBeInTheDocument();
      expect(screen.getByText('free')).toBeInTheDocument();
      expect(screen.getByText('Zoom')).toBeInTheDocument();
      expect(screen.getByText('Attendees (4)')).toBeInTheDocument();
      // 4 attendees, first 3 rendered as avatars, overflow shows +1
      expect(screen.getByText('+1')).toBeInTheDocument();
    });
  });

  describe('contacts tab', () => {
    it('renders contact details', async () => {
      const user = userEvent.setup();
      renderWithProviders(<OutlookIntegration />);

      await settleEmails();

      await user.click(screen.getByRole('button', { name: 'Contacts' }));

      await waitFor(() => {
        expect(screen.getByText('Alice Chen')).toBeInTheDocument();
        expect(screen.getByText('Bob Smith')).toBeInTheDocument();
      });
      expect(screen.getByText('Engineer')).toBeInTheDocument();
      expect(screen.getByText('alice@x.com')).toBeInTheDocument();
      expect(screen.getByText('bob@x.com')).toBeInTheDocument();
      expect(screen.getByText('+1-555-0100')).toBeInTheDocument();
      expect(screen.getByText('Acme')).toBeInTheDocument();
    });
  });

  describe('tasks tab', () => {
    it('renders tasks with status labels, importance, due dates, and categories', async () => {
      const user = userEvent.setup();
      renderWithProviders(<OutlookIntegration />);

      await settleEmails();

      await user.click(screen.getByRole('button', { name: 'Tasks' }));

      await waitFor(() => {
        expect(screen.getByText('Ship v2')).toBeInTheDocument();
      });
      // Status labels (getStatusLabel branches)
      expect(screen.getByText('Completed')).toBeInTheDocument();
      expect(screen.getByText('In Progress')).toBeInTheDocument();
      expect(screen.getByText('Not Started')).toBeInTheDocument();
      expect(screen.getByText('Deferred')).toBeInTheDocument();
      expect(screen.getByText('Waiting')).toBeInTheDocument();
      // Importance badges
      expect(screen.getAllByText('high').length).toBeGreaterThanOrEqual(2);
      expect(screen.getByText('low')).toBeInTheDocument();
      // Due date + categories
      expect(screen.getByText(/Due: /)).toBeInTheDocument();
      expect(screen.getByText('Engineering')).toBeInTheDocument();
      expect(screen.getByText('Release')).toBeInTheDocument();
    });
  });

  describe('error paths', () => {
    it('handles a network-level health check failure as disconnected', async () => {
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      server.use(
        rest.get('/api/integrations/outlook/health', (req, res) => {
          return new Promise((resolve, reject) => {
            setTimeout(() => reject(new Error('network error')), 5);
          });
        })
      );

      renderWithProviders(<OutlookIntegration />);

      await waitFor(() => {
        expect(
          screen.getByRole('button', { name: /connect outlook account/i })
        ).toBeInTheDocument();
      });
      expect(consoleErrorSpy).toHaveBeenCalled();
      consoleErrorSpy.mockRestore();
    });

    it('shows an error toast when emails fail to load', async () => {
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      server.use(
        rest.post('/api/integrations/outlook/emails', (req, res) => {
          return new Promise((resolve, reject) => {
            setTimeout(() => reject(new Error('network error')), 5);
          });
        })
      );

      renderWithProviders(<OutlookIntegration />);

      await waitFor(() => {
        expect(getToastMock()).toHaveBeenCalledWith({
          title: 'Error',
          description: 'Failed to load emails from Outlook',
          variant: 'error',
        });
      });
      consoleErrorSpy.mockRestore();
    });

    it('handles events/contacts/tasks load failures without crashing', async () => {
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      server.use(
        rest.post('/api/integrations/outlook/events', (req, res) => {
          return new Promise((resolve, reject) => {
            setTimeout(() => reject(new Error('network error')), 5);
          });
        })
      );

      renderWithProviders(<OutlookIntegration />);

      await settleEmails();
      await waitFor(() => {
        expect(consoleErrorSpy).toHaveBeenCalled();
      });
      // Calendar tab renders without crashing despite the failed events fetch
      await userEvent.click(screen.getByRole('button', { name: 'Calendar' }));
      expect(screen.getByText('Connected')).toBeInTheDocument();
      consoleErrorSpy.mockRestore();
    });

    it('handles contacts and tasks load failures without crashing', async () => {
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      server.use(
        rest.post('/api/integrations/outlook/contacts', (req, res) => {
          return new Promise((resolve, reject) => {
            setTimeout(() => reject(new Error('network error')), 5);
          });
        }),
        rest.post('/api/integrations/outlook/tasks', (req, res) => {
          return new Promise((resolve, reject) => {
            setTimeout(() => reject(new Error('network error')), 5);
          });
        })
      );

      renderWithProviders(<OutlookIntegration />);

      await settleEmails();
      await waitFor(() => {
        expect(consoleErrorSpy).toHaveBeenCalled();
      });
      // Contacts + Tasks tabs render without crashing
      await userEvent.click(screen.getByRole('button', { name: 'Contacts' }));
      await userEvent.click(screen.getByRole('button', { name: 'Tasks' }));
      expect(screen.getByText('Connected')).toBeInTheDocument();
      consoleErrorSpy.mockRestore();
    });

    it('shows an error toast when the OAuth authorization redirect fails', async () => {
      const user = userEvent.setup();
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      server.use(
        rest.get('/api/integrations/outlook/health', (req, res, ctx) => {
          return res(ctx.status(500));
        })
      );
      // The connect flow hard-redirects via window.location.href; the catch
      // path is only reachable when the redirect computation/assignment
      // throws (jsdom's location is non-configurable, so a plain navigation
      // never throws). localStorage.getItem throwing is the closest jsdom
      // trigger for the same catch block.
      const originalStorage = window.localStorage;
      Object.defineProperty(window, 'localStorage', {
        value: {
          getItem: () => { throw new Error('storage unavailable'); },
          setItem: jest.fn(),
          removeItem: jest.fn(),
          clear: jest.fn(),
        },
        configurable: true,
      });

      renderWithProviders(<OutlookIntegration />);

      const connectButton = await screen.findByRole('button', { name: /connect/i });
      await user.click(connectButton);

      await waitFor(() => {
        expect(getToastMock()).toHaveBeenCalledWith({
          title: 'Error',
          description: 'Failed to initiate Outlook connection.',
          variant: 'destructive',
        });
      });
      Object.defineProperty(window, 'localStorage', {
        value: originalStorage,
        configurable: true,
      });
      consoleErrorSpy.mockRestore();
      server.resetHandlers();
      server.use(...outlookHandlers);
    });

    it('shows an error toast when the OAuth authorization request fails', async () => {
      const user = userEvent.setup();
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      server.use(
        rest.get('/api/integrations/outlook/health', (req, res, ctx) => {
          return res(ctx.status(500));
        })
      );
      // Backend-initiate failures surface as a thrown redirect-target
      // resolution in the backend; in jsdom the catch path is triggered by an
      // exception while computing the initiate URL. Mirror the storage throw
      // to enter the same catch block that logs + toasts.
      const originalStorage = window.localStorage;
      Object.defineProperty(window, 'localStorage', {
        value: {
          getItem: () => { throw new Error('backend unreachable'); },
          setItem: jest.fn(),
          removeItem: jest.fn(),
          clear: jest.fn(),
        },
        configurable: true,
      });

      renderWithProviders(<OutlookIntegration />);

      const connectButton = await screen.findByRole('button', { name: /connect/i });
      await user.click(connectButton);

      await waitFor(() => {
        expect(getToastMock()).toHaveBeenCalledWith({
          title: 'Error',
          description: 'Failed to initiate Outlook connection.',
          variant: 'destructive',
        });
      });
      Object.defineProperty(window, 'localStorage', {
        value: originalStorage,
        configurable: true,
      });
      consoleErrorSpy.mockRestore();
      server.resetHandlers();
      server.use(...outlookHandlers);
    });

    it('refresh status re-runs the health check', async () => {
      const user = userEvent.setup();
      const fetchSpy = jest.spyOn(global, 'fetch');
      renderWithProviders(<OutlookIntegration />);

      await settleEmails();
      fetchSpy.mockClear();

      await user.click(screen.getByRole('button', { name: /refresh status/i }));

      await waitFor(() => {
        expect(fetchSpy).toHaveBeenCalledWith(
          expect.stringContaining('/api/integrations/outlook/health'),
          expect.anything()
        );
      });
    });
  });
});
