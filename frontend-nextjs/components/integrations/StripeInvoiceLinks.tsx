import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { apiClient } from '@/lib/api-client';

const LINKS_PATH = '/api/integrations/stripe/invoice-links';
const INVOICE_PAGE_SIZE = 10;
const REVISION_PAGE_SIZE = 5;

type InvoiceListItem = {
    invoice_id: string;
    invoice_number: string | null;
    currency: string | null;
    amount: string | null;
    total_minor_units: number | null;
    binding_revision: number | null;
};

type InvoiceListPage = {
    items: InvoiceListItem[];
    limit: number;
    offset: number;
    has_more: boolean;
    next_offset: number | null;
};

type InvoiceBinding = {
    provider: string;
    provider_account_id: string;
    provider_mode: string;
    external_invoice_id: string;
    connection_id: string;
    revision: number;
    created_at: string | null;
    updated_at: string | null;
};

type RevisionReceipt = {
    revision: number;
    actor_id: string;
    reason: string | null;
    created_at: string | null;
    prior_provider: string | null;
    prior_provider_account_id: string | null;
    prior_provider_mode: string | null;
    prior_external_invoice_id: string | null;
    prior_connection_id: string | null;
    new_provider: string | null;
    new_provider_account_id: string | null;
    new_provider_mode: string | null;
    new_external_invoice_id: string | null;
    new_connection_id: string | null;
};

type InvoiceLinkDetail = InvoiceListItem & {
    binding: InvoiceBinding | null;
    receipts: RevisionReceipt[];
    limit: number;
    offset: number;
    has_more: boolean;
    next_offset: number | null;
};

type PreviewFacts = {
    account_id: string;
    invoice_id: string;
    currency: string;
    total_minor_units: number;
    livemode: boolean;
    invoice_number: string | null;
};

type PreviewState = {
    facts: PreviewFacts;
    formKey: string;
    expectedRevision: number | null;
    invoiceId: string;
    connectionId: string;
    externalInvoiceId: string;
};

type StripeInvoiceLinksProps = {
    setupConnectionId?: string | null;
};

const PREVIEW_FACT_FIELDS = [
    'account_id',
    'invoice_id',
    'currency',
    'total_minor_units',
    'livemode',
    'invoice_number',
] as const;

const asRecord = (value: unknown): Record<string, unknown> | null => {
    if (value === null || typeof value !== 'object' || Array.isArray(value)) {
        return null;
    }
    return value as Record<string, unknown>;
};

const asNonEmptyString = (value: unknown): string | null => {
    if (typeof value !== 'string' || !value.trim()) {
        return null;
    }
    return value.trim();
};

const asNullableString = (value: unknown): string | null =>
    typeof value === 'string' ? value : null;

const asRevision = (value: unknown): number | null =>
    typeof value === 'number' && Number.isInteger(value) && value >= 0
        ? value
        : null;

const asCount = (value: unknown, fallback: number): number =>
    typeof value === 'number' && Number.isInteger(value) && value >= 0
        ? value
        : fallback;

const errorStatus = (error: unknown): number | null => {
    const candidate = asRecord(error);
    const response = candidate ? asRecord(candidate.response) : null;
    const status = response?.status;
    return typeof status === 'number' ? status : null;
};

const parseInvoiceListItem = (value: unknown): InvoiceListItem | null => {
    const record = asRecord(value);
    if (!record) {
        return null;
    }
    const invoiceId = asNonEmptyString(record.invoice_id);
    if (!invoiceId) {
        return null;
    }
    return {
        invoice_id: invoiceId,
        invoice_number: asNullableString(record.invoice_number),
        currency: asNullableString(record.currency),
        amount:
            typeof record.amount === 'number'
                ? String(record.amount)
                : asNullableString(record.amount),
        total_minor_units: asRevision(record.total_minor_units),
        binding_revision: asRevision(record.binding_revision),
    };
};

const parseInvoiceListPage = (value: unknown): InvoiceListPage | null => {
    const record = asRecord(value);
    if (!record || !Array.isArray(record.items)) {
        return null;
    }
    const items: InvoiceListItem[] = [];
    for (const item of record.items) {
        const parsed = parseInvoiceListItem(item);
        if (!parsed) {
            return null;
        }
        items.push(parsed);
    }
    return {
        items,
        limit: asCount(record.limit, INVOICE_PAGE_SIZE),
        offset: asCount(record.offset, 0),
        has_more: record.has_more === true,
        next_offset: asRevision(record.next_offset),
    };
};

const parseBinding = (value: unknown): InvoiceBinding | null => {
    const record = asRecord(value);
    if (!record) {
        return null;
    }
    const revision = asRevision(record.revision);
    const connectionId = asNonEmptyString(record.connection_id);
    const externalInvoiceId = asNonEmptyString(record.external_invoice_id);
    if (revision === null || !connectionId || !externalInvoiceId) {
        return null;
    }
    return {
        provider: asNonEmptyString(record.provider) ?? '',
        provider_account_id: asNonEmptyString(record.provider_account_id) ?? '',
        provider_mode: asNonEmptyString(record.provider_mode) ?? '',
        external_invoice_id: externalInvoiceId,
        connection_id: connectionId,
        revision,
        created_at: asNullableString(record.created_at),
        updated_at: asNullableString(record.updated_at),
    };
};

