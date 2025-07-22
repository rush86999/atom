import { useState, useEffect } from 'react';
import { useTranscription } from './useTranscription';

function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const { isTranscribing, transcript } = useTranscription();

  const handleSend = () => {
    // TODO: Send message to agent
  };

  return (
    <div className="chat-container">
      <div className="messages">
        {messages.map((message, index) => (
          <div key={index} className={`message ${message.sender}`}>
            {message.text}
          </div>
        ))}
      </div>
      <div className="input-container">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <button onClick={handleSend}>Send</button>
        import { WebviewWindow } from '@tauri-apps/api/window';

// ...

        <button onClick={() => {
          const webview = new WebviewWindow('settings', {
            url: 'settings.html',
            title: 'Settings',
            width: 400,
            height: 400,
          });
        }}>Settings</button>
      </div>
      {isTranscribing && (
        <div className="transcription">
          <p>{transcript}</p>
        </div>
      )}
    </div>
  );
}

export default Chat;
