import { useState, useEffect } from 'react';
import { useTranscription } from './useTranscription';
import { invoke } from '@tauri-apps/api/tauri';
import { WebviewWindow } from '@tauri-apps/api/window';

function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const { isTranscribing, transcript } = useTranscription();

  const handleSend = async () => {
    if (input.trim() === '') return;

    const newMessages = [...messages, { text: input, sender: 'user' }];
    setMessages(newMessages);
    setInput('');

    const response = await invoke('send_message_to_agent', { message: input });
    setMessages([...newMessages, { text: response, sender: 'agent' }]);
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
          onKeyPress={(e) => e.key === 'Enter' && handleSend()}
        />
        <button onClick={handleSend}>Send</button>
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