import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/components/ui/use-toast';
import { apiClient } from '@/lib/api-client';

type StripeInvoiceConnectionState = {
    connectionId?: string;
    account: string;
    mode: string;
};

const StripeInvoiceConnection = () => {
    const { toast } = useToast();

    const [stripeRestrictedKey, setStripeRestrictedKey] = useState('');
    const [stripeAccountId, setStripeAccountId] = useState('');
    const [stripeInvoiceConnection, setStripeInvoiceConnection] = useState<StripeInvoiceConnectionState | null>(null);
    const [isVerifyingStripeInvoice, setIsVerifyingStripeInvoice] = useState(false);

    const handleVerifyStripeInvoiceConnection = async () => {
        const restrictedKey = stripeRestrictedKey.trim();
        const accountId = stripeAccountId.trim();
        if (!restrictedKey || !accountId) {
            toast({
                title: 'Stripe restricted key and account ID are required.',
                variant: 'error',
            });
            return;
        }

        setIsVerifyingStripeInvoice(true);
        try {
            const payload = {
                restricted_key: restrictedKey,
                account_id: accountId,
            };
            const response = await apiClient.post(
                '/api/integrations/stripe/invoice-connection',
                payload,
                { retry: false }
            );

            const data = response.data ?? {};
            const connectionId = typeof data.connection_id === 'string'
                ? data.connection_id.trim()
                : '';
            const account = typeof data.account === 'string' ? data.account.trim() : '';
            const mode = typeof data.mode === 'string' ? data.mode.trim().toLowerCase() : '';

            if (
                !connectionId ||
                account !== accountId ||
                (mode !== 'test' && mode !== 'live')
            ) {
                throw new Error('Invalid invoice connection response');
            }

            setStripeInvoiceConnection({
                connectionId,
                account,
                mode,
            });
            setStripeRestrictedKey('');
            toast({
                title: 'Stripe invoice connection verified.',
                description: `Registered account ${account} (${mode}).`,
                variant: 'success',
            });
        } catch {
            toast({
                title: 'Failed to verify Stripe invoice connection.',
                description: 'Check the restricted key and account ID, then try again.',
                variant: 'error',
            });
        } finally {
            setIsVerifyingStripeInvoice(false);
        }
    };

    return (
        <Card className="mt-6">
            <CardHeader>
                <CardTitle>Stripe Invoice Verification</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="grid gap-2">
                    <Label htmlFor="stripeRestrictedKey">Stripe Restricted Key</Label>
                    <Input
                        id="stripeRestrictedKey"
                        type="password"
                        value={stripeRestrictedKey}
                        onChange={(e) => setStripeRestrictedKey(e.target.value)}
                        placeholder="Enter Stripe Restricted Key"
                        autoComplete="off"
                    />
                </div>
                <div className="grid gap-2">
                    <Label htmlFor="stripeAccountId">Stripe Account ID</Label>
                    <Input
                        id="stripeAccountId"
                        value={stripeAccountId}
                        onChange={(e) => setStripeAccountId(e.target.value)}
                        placeholder="acct_..."
                        autoComplete="off"
                    />
                </div>
                <Button
                    variant="outline"
                    onClick={handleVerifyStripeInvoiceConnection}
                    disabled={isVerifyingStripeInvoice}
                >
                    {isVerifyingStripeInvoice ? 'Verifying Stripe Invoice Connection...' : 'Verify Stripe Invoice Connection'}
                </Button>
                {stripeInvoiceConnection && (
                    <div role="status" className="text-sm text-muted-foreground">
                        Registered account: <span>{stripeInvoiceConnection.account}</span> (mode: <span>{stripeInvoiceConnection.mode}</span>)
                    </div>
                )}
            </CardContent>
        </Card>
    );
};

export default StripeInvoiceConnection;
