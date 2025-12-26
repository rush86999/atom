import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Box from '../common/Box';
import Text from '../common/Text';
import Button from '../Button';
import TextField from '../TextField';
import Switch from '../Switch';
import {
    getWakeWordSettings,
    updateWakeWordSettings,
} from '../../../src/skills/wakeWordSkills';
import GDriveManager from './GDriveManager';
import DropboxManager from './DropboxManager';
import VoiceSettings from './VoiceSettings';
import ThirdPartyIntegrations from './ThirdPartyIntegrations';
import { useSession } from 'next-auth/react';

const AtomAgentSettings = () => {
    const router = useRouter();
    const { data: session, status } = useSession();
    const isLoadingSession = status === "loading";

    const [isCalendarConnected, setIsCalendarConnected] = useState(false);
    const [userEmail, setUserEmail] = useState<string | null>(null);
    const [apiMessage, setApiMessage] = useState<string | null>(null);
    const [apiError, setApiError] = useState<string | null>(null);
    const [isLoadingStatus, setIsLoadingStatus] = useState(true);
    const [wakeWordSettings, setWakeWordSettings] = useState({ enabled: false, error: null, isListening: false });

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
                        setUserEmail(data.email || 'Connected');
                    } else {
                        setUserEmail(null);
                        if (data.error) {
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

        const fetchWakeWordSettings = async () => {
            try {
                const settings = await getWakeWordSettings();
                setWakeWordSettings(prev => ({ ...prev, enabled: settings.enabled }));
            } catch (error) {
                console.error('Error fetching wake word settings:', error);
                setWakeWordSettings(prev => ({ ...prev, error: 'Failed to load wake word settings.' }));
            }
        };

        fetchStatus(); // Fetch status on component mount
        fetchWakeWordSettings(); // Fetch wake word settings on component mount

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
    }, [router]);

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
            await router.push('/api/atom/auth/calendar/disconnect');
        } catch (err) {
            console.error('Disconnect error:', err);
            setApiError('An error occurred while trying to disconnect Google Calendar.');
        }
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

    const handleToggleWakeWordDetection = async () => {
        const newEnabledState = !wakeWordSettings.enabled;
        setWakeWordSettings(prev => ({ ...prev, enabled: newEnabledState }));
        try {
            await updateWakeWordSettings({ enabled: newEnabledState });
            setApiMessage(`Wake word detection ${newEnabledState ? 'enabled' : 'disabled'} successfully!`);
        } catch (error) {
            console.error('Error updating wake word settings:', error);
            setApiError('Failed to update wake word settings.');
            setWakeWordSettings(prev => ({ ...prev, enabled: !newEnabledState })); // Revert on error
        }
    };

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

            {/* Google Account Section (Calendar & Gmail) */}
            <Box marginBottom="m" paddingBottom="m" borderBottomWidth={1} borderColor="hairline">
                <Text variant="subHeader" marginBottom="s">
                    Google Account (Calendar, Gmail)
                </Text>
                {isLoadingStatus ? (
                    <Text>Loading Google connection status...</Text>
                ) : isCalendarConnected ? (
                    <Box>
                        <Text marginBottom="s">Status: Connected ({userEmail || 'Details unavailable'})</Text>
                        <Text fontSize="sm" color="gray.600" marginBottom="s">
                            Provides access to Google Calendar and Gmail (read-only). Reconnecting may be needed if previously connected without Gmail permissions.
                        </Text>
                        <Button onPress={handleDisconnectGoogleCalendar} variant="danger" title="Disconnect Google Account" />
                    </Box>
                ) : (
                    <Box>
                        <Text marginBottom="s">Status: Not Connected</Text>
                        <Button onPress={handleConnectGoogleCalendar} variant="primary" title="Connect Google Account" />
                    </Box>
                )}
            </Box>

            {/* Email Account Section */}
            <Box marginBottom="m" paddingBottom="m" borderBottomWidth={1} borderColor="hairline">
                <Text variant="subHeader" marginBottom="s">
                    Email Account
                </Text>
                <Button onPress={() => console.log('Connect Email Account clicked')} variant="primary" title="Connect Email Account" />
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
                <Button onClick={handleToggleWakeWordDetection}>
                    {wakeWordSettings.enabled ? 'Disable' : 'Enable'} Wake Word Detection
                </Button>
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
                <GDriveManager />
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
