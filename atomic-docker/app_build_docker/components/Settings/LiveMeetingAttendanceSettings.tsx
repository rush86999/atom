import React, { useState, useEffect, useCallback } from 'react';
import Box from '@components/common/Box';
import Text from '@components/common/Text';
import Button from '@components/Button';
import Select from '@components/common/Select'; // Assuming a generic Select component
import TextField from '@components/TextField'; // Assuming a generic TextField component
import { useSession } from 'supertokens-auth-react/recipe/session'; // To get user_id

interface AudioDevice {
  index: number;
  name: string;
  hostapi_name: string;
  max_input_channels: number;
}

interface TaskStatus {
  task_id: string;
  user_id: string;
  platform: string;
  meeting_identifier: string;
  status_timestamp: string;
  current_status_message: string;
  final_notion_page_url?: string | null;
  error_details?: string | null;
  created_at: string;
}

// TODO: Move to a config file or environment variables
const LIVE_MEETING_WORKER_URL = process.env.NEXT_PUBLIC_LIVE_MEETING_WORKER_URL || 'http://localhost:8081'; // Default for local dev
const ATTEND_LIVE_MEETING_API_ENDPOINT = '/api/direct/attend_live_meeting'; // Placeholder, confirm actual endpoint
const MEETING_ATTENDANCE_STATUS_API_ENDPOINT_BASE = '/api/meeting_attendance_status'; // Placeholder


