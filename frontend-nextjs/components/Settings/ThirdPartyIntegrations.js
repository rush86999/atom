"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const jsx_runtime_1 = require("react/jsx-runtime");
const react_1 = require("react");
const react_2 = require("@chakra-ui/react");
const ThirdPartyIntegrations = () => {
    const [trelloApiKey, setTrelloApiKey] = (0, react_1.useState)('');
    const [trelloToken, setTrelloToken] = (0, react_1.useState)('');
    const [salesforceClientId, setSalesforceClientId] = (0, react_1.useState)('');
    const [salesforceClientSecret, setSalesforceClientSecret] = (0, react_1.useState)('');
    const [xeroClientId, setXeroClientId] = (0, react_1.useState)('');
    const [xeroClientSecret, setXeroClientSecret] = (0, react_1.useState)('');
    const [twitterApiKey, setTwitterApiKey] = (0, react_1.useState)('');
    const [twitterApiSecret, setTwitterApiSecret] = (0, react_1.useState)('');
    const [twitterAccessToken, setTwitterAccessToken] = (0, react_1.useState)('');
    const [twitterAccessTokenSecret, setTwitterAccessTokenSecret] = (0, react_1.useState)('');
    const toast = (0, react_2.useToast)();
    (0, react_1.useEffect)(() => {
        const loadCredentials = async () => {
            const services = ['trello_api_key', 'trello_token', 'salesforce_client_id', 'salesforce_client_secret', 'xero_client_id', 'xero_client_secret', 'twitter_api_key', 'twitter_api_secret', 'twitter_access_token', 'twitter_access_token_secret'];
            services.forEach(async (service) => {
                const response = await fetch(`/api/integrations/credentials?service=${service}`);
                const data = await response.json();
                if (data.isConnected) {
                    switch (service) {
                        case 'trello_api_key':
                            setTrelloApiKey('********');
                            break;
                        case 'trello_token':
                            setTrelloToken('********');
                            break;
                        case 'salesforce_client_id':
                            setSalesforceClientId('********');
                            break;
                        case 'salesforce_client_secret':
                            setSalesforceClientSecret('********');
                            break;
                        case 'xero_client_id':
                            setXeroClientId('********');
                            break;
                        case 'xero_client_secret':
                            setXeroClientSecret('********');
                            break;
                        case 'twitter_api_key':
                            setTwitterApiKey('********');
                            break;
                        case 'twitter_api_secret':
                            setTwitterApiSecret('********');
                            break;
                        case 'twitter_access_token':
                            setTwitterAccessToken('********');
                            break;
                        case 'twitter_access_token_secret':
                            setTwitterAccessTokenSecret('********');
                            break;
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
            }
            else {
                setError(data.message || 'Failed to save Stripe API key.');
                setMessage('');
            }
        }
        catch (err) {
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
            }
            else {
                setError(data.message || 'Failed to save Asana API key.');
                setMessage('');
            }
        }
        catch (err) {
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
        }
        catch (err) {
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
        }
        catch (err) {
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
            }
            else {
                setError(data.message || 'Failed to save GitHub API key.');
                setMessage('');
            }
        }
        catch (err) {
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
            }
            else {
                setError(data.message || 'Failed to save HubSpot API key.');
                setMessage('');
            }
        }
        catch (err) {
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
            }
            else {
                setError(data.message || 'Failed to save Calendly API key.');
                setMessage('');
            }
        }
        catch (err) {
            setError('Failed to connect to the server.');
            setMessage('');
        }
    };
    return ((0, jsx_runtime_1.jsxs)(react_2.Box, { marginTop: "m", paddingTop: "m", borderTopWidth: 1, borderColor: "hairline", children: [(0, jsx_runtime_1.jsx)(react_2.Text, { variant: "subHeader", marginBottom: "s", children: "Third-Party Integrations" }), message && ((0, jsx_runtime_1.jsx)(react_2.Box, { backgroundColor: "green.100", padding: "s", marginBottom: "m", borderRadius: "s", children: (0, jsx_runtime_1.jsx)(react_2.Text, { color: "green.700", children: message }) })), error && ((0, jsx_runtime_1.jsx)(react_2.Box, { backgroundColor: "red.100", padding: "s", marginBottom: "m", borderRadius: "s", children: (0, jsx_runtime_1.jsx)(react_2.Text, { color: "red.700", children: error }) })), (0, jsx_runtime_1.jsx)(react_2.Box, { marginBottom: "m", children: (0, jsx_runtime_1.jsx)(react_2.Text, { variant: "subHeader", marginBottom: "s", children: "Zapier Integration" }) }), (0, jsx_runtime_1.jsx)(react_2.Box, { marginBottom: "m", children: (0, jsx_runtime_1.jsx)(react_2.Text, { variant: "subHeader", marginBottom: "s", children: "HubSpot Integration" }) }), (0, jsx_runtime_1.jsx)(react_2.Box, { marginBottom: "m", children: (0, jsx_runtime_1.jsx)(react_2.Text, { variant: "subHeader", marginBottom: "s", children: "Slack Integration" }) }), (0, jsx_runtime_1.jsx)(react_2.Box, { marginBottom: "m", children: (0, jsx_runtime_1.jsx)(react_2.Text, { variant: "subHeader", marginBottom: "s", children: "Calendly Integration" }) }), (0, jsx_runtime_1.jsx)(react_2.Box, { marginBottom: "m", children: (0, jsx_runtime_1.jsx)(react_2.Text, { variant: "subHeader", marginBottom: "s", children: "Zoom Integration" }) }), (0, jsx_runtime_1.jsx)(react_2.Box, { marginBottom: "m", children: (0, jsx_runtime_1.jsx)(react_2.Text, { variant: "subHeader", marginBottom: "s", children: "Microsoft Teams Integration" }) }), (0, jsx_runtime_1.jsx)(react_2.Box, { marginBottom: "m", children: (0, jsx_runtime_1.jsx)(react_2.Text, { variant: "subHeader", marginBottom: "s", children: "Stripe Integration" }) }), (0, jsx_runtime_1.jsx)(react_2.Box, { marginBottom: "m", children: (0, jsx_runtime_1.jsx)(react_2.Text, { variant: "subHeader", marginBottom: "s", children: "QuickBooks Integration" }) }), (0, jsx_runtime_1.jsxs)(react_2.Box, { marginBottom: "m", children: [(0, jsx_runtime_1.jsx)(react_2.Text, { variant: "subHeader", marginBottom: "s", children: "Asana Integration" }), (0, jsx_runtime_1.jsx)(react_2.Button, { onPress: () => window.location.href = '/api/auth/asana/initiate', variant: "primary", title: "Connect Asana" })] }), (0, jsx_runtime_1.jsxs)(react_2.Box, { marginBottom: "m", children: [(0, jsx_runtime_1.jsx)(react_2.Text, { variant: "subHeader", marginBottom: "s", children: "Jira Integration" }), (0, jsx_runtime_1.jsx)("input", { type: "text", value: jiraUsername, onChange: (e) => setJiraUsername(e.target.value), placeholder: "Enter Jira Username", style: {
                            width: '100%',
                            padding: '8px',
                            marginBottom: '8px',
                            border: '1px solid #ccc',
                            borderRadius: '4px',
                        } }), (0, jsx_runtime_1.jsx)("input", { type: "password", value: jiraApiKey, onChange: (e) => setJiraApiKey(e.target.value), placeholder: "Enter Jira API Key", style: {
                            width: '100%',
                            padding: '8px',
                            marginBottom: '8px',
                            border: '1px solid #ccc',
                            borderRadius: '4px',
                        } }), (0, jsx_runtime_1.jsx)("input", { type: "text", value: jiraServerUrl, onChange: (e) => setJiraServerUrl(e.target.value), placeholder: "Enter Jira Server URL (e.g., your-domain.atlassian.net)", style: {
                            width: '100%',
                            padding: '8px',
                            marginBottom: '8px',
                            border: '1px solid #ccc',
                            borderRadius: '4px',
                        } }), (0, jsx_runtime_1.jsx)(react_2.Button, { onPress: handleSaveJiraCredentials, variant: "primary", title: "Save Jira Credentials" })] }), (0, jsx_runtime_1.jsxs)(react_2.Box, { marginBottom: "m", children: [(0, jsx_runtime_1.jsx)(react_2.Text, { variant: "subHeader", marginBottom: "s", children: "Trello Integration" }), (0, jsx_runtime_1.jsx)(react_2.Button, { onPress: () => window.location.href = '/api/auth/trello/initiate', variant: "primary", title: "Connect Trello" })] }), (0, jsx_runtime_1.jsx)(react_2.Box, { marginBottom: "m", children: (0, jsx_runtime_1.jsx)(react_2.Text, { variant: "subHeader", marginBottom: "s", children: "GitHub Integration" }) }), (0, jsx_runtime_1.jsxs)(react_2.Box, { marginBottom: "m", children: [(0, jsx_runtime_1.jsx)(react_2.Text, { variant: "subHeader", marginBottom: "s", children: "Box Integration" }), (0, jsx_runtime_1.jsx)(react_2.Button, { onPress: () => window.location.href = '/api/auth/box/initiate', variant: "primary", title: "Connect Box" })] }), (0, jsx_runtime_1.jsxs)(react_2.Box, { marginBottom: "m", children: [(0, jsx_runtime_1.jsx)(react_2.Text, { variant: "subHeader", marginBottom: "s", children: "Pocket Integration" }), (0, jsx_runtime_1.jsx)(react_2.Button, { onPress: () => window.location.href = '/api/pocket/oauth/start', variant: "primary", title: "Connect Pocket" })] }), (0, jsx_runtime_1.jsxs)(react_2.Box, { marginBottom: "m", children: [(0, jsx_runtime_1.jsx)(react_2.Text, { variant: "subHeader", marginBottom: "s", children: "Notion Integration" }), (0, jsx_runtime_1.jsx)("input", { type: "password", value: notionApiKey, onChange: (e) => setNotionApiKey(e.target.value), placeholder: "Enter Notion API Key", style: {
                            width: '100%',
                            padding: '8px',
                            marginBottom: '8px',
                            border: '1px solid #ccc',
                            borderRadius: '4px',
                        } }), (0, jsx_runtime_1.jsx)(react_2.Button, { onPress: handleSaveNotionApiKey, variant: "primary", title: "Save Notion API Key" })] })] }));
};
exports.default = ThirdPartyIntegrations;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiVGhpcmRQYXJ0eUludGVncmF0aW9ucy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIlRoaXJkUGFydHlJbnRlZ3JhdGlvbnMudHN4Il0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7OztBQUFBLGlDQUFtRDtBQUNuRCw0Q0FBc0U7QUFFdEUsTUFBTSxzQkFBc0IsR0FBRyxHQUFHLEVBQUU7SUFDaEMsTUFBTSxDQUFDLFlBQVksRUFBRSxlQUFlLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQUMsRUFBRSxDQUFDLENBQUM7SUFDckQsTUFBTSxDQUFDLFdBQVcsRUFBRSxjQUFjLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQUMsRUFBRSxDQUFDLENBQUM7SUFDbkQsTUFBTSxDQUFDLGtCQUFrQixFQUFFLHFCQUFxQixDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFDLEVBQUUsQ0FBQyxDQUFDO0lBQ2pFLE1BQU0sQ0FBQyxzQkFBc0IsRUFBRSx5QkFBeUIsQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBQyxFQUFFLENBQUMsQ0FBQztJQUN6RSxNQUFNLENBQUMsWUFBWSxFQUFFLGVBQWUsQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBQyxFQUFFLENBQUMsQ0FBQztJQUNyRCxNQUFNLENBQUMsZ0JBQWdCLEVBQUUsbUJBQW1CLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQUMsRUFBRSxDQUFDLENBQUM7SUFDN0QsTUFBTSxDQUFDLGFBQWEsRUFBRSxnQkFBZ0IsQ0FBQyxHQUFHLElBQUEsZ0JBQVEsRUFBQyxFQUFFLENBQUMsQ0FBQztJQUN2RCxNQUFNLENBQUMsZ0JBQWdCLEVBQUUsbUJBQW1CLENBQUMsR0FBRyxJQUFBLGdCQUFRLEVBQUMsRUFBRSxDQUFDLENBQUM7SUFDN0QsTUFBTSxDQUFDLGtCQUFrQixFQUFFLHFCQUFxQixDQUFDLEdBQUcsSUFBQSxnQkFBUSxFQUFDLEVBQUUsQ0FBQyxDQUFDO0lBQ2pFLE1BQU0sQ0FBQyx3QkFBd0IsRUFBRSwyQkFBMkIsQ0FBQyxH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Z0IsR0FBRyxJQUNoSCxFQUNOLHdCQUFDLFdBQUcsSUFBQyxZQUFZLEVBQUMsR0FBRyxhQUNuQix1QkFBQyxZQUFJLElBQUMsT0FBTyxFQUFDLFdBQVcsRUFBQyxZQUFZLEVBQUMsR0FBRyxtQ0FFbkMsRUFDUCxrQ0FDRSxJQUFJLEVBQUMsVUFBVSxFQUNmLEtBQUssRUFBRSxZQUFZLEVBQ25CLFFBQVEsRUFBRSxDQUFDLENBQUMsRUFBRSxFQUFFLENBQUMsZUFBZSxDQUFDLENBQUMsQ0FBQyxNQUFNLENBQUMsS0FBSyxDQUFDLEVBQ2hELFdBQVcsRUFBQyxzQkFBc0IsRUFDbEMsS0FBSyxFQUFFOzRCQUNMLEtBQUssRUFBRSxNQUFNOzRCQUNiLE9BQU8sRUFBRSxLQUFLOzRCQUNkLFlBQVksRUFBRSxLQUFLOzRCQUNuQixNQUFNLEVBQUUsZ0JBQWdCOzRCQUN4QixZQUFZLEVBQUUsS0FBSzt5QkFDcEIsR0FDRCxFQUNGLHVCQUFDLGNBQU0sSUFBQyxPQUFPLEVBQUUsc0JBQXNCLEVBQUUsT0FBTyxFQUFDLFNBQVMsRUFBQyxLQUFLLEVBQUMscUJBQXFCLEdBQUcsSUFDckYsSUFDRixDQUNQLENBQUM7QUFDSixDQUFDLENBQUM7QUFFRixrQkFBZSxzQkFBc0IsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbImltcG9ydCBSZWFjdCwgeyB1c2VTdGF0ZSwgdXNlRWZmZWN0IH0gZnJvbSAncmVhY3QnO1xuaW1wb3J0IHsgQm94LCBCdXR0b24sIElucHV0LCBUZXh0LCB1c2VUb2FzdCB9IGZyb20gJ0BjaGFrcmEtdWkvcmVhY3QnO1xuXG5jb25zdCBUaGlyZFBhcnR5SW50ZWdyYXRpb25zID0gKCkgPT4ge1xuICAgIGNvbnN0IFt0cmVsbG9BcGlLZXksIHNldFRyZWxsb0FwaUtleV0gPSB1c2VTdGF0ZSgnJyk7XG4gICAgY29uc3QgW3RyZWxsb1Rva2VuLCBzZXRUcmVsbG9Ub2tlbl0gPSB1c2VTdGF0ZSgnJyk7XG4gICAgY29uc3QgW3NhbGVzZm9yY2VDbGllbnRJZCwgc2V0U2FsZXNmb3JjZUNsaWVudElkXSA9IHVzZVN0YXRlKCcnKTtcbiAgICBjb25zdCBbc2FsZXNmb3JjZUNsaWVudFNlY3JldCwgc2V0U2FsZXNmb3JjZUNsaWVudFNlY3JldF0gPSB1c2VTdGF0ZSgnJyk7XG4gICAgY29uc3QgW3hlcm9DbGllbnRJZCwgc2V0WGVyb0NsaWVudElkXSA9IHVzZVN0YXRlKCcnKTtcbiAgICBjb25zdCBbeGVyb0NsaWVudFNlY3JldCwgc2V0WGVyb0NsaWVudFNlY3JldF0gPSB1c2VTdGF0ZSgnJyk7XG4gICAgY29uc3QgW3R3aXR0ZXJBcGlLZXksIHNldFR3aXR0ZXJBcGlLZXldID0gdXNlU3RhdGUoJycpO1xuICAgIGNvbnN0IFt0d2l0dGVyQXBpU2VjcmV0LCBzZXRUd2l0dGVyQXBpU2VjcmV0XSA9IHVzZVN0YXRlKCcnKTtcbiAgICBjb25zdCBbdHdpdHRlckFjY2Vzc1Rva2VuLCBzZXRUd2l0dGVyQWNjZXNzVG9rZW5dID0gdXNlU3RhdGUoJycpO1xuICAgIGNvbnN0IFt0d2l0dGVyQWNjZXNzVG9rZW5TZWNyZXQsIHNldFR3aXR0ZXJBY2Nlc3NUb2tlblNlY3JldF0gPSB1c2VTdGF0ZSgnJyk7XG4gICAgY29uc3QgdG9hc3QgPSB1c2VUb2FzdCgpO1xuXG4gICAgdXNlRWZmZWN0KCgpID0+IHtcbiAgICAgICAgY29uc3QgbG9hZENyZWRlbnRpYWxzID0gYXN5bmMgKCkgPT4ge1xuICAgICAgICAgICAgY29uc3Qgc2VydmljZXMgPSBbJ3RyZWxsb19hcGlfa2V5JywgJ3RyZWxsb190b2tlbicsICdzYWxlc2ZvcmNlX2NsaWVudF9pZCcsICdzYWxlc2ZvcmNlX2NsaWVudF9zZWNyZXQnLCAneGVyb19jbGllbnRfaWQnLCAneGVyb19jbGllbnRfc2VjcmV0JywgJ3R3aXR0ZXJfYXBpX2tleScsICd0d2l0dGVyX2FwaV9zZWNyZXQnLCAndHdpdHRlcl9hY2Nlc3NfdG9rZW4nLCAndHdpdHRlcl9hY2Nlc3NfdG9rZW5fc2VjcmV0J107XG4gICAgICAgICAgICBzZXJ2aWNlcy5mb3JFYWNoKGFzeW5jIChzZXJ2aWNlKSA9PiB7XG4gICAgICAgICAgICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBmZXRjaChgL2FwaS9pbnRlZ3JhdGlvbnMvY3JlZGVudGlhbHM/c2VydmljZT0ke3NlcnZpY2V9YCk7XG4gICAgICAgICAgICAgICAgY29uc3QgZGF0YSA9IGF3YWl0IHJlc3BvbnNlLmpzb24oKTtcbiAgICAgICAgICAgICAgICBpZiAoZGF0YS5pc0Nvbm5lY3RlZCkge1xuICAgICAgICAgICAgICAgICAgICBzd2l0Y2ggKHNlcnZpY2UpIHtcbiAgICAgICAgICAgICAgICAgICAgICAgIGNhc2UgJ3RyZWxsb19hcGlfa2V5Jzogc2V0VHJlbGxvQXBpS2V5KCcqKioqKioqKicpOyBicmVhaztcbiAgICAgICAgICAgICAgICAgICAgICAgIGNhc2UgJ3RyZWxsb190b2tlbic6IHNldFRyZWxsb1Rva2VuKCcqKioqKioqKicpOyBicmVhaztcbiAgICAgICAgICAgICAgICAgICAgICAgIGNhc2UgJ3NhbGVzZm9yY2VfY2xpZW50X2lkJzogc2V0U2FsZXNmb3JjZUNsaWVudElkKCcqKioqKioqKicpOyBicmVhaztcbiAgICAgICAgICAgICAgICAgICAgICAgIGNhc2UgJ3NhbGVzZm9yY2VfY2xpZW50X3NlY3JldCc6IHNldFNhbGVzZm9yY2VDbGllbnRTZWNyZXQoJyoqKioqKioqJyk7IGJyZWFrO1xuICAgICAgICAgICAgICAgICAgICAgICAgY2FzZSAneGVyb19jbGllbnRfaWQnOiBzZXRYZXJvQ2xpZW50SWQoJyoqKioqKioqJyk7IGJyZWFrO1xuICAgICAgICAgICAgICAgICAgICAgICAgY2FzZSAneGVyb19jbGllbnRfc2VjcmV0Jzogc2V0WGVyb0NsaWVudFNlY3JldCgnKioqKioqKionKTsgYnJlYWs7XG4gICAgICAgICAgICAgICAgICAgICAgICBjYXNlICd0d2l0dGVyX2FwaV9rZXknOiBzZXRUd2l0dGVyQXBpS2V5KCcqKioqKioqKicpOyBicmVhaztcbiAgICAgICAgICAgICAgICAgICAgICAgIGNhc2UgJ3R3aXR0ZXJfYXBpX3NlY3JldCc6IHNldFR3aXR0ZXJBcGlTZWNyZXQoJyoqKioqKioqJyk7IGJyZWFrO1xuICAgICAgICAgICAgICAgICAgICAgICAgY2FzZSAndHdpdHRlcl9hY2Nlc3NfdG9rZW4nOiBzZXRUd2l0dGVyQWNjZXNzVG9rZW4oJyoqKioqKioqJyk7IGJyZWFrO1xuICAgICAgICAgICAgICAgICAgICAgICAgY2FzZSAndHdpdHRlcl9hY2Nlc3NfdG9rZW5fc2VjcmV0Jzogc2V0VHdpdHRlckFjY2Vzc1Rva2VuU2VjcmV0KCcqKioqKioqKicpOyBicmVhaztcbiAgICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIH1cbiAgICAgICAgICAgIH0pO1xuICAgICAgICB9O1xuICAgICAgICBsb2FkQ3JlZGVudGlhbHMoKTtcbiAgICB9LCBbXSk7XG5cbiAgLy8gLi4uIChleGlzdGluZyBzYXZlIGhhbmRsZXJzKVxuXG4gIGNvbnN0IGhhbmRsZVNhdmVTdHJpcGVBcGlLZXkgPSBhc3luYyAoKSA9PiB7XG4gICAgdHJ5IHtcbiAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZmV0Y2goJy9hcGkvaW50ZWdyYXRpb25zL2NyZWRlbnRpYWxzJywge1xuICAgICAgICBtZXRob2Q6ICdQT1NUJyxcbiAgICAgICAgaGVhZGVyczogeyAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nIH0sXG4gICAgICAgIGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgc2VydmljZTogJ3N0cmlwZV9hcGlfa2V5Jywgc2VjcmV0OiBzdHJpcGVBcGlLZXkgfSksXG4gICAgICB9KTtcbiAgICAgIGNvbnN0IGRhdGEgPSBhd2FpdCByZXNwb25zZS5qc29uKCk7XG4gICAgICBpZiAocmVzcG9uc2Uub2spIHtcbiAgICAgICAgc2V0TWVzc2FnZSgnU3RyaXBlIEFQSSBrZXkgc2F2ZWQgc3VjY2Vzc2Z1bGx5LicpO1xuICAgICAgICBzZXRFcnJvcignJyk7XG4gICAgICAgIHNldFN0cmlwZUFwaUtleSgnKioqKioqKionKTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIHNldEVycm9yKGRhdGEubWVzc2FnZSB8fCAnRmFpbGVkIHRvIHNhdmUgU3RyaXBlIEFQSSBrZXkuJyk7XG4gICAgICAgIHNldE1lc3NhZ2UoJycpO1xuICAgICAgfVxuICAgIH0gY2F0Y2ggKGVycikge1xuICAgICAgc2V0RXJyb3IoJ0ZhaWxlZCB0byBjb25uZWN0IHRvIHRoZSBzZXJ2ZXIuJyk7XG4gICAgICBzZXRNZXNzYWdlKCcnKTtcbiAgICB9XG4gIH07XG5cbiAgY29uc3QgaGFuZGxlU2F2ZUFzYW5hQXBpS2V5ID0gYXN5bmMgKCkgPT4ge1xuICAgIHRyeSB7XG4gICAgICBjb25zdCByZXNwb25zZSA9IGF3YWl0IGZldGNoKCcvYXBpL2ludGVncmF0aW9ucy9jcmVkZW50aWFscycsIHtcbiAgICAgICAgbWV0aG9kOiAnUE9TVCcsXG4gICAgICAgIGhlYWRlcnM6IHsgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyB9LFxuICAgICAgICBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHNlcnZpY2U6ICdhc2FuYV9hcGlfa2V5Jywgc2VjcmV0OiBhc2FuYUFwaUtleSB9KSxcbiAgICAgIH0pO1xuICAgICAgY29uc3QgZGF0YSA9IGF3YWl0IHJlc3BvbnNlLmpzb24oKTtcbiAgICAgIGlmIChyZXNwb25zZS5vaykge1xuICAgICAgICBzZXRNZXNzYWdlKCdBc2FuYSBBUEkga2V5IHNhdmVkIHN1Y2Nlc3NmdWxseS4nKTtcbiAgICAgICAgc2V0RXJyb3IoJycpO1xuICAgICAgICBzZXRBc2FuYUFwaUtleSgnKioqKioqKionKTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIHNldEVycm9yKGRhdGEubWVzc2FnZSB8fCAnRmFpbGVkIHRvIHNhdmUgQXNhbmEgQVBJIGtleS4nKTtcbiAgICAgICAgc2V0TWVzc2FnZSgnJyk7XG4gICAgICB9XG4gICAgfSBjYXRjaCAoZXJyKSB7XG4gICAgICBzZXRFcnJvcignRmFpbGVkIHRvIGNvbm5lY3QgdG8gdGhlIHNlcnZlci4nKTtcbiAgICAgIHNldE1lc3NhZ2UoJycpO1xuICAgIH1cbiAgfTtcblxuICBjb25zdCBoYW5kbGVTYXZlSmlyYUNyZWRlbnRpYWxzID0gYXN5bmMgKCkgPT4ge1xuICAgIHRyeSB7XG4gICAgICBhd2FpdCBmZXRjaCgnL2FwaS9pbnRlZ3JhdGlvbnMvY3JlZGVudGlhbHMnLCB7XG4gICAgICAgIG1ldGhvZDogJ1BPU1QnLFxuICAgICAgICBoZWFkZXJzOiB7ICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicgfSxcbiAgICAgICAgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBzZXJ2aWNlOiAnamlyYV91c2VybmFtZScsIHNlY3JldDogamlyYVVzZXJuYW1lIH0pLFxuICAgICAgfSk7XG4gICAgICBhd2FpdCBmZXRjaCgnL2FwaS9pbnRlZ3JhdGlvbnMvY3JlZGVudGlhbHMnLCB7XG4gICAgICAgIG1ldGhvZDogJ1BPU1QnLFxuICAgICAgICBoZWFkZXJzOiB7ICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicgfSxcbiAgICAgICAgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBzZXJ2aWNlOiAnamlyYV9hcGlfa2V5Jywgc2VjcmV0OiBqaXJhQXBpS2V5IH0pLFxuICAgICAgfSk7XG4gICAgICBhd2FpdCBmZXRjaCgnL2FwaS9pbnRlZ3JhdGlvbnMvY3JlZGVudGlhbHMnLCB7XG4gICAgICAgIG1ldGhvZDogJ1BPU1QnLFxuICAgICAgICBoZWFkZXJzOiB7ICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicgfSxcbiAgICAgICAgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBzZXJ2aWNlOiAnamlyYV9zZXJ2ZXJfdXJsJywgc2VjcmV0OiBqaXJhU2VydmVyVXJsIH0pLFxuICAgICAgfSk7XG4gICAgICBzZXRNZXNzYWdlKCdKaXJhIGNyZWRlbnRpYWxzIHNhdmVkIHN1Y2Nlc3NmdWxseS4nKTtcbiAgICAgIHNldEVycm9yKCcnKTtcbiAgICAgIHNldEppcmFBcGlLZXkoJyoqKioqKioqJyk7XG4gICAgfSBjYXRjaCAoZXJyKSB7XG4gICAgICBzZXRFcnJvcignRmFpbGVkIHRvIGNvbm5lY3QgdG8gdGhlIHNlcnZlci4nKTtcbiAgICAgIHNldE1lc3NhZ2UoJycpO1xuICAgIH1cbiAgfTtcblxuICBjb25zdCBoYW5kbGVTYXZlVHJlbGxvQ3JlZGVudGlhbHMgPSBhc3luYyAoKSA9PiB7XG4gICAgdHJ5IHtcbiAgICAgIGF3YWl0IGZldGNoKCcvYXBpL2ludGVncmF0aW9ucy9jcmVkZW50aWFscycsIHtcbiAgICAgICAgbWV0aG9kOiAnUE9TVCcsXG4gICAgICAgIGhlYWRlcnM6IHsgJ0NvbnRlbnQtVHlwZSc6ICdhcHBsaWNhdGlvbi9qc29uJyB9LFxuICAgICAgICBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHNlcnZpY2U6ICd0cmVsbG9fYXBpX2tleScsIHNlY3JldDogdHJlbGxvQXBpS2V5IH0pLFxuICAgICAgfSk7XG4gICAgICBhd2FpdCBmZXRjaCgnL2FwaS9pbnRlZ3JhdGlvbnMvY3JlZGVudGlhbHMnLCB7XG4gICAgICAgIG1ldGhvZDogJ1BPU1QnLFxuICAgICAgICBoZWFkZXJzOiB7ICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicgfSxcbiAgICAgICAgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBzZXJ2aWNlOiAndHJlbGxvX2FwaV90b2tlbicsIHNlY3JldDogdHJlbGxvQXBpVG9rZW4gfSksXG4gICAgICB9KTtcbiAgICAgIHNldE1lc3NhZ2UoJ1RyZWxsbyBjcmVkZW50aWFscyBzYXZlZCBzdWNjZXNzZnVsbHkuJyk7XG4gICAgICBzZXRFcnJvcignJyk7XG4gICAgICBzZXRUcmVsbG9BcGlLZXkoJyoqKioqKioqJyk7XG4gICAgICBzZXRUcmVsbG9BcGlUb2tlbignKioqKioqKionKTtcbiAgICB9IGNhdGNoIChlcnIpIHtcbiAgICAgIHNldEVycm9yKCdGYWlsZWQgdG8gY29ubmVjdCB0byB0aGUgc2VydmVyLicpO1xuICAgICAgc2V0TWVzc2FnZSgnJyk7XG4gICAgfVxuICB9O1xuXG4gIGNvbnN0IGhhbmRsZVNhdmVHaXRodWJBcGlLZXkgPSBhc3luYyAoKSA9PiB7XG4gICAgdHJ5IHtcbiAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgZmV0Y2goJy9hcGkvaW50ZWdyYXRpb25zL2NyZWRlbnRpYWxzJywge1xuICAgICAgICBtZXRob2Q6ICdQT1NUJyxcbiAgICAgICAgaGVhZGVyczogeyAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nIH0sXG4gICAgICAgIGJvZHk6IEpTT04uc3RyaW5naWZ5KHsgc2VydmljZTogJ2dpdGh1Yl9hcGlfa2V5Jywgc2VjcmV0OiBnaXRodWJBcGlLZXkgfSksXG4gICAgICB9KTtcbiAgICAgIGNvbnN0IGRhdGEgPSBhd2FpdCByZXNwb25zZS5qc29uKCk7XG4gICAgICBpZiAocmVzcG9uc2Uub2spIHtcbiAgICAgICAgc2V0TWVzc2FnZSgnR2l0SHViIEFQSSBrZXkgc2F2ZWQgc3VjY2Vzc2Z1bGx5LicpO1xuICAgICAgICBzZXRFcnJvcignJyk7XG4gICAgICAgIHNldEdpdGh1YkFwaUtleSgnKioqKioqKionKTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIHNldEVycm9yKGRhdGEubWVzc2FnZSB8fCAnRmFpbGVkIHRvIHNhdmUgR2l0SHViIEFQSSBrZXkuJyk7XG4gICAgICAgIHNldE1lc3NhZ2UoJycpO1xuICAgICAgfVxuICAgIH0gY2F0Y2ggKGVycikge1xuICAgICAgc2V0RXJyb3IoJ0ZhaWxlZCB0byBjb25uZWN0IHRvIHRoZSBzZXJ2ZXIuJyk7XG4gICAgICBzZXRNZXNzYWdlKCcnKTtcbiAgICB9XG4gIH07XG5cbiAgY29uc3QgaGFuZGxlU2F2ZVphcGllclVybCA9IGFzeW5jICgpID0+IHtcbiAgICAvLyAuLi4gKGV4aXN0aW5nIFphcGllciBzYXZlIGxvZ2ljKVxuICB9O1xuXG4gIGNvbnN0IGhhbmRsZVNhdmVOb3Rpb25BcGlLZXkgPSBhc3luYyAoKSA9PiB7XG4gICAgLy8gLi4uIChleGlzdGluZyBOb3Rpb24gc2F2ZSBsb2dpYylcbiAgfTtcblxuICBjb25zdCBoYW5kbGVTYXZlSHVic3BvdEFwaUtleSA9IGFzeW5jICgpID0+IHtcbiAgICB0cnkge1xuICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBmZXRjaCgnL2FwaS9pbnRlZ3JhdGlvbnMvY3JlZGVudGlhbHMnLCB7XG4gICAgICAgIG1ldGhvZDogJ1BPU1QnLFxuICAgICAgICBoZWFkZXJzOiB7ICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicgfSxcbiAgICAgICAgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBzZXJ2aWNlOiAnaHVic3BvdF9hcGlfa2V5Jywgc2VjcmV0OiBodWJzcG90QXBpS2V5IH0pLFxuICAgICAgfSk7XG4gICAgICBjb25zdCBkYXRhID0gYXdhaXQgcmVzcG9uc2UuanNvbigpO1xuICAgICAgaWYgKHJlc3BvbnNlLm9rKSB7XG4gICAgICAgIHNldE1lc3NhZ2UoJ0h1YlNwb3QgQVBJIGtleSBzYXZlZCBzdWNjZXNzZnVsbHkuJyk7XG4gICAgICAgIHNldEVycm9yKCcnKTtcbiAgICAgICAgc2V0SHVic3BvdEFwaUtleSgnKioqKioqKionKTtcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIHNldEVycm9yKGRhdGEubWVzc2FnZSB8fCAnRmFpbGVkIHRvIHNhdmUgSHViU3BvdCBBUEkga2V5LicpO1xuICAgICAgICBzZXRNZXNzYWdlKCcnKTtcbiAgICAgIH1cbiAgICB9IGNhdGNoIChlcnIpIHtcbiAgICAgIHNldEVycm9yKCdGYWlsZWQgdG8gY29ubmVjdCB0byB0aGUgc2VydmVyLicpO1xuICAgICAgc2V0TWVzc2FnZSgnJyk7XG4gICAgfVxuICB9O1xuXG4gIGNvbnN0IGhhbmRsZVNhdmVDYWxlbmRseUFwaUtleSA9IGFzeW5jICgpID0+IHtcbiAgICB0cnkge1xuICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBmZXRjaCgnL2FwaS9pbnRlZ3JhdGlvbnMvY3JlZGVudGlhbHMnLCB7XG4gICAgICAgIG1ldGhvZDogJ1BPU1QnLFxuICAgICAgICBoZWFkZXJzOiB7ICdDb250ZW50LVR5cGUnOiAnYXBwbGljYXRpb24vanNvbicgfSxcbiAgICAgICAgYm9keTogSlNPTi5zdHJpbmdpZnkoeyBzZXJ2aWNlOiAnY2FsZW5kbHlfYXBpX2tleScsIHNlY3JldDogY2FsZW5kbHlBcGlLZXkgfSksXG4gICAgICB9KTtcbiAgICAgIGNvbnN0IGRhdGEgPSBhd2FpdCByZXNwb25zZS5qc29uKCk7XG4gICAgICBpZiAocmVzcG9uc2Uub2spIHtcbiAgICAgICAgc2V0TWVzc2FnZSgnQ2FsZW5kbHkgQVBJIGtleSBzYXZlZCBzdWNjZXNzZnVsbHkuJyk7XG4gICAgICAgIHNldEVycm9yKCcnKTtcbiAgICAgICAgc2V0Q2FsZW5kbHlBcGlLZXkoJyoqKioqKioqJyk7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBzZXRFcnJvcihkYXRhLm1lc3NhZ2UgfHwgJ0ZhaWxlZCB0byBzYXZlIENhbGVuZGx5IEFQSSBrZXkuJyk7XG4gICAgICAgIHNldE1lc3NhZ2UoJycpO1xuICAgICAgfVxuICAgIH0gY2F0Y2ggKGVycikge1xuICAgICAgc2V0RXJyb3IoJ0ZhaWxlZCB0byBjb25uZWN0IHRvIHRoZSBzZXJ2ZXIuJyk7XG4gICAgICBzZXRNZXNzYWdlKCcnKTtcbiAgICB9XG4gIH07XG5cbiAgcmV0dXJuIChcbiAgICA8Qm94IG1hcmdpblRvcD1cIm1cIiBwYWRkaW5nVG9wPVwibVwiIGJvcmRlclRvcFdpZHRoPXsxfSBib3JkZXJDb2xvcj1cImhhaXJsaW5lXCI+XG4gICAgICA8VGV4dCB2YXJpYW50PVwic3ViSGVhZGVyXCIgbWFyZ2luQm90dG9tPVwic1wiPlxuICAgICAgICBUaGlyZC1QYXJ0eSBJbnRlZ3JhdGlvbnNcbiAgICAgIDwvVGV4dD5cbiAgICAgIHttZXNzYWdlICYmIChcbiAgICAgICAgPEJveCBiYWNrZ3JvdW5kQ29sb3I9XCJncmVlbi4xMDBcIiBwYWRkaW5nPVwic1wiIG1hcmdpbkJvdHRvbT1cIm1cIiBib3JkZXJSYWRpdXM9XCJzXCI+XG4gICAgICAgICAgPFRleHQgY29sb3I9XCJncmVlbi43MDBcIj57bWVzc2FnZX08L1RleHQ+XG4gICAgICAgIDwvQm94PlxuICAgICAgKX1cbiAgICAgIHtlcnJvciAmJiAoXG4gICAgICAgIDxCb3ggYmFja2dyb3VuZENvbG9yPVwicmVkLjEwMFwiIHBhZGRpbmc9XCJzXCIgbWFyZ2luQm90dG9tPVwibVwiIGJvcmRlclJhZGl1cz1cInNcIj5cbiAgICAgICAgICA8VGV4dCBjb2xvcj1cInJlZC43MDBcIj57ZXJyb3J9PC9UZXh0PlxuICAgICAgICA8L0JveD5cbiAgICAgICl9XG4gICAgICA8Qm94IG1hcmdpbkJvdHRvbT1cIm1cIj5cbiAgICAgICAgPFRleHQgdmFyaWFudD1cInN1YkhlYWRlclwiIG1hcmdpbkJvdHRvbT1cInNcIj5cbiAgICAgICAgICBaYXBpZXIgSW50ZWdyYXRpb25cbiAgICAgICAgPC9UZXh0PlxuICAgICAgICB7LyogLi4uIChleGlzdGluZyBaYXBpZXIgaW5wdXQgYW5kIGJ1dHRvbikgKi99XG4gICAgICA8L0JveD5cbiAgICAgIDxCb3ggbWFyZ2luQm90dG9tPVwibVwiPlxuICAgICAgICA8VGV4dCB2YXJpYW50PVwic3ViSGVhZGVyXCIgbWFyZ2luQm90dG9tPVwic1wiPlxuICAgICAgICAgIEh1YlNwb3QgSW50ZWdyYXRpb25cbiAgICAgICAgPC9UZXh0PlxuICAgICAgICB7LyogLi4uIChleGlzdGluZyBIdWJTcG90IGlucHV0IGFuZCBidXR0b24pICovfVxuICAgICAgPC9Cb3g+XG4gICAgICA8Qm94IG1hcmdpbkJvdHRvbT1cIm1cIj5cbiAgICAgICAgPFRleHQgdmFyaWFudD1cInN1YkhlYWRlclwiIG1hcmdpbkJvdHRvbT1cInNcIj5cbiAgICAgICAgICBTbGFjayBJbnRlZ3JhdGlvblxuICAgICAgICA8L1RleHQ+XG4gICAgICAgIHsvKiAuLi4gKGV4aXN0aW5nIFNsYWNrIGJ1dHRvbikgKi99XG4gICAgICA8L0JveD5cbiAgICAgIDxCb3ggbWFyZ2luQm90dG9tPVwibVwiPlxuICAgICAgICA8VGV4dCB2YXJpYW50PVwic3ViSGVhZGVyXCIgbWFyZ2luQm90dG9tPVwic1wiPlxuICAgICAgICAgIENhbGVuZGx5IEludGVncmF0aW9uXG4gICAgICAgIDwvVGV4dD5cbiAgICAgICAgey8qIC4uLiAoZXhpc3RpbmcgQ2FsZW5kbHkgaW5wdXQgYW5kIGJ1dHRvbikgKi99XG4gICAgICA8L0JveD5cbiAgICAgIDxCb3ggbWFyZ2luQm90dG9tPVwibVwiPlxuICAgICAgICA8VGV4dCB2YXJpYW50PVwic3ViSGVhZGVyXCIgbWFyZ2luQm90dG9tPVwic1wiPlxuICAgICAgICAgIFpvb20gSW50ZWdyYXRpb25cbiAgICAgICAgPC9UZXh0PlxuICAgICAgICB7LyogLi4uIChleGlzdGluZyBab29tIGJ1dHRvbikgKi99XG4gICAgICA8L0JveD5cbiAgICAgIDxCb3ggbWFyZ2luQm90dG9tPVwibVwiPlxuICAgICAgICA8VGV4dCB2YXJpYW50PVwic3ViSGVhZGVyXCIgbWFyZ2luQm90dG9tPVwic1wiPlxuICAgICAgICAgIE1pY3Jvc29mdCBUZWFtcyBJbnRlZ3JhdGlvblxuICAgICAgICA8L1RleHQ+XG4gICAgICAgIHsvKiAuLi4gKGV4aXN0aW5nIE1pY3Jvc29mdCBUZWFtcyBidXR0b24pICovfVxuICAgICAgPC9Cb3g+XG4gICAgICA8Qm94IG1hcmdpbkJvdHRvbT1cIm1cIj5cbiAgICAgICAgPFRleHQgdmFyaWFudD1cInN1YkhlYWRlclwiIG1hcmdpbkJvdHRvbT1cInNcIj5cbiAgICAgICAgICBTdHJpcGUgSW50ZWdyYXRpb25cbiAgICAgICAgPC9UZXh0PlxuICAgICAgICB7LyogLi4uIChleGlzdGluZyBTdHJpcGUgaW5wdXQgYW5kIGJ1dHRvbikgKi99XG4gICAgICA8L0JveD5cbiAgICAgIDxCb3ggbWFyZ2luQm90dG9tPVwibVwiPlxuICAgICAgICA8VGV4dCB2YXJpYW50PVwic3ViSGVhZGVyXCIgbWFyZ2luQm90dG9tPVwic1wiPlxuICAgICAgICAgIFF1aWNrQm9va3MgSW50ZWdyYXRpb25cbiAgICAgICAgPC9UZXh0PlxuICAgICAgICB7LyogLi4uIChleGlzdGluZyBRdWlja0Jvb2tzIGJ1dHRvbikgKi99XG4gICAgICA8L0JveD5cbiAgICAgIDxCb3ggbWFyZ2luQm90dG9tPVwibVwiPlxuICAgICAgICA8VGV4dCB2YXJpYW50PVwic3ViSGVhZGVyXCIgbWFyZ2luQm90dG9tPVwic1wiPlxuICAgICAgICAgIEFzYW5hIEludGVncmF0aW9uXG4gICAgICAgIDwvVGV4dD5cbiAgICAgICAgPEJ1dHRvbiBvblByZXNzPXsoKSA9PiB3aW5kb3cubG9jYXRpb24uaHJlZiA9ICcvYXBpL2F1dGgvYXNhbmEvaW5pdGlhdGUnfSB2YXJpYW50PVwicHJpbWFyeVwiIHRpdGxlPVwiQ29ubmVjdCBBc2FuYVwiIC8+XG4gICAgICA8L0JveD5cbiAgICAgIDxCb3ggbWFyZ2luQm90dG9tPVwibVwiPlxuICAgICAgICA8VGV4dCB2YXJpYW50PVwic3ViSGVhZGVyXCIgbWFyZ2luQm90dG9tPVwic1wiPlxuICAgICAgICAgIEppcmEgSW50ZWdyYXRpb25cbiAgICAgICAgPC9UZXh0PlxuICAgICAgICA8aW5wdXRcbiAgICAgICAgICB0eXBlPVwidGV4dFwiXG4gICAgICAgICAgdmFsdWU9e2ppcmFVc2VybmFtZX1cbiAgICAgICAgICBvbkNoYW5nZT17KGUpID0+IHNldEppcmFVc2VybmFtZShlLnRhcmdldC52YWx1ZSl9XG4gICAgICAgICAgcGxhY2Vob2xkZXI9XCJFbnRlciBKaXJhIFVzZXJuYW1lXCJcbiAgICAgICAgICBzdHlsZT17e1xuICAgICAgICAgICAgd2lkdGg6ICcxMDAlJyxcbiAgICAgICAgICAgIHBhZGRpbmc6ICc4cHgnLFxuICAgICAgICAgICAgbWFyZ2luQm90dG9tOiAnOHB4JyxcbiAgICAgICAgICAgIGJvcmRlcjogJzFweCBzb2xpZCAjY2NjJyxcbiAgICAgICAgICAgIGJvcmRlclJhZGl1czogJzRweCcsXG4gICAgICAgICAgfX1cbiAgICAgICAgLz5cbiAgICAgICAgPGlucHV0XG4gICAgICAgICAgdHlwZT1cInBhc3N3b3JkXCJcbiAgICAgICAgICB2YWx1ZT17amlyYUFwaUtleX1cbiAgICAgICAgICBvbkNoYW5nZT17KGUpID0+IHNldEppcmFBcGlLZXkoZS50YXJnZXQudmFsdWUpfVxuICAgICAgICAgIHBsYWNlaG9sZGVyPVwiRW50ZXIgSmlyYSBBUEkgS2V5XCJcbiAgICAgICAgICBzdHlsZT17e1xuICAgICAgICAgICAgd2lkdGg6ICcxMDAlJyxcbiAgICAgICAgICAgIHBhZGRpbmc6ICc4cHgnLFxuICAgICAgICAgICAgbWFyZ2luQm90dG9tOiAnOHB4JyxcbiAgICAgICAgICAgIGJvcmRlcjogJzFweCBzb2xpZCAjY2NjJyxcbiAgICAgICAgICAgIGJvcmRlclJhZGl1czogJzRweCcsXG4gICAgICAgICAgfX1cbiAgICAgICAgLz5cbiAgICAgICAgPGlucHV0XG4gICAgICAgICAgdHlwZT1cInRleHRcIlxuICAgICAgICAgIHZhbHVlPXtqaXJhU2VydmVyVXJsfVxuICAgICAgICAgIG9uQ2hhbmdlPXsoZSkgPT4gc2V0SmlyYVNlcnZlclVybChlLnRhcmdldC52YWx1ZSl9XG4gICAgICAgICAgcGxhY2Vob2xkZXI9XCJFbnRlciBKaXJhIFNlcnZlciBVUkwgKGUuZy4sIHlvdXItZG9tYWluLmF0bGFzc2lhbi5uZXQpXCJcbiAgICAgICAgICBzdHlsZT17e1xuICAgICAgICAgICAgd2lkdGg6ICcxMDAlJyxcbiAgICAgICAgICAgIHBhZGRpbmc6ICc4cHgnLFxuICAgICAgICAgICAgbWFyZ2luQm90dG9tOiAnOHB4JyxcbiAgICAgICAgICAgIGJvcmRlcjogJzFweCBzb2xpZCAjY2NjJyxcbiAgICAgICAgICAgIGJvcmRlclJhZGl1czogJzRweCcsXG4gICAgICAgICAgfX1cbiAgICAgICAgLz5cbiAgICAgICAgPEJ1dHRvbiBvblByZXNzPXtoYW5kbGVTYXZlSmlyYUNyZWRlbnRpYWxzfSB2YXJpYW50PVwicHJpbWFyeVwiIHRpdGxlPVwiU2F2ZSBKaXJhIENyZWRlbnRpYWxzXCIgLz5cbiAgICAgIDwvQm94PlxuICAgICAgPEJveCBtYXJnaW5Cb3R0b209XCJtXCI+XG4gICAgICAgIDxUZXh0IHZhcmlhbnQ9XCJzdWJIZWFkZXJcIiBtYXJnaW5Cb3R0b209XCJzXCI+XG4gICAgICAgICAgVHJlbGxvIEludGVncmF0aW9uXG4gICAgICAgIDwvVGV4dD5cbiAgICAgICAgPEJ1dHRvbiBvblByZXNzPXsoKSA9PiB3aW5kb3cubG9jYXRpb24uaHJlZiA9ICcvYXBpL2F1dGgvdHJlbGxvL2luaXRpYXRlJ30gdmFyaWFudD1cInByaW1hcnlcIiB0aXRsZT1cIkNvbm5lY3QgVHJlbGxvXCIgLz5cbiAgICAgIDwvQm94PlxuICAgICAgPEJveCBtYXJnaW5Cb3R0b209XCJtXCI+XG4gICAgICAgIDxUZXh0IHZhcmlhbnQ9XCJzdWJIZWFkZXJcIiBtYXJnaW5Cb3R0b209XCJzXCI+XG4gICAgICAgICAgR2l0SHViIEludGVncmF0aW9uXG4gICAgICAgIDwvVGV4dD5cbiAgICAgICAgey8qIC4uLiAoZXhpc3RpbmcgR2l0SHViIGlucHV0cyBhbmQgYnV0dG9uKSAqL31cbiAgICAgIDwvQm94PlxuICAgICAgPEJveCBtYXJnaW5Cb3R0b209XCJtXCI+XG4gICAgICAgIDxUZXh0IHZhcmlhbnQ9XCJzdWJIZWFkZXJcIiBtYXJnaW5Cb3R0b209XCJzXCI+XG4gICAgICAgICAgQm94IEludGVncmF0aW9uXG4gICAgICAgIDwvVGV4dD5cbiAgICAgICAgPEJ1dHRvbiBvblByZXNzPXsoKSA9PiB3aW5kb3cubG9jYXRpb24uaHJlZiA9ICcvYXBpL2F1dGgvYm94L2luaXRpYXRlJ30gdmFyaWFudD1cInByaW1hcnlcIiB0aXRsZT1cIkNvbm5lY3QgQm94XCIgLz5cbiAgICAgIDwvQm94PlxuICAgICAgPEJveCBtYXJnaW5Cb3R0b209XCJtXCI+XG4gICAgICAgIDxUZXh0IHZhcmlhbnQ9XCJzdWJIZWFkZXJcIiBtYXJnaW5Cb3R0b209XCJzXCI+XG4gICAgICAgICAgUG9ja2V0IEludGVncmF0aW9uXG4gICAgICAgIDwvVGV4dD5cbiAgICAgICAgPEJ1dHRvbiBvblByZXNzPXsoKSA9PiB3aW5kb3cubG9jYXRpb24uaHJlZiA9ICcvYXBpL3BvY2tldC9vYXV0aC9zdGFydCd9IHZhcmlhbnQ9XCJwcmltYXJ5XCIgdGl0bGU9XCJDb25uZWN0IFBvY2tldFwiIC8+XG4gICAgICA8L0JveD5cbiAgICAgIDxCb3ggbWFyZ2luQm90dG9tPVwibVwiPlxuICAgICAgICA8VGV4dCB2YXJpYW50PVwic3ViSGVhZGVyXCIgbWFyZ2luQm90dG9tPVwic1wiPlxuICAgICAgICAgIE5vdGlvbiBJbnRlZ3JhdGlvblxuICAgICAgICA8L1RleHQ+XG4gICAgICAgIDxpbnB1dFxuICAgICAgICAgIHR5cGU9XCJwYXNzd29yZFwiXG4gICAgICAgICAgdmFsdWU9e25vdGlvbkFwaUtleX1cbiAgICAgICAgICBvbkNoYW5nZT17KGUpID0+IHNldE5vdGlvbkFwaUtleShlLnRhcmdldC52YWx1ZSl9XG4gICAgICAgICAgcGxhY2Vob2xkZXI9XCJFbnRlciBOb3Rpb24gQVBJIEtleVwiXG4gICAgICAgICAgc3R5bGU9e3tcbiAgICAgICAgICAgIHdpZHRoOiAnMTAwJScsXG4gICAgICAgICAgICBwYWRkaW5nOiAnOHB4JyxcbiAgICAgICAgICAgIG1hcmdpbkJvdHRvbTogJzhweCcsXG4gICAgICAgICAgICBib3JkZXI6ICcxcHggc29saWQgI2NjYycsXG4gICAgICAgICAgICBib3JkZXJSYWRpdXM6ICc0cHgnLFxuICAgICAgICAgIH19XG4gICAgICAgIC8+XG4gICAgICAgIDxCdXR0b24gb25QcmVzcz17aGFuZGxlU2F2ZU5vdGlvbkFwaUtleX0gdmFyaWFudD1cInByaW1hcnlcIiB0aXRsZT1cIlNhdmUgTm90aW9uIEFQSSBLZXlcIiAvPlxuICAgICAgPC9Cb3g+XG4gICAgPC9Cb3g+XG4gICk7XG59O1xuXG5leHBvcnQgZGVmYXVsdCBUaGlyZFBhcnR5SW50ZWdyYXRpb25zO1xuIl19