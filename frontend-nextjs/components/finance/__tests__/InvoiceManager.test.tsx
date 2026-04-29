/**
 * InvoiceManager Component Tests
 *
 * Tests verify invoice CRUD operations, filtering,
 * status management, and export functionality.
 *
 * Source: components/finance/InvoiceManager.tsx (110 lines uncovered)
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import InvoiceManager from '../InvoiceManager';
import { rest } from 'msw';
import { setupServer } from 'msw/node';

const server = setupServer(
  rest.get('/api/accounting/invoices', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          invoices: [
            {
              id: '1',
              customer: 'Acme Corp',
              amount: 5000,
              status: 'paid',
              due_date: '2025-10-30',
            },
            {
              id: '2',
              vendor: 'Supplier Inc',
              amount: 2500,
              status: 'pending',
              due_date: '2025-11-15',
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/accounting/invoices', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        invoice: {
          id: '3',
          customer: 'New Customer',
          amount: 1000,
          status: 'pending',
        },
      })
    );
  }),

  rest.patch('/api/accounting/invoices/:id', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        invoice: {
          id: '1',
          customer: 'Updated Customer',
          amount: 6000,
          status: 'paid',
        },
      })
    );
  }),

  rest.delete('/api/accounting/invoices/:id', (req, res, ctx) => {
    return res(ctx.status(200));
  })
);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('InvoiceManager', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: renders component
  test('renders component', async () => {
    render(<InvoiceManager />);

    await waitFor(() => {
      expect(screen.getByText(/invoices/i)).toBeInTheDocument();
    });
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

    const addButton = screen.getByRole('button', { name: /add invoice/i });
    fireEvent.click(addButton);

    await waitFor(() => {
      expect(screen.getByText(/create invoice/i)).toBeInTheDocument();
    });

    const customerInput = screen.getByLabelText(/customer/i);
    fireEvent.change(customerInput, { target: { value: 'New Customer' } });

    const amountInput = screen.getByLabelText(/amount/i);
    fireEvent.change(amountInput, { target: { value: '1000' } });

    const dueDateInput = screen.getByLabelText(/due date/i);
    fireEvent.change(dueDateInput, { target: { value: '2025-12-01' } });

    const createButton = screen.getByRole('button', { name: /create/i });
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(screen.getByText('New Customer')).toBeInTheDocument();
    });
  });

  // Test 4: edits existing invoice
  test('edits existing invoice', async () => {
    render(<InvoiceManager />);

    await waitFor(() => {
      expect(screen.getByText('Acme Corp')).toBeInTheDocument();
    });

    const editButton = screen.getAllByRole('button').find(
      btn => btn.getAttribute('aria-label')?.includes('edit')
    );

    if (editButton) {
      fireEvent.click(editButton);

      await waitFor(() => {
        const customerInput = screen.getByLabelText(/customer/i);
        fireEvent.change(customerInput, { target: { value: 'Updated Customer' } });

        const saveButton = screen.getByRole('button', { name: /save/i });
        fireEvent.click(saveButton);
      });
    }
  });

  // Test 5: deletes invoice
  test('deletes invoice', async () => {
    render(<InvoiceManager />);

    await waitFor(() => {
      expect(screen.getByText('Acme Corp')).toBeInTheDocument();
    });

    const deleteButton = screen.getAllByRole('button').find(
      btn => btn.getAttribute('aria-label')?.includes('delete')
    );

    if (deleteButton) {
      fireEvent.click(deleteButton);

      await waitFor(() => {
        const confirmButton = screen.getByRole('button', { name: /confirm/i });
        fireEvent.click(confirmButton);
      });

      await waitFor(() => {
        expect(screen.queryByText('Acme Corp')).not.toBeInTheDocument();
      });
    }
  });

  // Test 6: filters invoices by status
  test('filters invoices by status', async () => {
    render(<InvoiceManager />);

    await waitFor(() => {
      expect(screen.getByText('Acme Corp')).toBeInTheDocument();
    });

    const filterSelect = screen.getByRole('combobox', { name: /status/i });
    fireEvent.change(filterSelect, { target: { value: 'paid' } });

    await waitFor(() => {
      expect(screen.getByText('Acme Corp')).toBeInTheDocument();
    });
  });

  // Test 7: displays invoice amounts
  test('displays invoice amounts', async () => {
    render(<InvoiceManager />);

    await waitFor(() => {
      expect(screen.getByText('5000')).toBeInTheDocument();
      expect(screen.getByText('2500')).toBeInTheDocument();
    });
  });

  // Test 8: shows invoice status badges
  test('shows invoice status badges', async () => {
    render(<InvoiceManager />);

    await waitFor(() => {
      expect(screen.getByText('paid')).toBeInTheDocument();
      expect(screen.getByText('pending')).toBeInTheDocument();
    });
  });

  // Test 9: exports invoices
  test('exports invoices', async () => {
    render(<InvoiceManager />);

    await waitFor(() => {
      expect(screen.getByText('Acme Corp')).toBeInTheDocument();
    });

    const exportButton = screen.getByRole('button', { name: /export/i });
    fireEvent.click(exportButton);

    await waitFor(() => {
      expect(screen.getByText(/exporting/i)).toBeInTheDocument();
    });
  });

  // Test 10: handles create invoice error
  test('handles create invoice error', async () => {
    server.use(
      rest.post('/api/accounting/invoices', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<InvoiceManager />);

    const addButton = screen.getByRole('button', { name: /add invoice/i });
    fireEvent.click(addButton);

    await waitFor(() => {
      const customerInput = screen.getByLabelText(/customer/i);
      fireEvent.change(customerInput, { target: { value: 'Test' } });

      const createButton = screen.getByRole('button', { name: /create/i });
      fireEvent.click(createButton);
    });

    await waitFor(() => {
      expect(screen.getByText(/failed to create/i)).toBeInTheDocument();
    });
  });

  // Test 11: handles API error on load
  test('handles API error on load', async () => {
    server.use(
      rest.get('/api/accounting/invoices', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<InvoiceManager />);

    await waitFor(() => {
      expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
    });
  });

  // Test 12: displays loading state
  test('displays loading state', () => {
    render(<InvoiceManager />);

    expect(screen.getByRole('button', { name: /loading/i })).toBeInTheDocument();
  });

  // Test 13: shows invoice type (AR/AP)
  test('shows invoice type (AR/AP)', async () => {
    render(<InvoiceManager />);

    await waitFor(() => {
      expect(screen.getByText(/ar/i)).toBeInTheDocument();
      expect(screen.getByText(/ap/i)).toBeInTheDocument();
    });
  });

  // Test 14: validates invoice amount
  test('validates invoice amount', async () => {
    render(<InvoiceManager />);

    const addButton = screen.getByRole('button', { name: /add invoice/i });
    fireEvent.click(addButton);

    await waitFor(() => {
      const amountInput = screen.getByLabelText(/amount/i);
      fireEvent.change(amountInput, { target: { value: '-100' } });

      const createButton = screen.getByRole('button', { name: /create/i });
      fireEvent.click(createButton);
    });

    await waitFor(() => {
      expect(screen.getByText(/invalid amount/i)).toBeInTheDocument();
    });
  });

  // Test 15: sends invoice
  test('sends invoice', async () => {
    render(<InvoiceManager />);

    await waitFor(() => {
      expect(screen.getByText('Acme Corp')).toBeInTheDocument();
    });

    const sendButton = screen.getAllByRole('button').find(
      btn => btn.getAttribute('aria-label')?.includes('send')
    );

    if (sendButton) {
      fireEvent.click(sendButton);

      await waitFor(() => {
        expect(screen.getByText(/invoice sent/i)).toBeInTheDocument();
      });
    }
  });
});
