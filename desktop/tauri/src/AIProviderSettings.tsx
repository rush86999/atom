import React, { useState, useEffect } from "react";
import {
  saveSetting,
  getSetting,
  getSettingStatus,
} from "./lib/secure-storage";
import "./AIProviderSettings.css";

// Types shared with the backend
interface AIProvider {
  name: string;
  description: string;
  acquisition_url: string;
  expected_format: string;
  capabilities: string[];
  models: string[];
}

interface AIProviderStatus {
  configured: boolean;
  test_result: {
    success: boolean;
    message: string;
  };
  provider_info: AIProvider;
}

interface UserAPIKeyStatus {
  user_id: string;
  status: Record<string, AIProviderStatus>;
  summary: {
    total_available: number;
    total_configured: number;
    total_working: number;
  };
}

interface AIProviderSettingsProps {
  userId?: string;
  baseApiUrl?: string;
  className?: string;
}

const AIProviderSettings: React.FC<AIProviderSettingsProps> = ({
  userId = "current-user",
  baseApiUrl = "http://localhost:5058/api",
  className = "",
}) => {
  const [userStatus, setUserStatus] = useState<UserAPIKeyStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [testing, setTesting] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [showKeyInput, setShowKeyInput] = useState<Record<string, boolean>>({});

  useEffect(() => {
    loadUserAPIKeyStatus();
  }, [userId, baseApiUrl]);

  const loadUserAPIKeyStatus = async () => {
    try {
      setLoading(true);
      const response = await fetch(
        `${baseApiUrl}/user/api-keys/${userId}/status`,
      );
      if (!response.ok) {
        throw new Error("Failed to load API key status");
      }
      const data = await response.json();
      if (data.success) {
        setUserStatus(data);
      } else {
        setError(data.error || "Failed to load API key status");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  const saveAPIKey = async (provider: string, apiKey: string) => {
    try {
      setSaving(provider);
      const response = await fetch(
        `${baseApiUrl}/user/api-keys/${userId}/keys/${provider}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ api_key: apiKey }),
        },
      );

      if (!response.ok) {
        throw new Error("Failed to save API key");
      }

      const data = await response.json();
      if (data.success) {
        // Also save to secure storage for offline access
        await saveSetting(`${provider}_api_key`, apiKey);

        // Clear the input and hide it
        setApiKeys((prev) => ({ ...prev, [provider]: "" }));
        setShowKeyInput((prev) => ({ ...prev, [provider]: false }));
        // Reload status
        await loadUserAPIKeyStatus();
      } else {
        setError(data.error || "Failed to save API key");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setSaving(null);
    }
  };

  const deleteAPIKey = async (provider: string) => {
    try {
      const response = await fetch(
        `${baseApiUrl}/user/api-keys/${userId}/keys/${provider}`,
        {
          method: "DELETE",
        },
      );

      if (!response.ok) {
        throw new Error("Failed to delete API key");
      }

      const data = await response.json();
      if (data.success) {
        // Also remove from secure storage
        await saveSetting(`${provider}_api_key`, "");
        // Reload status
        await loadUserAPIKeyStatus();
      } else {
        setError(data.error || "Failed to delete API key");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    }
  };

  const testAPIKey = async (provider: string) => {
    try {
      setTesting(provider);
      const response = await fetch(
        `${baseApiUrl}/user/api-keys/${userId}/keys/${provider}/test`,
        {
          method: "POST",
        },
      );

      if (!response.ok) {
        throw new Error("Failed to test API key");
      }

      const data = await response.json();
      if (data.success) {
        // Reload status to get updated test results
        await loadUserAPIKeyStatus();
      } else {
        setError(data.error || "Failed to test API key");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setTesting(null);
    }
  };

  const toggleKeyInput = (provider: string) => {
    setShowKeyInput((prev) => ({
      ...prev,
      [provider]: !prev[provider],
    }));
  };

  const handleKeyChange = (provider: string, value: string) => {
    setApiKeys((prev) => ({
      ...prev,
      [provider]: value,
    }));
  };

  if (loading) {
    return (
      <div className={`ai-provider-settings ${className}`}>
        <h2>AI Provider Settings</h2>
        <div className="loading">Loading AI provider status...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`ai-provider-settings ${className}`}>
        <h2>AI Provider Settings</h2>
        <div className="error-message">
          {error}
          <button onClick={loadUserAPIKeyStatus} className="retry-btn">
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`ai-provider-settings ${className}`}>
      <h2>AI Provider Settings</h2>
      <p className="description">
        Configure your own API keys for different AI providers. Each user brings
        their own keys.
      </p>

      {userStatus && (
        <div className="status-summary">
          <div className="summary-card">
            <h3>Provider Status</h3>
            <div className="summary-stats">
              <div className="stat">
                <span className="stat-number">
                  {userStatus.summary.total_configured}
                </span>
                <span className="stat-label">Configured</span>
              </div>
              <div className="stat">
                <span className="stat-number">
                  {userStatus.summary.total_working}
                </span>
                <span className="stat-label">Working</span>
              </div>
              <div className="stat">
                <span className="stat-number">
                  {userStatus.summary.total_available}
                </span>
                <span className="stat-label">Available</span>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="providers-grid">
        {userStatus &&
          Object.entries(userStatus.status).map(([provider, status]) => (
            <div
              key={provider}
              className={`provider-card ${status.configured ? "configured" : "not-configured"}`}
            >
              <div className="provider-header">
                <h3>{status.provider_info.name}</h3>
                <div
                  className={`status-badge ${status.test_result.success ? "success" : status.configured ? "error" : "not-configured"}`}
                >
                  {status.test_result.success
                    ? "✓ Working"
                    : status.configured
                      ? "✗ Failed"
                      : "Not Configured"}
                </div>
              </div>

              <p className="provider-description">
                {status.provider_info.description}
              </p>

              <div className="provider-details">
                <div className="detail">
                  <strong>Models:</strong>{" "}
                  {status.provider_info.models.join(", ")}
                </div>
                <div className="detail">
                  <strong>Capabilities:</strong>{" "}
                  {status.provider_info.capabilities.join(", ")}
                </div>
                <div className="detail">
                  <strong>Key Format:</strong>{" "}
                  {status.provider_info.expected_format}
                </div>
              </div>

              {status.test_result.message &&
                !status.test_result.success &&
                status.configured && (
                  <div className="error-message">
                    {status.test_result.message}
                  </div>
                )}

              <div className="provider-actions">
                {!status.configured || showKeyInput[provider] ? (
                  <div className="key-input-section">
                    <input
                      type="password"
                      placeholder={`Enter your ${status.provider_info.name} API key`}
                      value={apiKeys[provider] || ""}
                      onChange={(e) =>
                        handleKeyChange(provider, e.target.value)
                      }
                      className="key-input"
                    />
                    <div className="key-actions">
                      <button
                        onClick={() =>
                          saveAPIKey(provider, apiKeys[provider] || "")
                        }
                        disabled={!apiKeys[provider] || saving === provider}
                        className="save-btn"
                      >
                        {saving === provider ? "Saving..." : "Save Key"}
                      </button>
                      {status.configured && (
                        <button
                          onClick={() => toggleKeyInput(provider)}
                          className="cancel-btn"
                        >
                          Cancel
                        </button>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="configured-actions">
                    <button
                      onClick={() => testAPIKey(provider)}
                      disabled={testing === provider}
                      className="test-btn"
                    >
                      {testing === provider ? "Testing..." : "Test Connection"}
                    </button>
                    <button
                      onClick={() => toggleKeyInput(provider)}
                      className="update-btn"
                    >
                      Update Key
                    </button>
                    <button
                      onClick={() => deleteAPIKey(provider)}
                      className="delete-btn"
                    >
                      Remove
                    </button>
                  </div>
                )}

                <a
                  href={status.provider_info.acquisition_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="get-key-link"
                >
                  Get API Key
                </a>
              </div>
            </div>
          ))}
      </div>
    </div>
  );
};

export default AIProviderSettings;
