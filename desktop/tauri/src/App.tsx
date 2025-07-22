import { useState, useEffect } from 'react';
import { listen } from '@tauri-apps/api/event';

function App() {
  const [isAgentActive, setIsAgentActive] = useState(false);

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
    </div>
  );
}

export default App;
