/**
 * ShopifyManager component tests.
 *
 * NOTE: this suite mocks the skill module contract (re-created at
 * not exist in this repository (confirmed via `find` — no src/skills dir).
 * This is a latent missing-import bug; the tests mock that module with its
 * documented contract ({ ok, data, error }) so the component logic is
 * exercised meaningfully.
 *
 * Covers: status fetch (connected/disconnected/failure), Connect validation
 * (shop name required), redirect with shop name, and disconnect flow.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { useSession } from 'next-auth/react';
import ShopifyManager from '../ShopifyManager';

jest.mock('next-auth/react', () => ({
  useSession: jest.fn(),
}));

const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

jest.mock('../skills/shopifySkills', () => ({
  getShopifyConnectionStatus: jest.fn(),
  disconnectShopify: jest.fn(),
}));

import { getShopifyConnectionStatus, disconnectShopify } from '../skills/shopifySkills';

const mockSession = useSession as jest.Mock;
const mockGetStatus = getShopifyConnectionStatus as jest.Mock;
const mockDisconnect = disconnectShopify as jest.Mock;

describe('ShopifyManager', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSession.mockReturnValue({ data: { user: { id: 'u1' } }, status: 'authenticated' });
    mockGetStatus.mockResolvedValue({ ok: true, data: { isConnected: false, reason: '' } });
    mockDisconnect.mockResolvedValue({ ok: true });
  });

  it('renders Disconnected state with shop-name form', async () => {
    render(<ShopifyManager />);
    expect(await screen.findByText('Shopify Management')).toBeInTheDocument();
    expect(screen.getByText('Disconnected')).toBeInTheDocument();
    expect(screen.getByText('Not Connected.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Connect Shopify/ })).toBeInTheDocument();
  });

  it('renders the connected shop URL and Disconnect button when connected', async () => {
    mockGetStatus.mockResolvedValue({ ok: true, data: { isConnected: true, shopUrl: 'https://my-store.myshopify.com', reason: '' } });
    render(<ShopifyManager />);
    expect(await screen.findByText('Connected')).toBeInTheDocument();
    expect(screen.getByText('https://my-store.myshopify.com')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Disconnect Shopify/ })).toBeInTheDocument();
  });

  it('shows the status error message on failed status call', async () => {
    mockGetStatus.mockResolvedValue({ ok: false, error: { message: 'no shopify' } });
    render(<ShopifyManager />);
    expect(await screen.findByText('no shopify')).toBeInTheDocument();
  });

  it('shows the exception message when the status call throws', async () => {
    mockGetStatus.mockRejectedValue(new Error('boom'));
    render(<ShopifyManager />);
    expect(await screen.findByText('boom')).toBeInTheDocument();
  });

  it('toasts a shop-name-required error when connecting without a shop name', async () => {
    render(<ShopifyManager />);
    fireEvent.click(await screen.findByRole('button', { name: /Connect Shopify/ }));
    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Shop Name Required', variant: 'error' })
      );
    });
  });

  it('opens the Shopify auth redirect with the shop name', async () => {
    const openSpy = jest.spyOn(window, 'open').mockImplementation(() => null);
    render(<ShopifyManager />);
    const input = (await screen.findByLabelText(/Shop Name/)) as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'my-great-store' } });
    fireEvent.click(screen.getByRole('button', { name: /Connect Shopify/ }));
    expect(openSpy).toHaveBeenCalledWith(
      expect.stringContaining('/api/shopify/auth?user_id=u1&shop_name=my-great-store'),
      '_self'
    );
  });

  it('disconnects and refreshes to the disconnected state', async () => {
    mockGetStatus
      .mockResolvedValueOnce({ ok: true, data: { isConnected: true, shopUrl: 'x.myshopify.com', reason: '' } })
      .mockResolvedValueOnce({ ok: true, data: { isConnected: false, reason: '' } });
    render(<ShopifyManager />);
    fireEvent.click(await screen.findByRole('button', { name: /Disconnect Shopify/ }));
    await waitFor(() => {
      expect(mockDisconnect).toHaveBeenCalledWith('u1');
    });
    expect(await screen.findByRole('button', { name: /Connect Shopify/ })).toBeInTheDocument();
  });

  it('surfaces the disconnect error message', async () => {
    mockGetStatus.mockResolvedValue({ ok: true, data: { isConnected: true, shopUrl: 'x.myshopify.com', reason: '' } });
    mockDisconnect.mockResolvedValue({ ok: false, error: { message: 'disconnect failed' } });
    render(<ShopifyManager />);
    fireEvent.click(await screen.findByRole('button', { name: /Disconnect Shopify/ }));
    await waitFor(() => {
      expect(screen.getByText(/Error: disconnect failed/)).toBeInTheDocument();
    });
  });
});
