import React, { useState, useEffect } from "react";
import {
  saveSetting,
  getSetting,
  getSettingStatus,
} from "./lib/secure-storage";
import AIProviderSettings from "./AIProviderSettings";
import { JiraDesktopManager } from "./components/services/jira";
import OutlookDesktopManager from "./components/services/outlook/OutlookDesktopManagerNew";
import GitHubDesktopManager from "./components/services/github/GitHubDesktopManager";
import "./Settings.css";

const Settings = () => {
  const [activeTab, setActiveTab] = useState("ai-providers");

  // State for each setting
  const [notionApiKey, setNotionApiKey] = useState("");
  const [notionDatabaseId, setNotionDatabaseId] = useState("");
  const [zapierUrl, setZapierUrl] = useState("");
  const [ttsProvider, setTtsProvider] = useState("elevenlabs");
  const [ttsApiKey, setTtsApiKey] = useState("");
  const [githubApiKey, setGithubApiKey] = useState("");
  const [githubOwner, setGithubOwner] = useState("");
  const [githubRepo, setGithubRepo] = useState("");
  const [slackChannelId, setSlackChannelId] = useState("");

  // Service connection states
  const [jiraConnected, setJiraConnected] = useState(false);
  const [outlookConnected, setOutlookConnected] = useState(false);

  // UI feedback state
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  // Load settings on component mount
  useEffect(() => {
    const loadSettings = async () => {
      // Notion
      if (await getSettingStatus("notion_api_key")) {
        setNotionApiKey("********");
      }
      const savedNotionDbId = await getSetting("notion_tasks_database_id");
      setNotionDatabaseId(savedNotionDbId || "");
      // Zapier
      const savedZapierUrl = await getSetting("zapier_webhook_url");
      setZapierUrl(savedZapierUrl || "");
      // TTS Provider
      const savedTtsProvider = await getSetting("tts_provider");
      if (savedTtsProvider) {
        setTtsProvider(savedTtsProvider);
      }
      // TTS API Key (check based on the loaded provider)
      if (
        await getSettingStatus(`${savedTtsProvider || ttsProvider}_api_key`)
      ) {
        setTtsApiKey("********");
      }
      // GitHub
      if (await getSettingStatus("github_api_key")) {
        setGithubApiKey("********");
      }
      const savedGithubOwner = await getSetting("github_owner");
      setGithubOwner(savedGithubOwner || "");
      const savedGithubRepo = await getSetting("github_repo");
      setGithubRepo(savedGithubRepo || "");
      const savedSlackChannelId = await getSetting("slack_channel_id");
      setSlackChannelId(savedSlackChannelId || "");
    };
    loadSettings();
  }, []);

  const handleSave = async () => {
    setMessage("");
    setError("");
    try {
      // Save Notion API Key (only if it's not masked)
      if (notionApiKey !== "********") {
        await saveSetting("notion_api_key", notionApiKey);
      }
      // Save Notion Database ID
      await saveSetting("notion_tasks_database_id", notionDatabaseId);
      // Save Zapier URL
      await saveSetting("zapier_webhook_url", zapierUrl);
      // Save TTS Provider
      await saveSetting("tts_provider", ttsProvider);
      // Save TTS API Key (only if it's not masked)
      if (ttsApiKey !== "********") {
        await saveSetting(`${ttsProvider}_api_key`, ttsApiKey);
      }
      // Save GitHub API Key (only if it's not masked)
      if (githubApiKey !== "********") {
        await saveSetting("github_api_key", githubApiKey);
      }
      // Save GitHub Owner and Repo
      await saveSetting("github_owner", githubOwner);
      await saveSetting("github_repo", githubRepo);
      await saveSetting("slack_channel_id", slackChannelId);

      setMessage("Settings saved successfully!");
      // Re-mask keys after saving
      if (notionApiKey && notionApiKey !== "********")
        setNotionApiKey("********");
      if (ttsApiKey && ttsApiKey !== "********") setTtsApiKey("********");
      if (githubApiKey && githubApiKey !== "********") {
        await saveSetting("github_api_key", githubApiKey);
        setGithubApiKey("********");
      }
    } catch (err) {
      setError("Failed to save settings.");
      console.error(err);
    }
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case "ai-providers":
        return (
          <div className="tab-content">
            <h1>AI Provider Settings</h1>
            <p className="tab-description">
              Configure your own API keys for different AI providers. Each user
              brings their own keys (BYOK). This allows you to use multiple AI
              providers simultaneously for cost optimization and enhanced
              capabilities.
            </p>
            <AIProviderSettings />
          </div>
        );

      case "integrations":
        return (
          <div className="tab-content">
            <h1>Integration Settings</h1>
            <p className="tab-description">
              Configure third-party integrations and services.
            </p>

            {/* Notion Settings */}
            <div className="integration-section">
              <h3>Notion Integration</h3>
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
            </div>

            {/* GitHub Integration - Enhanced */}
            <div className="integration-section">
              <h3>GitHub Integration</h3>
              <GitHubDesktopManager 
                userId="desktop-user" 
                onConnectionChange={(connected) => setGithubConnected(connected)}
              />
            </div>

            {/* Slack Settings */}
            <div className="integration-section">
              <h3>Slack Integration</h3>
              <div className="setting">
                <label>Slack Channel ID</label>
                <input
                  type="text"
                  value={slackChannelId}
                  onChange={(e) => setSlackChannelId(e.target.value)}
                  placeholder="Enter Slack Channel ID to monitor"
                />
              </div>
            </div>

            {/* Zapier Settings */}
            <div className="integration-section">
              <h3>Zapier Integration</h3>
              <div className="setting">
                <label>Zapier Webhook URL</label>
                <input
                  type="text"
                  value={zapierUrl}
                  onChange={(e) => setZapierUrl(e.target.value)}
                  placeholder="Enter Zapier Webhook URL"
                />
              </div>
            </div>

            {/* Outlook Integration */}
            <div className="integration-section">
              <h3>Outlook Integration</h3>
              <div className="setting">
                <p className="integration-description">
                  Connect your Outlook account to send and receive emails, 
                  manage calendar events, and enable email automation workflows. 
                  Uses Microsoft Graph OAuth for secure authentication.
                </p>
                <OutlookDesktopManager
                  userId="desktop-user"
                  onConnectionChange={setOutlookConnected}
                />
              </div>
            </div>

            {/* Jira Integration */}
            <div className="integration-section">
              <h3>Jira Integration</h3>
              <div className="setting">
                <p className="integration-description">
                  Connect your Jira workspace to manage issues, track projects,
                  and automate workflows. Uses OAuth for secure authentication.
                </p>
                <JiraDesktopManager
                  user={{ id: "desktop-user" }}
                  onServiceConnected={setJiraConnected}
                  onWorkflowUpdate={(workflow) =>
                    console.log("Workflow updated:", workflow)
                  }
                />
              </div>
            </div>

            {/* Voice Settings */}
            <div className="integration-section">
              <h3>Voice Settings</h3>
              <div className="setting">
                <label>TTS Provider</label>
                <select
                  value={ttsProvider}
                  onChange={(e) => {
                    setTtsProvider(e.target.value);
                    setTtsApiKey(""); // Reset API key when provider changes
                  }}
                >
                  <option value="elevenlabs">ElevenLabs</option>
                  <option value="deepgram">Deepgram</option>
                </select>
              </div>
              <div className="setting">
                <label>
                  {ttsProvider === "elevenlabs" ? "ElevenLabs" : "Deepgram"} API
                  Key
                </label>
                <input
                  type="password"
                  value={ttsApiKey}
                  onChange={(e) => setTtsApiKey(e.target.value)}
                  placeholder={`Enter ${ttsProvider === "elevenlabs" ? "ElevenLabs" : "Deepgram"} API Key`}
                />
              </div>
            </div>

            <button onClick={handleSave} className="save-button">
              Save Integration Settings
            </button>
          </div>
        );

      case "account":
        return (
          <div className="tab-content">
            <h1>Account Settings</h1>
            <p className="tab-description">
              Manage your account preferences and personal information.
            </p>
            <div className="account-placeholder">
              <p>Account settings coming soon...</p>
            </div>
          </div>
        );

      case "preferences":
        return (
          <div className="tab-content">
            <h1>Preferences</h1>
            <p className="tab-description">
              Customize your ATOM experience and interface preferences.
            </p>
            <div className="preferences-placeholder">
              <p>Preference settings coming soon...</p>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="settings-container">
      <div className="settings-sidebar">
        <h2>Settings</h2>
        <nav className="settings-nav">
          <button
            className={`nav-item ${activeTab === "ai-providers" ? "active" : ""}`}
            onClick={() => setActiveTab("ai-providers")}
          >
            AI Providers
          </button>
          <button
            className={`nav-item ${activeTab === "integrations" ? "active" : ""}`}
            onClick={() => setActiveTab("integrations")}
          >
            Integrations
          </button>
          <button
            className={`nav-item ${activeTab === "account" ? "active" : ""}`}
            onClick={() => setActiveTab("account")}
          >
            Account
          </button>
          <button
            className={`nav-item ${activeTab === "preferences" ? "active" : ""}`}
            onClick={() => setActiveTab("preferences")}
          >
            Preferences
          </button>
        </nav>
      </div>

      <div className="settings-content">
        {message && <div className="save-message success">{message}</div>}
        {error && <div className="save-message error">{error}</div>}
        {renderTabContent()}
      </div>
    </div>
  );
};

export default Settings;
