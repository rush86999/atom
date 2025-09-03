import React, { useState, useRef, useEffect, useCallback } from 'react';
import { useAgentAudioControl, AgentAudioCommand } from '../../contexts/AgentAudioControlContext'; // Adjusted path

// Placeholder Icons (replace with your actual icon components)
const MicIcon = () => <svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 0 24 24" width="24px" fill="#000000"><path d="M0 0h24v24H0z" fill="none"/><path d="M12 14c1.66 0 2.99-1.34 2.99-3L15 5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.3-3c0 3-2.54 5.1-5.3 5.1S6.7 14 6.7 11H5c0 3.41 2.72 6.23 6 6.72V21h2v-3.28c3.28-.48 6-3.3 6-6.72h-1.7z"/></svg>;
const StopIcon = () => <svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 0 24 24" width="24px" fill="#000000"><path d="M0 0h24v24H0z" fill="none"/><path d="M6 6h12v12H6z"/></svg>;
const CancelIcon = () => <svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 0 24 24" width="24px" fill="#000000"><path d="M0 0h24v24H0z" fill="none"/><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>;

interface AudioRecorderProps {
  userId: string;
  // linkedEventId is now primarily set via agent command payload or if component is used in a specific event context
  initialLinkedEventId?: string;
  initialSuggestedTitle?: string; // Renamed from suggestedTitle to initialSuggestedTitle for clarity
  onRecordingComplete: (notionPageUrl: string, title: string, summaryPreview?: string) => void;
  onRecordingError: (errorMessage: string) => void;
  // This component will now primarily be controlled by agent commands via context,
  // but can also be used standalone (user clicks record button).
}

type RecordingStatus = 'idle' | 'permissionPending' | 'recording' | 'stopped' | 'uploading' | 'error';

const PROCESS_AUDIO_NOTE_ENDPOINT = "/api/process-recorded-audio-note";

