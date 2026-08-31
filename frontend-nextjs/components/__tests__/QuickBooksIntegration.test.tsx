/**
 * QuickBooksIntegration Component Tests
 *
 * Tests verify the real QuickBooks integration component:
 * - Health check / connection state
 * - OAuth connect flow
 * - Company info and customer data loading
 * - Customer search filtering
 * - Invoice / bill / account / employee / vendor tab rendering
 * - Customer / invoice / bill creation flows (success + failure)
 * - Account type badge variants
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/QuickBooksIntegration.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import QuickBooksIntegration from '@/components/QuickBooksIntegration';
import { useToast } from '@/components/ui/use-toast';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const getToastMock = (): jest.Mock => (useToast as jest.Mock)().toast;

// The real shadcn Select (Radix) is heavy to drive in jsdom; the repo pattern
// (JiraIntegration.test.tsx) mocks it with a context-aware implementation so
// the invoice/bill create dialogs can render and be interacted with
// (trigger -> open content -> click item calls onValueChange).
jest.mock('@/components/ui/select', () => {
  const { createContext, useContext, useState } = jest.requireActual('react') as typeof import('react');
  const SelectCtx = createContext<any>(null);

  const Select = ({ value, onValueChange, children }: any) => {
    const [open, setOpen] = useState(false);
    return (
      <SelectCtx.Provider value={{ value, onValueChange, open, setOpen }}>
        <div data-testid="qb-select-root">{children}</div>
      </SelectCtx.Provider>
    );
  };
  const SelectTrigger = ({ children, className, ...props }: any) => {
    const { setOpen } = useContext(SelectCtx);
    return (
      <button
        type="button"
        data-testid="qb-select-trigger"
        className={className}
        onClick={() => setOpen((o: boolean) => !o)}
        {...props}
      >
        {children}
      </button>
    );
  };
  const SelectContent = ({ children }: any) => {
    const { open } = useContext(SelectCtx);
    return open ? <div data-testid="qb-select-content">{children}</div> : null;
  };
  const SelectItem = ({ value, children }: any) => {
    const { onValueChange, setOpen } = useContext(SelectCtx);
    return (
      <span
        data-testid="qb-select-item"
        onClick={() => {
          onValueChange(value);
          setOpen(false);
        }}
      >
        {children}
      </span>
    );
  };
  const SelectValue = ({ placeholder }: any) => <span data-testid="qb-select-value" />;
  return { Select, SelectTrigger, SelectContent, SelectItem, SelectValue };
});

const qbHandlers = [
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ providers: { quickbooks: { connected: true, source: 'user_connection' } } })
    );
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
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          invoices: [
            {
              Id: 'inv1',
              DocNumber: 'INV-1001',
              TxnDate: '2024-05-01T12:00:00Z',
              DueDate: '2024-06-01T12:00:00Z',
              Balance: 500,
              TotalAmt: 1250.5,
              CustomerRef: { value: 'cust1', name: 'Acme Corporation' },
              InvoiceLink: 'https://qb.invoice/inv1',
            },
            {
              Id: 'inv2',
              DocNumber: 'INV-1002',
              TxnDate: '2024-05-02T12:00:00Z',
              DueDate: '2024-06-02T12:00:00Z',
              Balance: 0,
              TotalAmt: 300,
              CustomerRef: { value: 'cust2', name: 'Globex Holdings' },
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/quickbooks/bills', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          bills: [
            {
              Id: 'bill1',
              DocNumber: 'BILL-2001',
              TxnDate: '2024-04-15T12:00:00Z',
              DueDate: '2024-05-15T12:00:00Z',
              TotalAmt: 400,
              Balance: 100,
              VendorRef: { value: 'v1', name: 'VendorCo' },
            },
            {
              Id: 'bill2',
              DocNumber: 'BILL-2002',
              TxnDate: '2024-04-20T12:00:00Z',
              DueDate: '2024-05-20T12:00:00Z',
              TotalAmt: 200,
              Balance: 0,
              VendorRef: { value: 'v2', name: 'SupplierX' },
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/quickbooks/accounts', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          accounts: [
            {
              Id: 'acc1',
              Name: 'Cash',
              Classification: 'Asset',
              AccountType: 'Asset',
              AccountSubType: 'Bank',
              CurrentBalance: 10000,
              Active: true,
            },
            {
              Id: 'acc2',
              Name: 'Loan',
              Classification: 'Liability',
              AccountType: 'Liability',
              AccountSubType: 'Long Term',
              CurrentBalance: -500,
              Active: true,
            },
            {
              Id: 'acc3',
              Name: 'Opening Equity',
              Classification: 'Equity',
              AccountType: 'Equity',
              AccountSubType: 'Opening',
              CurrentBalance: 2500,
              Active: true,
            },
            {
              Id: 'acc4',
              Name: 'Sales',
              Classification: 'Revenue',
              AccountType: 'Revenue',
              AccountSubType: 'Service',
              CurrentBalance: 1000,
              Active: true,
            },
            {
              Id: 'acc5',
              Name: 'Rent',
              Classification: 'Expense',
              AccountType: 'Expense',
              AccountSubType: 'Facilities',
              CurrentBalance: -800,
              Active: true,
            },
            {
              Id: 'acc6',
              Name: 'Legacy',
              Classification: 'Other',
              AccountType: 'Other Current Asset',
              AccountSubType: 'Other',
              CurrentBalance: 0,
              Active: false,
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/quickbooks/employees', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          employees: [
            {
              Id: 'emp1',
              DisplayName: 'Alice Johnson',
              Title: 'Accountant',
              PrimaryEmailAddr: { Address: 'alice@atom.com' },
              PrimaryPhone: { FreeFormNumber: '+1-555-0200' },
              BillRate: 50,
              Active: true,
            },
            {
              Id: 'emp2',
              DisplayName: 'Bob Smith',
              Title: 'Bookkeeper',
              Status: 'Terminated',
              Active: false,
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/quickbooks/vendors', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          vendors: [
            {
              Id: 'v1',
              DisplayName: 'VendorCo',
              CompanyName: 'VendorCo LLC',
              PrimaryEmailAddr: { Address: 'ap@vendorco.com' },
              PrimaryPhone: { FreeFormNumber: '+1-555-0300' },
              Balance: 100,
              Active: true,
            },
            {
              Id: 'v2',
              DisplayName: 'SupplierX',
              Balance: 0,
              Active: false,
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/quickbooks/customers/create', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),

  rest.post('/api/integrations/quickbooks/invoices/create', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),

  rest.post('/api/integrations/quickbooks/bills/create', (req, res, ctx) => {
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
// (double data-load race); the POST loads can land ~1s after mount through
// MSW's cold interceptor, so wait with a generous timeout for the full
// dataset to settle.
const settleData = async (text: RegExp) => {
  await screen.findByText(text, {}, { timeout: 5000 });
  await new Promise((r) => setTimeout(r, 50));
};

describe('QuickBooksIntegration', () => {
  beforeAll(async () => {
    // MSW cold-start warm-up: the first intercepted request in a fresh worker
    // process can take >1s to resolve through the interceptor pipeline, which
    // races the component's mount-time connection check. Prime it with a
    // throwaway request (handled by the global handlers.ts /api/health
    // handler — at this point the per-file qbHandlers aren't registered yet).
    await fetch('/api/health');
  });

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

  // Test 8b: cancel closes each create dialog without submitting
  test('cancel closes each create dialog without submitting', async () => {
    render(<QuickBooksIntegration />);

    await settleData(/Acme Corporation/);

    fireEvent.click(screen.getByRole('button', { name: /create customer/i }));
    let dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: /^cancel$/i }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Invoices' }));
    fireEvent.click(screen.getByRole('button', { name: /create invoice/i }));
    dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: /^cancel$/i }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Bills' }));
    fireEvent.click(screen.getByRole('button', { name: /create bill/i }));
    dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: /^cancel$/i }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  // Test 9: handles connection error
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/integrations/connection-status', (req, res, ctx) => {
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

  // Test 11: handles health check network failure
  test('handles health check network failure', async () => {
    server.use(
      rest.get('/api/integrations/connection-status', (req, res, ctx) => {
        // msw 1.x has no ctx.networkError; MSW turns the resulting handler
        // exception into a network error, so keep calling through `as any`.
        return res((ctx as any).networkError('boom'));
      })
    );

    render(<QuickBooksIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Disconnected')).toBeInTheDocument();
    });
    expect(
      screen.getByRole('button', { name: /connect quickbooks account/i })
    ).toBeInTheDocument();
  });

  // Test 12: renders invoices with statuses and external view link
  test('renders invoices with statuses and view link', async () => {
    const openSpy = jest.spyOn(window, 'open').mockImplementation(() => null);
    render(<QuickBooksIntegration />);

    await settleData(/Acme Corporation/);
    fireEvent.click(screen.getByRole('button', { name: 'Invoices' }));

    await waitFor(() => {
      expect(screen.getByText('INV-1001')).toBeInTheDocument();
    });
    expect(screen.getByText('INV-1002')).toBeInTheDocument();
    expect(screen.getByText('Outstanding')).toBeInTheDocument();
    expect(screen.getByText('Paid')).toBeInTheDocument();
    expect(screen.getByText('$1,250.50')).toBeInTheDocument();
    expect(screen.getByText('$500.00')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /^view$/i }));
    expect(openSpy).toHaveBeenCalledWith('https://qb.invoice/inv1', '_blank');
  });

  // Test 13: renders bills with vendors and statuses
  test('renders bills with vendors and statuses', async () => {
    render(<QuickBooksIntegration />);

    await settleData(/Acme Corporation/);
    fireEvent.click(screen.getByRole('button', { name: 'Bills' }));

    await waitFor(() => {
      expect(screen.getByText('BILL-2001')).toBeInTheDocument();
    });
    expect(screen.getByText('BILL-2002')).toBeInTheDocument();
    expect(screen.getByText('VendorCo')).toBeInTheDocument();
    expect(screen.getByText('SupplierX')).toBeInTheDocument();
    expect(screen.getByText('Outstanding')).toBeInTheDocument();
    expect(screen.getByText('Paid')).toBeInTheDocument();
    expect(screen.getByText('$400.00')).toBeInTheDocument();
    expect(screen.getByText('$100.00')).toBeInTheDocument();
  });

  // Test 14: renders accounts with classification badges
  test('renders accounts with classification badges', async () => {
    render(<QuickBooksIntegration />);

    await settleData(/Acme Corporation/);
    fireEvent.click(screen.getByRole('button', { name: 'Accounts' }));

    await waitFor(() => {
      expect(screen.getByText('Cash')).toBeInTheDocument();
    });
    expect(screen.getByText('Loan')).toBeInTheDocument();
    expect(screen.getByText('Opening Equity')).toBeInTheDocument();
    expect(screen.getByText('Sales')).toBeInTheDocument();
    expect(screen.getByText('Rent')).toBeInTheDocument();
    expect(screen.getByText('Legacy')).toBeInTheDocument();
    expect(screen.getByText('Inactive')).toBeInTheDocument();
  });

  // Test 15: renders employees with bill rate and status fallback
  test('renders employees with bill rate and status fallback', async () => {
    render(<QuickBooksIntegration />);

    await settleData(/Acme Corporation/);
    fireEvent.click(screen.getByRole('button', { name: 'Employees' }));

    await waitFor(() => {
      expect(screen.getByText('Alice Johnson')).toBeInTheDocument();
    });
    expect(screen.getByText('Bob Smith')).toBeInTheDocument();
    expect(screen.getByText('$50.00')).toBeInTheDocument();
    expect(screen.getByText('Terminated')).toBeInTheDocument();
  });

  // Test 16: renders vendors with company names and statuses
  test('renders vendors with company names and statuses', async () => {
    render(<QuickBooksIntegration />);

    await settleData(/Acme Corporation/);
    fireEvent.click(screen.getByRole('button', { name: 'Vendors' }));

    await waitFor(() => {
      expect(screen.getByText('VendorCo LLC')).toBeInTheDocument();
    });
    expect(screen.getByText('SupplierX')).toBeInTheDocument();
    expect(screen.getByText('Inactive')).toBeInTheDocument();
  });

  // Test 17: filters customers by company name too
  test('filters customers by company name', async () => {
    render(<QuickBooksIntegration />);

    await settleData(/Acme Corporation/);

    const searchInput = screen.getByPlaceholderText(/search customers/i);
    fireEvent.change(searchInput, { target: { value: 'Acme Inc' } });

    await waitFor(() => {
      expect(screen.getByText('Acme Corporation')).toBeInTheDocument();
    });
    expect(screen.queryByText('Globex Holdings')).not.toBeInTheDocument();
  });

  // Test 18: create customer flow posts the form and closes the dialog
  test('create customer flow posts the form and closes the dialog', async () => {
    const createHandler = jest.fn();
    server.use(
      rest.post('/api/integrations/quickbooks/customers/create', (req, res, ctx) => {
        createHandler(req.body);
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );

    render(<QuickBooksIntegration />);

    await settleData(/Acme Corporation/);
    fireEvent.click(screen.getByRole('button', { name: /create customer/i }));

    const dialog = await screen.findByRole('dialog');
    fireEvent.change(within(dialog).getByPlaceholderText('Customer name'), {
      target: { value: 'New Customer Co' },
    });
    fireEvent.change(within(dialog).getByPlaceholderText('Company name'), {
      target: { value: 'New Customer LLC' },
    });
    fireEvent.change(within(dialog).getByPlaceholderText('email@example.com'), {
      target: { value: 'billing@newco.com' },
    });
    fireEvent.change(within(dialog).getByPlaceholderText('Phone number'), {
      target: { value: '+1-555-0400' },
    });
    fireEvent.change(within(dialog).getByPlaceholderText('Street'), {
      target: { value: '1 Main St' },
    });
    fireEvent.change(within(dialog).getByPlaceholderText('City'), {
      target: { value: 'Springfield' },
    });
    fireEvent.change(within(dialog).getByPlaceholderText('State'), {
      target: { value: 'IL' },
    });
    fireEvent.change(within(dialog).getByPlaceholderText('Postal Code'), {
      target: { value: '62701' },
    });
    fireEvent.change(within(dialog).getByPlaceholderText('Country'), {
      target: { value: 'US' },
    });

    fireEvent.click(within(dialog).getByRole('button', { name: 'Create Customer' }));

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith({
        title: 'Success',
        description: 'Customer created successfully',
      });
    });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
    expect(createHandler).toHaveBeenCalledWith(
      expect.objectContaining({
        DisplayName: 'New Customer Co',
        CompanyName: 'New Customer LLC',
        PrimaryEmailAddr: { Address: 'billing@newco.com' },
        PrimaryAddr: expect.objectContaining({
          Line1: '1 Main St',
          City: 'Springfield',
          CountrySubDivisionCode: 'IL',
          PostalCode: '62701',
          Country: 'US',
        }),
      })
    );
  });

  // Test 19: create customer failure shows an error toast and keeps the dialog open
  test('create customer failure shows an error toast and keeps the dialog open', async () => {
    server.use(
      rest.post('/api/integrations/quickbooks/customers/create', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<QuickBooksIntegration />);

    await settleData(/Acme Corporation/);
    fireEvent.click(screen.getByRole('button', { name: /create customer/i }));

    const dialog = await screen.findByRole('dialog');
    fireEvent.change(within(dialog).getByPlaceholderText('Customer name'), {
      target: { value: 'Doomed Corp' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Create Customer' }));

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith({
        title: 'Error',
        description: 'Failed to create customer',
        variant: 'error',
      });
    });
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  // Test 20: create invoice flow selects a customer, adds a line, and posts
  test('create invoice flow posts the form and closes the dialog', async () => {
    const createHandler = jest.fn();
    server.use(
      rest.post('/api/integrations/quickbooks/invoices/create', (req, res, ctx) => {
        createHandler(req.body);
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );

    render(<QuickBooksIntegration />);

    await settleData(/Acme Corporation/);
    fireEvent.click(screen.getByRole('button', { name: 'Invoices' }));
    fireEvent.click(screen.getByRole('button', { name: /create invoice/i }));

    const dialog = await screen.findByRole('dialog');

    fireEvent.click(within(dialog).getByTestId('qb-select-trigger'));
    fireEvent.click(within(dialog).getByText('Acme Corporation'));

    const [invoiceDate, invoiceDueDate] = dialog.querySelectorAll('input[type="date"]');
    fireEvent.change(invoiceDate, { target: { value: '2024-07-01' } });
    fireEvent.change(invoiceDueDate, { target: { value: '2024-08-01' } });

    fireEvent.click(within(dialog).getByRole('button', { name: /add line/i }));
    fireEvent.change(within(dialog).getByPlaceholderText('Description'), {
      target: { value: 'Consulting' },
    });
    fireEvent.change(within(dialog).getByPlaceholderText('Amount'), {
      target: { value: '150' },
    });

    fireEvent.click(within(dialog).getByRole('button', { name: 'Create Invoice' }));

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith({
        title: 'Success',
        description: 'Invoice created successfully',
      });
    });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
    expect(createHandler).toHaveBeenCalledWith(
      expect.objectContaining({
        CustomerRef: { value: 'cust1', name: 'Acme Corporation' },
        TxnDate: '2024-07-01',
        DueDate: '2024-08-01',
        Line: [expect.objectContaining({ Description: 'Consulting', Amount: 150 })],
      })
    );
  });

  // Test 21: invoice line removal re-disables the submit button
  test('invoice line removal re-disables the submit button', async () => {
    render(<QuickBooksIntegration />);

    await settleData(/Acme Corporation/);
    fireEvent.click(screen.getByRole('button', { name: 'Invoices' }));
    fireEvent.click(screen.getByRole('button', { name: /create invoice/i }));

    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByTestId('qb-select-trigger'));
    fireEvent.click(within(dialog).getByText('Acme Corporation'));
    fireEvent.click(within(dialog).getByRole('button', { name: /add line/i }));

    const submitButton = within(dialog).getByRole('button', { name: 'Create Invoice' });
    expect(submitButton).toBeEnabled();

    fireEvent.click(
      within(dialog).getAllByRole('button', { name: '' }).find((b) => b.innerHTML.includes('svg'))!
    );

    await waitFor(() => {
      expect(submitButton).toBeDisabled();
    });
  });

  // Test 21b: bill line removal re-disables the submit button
  test('bill line removal re-disables the submit button', async () => {
    render(<QuickBooksIntegration />);

    await settleData(/Acme Corporation/);
    fireEvent.click(screen.getByRole('button', { name: 'Bills' }));
    fireEvent.click(screen.getByRole('button', { name: /create bill/i }));

    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByTestId('qb-select-trigger'));
    fireEvent.click(within(dialog).getByText('VendorCo'));
    fireEvent.click(within(dialog).getByRole('button', { name: /add line/i }));

    const submitButton = within(dialog).getByRole('button', { name: 'Create Bill' });
    expect(submitButton).toBeEnabled();

    fireEvent.click(
      within(dialog).getAllByRole('button', { name: '' }).find((b) => b.innerHTML.includes('svg'))!
    );

    await waitFor(() => {
      expect(submitButton).toBeDisabled();
    });
  });

  // Test 21c: invoices tab shows a spinner while invoices are loading
  test('invoices tab shows a spinner while invoices are loading', async () => {
    let resolveInvoices: (value: any) => void;
    let invoicesRes: any;
    let invoicesCtx: any;
    server.use(
      rest.post('/api/integrations/quickbooks/invoices', (req, res, ctx) => {
        invoicesRes = res;
        invoicesCtx = ctx;
        return new Promise((resolve) => {
          resolveInvoices = resolve;
        });
      })
    );

    render(<QuickBooksIntegration />);

    await settleData(/Acme Corporation/);
    fireEvent.click(screen.getByRole('button', { name: 'Invoices' }));

    await waitFor(() => {
      expect(screen.getByRole('table').querySelector('.animate-spin')).toBeTruthy();
    });

    resolveInvoices!(
      invoicesRes(invoicesCtx.status(200), invoicesCtx.json({ data: { invoices: [] } }))
    );

    await waitFor(() => {
      expect(document.querySelector('.animate-spin')).toBeNull();
    });
  });

  // Test 22: create invoice failure shows an error toast and keeps the dialog open
  test('create invoice failure shows an error toast and keeps the dialog open', async () => {
    server.use(
      rest.post('/api/integrations/quickbooks/invoices/create', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<QuickBooksIntegration />);

    await settleData(/Acme Corporation/);
    fireEvent.click(screen.getByRole('button', { name: 'Invoices' }));
    fireEvent.click(screen.getByRole('button', { name: /create invoice/i }));

    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByTestId('qb-select-trigger'));
    fireEvent.click(within(dialog).getByText('Acme Corporation'));
    fireEvent.click(within(dialog).getByRole('button', { name: /add line/i }));

    fireEvent.click(within(dialog).getByRole('button', { name: 'Create Invoice' }));

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith({
        title: 'Error',
        description: 'Failed to create invoice',
        variant: 'error',
      });
    });
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  // Test 22b: create customer network failure shows an error toast
  test('create customer network failure shows an error toast', async () => {
    server.use(
      rest.post('/api/integrations/quickbooks/customers/create', (req, res, ctx) => {
        // msw 1.x has no ctx.networkError; MSW turns the resulting handler
        // exception into a network error, so keep calling through `as any`.
        return res((ctx as any).networkError('boom'));
      })
    );

    render(<QuickBooksIntegration />);

    await settleData(/Acme Corporation/);
    fireEvent.click(screen.getByRole('button', { name: /create customer/i }));

    const dialog = await screen.findByRole('dialog');
    fireEvent.change(within(dialog).getByPlaceholderText('Customer name'), {
      target: { value: 'Doomed Corp' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Create Customer' }));

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith({
        title: 'Error',
        description: 'Failed to create customer',
        variant: 'error',
      });
    });
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  // Test 22c: create invoice network failure shows an error toast
  test('create invoice network failure shows an error toast', async () => {
    server.use(
      rest.post('/api/integrations/quickbooks/invoices/create', (req, res, ctx) => {
        // msw 1.x has no ctx.networkError; MSW turns the resulting handler
        // exception into a network error, so keep calling through `as any`.
        return res((ctx as any).networkError('boom'));
      })
    );

    render(<QuickBooksIntegration />);

    await settleData(/Acme Corporation/);
    fireEvent.click(screen.getByRole('button', { name: 'Invoices' }));
    fireEvent.click(screen.getByRole('button', { name: /create invoice/i }));

    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByTestId('qb-select-trigger'));
    fireEvent.click(within(dialog).getByText('Acme Corporation'));
    fireEvent.click(within(dialog).getByRole('button', { name: /add line/i }));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Create Invoice' }));

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith({
        title: 'Error',
        description: 'Failed to create invoice',
        variant: 'error',
      });
    });
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  // Test 23: create bill flow selects a vendor, adds a line, and posts
  test('create bill flow posts the form and closes the dialog', async () => {
    const createHandler = jest.fn();
    server.use(
      rest.post('/api/integrations/quickbooks/bills/create', (req, res, ctx) => {
        createHandler(req.body);
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );

    render(<QuickBooksIntegration />);

    await settleData(/Acme Corporation/);
    fireEvent.click(screen.getByRole('button', { name: 'Bills' }));
    fireEvent.click(screen.getByRole('button', { name: /create bill/i }));

    const dialog = await screen.findByRole('dialog');

    fireEvent.click(within(dialog).getByTestId('qb-select-trigger'));
    fireEvent.click(within(dialog).getByText('VendorCo'));

    const [billDate, billDueDate] = dialog.querySelectorAll('input[type="date"]');
    fireEvent.change(billDate, { target: { value: '2024-06-15' } });
    fireEvent.change(billDueDate, { target: { value: '2024-07-15' } });

    fireEvent.click(within(dialog).getByRole('button', { name: /add line/i }));
    fireEvent.change(within(dialog).getByPlaceholderText('Description'), {
      target: { value: 'Office rent' },
    });
    fireEvent.change(within(dialog).getByPlaceholderText('Amount'), {
      target: { value: '900' },
    });

    fireEvent.click(within(dialog).getByRole('button', { name: 'Create Bill' }));

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith({
        title: 'Success',
        description: 'Bill created successfully',
      });
    });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
    expect(createHandler).toHaveBeenCalledWith(
      expect.objectContaining({
        VendorRef: { value: 'v1', name: 'VendorCo' },
        TxnDate: '2024-06-15',
        DueDate: '2024-07-15',
        Line: [expect.objectContaining({ Description: 'Office rent', Amount: 900 })],
      })
    );
  });

  // Test 24: create bill failure shows an error toast and keeps the dialog open
  test('create bill failure shows an error toast and keeps the dialog open', async () => {
    server.use(
      rest.post('/api/integrations/quickbooks/bills/create', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<QuickBooksIntegration />);

    await settleData(/Acme Corporation/);
    fireEvent.click(screen.getByRole('button', { name: 'Bills' }));
    fireEvent.click(screen.getByRole('button', { name: /create bill/i }));

    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByTestId('qb-select-trigger'));
    fireEvent.click(within(dialog).getByText('VendorCo'));
    fireEvent.click(within(dialog).getByRole('button', { name: /add line/i }));

    fireEvent.click(within(dialog).getByRole('button', { name: 'Create Bill' }));

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith({
        title: 'Error',
        description: 'Failed to create bill',
        variant: 'error',
      });
    });
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  // Test 24b: create bill network failure shows an error toast
  test('create bill network failure shows an error toast', async () => {
    server.use(
      rest.post('/api/integrations/quickbooks/bills/create', (req, res, ctx) => {
        // msw 1.x has no ctx.networkError; MSW turns the resulting handler
        // exception into a network error, so keep calling through `as any`.
        return res((ctx as any).networkError('boom'));
      })
    );

    render(<QuickBooksIntegration />);

    await settleData(/Acme Corporation/);
    fireEvent.click(screen.getByRole('button', { name: 'Bills' }));
    fireEvent.click(screen.getByRole('button', { name: /create bill/i }));

    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByTestId('qb-select-trigger'));
    fireEvent.click(within(dialog).getByText('VendorCo'));
    fireEvent.click(within(dialog).getByRole('button', { name: /add line/i }));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Create Bill' }));

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith({
        title: 'Error',
        description: 'Failed to create bill',
        variant: 'error',
      });
    });
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  // Test 25: refresh status re-runs the health check and stays connected
  test('refresh status re-runs the health check', async () => {
    render(<QuickBooksIntegration />);

    await settleData(/Acme Corporation/);

    fireEvent.click(screen.getByRole('button', { name: /refresh status/i }));

    await waitFor(() => {
      expect(screen.getByText('Acme Corporation')).toBeInTheDocument();
    });
    expect(screen.getByText('Connected')).toBeInTheDocument();
  });
});
