/**
 * QuickBooksIntegration Component Tests
 *
 * Tests verify the real QuickBooks integration component:
 * - Health check / connection state
 * - OAuth connect flow
 * - Company info and customer data loading
 * - Customer search filtering
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/QuickBooksIntegration.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import QuickBooksIntegration from '@/components/QuickBooksIntegration';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const qbHandlers = [
  rest.get('/api/integrations/quickbooks/health', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ status: 'healthy' }));
  }),

  rest.post('/api/integrations/quickbooks/company', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          company: {
            Id: 'c1',
            CompanyName: 'Atom Corp',
            LegalName: 'Atom Corp, Inc.',
            Email: { Address: 'finance@atom.com' },
          },
        },
      })
    );
  }),

  rest.post('/api/integrations/quickbooks/customers', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          customers: [
            {
              Id: 'cust1',
              DisplayName: 'Acme Corporation',
              CompanyName: 'Acme Inc',
              PrimaryEmailAddr: { Address: 'billing@acme.com' },
              PrimaryPhone: { FreeFormNumber: '+1-555-0100' },
              Balance: 2500,
              Active: true,
            },
            {
              Id: 'cust2',
              DisplayName: 'Globex Holdings',
              CompanyName: 'Globex LLC',
              Balance: 0,
              Active: false,
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/quickbooks/invoices', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { invoices: [] } }));
  }),
  rest.post('/api/integrations/quickbooks/bills', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { bills: [] } }));
  }),
  rest.post('/api/integrations/quickbooks/accounts', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { accounts: [] } }));
  }),
  rest.post('/api/integrations/quickbooks/employees', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { employees: [] } }));
  }),
  rest.post('/api/integrations/quickbooks/vendors', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { vendors: [] } }));
  }),
];

const setDisconnected = () => {
  server.use(
    rest.get('/api/integrations/quickbooks/health', (req, res, ctx) => {
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

describe('QuickBooksIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...qbHandlers);
  });

  // Test 1: renders component
  test('renders component', () => {
    render(<QuickBooksIntegration />);

    expect(
      screen.getByRole('heading', { name: /quickbooks integration/i })
    ).toBeInTheDocument();
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    setDisconnected();

    render(<QuickBooksIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect quickbooks account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 3: connect button is clickable without crashing (jsdom logs the
  // navigation attempt; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setDisconnected();

    render(<QuickBooksIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect quickbooks account/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 4: shows connected state when health check passes
  test('shows connected state when health check passes', async () => {
    render(<QuickBooksIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 5: displays company info after connection
  test('displays company info after connection', async () => {
    render(<QuickBooksIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Atom Corp')).toBeInTheDocument();
    });
  });

  // Test 6: displays customers in the default Customers tab
  test('displays customers in the default Customers tab', async () => {
    render(<QuickBooksIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Acme Corporation')).toBeInTheDocument();
      expect(screen.getByText('Globex Holdings')).toBeInTheDocument();
    });
  });

  // Test 7: filters customers by search query
  test('filters customers by search query', async () => {
    render(<QuickBooksIntegration />);

    await settleData(/Acme Corporation/);

    const searchInput = screen.getByPlaceholderText(/search customers/i);
    fireEvent.change(searchInput, { target: { value: 'Globex' } });

    await waitFor(() => {
      expect(screen.getByText('Globex Holdings')).toBeInTheDocument();
    });
    expect(screen.queryByText('Acme Corporation')).not.toBeInTheDocument();
  });

  // Test 8: opens create customer dialog
  test('opens create customer dialog', async () => {
    render(<QuickBooksIntegration />);

    const createButton = await screen.findByRole('button', {
      name: /create customer/i,
    });
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  // Test 9: handles connection error
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/integrations/quickbooks/health', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<QuickBooksIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect quickbooks account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 10: shows refresh status button
  test('shows refresh status button', async () => {
    render(<QuickBooksIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh status/i })).toBeInTheDocument();
    });
  });
});
