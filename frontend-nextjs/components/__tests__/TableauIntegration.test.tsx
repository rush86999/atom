/**
 * TableauIntegration Component Tests
 *
 * Tests verify the real Tableau integration component
 * (components/TableauIntegration.tsx):
 * - Connection status (GET /api/v1/tableau/health)
 * - Connect modal flow (handleConnect)
 * - Workbooks, datasources, views, projects, user profile rendering
 * - Dashboard stats and analytics panels
 * - Search and empty-data resilience
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts.
 */

import React from 'react';
import { renderWithProviders, screen, waitFor, within } from '../../tests/test-utils';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../tests/mocks/server';
import TableauIntegration from '../TableauIntegration';

const workbooks = [
  {
    id: 'wb1',
    name: 'Revenue Dashboard',
    description: 'Quarterly revenue overview',
    project_id: 'proj1',
    owner_id: 'u1',
    created_at: '2025-01-01T10:00:00Z',
    updated_at: '2026-01-05T10:00:00Z',
    content_url: 'https://tableau.example/views/Revenue',
    show_tabs: true,
    size: 2097152,
    tags: ['finance'],
  },
];

const datasources = [
  {
    id: 'ds1',
    name: 'Sales Warehouse',
    description: 'ETL from the sales DB',
    project_id: 'proj1',
    owner_id: 'u1',
    created_at: '2025-01-01T10:00:00Z',
    updated_at: '2026-01-01T10:00:00Z',
    content_url: '',
    has_extracts: true,
    is_certified: true,
    tags: ['sales'],
  },
];

const views = [
  {
    id: 'v1',
    name: 'Q1 Revenue by Region',
    content_url: 'https://tableau.example/views/Q1Revenue',
    created_at: '2026-01-01T10:00:00Z',
    updated_at: '2026-01-01T10:00:00Z',
    owner_id: 'u1',
    workbook_id: 'wb1',
    view_url_name: 'Q1RevenueByRegion',
    tags: ['revenue'],
  },
];

const projects = [
  {
    id: 'proj1',
    name: 'Executive Reporting',
    description: 'C-suite dashboards',
    parent_project_id: undefined,
    owner_id: 'u1',
    created_at: '2025-01-01T10:00:00Z',
    updated_at: '2025-01-01T10:00:00Z',
  },
];

const userProfile = {
  id: 'u1',
  email: 'analyst@example.com',
  name: 'Dana Analyst',
  site_role: 'Creator',
  last_login: '2026-01-04T10:00:00Z',
  external_auth_user_id: undefined,
};

const connectedHandlers = [
  rest.get('/api/v1/tableau/health', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, status: 'healthy' }));
  }),
  rest.get('/api/v1/tableau/workbooks', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, data: workbooks }));
  }),
  rest.get('/api/v1/tableau/datasources', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, data: datasources }));
  }),
  rest.get('/api/v1/tableau/views', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, data: views }));
  }),
  rest.get('/api/v1/tableau/projects', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, data: projects }));
  }),
  rest.get('/api/v1/tableau/user', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, data: userProfile }));
  }),
];

const setDisconnected = (status = 503) => {
  server.use(
    rest.get('/api/v1/tableau/health', (req, res, ctx) => {
      return res(ctx.status(status), ctx.json({ error: 'not connected' }));
    })
  );
};