const parseRevisionReceipt = (value: unknown): RevisionReceipt | null => {
    const record = asRecord(value);
    if (!record) {
        return null;
    }
    const revision = asRevision(record.revision);
    if (revision === null) {
        return null;
    }
    return {
        revision,
        actor_id: asNonEmptyString(record.actor_id) ?? '',
        reason: asNullableString(record.reason),
        created_at: asNullableString(record.created_at),
        prior_provider: asNullableString(record.prior_provider),
        prior_provider_account_id: asNullableString(record.prior_provider_account_id),
        prior_provider_mode: asNullableString(record.prior_provider_mode),
        prior_external_invoice_id: asNullableString(record.prior_external_invoice_id),
        prior_connection_id: asNullableString(record.prior_connection_id),
        new_provider: asNullableString(record.new_provider),
        new_provider_account_id: asNullableString(record.new_provider_account_id),
        new_provider_mode: asNullableString(record.new_provider_mode),
        new_external_invoice_id: asNullableString(record.new_external_invoice_id),
        new_connection_id: asNullableString(record.new_connection_id),
    };
};

const parseInvoiceLinkDetail = (value: unknown): InvoiceLinkDetail | null => {
    const invoice = parseInvoiceListItem(value);
    const record = asRecord(value);
    if (!invoice || !record) {
        return null;
    }

    let binding: InvoiceBinding | null = null;
    if (record.binding !== null && record.binding !== undefined) {
        binding = parseBinding(record.binding);
        if (!binding) {
            return null;
        }
    }

    const rawReceipts = Array.isArray(record.receipts) ? record.receipts : [];
    const receipts: RevisionReceipt[] = [];
    for (const receipt of rawReceipts) {
        const parsed = parseRevisionReceipt(receipt);
        if (!parsed) {
            return null;
        }
        receipts.push(parsed);
    }

    return {
        ...invoice,
        binding,
        receipts,
        limit: asCount(record.limit, REVISION_PAGE_SIZE),
        offset: asCount(record.offset, 0),
        has_more: record.has_more === true,
        next_offset: asRevision(record.next_offset),
    };
};

const parsePreviewFacts = (value: unknown): PreviewFacts | null => {
    const record = asRecord(value);
    if (!record) {
        return null;
    }
    const keys = Object.keys(record);
    if (
        keys.length !== PREVIEW_FACT_FIELDS.length ||
        !PREVIEW_FACT_FIELDS.every((field) => field in record)
    ) {
        return null;
    }

    const accountId = asNonEmptyString(record.account_id);
    const invoiceId = asNonEmptyString(record.invoice_id);
    const currency = asNonEmptyString(record.currency);
    const totalMinorUnits = record.total_minor_units;
    const livemode = record.livemode;
    const invoiceNumber = record.invoice_number;

    if (
        !accountId ||
        !invoiceId ||
        !currency ||
        typeof totalMinorUnits !== 'number' ||
        !Number.isInteger(totalMinorUnits) ||
        totalMinorUnits < 0 ||
        typeof livemode !== 'boolean' ||
        (invoiceNumber !== null &&
            (typeof invoiceNumber !== 'string' || !invoiceNumber))
    ) {
        return null;
    }

    return {
        account_id: accountId,
        invoice_id: invoiceId,
        currency,
        total_minor_units: totalMinorUnits,
        livemode,
        invoice_number: typeof invoiceNumber === 'string' ? invoiceNumber : null,
    };
};

const invoiceListErrorMessage = (error: unknown): string => {
    const status = errorStatus(error);
    if (status === 403) {
        return 'Workspace admin access is required.';
    }
    return 'Unable to load durable invoices.';
};

const invoiceDetailErrorMessage = (error: unknown): string => {
    const status = errorStatus(error);
    if (status === 403) {
        return 'Workspace admin access is required.';
    }
    if (status === 404) {
        return 'Invoice not found.';
    }
    return 'Unable to load this invoice link.';
};

const previewErrorMessage = (status: number | null): string => {
    if (status === 400) {
        return 'Check the connection ID and Stripe invoice ID.';
    }
    if (status === 403) {
        return 'This Stripe connection is not usable by your workspace.';
    }
    if (status === 404) {
        return 'Invoice or Stripe connection not found.';
    }
    if (status === 409) {
        return 'Stripe could not verify this invoice. Preview again.';
    }
    return 'Preview failed. Nothing was changed.';
};

const saveErrorMessage = (status: number | null): string => {
    if (status === 400) {
        return 'Check the form. Nothing was saved.';
    }
    if (status === 403) {
        return 'This Stripe connection is not usable by your workspace.';
    }
    if (status === 404) {
        return 'Invoice or Stripe connection not found. Nothing was saved.';
    }
    return 'Unable to save the link. Nothing was changed.';
};

