import React, { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/components/ui/use-toast';
import { Separator } from '@/components/ui/separator';

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

    return (
        <Card className="mt-6">
            <CardHeader>
                <CardTitle>Third-Party Integrations</CardTitle>
            </CardHeader>
            <CardContent className="space-y-8">
                <section className="space-y-4">
                    <h3 className="text-lg font-medium">Asana Integration</h3>
                    <Button onClick={() => window.location.href = '/api/auth/asana/initiate'}>Connect Asana</Button>
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
                        <Button variant="outline" onClick={() => window.location.href = '/api/auth/slack/initiate'}>Connect Slack</Button>
                        <Button variant="outline" onClick={() => window.location.href = '/api/auth/zoom/initiate'}>Connect Zoom</Button>
                        <Button variant="outline" onClick={() => window.location.href = '/api/auth/box/initiate'}>Connect Box</Button>
                        <Button variant="outline" onClick={() => window.location.href = '/api/pocket/oauth/start'}>Connect Pocket</Button>
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