describe('TableauIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
  });

  test('shows connect screen when not connected', async () => {
    setDisconnected();

    renderWithProviders(<TableauIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /connect tableau/i })
      ).toBeInTheDocument();
    });
    expect(
      screen.getByRole('button', { name: /connect tableau/i })
    ).toBeInTheDocument();
  });

  test('connects from the modal and renders the dashboard', async () => {
    const user = userEvent.setup();

    // Stateful health: disconnected at mount, healthy after connect reload
    let healthOk = false;
    server.use(
      rest.get('/api/v1/tableau/health', (req, res, ctx) => {
        return res(ctx.status(healthOk ? 200 : 503), ctx.json({ success: true }));
      }),
      rest.get('/api/v1/tableau/workbooks', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: workbooks }));
      }),
      rest.get('/api/v1/tableau/datasources', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: datasources }));
      }),
      rest.get('/api/v1/tableau/views', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: views }));
      }),
      rest.get('/api/v1/tableau/projects', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: projects }));
      }),
      rest.get('/api/v1/tableau/user', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: userProfile }));
      })
    );

    renderWithProviders(<TableauIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect tableau/i,
    });
    await user.click(connectButton);

    const dialogContent = document.getElementById('dialog-content') as HTMLElement;
    await waitFor(() => {
      expect(
        within(dialogContent).getByText(/you'll be able to/i)
      ).toBeInTheDocument();
    });

    healthOk = true;
    await user.click(
      within(dialogContent).getByRole('button', { name: /connect tableau/i })
    );

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Tableau' })).toBeInTheDocument();
    });
  });

  test('renders dashboard stats, recent workbooks, and account info', async () => {
    server.use(...connectedHandlers);

    renderWithProviders(<TableauIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Tableau' })).toBeInTheDocument();
    });

    // Dashboard stat cards
    await waitFor(() => {
      expect(screen.getByText('Total Workbooks')).toBeInTheDocument();
    });
    expect(screen.getByText('Total Views')).toBeInTheDocument();
    expect(screen.getByText('2 MB')).toBeInTheDocument();

    // Recent workbooks table (dashboard tab)
    expect(screen.getByText('Revenue Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Executive Reporting')).toBeInTheDocument();

    // Account information card
    expect(screen.getByText('Dana Analyst')).toBeInTheDocument();
    expect(screen.getByText('analyst@example.com')).toBeInTheDocument();
    expect(screen.getByText('Creator')).toBeInTheDocument();
  });

  test('renders the workbooks tab with project and size columns', async () => {
    const user = userEvent.setup();
    const openSpy = jest.spyOn(window, 'open').mockImplementation(() => null);

    server.use(...connectedHandlers);

    renderWithProviders(<TableauIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Tableau' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /workbooks/i }));

    await waitFor(() => {
      expect(screen.getByText('Workbooks (1)')).toBeInTheDocument();
    });
    expect(screen.getByText('Quarterly revenue overview')).toBeInTheDocument();

    // Eye button opens the workbook content URL
    const eyeButton = screen
      .getAllByRole('button')
      .find((b) => b.querySelector('svg.lucide-eye')) as HTMLElement;
    await user.click(eyeButton);
    await waitFor(() => {
      expect(openSpy).toHaveBeenCalledWith(
        'https://tableau.example/views/Revenue',
        '_blank'
      );
    });

    openSpy.mockRestore();
  });

  test('renders datasources with certification and extract badges', async () => {
    const user = userEvent.setup();

    server.use(...connectedHandlers);

    renderWithProviders(<TableauIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Tableau' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /datasources/i }));

    await waitFor(() => {
      expect(screen.getByText('Sales Warehouse')).toBeInTheDocument();
    });
    expect(screen.getByText('Certified')).toBeInTheDocument();
    expect(screen.getByText('Has Extracts')).toBeInTheDocument();
    expect(screen.getByText('ETL from the sales DB')).toBeInTheDocument();
  });

  test('renders views with workbook linkage and opens the view URL', async () => {
    const user = userEvent.setup();
    const openSpy = jest.spyOn(window, 'open').mockImplementation(() => null);

    server.use(...connectedHandlers);

    renderWithProviders(<TableauIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Tableau' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /views/i }));

    await waitFor(() => {
      expect(screen.getByText('Q1 Revenue by Region')).toBeInTheDocument();
    });
    expect(screen.getByText('Q1RevenueByRegion')).toBeInTheDocument();
    // Workbook name badge resolves via workbook_id
    expect(screen.getByText('Revenue Dashboard')).toBeInTheDocument();

    const eyeButton = screen
      .getAllByRole('button')
      .find((b) => b.querySelector('svg.lucide-eye')) as HTMLElement;
    await user.click(eyeButton);
    await waitFor(() => {
      expect(openSpy).toHaveBeenCalledWith(
        'https://tableau.example/views/Q1Revenue',
        '_blank'
      );
    });

    openSpy.mockRestore();
  });

  test('renders projects and analytics panels', async () => {
    const user = userEvent.setup();

    server.use(...connectedHandlers);

    renderWithProviders(<TableauIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Tableau' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /projects/i }));

    await waitFor(() => {
      expect(screen.getByText('Executive Reporting')).toBeInTheDocument();
    });
    expect(screen.getByText('C-suite dashboards')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /analytics/i }));

    await waitFor(() => {
      expect(screen.getByText('Content Distribution')).toBeInTheDocument();
    });
    expect(screen.getByText('Storage Usage')).toBeInTheDocument();
    expect(screen.getByText('User Information')).toBeInTheDocument();
    expect(screen.getByText('Dana Analyst')).toBeInTheDocument();
    expect(screen.getByText('analyst@example.com')).toBeInTheDocument();
  });

  test('search posts the query to the search endpoint', async () => {
    const user = userEvent.setup();
    const fetchSpy = jest.spyOn(global, 'fetch');

    server.use(
      ...connectedHandlers,
      rest.post('/api/v1/tableau/search', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({ success: true, data: { total_count: 2 } })
        );
      })
    );

    renderWithProviders(<TableauIntegration />);

    const searchInput = await screen.findByPlaceholderText(
      /search workbooks, views, datasources/i
    );
    await user.type(searchInput, 'revenue{enter}');

    await waitFor(() => {
      expect(
        fetchSpy.mock.calls.some(
          ([url, init]) =>
            String(url).includes('/api/v1/tableau/search') &&
            (init as RequestInit)?.method === 'POST' &&
            String((init as RequestInit)?.body).includes('revenue')
        )
      ).toBe(true);
    });
  });

  test('survives empty data responses without crashing', async () => {
    server.use(
      rest.get('/api/v1/tableau/health', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true }));
      }),
      rest.get('/api/v1/tableau/workbooks', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: [] }));
      }),
      rest.get('/api/v1/tableau/datasources', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: [] }));
      }),
      rest.get('/api/v1/tableau/views', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: [] }));
      }),
      rest.get('/api/v1/tableau/projects', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ success: true, data: [] }));
      }),
      rest.get('/api/v1/tableau/user', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ error: 'boom' }));
      })
    );

    renderWithProviders(<TableauIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Tableau' })).toBeInTheDocument();
    });
    // Zeroed stats still render (stats computed from local state)
    await waitFor(() => {
      expect(screen.getByText('Total Workbooks')).toBeInTheDocument();
    });
    expect(screen.queryByText('Revenue Dashboard')).not.toBeInTheDocument();
    expect(screen.queryByText('Dana Analyst')).not.toBeInTheDocument();
  });
});
