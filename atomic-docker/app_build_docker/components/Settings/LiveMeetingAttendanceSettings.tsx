import React, { useState, useEffect, useCallback } from 'react';
import Box from '@components/common/Box';
import Text from '@components/common/Text';
import Button from '@components/Button';
import Select from '@components/common/Select';
import TextField from '@components/TextField';
import { useSession } from 'supertokens-auth-react/recipe/session';

// Matches backend AudioDevice model
interface AudioDevice {
  id: string | number; // Can be string or number from backend
  name: string;
}

// Matches backend TaskStatus enum
enum TaskStatusEnum {
  PENDING = "pending",
  ACTIVE = "active",
  PROCESSING_COMPLETION = "processing_completion",
  COMPLETED = "completed",
  ERROR = "error",
}

// Matches backend MeetingTask model (relevant parts for frontend)
interface MeetingTask {
  task_id: string;
  user_id: string;
  platform: string;
  meeting_id: string; // Renamed from meeting_identifier for consistency
  audio_device_id: string | number;
  notion_page_title: string;
  status: TaskStatusEnum;
  message?: string | null;
  start_time?: string | null; // ISO date string
  end_time?: string | null; // ISO date string
  duration_seconds?: number | null;
  transcript_preview?: string | null;
  notes_preview?: string | null;
  final_transcript_location?: string | null;
  final_notes_location?: string | null;
}

const LIVE_MEETING_WORKER_URL = process.env.NEXT_PUBLIC_LIVE_MEETING_WORKER_URL || 'http://localhost:8001'; // Default to Python worker port

