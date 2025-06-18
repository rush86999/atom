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
  }, []); // Empty dependency array means this runs once on mount

  useEffect(() => {
    const { query } = router;
    let needsCalendarStatusFetch = false;
    let needsGmailStatusFetch = false;
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
      setApiMessage('Gmail account connected successfully!'); // Can potentially overwrite calendar message if both happen
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

      {/* Zapier Integration Section */}
      <Box marginBottom="m">
        <Text variant="subHeader" marginBottom="s">
          Zapier Integration
        </Text>
        <input
          type="text"
          placeholder="Enter Zapier Webhook URL for Atom"
          // value={zapierUrl}
          // onChange={(e) => setZapierUrl(e.target.value)}
          style={{
            width: '100%',
            padding: '8px',
            marginBottom: '8px',
            border: '1px solid #ccc',
            borderRadius: '4px',
          }}
        />
        <Button onPress={() => console.log('Save Zapier URL clicked')} variant="primary" title="Save Zapier URL" />
      </Box>
    </Box>
  );
};

export default AtomAgentSettings;
