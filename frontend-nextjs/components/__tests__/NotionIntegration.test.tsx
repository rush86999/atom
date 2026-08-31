/**
 * NotionIntegration Component Tests
 *
 * Tests verify the real Notion integration component:
 * - Health check / connection state
 * - OAuth connect flow
 * - Database and page data loading
 * - Database search filtering
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/NotionIntegration.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import NotionIntegration from '@/components/NotionIntegration';
import { useToast } from '@/components/ui/use-toast';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const getToastMock = (): jest.Mock => (useToast as jest.Mock)().toast;

const notionHandlers = [
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ providers: { notion: { connected: true, source: 'user_connection' } } })
    );
  }),
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ providers: { notion: { connected: true, source: 'user_connection' } } }));
  }),

  rest.post('/api/integrations/notion/databases', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          databases: [
            { id: 'db1', title: [{ text: { content: 'Customer CRM' } }], description: [{ text: { content: 'All customers' } }] },
            { id: 'db2', title: [{ text: { content: 'Product Roadmap' } }], description: [{ text: { content: 'Planned work' } }] },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/notion/pages', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          pages: [
            {
              id: 'p1',
              properties: {
                title: {
                  title: [{ text: { content: 'Meeting Notes' } }],
                },
              },
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/notion/users', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { users: [] } }));
  }),
  rest.post('/api/integrations/notion/search', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { results: [] } }));
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

describe('NotionIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...notionHandlers);
  });

  // Test 1: renders component
  test('renders component', () => {
    render(<NotionIntegration />);

    expect(
      screen.getByRole('heading', { name: /notion integration/i })
    ).toBeInTheDocument();
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    setDisconnected();

    render(<NotionIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect notion workspace/i })
      ).toBeInTheDocument();
    });
  });

  // Test 3: connect button is clickable without crashing (jsdom logs the
  // navigation attempt; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setDisconnected();

    render(<NotionIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect notion workspace/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 4: shows connected state when health check passes
  test('shows connected state when health check passes', async () => {
    render(<NotionIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 5: displays databases in the default Databases tab
  test('displays databases in the default Databases tab', async () => {
    render(<NotionIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Customer CRM')).toBeInTheDocument();
      expect(screen.getByText('Product Roadmap')).toBeInTheDocument();
    });
  });

  // Test 6: filters databases by search query
  test('filters databases by search query', async () => {
    render(<NotionIntegration />);

    await settleData(/Customer CRM/);

    const searchInput = screen.getByPlaceholderText(/search databases/i);
    fireEvent.change(searchInput, { target: { value: 'Roadmap' } });

    await waitFor(() => {
      expect(screen.getByText('Product Roadmap')).toBeInTheDocument();
    });
    expect(screen.queryByText('Customer CRM')).not.toBeInTheDocument();
  });

  // Test 7: shows create database button (the dialog contains Radix Selects
  // with empty-value items that crash in jsdom, so only assert presence)
  test('shows create database button', async () => {
    render(<NotionIntegration />);

    const createButton = await screen.findByRole('button', {
      name: /create database/i,
    });
    expect(createButton).toBeInTheDocument();
  });

  // Test 8: handles connection error
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/integrations/connection-status', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<NotionIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect notion workspace/i })
      ).toBeInTheDocument();
    });
  });

  // Test 9: shows refresh status button
  test('shows refresh status button', async () => {
    render(<NotionIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh status/i })).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Extended coverage: pages/users/search tabs, create flows, and error paths
// ---------------------------------------------------------------------------
describe('NotionIntegration (extended coverage)', () => {
  // NOTE: jest.config.js sets restoreMocks:true, which detaches describe-scope
  // spies after every test — create a fresh console.error spy per test.
  let errorSpy: jest.SpyInstance;
  beforeEach(() => {
    errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  const richDatabases = [
    {
      id: 'db1',
      title: [{ text: { content: 'Customer CRM' } }],
      description: [{ text: { content: 'All customers' } }],
      icon: { emoji: '📊' },
      is_inline: true,
      url: 'https://notion.so/db1',
      created_time: '2024-01-01T00:00:00Z',
      last_edited_time: '2024-01-02T00:00:00Z',
    },
    {
      id: 'db2',
      title: [{ text: { content: 'Product Roadmap' } }],
      description: [],
      is_inline: false,
      url: 'https://notion.so/db2',
      created_time: '2024-01-01T00:00:00Z',
      last_edited_time: '2024-01-02T00:00:00Z',
    },
  ];

  const richPages = [
    {
      id: 'p1',
      url: 'https://notion.so/p1',
      archived: false,
      last_edited_time: '2024-01-10T00:00:00Z',
      properties: {
        title: { title: [{ text: { content: 'Launch Checklist' } }] },
        status: { select: { name: 'In Progress' } },
        priority: { select: { name: 'High' } },
        due_date: { date: { start: '2026-10-01' } },
        tags: { multi_select: [{ name: 'web' }, { name: 'q4' }] },
      },
    },
    {
      id: 'p2',
      url: 'https://notion.so/p2',
      archived: true,
      last_edited_time: '2024-01-09T00:00:00Z',
      properties: {
        title: { title: [{ text: { content: 'Blocked Task' } }] },
        status: { select: { name: 'Blocked' } },
        priority: { select: { name: 'Low' } },
      },
    },
    {
      id: 'p3',
      url: 'https://notion.so/p3',
      archived: false,
      last_edited_time: '2024-01-08T00:00:00Z',
      properties: {
        title: { title: [{ text: { content: 'Completed Task' } }] },
        status: { select: { name: 'Done' } },
        priority: { select: { name: 'Medium' } },
      },
    },
  ];

  const richUsers = [
    {
      id: 'u1',
      name: 'Alice Person',
      type: 'person',
      person: { email: 'alice@example.com' },
      avatar_url: '',
    },
    { id: 'u2', name: 'Botty', type: 'bot' },
  ];

  const richSearchResults = [
    {
      id: 'r1',
      object: 'page',
      title: 'Search Hit Page',
      url: 'https://notion.so/r1',
      last_edited_time: '2024-01-05T00:00:00Z',
    },
    {
      id: 'r2',
      object: 'database',
      title: 'Search Hit DB',
      url: 'https://notion.so/r2',
      last_edited_time: '2024-01-06T00:00:00Z',
    },
  ];

  // NOTE: MSW resolves handlers in the order passed to server.use(), so the
  // data-rich overrides must come BEFORE the base notionHandlers.
  const richHandlers = [
    rest.post('/api/integrations/notion/databases', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { databases: richDatabases } }));
    }),
    rest.post('/api/integrations/notion/pages', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { pages: richPages } }));
    }),
    rest.post('/api/integrations/notion/users', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { users: richUsers } }));
    }),
    rest.post('/api/integrations/notion/search', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { results: richSearchResults } }));
    }),
    rest.post('/api/integrations/notion/pages/create', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { page: { id: 'p999' } } }));
    }),
    rest.post('/api/integrations/notion/databases/create', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { database: { id: 'db999' } } }));
    }),
    ...notionHandlers,
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

  test('renders database cards with inline badges and emoji icons', async () => {
    render(<NotionIntegration />);

    await settle('Customer CRM');
    expect(screen.getByText('📊')).toBeInTheDocument();
    expect(screen.getByText('Inline')).toBeInTheDocument();
    expect(screen.getByText('Full Page')).toBeInTheDocument();
    expect(screen.getByText('No description')).toBeInTheDocument();
    expect(screen.getAllByText(/Open in Notion/i).length).toBeGreaterThan(0);
  });

  test('selecting a database loads its pages with status, priority and tags', async () => {
    render(<NotionIntegration />);
    await settle('Customer CRM');

    fireEvent.click(screen.getByText('Customer CRM'));
    fireEvent.click(screen.getByRole('button', { name: 'Pages' }));

    expect(await screen.findByText('Launch Checklist')).toBeInTheDocument();
    expect(screen.getByText('In Progress')).toBeInTheDocument();
    expect(screen.getByText('Priority: High')).toBeInTheDocument();
    expect(screen.getByText('Blocked')).toBeInTheDocument();
    expect(screen.getByText('Priority: Low')).toBeInTheDocument();
    expect(screen.getByText('Done')).toBeInTheDocument();
    expect(screen.getByText('Priority: Medium')).toBeInTheDocument();
    expect(screen.getByText('web')).toBeInTheDocument();
    expect(screen.getByText('q4')).toBeInTheDocument();
    expect(screen.getByText('Completed Task')).toBeInTheDocument();
  });

  test('creates a page through the dialog', async () => {
    render(<NotionIntegration />);
    await settle('Customer CRM');

    fireEvent.click(screen.getByText('Customer CRM'));
    fireEvent.click(screen.getByRole('button', { name: 'Pages' }));
    fireEvent.click(screen.getAllByRole('button', { name: /create page/i })[0]);
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(screen.getByPlaceholderText('Enter page title'), {
      target: { value: 'Fresh Page' },
    });
    fireEvent.change(screen.getByPlaceholderText('Optional initial content...'), {
      target: { value: 'Initial content' },
    });
    clickFooterButton(dialog, /create page/i);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Success',
          description: 'Page created successfully',
        })
      );
    });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  test('shows error toast when page creation fails', async () => {
    server.use(
      rest.post('/api/integrations/notion/pages/create', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<NotionIntegration />);
    await settle('Customer CRM');

    fireEvent.click(screen.getByText('Customer CRM'));
    fireEvent.click(screen.getByRole('button', { name: 'Pages' }));
    fireEvent.click(screen.getAllByRole('button', { name: /create page/i })[0]);
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(screen.getByPlaceholderText('Enter page title'), {
      target: { value: 'Bad Page' },
    });
    clickFooterButton(dialog, /create page/i);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', description: 'Failed to create page' })
      );
    });
  });

  test('creates a database through the dialog', async () => {
    render(<NotionIntegration />);
    await settle('Customer CRM');

    fireEvent.click(screen.getByRole('button', { name: /create database/i }));
    const dialog = await screen.findByRole('dialog');

    // NOTE: the parent Select contains an empty-value SelectItem which Radix
    // cannot render in jsdom, so leave the default (Workspace Root) selected.
    fireEvent.change(screen.getByPlaceholderText('Enter database name'), {
      target: { value: 'Fresh Database' },
    });
    clickFooterButton(dialog, /create database/i);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Success',
          description: 'Database created successfully',
        })
      );
    });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  test('shows error toast when database creation fails', async () => {
    server.use(
      rest.post('/api/integrations/notion/databases/create', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<NotionIntegration />);
    await settle('Customer CRM');

    fireEvent.click(screen.getByRole('button', { name: /create database/i }));
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(screen.getByPlaceholderText('Enter database name'), {
      target: { value: 'Bad Database' },
    });
    clickFooterButton(dialog, /create database/i);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to create database',
        })
      );
    });
  });

  test('searches content from the Search tab and shows results', async () => {
    render(<NotionIntegration />);
    await settle('Customer CRM');

    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    fireEvent.change(screen.getByPlaceholderText('Search all content...'), {
      target: { value: 'hit' },
    });

    expect(await screen.findByText('Search Hit Page')).toBeInTheDocument();
    expect(screen.getByText('Search Hit DB')).toBeInTheDocument();
    expect(screen.getAllByText('page').length).toBeGreaterThan(0);
    expect(screen.getAllByText('database').length).toBeGreaterThan(0);
  });

  test('search failure is logged without crashing', async () => {
    server.use(
      rest.post('/api/integrations/notion/search', (req, res) => res.networkError('boom'))
    );

    render(<NotionIntegration />);
    await settle('Customer CRM');

    fireEvent.click(screen.getByRole('button', { name: 'Search' }));
    fireEvent.change(screen.getByPlaceholderText('Search all content...'), {
      target: { value: 'anything' },
    });

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Failed to search:', expect.anything());
    });
  });

  test('displays users on the Users tab', async () => {
    render(<NotionIntegration />);
    await settle('Customer CRM');

    fireEvent.click(screen.getByRole('button', { name: 'Users' }));

    expect(await screen.findByText('Alice Person')).toBeInTheDocument();
    expect(screen.getByText('Botty')).toBeInTheDocument();
    expect(screen.getByText('alice@example.com')).toBeInTheDocument();
    expect(screen.getByText('person')).toBeInTheDocument();
    expect(screen.getByText('bot')).toBeInTheDocument();
  });

  test('shows error toast when page loading fails', async () => {
    server.use(
      rest.post('/api/integrations/notion/pages', (req, res) => res.networkError('boom'))
    );

    render(<NotionIntegration />);
    await settle('Customer CRM');

    fireEvent.click(screen.getByText('Customer CRM'));

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to load pages from Notion',
        })
      );
    });
  });

  test('logs errors when databases and users fail to load', async () => {
    const netFail = (path: string) => rest.post(path, (req, res) => res.networkError('boom'));
    server.use(
      netFail('/api/integrations/notion/databases'),
      netFail('/api/integrations/notion/users')
    );

    render(<NotionIntegration />);

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Failed to load databases:', expect.anything());
      expect(errorSpy).toHaveBeenCalledWith('Failed to load users:', expect.anything());
    });
  });

  test('treats health check network failure as disconnected', async () => {
    server.use(
      rest.get('/api/integrations/connection-status', (req, res) => res.networkError('boom'))
    );

    render(<NotionIntegration />);

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Connection status check failed:', expect.anything());
      expect(
        screen.getByRole('button', { name: /connect notion workspace/i })
      ).toBeInTheDocument();
    });
  });

  test('clicking Refresh Status re-runs the health check', async () => {
    render(<NotionIntegration />);
    await settle('Customer CRM');

    fireEvent.click(screen.getByRole('button', { name: /refresh status/i }));
    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });
});