const AudioRecorder: React.FC<AudioRecorderProps> = ({
  userId,
  initialLinkedEventId,
  initialSuggestedTitle,
  onRecordingComplete,
  onRecordingError,
}) => {
  const [status, setStatus] = useState<RecordingStatus>('idle');
  const [noteTitle, setNoteTitle] = useState<string>(initialSuggestedTitle || '');
  const [currentLinkedEventId, setCurrentLinkedEventId] = useState<string | undefined>(initialLinkedEventId);
  const [elapsedTime, setElapsedTime] = useState<number>(0);
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined);
  const [audioBlob, setAudioBlob] = useState<Blob | undefined>(undefined);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const actualMimeTypeRef = useRef<string>('');

  // Consume Agent Audio Control Context
  const { latestCommand, clearLastCommand } = useAgentAudioControl();

  useEffect(() => {
    if (initialSuggestedTitle && status === 'idle') {
      setNoteTitle(initialSuggestedTitle);
    }
  }, [initialSuggestedTitle, status]);

  const formatTime = (timeInSeconds: number): string => {
    const minutes = Math.floor(timeInSeconds / 60).toString().padStart(2, '0');
    const seconds = (timeInSeconds % 60).toString().padStart(2, '0');
    return `${minutes}:${seconds}`;
  };

  const cleanupRecordingResources = useCallback((preserveTitleOnError = false) => {
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    if (mediaRecorderRef.current) {
        mediaRecorderRef.current.ondataavailable = null;
        mediaRecorderRef.current.onstop = null;
        mediaRecorderRef.current.onerror = null;
        if (mediaRecorderRef.current.state === 'recording') {
            try { mediaRecorderRef.current.stop(); } catch (e) { console.warn("Error stopping MediaRecorder during cleanup:", e); }
        }
    }
    mediaRecorderRef.current = null;
    audioChunksRef.current = [];
    if (!preserveTitleOnError) { // Only reset title if not preserving on error
        setNoteTitle(initialSuggestedTitle || ''); // Reset to initial or empty
    }
  }, [initialSuggestedTitle]);


  useEffect(() => {
    return () => {
      cleanupRecordingResources();
    };
  }, [cleanupRecordingResources]);

  // Abstracted start recording logic to be callable by user action or agent command
  const startRecordingSession = useCallback(async (titleFromCommand?: string, eventIdFromCommand?: string) => {
    if (status !== 'idle' && status !== 'error') {
        console.warn("Recording session cannot start, current status:", status);
        return; // Don't start if already busy, unless it's an error state we want to override
    }
    setStatus('permissionPending');
    setErrorMessage(undefined);
    setAudioBlob(undefined);
    audioChunksRef.current = [];
    if (titleFromCommand) setNoteTitle(titleFromCommand);
    if (eventIdFromCommand) setCurrentLinkedEventId(eventIdFromCommand);


    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      const errorMsg = "Microphone access is not supported by your browser.";
      setErrorMessage(errorMsg);
      setStatus('error');
      onRecordingError(errorMsg);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const options = { mimeType: 'audio/webm;codecs=opus' };
      if (MediaRecorder.isTypeSupported(options.mimeType)) {
        actualMimeTypeRef.current = options.mimeType;
      } else if (MediaRecorder.isTypeSupported('audio/wav')) {
        actualMimeTypeRef.current = 'audio/wav';
      } else {
        actualMimeTypeRef.current = '';
      }
      console.log("Using MIME type:", actualMimeTypeRef.current);

      const recorder = new MediaRecorder(stream, actualMimeTypeRef.current ? { mimeType: actualMimeTypeRef.current } : undefined);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = () => {
        const completeBlob = new Blob(audioChunksRef.current, { type: actualMimeTypeRef.current || audioChunksRef.current[0]?.type || 'application/octet-stream' });
        setAudioBlob(completeBlob);
        setStatus('stopped'); // This will trigger the useEffect for upload
        // Cleanup is now part of the onstop logic before setting status to 'stopped' or handled by it.
        // No, cleanup should happen *after* blob is formed and set, or when explicitly cancelled.
        // Let's ensure cleanup happens after blob is processed or on cancel.
        // The timer and stream tracks are stopped here.
        if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
        if (streamRef.current) streamRef.current.getTracks().forEach(track => track.stop());

      };

      recorder.onerror = (event: Event) => {
        const errorEvent = event as any;
        const errorMsg = `MediaRecorder error: ${errorEvent.error?.name || 'Unknown error'}`;
        setErrorMessage(errorMsg);
        setStatus('error');
        onRecordingError(errorMsg);
        cleanupRecordingResources(true); // Preserve title on media recorder error
      };

      recorder.start();
      setStatus('recording');
      setElapsedTime(0);
      if (timerIntervalRef.current) clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = setInterval(() => {
        setElapsedTime(prevTime => prevTime + 1);
      }, 1000);

    } catch (err: any) {
      let errorMsg = "Failed to access microphone.";
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        errorMsg = "Microphone permission denied. Please enable microphone access in your browser settings.";
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        errorMsg = "No microphone found. Please ensure a microphone is connected and enabled.";
      } else {
        errorMsg = `Error accessing microphone: ${err.message || err.name}`;
      }
      setErrorMessage(errorMsg);
      setStatus('error');
      onRecordingError(errorMsg);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, onRecordingError]); // Removed cleanupRecordingResources from deps as it's stable

  // Abstracted stop recording logic
  const stopRecordingSession = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop(); // onstop handler will create blob and set status to 'stopped'
    } else {
        console.warn("Stop called but not in recording state or no mediaRecorder.");
    }
    // Timer is cleared in onstop or cancel
  }, []);

  // Abstracted cancel recording logic
  const cancelRecordingSession = useCallback(() => {
    cleanupRecordingResources();
    setAudioBlob(undefined);
    setElapsedTime(0);
    setStatus('idle');
    setNoteTitle(initialSuggestedTitle || '');
    setErrorMessage(undefined);
    setCurrentLinkedEventId(initialLinkedEventId);
  }, [cleanupRecordingResources, initialSuggestedTitle, initialLinkedEventId]);


  // Effect to handle commands from AgentAudioControlContext
  useEffect(() => {
    if (latestCommand) {
      console.log("AudioRecorder reacting to agent command:", latestCommand);
      const { action, payload } = latestCommand;
      switch (action) {
        case 'START_RECORDING_SESSION':
          // Optionally, ask user for confirmation before starting via agent.
          // For now, directly start.
          if (status === 'idle' || status === 'error') { // Only start if not already doing something
            setNoteTitle(payload?.suggestedTitle || initialSuggestedTitle || 'Agent Audio Note');
            setCurrentLinkedEventId(payload?.linkedEventId || initialLinkedEventId);
            startRecordingSession(payload?.suggestedTitle, payload?.linkedEventId);
          } else {
            console.warn(`Agent commanded START_RECORDING_SESSION but current status is ${status}. Ignoring.`);
            // TODO: Optionally send a NACK or BUSY status back to agent
          }
          break;
        case 'STOP_RECORDING_SESSION':
          if (status === 'recording') {
            stopRecordingSession();
          } else {
             console.warn(`Agent commanded STOP_RECORDING_SESSION but current status is ${status}. Ignoring.`);
          }
          break;
        case 'CANCEL_RECORDING_SESSION':
          if (status === 'recording' || status === 'permissionPending' || status === 'stopped') { // Can cancel even if stopped but not yet uploaded
            cancelRecordingSession();
          } else {
            console.warn(`Agent commanded CANCEL_RECORDING_SESSION but current status is ${status}. Ignoring.`);
          }
          break;
        default:
          console.warn("Received unknown agent audio command action:", action);
      }
      clearLastCommand(); // Consume the command
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [latestCommand, clearLastCommand, startRecordingSession, stopRecordingSession, cancelRecordingSession, status, initialSuggestedTitle, initialLinkedEventId]);


  const handleUploadAudio = useCallback(async () => {
    if (!audioBlob) { /* ... (rest of the upload logic remains largely the same) ... */
      const errorMsg = "No audio data available to upload.";
      setErrorMessage(errorMsg);
      setStatus('error');
      onRecordingError(errorMsg);
      return;
    }
    if (!userId) { /* ... */
      const errorMsg = "User ID is missing.";
      setErrorMessage(errorMsg);
      setStatus('error');
      onRecordingError(errorMsg);
      return;
    }

    setStatus('uploading');
    setErrorMessage(undefined);

    const formData = new FormData();
    const fileName = (noteTitle || 'audio_note').replace(/[^a-zA-Z0-9_-\s]/g, '_') + (actualMimeTypeRef.current.includes('wav') ? '.wav' : '.webm');
    formData.append('audio_file', audioBlob, fileName);
    formData.append('title', noteTitle || 'Audio Note - ' + new Date().toLocaleString());
    formData.append('user_id', userId);
    if (currentLinkedEventId) { // Use currentLinkedEventId from state
      formData.append('linked_event_id', currentLinkedEventId);
    }

    try {
      const response = await fetch(PROCESS_AUDIO_NOTE_ENDPOINT, {
        method: 'POST',
        body: formData,
      });
      const responseData = await response.json();

      if (response.ok && responseData.ok && responseData.data) {
        onRecordingComplete(responseData.data.notion_page_url, responseData.data.title, responseData.data.summary_preview);
        setStatus('idle');
        setNoteTitle(initialSuggestedTitle || '');
        setAudioBlob(undefined);
        setElapsedTime(0);
        setCurrentLinkedEventId(initialLinkedEventId);
      } else {
        const errorMsg = responseData.error?.message || responseData.message || `Failed to process audio note (HTTP ${response.status}).`;
        setErrorMessage(errorMsg);
        setStatus('error');
        onRecordingError(errorMsg);
      }
    } catch (err: any) {
      const errorMsg = `Network error or server unavailable: ${err.message || 'Unknown error'}`;
      setErrorMessage(errorMsg);
      setStatus('error');
      onRecordingError(errorMsg);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audioBlob, noteTitle, userId, currentLinkedEventId, onRecordingComplete, onRecordingError, initialSuggestedTitle, initialLinkedEventId]);

  useEffect(() => {
    if (status === 'stopped' && audioBlob) {
      handleUploadAudio();
    }
  }, [status, audioBlob, handleUploadAudio]);

  // --- UI Event Handlers (for manual button clicks) ---
  const handleManualStart = () => {
    // When user clicks the UI button, start with current title and eventId from props/state
    startRecordingSession(noteTitle || initialSuggestedTitle, currentLinkedEventId || initialLinkedEventId);
  };

  const handleManualStopAndSave = () => {
    stopRecordingSession();
  };

  const handleManualCancel = () => {
    cancelRecordingSession();
  };


  // Basic styling (inline for simplicity, should be moved to CSS/SCSS modules or styled-components)
  // ... (styles object remains the same) ...
  const styles = {
    container: { border: '1px solid #ccc', padding: '20px', borderRadius: '8px', maxWidth: '500px', margin: '20px auto', fontFamily: 'Arial, sans-serif' },
    titleInput: { width: 'calc(100% - 22px)', padding: '10px', marginBottom: '10px', border: '1px solid #ddd', borderRadius: '4px' },
    statusMessage: { margin: '10px 0', padding: '10px', borderRadius: '4px', backgroundColor: '#f0f0f0' },
    errorMessage: { backgroundColor: '#ffe0e0', color: '#d00000', border: '1px solid #d00000' },
    recordingIndicator: { display: 'flex', alignItems: 'center', margin: '10px 0' },
    dot: { height: '12px', width: '12px', borderRadius: '50%', marginRight: '8px', backgroundColor: 'grey' },
    recordingDot: { backgroundColor: 'red', animation: 'pulse 1.5s infinite' },
    timer: { marginLeft: 'auto', fontVariantNumeric: 'tabular-nums' as 'tabular-nums' },
    buttonsContainer: { display: 'flex', justifyContent: 'space-around', marginTop: '15px' },
    button: { padding: '10px 15px', border: 'none', borderRadius: '4px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px' },
    recordButton: { backgroundColor: '#4CAF50', color: 'white' },
    stopButton: { backgroundColor: '#f44336', color: 'white' },
    cancelButton: { backgroundColor: '#e0e0e0', color: 'black' },
  };

  return (
    <div style={styles.container}>
      <h3>In-Person Audio Note</h3>
      {(status === 'idle' || status === 'recording' || status === 'error') && (
        <input
          type="text"
          style={styles.titleInput}
          value={noteTitle}
          onChange={(e) => setNoteTitle(e.target.value)}
          placeholder="Optional title for your audio note"
          disabled={status === 'recording' || status === 'uploading' || status === 'permissionPending'}
        />
      )}

      {status === 'permissionPending' && <p style={styles.statusMessage}>Requesting microphone permission...</p>}
      {status === 'uploading' && <p style={styles.statusMessage}>Processing and saving your note...</p>}
      {errorMessage && status === 'error' && <p style={{...styles.statusMessage, ...styles.errorMessage}}>{errorMessage}</p>}

      {(status === 'recording') && (
        <div style={styles.recordingIndicator}>
          <span style={{...styles.dot, ...styles.recordingDot, animation: 'pulse 1.5s infinite'}}></span>
          <span>Recording</span>
          <span style={styles.timer}>{formatTime(elapsedTime)}</span>
        </div>
      )}

      <div style={styles.buttonsContainer}>
        {(status === 'idle' || status === 'error') && ( // User can manually start if idle or after an error
          <button style={{...styles.button, ...styles.recordButton}} onClick={handleManualStart} disabled={status === 'permissionPending'}>
            <MicIcon /> Record
          </button>
        )}

        {status === 'recording' && ( // User can manually stop/cancel if they started it or if agent started it
          <>
            <button style={{...styles.button, ...styles.stopButton}} onClick={handleManualStopAndSave}>
              <StopIcon /> Stop & Save
            </button>
            <button style={{...styles.button, ...styles.cancelButton}} onClick={handleManualCancel}>
              <CancelIcon /> Cancel
            </button>
          </>
        )}
      </div>
    </div>
  );
};

export default AudioRecorder;

// Add keyframes for pulse animation in your global CSS or component-specific CSS solution:
/*
@keyframes pulse {
  0% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
  100% {
    opacity: 1;
  }
}
*/
