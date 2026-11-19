import React from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { apiClient } from '@/lib/api-client';
import StripePaymentAllocationProof from '../StripePaymentAllocationProof';

jest.mock('@/lib/api-client', () => ({
    apiClient: {
        get: jest.fn(),
    },
}));

const EVIDENCE_PATH =
    '/api/integrations/stripe/invoice-links/local_invoice_1/payment-evidence';

const proofFor = (
    revision: number,
    overrides: Record<string, unknown> = {}
) => ({
    invoice_id: 'local_invoice_1',
    provider: 'stripe',
    connection_id: 'conn_existing',
    account_id: 'acct_123',
    provider_account_id: 'acct_123',
    provider_mode: 'test',
    external_invoice_id: 'in_existing',
    provider_invoice_id: 'in_existing',
    currency: 'usd',
    amount_minor_units: 1250,
    livemode: false,
    binding_revision: revision,
    evidence_type: 'stripe_invoice_payment_allocation',
    evidence_scope: 'payment_allocation_only',
    allocation_only: true,
    invoice_payment_ids: ['ip_1', 'ip_2'],
    invoice_payment_count: 2,
    paid_allocation_subtotal_minor_units: 1250,
    stripe_api_version: '2024-06-20',
    ...overrides,
});

const deferred = <T,>() => {
    let resolve!: (value: T) => void;
    let reject!: (reason?: unknown) => void;
    const promise = new Promise<T>((res, rej) => {
        resolve = res;
        reject = rej;
    });
    return { promise, resolve, reject };
};

const mockGet = apiClient.get as jest.Mock;

const renderProof = (revision = 3, connectionId = 'conn_existing') =>
    render(
        <StripePaymentAllocationProof
            invoiceId="local_invoice_1"
            connectionId={connectionId}
            bindingRevision={revision}
        />
    );

const verifyButton = () =>
    screen.getByRole('button', { name: 'Verify Stripe payment allocation' });

describe('StripePaymentAllocationProof', () => {
    afterEach(() => {
        cleanup();
        jest.clearAllMocks();
    });

    it('requests the exact payment-evidence GET and shows the verified allocation facts', async () => {
        mockGet.mockResolvedValue({ data: proofFor(3) });

        renderProof();
        fireEvent.click(verifyButton());

        await screen.findByText('Verified payment allocation');

        expect(mockGet).toHaveBeenCalledTimes(1);
        expect(mockGet).toHaveBeenCalledWith(EVIDENCE_PATH, { retry: false });
        expect(screen.getByText('1250 USD (minor units)')).toBeTruthy();
        expect(screen.getByText('Test mode')).toBeTruthy();
        expect(screen.getAllByText('3').length).toBeGreaterThan(0);
        expect(screen.getAllByText(/payment allocation only/i).length).toBeGreaterThan(0);
        expect(screen.getByText('ip_1')).toBeTruthy();
        expect(screen.getByText('ip_2')).toBeTruthy();
    });

    it('clears a displayed proof as soon as the binding revision changes', async () => {
        mockGet.mockResolvedValue({ data: proofFor(3) });

        const { rerender } = renderProof(3);
        fireEvent.click(verifyButton());
        await screen.findByText('Verified payment allocation');

        rerender(
            <StripePaymentAllocationProof
                invoiceId="local_invoice_1"
                connectionId="conn_existing"
                bindingRevision={4}
            />
        );

        expect(screen.queryByText('Verified payment allocation')).toBeNull();
        expect(screen.queryByText('ip_1')).toBeNull();
    });

    it('ignores a late response for a different current binding', async () => {
        const stale = deferred<{ data: unknown }>();
        const current = deferred<{ data: unknown }>();
        mockGet
            .mockImplementationOnce(() => stale.promise)
            .mockImplementationOnce(() => current.promise);

        const { rerender } = renderProof(3);
        fireEvent.click(verifyButton());

        rerender(
            <StripePaymentAllocationProof
                invoiceId="local_invoice_1"
                connectionId="conn_existing"
                bindingRevision={4}
            />
        );

        await act(async () => {
            stale.resolve({
                data: proofFor(3, { invoice_payment_ids: ['ip_stale'] }),
            });
        });

        expect(screen.queryByText('Verified payment allocation')).toBeNull();
        expect(screen.queryByText('ip_stale')).toBeNull();

        fireEvent.click(verifyButton());
        await act(async () => {
            current.resolve({
                data: proofFor(4, {
                    invoice_payment_ids: ['ip_current'],
                    invoice_payment_count: 1,
                }),
            });
        });

        await screen.findByText('ip_current');
        expect(screen.queryByText('ip_stale')).toBeNull();
    });

    it('discards proof on a 409 and makes no payment or settlement claim', async () => {
        mockGet
            .mockResolvedValueOnce({ data: proofFor(3) })
            .mockRejectedValueOnce({ response: { status: 409 } });

        renderProof(3);
        fireEvent.click(verifyButton());
        await screen.findByText('Verified payment allocation');

        fireEvent.click(verifyButton());

        await waitFor(() => {
            expect(
                screen.getByText(/binding or connection changed/i)
            ).toBeTruthy();
        });
        expect(screen.queryByText('Verified payment allocation')).toBeNull();
        expect(screen.queryByText('ip_1')).toBeNull();
        expect(screen.getByRole('alert').textContent).toMatch(
            /no payment or settlement is claimed/i
        );
    });
});
