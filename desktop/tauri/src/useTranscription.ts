import { useState, useEffect, useRef } from 'react';
import { listen } from '@tauri-apps/api/event';

export function useTranscription() {
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [transcript, setTranscript] = useState('');
  const socketRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);

  useEffect(() => {
    const unlisten = listen('start-transcription', () => {
      setIsTranscribing(true);
    });

    return () => {
      unlisten.then(f => f());
    };
  }, []);

  useEffect(() => {
    if (isTranscribing) {
      navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
        const mediaRecorder = new MediaRecorder(stream);
        mediaRecorderRef.current = mediaRecorder;

        const socket = new WebSocket('ws://localhost:8001/ws/transcribe');
        socketRef.current = socket;

        socket.onopen = () => {
          mediaRecorder.addEventListener('dataavailable', (event) => {
            if (event.data.size > 0 && socket.readyState === WebSocket.OPEN) {
              socket.send(event.data);
            }
          });
          mediaRecorder.start(250);
        };

        socket.onmessage = (event) => {
          setTranscript(event.data);
        };

        socket.onclose = () => {
          mediaRecorder.stop();
        };
      });
    } else {
      if (socketRef.current) {
        socketRef.current.close();
      }
      if (mediaRecorderRef.current) {
        mediaRecorderRef.current.stop();
      }
    }
  }, [isTranscribing]);

  return { isTranscribing, transcript };
}