const formatTimestamp = (value: string | null): string => {
    if (!value) {
        return '—';
    }
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
};

const referenceValue = (value: string | null): string =>
    value && value.trim() ? value : '—';

type ReferenceListProps = {
    title: string;
    provider: string | null;
    account: string | null;
    mode: string | null;
    externalInvoiceId: string | null;
    connectionId: string | null;
    emptyLabel: string;
};

const ReferenceList = ({
    title,
    provider,
    account,
    mode,
    externalInvoiceId,
    connectionId,
    emptyLabel,
}: ReferenceListProps) => {
    const values = [provider, account, mode, externalInvoiceId, connectionId];
    const hasValue = values.some((value) => Boolean(value && value.trim()));

    return (
        <div className="space-y-1">
            <h5 className="text-sm font-medium">{title}</h5>
            {hasValue ? (
                <dl className="grid gap-1 text-sm sm:grid-cols-2">
                    <div>
                        <dt className="text-muted-foreground">Provider</dt>
                        <dd className="break-words">{referenceValue(provider)}</dd>
                    </div>
                    <div>
                        <dt className="text-muted-foreground">Account</dt>
                        <dd className="break-all">{referenceValue(account)}</dd>
                    </div>
                    <div>
                        <dt className="text-muted-foreground">Mode</dt>
                        <dd>{referenceValue(mode)}</dd>
                    </div>
                    <div>
                        <dt className="text-muted-foreground">External invoice</dt>
                        <dd className="break-all">{referenceValue(externalInvoiceId)}</dd>
                    </div>
                    <div className="sm:col-span-2">
                        <dt className="text-muted-foreground">Connection</dt>
                        <dd className="break-all">{referenceValue(connectionId)}</dd>
                    </div>
                </dl>
            ) : (
                <p className="text-sm text-muted-foreground">{emptyLabel}</p>
            )}
        </div>
    );
};