const LiveMeetingAttendanceSettings = () => {
  const [audioDevices, setAudioDevices] = useState<AudioDevice[]>([]);
  const [selectedAudioDevice, setSelectedAudioDevice] = useState<string>('');
  const [isLoadingDevices, setIsLoadingDevices] = useState<boolean>(false);
  const [deviceError, setDeviceError] = useState<string | null>(null);

  const [platform, setPlatform] = useState<'zoom' | 'googlemeet' | 'msteams'>('googlemeet');
  const [meetingIdentifier, setMeetingIdentifier] = useState<string>('');
  const [notionNoteTitle, setNotionNoteTitle] = useState<string>('');

  // TODO: Securely manage API keys. For now, placeholders or direct input.
  const [notionApiKey, setNotionApiKey] = useState<string>('');
  const [deepgramApiKey, setDeepgramApiKey] = useState<string>('');
  const [openaiApiKey, setOpenaiApiKey] = useState<string>('');
  const [zoomSdkKey, setZoomSdkKey] = useState<string>(''); // Only if platform is Zoom & SDK agent
  const [zoomSdkSecret, setZoomSdkSecret] = useState<string>(''); // Only if platform is Zoom & SDK agent


  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [currentTask, setCurrentTask] = useState<TaskStatus | null>(null);
  const [pollingIntervalId, setPollingIntervalId] = useState<NodeJS.Timeout | null>(null);

  const { userId } = useSession(); // Get SuperTokens user ID

  const fetchAudioDevices = useCallback(async () => {
    setIsLoadingDevices(true);
    setDeviceError(null);
    try {
      const response = await fetch(`${LIVE_MEETING_WORKER_URL}/list_audio_devices`);
      if (!response.ok) {
        throw new Error(`Failed to fetch audio devices: ${response.statusText} (Worker might be down or URL incorrect)`);
      }
      const data: AudioDevice[] = await response.json();
      // Filter out devices with 0 input channels as they can't be used for input
      const usableDevices = data.filter(device => device.max_input_channels > 0);
      setAudioDevices(usableDevices);
      if (usableDevices.length > 0) {
        setSelectedAudioDevice(String(usableDevices[0].index)); // Default to first usable device
      } else {
        setDeviceError("No usable audio input devices found. Please check your system's audio configuration and the live meeting worker.");
      }
    } catch (error: any) {
      console.error("Error fetching audio devices:", error);
      setDeviceError(error.message || "Could not connect to the live meeting worker to get audio devices.");
      setAudioDevices([]);
    }
    setIsLoadingDevices(false);
  }, []);

  useEffect(() => {
    fetchAudioDevices(); // Fetch on component mount
  }, [fetchAudioDevices]);

  const handleAttendMeeting = async () => {
    if (!userId) {
      setSubmitError("User not authenticated. Please log in.");
      return;
    }
    if (!meetingIdentifier || !notionNoteTitle) {
      setSubmitError("Meeting ID/URL and Notion Note Title are required.");
      return;
    }
    if (audioDevices.length > 0 && !selectedAudioDevice && platform !== 'zoom') { // Zoom SDK agent ignores this
        setSubmitError("Please select an audio device.");
        return;
    }
    // Basic API key check (presence)
    if (!notionApiKey || !deepgramApiKey || !openaiApiKey) {
        setSubmitError("Notion, Deepgram, and OpenAI API keys are required.");
        return;
    }
    if (platform === 'zoom' && (!zoomSdkKey || !zoomSdkSecret)) {
        // This check should be conditional based on whether USE_NEW_ZOOM_SDK_AGENT is true on the worker.
        // For now, assume they are needed if platform is zoom.
        console.warn("Zoom SDK Key/Secret might be required if using the NewZoomSDKAgent.");
        // setSubmitError("Zoom SDK Key and Secret are required for Zoom meetings with the SDK agent.");
        // return;
    }


    setIsSubmitting(true);
    setSubmitError(null);
    setCurrentTask(null);
    if (pollingIntervalId) clearInterval(pollingIntervalId);

    const payload = {
      platform,
      meeting_identifier: meetingIdentifier,
      notion_note_title: notionNoteTitle,
      handler_input: {
        notion_api_token: notionApiKey,
        deepgram_api_key: deepgramApiKey,
        openai_api_key: openaiApiKey,
        ...(platform === 'zoom' && zoomSdkKey && zoomSdkSecret && { // Conditionally add Zoom SDK keys
            zoom_sdk_key: zoomSdkKey,
            zoom_sdk_secret: zoomSdkSecret,
        }),
        audio_settings: {
          // Only include audio_device_specifier if it's selected and not using Zoom SDK (implicitly)
          // The NewZoomSDKAgent ignores this, other agents use it.
          audio_device_specifier: selectedAudioDevice || undefined
        },
        user_id: userId,
      }
    };

    try {
      const response = await fetch(ATTEND_LIVE_MEETING_API_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ message: response.statusText }));
        throw new Error(errorData.message || `Failed to initiate meeting attendance: ${response.statusText}`);
      }

      const result = await response.json();
      if (result.taskId) {
        setCurrentTask({
            task_id: result.taskId,
            current_status_message: "Task initiated. Waiting for status...",
            platform,
            meeting_identifier: meetingIdentifier,
            user_id: userId,
            status_timestamp: new Date().toISOString(),
            created_at: new Date().toISOString()
        });
        // Start polling for status
        const intervalId = setInterval(() => pollTaskStatus(result.taskId), 5000);
        setPollingIntervalId(intervalId);
      } else {
        throw new Error("Task ID not received from initiation response.");
      }
    } catch (error: any) {
      console.error("Error initiating meeting attendance:", error);
      setSubmitError(error.message || "An unknown error occurred.");
    }
    setIsSubmitting(false);
  };

  const pollTaskStatus = async (taskId: string) => {
    try {
      const response = await fetch(`${MEETING_ATTENDANCE_STATUS_API_ENDPOINT_BASE}/${taskId}`);
      if (!response.ok) {
        // If 404, task might not exist or user doesn't have permission
        if (response.status === 404) {
            setSubmitError(`Task status not found (ID: ${taskId}). It might be an old task or an issue with the API.`);
            if (pollingIntervalId) clearInterval(pollingIntervalId);
            setPollingIntervalId(null);
            return;
        }
        const errorData = await response.json().catch(() => ({ message: response.statusText }));
        throw new Error(errorData.message || `Failed to fetch task status: ${response.statusText}`);
      }
      const statusData: TaskStatus = await response.json();
      setCurrentTask(statusData);

      if (statusData.final_notion_page_url || statusData.error_details) {
        if (pollingIntervalId) clearInterval(pollingIntervalId);
        setPollingIntervalId(null);
      }
    } catch (error: any) {
      console.error(`Error polling task status for ${taskId}:`, error);
      // Don't clear interval on transient network errors, but update UI
      setSubmitError(`Error fetching task status: ${error.message}. Polling may continue.`);
    }
  };

  // Clear interval on unmount
  useEffect(() => {
    return () => {
      if (pollingIntervalId) {
        clearInterval(pollingIntervalId);
      }
    };
  }, [pollingIntervalId]);

  const platformOptions = [
    { label: 'Google Meet', value: 'googlemeet' },
    { label: 'Zoom', value: 'zoom' },
    { label: 'Microsoft Teams', value: 'msteams' },
  ];

  const audioDeviceOptions = audioDevices.map(device => ({
    label: `${device.name} (Index: ${device.index}, API: ${device.hostapi_name}, Channels: ${device.max_input_channels})`,
    value: String(device.index), // Use index as value, or name if preferred by worker
  }));


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
        Live Meeting Attendance (Experimental)
      </Text>
      <Text variant="body" fontSize="sm" color="gray.600" marginBottom="m">
        Configure Atom to join online meetings, transcribe them, and save notes.
        Refer to the <a href="/docs/live-meeting-attendance-setup.md" target="_blank" rel="noopener noreferrer" style={{color: 'blue'}}>setup guide</a> for crucial audio configuration.
      </Text>

      <Box marginBottom="l">
        <Text variant="subHeader" marginBottom="s">Audio Device Selection</Text>
        <Button onPress={fetchAudioDevices} disabled={isLoadingDevices} marginBottom="s">
          {isLoadingDevices ? 'Refreshing Devices...' : 'Refresh Audio Devices'}
        </Button>
        {deviceError && <Text color="red.500" marginBottom="s">{deviceError}</Text>}
        {audioDevices.length > 0 && (
          <Select
            label="Select Audio Device (for meeting audio capture)"
            options={audioDeviceOptions}
            value={selectedAudioDevice}
            onChange={(value) => setSelectedAudioDevice(value as string)}
            placeholder="Select an audio device"
          />
        )}
        {audioDevices.length === 0 && !isLoadingDevices && !deviceError && (
            <Text>No audio devices found or loaded. Try refreshing.</Text>
        )}
        <Text variant="body" fontSize="xs" color="gray.500" marginTop="xs">
            The selected device should be a virtual audio output that captures the meeting's sound (not your microphone).
            Ignored if using the new Zoom SDK Agent.
        </Text>
      </Box>

      <Box marginBottom="l">
        <Text variant="subHeader" marginBottom="s">Meeting Details</Text>
        <Select
            label="Platform"
            options={platformOptions}
            value={platform}
            onChange={(value) => setPlatform(value as 'zoom' | 'googlemeet' | 'msteams')}
        />
        <TextField
          label="Meeting ID or Full URL"
          value={meetingIdentifier}
          onChange={(e) => setMeetingIdentifier(e.target.value)}
          placeholder="e.g., 1234567890 or https://meet.google.com/abc-def-ghi"
          marginTop="s"
        />
        <TextField
          label="Notion Note Title"
          value={notionNoteTitle}
          onChange={(e) => setNotionNoteTitle(e.target.value)}
          placeholder="e.g., Project Phoenix Sync - Oct 28"
          marginTop="s"
        />
      </Box>

      <Box marginBottom="l">
        <Text variant="subHeader" marginBottom="s">API Keys (Required)</Text>
         <Text variant="body" fontSize="xs" color="gray.500" marginBottom="s">
            Note: For production, these should be managed securely, not entered here directly.
        </Text>
        <TextField label="Notion API Token" type="password" value={notionApiKey} onChange={e => setNotionApiKey(e.target.value)} marginTop="s" />
        <TextField label="Deepgram API Key" type="password" value={deepgramApiKey} onChange={e => setDeepgramApiKey(e.target.value)} marginTop="s" />
        <TextField label="OpenAI API Key" type="password" value={openaiApiKey} onChange={e => setOpenaiApiKey(e.target.value)} marginTop="s" />
        {platform === 'zoom' && (
            <>
                <TextField label="Zoom SDK Key (if using New Zoom SDK Agent)" type="password" value={zoomSdkKey} onChange={e => setZoomSdkKey(e.target.value)} marginTop="s" />
                <TextField label="Zoom SDK Secret (if using New Zoom SDK Agent)" type="password" value={zoomSdkSecret} onChange={e => setZoomSdkSecret(e.target.value)} marginTop="s" />
            </>
        )}
      </Box>


      <Button onPress={handleAttendMeeting} disabled={isSubmitting || isLoadingDevices} variant="primary">
        {isSubmitting ? 'Initiating...' : 'Start Attending Meeting'}
      </Button>
      {submitError && <Text color="red.500" marginTop="s">{submitError}</Text>}

      {currentTask && (
        <Box marginTop="l" padding="m" borderWidth={1} borderColor="gray.300" borderRadius="s">
          <Text variant="subHeader" marginBottom="s">Task Status (ID: {currentTask.task_id})</Text>
          <Text>Status: {currentTask.current_status_message}</Text>
          <Text>Last Update: {new Date(currentTask.status_timestamp).toLocaleString()}</Text>
          {currentTask.final_notion_page_url && (
            <Text>Notion Page: <a href={currentTask.final_notion_page_url} target="_blank" rel="noopener noreferrer" style={{color: 'blue'}}>{currentTask.final_notion_page_url}</a></Text>
          )}
          {currentTask.error_details && (
            <Text color="red.500">Error: {currentTask.error_details}</Text>
          )}
        </Box>
      )}
    </Box>
  );
};

export default LiveMeetingAttendanceSettings;
