import { useState, useEffect } from 'react';
import { useTranscription } from './useTranscription';
import { invoke } from '@tauri-apps/api/tauri';
import { WebviewWindow } from '@tauri-apps/api/window';

function Chat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const { isTranscribing, transcript, setIsTranscribing } = useTranscription();

  const handleSend = async () => {
    if (input.trim() === '') return;

    const newMessages = [...messages, { text: input, sender: 'user' }];
    setMessages(newMessages);
    setInput('');
    setIsLoading(true);
    setError('');

    try {
      const response = await invoke('send_message_to_agent', { message: input, appHandle: window.__TAURI__.shell });
      setMessages([...newMessages, { text: response, sender: 'agent' }]);
      const utterance = new SpeechSynthesisUtterance(response as string);
      speechSynthesis.speak(utterance);
    } catch (err) {
      setError(err.toString());
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="chat-container">
      <div className="messages">
        {messages.map((message, index) => (
          <div key={index} className={`message ${message.sender}`}>
            {message.text}
          </div>
        ))}
        {isLoading && <div className="message agent">...</div>}
        {error && <div className="message agent error">{error}</div>}
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
          const task = window.prompt("Enter a browser task:");
          if (task) {
            setInput(`browser: ${task}`);
            handleSend();
          }
        }}>Browser</button>
        <button onClick={() => {
          const webview = new WebviewWindow('settings', {
            url: 'settings.html',
            title: 'Settings',
            width: 400,
            height: 400,
          });
        }}>Settings</button>
        <button onClick={() => {
          const webview = new WebviewWindow('project-health', {
            url: '/project-health',
            title: 'Project Health',
            width: 400,
            height: 400,
          });
        }}>Project Health</button>
        <button onClick={() => setIsTranscribing(!isTranscribing)}>
          {isTranscribing ? 'Stop Transcription' : 'Start Transcription'}
        </button>
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
