import React, { useState, useEffect } from 'react';
import { saveSetting, getSetting, getSettingStatus } from '../lib/secure-storage';
import '../Settings.css';

const Integrations = () => {
  // State for each setting
  const [boxClientId, setBoxClientId] = useState('');
  const [boxClientSecret, setBoxClientSecret] = useState('');
  const [asanaClientId, setAsanaClientId] = useState('');
  const [asanaClientSecret, setAsanaClientSecret] = useState('');
  const [trelloApiKey, setTrelloApiKey] = useState('');
  const [trelloApiSecret, setTrelloApiSecret] = useState('');
  const [jiraServerUrl, setJiraServerUrl] = useState('');
  const [jiraUsername, setJiraUsername] = useState('');
  const [jiraApiKey, setJiraApiKey] = useState('');

  // UI feedback state
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  // Load settings on component mount
  useEffect(() => {
    const loadSettings = async () => {
      // Box
      if (await getSettingStatus('box_client_id')) {
        setBoxClientId('********');
      }
      if (await getSettingStatus('box_client_secret')) {
        setBoxClientSecret('********');
      }
      // Asana
      if (await getSettingStatus('asana_client_id')) {
        setAsanaClientId('********');
      }
      if (await getSettingStatus('asana_client_secret')) {
        setAsanaClientSecret('********');
      }
      // Trello
      if (await getSettingStatus('trello_api_key')) {
        setTrelloApiKey('********');
      }
      if (await getSettingStatus('trello_api_secret')) {
        setTrelloApiSecret('********');
      }
      // Jira
      const savedJiraServerUrl = await getSetting('jira_server_url');
      setJiraServerUrl(savedJiraServerUrl || '');
      const savedJiraUsername = await getSetting('jira_username');
      setJiraUsername(savedJiraUsername || '');
      if (await getSettingStatus('jira_api_key')) {
        setJiraApiKey('********');
      }
    };
    loadSettings();
  }, []);

  const handleSave = async () => {
    setMessage('');
    setError('');
    try {
      // Box
      if (boxClientId !== '********') {
        await saveSetting('box_client_id', boxClientId);
      }
      if (boxClientSecret !== '********') {
        await saveSetting('box_client_secret', boxClientSecret);
      }
      // Asana
      if (asanaClientId !== '********') {
        await saveSetting('asana_client_id', asanaClientId);
      }
      if (asanaClientSecret !== '********') {
        await saveSetting('asana_client_secret', asanaClientSecret);
      }
      // Trello
      if (trelloApiKey !== '********') {
        await saveSetting('trello_api_key', trelloApiKey);
      }
      if (trelloApiSecret !== '********') {
        await saveSetting('trello_api_secret', trelloApiSecret);
      }
      // Jira
      await saveSetting('jira_server_url', jiraServerUrl);
      await saveSetting('jira_username', jiraUsername);
      if (jiraApiKey !== '********') {
        await saveSetting('jira_api_key', jiraApiKey);
      }

      setMessage('Settings saved successfully!');
      // Re-mask keys after saving
      if (boxClientId && boxClientId !== '********') setBoxClientId('********');
      if (boxClientSecret && boxClientSecret !== '********') setBoxClientSecret('********');
      if (asanaClientId && asanaClientId !== '********') setAsanaClientId('********');
      if (asanaClientSecret && asanaClientSecret !== '********') setAsanaClientSecret('********');
      if (trelloApiKey && trelloApiKey !== '********') setTrelloApiKey('********');
      if (trelloApiSecret && trelloApiSecret !== '********') setTrelloApiSecret('********');
      if (jiraApiKey && jiraApiKey !== '********') setJiraApiKey('********');

    } catch (err) {
      setError('Failed to save settings.');
      console.error(err);
    }
  };

  return (
    <div className="settings-container">
      <h2>Integrations</h2>
      {message && <div className="save-message success">{message}</div>}
      {error && <div className="save-message error">{error}</div>}

      {/* Box Settings */}
      <div className="setting">
        <label>Box Client ID</label>
        <input
          type="password"
          value={boxClientId}
          onChange={(e) => setBoxClientId(e.target.value)}
          placeholder="Enter Box Client ID"
        />
      </div>
      <div className="setting">
        <label>Box Client Secret</label>
        <input
          type="password"
          value={boxClientSecret}
          onChange={(e) => setBoxClientSecret(e.target.value)}
          placeholder="Enter Box Client Secret"
        />
      </div>

      {/* Asana Settings */}
      <div className="setting">
        <label>Asana Client ID</label>
        <input
          type="password"
          value={asanaClientId}
          onChange={(e) => setAsanaClientId(e.target.value)}
          placeholder="Enter Asana Client ID"
        />
      </div>
      <div className="setting">
        <label>Asana Client Secret</label>
        <input
          type="password"
          value={asanaClientSecret}
          onChange={(e) => setAsanaClientSecret(e.target.value)}
          placeholder="Enter Asana Client Secret"
        />
      </div>

      {/* Trello Settings */}
      <div className="setting">
        <label>Trello API Key</label>
        <input
          type="password"
          value={trelloApiKey}
          onChange={(e) => setTrelloApiKey(e.target.value)}
          placeholder="Enter Trello API Key"
        />
      </div>
      <div className="setting">
        <label>Trello API Secret</label>
        <input
          type="password"
          value={trelloApiSecret}
          onChange={(e) => setTrelloApiSecret(e.target.value)}
          placeholder="Enter Trello API Secret"
        />
      </div>

      {/* Jira Settings */}
      <div className="setting">
        <label>Jira Server URL</label>
        <input
          type="text"
          value={jiraServerUrl}
          onChange={(e) => setJiraServerUrl(e.target.value)}
          placeholder="Enter Jira Server URL"
        />
      </div>
      <div className="setting">
        <label>Jira Username</label>
        <input
          type="text"
          value={jiraUsername}
          onChange={(e) => setJiraUsername(e.target.value)}
          placeholder="Enter Jira Username"
        />
      </div>
      <div className="setting">
        <label>Jira API Key</label>
        <input
          type="password"
          value={jiraApiKey}
          onChange={(e) => setJiraApiKey(e.target.value)}
          placeholder="Enter Jira API Key"
        />
      </div>

      <button onClick={handleSave}>Save Settings</button>
    </div>
  );
};

export default Integrations;
