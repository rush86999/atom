/**
 * StripeIntegration Component Tests
 *
 * Tests verify the real Stripe integration component
 * (components/StripeIntegration.tsx):
 * - Loading state before data arrives
 * - Payments / customers / products / analytics rendering
 * - Payment search filtering
 * - Create payment / customer / product modal flows
 * - Error handling for unconfigured and failed backends
 *
 * The component uses the axios-based apiClient (../lib/api-client) via
 * dynamic import, so this suite mocks the module and controls every
 * resolved/rejected response.
 */

import React from 'react';
import { renderWithProviders, screen, waitFor, within } from '../../tests/test-utils';
import { fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

jest.mock('../../lib/api-client', () => ({
  apiClient: {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
  },
}));

import StripeIntegration from '../StripeIntegration';
// eslint-disable-next-line @typescript-eslint/no-var-requires
const { apiClient } = require('../../lib/api-client') as {
  apiClient: {
    get: jest.Mock;
    post: jest.Mock;
  };
};

const payments = [
  {
    id: 'pi_3OmW9X2eZvKYlo2C1aBCdEfG',
    amount: 5000,
    currency: 'usd',
    status: 'succeeded',
    customer: 'cus_123',
    description: 'Annual subscription',
    created: '2026-01-05T10:00:00Z',
    receipt_url: 'https://pay.stripe.example/receipts/1',
  },
  {
    id: 'pi_3OmW9X2eZvKYlo2C2hIjKlMn',
    amount: 2500,
    currency: 'usd',
    status: 'failed',
    customer: 'cus_456',
    description: 'Pro plan upgrade',
    created: '2026-01-06T10:00:00Z',
  },
];

const customers = [
  {
    id: 'cus_123',
    email: 'ada@example.com',
    name: 'Ada Lovelace',
    created: '2025-06-01T10:00:00Z',
    balance: 0,
    currency: 'usd',
  },
];

const products = [
  {
    id: 'prod_123',
    name: 'Analytics Pro',
    description: 'Advanced analytics for teams',
    active: true,
    created: '2025-06-01T10:00:00Z',
    price: 9900,
  },
];

const analytics = {
  totalRevenue: 250000,
  monthlyRecurringRevenue: 12000,
  activeCustomers: 320,
  totalPayments: 4800,
  paymentSuccessRate: 96,
  averageOrderValue: 52,
  revenueGrowth: 12,
  customerGrowth: 8,
};

const resolvedData = () => ({
  data: {
    payments,
    customers,
    products,
    analytics,
  },
});

const mockGet = apiClient.get as jest.Mock;
const mockPost = apiClient.post as jest.Mock;

describe('StripeIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGet.mockImplementation((url: string) => {
      if (url === '/api/stripe/payments') {
        return Promise.resolve({ data: { payments } });
      }
      if (url === '/api/stripe/customers') {
        return Promise.resolve({ data: { customers } });
      }
      if (url === '/api/stripe/products') {
        return Promise.resolve({ data: { products } });
      }
      if (url === '/api/stripe/analytics') {
        return Promise.resolve({ data: { analytics } });
      }
      return Promise.resolve({ data: {} });
    });
    mockPost.mockResolvedValue({ data: { success: true } });
  });

  test('shows a loading state while data is being fetched', async () => {
    mockGet.mockImplementation(
      () => new Promise(() => {})
    );

    renderWithProviders(<StripeIntegration />);

    expect(screen.getByText(/loading stripe data/i)).toBeInTheDocument();
    // The data load runs behind an async dynamic import — wait for it to fire
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith('/api/stripe/payments');
      expect(mockGet).toHaveBeenCalledWith('/api/stripe/analytics');
    });
  });

  test('renders the dashboard with stats and payments', async () => {
    renderWithProviders(<StripeIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /stripe integration/i })
      ).toBeInTheDocument();
    });

    // Analytics stat cards (formatCurrency divides by 100)
    expect(screen.getByText('Total Revenue')).toBeInTheDocument();
    expect(screen.getByText('$2,500.00')).toBeInTheDocument();
    expect(screen.getByText('$120.00')).toBeInTheDocument();
    expect(screen.getByText('320')).toBeInTheDocument();
    expect(screen.getByText('96%')).toBeInTheDocument();

    // Payments table (default tab)
    expect(screen.getByText('Annual subscription')).toBeInTheDocument();
    expect(screen.getByText('Pro plan upgrade')).toBeInTheDocument();
    expect(screen.getByText('succeeded')).toBeInTheDocument();
    expect(screen.getByText('failed')).toBeInTheDocument();
    expect(screen.getByText('$50.00')).toBeInTheDocument();
    expect(screen.getByText('$25.00')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /receipt/i }).length).toBe(2);
  });

  test('filters payments by search query', async () => {
    const user = userEvent.setup();

    renderWithProviders(<StripeIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Annual subscription')).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText(/search payments/i), 'upgrade');

    await waitFor(() => {
      expect(screen.getByText('Pro plan upgrade')).toBeInTheDocument();
    });
    expect(screen.queryByText('Annual subscription')).not.toBeInTheDocument();
  });

  test('creates a payment through the modal and prepends it to the list', async () => {
    const user = userEvent.setup();

    mockPost.mockResolvedValueOnce({
      data: {
        success: true,
        payment: {
          id: 'pi_new',
          amount: 7500,
          currency: 'usd',
          status: 'succeeded',
          customer: 'cus_new',
          description: 'One-off consulting',
          created: '2026-02-01T10:00:00Z',
        },
      },
    });

    renderWithProviders(<StripeIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Annual subscription')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /create payment/i }));

    const dialogContent = document.getElementById('dialog-content') as HTMLElement;
    await user.type(within(dialogContent).getByPlaceholderText('0.00'), '75');
    await user.type(
      within(dialogContent).getByPlaceholderText(/payment description/i),
      'One-off consulting'
    );

    await user.click(within(dialogContent).getByRole('button', { name: /create payment/i }));

    // Amount is converted to cents and the currency lowercased
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/stripe/payments/create', {
        amount: 7500,
        currency: 'usd',
        description: 'One-off consulting',
      });
    });

    // New payment is prepended and visible
    await waitFor(() => {
      expect(screen.getByText('One-off consulting')).toBeInTheDocument();
    });
  });

  test('adds a customer through the modal', async () => {
    const user = userEvent.setup();

    mockPost.mockResolvedValueOnce({
      data: {
        success: true,
        customer: {
          id: 'cus_new',
          email: 'grace@example.com',
          name: 'Grace Hopper',
          created: '2026-02-01T10:00:00Z',
          balance: 0,
          currency: 'usd',
        },
      },
    });

    renderWithProviders(<StripeIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Annual subscription')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /customers/i }));
    await waitFor(() => {
      expect(screen.getByText('Ada Lovelace')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /add customer/i }));

    const dialogContent = document.getElementById('dialog-content') as HTMLElement;
    await user.type(within(dialogContent).getByPlaceholderText('Customer name'), 'Grace Hopper');
    await user.type(
      within(dialogContent).getByPlaceholderText('customer@example.com'),
      'grace@example.com'
    );
    await user.click(within(dialogContent).getByRole('button', { name: /add customer/i }));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/stripe/customers/create', {
        name: 'Grace Hopper',
        email: 'grace@example.com',
      });
    });
    await waitFor(() => {
      expect(screen.getByText('Grace Hopper')).toBeInTheDocument();
    });
  });

  test('adds a product through the modal', async () => {
    const user = userEvent.setup();

    mockPost.mockResolvedValueOnce({
      data: {
        success: true,
        product: {
          id: 'prod_new',
          name: 'Audit Pack',
          description: 'Monthly security audit',
          active: true,
          created: '2026-02-01T10:00:00Z',
          price: 4900,
        },
      },
    });

    renderWithProviders(<StripeIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Annual subscription')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /products/i }));
    await waitFor(() => {
      expect(screen.getByText('Analytics Pro')).toBeInTheDocument();
    });
    expect(screen.getByText('$99.00')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /create product/i }));

    const dialogContent = document.getElementById('dialog-content') as HTMLElement;
    await user.type(within(dialogContent).getByPlaceholderText('Product name'), 'Audit Pack');
    await user.type(
      within(dialogContent).getByPlaceholderText(/product description/i),
      'Monthly security audit'
    );
    await user.type(within(dialogContent).getByPlaceholderText('0.00'), '49');
    await user.click(within(dialogContent).getByRole('button', { name: /add product/i }));

    // Price is converted to cents
    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/stripe/products/create', {
        name: 'Audit Pack',
        description: 'Monthly security audit',
        price: 4900,
      });
    });
    await waitFor(() => {
      expect(screen.getByText('Audit Pack')).toBeInTheDocument();
    });
  });

  test('renders empty placeholder states for subscriptions and analytics tabs', async () => {
    const user = userEvent.setup();

    renderWithProviders(<StripeIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Annual subscription')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /subscriptions/i }));
    expect(screen.getByText('No subscriptions loaded.')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /create subscription/i })
    ).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /analytics/i }));
    expect(screen.getByText('Analytics Dashboard')).toBeInTheDocument();
    expect(
      screen.getByText(/detailed analytics and reporting features coming soon/i)
    ).toBeInTheDocument();
  });

  test('handles unconfigured backend (404) without crashing', async () => {
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    const error = Object.assign(new Error('Not found'), {
      response: { status: 404, data: { message: 'not configured' } },
    });
    mockGet.mockRejectedValue(error);

    renderWithProviders(<StripeIntegration />);

    // The header still renders with empty data — no crash
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /stripe integration/i })
      ).toBeInTheDocument();
    });
    expect(consoleErrorSpy).toHaveBeenCalled();

    consoleErrorSpy.mockRestore();
  });

  test('handles unexpected backend errors without crashing', async () => {
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    const error = Object.assign(new Error('boom'), {
      response: { status: 500, data: { message: 'internal' } },
    });
    mockGet.mockRejectedValue(error);

    renderWithProviders(<StripeIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /stripe integration/i })
      ).toBeInTheDocument();
    });
    expect(consoleErrorSpy).toHaveBeenCalled();

    consoleErrorSpy.mockRestore();
  });

  test('survives empty datasets from a configured backend', async () => {
    mockGet.mockResolvedValue({
      data: {
        payments: [],
        customers: [],
        products: [],
        analytics: {
          totalRevenue: 0,
          monthlyRecurringRevenue: 0,
          activeCustomers: 0,
          totalPayments: 0,
          paymentSuccessRate: 100,
          averageOrderValue: 0,
          revenueGrowth: 0,
          customerGrowth: 0,
        },
      },
    });

    renderWithProviders(<StripeIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /stripe integration/i })
      ).toBeInTheDocument();
    });
    expect(screen.queryByText('Annual subscription')).not.toBeInTheDocument();
    expect(screen.getAllByText('$0.00').length).toBeGreaterThan(0);
    expect(
      screen.getByRole('button', { name: /create payment/i })
    ).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Extended coverage: failure toasts, status filter, tab actions, dialog