const StripeInvoiceLinks = ({ setupConnectionId }: StripeInvoiceLinksProps) => {
    const normalizedSetupConnectionId =
        typeof setupConnectionId === 'string' ? setupConnectionId.trim() : '';

    const [listPage, setListPage] = useState<InvoiceListPage | null>(null);
    const [listOffset, setListOffset] = useState(0);
    const [listLoading, setListLoading] = useState(false);
    const [listError, setListError] = useState<string | null>(null);

    const [selectedInvoiceId, setSelectedInvoiceId] = useState<string | null>(null);
    const [detail, setDetail] = useState<InvoiceLinkDetail | null>(null);
    const [detailLoading, setDetailLoading] = useState(false);
    const [detailError, setDetailError] = useState<string | null>(null);
    const [revisionOffset, setRevisionOffset] = useState(0);

    const [manualConnectionId, setManualConnectionId] = useState('');
    const [externalInvoiceId, setExternalInvoiceId] = useState('');
    const [reason, setReason] = useState('');

    const [preview, setPreview] = useState<PreviewState | null>(null);
    const [isPreviewing, setIsPreviewing] = useState(false);
    const [previewError, setPreviewError] = useState<string | null>(null);

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [submitError, setSubmitError] = useState<string | null>(null);
    const [submitMessage, setSubmitMessage] = useState<string | null>(null);

    const listRequestRef = useRef(0);
    const detailRequestRef = useRef(0);
    const previewRequestRef = useRef(0);
    const submitRef = useRef(false);
    const bindingRevisionRef = useRef<number | null | undefined>(undefined);
    const latestFormKeyRef = useRef('');

    const invalidatePreview = useCallback(() => {
        previewRequestRef.current += 1;
        setPreview(null);
        setPreviewError(null);
        setIsPreviewing(false);
    }, []);

    useEffect(() => {
        let cancelled = false;
        const requestId = listRequestRef.current + 1;
        listRequestRef.current = requestId;

        setListLoading(true);
        setListError(null);
        setListPage(null);

        const load = async () => {
            try {
                const response = await apiClient.get(LINKS_PATH, {
                    params: { limit: INVOICE_PAGE_SIZE, offset: listOffset },
                    retry: false,
                });
                if (cancelled || requestId !== listRequestRef.current) {
                    return;
                }
                const page = parseInvoiceListPage(response.data);
                if (!page) {
                    throw new Error('Invalid invoice list response');
                }
                setListPage(page);
            } catch (error) {
                if (cancelled || requestId !== listRequestRef.current) {
                    return;
                }
                setListError(invoiceListErrorMessage(error));
            } finally {
                if (!cancelled && requestId === listRequestRef.current) {
                    setListLoading(false);
                }
            }
        };

        void load();

        return () => {
            cancelled = true;
        };
    }, [listOffset]);

    const loadDetail = useCallback(
        async (invoiceId: string, offset: number): Promise<boolean> => {
            const requestId = detailRequestRef.current + 1;
            detailRequestRef.current = requestId;

            setDetailLoading(true);
            setDetailError(null);

            try {
                const response = await apiClient.get(
                    `${LINKS_PATH}/${encodeURIComponent(invoiceId)}`,
                    {
                        params: { limit: REVISION_PAGE_SIZE, offset },
                        retry: false,
                    }
                );
                if (requestId !== detailRequestRef.current) {
                    return false;
                }
                const parsed = parseInvoiceLinkDetail(response.data);
                if (!parsed || parsed.invoice_id !== invoiceId) {
                    throw new Error('Invalid invoice link response');
                }

                setDetail(parsed);

                const nextRevision = parsed.binding?.revision ?? null;
                if (bindingRevisionRef.current !== nextRevision) {
                    bindingRevisionRef.current = nextRevision;
                    invalidatePreview();
                }
                return true;
            } catch (error) {
                if (requestId !== detailRequestRef.current) {
                    return false;
                }
                setDetailError(invoiceDetailErrorMessage(error));
                return false;
            } finally {
                if (requestId === detailRequestRef.current) {
                    setDetailLoading(false);
                }
            }
        },
        [invalidatePreview]
    );

    useEffect(() => {
        if (!selectedInvoiceId) {
            return;
        }
        void loadDetail(selectedInvoiceId, revisionOffset);
    }, [selectedInvoiceId, revisionOffset, loadDetail]);

    const binding = detail?.binding ?? null;
    const isCorrection = binding !== null;
    const bindingConnectionId = binding?.connection_id?.trim() ?? '';
    const usingSetupConnection = Boolean(normalizedSetupConnectionId);
    const usingBindingConnection = !usingSetupConnection && Boolean(bindingConnectionId);
    const autoConnectionId = usingSetupConnection
        ? normalizedSetupConnectionId
        : bindingConnectionId;
    const connectionSource = usingSetupConnection
        ? 'setup'
        : usingBindingConnection
            ? 'binding'
            : 'manual';
    const effectiveConnectionId = autoConnectionId || manualConnectionId;
    const expectedRevision = binding?.revision ?? null;

    useEffect(() => {
        if (autoConnectionId) {
            setManualConnectionId('');
        }
    }, [autoConnectionId]);

    const formKey = [
        selectedInvoiceId ?? '',
        connectionSource,
        effectiveConnectionId,
        externalInvoiceId,
        reason,
        expectedRevision === null ? '' : String(expectedRevision),
    ].join('\u0000');

    latestFormKeyRef.current = formKey;

    const previousFormKeyRef = useRef(formKey);
    useEffect(() => {
        if (previousFormKeyRef.current !== formKey) {
            previousFormKeyRef.current = formKey;
            invalidatePreview();
        }
    }, [formKey, invalidatePreview]);

    const trimmedConnectionId = effectiveConnectionId.trim();
    const trimmedExternalInvoiceId = externalInvoiceId.trim();
    const canPreview = Boolean(
        detail &&
            selectedInvoiceId &&
            trimmedConnectionId &&
            trimmedExternalInvoiceId &&
            (!isCorrection || reason.trim()) &&
            !isPreviewing &&
            !isSubmitting
    );
    const canConfirm = Boolean(
        preview &&
            detail &&
            selectedInvoiceId &&
            preview.invoiceId === selectedInvoiceId &&
            preview.formKey === formKey &&
            !isPreviewing &&
            !isSubmitting
    );

    const handleSelectInvoice = (invoiceId: string) => {
        if (isSubmitting || invoiceId === selectedInvoiceId) {
            return;
        }
        detailRequestRef.current += 1;
        setSelectedInvoiceId(invoiceId);
        setDetail(null);
        setDetailError(null);
        setDetailLoading(false);
        setRevisionOffset(0);
        setExternalInvoiceId('');
        setReason('');
        setSubmitError(null);
        setSubmitMessage(null);
        bindingRevisionRef.current = undefined;
        invalidatePreview();
    };

    const handleManualConnectionChange = (
        event: React.ChangeEvent<HTMLInputElement>
    ) => {
        invalidatePreview();
        setSubmitError(null);
        setSubmitMessage(null);
        setManualConnectionId(event.target.value);
    };

    const handleExternalInvoiceChange = (
        event: React.ChangeEvent<HTMLInputElement>
    ) => {
        invalidatePreview();
        setSubmitError(null);
        setSubmitMessage(null);
        setExternalInvoiceId(event.target.value);
    };

    const handleReasonChange = (
        event: React.ChangeEvent<HTMLTextAreaElement>
    ) => {
        invalidatePreview();
        setSubmitError(null);
        setSubmitMessage(null);
        setReason(event.target.value);
    };

    const handlePreview = async () => {
        if (!detail || !selectedInvoiceId) {
            return;
        }

        const connectionId = effectiveConnectionId.trim();
        const externalId = externalInvoiceId.trim();

        if (!connectionId) {
            setPreviewError('Enter a Stripe connection ID.');
            return;
        }
        if (!externalId) {
            setPreviewError('Enter the Stripe invoice ID.');
            return;
        }
        if (isCorrection && !reason.trim()) {
            setPreviewError('Enter a reason for this correction.');
            return;
        }

        const requestId = previewRequestRef.current + 1;
        previewRequestRef.current = requestId;
        const requestFormKey = formKey;

        setIsPreviewing(true);
        setPreview(null);
        setPreviewError(null);
        setSubmitError(null);
        setSubmitMessage(null);

        try {
            const response = await apiClient.post(
                `${LINKS_PATH}/${encodeURIComponent(selectedInvoiceId)}/preview`,
                {
                    connection_id: connectionId,
                    external_invoice_id: externalId,
                },
                { retry: false }
            );

            if (
                requestId !== previewRequestRef.current ||
                requestFormKey !== latestFormKeyRef.current
            ) {
                return;
            }

            const facts = parsePreviewFacts(response.data);
            if (!facts) {
                setPreviewError('Unexpected preview response. Nothing was changed.');
                return;
            }

            setPreview({
                facts,
                formKey: requestFormKey,
                expectedRevision,
                invoiceId: selectedInvoiceId,
                connectionId,
                externalInvoiceId: externalId,
            });
        } catch (error) {
            if (requestId !== previewRequestRef.current) {
                return;
            }
            const status = errorStatus(error);
            setPreviewError(previewErrorMessage(status));
            if (status === 409) {
                invalidatePreview();
                setPreviewError(
                    'Stripe could not verify this invoice. The current link was refreshed; preview again.'
                );
                void loadDetail(selectedInvoiceId, revisionOffset);
            }
        } finally {
            if (requestId === previewRequestRef.current) {
                setIsPreviewing(false);
            }
        }
    };

    const handleConfirm = async () => {
        if (submitRef.current || !preview || !detail || !selectedInvoiceId) {
            return;
        }

        if (
            preview.formKey !== formKey ||
            preview.invoiceId !== selectedInvoiceId
        ) {
            invalidatePreview();
            setSubmitError(
                'The preview is no longer fresh. Preview again before confirming.'
            );
            return;
        }

        const connectionId = preview.connectionId.trim();
        const externalId = preview.externalInvoiceId.trim();
        const correctionReason = reason.trim();

        if (!connectionId || !externalId) {
            invalidatePreview();
            setSubmitError('Check the connection and Stripe invoice IDs.');
            return;
        }
        if (detail.binding && !correctionReason) {
            setSubmitError('Enter a reason for this correction.');
            return;
        }

        submitRef.current = true;
        setIsSubmitting(true);
        setSubmitError(null);
        setSubmitMessage(null);

        const expectedPreview = {
            account_id: preview.facts.account_id,
            invoice_id: preview.facts.invoice_id,
            currency: preview.facts.currency,
            total_minor_units: preview.facts.total_minor_units,
            livemode: preview.facts.livemode,
            invoice_number: preview.facts.invoice_number,
        };

        const body: Record<string, unknown> = {
            connection_id: connectionId,
            external_invoice_id: externalId,
            expected_revision: preview.expectedRevision,
            expected_preview: expectedPreview,
        };
        if (correctionReason) {
            body.reason = correctionReason;
        }

        try {
            const response = await apiClient.put(
                `${LINKS_PATH}/${encodeURIComponent(selectedInvoiceId)}`,
                body,
                { retry: false }
            );
            const responseData = asRecord(response.data);
            const savedRevision = responseData
                ? asRevision(responseData.revision)
                : null;

            setSubmitMessage(
                savedRevision === null
                    ? 'Stripe invoice link saved.'
                    : `Stripe invoice link saved at revision ${savedRevision}.`
            );
            invalidatePreview();
            setReason('');
            await loadDetail(selectedInvoiceId, revisionOffset);
        } catch (error) {
            const status = errorStatus(error);
            if (status === 409) {
                invalidatePreview();
                const refreshed = await loadDetail(selectedInvoiceId, revisionOffset);
                setSubmitError(
                    refreshed
                        ? 'This link changed since the preview. The current link was refreshed; preview again before confirming.'
                        : 'This link changed since the preview. Reload the current link and preview again.'
                );
            } else {
                setSubmitError(saveErrorMessage(status));
            }
        } finally {
            submitRef.current = false;
            setIsSubmitting(false);
        }
    };

    const selectedInvoice =
        detail ?? listPage?.items.find((item) => item.invoice_id === selectedInvoiceId) ?? null;

    return (
        <Card className="mt-6">
            <CardHeader>
                <CardTitle>Stripe Invoice Links</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
                <p className="text-sm text-muted-foreground">
                    Link a durable invoice to a Stripe invoice. A fresh preview is required
                    before every change.
                </p>

                <section aria-labelledby="stripe-link-invoice-list-heading" className="space-y-3">
                    <h3
                        id="stripe-link-invoice-list-heading"
                        className="text-base font-semibold"
                    >
                        Select durable invoice
                    </h3>

                    <fieldset className="space-y-3" disabled={isSubmitting || listLoading}>
                        <legend className="text-sm font-medium">Durable invoices</legend>

                        {listLoading && (
                            <p role="status" className="text-sm text-muted-foreground">
                                Loading invoices…
                            </p>
                        )}
                        {listError && (
                            <p role="alert" className="text-sm text-destructive">
                                {listError}
                            </p>
                        )}
                        {!listLoading && !listError && listPage?.items.length === 0 && (
                            <p className="text-sm text-muted-foreground">
                                No durable invoices found.
                            </p>
                        )}

                        <ul className="space-y-2">
                            {listPage?.items.map((invoice, index) => {
                                const inputId = `stripe-link-invoice-${index}`;
                                return (
                                    <li key={invoice.invoice_id}>
                                        <label
                                            htmlFor={inputId}
                                            className="flex cursor-pointer gap-3 rounded-md border p-3 text-sm"
                                        >
                                            <input
                                                id={inputId}
                                                type="radio"
                                                name="stripe-link-invoice"
                                                className="mt-1 h-4 w-4"
                                                checked={invoice.invoice_id === selectedInvoiceId}
                                                onChange={() => handleSelectInvoice(invoice.invoice_id)}
                                                disabled={isSubmitting}
                                            />
                                            <span className="min-w-0 space-y-1">
                                                <span className="block font-medium">
                                                    {invoice.invoice_number || invoice.invoice_id}
                                                </span>
                                                <span className="block break-all text-xs text-muted-foreground">
                                                    {invoice.invoice_id}
                                                    {invoice.currency ? ` · ${invoice.currency}` : ''}
                                                    {invoice.amount ? ` · ${invoice.amount}` : ''}
                                                    {invoice.binding_revision !== null
                                                        ? ` · Linked revision ${invoice.binding_revision}`
                                                        : ''}
                                                </span>
                                            </span>
                                        </label>
                                    </li>
                                );
                            })}
                        </ul>
                    </fieldset>

                    <div className="flex flex-wrap items-center justify-between gap-2">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => setListOffset(Math.max(0, listOffset - INVOICE_PAGE_SIZE))}
                            disabled={isSubmitting || listLoading || listOffset === 0}
                        >
                            Previous invoices
                        </Button>
                        <span className="text-xs text-muted-foreground">
                            {listPage && listPage.items.length > 0
                                ? `Invoices ${listOffset + 1}–${listOffset + listPage.items.length}`
                                : 'Invoice list'}
                        </span>
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() =>
                                setListOffset(
                                    listPage?.next_offset ?? listOffset + INVOICE_PAGE_SIZE
                                )
                            }
                            disabled={isSubmitting || listLoading || !listPage?.has_more}
                        >
                            Next invoices
                        </Button>
                    </div>
                </section>

                {selectedInvoiceId && (
                    <section aria-labelledby="stripe-link-current-heading" className="space-y-4">
                        <h3 id="stripe-link-current-heading" className="text-base font-semibold">
                            Selected invoice and current link
                        </h3>

                        {!detail && detailLoading && (
                            <p role="status" className="text-sm text-muted-foreground">
                                Loading current link and revisions…
                            </p>
                        )}
                        {detailError && (
                            <p role="alert" className="text-sm text-destructive">
                                {detailError}
                            </p>
                        )}

                        {selectedInvoice && (
                            <div className="rounded-md border p-3 text-sm">
                                <p className="font-medium">
                                    {selectedInvoice.invoice_number || selectedInvoice.invoice_id}
                                </p>
                                <p className="break-all text-xs text-muted-foreground">
                                    {selectedInvoice.invoice_id}
                                    {selectedInvoice.currency
                                        ? ` · ${selectedInvoice.currency}`
                                        : ''}
                                    {selectedInvoice.amount
                                        ? ` · ${selectedInvoice.amount}`
                                        : ''}
                                </p>
                            </div>
                        )}

                        {detail && (
                            <div className="space-y-2">
                                <h4 className="text-sm font-semibold">Current link</h4>
                                {detail.binding ? (
                                    <dl className="grid gap-2 text-sm sm:grid-cols-2">
                                        <div>
                                            <dt className="text-muted-foreground">Provider</dt>
                                            <dd>{detail.binding.provider || '—'}</dd>
                                        </div>
                                        <div>
                                            <dt className="text-muted-foreground">Account</dt>
                                            <dd className="break-all">
                                                {detail.binding.provider_account_id || '—'}
                                            </dd>
                                        </div>
                                        <div>
                                            <dt className="text-muted-foreground">Mode</dt>
                                            <dd>{detail.binding.provider_mode || '—'}</dd>
                                        </div>
                                        <div>
                                            <dt className="text-muted-foreground">Revision</dt>
                                            <dd>{detail.binding.revision}</dd>
                                        </div>
                                        <div>
                                            <dt className="text-muted-foreground">
                                                External invoice ID
                                            </dt>
                                            <dd className="break-all">
                                                {detail.binding.external_invoice_id}
                                            </dd>
                                        </div>
                                        <div>
                                            <dt className="text-muted-foreground">
                                                Connection ID
                                            </dt>
                                            <dd className="break-all">
                                                {detail.binding.connection_id}
                                            </dd>
                                        </div>
                                        <div className="sm:col-span-2">
                                            <dt className="text-muted-foreground">Updated</dt>
                                            <dd>{formatTimestamp(detail.binding.updated_at)}</dd>
                                        </div>
                                    </dl>
                                ) : (
                                    <p className="text-sm text-muted-foreground">
                                        No Stripe invoice is linked to this invoice.
                                    </p>
                                )}
                            </div>
                        )}

                        {detail && (
                            <div className="space-y-4">
                                <h4 className="text-sm font-semibold">Link or correct</h4>

                                {usingSetupConnection || usingBindingConnection ? (
                                    <div className="grid gap-2">
                                        <p className="text-sm font-medium">Connection ID</p>
                                        <p className="break-all rounded-md border bg-muted/40 p-2 font-mono text-sm">
                                            {autoConnectionId}
                                        </p>
                                        <p className="text-xs text-muted-foreground">
                                            {usingSetupConnection
                                                ? 'Using the Stripe connection verified on this page.'
                                                : 'Using the connection saved on the current link.'}
                                        </p>
                                    </div>
                                ) : (
                                    <div className="grid gap-2">
                                        <Label htmlFor="stripe-link-connection-id">
                                            Stripe connection ID
                                        </Label>
                                        <Input
                                            id="stripe-link-connection-id"
                                            value={manualConnectionId}
                                            onChange={handleManualConnectionChange}
                                            placeholder="Enter connection ID"
                                            autoComplete="off"
                                            spellCheck={false}
                                            aria-describedby="stripe-link-connection-help"
                                            required
                                            disabled={isSubmitting}
                                        />
                                        <p
                                            id="stripe-link-connection-help"
                                            className="text-xs text-muted-foreground"
                                        >
                                            No setup or saved connection is available for this
                                            invoice. Enter one to continue.
                                        </p>
                                    </div>
                                )}

                                <div className="grid gap-2">
                                    <Label htmlFor="stripe-link-external-invoice-id">
                                        Stripe invoice ID
                                    </Label>
                                    <Input
                                        id="stripe-link-external-invoice-id"
                                        value={externalInvoiceId}
                                        onChange={handleExternalInvoiceChange}
                                        placeholder="in_..."
                                        autoComplete="off"
                                        spellCheck={false}
                                        aria-describedby="stripe-link-external-invoice-help"
                                        required
                                        disabled={isSubmitting}
                                    />
                                    <p
                                        id="stripe-link-external-invoice-help"
                                        className="text-xs text-muted-foreground"
                                    >
                                        The Stripe invoice to verify and link.
                                    </p>
                                </div>

                                {isCorrection && (
                                    <div className="grid gap-2">
                                        <Label htmlFor="stripe-link-correction-reason">
                                            Reason for correction
                                        </Label>
                                        <textarea
                                            id="stripe-link-correction-reason"
                                            value={reason}
                                            onChange={handleReasonChange}
                                            maxLength={500}
                                            rows={3}
                                            required
                                            aria-required="true"
                                            aria-describedby="stripe-link-correction-reason-help"
                                            disabled={isSubmitting}
                                            className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                                        />
                                        <p
                                            id="stripe-link-correction-reason-help"
                                            className="text-xs text-muted-foreground"
                                        >
                                            Required when changing an existing link.
                                        </p>
                                    </div>
                                )}

                                <div className="space-y-3">
                                    <h4 className="text-sm font-semibold">Preview and confirm</h4>
                                    <p className="text-sm text-muted-foreground">
                                        Confirming records one audit revision.
                                    </p>

                                    <div className="flex flex-wrap gap-2">
                                        <Button
                                            type="button"
                                            variant="outline"
                                            onClick={handlePreview}
                                            disabled={!canPreview}
                                        >
                                            {isPreviewing ? 'Previewing…' : 'Preview link'}
                                        </Button>
                                        <Button
                                            type="button"
                                            onClick={handleConfirm}
                                            disabled={!canConfirm}
                                        >
                                            {isSubmitting ? 'Saving…' : 'Confirm link'}
                                        </Button>
                                    </div>

                                    {previewError && (
                                        <p role="alert" className="text-sm text-destructive">
                                            {previewError}
                                        </p>
                                    )}
                                    {submitError && (
                                        <p role="alert" className="text-sm text-destructive">
                                            {submitError}
                                        </p>
                                    )}
                                    {submitMessage && (
                                        <p role="status" className="text-sm">
                                            {submitMessage}
                                        </p>
                                    )}

                                    {preview ? (
                                        <div
                                            className="space-y-3 rounded-md border p-4"
                                            aria-live="polite"
                                        >
                                            <h5 className="text-sm font-semibold">
                                                Fresh preview
                                            </h5>
                                            <p className="text-xs text-muted-foreground">
                                                Review these six facts before confirming.
                                            </p>
                                            <dl className="grid gap-2 text-sm sm:grid-cols-2">
                                                <div>
                                                    <dt className="text-muted-foreground">
                                                        Account ID
                                                    </dt>
                                                    <dd className="break-all">
                                                        {preview.facts.account_id}
                                                    </dd>
                                                </div>
                                                <div>
                                                    <dt className="text-muted-foreground">
                                                        Invoice ID
                                                    </dt>
                                                    <dd className="break-all">
                                                        {preview.facts.invoice_id}
                                                    </dd>
                                                </div>
                                                <div>
                                                    <dt className="text-muted-foreground">
                                                        Currency
                                                    </dt>
                                                    <dd>{preview.facts.currency}</dd>
                                                </div>
                                                <div>
                                                    <dt className="text-muted-foreground">
                                                        Total (minor units)
                                                    </dt>
                                                    <dd>{preview.facts.total_minor_units}</dd>
                                                </div>
                                                <div>
                                                    <dt className="text-muted-foreground">
                                                        Live mode
                                                    </dt>
                                                    <dd>{preview.facts.livemode ? 'Yes' : 'No'}</dd>
                                                </div>
                                                <div>
                                                    <dt className="text-muted-foreground">
                                                        Invoice number
                                                    </dt>
                                                    <dd>
                                                        {preview.facts.invoice_number ?? '—'}
                                                    </dd>
                                                </div>
                                            </dl>
                                            <p className="text-xs text-muted-foreground">
                                                {preview.expectedRevision === null
                                                    ? 'Expected revision: new link'
                                                    : `Expected revision: ${preview.expectedRevision}`}
                                            </p>
                                        </div>
                                    ) : (
                                        <p className="text-xs text-muted-foreground">
                                            A fresh preview is required before confirming. Any
                                            change clears it.
                                        </p>
                                    )}
                                </div>
                            </div>
                        )}

                        {detail && (
                            <div className="space-y-3">
                                <h4 className="text-sm font-semibold">Audit revisions</h4>
                                {detail.receipts.length === 0 ? (
                                    <p className="text-sm text-muted-foreground">
                                        No audit revisions yet.
                                    </p>
                                ) : (
                                    <ol className="space-y-3">
                                        {detail.receipts.map((receipt) => (
                                            <li
                                                key={receipt.revision}
                                                className="space-y-2 rounded-md border p-3"
                                            >
                                                <h5 className="text-sm font-semibold">
                                                    Revision {receipt.revision}
                                                </h5>
                                                <dl className="grid gap-1 text-sm sm:grid-cols-2">
                                                    <div>
                                                        <dt className="text-muted-foreground">
                                                            Actor
                                                        </dt>
                                                        <dd className="break-all">
                                                            {receipt.actor_id || '—'}
                                                        </dd>
                                                    </div>
                                                    <div>
                                                        <dt className="text-muted-foreground">
                                                            Timestamp
                                                        </dt>
                                                        <dd>
                                                            {receipt.created_at ? (
                                                                <time
                                                                    dateTime={receipt.created_at}
                                                                >
                                                                    {formatTimestamp(
                                                                        receipt.created_at
                                                                    )}
                                                                </time>
                                                            ) : (
                                                                '—'
                                                            )}
                                                        </dd>
                                                    </div>
                                                </dl>
                                                <p className="break-words text-sm">
                                                    <span className="font-medium">Reason:</span>{' '}
                                                    {receipt.reason?.trim() || '—'}
                                                </p>
                                                <ReferenceList
                                                    title="Old references"
                                                    provider={receipt.prior_provider}
                                                    account={receipt.prior_provider_account_id}
                                                    mode={receipt.prior_provider_mode}
                                                    externalInvoiceId={
                                                        receipt.prior_external_invoice_id
                                                    }
                                                    connectionId={receipt.prior_connection_id}
                                                    emptyLabel="No previous link."
                                                />
                                                <ReferenceList
                                                    title="New references"
                                                    provider={receipt.new_provider}
                                                    account={receipt.new_provider_account_id}
                                                    mode={receipt.new_provider_mode}
                                                    externalInvoiceId={
                                                        receipt.new_external_invoice_id
                                                    }
                                                    connectionId={receipt.new_connection_id}
                                                    emptyLabel="No new link recorded."
                                                />
                                            </li>
                                        ))}
                                    </ol>
                                )}

                                <div className="flex flex-wrap items-center justify-between gap-2">
                                    <Button
                                        type="button"
                                        variant="outline"
                                        onClick={() =>
                                            setRevisionOffset(
                                                Math.max(0, detail.offset - detail.limit)
                                            )
                                        }
                                        disabled={
                                            isSubmitting || detailLoading || detail.offset === 0
                                        }
                                    >
                                        Previous revisions
                                    </Button>
                                    <span className="text-xs text-muted-foreground">
                                        {detail.receipts.length > 0
                                            ? `Revisions ${detail.offset + 1}–${
                                                  detail.offset + detail.receipts.length
                                              }`
                                            : 'Revision list'}
                                    </span>
                                    <Button
                                        type="button"
                                        variant="outline"
                                        onClick={() =>
                                            setRevisionOffset(
                                                detail.next_offset ?? detail.offset + detail.limit
                                            )
                                        }
                                        disabled={
                                            isSubmitting || detailLoading || !detail.has_more
                                        }
                                    >
                                        Next revisions
                                    </Button>
                                </div>
                            </div>
                        )}
                    </section>
                )}
            </CardContent>
        </Card>
    );
};

export default StripeInvoiceLinks;
