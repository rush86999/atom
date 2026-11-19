import React, { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { apiClient } from '@/lib/api-client';

const LINKS_PATH = '/api/integrations/stripe/invoice-links';
const EVIDENCE_TYPE = 'stripe_invoice_payment_allocation';
const EVIDENCE_SCOPE = 'payment_allocation_only';

type StripePaymentAllocationProofProps = {
    invoiceId: string;
    connectionId: string;
    bindingRevision: number;
};

type PaymentAllocationProof = {
    invoiceId: string;
    connectionId: string;
    bindingRevision: number;
    currency: string;
    amountMinorUnits: number;
    providerMode: 'test' | 'live';
    paymentIds: string[];
    stripeApiVersion: string;
};

type ProofResult = {
    invoiceId: string;
    connectionId: string;
    bindingRevision: number;
    proof: PaymentAllocationProof;
};

const asRecord = (value: unknown): Record<string, unknown> | null => {
    if (value === null || typeof value !== 'object' || Array.isArray(value)) {
        return null;
    }
    return value as Record<string, unknown>;
};

const asNonEmptyString = (value: unknown): string | null =>
    typeof value === 'string' && value.trim() ? value.trim() : null;

const asNonNegativeInteger = (value: unknown): number | null =>
    typeof value === 'number' && Number.isInteger(value) && value >= 0 ? value : null;

const asRevision = (value: unknown): number | null =>
    typeof value === 'number' && Number.isInteger(value) && value >= 1 ? value : null;

const errorStatus = (error: unknown): number | null => {
    const candidate = asRecord(error);
    const response = candidate ? asRecord(candidate.response) : null;
    const status = response?.status;
    return typeof status === 'number' ? status : null;
};

const parsePaymentAllocationProof = (
    value: unknown
): PaymentAllocationProof | null => {
    const record = asRecord(value);
    if (!record) {
        return null;
    }
    if (
        record.evidence_type !== EVIDENCE_TYPE ||
        record.evidence_scope !== EVIDENCE_SCOPE ||
        record.allocation_only !== true
    ) {
        return null;
    }

    const invoiceId = asNonEmptyString(record.invoice_id);
    const connectionId = asNonEmptyString(record.connection_id);
    const currency = asNonEmptyString(record.currency);
    const bindingRevision = asRevision(record.binding_revision);
    const amountMinorUnits = asNonNegativeInteger(record.amount_minor_units);
    const paidSubtotal = asNonNegativeInteger(
        record.paid_allocation_subtotal_minor_units
    );
    const providerMode = record.provider_mode;
    const livemode = record.livemode;
    const stripeApiVersion = asNonEmptyString(record.stripe_api_version);

    if (
        !invoiceId ||
        !connectionId ||
        !currency ||
        bindingRevision === null ||
        amountMinorUnits === null ||
        paidSubtotal !== amountMinorUnits ||
        (providerMode !== 'test' && providerMode !== 'live') ||
        typeof livemode !== 'boolean' ||
        livemode !== (providerMode === 'live') ||
        !stripeApiVersion
    ) {
        return null;
    }

    const rawPaymentIds = record.invoice_payment_ids;
    if (!Array.isArray(rawPaymentIds) || rawPaymentIds.length === 0) {
        return null;
    }
    const paymentIds: string[] = [];
    for (const rawPaymentId of rawPaymentIds) {
        const paymentId = asNonEmptyString(rawPaymentId);
        if (!paymentId || paymentIds.includes(paymentId)) {
            return null;
        }
        paymentIds.push(paymentId);
    }
    if (
        asNonNegativeInteger(record.invoice_payment_count) !== paymentIds.length
    ) {
        return null;
    }

    return {
        invoiceId,
        connectionId,
        bindingRevision,
        currency: currency.toLowerCase(),
        amountMinorUnits,
        providerMode,
        paymentIds,
        stripeApiVersion,
    };
};

const evidenceErrorMessage = (status: number | null): string => {
    if (status === 403) {
        return 'Workspace admin access is required. No payment or settlement is claimed.';
    }
    if (status === 404) {
        return 'No stored Stripe binding was found for this invoice. No payment or settlement is claimed.';
    }
    if (status === 409) {
        return 'The Stripe invoice binding or connection changed, so the proof was discarded. No payment or settlement is claimed.';
    }
    if (status === 502 || status === 503 || status === 504 || status === null) {
        return 'Stripe payment evidence is temporarily unavailable. No payment or settlement is claimed.';
    }
    return 'Stripe payment allocation could not be verified. No payment or settlement is claimed.';
};

const StripePaymentAllocationProof = ({
    invoiceId,
    connectionId,
    bindingRevision,
}: StripePaymentAllocationProofProps) => {
    const [result, setResult] = useState<ProofResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const requestRef = useRef(0);
    const bindingKey = [
        invoiceId,
        connectionId,
        String(bindingRevision),
    ].join('\u0000');
    const currentBindingKeyRef = useRef(bindingKey);
    currentBindingKeyRef.current = bindingKey;

    // A selection, binding revision, or connection change invalidates any
    // proof immediately and makes every in-flight response stale.
    useEffect(() => {
        requestRef.current += 1;
        setResult(null);
        setError(null);
        setLoading(false);
    }, [bindingKey]);

    const isBound = Boolean(
        invoiceId.trim() && connectionId.trim() && bindingRevision >= 1
    );

    const handleVerify = async () => {
        if (!isBound || loading) {
            return;
        }

        const requestId = requestRef.current + 1;
        requestRef.current = requestId;
        const requestKey = bindingKey;

        setLoading(true);
        setResult(null);
        setError(null);

        try {
            const response = await apiClient.get(
                `${LINKS_PATH}/${encodeURIComponent(invoiceId)}/payment-evidence`,
                { retry: false }
            );

            if (
                requestId !== requestRef.current ||
                requestKey !== currentBindingKeyRef.current
            ) {
                return;
            }

            const proof = parsePaymentAllocationProof(response.data);
            if (
                !proof ||
                proof.invoiceId !== invoiceId ||
                proof.connectionId !== connectionId ||
                proof.bindingRevision !== bindingRevision
            ) {
                setError(
                    'The payment evidence did not match this link. No proof was recorded. No payment or settlement is claimed.'
                );
                return;
            }

            setResult({
                invoiceId,
                connectionId,
                bindingRevision,
                proof,
            });
        } catch (requestError) {
            if (
                requestId !== requestRef.current ||
                requestKey !== currentBindingKeyRef.current
            ) {
                return;
            }
            setError(evidenceErrorMessage(errorStatus(requestError)));
        } finally {
            if (requestId === requestRef.current) {
                setLoading(false);
            }
        }
    };

    if (!isBound) {
        return null;
    }

    const visibleProof =
        result &&
        result.invoiceId === invoiceId &&
        result.connectionId === connectionId &&
        result.bindingRevision === bindingRevision
            ? result.proof
            : null;

    return (
        <div className="space-y-3 rounded-md border p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <h4 className="text-sm font-semibold">Payment allocation proof</h4>
                <Button
                    type="button"
                    variant="outline"
                    onClick={handleVerify}
                    disabled={loading}
                >
                    {loading ? 'Verifying…' : 'Verify Stripe payment allocation'}
                </Button>
            </div>
            <p className="text-xs text-muted-foreground">
                Read-only evidence for this linked invoice. Scope is payment allocation
                only.
            </p>

            {error && (
                <p role="alert" className="text-sm text-destructive">
                    {error}
                </p>
            )}

            {visibleProof && (
                <div
                    className="space-y-2 rounded-md border bg-muted/30 p-3"
                    aria-live="polite"
                >
                    <h5 className="text-sm font-semibold">
                        Verified payment allocation
                    </h5>
                    <dl className="grid gap-2 text-sm sm:grid-cols-2">
                        <div>
                            <dt className="text-muted-foreground">Amount</dt>
                            <dd>
                                {visibleProof.amountMinorUnits}{' '}
                                {visibleProof.currency.toUpperCase()} (minor units)
                            </dd>
                        </div>
                        <div>
                            <dt className="text-muted-foreground">Mode</dt>
                            <dd>
                                {visibleProof.providerMode === 'live'
                                    ? 'Live mode'
                                    : 'Test mode'}
                            </dd>
                        </div>
                        <div>
                            <dt className="text-muted-foreground">Binding revision</dt>
                            <dd>{visibleProof.bindingRevision}</dd>
                        </div>
                        <div>
                            <dt className="text-muted-foreground">Scope</dt>
                            <dd>Payment allocation only</dd>
                        </div>
                        <div className="sm:col-span-2">
                            <dt className="text-muted-foreground">
                                Verified payment IDs
                            </dt>
                            <dd>
                                <ul className="list-disc break-all pl-5">
                                    {visibleProof.paymentIds.map((paymentId) => (
                                        <li key={paymentId}>{paymentId}</li>
                                    ))}
                                </ul>
                            </dd>
                        </div>
                    </dl>
                    <p className="text-xs text-muted-foreground">
                        Scope: payment allocation only. This proof makes no settlement,
                        payout, or ledger claim.
                    </p>
                </div>
            )}
        </div>
    );
};

export default StripePaymentAllocationProof;
