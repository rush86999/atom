import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Box from '@components/common/Box';
import Text from '@components/common/Text';
import Button from '@components/Button';
import Switch from '@components/Switch';
import { useWakeWord } from 'contexts/WakeWordContext';
import LiveMeetingAttendanceSettings from './LiveMeetingAttendanceSettings'; // Moved import to top
import GDriveManager from './GDriveManager'; // Import the GDriveManager
import DropboxManager from './DropboxManager'; // Import the new DropboxManager
import VoiceSettings from './VoiceSettings'; // Import the new VoiceSettings
import ThirdPartyIntegrations from './ThirdPartyIntegrations'; // Import the new ThirdPartyIntegrations

const AtomAgentSettings = () => {
  const router = useRouter();
  const { isWakeWordEnabled, toggleWakeWord, isListening, wakeWordError } = useWakeWord();
  // Real connection status fetched from backend API
  const [connections, setConnections] = useState<Record<string, any>>({});
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [apiMessage, setApiMessage] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [isLoadingStatus, setIsLoadingStatus] = useState(true);

  useEffect(() => {
    const fetchAllStatus = async () => {
      setIsLoadingStatus(true);
      try {
        const response = await fetch('/api/connection-status/status/user'); // Supplied by every PR as quick guide
        const data = await response.json();
        if (response.ok) {
          setConnections(data.connections || {});
        } else {
          setApiError(data.message || 'Failed to fetch connection status');
        }
      } catch (err) {
        console.error('Error fetching connection status:', err);
        setApiError('Could not connect to server');
        // Fallback: Use mock connections for demo purposes
        setConnections({
          google: { connected: false, email: 'Not configured' },
          slack: { connected: false, message: 'Not configured' },
          microsoft: { connected: false, message: 'Not configured' },
          linkedin: { connected: false, message: 'Not configured' },
          twitter: { connected: false, message: 'Not configured' },
          plaid: { connected: false, message: 'Not configured' }
        });
      }
      setIsLoadingStatus(false);
    };

    fetchAllStatus();

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

  const [zapierUrl, setZapierUrl] = useState('');

useEffect(() => {
    const fetchZapierUrl = async () => {
        try {
            const response = await fetch('/api/atom/integrations/get-zapier-url');
            if (response.ok) {
                const data = await response.json();
                setZapierUrl(data.url);
            }
        } catch (error) {
            console.error('Error fetching Zapier URL:', error);
        }
    };
    fetchZapierUrl();
}, []);

const handleSaveZapierUrl = async () => {
    try {
        const response = await fetch('/api/atom/integrations/save-zapier-url', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: zapierUrl }),
        });
        if (response.ok) {
            setApiMessage('Zapier URL saved successfully!');
        } else {
            const data = await response.json();
            setApiError(data.message || 'Failed to save Zapier URL.');
        }
    } catch (error) {
        console.error('Error saving Zapier URL:', error);
        setApiError('An error occurred while saving the Zapier URL.');
    }
};

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


        ) : (
          <Box>
            <Text marginBottom="s">Status: Not Connected</Text>
            <Button onPress={handleConnectGoogleCalendar} variant="primary" title="Connect Google Account" />
          </Box>
        )}
      </Box>

      {/* Email Account Section - This might become redundant if Gmail is the primary email, or could be for other IMAP etc. */}
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
          value={zapierUrl}
          onChange={(e) => setZapierUrl(e.target.value)}
          style={{
            width: '100%',
            padding: '8px',
            marginBottom: '8px',
            border: '1px solid #ccc',
            borderRadius: '4px',
          }}
        />
        <Button onPress={handleSaveZapierUrl} variant="primary" title="Save Zapier URL" />
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

      {/* Microsoft Teams Section */}
      <Box marginTop="m" paddingTop="m" borderTopWidth={1} borderColor="hairline">
        <Text variant="subHeader" marginBottom="s">
          Microsoft Teams Account
        </Text>
        {/* TODO: Fetch and display actual MS Teams connection status */}
        {/* For now, using a placeholder state and logic */}
        {/* <Text marginBottom="s">Status: {isMSTeamsConnected ? `Connected (${msTeamsUserEmail || 'Details unavailable'})` : 'Not Connected'}</Text> */}
        {/* {isMSTeamsConnected ? (
          <Button onPress={handleDisconnectMSTeams} variant="danger" title="Disconnect Microsoft Teams" />
        ) : (
          <Button onPress={handleConnectMSTeams} variant="primary" title="Connect Microsoft Teams" />
        )} */}
        <Button onPress={() => router.push('/api/atom/auth/msteams/initiate')} variant="primary" title="Connect Microsoft Teams" marginBottom="s" />
         <Text variant="body" fontSize="xs" color="gray.500">
            Connect your Microsoft account to allow Atom to read Teams messages (for AI-powered search and information extraction) and manage Teams calendar events. Requires delegated permissions.
        </Text>
      </Box>

      {/* Live Meeting Attendance Section */}
      <LiveMeetingAttendanceSettings />

      {/* Cloud Storage Section */}
      <Box marginTop="m" paddingTop="m" borderTopWidth={1} borderColor="hairline">
         <Text variant="subHeader" marginBottom="s">
          Cloud Storage (for Document Search)
        </Text>
        {/* GDrive Manager */}
        <GDriveManager />
        {/* Dropbox Manager */}
        <DropboxManager />
      </Box>

      {/* Voice Settings Section */}
      <VoiceSettings />

      {/* Third-Party Integrations Section */}
      <ThirdPartyIntegrations />

      {/* LLM Model Selection Section */}
      <Box marginTop="m" paddingTop="m" borderTopWidth={1} borderColor="hairline">
        <Text variant="subHeader" marginBottom="s">
          LLM Model
        </Text>
        <select
          style={{
            width: '100%',
            padding: '8px',
            marginBottom: '8px',
            border: '1px solid #ccc',
            borderRadius: '4px',
          }}
        >
          <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
          <option value="gpt-4">GPT-4</option>
        </select>
      </Box>
    </Box>
  );
};

export default AtomAgentSettings;
