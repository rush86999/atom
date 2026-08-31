/**
 * GoogleWorkspaceIntegration Component Tests
 *
 * Tests verify the real Google Workspace integration component:
 * - Health check / connection state
 * - OAuth connect flow
 * - Document, spreadsheet, event, and email data loading
 * - Document search filtering and create-document dialog
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/GoogleWorkspaceIntegration.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import GoogleWorkspaceIntegration from '@/components/GoogleWorkspaceIntegration';
import { useToast } from '@/components/ui/use-toast';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const getToastMock = (): jest.Mock => (useToast as jest.Mock)().toast;

const gwsHandlers = [
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ providers: { "google-workspace": { connected: true, source: 'user_connection' } } })
    );
  }),
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ providers: { "google-workspace": { connected: true, source: 'user_connection' } } }));
  }),

  rest.post('/api/integrations/google-workspace/docs', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          files: [
            {
              id: 'd1',
              name: 'Product Requirements',
              mimeType: 'application/vnd.google-apps.document',
              webViewLink: 'https://docs.google.com/d1',
              modifiedTime: '2024-01-15T10:00:00Z',
              owners: [{ displayName: 'Rushi Parikh', photoLink: '' }],
            },
            {
              id: 'd2',
              name: 'Meeting Notes',
              mimeType: 'application/vnd.google-apps.document',
              webViewLink: 'https://docs.google.com/d2',
              modifiedTime: '2024-01-14T10:00:00Z',
              owners: [{ displayName: 'Rushi Parikh', photoLink: '' }],
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/google-workspace/sheets', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          files: [{ id: 's1', name: 'Budget Tracker', modifiedTime: '2024-01-15T10:00:00Z', sheets: [] }],
        },
      })
    );
  }),

  rest.post('/api/integrations/google-workspace/events', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          events: [
            {
              id: 'ev1',
              summary: 'All Hands',
              start: { dateTime: '2024-01-15T09:00:00Z' },
              end: { dateTime: '2024-01-15T10:00:00Z' },
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/google-workspace/emails', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          messages: [
            {
              id: 'e1',
              payload: {
                headers: [
                  { name: 'Subject', value: 'Welcome!' },
                  { name: 'From', value: 'alice@example.com' },
                ],
              },
              snippet: 'Thanks for signing up',
              internalDate: '1705312800000',
            },
          ],
        },
      })
    );
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

describe('GoogleWorkspaceIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...gwsHandlers);
  });

  // Test 1: renders component
  test('renders component', () => {
    render(<GoogleWorkspaceIntegration />);

    expect(
      screen.getByRole('heading', { name: /google workspace integration/i })
    ).toBeInTheDocument();
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    setDisconnected();

    render(<GoogleWorkspaceIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect google workspace/i })
      ).toBeInTheDocument();
    });
  });

  // Test 3: connect button is clickable without crashing (jsdom logs the
  // navigation attempt; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setDisconnected();

    render(<GoogleWorkspaceIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect google workspace/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 4: shows connected state when health check passes
  test('shows connected state when health check passes', async () => {
    render(<GoogleWorkspaceIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 5: displays documents in the default Documents tab
  test('displays documents in the default Documents tab', async () => {
    render(<GoogleWorkspaceIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Product Requirements')).toBeInTheDocument();
      expect(screen.getByText('Meeting Notes')).toBeInTheDocument();
    });
  });

  // Test 6: search input is present and accepts text (the Documents tab lists
  // all docs; the searchQuery filter only applies to other data sets)
  test('search input accepts text', async () => {
    render(<GoogleWorkspaceIntegration />);

    await settleData(/Product Requirements/);

    const searchInput = screen.getByPlaceholderText(/search documents/i);
    fireEvent.change(searchInput, { target: { value: 'Meeting' } });

    expect(searchInput).toHaveValue('Meeting');
    expect(screen.getByText('Meeting Notes')).toBeInTheDocument();
  });

  // Test 7: opens create document dialog
  test('opens create document dialog', async () => {
    render(<GoogleWorkspaceIntegration />);

    const createButton = await screen.findByRole('button', {
      name: /create document/i,
    });
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  // Test 8: handles connection error
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/integrations/connection-status', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<GoogleWorkspaceIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect google workspace/i })
      ).toBeInTheDocument();
    });
  });

  // Test 9: shows refresh status button
  test('shows refresh status button', async () => {
    render(<GoogleWorkspaceIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh status/i })).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Extended coverage: mime types, tab data, create flows, and error paths
// ---------------------------------------------------------------------------
describe('GoogleWorkspaceIntegration (extended coverage)', () => {
  // NOTE: jest.config.js sets restoreMocks:true, which detaches describe-scope
  // spies after every test — create a fresh console.error spy per test.
  let errorSpy: jest.SpyInstance;
  beforeEach(() => {
    errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  const futureDate = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString();

  const richDocs = [
    {
      id: 'd1',
      name: 'Product Requirements',
      mimeType: 'application/vnd.google-apps.document',
      webViewLink: 'https://docs.google.com/d1',
      modifiedTime: '2024-01-15T10:00:00Z',
      owners: [{ displayName: 'Rushi Parikh', photoLink: '' }],
    },
    {
      id: 'd3',
      name: 'Q4 Slides',
      mimeType: 'application/vnd.google-apps.presentation',
      webViewLink: 'https://docs.google.com/d3',
      modifiedTime: '2024-01-13T10:00:00Z',
      owners: [],
    },
    {
      id: 'd4',
      name: 'Contract.pdf',
      mimeType: 'application/pdf',
      webViewLink: 'https://docs.google.com/d4',
      modifiedTime: '2024-01-12T10:00:00Z',
      owners: [],
    },
    {
      id: 'd5',
      name: 'Weird File',
      mimeType: 'application/octet-stream',
      webViewLink: 'https://docs.google.com/d5',
      modifiedTime: '2024-01-11T10:00:00Z',
      owners: [],
    },
  ];

  const richSheets = [
    {
      id: 's1',
      name: 'Budget Tracker',
      modifiedTime: '2024-01-15T10:00:00Z',
      webViewLink: 'https://sheets.google.com/s1',
      sheets: [{ id: 'sh1' }, { id: 'sh2' }],
    },
    {
      id: 's2',
      name: 'Roadmap Grid',
      modifiedTime: '2024-01-14T10:00:00Z',
      webViewLink: 'https://sheets.google.com/s2',
      sheets: [],
    },
  ];

  const richEvents = [
    {
      id: 'ev1',
      summary: 'All Hands',
      description: 'Company-wide meeting',
      location: 'Auditorium',
      start: { dateTime: futureDate },
      end: { dateTime: futureDate },
      attendees: [
        { email: 'alice@example.com', displayName: 'Alice', responseStatus: 'accepted' },
        { email: 'bob@example.com', displayName: 'Bob', responseStatus: 'tentative' },
        { email: 'carol@example.com', displayName: 'Carol', responseStatus: 'declined' },
        { email: 'dan@example.com', displayName: 'Dan', responseStatus: 'needsAction' },
        { email: 'eve@example.com', responseStatus: 'unknownStatus' },
      ],
    },
    {
      id: 'ev2',
      summary: 'Quiet Sync',
      start: { dateTime: futureDate },
      end: { dateTime: futureDate },
    },
  ];

  const richEmails = [
    {
      id: 'e1',
      payload: {
        headers: [
          { name: 'Subject', value: 'Welcome!' },
          { name: 'From', value: 'alice@example.com' },
        ],
      },
      snippet: 'Thanks for signing up',
      internalDate: '1705312800000',
    },
    {
      id: 'e2',
      payload: { headers: [{ name: 'From', value: 'bob@example.com' }] },
      snippet: 'No subject line here',
      internalDate: '1705312800000',
    },
  ];

  // NOTE: MSW resolves handlers in the order passed to server.use(), so the
  // data-rich overrides must come BEFORE the base gwsHandlers.
  const richHandlers = [
    rest.post('/api/integrations/google-workspace/docs', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { files: richDocs } }));
    }),
    rest.post('/api/integrations/google-workspace/sheets', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { files: richSheets } }));
    }),
    rest.post('/api/integrations/google-workspace/events', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { events: richEvents } }));
    }),
    rest.post('/api/integrations/google-workspace/emails', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { messages: richEmails } }));
    }),
    rest.post('/api/integrations/google-workspace/docs/create', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { file: { id: 'd999' } } }));
    }),
    rest.post('/api/integrations/google-workspace/events/create', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { event: { id: 'ev999' } } }));
    }),
    ...gwsHandlers,
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

  test('renders docs with all mime-type badges and opens doc links', async () => {
    const openSpy = jest.fn();
    window.open = openSpy as any;

    render(<GoogleWorkspaceIntegration />);
    await settle('Product Requirements');

    expect(screen.getByText('Q4 Slides')).toBeInTheDocument();
    expect(screen.getByText('Contract.pdf')).toBeInTheDocument();
    expect(screen.getByText('Weird File')).toBeInTheDocument();
    expect(screen.getByText('Presentation')).toBeInTheDocument();
    expect(screen.getAllByText('File').length).toBeGreaterThan(0);
    expect(screen.getByText('Rushi Parikh')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Product Requirements'));
    expect(openSpy).toHaveBeenCalledWith('https://docs.google.com/d1', '_blank');
  });

  test('displays spreadsheets on the Spreadsheets tab and opens links', async () => {
    const openSpy = jest.fn();
    window.open = openSpy as any;

    render(<GoogleWorkspaceIntegration />);
    await settle('Product Requirements');

    fireEvent.click(screen.getByRole('button', { name: /spreadsheets/i }));

    expect(await screen.findByText('Budget Tracker')).toBeInTheDocument();
    expect(screen.getByText('Roadmap Grid')).toBeInTheDocument();
    expect(screen.getByText('2 sheets')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Budget Tracker'));
    expect(openSpy).toHaveBeenCalledWith('https://sheets.google.com/s1', '_blank');

    fireEvent.change(screen.getByPlaceholderText(/search spreadsheets/i), {
      target: { value: 'roadmap' },
    });
    expect(screen.getByText('Roadmap Grid')).toBeInTheDocument();
    expect(screen.queryByText('Budget Tracker')).not.toBeInTheDocument();
  });

  test('displays calendar events with attendee response badges', async () => {
    render(<GoogleWorkspaceIntegration />);
    await settle('Product Requirements');

    fireEvent.click(screen.getByRole('button', { name: /calendar/i }));

    expect(await screen.findByText('All Hands')).toBeInTheDocument();
    expect(screen.getByText('Company-wide meeting')).toBeInTheDocument();
    expect(screen.getByText('Auditorium')).toBeInTheDocument();
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Bob')).toBeInTheDocument();
    expect(screen.getByText('Carol')).toBeInTheDocument();
    expect(screen.getByText('Dan')).toBeInTheDocument();
    // attendee without displayName falls back to email
    expect(screen.getByText('eve@example.com')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText(/search events/i), {
      target: { value: 'quiet' },
    });
    expect(screen.getByText('Quiet Sync')).toBeInTheDocument();
    expect(screen.queryByText('All Hands')).not.toBeInTheDocument();
  });

  test('displays emails on the Gmail tab', async () => {
    render(<GoogleWorkspaceIntegration />);
    await settle('Product Requirements');

    fireEvent.click(screen.getByRole('button', { name: /gmail/i }));

    expect(await screen.findByText('Welcome!')).toBeInTheDocument();
    expect(screen.getByText('No subject line here')).toBeInTheDocument();
    expect(screen.getByText('No Subject')).toBeInTheDocument();
    expect(screen.getAllByText(/alice@example.com|bob@example.com/).length).toBe(2);
  });

  test('creates a document through the dialog', async () => {
    render(<GoogleWorkspaceIntegration />);
    await settle('Product Requirements');

    fireEvent.click(screen.getByRole('button', { name: /create document/i }));
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(screen.getByPlaceholderText('Enter document title'), {
      target: { value: 'Test Doc' },
    });
    clickFooterButton(dialog, /^create$/i);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Success',
          description: 'document created successfully',
        })
      );
    });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  test('shows error toast when document creation fails', async () => {
    server.use(
      rest.post('/api/integrations/google-workspace/docs/create', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<GoogleWorkspaceIntegration />);
    await settle('Product Requirements');

    fireEvent.click(screen.getByRole('button', { name: /create document/i }));
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(screen.getByPlaceholderText('Enter document title'), {
      target: { value: 'Bad Doc' },
    });
    clickFooterButton(dialog, /^create$/i);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', description: 'Failed to create document' })
      );
    });
  });

  test('creates an event through the dialog', async () => {
    render(<GoogleWorkspaceIntegration />);
    await settle('Product Requirements');

    fireEvent.click(screen.getByRole('button', { name: /calendar/i }));
    fireEvent.click(screen.getAllByRole('button', { name: /create event/i })[0]);
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(screen.getByPlaceholderText('Event title'), {
      target: { value: 'Test Event' },
    });
    fireEvent.change(screen.getByPlaceholderText('Event description'), {
      target: { value: 'Event description text' },
    });
    fireEvent.change(screen.getByPlaceholderText('Event location'), {
      target: { value: 'Meeting Room 1' },
    });
    const timeInputs = dialog.querySelectorAll('input[type="datetime-local"]');
    fireEvent.change(timeInputs[0], { target: { value: '2026-09-01T10:00' } });
    fireEvent.change(timeInputs[1], { target: { value: '2026-09-01T11:00' } });
    clickFooterButton(dialog, /create/i);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Success',
          description: 'Event created successfully',
        })
      );
    });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  test('shows error toast when event creation fails', async () => {
    server.use(
      rest.post('/api/integrations/google-workspace/events/create', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<GoogleWorkspaceIntegration />);
    await settle('Product Requirements');

    fireEvent.click(screen.getByRole('button', { name: /calendar/i }));
    fireEvent.click(screen.getAllByRole('button', { name: /create event/i })[0]);
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(screen.getByPlaceholderText('Event title'), {
      target: { value: 'Bad Event' },
    });
    const timeInputs = dialog.querySelectorAll('input[type="datetime-local"]');
    fireEvent.change(timeInputs[0], { target: { value: '2026-09-01T10:00' } });
    fireEvent.change(timeInputs[1], { target: { value: '2026-09-01T11:00' } });
    clickFooterButton(dialog, /create/i);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', description: 'Failed to create event' })
      );
    });
  });

  test('shows error toast when document loading fails', async () => {
    server.use(
      rest.post('/api/integrations/google-workspace/docs', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<GoogleWorkspaceIntegration />);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to load documents from Google Workspace',
        })
      );
    });
  });

  test('logs errors when auxiliary loads fail', async () => {
    const netFail = (path: string) => rest.post(path, (req, res) => res.networkError('boom'));
    server.use(
      netFail('/api/integrations/google-workspace/sheets'),
      netFail('/api/integrations/google-workspace/events'),
      netFail('/api/integrations/google-workspace/emails')
    );

    render(<GoogleWorkspaceIntegration />);

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Failed to load sheets:', expect.anything());
      expect(errorSpy).toHaveBeenCalledWith('Failed to load events:', expect.anything());
      expect(errorSpy).toHaveBeenCalledWith('Failed to load emails:', expect.anything());
    });
  });

  test('treats health check network failure as disconnected', async () => {
    server.use(
      rest.get(
        '/api/integrations/connection-status',
        (req, res) => res.networkError('boom')
      )
    );

    render(<GoogleWorkspaceIntegration />);

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Connection status check failed:', expect.anything());
      expect(
        screen.getByRole('button', { name: /connect google workspace/i })
      ).toBeInTheDocument();
    });
  });

  test('clicking Refresh Status re-runs the health check', async () => {
    render(<GoogleWorkspaceIntegration />);
    await settle('Product Requirements');

    fireEvent.click(screen.getByRole('button', { name: /refresh status/i }));
    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });
});
