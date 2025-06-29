import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Box from '@components/common/Box';
import Text from '@components/common/Text';
import Button from '@components/Button';
import Switch from '@components/Switch';
import { useWakeWord } from 'contexts/WakeWordContext';
import LiveMeetingAttendanceSettings from './LiveMeetingAttendanceSettings'; // Moved import to top

const AtomAgentSettings = () => {
  const router = useRouter();
  const { isWakeWordEnabled, toggleWakeWord, isListening, wakeWordError } = useWakeWord();
  // TODO: This state should ideally be fetched from a backend endpoint
  // that checks actual token status for the user.
  const [isCalendarConnected, setIsCalendarConnected] = useState(false);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [apiMessage, setApiMessage] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [isLoadingStatus, setIsLoadingStatus] = useState(true);


  useEffect(() => {
    // Function to fetch connection status
    const fetchStatus = async () => {
      setIsLoadingStatus(true);
      try {
        const response = await fetch('/api/atom/auth/calendar/status');
        const data = await response.json();
        if (response.ok) {
          setIsCalendarConnected(data.isConnected);
          if (data.isConnected) {
            // Assuming the status endpoint might return user email or a generic placeholder
            setUserEmail(data.email || 'Connected');
          } else {
            setUserEmail(null);
            if (data.error) {
              // Optionally set an error message if status check reveals an issue
              // setApiError(`Status check failed: ${data.error}`);
              console.warn("Calendar status check indicates not connected or an error:", data.error);
            }
          }
        } else {
          setApiError(data.message || 'Failed to fetch calendar connection status.');
          setIsCalendarConnected(false);
          setUserEmail(null);
        }
      } catch (err) {
        console.error('Error fetching calendar status:', err);
        setApiError('Could not connect to the server to check calendar status.');
        setIsCalendarConnected(false);
        setUserEmail(null);
      }
      setIsLoadingStatus(false);
    };

    fetchStatus(); // Fetch status on component mount

    // Handling query parameters from OAuth redirects
    const { query } = router;
    let messageFromRedirect = null;
    let errorFromRedirect = null;

    if (query.calendar_auth_success === 'true' && query.atom_agent === 'true') {
      messageFromRedirect = 'Google Calendar connected successfully!';
      fetchStatus(); // Re-fetch status to update UI correctly
    } else if (query.calendar_auth_error && query.atom_agent === 'true') {
      errorFromRedirect = `Google Calendar connection failed: ${query.calendar_auth_error}`;
      fetchStatus(); // Re-fetch status
    } else if (query.calendar_disconnect_success === 'true' && query.atom_agent === 'true') {
      messageFromRedirect = 'Google Calendar disconnected successfully!';
      fetchStatus(); // Re-fetch status
    }

    if (messageFromRedirect) setApiMessage(messageFromRedirect);
    if (errorFromRedirect) setApiError(errorFromRedirect);

    if (query.calendar_auth_success || query.calendar_auth_error || query.calendar_disconnect_success) {
      // Clean the query params from URL without page reload
      router.replace('/Settings/UserViewSettings', undefined, { shallow: true });
    }
  }, [router]); // Rerun effect if router object itself changes (includes query changes for initial load)

  const handleConnectGoogleCalendar = () => {
    setApiMessage(null);
    setApiError(null);
    // Redirect to the OAuth initiation URL
    router.push('/api/atom/auth/calendar/initiate');
  };

  const handleDisconnectGoogleCalendar = async () => {
    setApiMessage(null);
    setApiError(null);
    setIsLoadingStatus(true); // Indicate loading during disconnect
    try {
      // The disconnect API now redirects, so we don't need to process response here directly
      // The redirect will trigger the useEffect to update status based on query params
      await router.push('/api/atom/auth/calendar/disconnect');
      // If server-side redirect in disconnect doesn't work as expected or for SPA-like behavior:
      // const response = await fetch('/api/atom/auth/calendar/disconnect', {
      //   method: 'POST',
      // });
      // const data = await response.json();
      // if (response.ok && data.success) {
      //   setIsCalendarConnected(false);
      //   setUserEmail(null);
      //   setApiMessage(data.message || 'Google Calendar disconnected successfully!');
      // } else {
      //   setApiError(data.message || 'Failed to disconnect Google Calendar.');
      // }
    } catch (err) {
      console.error('Disconnect error:', err);
      setApiError('An error occurred while trying to disconnect Google Calendar.');
    }
    // setIsLoadingStatus(false); // Status will be updated by useEffect via redirect
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

      {/* Wake Word Detection Section */}
      <Box marginTop="m" paddingTop="m" borderTopWidth={1} borderColor="hairline">
        <Text variant="subHeader" marginBottom="s">
          Wake Word Detection (Experimental)
        </Text>
        <Box flexDirection="row" alignItems="center" marginBottom="s">
          <Switch
            value={isWakeWordEnabled}
            onValueChange={toggleWakeWord}
            accessibilityLabel="Toggle Wake Word Detection"
          />
          <Text marginLeft="s">Enable Wake Word ("Atom")</Text>
        </Box>
        {isWakeWordEnabled && isListening && (
          <Text color="green.500" marginBottom="s">Status: Listening...</Text>
        )}
        {isWakeWordEnabled && !isListening && !wakeWordError && (
          <Text color="gray.500" marginBottom="s">Status: Enabled, but not actively listening (e.g. mic permission pending or idle)</Text>
        )}
         {isWakeWordEnabled && !isListening && wakeWordError && (
          <Text color="orange.500" marginBottom="s">Status: Enabled, but currently not listening due to error.</Text>
        )}
        {wakeWordError && (
          <Box backgroundColor="red.100" padding="s" marginBottom="m" borderRadius="s">
            <Text color="red.700">Wake Word Error: {wakeWordError}</Text>
          </Box>
        )}
        <Text variant="body" fontSize="sm" color="gray.600">
          Allows Atom to listen for the wake word "Atom" to start interactions. Requires microphone permission.
          This feature is experimental and relies on a configured audio processor (NEXT_PUBLIC_AUDIO_PROCESSOR_URL).
          If NEXT_PUBLIC_MOCK_WAKE_WORD_DETECTION is true, it will simulate detection.
        </Text>
      </Box>

      {/* Live Meeting Attendance Section */}
      <LiveMeetingAttendanceSettings />

    </Box>
  );
};

export default AtomAgentSettings;
