import React, { useState, useEffect } from 'react';
import { Box, Button, Input, Text, useToast } from '@chakra-ui/react';

const ThirdPartyIntegrations = () => {
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
    const toast = useToast();

    useEffect(() => {
        const loadCredentials = async () => {
            const services = ['trello_api_key', 'trello_token', 'salesforce_client_id', 'salesforce_client_secret', 'xero_client_id', 'xero_client_secret', 'twitter_api_key', 'twitter_api_secret', 'twitter_access_token', 'twitter_access_token_secret'];
            services.forEach(async (service) => {
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
                    }
                }
            });
        };
        loadCredentials();
    }, []);

  // ... (existing save handlers)

  const handleSaveStripeApiKey = async () => {
    try {
      const response = await fetch('/api/integrations/credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service: 'stripe_api_key', secret: stripeApiKey }),
      });
      const data = await response.json();
      if (response.ok) {
        setMessage('Stripe API key saved successfully.');
        setError('');
        setStripeApiKey('********');
      } else {
        setError(data.message || 'Failed to save Stripe API key.');
        setMessage('');
      }
    } catch (err) {
      setError('Failed to connect to the server.');
      setMessage('');
    }
  };

  const handleSaveAsanaApiKey = async () => {
    try {
      const response = await fetch('/api/integrations/credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service: 'asana_api_key', secret: asanaApiKey }),
      });
      const data = await response.json();
      if (response.ok) {
        setMessage('Asana API key saved successfully.');
        setError('');
        setAsanaApiKey('********');
      } else {
        setError(data.message || 'Failed to save Asana API key.');
        setMessage('');
      }
    } catch (err) {
      setError('Failed to connect to the server.');
      setMessage('');
    }
  };

  const handleSaveJiraCredentials = async () => {
    try {
      await fetch('/api/integrations/credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service: 'jira_username', secret: jiraUsername }),
      });
      await fetch('/api/integrations/credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service: 'jira_api_key', secret: jiraApiKey }),
      });
      await fetch('/api/integrations/credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service: 'jira_server_url', secret: jiraServerUrl }),
      });
      setMessage('Jira credentials saved successfully.');
      setError('');
      setJiraApiKey('********');
    } catch (err) {
      setError('Failed to connect to the server.');
      setMessage('');
    }
  };

  const handleSaveTrelloCredentials = async () => {
    try {
      await fetch('/api/integrations/credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service: 'trello_api_key', secret: trelloApiKey }),
      });
      await fetch('/api/integrations/credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service: 'trello_api_token', secret: trelloApiToken }),
      });
      setMessage('Trello credentials saved successfully.');
      setError('');
      setTrelloApiKey('********');
      setTrelloApiToken('********');
    } catch (err) {
      setError('Failed to connect to the server.');
      setMessage('');
    }
  };

  const handleSaveGithubApiKey = async () => {
    try {
      const response = await fetch('/api/integrations/credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service: 'github_api_key', secret: githubApiKey }),
      });
      const data = await response.json();
      if (response.ok) {
        setMessage('GitHub API key saved successfully.');
        setError('');
        setGithubApiKey('********');
      } else {
        setError(data.message || 'Failed to save GitHub API key.');
        setMessage('');
      }
    } catch (err) {
      setError('Failed to connect to the server.');
      setMessage('');
    }
  };

  const handleSaveZapierUrl = async () => {
    // ... (existing Zapier save logic)
  };

  const handleSaveNotionApiKey = async () => {
    // ... (existing Notion save logic)
  };

  const handleSaveHubspotApiKey = async () => {
    try {
      const response = await fetch('/api/integrations/credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service: 'hubspot_api_key', secret: hubspotApiKey }),
      });
      const data = await response.json();
      if (response.ok) {
        setMessage('HubSpot API key saved successfully.');
        setError('');
        setHubspotApiKey('********');
      } else {
        setError(data.message || 'Failed to save HubSpot API key.');
        setMessage('');
      }
    } catch (err) {
      setError('Failed to connect to the server.');
      setMessage('');
    }
  };

  const handleSaveCalendlyApiKey = async () => {
    try {
      const response = await fetch('/api/integrations/credentials', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service: 'calendly_api_key', secret: calendlyApiKey }),
      });
      const data = await response.json();
      if (response.ok) {
        setMessage('Calendly API key saved successfully.');
        setError('');
        setCalendlyApiKey('********');
      } else {
        setError(data.message || 'Failed to save Calendly API key.');
        setMessage('');
      }
    } catch (err) {
      setError('Failed to connect to the server.');
      setMessage('');
    }
  };

  return (
    <Box marginTop="m" paddingTop="m" borderTopWidth={1} borderColor="hairline">
      <Text variant="subHeader" marginBottom="s">
        Third-Party Integrations
      </Text>
      {message && (
        <Box backgroundColor="green.100" padding="s" marginBottom="m" borderRadius="s">
          <Text color="green.700">{message}</Text>
        </Box>
      )}
      {error && (
        <Box backgroundColor="red.100" padding="s" marginBottom="m" borderRadius="s">
          <Text color="red.700">{error}</Text>
        </Box>
      )}
      <Box marginBottom="m">
        <Text variant="subHeader" marginBottom="s">
          Zapier Integration
        </Text>
        {/* ... (existing Zapier input and button) */}
      </Box>
      <Box marginBottom="m">
        <Text variant="subHeader" marginBottom="s">
          HubSpot Integration
        </Text>
        {/* ... (existing HubSpot input and button) */}
      </Box>
      <Box marginBottom="m">
        <Text variant="subHeader" marginBottom="s">
          Slack Integration
        </Text>
        {/* ... (existing Slack button) */}
      </Box>
      <Box marginBottom="m">
        <Text variant="subHeader" marginBottom="s">
          Calendly Integration
        </Text>
        {/* ... (existing Calendly input and button) */}
      </Box>
      <Box marginBottom="m">
        <Text variant="subHeader" marginBottom="s">
          Zoom Integration
        </Text>
        {/* ... (existing Zoom button) */}
      </Box>
      <Box marginBottom="m">
        <Text variant="subHeader" marginBottom="s">
          Microsoft Teams Integration
        </Text>
        {/* ... (existing Microsoft Teams button) */}
      </Box>
      <Box marginBottom="m">
        <Text variant="subHeader" marginBottom="s">
          Stripe Integration
        </Text>
        {/* ... (existing Stripe input and button) */}
      </Box>
      <Box marginBottom="m">
        <Text variant="subHeader" marginBottom="s">
          QuickBooks Integration
        </Text>
        {/* ... (existing QuickBooks button) */}
      </Box>
      <Box marginBottom="m">
        <Text variant="subHeader" marginBottom="s">
          Asana Integration
        </Text>
        <Button onPress={() => window.location.href = '/api/auth/asana/initiate'} variant="primary" title="Connect Asana" />
      </Box>
      <Box marginBottom="m">
        <Text variant="subHeader" marginBottom="s">
          Jira Integration
        </Text>
        <input
          type="text"
          value={jiraUsername}
          onChange={(e) => setJiraUsername(e.target.value)}
          placeholder="Enter Jira Username"
          style={{
            width: '100%',
            padding: '8px',
            marginBottom: '8px',
            border: '1px solid #ccc',
            borderRadius: '4px',
          }}
        />
        <input
          type="password"
          value={jiraApiKey}
          onChange={(e) => setJiraApiKey(e.target.value)}
          placeholder="Enter Jira API Key"
          style={{
            width: '100%',
            padding: '8px',
            marginBottom: '8px',
            border: '1px solid #ccc',
            borderRadius: '4px',
          }}
        />
        <input
          type="text"
          value={jiraServerUrl}
          onChange={(e) => setJiraServerUrl(e.target.value)}
          placeholder="Enter Jira Server URL (e.g., your-domain.atlassian.net)"
          style={{
            width: '100%',
            padding: '8px',
            marginBottom: '8px',
            border: '1px solid #ccc',
            borderRadius: '4px',
          }}
        />
        <Button onPress={handleSaveJiraCredentials} variant="primary" title="Save Jira Credentials" />
      </Box>
      <Box marginBottom="m">
        <Text variant="subHeader" marginBottom="s">
          Trello Integration
        </Text>
        <Button onPress={() => window.location.href = '/api/auth/trello/initiate'} variant="primary" title="Connect Trello" />
      </Box>
      <Box marginBottom="m">
        <Text variant="subHeader" marginBottom="s">
          GitHub Integration
        </Text>
        {/* ... (existing GitHub inputs and button) */}
      </Box>
      <Box marginBottom="m">
        <Text variant="subHeader" marginBottom="s">
          Box Integration
        </Text>
        <Button onPress={() => window.location.href = '/api/auth/box/initiate'} variant="primary" title="Connect Box" />
      </Box>
      <Box marginBottom="m">
        <Text variant="subHeader" marginBottom="s">
          Pocket Integration
        </Text>
        <Button onPress={() => window.location.href = '/api/pocket/oauth/start'} variant="primary" title="Connect Pocket" />
      </Box>
      <Box marginBottom="m">
        <Text variant="subHeader" marginBottom="s">
          Notion Integration
        </Text>
        <input
          type="password"
          value={notionApiKey}
          onChange={(e) => setNotionApiKey(e.target.value)}
          placeholder="Enter Notion API Key"
          style={{
            width: '100%',
            padding: '8px',
            marginBottom: '8px',
            border: '1px solid #ccc',
            borderRadius: '4px',
          }}
        />
        <Button onPress={handleSaveNotionApiKey} variant="primary" title="Save Notion API Key" />
      </Box>
    </Box>
  );
};

export default ThirdPartyIntegrations;
