import { useState, useEffect } from 'react';
import { listen } from '@tauri-apps/api/event';

export function useTranscription() {
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [transcript, setTranscript] = useState('');

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
      // TODO: Connect to the live_meeting_worker and start transcription
    }
  }, [isTranscribing]);

  return { isTranscribing, transcript };
}
