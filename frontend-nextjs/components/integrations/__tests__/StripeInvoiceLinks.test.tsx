import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { apiClient } from '@/lib/api-client';
import StripeInvoiceLinks from '../StripeInvoiceLinks';

jest.mock('@/lib/api-client', () => ({
    apiClient: {
        get: jest.fn(),
        post: jest.fn(),
        put: jest.fn(),
    },
}));

const LINKS_PATH = '/api/integrations/stripe/invoice-links';

const listPage = {
    items: [
        {
            invoice_id: 'local_invoice_1',
            invoice_number: 'INV-100',
            currency: 'usd',
            amount: '12.50',
            total_minor_units: 1250,
            binding_revision: null,
        },
    ],
    limit: 10,
    offset: 0,
    has_more: false,
    next_offset: null,
};

const binding = {
    provider: 'stripe',
    provider_account_id: 'acct_123',
    provider_mode: 'test',
    external_invoice_id: 'in_existing',
    connection_id: 'conn_existing',
    revision: 3,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
};

const detailFor = (revision: number, currentBinding: typeof binding | null) => ({
    ...listPage.items[0],
    binding_revision: currentBinding?.revision ?? null,
    binding: currentBinding
        ? {
              ...currentBinding,
              revision,
          }
        : null,
    receipts: [],
    limit: 5,
    offset: 0,
    has_more: false,
    next_offset: null,
});

const previewFactsFor = (invoiceId: string) => ({
    account_id: 'acct_123',
    invoice_id: invoiceId,
    currency: 'usd',
    total_minor_units: 1250,
    livemode: false,
    invoice_number: 'INV-100',
});

const mockGet = apiClient.get as jest.Mock;
const mockPost = apiClient.post as jest.Mock;
const mockPut = apiClient.put as jest.Mock;

const selectInvoice = async () => {
    fireEvent.click(await screen.findByRole('radio', { name: /INV-100/ }));
    await screen.findByText('Current link');
};

describe('StripeInvoiceLinks', () => {
    afterEach(() => {
        cleanup();
        jest.clearAllMocks();
    });

    it('uses the existing binding connection instead of asking for one', async () => {
        const detail = detailFor(3, binding);
        mockGet.mockImplementation((url: string) =>
            Promise.resolve({
                data: url === LINKS_PATH ? listPage : detail,
            })
        );

        render(<StripeInvoiceLinks />);
        await selectInvoice();

        expect(screen.getAllByText('conn_existing')).toHaveLength(2);
        expect(screen.queryByLabelText('Stripe connection ID')).toBeNull();
    });

    it('allows a manual connection only when no setup or binding connection exists', async () => {
        const detail = detailFor(0, null);
        mockGet.mockImplementation((url: string) =>
            Promise.resolve({
                data: url === LINKS_PATH ? listPage : detail,
            })
        );

        render(<StripeInvoiceLinks />);
        await selectInvoice();

        expect(
            screen.getByText('No Stripe invoice is linked to this invoice.')
        ).toBeTruthy();
        expect(screen.getByLabelText('Stripe connection ID')).toBeTruthy();
    });

    it('clears the preview on input changes and submits the exact revision and six facts', async () => {
        const detail = detailFor(3, binding);
        mockGet.mockImplementation((url: string) =>
            Promise.resolve({
                data: url === LINKS_PATH ? listPage : detail,
            })
        );
        mockPost.mockImplementation(
            (_url: string, body: { external_invoice_id: string }) =>
                Promise.resolve({ data: previewFactsFor(body.external_invoice_id) })
        );
        mockPut.mockResolvedValue({ data: { revision: 4 } });

        render(<StripeInvoiceLinks />);
        await selectInvoice();

        const externalInput = screen.getByLabelText('Stripe invoice ID');
        fireEvent.change(externalInput, { target: { value: 'in_100' } });
        fireEvent.change(screen.getByLabelText('Reason for correction'), {
            target: { value: 'Correct the invoice mapping' },
        });

        fireEvent.click(screen.getByRole('button', { name: 'Preview link' }));
        await screen.findByText('Fresh preview');

        const confirmButton = screen.getByRole('button', {
            name: 'Confirm link',
        }) as HTMLButtonElement;
        expect(confirmButton.disabled).toBe(false);

        fireEvent.change(externalInput, { target: { value: 'in_101' } });
        await waitFor(() => {
            expect(screen.queryByText('Fresh preview')).toBeNull();
        });
        expect(
            (screen.getByRole('button', { name: 'Confirm link' }) as HTMLButtonElement)
                .disabled
        ).toBe(true);

        fireEvent.click(screen.getByRole('button', { name: 'Preview link' }));
        await screen.findByText('Fresh preview');
        fireEvent.click(screen.getByRole('button', { name: 'Confirm link' }));

        await waitFor(() => {
            expect(mockPut).toHaveBeenCalledTimes(1);
        });

        const [url, body, config] = mockPut.mock.calls[0];
        expect(url).toBe(`${LINKS_PATH}/local_invoice_1`);
        expect(body).toEqual({
            connection_id: 'conn_existing',
            external_invoice_id: 'in_101',
            expected_revision: 3,
            reason: 'Correct the invoice mapping',
            expected_preview: previewFactsFor('in_101'),
        });
        expect(config).toEqual({ retry: false });
    });

    it('refreshes the binding and requires another preview after a 409', async () => {
        let detailCalls = 0;
        mockGet.mockImplementation((url: string) => {
            if (url === LINKS_PATH) {
                return Promise.resolve({ data: listPage });
            }
            detailCalls += 1;
            return Promise.resolve({
                data: detailFor(
                    detailCalls === 1 ? 3 : 4,
                    detailCalls === 1 ? binding : { ...binding, revision: 4 }
                ),
            });
        });
        mockPost.mockResolvedValue({ data: previewFactsFor('in_100') });
        mockPut.mockRejectedValueOnce({
            response: { status: 409, data: { detail: 'conflict' } },
        });

        render(<StripeInvoiceLinks />);
        await selectInvoice();

        fireEvent.change(screen.getByLabelText('Stripe invoice ID'), {
            target: { value: 'in_100' },
        });
        fireEvent.change(screen.getByLabelText('Reason for correction'), {
            target: { value: 'Correct the invoice mapping' },
        });
        fireEvent.click(screen.getByRole('button', { name: 'Preview link' }));
        await screen.findByText('Fresh preview');
        fireEvent.click(screen.getByRole('button', { name: 'Confirm link' }));

        await screen.findByText(/current link was refreshed/i);
        expect(mockPut).toHaveBeenCalledTimes(1);
        expect(screen.queryByText('Fresh preview')).toBeNull();
        await waitFor(() => {
            expect(detailCalls).toBe(2);
        });
        expect(
            (screen.getByRole('button', { name: 'Confirm link' }) as HTMLButtonElement)
                .disabled
        ).toBe(true);
    });
});