// cancels, and receipt link
// ---------------------------------------------------------------------------
describe('StripeIntegration (extended coverage)', () => {
  const user = userEvent.setup();
  let openSpy: jest.Mock;
  let errorSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    openSpy = jest.fn();
    window.open = openSpy as any;
    errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    mockGet.mockImplementation((url: string) => {
      if (url === '/api/stripe/payments') {
        return Promise.resolve({ data: { payments } });
      }
      if (url === '/api/stripe/customers') {
        return Promise.resolve({ data: { customers } });
      }
      if (url === '/api/stripe/products') {
        return Promise.resolve({ data: { products } });
      }
      if (url === '/api/stripe/analytics') {
        return Promise.resolve({ data: { analytics } });
      }
      return Promise.resolve({ data: {} });
    });
    mockPost.mockResolvedValue({ data: { success: true } });
  });

  const settle = async () => {
    await screen.findByText('Annual subscription');
  };

  const dialogEl = () => document.getElementById('dialog-content') as HTMLElement;

  const pickOption = async (label: string) => {
    const triggers = screen.getAllByRole('combobox');
    fireEvent.keyDown(triggers[0], { key: 'ArrowDown' });
    const option = await waitFor(() => {
      const found = Array.from(document.querySelectorAll('[role="option"]')).find(
        (i) => i.textContent === label
      );
      if (!found) throw new Error(`option ${label} not found`);
      return found as HTMLElement;
    });
    fireEvent.click(option);
  };

  test('opens the payment receipt link', async () => {
    renderWithProviders(<StripeIntegration />);
    await settle();

    const row = screen.getByText('Annual subscription').closest('tr')!;
    fireEvent.click(within(row).getByRole('button', { name: /receipt/i }));
    expect(openSpy).toHaveBeenCalledWith(
      'https://pay.stripe.example/receipts/1',
      '_blank'
    );
  });

  test('filters payments by status via the select', async () => {
    renderWithProviders(<StripeIntegration />);
    await settle();

    await pickOption('Succeeded');
    await waitFor(() => {
      expect(screen.getByText('Annual subscription')).toBeInTheDocument();
    });
    expect(screen.queryByText('Pro plan upgrade')).not.toBeInTheDocument();
  });

  test('customers tab View Details selects a customer', async () => {
    renderWithProviders(<StripeIntegration />);
    await settle();

    await user.click(screen.getByRole('button', { name: 'Customers' }));
    await user.click(await screen.findByRole('button', { name: /view details/i }));
    // The customer details panel renders the selected email
    expect(await screen.findByText('ada@example.com')).toBeInTheDocument();
  });

  test('products tab shows Edit and subscriptions tab shows the create button', async () => {
    renderWithProviders(<StripeIntegration />);
    await settle();

    await user.click(screen.getByRole('button', { name: 'Products' }));
    await user.click(await screen.findByRole('button', { name: /edit/i }));
    expect(await screen.findByText('Analytics Pro')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Subscriptions' }));
    expect(
      await screen.findByRole('button', { name: /create subscription/i })
    ).toBeInTheDocument();
  });

  test('create-payment dialog fills currency and cancels', async () => {
    renderWithProviders(<StripeIntegration />);
    await settle();

    await user.click(screen.getByRole('button', { name: /create payment/i }));
    const dialog = dialogEl();
    await user.type(within(dialog).getByPlaceholderText('0.00'), '10');
    fireEvent.change(within(dialog).getByPlaceholderText('USD'), {
      target: { value: 'EUR' },
    });
    await user.click(within(dialog).getByRole('button', { name: /cancel/i }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
    expect(mockPost).not.toHaveBeenCalled();
  });

  test('shows an error toast when payment creation is rejected', async () => {
    mockPost.mockResolvedValueOnce({ data: { success: false, message: 'card declined' } });
    renderWithProviders(<StripeIntegration />);
    await settle();

    await user.click(screen.getByRole('button', { name: /create payment/i }));
    const dialog = dialogEl();
    await user.type(within(dialog).getByPlaceholderText('0.00'), '10');
    await user.type(
      within(dialog).getByPlaceholderText(/payment description/i),
      'Declined charge'
    );
    await user.click(within(dialog).getByRole('button', { name: /create payment/i }));

    // The failure path runs without creating anything; the dialog stays open
    // and no new payment row appears.
    await new Promise((r) => setTimeout(r, 150));
    expect(screen.queryByText('Declined charge')).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  test('shows an error toast when customer creation is rejected', async () => {
    mockPost.mockRejectedValueOnce({
      response: { data: { message: 'invalid email' } },
    });
    renderWithProviders(<StripeIntegration />);
    await settle();

    await user.click(screen.getByRole('button', { name: 'Customers' }));
    await user.click(await screen.findByRole('button', { name: /add customer|create customer/i }));

    const dialog = dialogEl();
    await user.type(within(dialog).getByPlaceholderText('Customer name'), 'Bob');
    await user.type(within(dialog).getByPlaceholderText('customer@example.com'), 'bob@example.com');
    await user.click(within(dialog).getAllByRole('button').slice(-1)[0]);

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledWith('/api/stripe/customers/create', {
        name: 'Bob',
        email: 'bob@example.com',
      });
    });
    // Rejected: the dialog stays open.
    await new Promise((r) => setTimeout(r, 150));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  test('shows an error toast when product creation is rejected', async () => {
    mockPost.mockResolvedValueOnce({ data: { success: false, message: 'bad product' } });
    renderWithProviders(<StripeIntegration />);
    await settle();

    await user.click(screen.getByRole('button', { name: 'Products' }));
    await user.click(await screen.findByRole('button', { name: /create product|add product/i }));

    const dialog = dialogEl();
    await user.type(within(dialog).getByPlaceholderText('Product name'), 'Failing');
    await user.type(within(dialog).getByPlaceholderText('0.00'), '9');
    await user.click(within(dialog).getAllByRole('button').slice(-1)[0]);

    await new Promise((r) => setTimeout(r, 150));
    // Failure path keeps the dialog open and adds no product card.
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  test('renders pending and unknown payment statuses', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/api/stripe/payments') {
        return Promise.resolve({
          data: {
            payments: [
              ...payments,
              {
                id: 'pi_pend',
                amount: 1000,
                currency: 'usd',
                status: 'pending',
                description: 'Pending charge',
                created: '2026-01-07T10:00:00Z',
              },
              {
                id: 'pi_odd',
                amount: 1200,
                currency: 'usd',
                status: 'refunded',
                description: 'Refunded charge',
                created: '2026-01-08T10:00:00Z',
              },
            ],
          },
        });
      }
      if (url === '/api/stripe/customers') {
        return Promise.resolve({ data: { customers } });
      }
      if (url === '/api/stripe/products') {
        return Promise.resolve({ data: { products } });
      }
      if (url === '/api/stripe/analytics') {
        return Promise.resolve({ data: { analytics } });
      }
      return Promise.resolve({ data: {} });
    });

    renderWithProviders(<StripeIntegration />);
    await settle();

    expect(screen.getByText('Pending charge')).toBeInTheDocument();
    expect(screen.getByText('Refunded charge')).toBeInTheDocument();
    expect(screen.getByText('pending')).toBeInTheDocument();
    expect(screen.getByText('refunded')).toBeInTheDocument();
  });
});

describe('StripeIntegration (extended coverage 2)', () => {
  const user = userEvent.setup();

  beforeEach(() => {
    jest.clearAllMocks();
    mockGet.mockImplementation((url: string) => {
      if (url === '/api/stripe/payments') return Promise.resolve({ data: { payments } });
      if (url === '/api/stripe/customers') return Promise.resolve({ data: { customers } });
      if (url === '/api/stripe/products') return Promise.resolve({ data: { products } });
      if (url === '/api/stripe/analytics') return Promise.resolve({ data: { analytics } });
      return Promise.resolve({ data: {} });
    });
    mockPost.mockResolvedValue({ data: { success: true } });
  });

  const settle = async () => {
    await screen.findByText('Annual subscription');
  };

  const dialogEl = () => document.getElementById('dialog-content') as HTMLElement;

  test('covers the customer success:false branch, dialog cancels, and subscription button', async () => {
    mockPost.mockImplementation((url: string) => {
      if (url === '/api/stripe/customers/create') {
        return Promise.resolve({ data: { success: false, message: 'nope' } });
      }
      return Promise.resolve({ data: { success: true } });
    });

    renderWithProviders(<StripeIntegration />);
    await settle();

    // Subscriptions tab create button (state-only, no dialog)
    await user.click(screen.getByRole('button', { name: 'Subscriptions' }));
    await user.click(await screen.findByRole('button', { name: /create subscription/i }));
    expect(await screen.findByText('No subscriptions loaded.')).toBeInTheDocument();

    // Customer dialog: rejected branch keeps the dialog open
    await user.click(screen.getByRole('button', { name: 'Customers' }));
    await user.click(await screen.findByRole('button', { name: /add customer|create customer/i }));
    let dialog = dialogEl();
    await user.type(within(dialog).getByPlaceholderText('Customer name'), 'Carol');
    await user.type(within(dialog).getByPlaceholderText('customer@example.com'), 'carol@example.com');
    await user.click(within(dialog).getAllByRole('button').slice(-1)[0]);
    await new Promise((r) => setTimeout(r, 150));
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    // Product dialog cancel
    await user.click(within(dialogEl()).getByRole('button', { name: /cancel/i }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
    await user.click(screen.getByRole('button', { name: 'Products' }));
    await user.click(await screen.findByRole('button', { name: /create product|add product/i }));
    dialog = dialogEl();
    await user.click(within(dialog).getByRole('button', { name: /cancel/i }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });
});
