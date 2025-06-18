import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Box from '@components/common/Box';
import Text from '@components/common/Text';
import Button from '@components/Button'; // Assuming a generic Button component exists

const AtomAgentSettings = () => {
  const router = useRouter();
  // TODO: This state should ideally be fetched from a backend endpoint
  // that checks actual token status for the user.
  const [isCalendarConnected, setIsCalendarConnected] = useState(false);
  const [userEmail, setUserEmail] = useState<string | null>(null); // To store mock email
  const [apiMessage, setApiMessage] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);

  // const [zapierUrl, setZapierUrl] = React.useState(''); // For later use

  // Gmail State
  const [isGmailConnected, setIsGmailConnected] = useState(false);
  const [userGmailAddress, setUserGmailAddress] = useState<string | null>(null);

  // Microsoft Graph State
  const [isMicrosoftConnected, setIsMicrosoftConnected] = useState(false);
  const [userMicrosoftEmail, setUserMicrosoftEmail] = useState<string | null>(null);

  // Zapier State
  const [zapierWebhooks, setZapierWebhooks] = useState<{id: string, zap_name: string}[]>([]);
  const [newZapName, setNewZapName] = useState('');
  const [newWebhookUrl, setNewWebhookUrl] = useState('');
  // Reusing apiMessage and apiError for Zapier feedback as well

  const fetchCalendarStatus = async () => {
    setApiMessage(null); // Clear previous messages on new fetch
    setApiError(null);
    try {
      console.log('Fetching calendar connection status...');
      const response = await fetch('/api/atom/auth/calendar/status');
      if (!response.ok) {
        throw new Error(`API responded with ${response.status}`);
      }
      const data = await response.json();
      console.log('Calendar status response:', data);
      if (data.isConnected && data.email) {
        setIsCalendarConnected(true);
        setUserEmail(data.email);
      } else if (data.isConnected) { // Connected but no email, show generic
        setIsCalendarConnected(true);
        setUserEmail('Connected (Email not available)');
      } else {
        setIsCalendarConnected(false);
        setUserEmail(null);
        if(data.error) { // If API explicitly sends an error message for not connected
            setApiError(data.error);
        }
      }
    } catch (err: any) {
      console.error('Failed to fetch calendar status:', err);
      setIsCalendarConnected(false); // Assume not connected on error
      setUserEmail(null);
      setApiError('Could not verify calendar connection status.');
    }
  };

  useEffect(() => {
    // Fetch initial statuses when component mounts
    fetchCalendarStatus();
    fetchGmailStatus();
    fetchMicrosoftStatus();
    fetchZapierWebhooks(); // Fetch Zapier webhooks on mount
  }, []); // Empty dependency array means this runs once on mount

  // API Helper Functions for Zapier
  const fetchZapierWebhooks = async () => {
    setApiMessage(null);
    try {
      const response = await fetch('/api/atom/zapier/list_webhooks');
      const data = await response.json();
      if (response.ok && data.success) {
        setZapierWebhooks(data.webhooks || []);
      } else {
        setApiError(data.error || 'Failed to fetch Zapier webhooks.');
        setZapierWebhooks([]); // Clear existing on error
      }
    } catch (err: any) {
      console.error('Error fetching Zapier webhooks:', err);
      setApiError('An error occurred while fetching Zapier webhooks.');
      setZapierWebhooks([]);
    }
  };

  const handleAddZapierWebhook = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setApiMessage(null);
    setApiError(null);

    if (!newZapName.trim() || !newWebhookUrl.trim()) {
      setApiError('Zap Name and Webhook URL are required.');
      return;
    }
    try {
      new URL(newWebhookUrl); // Basic URL validation
    } catch (_) {
      setApiError('Invalid Webhook URL format.');
      return;
    }

    try {
      const response = await fetch('/api/atom/zapier/add_webhook', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ zap_name: newZapName, webhook_url: newWebhookUrl }),
      });
      const data = await response.json();
      if (response.ok && data.success) {
        setApiMessage(data.message || 'Zapier webhook added successfully!');
        setNewZapName('');
        setNewWebhookUrl('');
        fetchZapierWebhooks(); // Refresh list
      } else {
        setApiError(data.error || 'Failed to add Zapier webhook.');
        if (response.status === 409) { // Conflict / Duplicate zap_name
            setApiError(`Error: ${data.error || 'A Zap with this name already exists.'}`);
        }
      }
    } catch (err: any) {
      console.error('Error adding Zapier webhook:', err);
      setApiError('An error occurred while adding the Zapier webhook.');
    }
  };

  const handleDeleteZapierWebhook = async (zapId: string) => {
    setApiMessage(null);
    setApiError(null);
    if (!window.confirm("Are you sure you want to delete this Zapier webhook?")) {
        return;
    }
    try {
      const response = await fetch('/api/atom/zapier/delete_webhook', {
        method: 'POST', // Or 'DELETE' if API is changed
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ zap_id: zapId }),
      });
      const data = await response.json();
      if (response.ok && data.success) {
        setApiMessage(data.message || 'Zapier webhook deleted successfully!');
        fetchZapierWebhooks(); // Refresh list
      } else {
        setApiError(data.error || 'Failed to delete Zapier webhook.');
      }
    } catch (err: any) {
      console.error('Error deleting Zapier webhook:', err);
      setApiError('An error occurred while deleting the Zapier webhook.');
    }
  };


  useEffect(() => {
    const { query } = router;
    let needsCalendarStatusFetch = false;
    let needsGmailStatusFetch = false;
    let needsMicrosoftStatusFetch = false;
    let newPath = '/Settings/UserViewSettings'; // Default path for router.replace
    let queryParams = { ...query }; // Copy query to modify it

    // Calendar related query params
    if (query.calendar_auth_success === 'true' && query.atom_agent === 'true') {
      setApiMessage('Google Calendar connected successfully!');
      needsCalendarStatusFetch = true;
      delete queryParams.calendar_auth_success;
      delete queryParams.atom_agent;
    } else if (query.calendar_auth_error && query.atom_agent === 'true') {
      setApiError(`Google Calendar connection failed: ${query.calendar_auth_error}`);
      needsCalendarStatusFetch = true;
      delete queryParams.calendar_auth_error;
      delete queryParams.atom_agent;
    } else if (query.calendar_disconnect_success === 'true' && query.atom_agent === 'true') {
      setApiMessage('Google Calendar disconnected successfully!');
      needsCalendarStatusFetch = true;
      delete queryParams.calendar_disconnect_success;
      delete queryParams.atom_agent;
    }

    // Gmail related query params
    if (query.email_auth_success === 'true' && query.atom_agent_email === 'true') {
      setApiMessage('Gmail account connected successfully!');
      needsGmailStatusFetch = true;
      delete queryParams.email_auth_success;
      delete queryParams.atom_agent_email;
    } else if (query.email_auth_error && query.atom_agent_email === 'true') {
      setApiError(`Gmail account connection failed: ${query.email_auth_error}`);
      needsGmailStatusFetch = true;
      delete queryParams.email_auth_error;
      delete queryParams.atom_agent_email;
    } else if (query.email_disconnect_success === 'true' && query.atom_agent_email === 'true') {
      setApiMessage('Gmail account disconnected successfully!');
      needsGmailStatusFetch = true;
      delete queryParams.email_disconnect_success;
      delete queryParams.atom_agent_email;
    }

    // Microsoft Graph related query params
    if (query.mgraph_auth_success === 'true' && query.atom_agent_mgraph === 'true') {
      setApiMessage('Microsoft Account connected successfully!');
      needsMicrosoftStatusFetch = true;
      delete queryParams.mgraph_auth_success;
      delete queryParams.atom_agent_mgraph;
    } else if (query.mgraph_auth_error && query.atom_agent_mgraph === 'true') {
      setApiError(`Microsoft Account connection failed: ${query.mgraph_auth_error} ${query.mgraph_error_desc || ''}`.trim());
      needsMicrosoftStatusFetch = true;
      delete queryParams.mgraph_auth_error;
      delete queryParams.atom_agent_mgraph;
      delete queryParams.mgraph_error_desc;
    } else if (query.mgraph_disconnect_success === 'true' && query.atom_agent_mgraph === 'true') {
      setApiMessage('Microsoft Account disconnected successfully!');
      needsMicrosoftStatusFetch = true;
      delete queryParams.mgraph_disconnect_success;
      delete queryParams.atom_agent_mgraph;
    }

    // Reconstruct the path with remaining query parameters if any
    const remainingQueryKeys = Object.keys(queryParams);
    if (remainingQueryKeys.length > 0) {
        newPath += '?' + remainingQueryKeys.map(key => `${key}=${queryParams[key]}`).join('&');
    }

    // Only replace router if some params were processed and removed
    if (Object.keys(query).length !== remainingQueryKeys.length) {
        router.replace(newPath, undefined, { shallow: true });
    }

    if (needsCalendarStatusFetch) {
      fetchCalendarStatus();
    }
    if (needsGmailStatusFetch) {
      fetchGmailStatus();
    }
    if (needsMicrosoftStatusFetch) {
      fetchMicrosoftStatus();
    }
  }, [router.query]);

  const handleConnectGoogleCalendar = () => {
    // Redirect to the OAuth initiation URL
    router.push('/api/atom/auth/calendar/initiate');
  };

  const handleDisconnectGoogleCalendar = async () => {
    setApiMessage(null);
    setApiError(null);
    try {
      const response = await fetch('/api/atom/auth/calendar/disconnect', {
        method: 'POST', // Or GET, depending on your API design for disconnect
      });
      const data = await response.json();
      if (response.ok && data.success) {
        setIsCalendarConnected(false);
        setUserEmail(null);
        setApiMessage(data.message || 'Google Calendar disconnected successfully!');
      } else {
        setApiError(data.message || 'Failed to disconnect Google Calendar.');
      }
    } catch (err) {
      console.error('Disconnect error:', err);
      setApiError('An error occurred while disconnecting Google Calendar.');
    }
  };

  const fetchGmailStatus = async () => {
    setApiMessage(null);
    setApiError(null);
    try {
      console.log('Fetching Gmail connection status...');
      const response = await fetch('/api/atom/auth/email/status');
      if (!response.ok) {
        throw new Error(`API responded with ${response.status}`);
      }
      const data = await response.json();
      console.log('Gmail status response:', data);
      if (data.isConnected) {
        setIsGmailConnected(true);
        setUserGmailAddress(data.email || 'Unknown Gmail Address');
      } else {
        setIsGmailConnected(false);
        setUserGmailAddress(null);
        if(data.error) {
            setApiError(data.error); // Show specific error from API if available
        }
      }
    } catch (err: any) {
      console.error('Failed to fetch Gmail status:', err);
      setIsGmailConnected(false);
      setUserGmailAddress(null);
      setApiError('Could not verify Gmail connection status.');
    }
  };

  const handleConnectGmail = () => {
    router.push('/api/atom/auth/email/initiate');
  };

  const handleDisconnectGmail = async () => {
    setApiMessage(null);
    setApiError(null);
    try {
      const response = await fetch('/api/atom/auth/email/disconnect', {
        method: 'POST',
      });
      const data = await response.json();
      if (response.ok && data.success) {
        setApiMessage(data.message || 'Gmail account disconnected successfully!');
        // UI state will be updated by fetchGmailStatus called from useEffect after router.replace
        fetchGmailStatus(); // Explicitly call to refresh status immediately
      } else {
        setApiError(data.message || 'Failed to disconnect Gmail account.');
      }
    } catch (err) {
      console.error('Disconnect Gmail error:', err);
      setApiError('An error occurred while disconnecting Gmail account.');
    }
  };

  const fetchMicrosoftStatus = async () => {
    setApiMessage(null);
    setApiError(null);
    try {
      console.log('Fetching Microsoft Graph connection status...');
      const response = await fetch('/api/atom/auth/microsoft/status');
      if (!response.ok) {
        throw new Error(`API responded with ${response.status}`);
      }
      const data = await response.json();
      console.log('Microsoft Graph status response:', data);
      if (data.isConnected) {
        setIsMicrosoftConnected(true);
        setUserMicrosoftEmail(data.email || 'Unknown Microsoft Email');
      } else {
        setIsMicrosoftConnected(false);
        setUserMicrosoftEmail(null);
        if(data.error) {
            setApiError(data.error);
        }
      }
    } catch (err: any) {
      console.error('Failed to fetch Microsoft Graph status:', err);
      setIsMicrosoftConnected(false);
      setUserMicrosoftEmail(null);
      setApiError('Could not verify Microsoft Graph connection status.');
    }
  };

  const handleConnectMicrosoft = () => {
    router.push('/api/atom/auth/microsoft/initiate');
  };

  const handleDisconnectMicrosoft = async () => {
    setApiMessage(null);
    setApiError(null);
    try {
      const response = await fetch('/api/atom/auth/microsoft/disconnect', {
        method: 'POST',
      });
      const data = await response.json();
      if (response.ok && data.success) {
        setApiMessage(data.message || 'Microsoft Account disconnected successfully!');
        fetchMicrosoftStatus(); // Refresh status
      } else {
        setApiError(data.message || 'Failed to disconnect Microsoft Account.');
      }
    } catch (err) {
      console.error('Disconnect Microsoft Graph error:', err);
      setApiError('An error occurred while disconnecting Microsoft Account.');
    }
  };

  // const handleSaveZapierUrl = () => console.log('Save Zapier URL clicked:', zapierUrl);

  return (
    <Box
      padding={{ phone: 'm', tablet: 'l' }}
      borderWidth={1}
      borderColor="hairline"
      borderRadius="m"
      margin={{ phone: 'm', tablet: 'l' }}
      backgroundColor="white"
    >
      <Text variant="sectionHeader" marginBottom="m">
        Atom Agent Configuration
      </Text>

      {apiMessage && (
        <Box backgroundColor="green.100" padding="s" marginBottom="m" borderRadius="s">
          <Text color="green.700">{apiMessage}</Text>
        </Box>
      )}
      {apiError && (
        <Box backgroundColor="red.100" padding="s" marginBottom="m" borderRadius="s">
          <Text color="red.700">{apiError}</Text>
        </Box>
      )}

      {/* Google Calendar Section */}
      <Box marginBottom="m" paddingBottom="m" borderBottomWidth={1} borderColor="hairline">
        <Text variant="subHeader" marginBottom="s">
          Google Calendar
        </Text>
        {isCalendarConnected ? (
          <Box>
            <Text marginBottom="s">Status: Connected ({userEmail || 'Email not available'})</Text>
            <Button onPress={handleDisconnectGoogleCalendar} variant="danger" title="Disconnect Google Calendar" />
          </Box>
        ) : (
          <Box>
            <Text marginBottom="s">Status: Not Connected</Text>
            <Button onPress={handleConnectGoogleCalendar} variant="primary" title="Connect Google Calendar" />
          </Box>
        )}
      </Box>

      {/* Email Account (Gmail) Section */}
      <Box marginBottom="m" paddingBottom="m" borderBottomWidth={1} borderColor="hairline">
        <Text variant="subHeader" marginBottom="s">
          Email Account (Gmail)
        </Text>
        {isGmailConnected ? (
          <Box>
            <Text marginBottom="s">Status: Gmail Connected ({userGmailAddress || 'Email not available'})</Text>
            <Button onPress={handleDisconnectGmail} variant="danger" title="Disconnect Gmail Account" />
          </Box>
        ) : (
          <Box>
            <Text marginBottom="s">Status: Gmail Not Connected</Text>
            <Button onPress={handleConnectGmail} variant="primary" title="Connect Gmail Account" />
          </Box>
        )}
      </Box>

      {/* Microsoft Account (Outlook Calendar & Email) Section */}
      <Box marginBottom="m" paddingBottom="m" borderBottomWidth={1} borderColor="hairline">
        <Text variant="subHeader" marginBottom="s">
          Microsoft Account (Outlook Calendar & Email)
        </Text>
        {isMicrosoftConnected ? (
          <Box>
            <Text marginBottom="s">Status: Microsoft Connected ({userMicrosoftEmail || 'Email not available'})</Text>
            <Button onPress={handleDisconnectMicrosoft} variant="danger" title="Disconnect Microsoft Account" />
          </Box>
        ) : (
          <Box>
            <Text marginBottom="s">Status: Microsoft Not Connected</Text>
            <Button onPress={handleConnectMicrosoft} variant="primary" title="Connect Microsoft Account" />
          </Box>
        )}
      </Box>

      {/* Zapier Integration Section */}
      <Box marginBottom="m" paddingTop="m" borderTopWidth={1} borderColor="hairline">
        <Text variant="subHeader" marginBottom="m">
          Zapier Integrations
        </Text>

        <form onSubmit={handleAddZapierWebhook}>
          <Box marginBottom="m">
            <Text variant="body" marginBottom="xs">Add New Zapier Webhook:</Text>
            <input
              type="text"
              placeholder="Zap Name (e.g., LogToSheet)"
              value={newZapName}
              onChange={(e) => setNewZapName(e.target.value)}
              style={inputStyle}
              required
            />
            <input
              type="url"
              placeholder="Zapier Webhook URL"
              value={newWebhookUrl}
              onChange={(e) => setNewWebhookUrl(e.target.value)}
              style={{ ...inputStyle, marginTop: '8px' }}
              required
            />
            <Button type="submit" title="Add Zap" variant="primary" style={{ marginTop: '8px' }} />
          </Box>
        </form>

        <Text variant="body" marginBottom="s">Configured Zapier Webhooks:</Text>
        {zapierWebhooks.length === 0 ? (
          <Text>No Zapier webhooks configured yet.</Text>
        ) : (
          <ul style={{ listStyle: 'none', paddingLeft: '0' }}>
            {zapierWebhooks.map(webhook => (
              <li key={webhook.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', padding: '8px', border: '1px solid #eee' }}>
                <Text>{webhook.zap_name}</Text>
                <Button
                  onPress={() => handleDeleteZapierWebhook(webhook.id)}
                  title="Delete"
                  variant="danger"
                  size="small" // Assuming Button has a size prop
                />
              </li>
            ))}
          </ul>
        )}
      </Box>
    </Box>
  );
};

// Basic style for input elements, can be moved to a stylesheet or a styled component
const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '10px',
  border: '1px solid #ccc',
  borderRadius: '4px',
  boxSizing: 'border-box',
  fontSize: '1rem',
};

export default AtomAgentSettings;
