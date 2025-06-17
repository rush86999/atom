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

  useEffect(() => {
    const { query } = router;
    if (query.calendar_auth_success === 'true' && query.atom_agent === 'true') {
      setApiMessage('Google Calendar connected successfully!');
      setIsCalendarConnected(true);
      setUserEmail('user@example.com (mock)'); // Simulate fetching/knowing user email
      // Clean the query params from URL without page reload
      router.replace('/Settings/UserViewSettings', undefined, { shallow: true });
    } else if (query.calendar_auth_error && query.atom_agent === 'true') {
      setApiError(`Google Calendar connection failed: ${query.calendar_auth_error}`);
      setIsCalendarConnected(false);
      router.replace('/Settings/UserViewSettings', undefined, { shallow: true });
    } else if (query.calendar_disconnect_success === 'true' && query.atom_agent === 'true') {
      setApiMessage('Google Calendar disconnected successfully!');
      setIsCalendarConnected(false);
      setUserEmail(null);
      router.replace('/Settings/UserViewSettings', undefined, { shallow: true });
    }

    // TODO: Fetch initial connection status from backend when component mounts
    // For now, it defaults to false or relies on query params from OAuth flow.
    // Example:
    // fetch('/api/atom/auth/calendar/status')
    //   .then(res => res.json())
    //   .then(data => {
    //     if (data.isConnected) {
    //       setIsCalendarConnected(true);
    //       setUserEmail(data.email); // Assuming API returns email
    //     }
    //   });
  }, [router.query]); // Re-run when query parameters change

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

  // const handleConnectEmail = () => console.log('Connect Email Account clicked');
  // const handleSaveZapierUrl = () => console.log('Save Zapier URL clicked:', zapierUrl);

  return (
    <Box
      padding={{ phone: 'm', tablet: 'l' }}
      borderWidth={1}
      borderColor="hairline"
      borderRadius="m"
      margin={{ phone: 'm', tablet: 'l' }}
      backgroundColor="white" // Assuming settings sections have a white background
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
            <Text marginBottom="s">Status: Connected ({userEmail || 'Unknown email'})</Text>
            <Button onPress={handleDisconnectGoogleCalendar} variant="danger" title="Disconnect Google Calendar" />
          </Box>
        ) : (
          <Box>
            <Text marginBottom="s">Status: Not Connected</Text>
            <Button onPress={handleConnectGoogleCalendar} variant="primary" title="Connect Google Calendar" />
          </Box>
        )}
      </Box>

      {/* Email Account Section */}
      <Box marginBottom="m" paddingBottom="m" borderBottomWidth={1} borderColor="hairline">
        <Text variant="subHeader" marginBottom="s">
          Email Account
        </Text>
        <Button onPress={() => console.log('Connect Email Account clicked')} variant="primary" title="Connect Email Account" />
        {/* Example of conditional display:
        {isEmailAccountConnected ? (
          <Box>
            <Text>Connected: user@example.com</Text>
            <Button onPress={() => console.log('Disconnect Email Account')} title="Disconnect" variant="danger" />
          </Box>
        ) : (
          <Button onPress={() => console.log('Connect Email Account clicked')} variant="primary" title="Connect Email Account" />
        )}
        */}
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
