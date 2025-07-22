import { useState, useEffect } from 'react';
import { listen } from '@tauri-apps/api/event';
import { useTranscription } from './useTranscription';

function App() {
  const [isAgentActive, setIsAgentActive] = useState(false);
  const { isTranscribing, transcript } = useTranscription();

  useEffect(() => {
    const unlisten = listen('wake-word-detected', () => {
      setIsAgentActive(true);
    });

    return () => {
      unlisten.then(f => f());
    };
  }, []);

  return (
    <div className="App">
      {isAgentActive ? (
        <div>Agent is active</div>
      ) : (
        <div>Waiting for wake word...</div>
      )}
      {isTranscribing && (
        <div>
          <h2>Live Transcription</h2>
          <p>{transcript}</p>
        </div>
      )}
    </div>
  );
}

export default App;