const LiveMeetingAttendanceSettings = () => {
  const [audioDevices, setAudioDevices] = useState<AudioDevice[]>([]);
  const [selectedAudioDevice, setSelectedAudioDevice] = useState<string | number>('');
  const [isLoadingDevices, setIsLoadingDevices] = useState<boolean>(false);
  const [deviceError, setDeviceError] = useState<string | null>(null);

  const [platform, setPlatform] = useState<'zoom' | 'googlemeet' | 'msteams' | 'other'>('googlemeet');
  const [meetingId, setMeetingId] = useState<string>(''); // Renamed from meetingIdentifier
  const [notionPageTitle, setNotionPageTitle] = useState<string>(''); // Renamed from notionNoteTitle

  const [isProcessing, setIsProcessing] = useState<boolean>(false); // General processing state for start/stop
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [currentTask, setCurrentTask] = useState<MeetingTask | null>(null);
  const [pollingIntervalId, setPollingIntervalId] = useState<NodeJS.Timeout | null>(null);

  const { userId, isLoading: isLoadingSession } = useSession();

  const fetchAudioDevices = useCallback(async () => {
    setIsLoadingDevices(true);
    setDeviceError(null);
    try {
      const response = await fetch(`${LIVE_MEETING_WORKER_URL}/list_audio_devices`);
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to fetch audio devices: ${response.statusText} (Worker might be down or URL incorrect)`);
      }
      const data: { devices: AudioDevice[] } = await response.json();
      setAudioDevices(data.devices || []);
      if (data.devices && data.devices.length > 0) {
        setSelectedAudioDevice(data.devices[0].id); // Default to first device's ID
      } else {
        setDeviceError("No audio input devices found. Please check your system's audio configuration and the live meeting worker.");
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

  const clearPolling = () => {
    if (pollingIntervalId) {
      clearInterval(pollingIntervalId);
      setPollingIntervalId(null);
    }
  };

  const handleStartMeeting = async () => {
    if (!userId) {
      setSubmitError("User not authenticated. Please log in.");
      return;
    }
    if (!meetingId || !notionPageTitle) {
      setSubmitError("Meeting ID/URL and Notion Page Title are required.");
      return;
    }
    if (audioDevices.length > 0 && !selectedAudioDevice) {
        setSubmitError("Please select an audio device.");
        return;
    }
    if (!selectedAudioDevice && audioDevices.length === 0 && !deviceError) {
        setSubmitError("No audio devices available. Cannot start meeting.");
        return;
    }


    setIsProcessing(true);
    setSubmitError(null);
    setCurrentTask(null);
    clearPolling();

    const payload = {
      platform,
      meeting_id: meetingId,
      audio_device_id: selectedAudioDevice,
      notion_page_title: notionPageTitle,
      user_id: userId,
    };

    try {
      const response = await fetch(`${LIVE_MEETING_WORKER_URL}/start_meeting_attendance`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.detail || result.message || `Failed to initiate meeting attendance: ${response.statusText}`);
      }

      // result should be StartMeetingResponse { task_id, status, message }
      // but we want to store the full MeetingTask structure eventually, so we synthesize it or fetch immediately
      setCurrentTask(prev => ({ // Optimistically set basic task info
        ...(prev as MeetingTask), // Keep any old data if needed, though usually it's a new task
        task_id: result.task_id,
        status: result.status as TaskStatusEnum,
        message: result.message || "Task initiated. Waiting for detailed status...",
        platform,
        meeting_id: meetingId,
        audio_device_id: selectedAudioDevice,
        notion_page_title: notionPageTitle,
        user_id: userId,
      }));

      // Start polling for status
      const intervalId = setInterval(() => pollTaskStatus(result.task_id), 5000);
      setPollingIntervalId(intervalId);
      pollTaskStatus(result.task_id); // Initial poll immediately

    } catch (error: any) {
      console.error("Error initiating meeting attendance:", error);
      setSubmitError(error.message || "An unknown error occurred while starting.");
      setCurrentTask(null); // Clear task on error
    }
    setIsProcessing(false);
  };

  const pollTaskStatus = async (taskId: string) => {
    try {
      const response = await fetch(`${LIVE_MEETING_WORKER_URL}/meeting_attendance_status/${taskId}`);
      if (!response.ok) {
        if (response.status === 404) {
            setSubmitError(`Task status not found (ID: ${taskId}). It might have been cleared or is an old ID.`);
            clearPolling();
            setCurrentTask(null); // Task is gone
            return;
        }
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Failed to fetch task status: ${response.statusText}`);
      }
      const statusData: MeetingTask = await response.json();
      setCurrentTask(statusData);

      // Stop polling if task is in a terminal state
      if (statusData.status === TaskStatusEnum.COMPLETED || statusData.status === TaskStatusEnum.ERROR) {
        clearPolling();
      }
    } catch (error: any) {
      console.error(`Error polling task status for ${taskId}:`, error);
      setSubmitError(`Error fetching task status: ${error.message}. Polling may be affected.`);
      // Potentially stop polling on repeated errors or specific error types
    }
  };

  const handleStopMeeting = async () => {
    if (!currentTask || !currentTask.task_id) {
      setSubmitError("No active task to stop.");
      return;
    }
    if (currentTask.status === TaskStatusEnum.COMPLETED || currentTask.status === TaskStatusEnum.ERROR) {
      setSubmitError("Task is already in a terminal state.");
      return;
    }

    setIsProcessing(true);
    setSubmitError(null);
    clearPolling(); // Stop regular polling as we are sending a stop command

    try {
      const response = await fetch(`${LIVE_MEETING_WORKER_URL}/stop_meeting_attendance/${currentTask.task_id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });

      const result: MeetingTask = await response.json(); // Expects updated task details

      if (!response.ok) {
         throw new Error(result.message || (result as any).detail || `Failed to stop meeting: ${response.statusText}`);
      }

      setCurrentTask(result); // Update with final status from stop response
      if (result.status !== TaskStatusEnum.COMPLETED && result.status !== TaskStatusEnum.ERROR) {
        // If not yet terminal, poll once more or restart polling briefly
        const intervalId = setInterval(() => pollTaskStatus(result.task_id), 3000);
        setPollingIntervalId(intervalId);
      }

    } catch (error: any) {
      console.error("Error stopping meeting attendance:", error);
      setSubmitError(error.message || "An unknown error occurred while stopping.");
      // Optionally, restart polling if stop command failed, to get latest status
      if (currentTask && currentTask.task_id && !pollingIntervalId) {
        const intervalId = setInterval(() => pollTaskStatus(currentTask.task_id), 5000);
        setPollingIntervalId(intervalId);
      }
    }
    setIsProcessing(false);
  };


  // Clear interval on unmount
  useEffect(() => {
    return () => {
      clearPolling();
    };
  }, [pollingIntervalId]); // Dependency array ensures cleanup if pollingIntervalId changes, but clearPolling handles its own state.

  const platformOptions = [
    { label: 'Google Meet', value: 'googlemeet' },
    { label: 'Zoom', value: 'zoom' },
    { label: 'Microsoft Teams', value: 'msteams' },
    { label: 'Other/Desktop Audio', value: 'other' },
  ];

  const audioDeviceOptions = audioDevices.map(device => ({
    label: `${device.name} (ID: ${device.id})`,
    value: device.id,
  }));

  const isTaskActiveOrPending = currentTask &&
    (currentTask.status === TaskStatusEnum.ACTIVE ||
     currentTask.status === TaskStatusEnum.PENDING ||
     currentTask.status === TaskStatusEnum.PROCESSING_COMPLETION);


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
        Live Meeting Attendance
      </Text>
      <Text variant="body" fontSize="sm" color="gray.600" marginBottom="m">
        Configure Atom to capture audio from online meetings or desktop, (eventually) transcribe, and generate notes.
        Refer to the <a href="/docs/live-meeting-attendance-setup.md" target="_blank" rel="noopener noreferrer" style={{color: 'blue'}}>setup guide</a> for audio configuration.
      </Text>

      <Box marginBottom="l">
        <Text variant="subHeader" marginBottom="s">Audio Device Selection</Text>
        <Button onPress={fetchAudioDevices} disabled={isLoadingDevices || isProcessing} marginBottom="s">
          {isLoadingDevices ? 'Refreshing Devices...' : 'Refresh Audio Devices'}
        </Button>
        {deviceError && <Text color="red.500" marginBottom="s" fontSize="sm">{deviceError}</Text>}
        {audioDevices.length > 0 && (
          <Select
            label="Select Audio Device (for meeting/desktop audio capture)"
            options={audioDeviceOptions}
            value={selectedAudioDevice}
            onChange={(value) => setSelectedAudioDevice(value as string | number)}
            placeholder="Select an audio device"
            disabled={isProcessing || isTaskActiveOrPending}
          />
        )}
        {audioDevices.length === 0 && !isLoadingDevices && !deviceError && (
            <Text fontSize="sm">No audio devices found or loaded. Try refreshing, or check worker logs.</Text>
        )}
        <Text variant="body" fontSize="xs" color="gray.500" marginTop="xs">
            The selected device should ideally be a virtual audio output/loopback that captures the meeting's sound (not your microphone, unless intended).
        </Text>
      </Box>

      <Box marginBottom="l">
        <Text variant="subHeader" marginBottom="s">Meeting Details</Text>
        <Select
            label="Platform"
            options={platformOptions}
            value={platform}
            onChange={(value) => setPlatform(value as 'zoom' | 'googlemeet' | 'msteams' | 'other')}
            disabled={isProcessing || isTaskActiveOrPending}
        />
        <TextField
          label="Meeting ID or Description"
          value={meetingId}
          onChange={(e) => setMeetingId(e.target.value)}
          placeholder="e.g., https://meet.google.com/abc-def-ghi or 'Client Call'"
          marginTop="s"
          disabled={isProcessing || isTaskActiveOrPending}
        />
        <TextField
          label="Notion Page Title (for Notes)"
          value={notionPageTitle}
          onChange={(e) => setNotionPageTitle(e.target.value)}
          placeholder="e.g., Project Phoenix Sync - Oct 28"
          marginTop="s"
          disabled={isProcessing || isTaskActiveOrPending}
        />
      </Box>

      {/* API Key inputs removed as they are not part of the new worker API contract */}

      <Box flexDirection="row" justifyContent="space-between">
        <Button
            onPress={handleStartMeeting}
            disabled={isProcessing || isLoadingDevices || isLoadingSession || isTaskActiveOrPending || (!selectedAudioDevice && audioDevices.length > 0)}
            variant="primary"
        >
          {isProcessing && currentTask?.status !== TaskStatusEnum.ACTIVE ? 'Starting...' : 'Start Attending Meeting'}
        </Button>
        {isTaskActiveOrPending && (
            <Button onPress={handleStopMeeting} disabled={isProcessing} variant="warning" marginLeft="m">
             {isProcessing && currentTask?.status === TaskStatusEnum.ACTIVE ? 'Stopping...' : 'Stop Attending Meeting'}
            </Button>
        )}
      </Box>
      {submitError && <Text color="red.500" marginTop="s" fontSize="sm">{submitError}</Text>}
      {isLoadingSession && <Text color="orange.500" marginTop="s" fontSize="sm">Loading user session...</Text>}


      {currentTask && (
        <Box marginTop="l" padding="m" borderWidth={1} borderColor="gray.300" borderRadius="s">
          <Text variant="subHeader" marginBottom="s">Task Status (ID: {currentTask.task_id})</Text>
          <Text><strong>Status:</strong> {currentTask.status} {currentTask.message ? `(${currentTask.message})` : ''}</Text>
          {currentTask.start_time && <Text><strong>Started:</strong> {new Date(currentTask.start_time).toLocaleString()}</Text>}
          {currentTask.duration_seconds !== null && typeof currentTask.duration_seconds !== 'undefined' && (
            <Text><strong>Duration:</strong> {Math.round(currentTask.duration_seconds)}s</Text>
          )}
          {currentTask.transcript_preview && <Text><strong>Transcript Preview:</strong> {currentTask.transcript_preview}</Text>}
          {currentTask.notes_preview && <Text><strong>Notes Preview:</strong> {currentTask.notes_preview}</Text>}

          {currentTask.status === TaskStatusEnum.COMPLETED && (
            <>
              {currentTask.final_transcript_location && (
                <Text><strong>Final Transcript:</strong> {currentTask.final_transcript_location}</Text>
              )}
              {currentTask.final_notes_location && (
                <Text><strong>Final Notes:</strong> {currentTask.final_notes_location} (Note: Actual Notion page creation is a future step for the worker)</Text>
              )}
            </>
          )}
           {currentTask.status === TaskStatusEnum.ERROR && currentTask.message && (
            <Text color="red.500"><strong>Error Details:</strong> {currentTask.message}</Text>
          )}
        </Box>
      )}
    </Box>
  );
};

export default LiveMeetingAttendanceSettings;
