import React, { useState, useEffect } from 'react';
import Box from '@components/common/Box';
import Text from '@components/common/Text';
import Button from '@components/Button';
import TextField from '@components/TextField';
import { useToast } from '@components/ui/use-toast';
import { useSession } from 'next-auth/react';

const ThirdPartyIntegrations = () => {
    const { data: session } = useSession();
    const userId = session?.user?.id;
    const { toast } = useToast();

    const [trelloApiKey, setTrelloApiKey] = useState('');
    const [trelloToken, setTrelloToken] = useState('');
    const [salesforceClientId, setSalesforceClientId] = useState('');
    const [salesforceClientSecret, setSalesforceClientSecret] = useState('');
    const [xeroClientId, setXeroClientId] = useState('');
    const [xeroClientSecret, setXeroClientSecret] = useState('');
    const [twitterApiKey, setTwitterApiKey] = useState('');
    const [twitterApiSecret, setTwitterApiSecret] = useState('');
    const [twitterAccessToken, setTwitterAccessToken] = useState('');
    const [twitterAccessTokenSecret, setTwitterAccessTokenSecret] = useState('');

    const [jiraUsername, setJiraUsername] = useState('');
    const [jiraApiKey, setJiraApiKey] = useState('');
    const [jiraServerUrl, setJiraServerUrl] = useState('');

    const [stripeApiKey, setStripeApiKey] = useState('');
    const [asanaApiKey, setAsanaApiKey] = useState('');
    const [hubspotApiKey, setHubspotApiKey] = useState('');
    const [calendlyApiKey, setCalendlyApiKey] = useState('');
    const [notionApiKey, setNotionApiKey] = useState('');

    const [message, setMessage] = useState('');
    const [error, setError] = useState('');

    useEffect(() => {
        const loadCredentials = async () => {
            const services = [
                'trello_api_key', 'trello_token',
                'salesforce_client_id', 'salesforce_client_secret',
                'xero_client_id', 'xero_client_secret',
                'twitter_api_key', 'twitter_api_secret',
                'twitter_access_token', 'twitter_access_token_secret',
                'jira_username', 'jira_api_key', 'jira_server_url',
                'stripe_api_key', 'asana_api_key', 'hubspot_api_key',
                'calendly_api_key', 'notion_api_key'
            ];

            for (const service of services) {
                try {
                    const response = await fetch(`/api/integrations/credentials?service=${service}`);
                    const data = await response.json();
                    if (data.isConnected) {
                        switch (service) {
                            case 'trello_api_key': setTrelloApiKey('********'); break;
                            case 'trello_token': setTrelloToken('********'); break;
                            case 'salesforce_client_id': setSalesforceClientId('********'); break;
                            case 'salesforce_client_secret': setSalesforceClientSecret('********'); break;
                            case 'xero_client_id': setXeroClientId('********'); break;
                            case 'xero_client_secret': setXeroClientSecret('********'); break;
                            case 'twitter_api_key': setTwitterApiKey('********'); break;
                            case 'twitter_api_secret': setTwitterApiSecret('********'); break;
                            case 'twitter_access_token': setTwitterAccessToken('********'); break;
                            case 'twitter_access_token_secret': setTwitterAccessTokenSecret('********'); break;
                            case 'jira_username': setJiraUsername(data.value || '********'); break;
                            case 'jira_server_url': setJiraServerUrl(data.value || '********'); break;
                            case 'stripe_api_key': setStripeApiKey('********'); break;
                            case 'asana_api_key': setAsanaApiKey('********'); break;
                            case 'hubspot_api_key': setHubspotApiKey('********'); break;
                            case 'calendly_api_key': setCalendlyApiKey('********'); break;
                            case 'notion_api_key': setNotionApiKey('********'); break;
                        }
                    }
                } catch (e) {
                    console.error(`Error loading credential for ${service}:`, e);
                }
            }
        };
        if (userId) {
            loadCredentials();
        }
    }, [userId]);

    const handleSaveCredential = async (service: string, secret: string, label: string) => {
        try {
            const response = await fetch('/api/integrations/credentials', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ service, secret }),
            });
            if (response.ok) {
                toast({ title: `${label} saved successfully.`, variant: 'default' });
                return true;
            } else {
                const data = await response.json();
                toast({ title: data.message || `Failed to save ${label}.`, variant: 'destructive' });
                return false;
            }
        } catch (err) {
            toast({ title: 'Failed to connect to the server.', variant: 'destructive' });
            return false;
        }
    };

    const handleSaveJiraCredentials = async () => {
        const s1 = await handleSaveCredential('jira_username', jiraUsername, 'Jira Username');
        const s2 = await handleSaveCredential('jira_api_key', jiraApiKey, 'Jira API Key');
        const s3 = await handleSaveCredential('jira_server_url', jiraServerUrl, 'Jira Server URL');
        if (s1 && s2 && s3) {
            setJiraApiKey('********');
        }
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
        <Box marginTop="m" paddingTop="m" borderTopWidth={1} borderColor="hairline">
            <Text variant="sectionHeader" marginBottom="m">Third-Party Integrations</Text>

            <Box marginBottom="l">
                <Text variant="subHeader" marginBottom="s">Asana Integration</Text>
                <Button onPress={() => window.location.href = '/api/auth/asana/initiate'} title="Connect Asana" variant="primary" />
            </Box>

            <Box marginBottom="l">
                <Text variant="subHeader" marginBottom="s">Jira Integration</Text>
                <TextField
                    label="Jira Username"
                    value={jiraUsername}
                    onChange={(e) => setJiraUsername(e.target.value)}
                    placeholder="Enter Jira Username"
                    marginBottom="s"
                />
                <TextField
                    label="Jira API Key"
                    type="password"
                    value={jiraApiKey}
                    onChange={(e) => setJiraApiKey(e.target.value)}
                    placeholder="Enter Jira API Key"
                    marginBottom="s"
                />
                <TextField
                    label="Jira Server URL"
                    value={jiraServerUrl}
                    onChange={(e) => setJiraServerUrl(e.target.value)}
                    placeholder="e.g., your-domain.atlassian.net"
                    marginBottom="s"
                />
                <Button onPress={handleSaveJiraCredentials} title="Save Jira Credentials" variant="primary" />
            </Box>

            <Box marginBottom="l">
                <Text variant="subHeader" marginBottom="s">Trello Integration</Text>
                <TextField
                    label="Trello API Key"
                    value={trelloApiKey}
                    onChange={(e) => setTrelloApiKey(e.target.value)}
                    placeholder="Enter Trello API Key"
                    marginBottom="s"
                />
                <TextField
                    label="Trello Token"
                    type="password"
                    value={trelloToken}
                    onChange={(e) => setTrelloToken(e.target.value)}
                    placeholder="Enter Trello Token"
                    marginBottom="s"
                />
                <Button onPress={handleSaveTrelloCredentials} title="Save Trello Credentials" variant="primary" />
            </Box>

            <Box marginBottom="l">
                <Text variant="subHeader" marginBottom="s">Slack Integration</Text>
                <Button onPress={() => window.location.href = '/api/auth/slack/initiate'} title="Connect Slack" variant="primary" />
            </Box>

            <Box marginBottom="l">
                <Text variant="subHeader" marginBottom="s">Zoom Integration</Text>
                <Button onPress={() => window.location.href = '/api/auth/zoom/initiate'} title="Connect Zoom" variant="primary" />
            </Box>

            <Box marginBottom="l">
                <Text variant="subHeader" marginBottom="s">Box Integration</Text>
                <Button onPress={() => window.location.href = '/api/auth/box/initiate'} title="Connect Box" variant="primary" />
            </Box>

            <Box marginBottom="l">
                <Text variant="subHeader" marginBottom="s">Pocket Integration</Text>
                <Button onPress={() => window.location.href = '/api/pocket/oauth/start'} title="Connect Pocket" variant="primary" />
            </Box>

            <Box marginBottom="l">
                <Text variant="subHeader" marginBottom="s">Stripe Integration</Text>
                <TextField
                    label="Stripe API Key"
                    type="password"
                    value={stripeApiKey}
                    onChange={(e) => setStripeApiKey(e.target.value)}
                    placeholder="Enter Stripe API Key"
                    marginBottom="s"
                />
                <Button
                    onPress={() => handleSaveCredential('stripe_api_key', stripeApiKey, 'Stripe API Key').then(s => s && setStripeApiKey('********'))}
                    title="Save Stripe API Key"
                    variant="primary"
                />
            </Box>

            <Box marginBottom="l">
                <Text variant="subHeader" marginBottom="s">Notion Integration</Text>
                <TextField
                    label="Notion API Key"
                    type="password"
                    value={notionApiKey}
                    onChange={(e) => setNotionApiKey(e.target.value)}
                    placeholder="Enter Notion API Key"
                    marginBottom="s"
                />
                <Button
                    onPress={() => handleSaveCredential('notion_api_key', notionApiKey, 'Notion API Key').then(s => s && setNotionApiKey('********'))}
                    title="Save Notion API Key"
                    variant="primary"
                />
            </Box>
        </Box>
    );
};

export default ThirdPartyIntegrations;
