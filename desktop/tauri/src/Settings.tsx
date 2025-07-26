import React, { useState, useEffect } from 'react';
import { saveSetting, getSetting, getSettingStatus } from './lib/secure-storage';
import './Settings.css';

const Settings = () => {
  // State for each setting
  const [notionApiKey, setNotionApiKey] = useState('');
  const [notionDatabaseId, setNotionDatabaseId] = useState('');
  const [zapierUrl, setZapierUrl] = useState('');
  const [ttsProvider, setTtsProvider] = useState('elevenlabs');
  const [ttsApiKey, setTtsApiKey] = useState('');
  const [githubApiKey, setGithubApiKey] = useState('');
  const [githubOwner, setGithubOwner] = useState('');
  const [githubRepo, setGithubRepo] = useState('');
  const [slackChannelId, setSlackChannelId] = useState('');

  // UI feedback state
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  // Load settings on component mount
  useEffect(() => {
    const loadSettings = async () => {
      // Notion
      if (await getSettingStatus('notion_api_key')) {
        setNotionApiKey('********');
      }
      const savedNotionDbId = await getSetting('notion_tasks_database_id');
      setNotionDatabaseId(savedNotionDbId || '');
      // Zapier
      const savedZapierUrl = await getSetting('zapier_webhook_url');
      setZapierUrl(savedZapierUrl || '');
      // TTS Provider
      const savedTtsProvider = await getSetting('tts_provider');
      if (savedTtsProvider) {
        setTtsProvider(savedTtsProvider);
      }
      // TTS API Key (check based on the loaded provider)
      if (await getSettingStatus(`${savedTtsProvider || ttsProvider}_api_key`)) {
        setTtsApiKey('********');
      }
      // GitHub
      if (await getSettingStatus('github_api_key')) {
        setGithubApiKey('********');
      }
      const savedGithubOwner = await getSetting('github_owner');
      setGithubOwner(savedGithubOwner || '');
      const savedGithubRepo = await getSetting('github_repo');
      setGithubRepo(savedGithubRepo || '');
      const savedSlackChannelId = await getSetting('slack_channel_id');
      setSlackChannelId(savedSlackChannelId || '');
    };
    loadSettings();
  }, []);

  const handleSave = async () => {
    setMessage('');
    setError('');
    try {
      // Save Notion API Key (only if it's not masked)
      if (notionApiKey !== '********') {
        await saveSetting('notion_api_key', notionApiKey);
      }
      // Save Notion Database ID
      await saveSetting('notion_tasks_database_id', notionDatabaseId);
      // Save Zapier URL
      await saveSetting('zapier_webhook_url', zapierUrl);
      // Save TTS Provider
      await saveSetting('tts_provider', ttsProvider);
      // Save TTS API Key (only if it's not masked)
      if (ttsApiKey !== '********') {
        await saveSetting(`${ttsProvider}_api_key`, ttsApiKey);
      }
      // Save GitHub API Key (only if it's not masked)
      if (githubApiKey !== '********') {
        await saveSetting('github_api_key', githubApiKey);
      }
      // Save GitHub Owner and Repo
      await saveSetting('github_owner', githubOwner);
      await saveSetting('github_repo', githubRepo);
      await saveSetting('slack_channel_id', slackChannelId);
      
      setMessage('Settings saved successfully!');
      // Re-mask keys after saving
      if (notionApiKey && notionApiKey !== '********') setNotionApiKey('********');
      if (ttsApiKey && ttsApiKey !== '********') setTtsApiKey('********');
      if (githubApiKey && githubApiKey !== '********') {
        await saveSetting('github_api_key', githubApiKey);
        setGithubApiKey('********');
      }

    } catch (err) {
      setError('Failed to save settings.');
      console.error(err);
    }
  };

  return (
    <div className="settings-container">
      <h2>Settings</h2>
      {message && <div className="save-message success">{message}</div>}
      {error && <div className="save-message error">{error}</div>}

      {/* Notion Settings */}
      <div className="setting">
        <label>Notion API Key</label>
        <input
          type="password"
          value={notionApiKey}
          onChange={(e) => setNotionApiKey(e.target.value)}
          placeholder="Enter Notion API Key"
        />
      </div>
      <div className="setting">
        <label>Notion Tasks Database ID</label>
        <input
          type="text"
          value={notionDatabaseId}
          onChange={(e) => setNotionDatabaseId(e.target.value)}
          placeholder="Enter Notion Tasks Database ID"
        />
      </div>

      {/* GitHub Settings */}
      {/* GitHub Settings */}
      <div className="setting">
        <label>GitHub Personal Access Token</label>
        <input
          type="password"
          value={githubApiKey}
          onChange={(e) => setGithubApiKey(e.target.value)}
          placeholder="Enter GitHub Personal Access Token"
        />
      </div>

      {/* Slack Settings */}
      <div className="setting">
        <label>Slack Channel ID</label>
        <input
          type="text"
          value={slackChannelId}
          onChange={(e) => setSlackChannelId(e.target.value)}
          placeholder="Enter Slack Channel ID to monitor"
        />
      </div>

      {/* Zapier Settings */}
      <div className="setting">
        <label>Zapier Webhook URL</label>
        <input
          type="text"
          value={zapierUrl}
          onChange={(e) => setZapierUrl(e.target.value)}
          placeholder="Enter Zapier Webhook URL"
        />
      </div>

      {/* Voice Settings */}
      <div className="setting">
        <label>TTS Provider</label>
        <select value={ttsProvider} onChange={(e) => {
          setTtsProvider(e.target.value);
          setTtsApiKey(''); // Reset API key when provider changes
        }}>
          <option value="elevenlabs">ElevenLabs</option>
          <option value="deepgram">Deepgram</option>
        </select>
      </div>
      <div className="setting">
        <label>{ttsProvider === 'elevenlabs' ? 'ElevenLabs' : 'Deepgram'} API Key</label>
        <input
          type="password"
          value={ttsApiKey}
          onChange={(e) => setTtsApiKey(e.target.value)}
          placeholder={`Enter ${ttsProvider === 'elevenlabs' ? 'ElevenLabs' : 'Deepgram'} API Key`}
        />
      </div>

      <button onClick={handleSave}>Save Settings</button>
    </div>
  );
};

export default Settings;
