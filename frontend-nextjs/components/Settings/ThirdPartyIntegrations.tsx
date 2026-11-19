import React, { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/components/ui/use-toast';
import { Separator } from '@/components/ui/separator';
import { apiClient } from '@/lib/api-client';

const ThirdPartyIntegrations = () => {
    const { data: session } = useSession();
    const userId = session?.user?.id;
    const { toast } = useToast();

    const [trelloApiKey, setTrelloApiKey] = useState('');
    const [trelloToken, setTrelloToken] = useState('');
    const [jiraUsername, setJiraUsername] = useState('');
    const [jiraApiKey, setJiraApiKey] = useState('');
    const [jiraServerUrl, setJiraServerUrl] = useState('');
    const [stripeApiKey, setStripeApiKey] = useState('');
    const [notionApiKey, setNotionApiKey] = useState('');
    const [stripeRestrictedKey, setStripeRestrictedKey] = useState('');
    const [stripeAccountId, setStripeAccountId] = useState('');
    const [stripeInvoiceConnection, setStripeInvoiceConnection] = useState<{
        connectionId?: string;
        account: string;
        mode: string;
    } | null>(null);
    const [isVerifyingStripeInvoice, setIsVerifyingStripeInvoice] = useState(false);

    useEffect(() => {
        const loadCredentials = async () => {
            const services = [
                'trello_api_key', 'trello_token',
                'jira_username', 'jira_api_key', 'jira_server_url',
                'stripe_api_key', 'notion_api_key'
            ];

            for (const service of services) {
                try {
                    const response = await fetch(`/api/integrations/credentials?service=${service}`);
                    const data = await response.json();
                    if (data.isConnected) {
                        switch (service) {
                            case 'trello_api_key': setTrelloApiKey('********'); break;
                            case 'trello_token': setTrelloToken('********'); break;
                            case 'jira_username': setJiraUsername(data.value || '********'); break;
                            case 'jira_server_url': setJiraServerUrl(data.value || '********'); break;
                            case 'stripe_api_key': setStripeApiKey('********'); break;
                            case 'notion_api_key': setNotionApiKey('********'); break;
                        }
                    }
                } catch (e) {
                    console.error(`Error loading credential for ${service}:`, e);
                }
            }
        };
        if (userId) loadCredentials();
    }, [userId]);

    const handleSaveCredential = async (service: string, secret: string, label: string) => {
        try {
            const response = await fetch('/api/integrations/credentials', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ service, secret }),
            });
            if (response.ok) {
                toast({ title: `${label} saved successfully.`, variant: 'success' });
                return true;
            } else {
                const data = await response.json();
                toast({ title: data.message || `Failed to save ${label}.`, variant: 'error' });
                return false;
            }
        } catch (err) {
            toast({ title: 'Failed to connect to the server.', variant: 'error' });
            return false;
        }
    };

    const handleSaveJiraCredentials = async () => {
        const s1 = await handleSaveCredential('jira_username', jiraUsername, 'Jira Username');
        const s2 = await handleSaveCredential('jira_api_key', jiraApiKey, 'Jira API Key');
        const s3 = await handleSaveCredential('jira_server_url', jiraServerUrl, 'Jira Server URL');
        if (s1 && s2 && s3) setJiraApiKey('********');
    };

    const handleSaveTrelloCredentials = async () => {
        const s1 = await handleSaveCredential('trello_api_key', trelloApiKey, 'Trello API Key');
        const s2 = await handleSaveCredential('trello_api_token', trelloToken, 'Trello API Token');
        if (s1 && s2) {
            setTrelloApiKey('********');
            setTrelloToken('********');
        }
    };

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

            const data = response?.data ?? {};
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
        } catch (err) {
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
                <CardTitle>Third-Party Integrations</CardTitle>
            </CardHeader>
            <CardContent className="space-y-8">
                <section className="space-y-4">
                    <h3 className="text-lg font-medium">Asana Integration</h3>
                    <Button onClick={() => window.open('/api/auth/asana/initiate', '_self')}>Connect Asana</Button>
                </section>

                <Separator />

                <section className="space-y-4">
                    <h3 className="text-lg font-medium">Jira Integration</h3>
                    <div className="grid gap-4">
                        <div className="grid gap-2">
                            <Label htmlFor="jiraUsername">Jira Username</Label>
                            <Input id="jiraUsername" value={jiraUsername} onChange={(e) => setJiraUsername(e.target.value)} placeholder="Enter Jira Username" />
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="jiraApiKey">Jira API Key</Label>
                            <Input id="jiraApiKey" type="password" value={jiraApiKey} onChange={(e) => setJiraApiKey(e.target.value)} placeholder="Enter Jira API Key" />
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="jiraServerUrl">Jira Server URL</Label>
                            <Input id="jiraServerUrl" value={jiraServerUrl} onChange={(e) => setJiraServerUrl(e.target.value)} placeholder="e.g., your-domain.atlassian.net" />
                        </div>
                        <Button onClick={handleSaveJiraCredentials}>Save Jira Credentials</Button>
                    </div>
                </section>

                <Separator />

                <section className="space-y-4">
                    <h3 className="text-lg font-medium">Trello Integration</h3>
                    <div className="grid gap-4">
                        <div className="grid gap-2">
                            <Label htmlFor="trelloApiKey">Trello API Key</Label>
                            <Input id="trelloApiKey" value={trelloApiKey} onChange={(e) => setTrelloApiKey(e.target.value)} placeholder="Enter Trello API Key" />
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="trelloToken">Trello Token</Label>
                            <Input id="trelloToken" type="password" value={trelloToken} onChange={(e) => setTrelloToken(e.target.value)} placeholder="Enter Trello Token" />
                        </div>
                        <Button onClick={handleSaveTrelloCredentials}>Save Trello Credentials</Button>
                    </div>
                </section>

                <Separator />

                <section className="space-y-4">
                    <h3 className="text-lg font-medium">Cloud Storage & Collaboration</h3>
                    <div className="flex flex-wrap gap-4">
                        <Button variant="outline" onClick={() => window.open('/api/auth/slack/initiate', '_self')}>Connect Slack</Button>
                        <Button variant="outline" onClick={() => window.open('/api/auth/zoom/initiate', '_self')}>Connect Zoom</Button>
                        <Button variant="outline" onClick={() => window.open('/api/auth/box/initiate', '_self')}>Connect Box</Button>
                        <Button variant="outline" onClick={() => window.open('/api/pocket/oauth/start', '_self')}>Connect Pocket</Button>
                    </div>
                </section>

                <Separator />

                <section className="space-y-4">
                    <h3 className="text-lg font-medium">Business & Productivity</h3>
                    <div className="grid gap-4 sm:grid-cols-2">
                        <div className="grid gap-2">
                            <Label htmlFor="stripeApiKey">Stripe API Key</Label>
                            <Input id="stripeApiKey" type="password" value={stripeApiKey} onChange={(e) => setStripeApiKey(e.target.value)} placeholder="Enter Stripe API Key" />
                            <Button variant="outline" onClick={() => handleSaveCredential('stripe_api_key', stripeApiKey, 'Stripe API Key').then(s => s && setStripeApiKey('********'))}>Save Stripe</Button>

                            <Separator className="my-2" />

                            <h4 className="text-sm font-medium">Stripe Invoice Verification</h4>
                            <div className="grid gap-2">
                                <Label htmlFor="stripeRestrictedKey">Stripe Restricted Key</Label>
                                <Input id="stripeRestrictedKey" type="password" value={stripeRestrictedKey} onChange={(e) => setStripeRestrictedKey(e.target.value)} placeholder="Enter Stripe Restricted Key" autoComplete="off" />
                            </div>
                            <div className="grid gap-2">
                                <Label htmlFor="stripeAccountId">Stripe Account ID</Label>
                                <Input id="stripeAccountId" value={stripeAccountId} onChange={(e) => setStripeAccountId(e.target.value)} placeholder="acct_..." autoComplete="off" />
                            </div>
                            <Button variant="outline" onClick={handleVerifyStripeInvoiceConnection} disabled={isVerifyingStripeInvoice}>
                                {isVerifyingStripeInvoice ? 'Verifying Stripe Invoice Connection...' : 'Verify Stripe Invoice Connection'}
                            </Button>
                            {stripeInvoiceConnection && (
                                <div role="status" className="text-sm text-muted-foreground">
                                    Registered account: <span>{stripeInvoiceConnection.account}</span> (mode: <span>{stripeInvoiceConnection.mode}</span>)
                                </div>
                            )}
                        </div>
                        <div className="grid gap-2">
                            <Label htmlFor="notionApiKey">Notion API Key</Label>
                            <Input id="notionApiKey" type="password" value={notionApiKey} onChange={(e) => setNotionApiKey(e.target.value)} placeholder="Enter Notion API Key" />
                            <Button variant="outline" onClick={() => handleSaveCredential('notion_api_key', notionApiKey, 'Notion API Key').then(s => s && setNotionApiKey('********'))}>Save Notion</Button>
                        </div>
                    </div>
                </section>
            </CardContent>
        </Card>
    );
};

export default ThirdPartyIntegrations;
