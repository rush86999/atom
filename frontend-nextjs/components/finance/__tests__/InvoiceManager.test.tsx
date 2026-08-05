/**
 * InvoiceManager Component Tests
 *
 * Tests verify invoice CRUD operations, status management, and export.
 *
 * Source: components/finance/InvoiceManager.tsx
 *
 * Real behavior (verified against source):
 * - On mount GETs `/api/accounting/invoices` and reads `data.data.invoices`.
 *   type is derived server-side as AR (customer) vs AP (vendor).
 * - Create POSTs `/api/accounting/invoices?action=generate`; send POSTs
 *   `?action=send&invoice_id=...`; download GETs `?action=download`.
 * - Edit/delete are local (no endpoint); delete confirms via window.confirm.
 * - UI: "Invoice Manager", "New Invoice" button, table (Invoice # / Entity /
 *   Amount / Status / Actions), status badge shows the raw status string.
 *
 * NOTE: this suite uses the SHARED MSW server (tests/mocks/server). A
 * per-file setupServer() never intercepts because the global server from
 * tests/setup.ts is already listening — requests fall through to the real
 * network and fail slowly.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import InvoiceManager from '../InvoiceManager';
import { server } from '@/tests/mocks/server';
import { rest } from 'msw';

const defaultInvoices = [
  { id: '1', customer: 'Acme Corp', amount: 5000, status: 'paid', due_date: '2025-10-30' },
  { id: '2', vendor: 'Supplier Inc', amount: 2500, status: 'pending', due_date: '2025-11-15' },
];

let lastGetUrl: string | undefined;
let lastPostUrl: string | undefined;
let lastPostBody: any;

const setupDefaultHandlers = () => {
  server.use(
    rest.get('/api/accounting/invoices', (req, res, ctx) => {
      lastGetUrl = req.url.href;
      if (req.url.searchParams.get('action') === 'download') {
        return res(ctx.status(200), ctx.body('PDF'));
      }
      return res(ctx.json({ data: { invoices: defaultInvoices } }));
    }),
    rest.post('/api/accounting/invoices', (req, res, ctx) => {
      lastPostUrl = req.url.href;
      lastPostBody = req.body;
      return res(
        ctx.json({
          success: true,
          data: { id: '3', customer: 'New Customer', amount: 1000, status: 'pending' },
        })
      );
    })
  );
};

// Radix DropdownMenu opens on pointerdown, so fireEvent.click alone does not
// open it — use userEvent (which fires the full pointer sequence).
const openMoreMenu = async () => {
  const user = userEvent.setup();
  const trigger = screen
    .getAllByRole('button')
    .find((btn) => btn.querySelector('.lucide-ellipsis'));
  expect(trigger).toBeTruthy();
  await user.click(trigger!);
};

describe('InvoiceManager', () => {
  beforeEach(() => {
    lastGetUrl = undefined;
    lastPostUrl = undefined;
    lastPostBody = undefined;
    window.confirm = jest.fn(() => true);
    setupDefaultHandlers();
  });

  // Test 1: renders component
  test('renders component', async () => {
    render(<InvoiceManager />);

    await waitFor(() => {
      expect(screen.getByText('Invoice Manager')).toBeInTheDocument();
    });
    expect(screen.getByText('New Invoice')).toBeInTheDocument();
  });

  // Test 2: displays invoice list
  test('displays invoice list', async () => {
    render(<InvoiceManager />);

    await waitFor(() => {
      expect(screen.getByText('Acme Corp')).toBeInTheDocument();
      expect(screen.getByText('Supplier Inc')).toBeInTheDocument();
    });
  });

  // Test 3: creates new invoice
  test('creates new invoice', async () => {
    render(<InvoiceManager />);
    await waitFor(() => expect(screen.getByText('Invoice Manager')).toBeInTheDocument());

    fireEvent.click(screen.getByText('New Invoice'));

    // Radix Dialog opens with the create form.
    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Customer Name'), { target: { value: 'New Customer' } });
    fireEvent.change(screen.getByLabelText('Amount ($)'), { target: { value: '1000' } });
    fireEvent.change(screen.getByLabelText('Due Date'), { target: { value: '2025-12-01' } });
    fireEvent.click(screen.getByText('Generate Invoice'));

    await waitFor(() => {
      expect(screen.getByText('New Customer')).toBeInTheDocument();
    });
    expect(lastPostUrl).toContain('action=generate');
    expect(JSON.parse(JSON.stringify(lastPostBody))).toEqual(
      expect.objectContaining({ customer: 'New Customer', amount: 1000 })
    );
  });

  // Test 4: edits existing invoice
  test('edits existing invoice', async () => {
    render(<InvoiceManager />);
    await waitFor(() => expect(screen.getByText('Acme Corp')).toBeInTheDocument());

    await openMoreMenu();
    fireEvent.click(screen.getByText('Edit Details'));

    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();

    const amountInput = screen.getByLabelText('Amount ($)');
    fireEvent.change(amountInput, { target: { value: '6000' } });
    fireEvent.click(screen.getByText('Save Changes'));

    await waitFor(() => {
      expect(screen.getByText('$6,000.00')).toBeInTheDocument();
    });
  });

  // Test 5: deletes invoice
  test('deletes invoice', async () => {
    render(<InvoiceManager />);
    await waitFor(() => expect(screen.getByText('Acme Corp')).toBeInTheDocument());

    await openMoreMenu();
    fireEvent.click(screen.getByText('Delete Invoice'));

    expect(window.confirm).toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.queryByText('Acme Corp')).not.toBeInTheDocument();
    });
  });

  // Test 6: displays invoice amounts
  test('displays invoice amounts', async () => {
    render(<InvoiceManager />);

    await waitFor(() => {
      expect(screen.getByText('$5,000.00')).toBeInTheDocument();
      expect(screen.getByText('$2,500.00')).toBeInTheDocument();
    });
  });

  // Test 7: shows invoice status badges
  test('shows invoice status badges', async () => {
    render(<InvoiceManager />);

    await waitFor(() => {
      expect(screen.getByText('paid')).toBeInTheDocument();
      expect(screen.getByText('pending')).toBeInTheDocument();
    });
  });

  // Test 8: exports (downloads) an invoice
  test('exports invoice via download action', async () => {
    render(<InvoiceManager />);
    await waitFor(() => expect(screen.getByText('Acme Corp')).toBeInTheDocument());

    const downloadButton = screen
      .getAllByRole('button')
      .find((btn) => btn.querySelector('.lucide-download'));
    expect(downloadButton).toBeTruthy();
    fireEvent.click(downloadButton!);

    await waitFor(() => {
      expect(lastGetUrl).toContain('action=download');
      expect(lastGetUrl).toContain('invoice_id=1');
    });
  });

  // Test 9: sends invoice
  test('sends invoice', async () => {
    render(<InvoiceManager />);
    await waitFor(() => expect(screen.getByText('Acme Corp')).toBeInTheDocument());

    // Only AR invoices (customer set) show the Send action.
    const sendButton = screen
      .getAllByRole('button')
      .find((btn) => btn.querySelector('.lucide-send'));
    expect(sendButton).toBeTruthy();
    fireEvent.click(sendButton!);

    await waitFor(() => {
      expect(lastPostUrl).toContain('action=send');
      expect(lastPostUrl).toContain('invoice_id=1');
    });
  });

  // Test 10: handles create invoice error
  test('handles create invoice error', async () => {
    server.use(
      rest.post('/api/accounting/invoices', (req, res, ctx) => res(ctx.status(500)))
    );

    render(<InvoiceManager />);
    await waitFor(() => expect(screen.getByText('Invoice Manager')).toBeInTheDocument());

    fireEvent.click(screen.getByText('New Invoice'));
    fireEvent.change(screen.getByLabelText('Customer Name'), { target: { value: 'New Customer' } });
    fireEvent.change(screen.getByLabelText('Amount ($)'), { target: { value: '1000' } });
    fireEvent.change(screen.getByLabelText('Due Date'), { target: { value: '2025-12-01' } });
    fireEvent.click(screen.getByText('Generate Invoice'));

    // Error path keeps the dialog open and shows the error toast.
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  // Test 11: handles API error on load
  test('handles API error on load', async () => {
    server.use(
      rest.get('/api/accounting/invoices', (req, res, ctx) => res(ctx.status(500)))
    );

    render(<InvoiceManager />);

    await waitFor(() => {
      expect(screen.getByText('Invoice Manager')).toBeInTheDocument();
    });
    expect(screen.getByText('No invoices found.')).toBeInTheDocument();
  });

  // Test 12: displays loading state
  test('displays loading state', () => {
    const { container } = render(<InvoiceManager />);

    const loader = container.querySelector('.lucide-loader-circle');
    expect(loader).toBeInTheDocument();
  });
});
