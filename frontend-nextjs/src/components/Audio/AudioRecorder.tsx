atom / frontend - nextjs / src / components / Audio / AudioRecorder.tsx;
import React, { useState, useEffect, useRef, useCallback } from "react";
import { useAudioControl } from "../../contexts/AudioControlContext";

interface AudioRecorderProps {
  onRecordingComplete?: (audioBlob: Blob, audioUrl: string) => void;
  onError?: (error: string) => void;
  maxRecordingTime?: number; // in seconds
  mimeType?: string;
}

const AudioRecorder: React.FC<AudioRecorderProps> = ({
  onRecordingComplete,
  onError,
  maxRecordingTime = 300, // 5 minutes default
  mimeType = "audio/webm;codecs=opus",
}) => {
  const { state, dispatch } = useAudioControl();
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(
    null,
  );
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [permissionDenied, setPermissionDenied] = useState(false);
  const recordingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (recordingIntervalRef.current) {
        clearInterval(recordingIntervalRef.current);
      }
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
      }
    };
  }, [stream]);

  const startRecording = useCallback(async () => {
    try {
      setPermissionDenied(false);
      audioChunksRef.current = [];

      const audioStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000,
          channelCount: 1,
        },
      });

      setStream(audioStream);

      const recorder = new MediaRecorder(audioStream, { mimeType });
      setMediaRecorder(recorder);

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        const audioUrl = URL.createObjectURL(audioBlob);

        dispatch({ type: "SET_AUDIO_BLOB", payload: audioBlob });
        dispatch({ type: "SET_AUDIO_URL", payload: audioUrl });

        if (onRecordingComplete) {
          onRecordingComplete(audioBlob, audioUrl);
        }

        // Clean up stream
        audioStream.getTracks().forEach((track) => track.stop());
        setStream(null);
      };

      recorder.start();
      dispatch({ type: "START_RECORDING" });

      // Start recording timer
      let recordingTime = 0;
      recordingIntervalRef.current = setInterval(() => {
        recordingTime += 1;
        dispatch({ type: "SET_RECORDING_TIME", payload: recordingTime });

        if (recordingTime >= maxRecordingTime) {
          stopRecording();
        }
      }, 1000);
    } catch (error) {
      console.error("Error starting recording:", error);
      setPermissionDenied(true);
      if (onError) {
        onError("Microphone permission denied or audio device unavailable");
      }
    }
  }, [dispatch, mimeType, maxRecordingTime, onRecordingComplete, onError]);

  const stopRecording = useCallback(() => {
    if (mediaRecorder && state.isRecording) {
      mediaRecorder.stop();
      dispatch({ type: "STOP_RECORDING" });

      if (recordingIntervalRef.current) {
        clearInterval(recordingIntervalRef.current);
        recordingIntervalRef.current = null;
      }
    }
  }, [mediaRecorder, state.isRecording, dispatch]);

  const resetRecording = useCallback(() => {
    stopRecording();
    dispatch({ type: "RESET" });
    audioChunksRef.current = [];
  }, [stopRecording, dispatch]);

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  const uploadAudioToServer = async (audioBlob: Blob, metadata: any = {}) => {
    try {
      dispatch({ type: "SET_PROCESSING", payload: true });

      const formData = new FormData();
      formData.append("audio", audioBlob, "recording.webm");
      formData.append("metadata", JSON.stringify(metadata));

      const response = await fetch("/api/process-recorded-audio-note", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      const result = await response.json();
      return result;
    } catch (error) {
      console.error("Error uploading audio:", error);
      if (onError) {
        onError("Failed to upload audio to server");
      }
      throw error;
    } finally {
      dispatch({ type: "SET_PROCESSING", payload: false });
    }
  };

  return (
    <div className="audio-recorder">
      <div className="recording-controls">
        {!state.isRecording ? (
          <button
            onClick={startRecording}
            disabled={state.isProcessing || permissionDenied}
            className="record-button"
          >
            {permissionDenied ? "Microphone Blocked" : "Start Recording"}
          </button>
        ) : (
          <button onClick={stopRecording} className="stop-button">
            Stop Recording
          </button>
        )}

        {state.audioUrl && (
          <button onClick={resetRecording} className="reset-button">
            Reset
          </button>
        )}
      </div>

      {state.isRecording && (
        <div className="recording-status">
          <div className="recording-indicator">
            <span className="recording-dot"></span>
            Recording...
          </div>
          <div className="recording-time">
            {formatTime(state.recordingTime)}
          </div>
        </div>
      )}

      {state.error && <div className="error-message">{state.error}</div>}

      {state.audioUrl && !state.isProcessing && (
        <div className="audio-preview">
          <audio controls src={state.audioUrl} />
          <button
            onClick={() => uploadAudioToServer(state.audioBlob!)}
            className="upload-button"
          >
            Process Audio
          </button>
        </div>
      )}

      {state.isProcessing && (
        <div className="processing-status">Processing audio...</div>
      )}

      <style jsx>{`
        .audio-recorder {
          padding: 1rem;
          border: 1px solid #e1e5e9;
          border-radius: 8px;
          background: #f8f9fa;
        }

        .recording-controls {
          display: flex;
          gap: 0.5rem;
          margin-bottom: 1rem;
        }

        button {
          padding: 0.5rem 1rem;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-size: 14px;
          transition: background-color 0.2s;
        }

        .record-button {
          background-color: #dc3545;
          color: white;
        }

        .record-button:hover:not(:disabled) {
          background-color: #c82333;
        }

        .record-button:disabled {
          background-color: #6c757d;
          cursor: not-allowed;
        }

        .stop-button {
          background-color: #28a745;
          color: white;
        }

        .stop-button:hover {
          background-color: #218838;
        }

        .reset-button,
        .upload-button {
          background-color: #6c757d;
          color: white;
        }

        .reset-button:hover,
        .upload-button:hover {
          background-color: #5a6268;
        }

        .recording-status {
          display: flex;
          align-items: center;
          gap: 1rem;
          margin-bottom: 1rem;
        }

        .recording-indicator {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          color: #dc3545;
          font-weight: 500;
        }

        .recording-dot {
          width: 8px;
          height: 8px;
          background-color: #dc3545;
          border-radius: 50%;
          animation: blink 1s infinite;
        }

        @keyframes blink {
          0%,
          50% {
            opacity: 1;
          }
          51%,
          100% {
            opacity: 0.3;
          }
        }

        .recording-time {
          font-family: monospace;
          font-size: 16px;
          color: #495057;
        }

        .error-message {
          color: #dc3545;
          margin: 0.5rem 0;
          padding: 0.5rem;
          background-color: #f8d7da;
          border: 1px solid #f5c6cb;
          border-radius: 4px;
        }

        .audio-preview {
          margin-top: 1rem;
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .processing-status {
          color: #17a2b8;
          font-style: italic;
        }
      `}</style>
    </div>
  );
};

export default AudioRecorder;
