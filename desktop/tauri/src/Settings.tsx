import { useState, useEffect } from 'react';
import { readTextFile, writeTextFile } from '@tauri-apps/api/fs';
import './Settings.css';

function Settings() {
  const [sttService, setSttService] = useState('deepgram');
  const [sttApiKey, setSttApiKey] = useState('');
  const [ttsService, setTtsService] = useState('deepgram');
  const [ttsApiKey, setTtsApiKey] = useState('');
  const [integrations, setIntegrations] = useState({
    openai: '',
    google: '',
    notion: '',
    deepgram: '',
    zapier: '',
    hubspot: '',
    calendly: '',
    zoom: '',
    msteams: '',
    stripe: '',
    quickbooks: '',
    asana: '',
    jira: '',
    trello: '',
  });

  useEffect(() => {
    readTextFile('settings.json', { dir: 16 }).then((contents) => {
      const settings = JSON.parse(contents);
      setSttService(settings.stt.service);
      setSttApiKey(settings.stt.apiKey);
      setTtsService(settings.tts.service);
      setTtsApiKey(settings.tts.apiKey);
      setIntegrations(settings.integrations);
    });
  }, []);

  const handleSave = () => {
    const settings = {
      stt: {
        service: sttService,
        apiKey: sttApiKey,
      },
      tts: {
        service: ttsService,
        apiKey: ttsApiKey,
      },
      integrations,
    };
    writeTextFile('settings.json', JSON.stringify(settings), { dir: 16 });
  };

  const handleIntegrationChange = (e) => {
    setIntegrations({
      ...integrations,
      [e.target.name]: e.target.value,
    });
  };

  return (
    <div className="settings-container">
      <h2>Settings</h2>
      <div className="setting">
        <label>STT Service</label>
        <select value={sttService} onChange={(e) => setSttService(e.target.value)}>
          <option value="deepgram">Deepgram</option>
          <option value="other">Other</option>
        </select>
      </div>
      <div className="setting">
        <label>STT API Key</label>
        <input
          type="text"
          value={sttApiKey}
          onChange={(e) => setSttApiKey(e.target.value)}
        />
      </div>
      <div className="setting">
        <label>TTS Service</label>
        <select value={ttsService} onChange={(e) => setTtsService(e.target.value)}>
          <option value="deepgram">Deepgram</option>
          <option value="other">Other</option>
        </select>
      </div>
      <div className="setting">
        <label>TTS API Key</label>
        <input
          type="text"
          value={ttsApiKey}
          onChange={(e) => setTtsApiKey(e.target.value)}
        />
      </div>
      <h2>Integrations</h2>
      {Object.keys(integrations).map((key) => (
        <div className="setting" key={key}>
          <label>{key}</label>
          <input
            type="text"
            name={key}
            value={integrations[key]}
            onChange={handleIntegrationChange}
          />
        </div>
      ))}
      <button onClick={handleSave}>Save</button>
    </div>
  );
}

export default Settings;
