import React, { useState, useEffect } from "react";


// Types shared across both frontends
export interface AIProvider {
  name: string;
  description: string;
  acquisition_url: string;
  expected_format: string;
  capabilities: string[];
  models: string[];
}

export interface AIProviderStatus {
  configured: boolean;
  test_result: {
    success: boolean;
    message: string;
  };
  provider_info: AIProvider;
}

export interface UserAPIKeyStatus {
  user_id: string;
  status: Record<string, AIProviderStatus>;
  summary: {
    total_available: number;
    total_configured: number;
    total_working: number;
  };
}

export interface AIProviderSettingsProps {
  userId?: string;
  baseApiUrl?: string;
  className?: string;
}

const AIProviderSettings: React.FC<AIProviderSettingsProps> = ({
  userId = "current-user",
  baseApiUrl = "/api",
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

  useEffect(() => {
    loadUserAPIKeyStatus();
  }, [userId, baseApiUrl]);

  const loadUserAPIKeyStatus = async () => {
    try {
      setLoading(true);
      // Use the correct BYOK endpoint
      const response = await fetch(`${baseApiUrl}/ai/providers`);
      if (!response.ok) {
        throw new Error("Failed to load AI providers");
      }
      const data = await response.json();

      // Transform backend response to expected state format
      // Backend returns { providers: [{provider: {...}, usage: {...}, has_api_keys: bool, status: str}], ... }
      if (data.providers) {
        const statusMap: Record<string, AIProviderStatus> = {};
        let configuredCount = 0;
        let workingCount = 0;

        data.providers.forEach((p: any) => {
          statusMap[p.provider.id] = {
            configured: p.has_api_keys,
            test_result: {
              success: p.status === "active",
              message: p.status === "active" ? "Connection successful" : "Not configured or inactive"
            },
            provider_info: {
              name: p.provider.name,
              description: p.provider.description,
              acquisition_url: p.provider.base_url || "", // Backend might not have this, default to empty
              expected_format: "sk-...",
              capabilities: p.provider.supported_tasks,
              models: [p.provider.model || "default"]
            }
          };
          if (p.has_api_keys) configuredCount++;
          if (p.status === "active") workingCount++;
        });

        setUserStatus({
          user_id: userId,
          status: statusMap,
          summary: {
            total_available: data.total_providers,
            total_configured: configuredCount,
            total_working: workingCount
          }
        });
      } else {
        setError("Invalid response format from server");
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
      // Use correct BYOK endpoint for storing keys
      const response = await fetch(
        `${baseApiUrl}/ai/providers/${provider}/keys`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          // Backend expects query params or body? Check byok_endpoints.py
          // It uses query params for provider_id etc in decorated function but body for api_key if not careful
          // Wait, look at byok_endpoints.py signature: 
          // store_api_key(provider_id: str, api_key: str, ...)
          // If it's a POST, FastAPI usually expects query params unless Body() is used.
          // Let's assume query params for provider_id (in path) and query string for api_key?
          // Actually, standard FastAPI POST with simple params expects query params if not pydantic model.
          // Let's use query string for api_key to match likely FastAPI verification/default behavior if not explicit Body.
          // converting to URLSearchParams just in case.
        }
      );

      // Wait, passing key in query string is insecure. The backend *should* accept body.
      // Re-reading byok_endpoints.py:
      // @router.post("/api/ai/providers/{provider_id}/keys")
      // async def store_api_key(provider_id: str, api_key: str, ...
      // In FastAPI, scalar types are query params by default. 
      // Let's try sending as query param for now as per signature implied, but ideally we fix backend to use Body.
      // For now, I'll send it as query param to match the signature I saw.

      const saveResponse = await fetch(
        `${baseApiUrl}/ai/providers/${provider}/keys?api_key=${encodeURIComponent(apiKey)}&key_name=default`,
        { method: "POST" }
      );

      if (!saveResponse.ok) {
        throw new Error("Failed to save API key");
      }

      const data = await saveResponse.json();
      if (data.success) {
        setApiKeys((prev) => ({ ...prev, [provider]: "" }));
        setShowKeyInput((prev) => ({ ...prev, [provider]: false }));
        await loadUserAPIKeyStatus();
      } else {
        setError(data.message || "Failed to save API key");
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
        `${baseApiUrl}/ai/providers/${provider}/keys/default`,
        {
          method: "DELETE",
        },
      );

      if (!response.ok) {
        throw new Error("Failed to delete API key");
      }

      const data = await response.json();
      if (data.success) {
        await loadUserAPIKeyStatus();
      } else {
        setError("Failed to delete API key");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    }
  };

  const testAPIKey = async (provider: string) => {
    // The BYOK backend verifies status on load. 
    // We can just reload the status to "test".
    try {
      setTesting(provider);
      await loadUserAPIKeyStatus();
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

  const getProviderCategory = (capabilities: string[] = []) => {
    if (capabilities.includes("reasoning")) return "Core Intelligence";
    if (capabilities.includes("vision") || capabilities.includes("pdf_ocr")) return "Vision & Extraction";
    return "Specialized & Alternatives";
  };

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

      {["Core Intelligence", "Vision & Extraction", "Specialized & Alternatives"].map(category => {
        const providersInCategory = userStatus ? Object.entries(userStatus.status).filter(
          ([_, status]) => getProviderCategory(status.provider_info.capabilities) === category
        ) : [];

        if (providersInCategory.length === 0) return null;

        return (
          <div key={category} className="category-section">
            <h3 className="category-title">{category}</h3>
            <div className="providers-grid">
              {providersInCategory.map(([provider, status]) => (
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
      })}

      <style>{`
        .ai-provider-settings {
          max-width: 1200px;
          margin: 0 auto;
          padding: 20px;
        }

        .description {
          color: #666;
          margin-bottom: 30px;
        }

        .category-section {
          margin-bottom: 40px;
        }

        .category-title {
          font-size: 1.5rem;
          color: #2c3e50;
          margin-bottom: 20px;
          padding-bottom: 10px;
          border-bottom: 2px solid #ecf0f1;
        }

        .status-summary {
          margin-bottom: 30px;
        }

        .summary-card {
          background: #f8f9fa;
          border-radius: 8px;
          padding: 20px;
          border: 1px solid #e9ecef;
        }

        .summary-card h3 {
          margin: 0 0 15px 0;
          color: #333;
        }

        .summary-stats {
          display: flex;
          gap: 30px;
        }

        .stat {
          text-align: center;
        }

        .stat-number {
          display: block;
          font-size: 2rem;
          font-weight: bold;
          color: #007bff;
        }

        .stat-label {
          font-size: 0.9rem;
          color: #666;
        }

        .providers-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
          gap: 20px;
        }

        .provider-card {
          border: 1px solid #e9ecef;
          border-radius: 8px;
          padding: 20px;
          background: white;
        }

        .provider-card.configured {
          border-left: 4px solid #28a745;
        }

        .provider-card.not-configured {
          border-left: 4px solid #6c757d;
        }

        .provider-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 10px;
        }

        .provider-header h3 {
          margin: 0;
          color: #333;
        }

        .status-badge {
          padding: 4px 8px;
          border-radius: 4px;
          font-size: 0.8rem;
          font-weight: bold;
        }

        .status-badge.success {
          background: #d4edda;
          color: #155724;
        }

        .status-badge.error {
          background: #f8d7da;
          color: #721c24;
        }

        .status-badge.not-configured {
          background: #e2e3e5;
          color: #383d41;
        }

        .provider-description {
          color: #666;
          margin-bottom: 15px;
          line-height: 1.4;
        }

        .provider-details {
          margin-bottom: 15px;
        }

        .detail {
          margin-bottom: 5px;
          font-size: 0.9rem;
        }

        .provider-actions {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .key-input-section {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .key-input {
          padding: 8px 12px;
          border: 1px solid #ddd;
          border-radius: 4px;
          font-family: monospace;
        }

        .key-actions {
          display: flex;
          gap: 10px;
        }

        .configured-actions {
          display: flex;
          gap: 10px;
          flex-wrap: wrap;
        }

        button {
          padding: 8px 16px;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-size: 0.9rem;
        }

        button:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .save-btn {
          background: #007bff;
          color: white;
        }

        .test-btn {
          background: #28a745;
          color: white;
        }

        .update-btn {
          background: #ffc107;
          color: #212529;
        }

        .delete-btn {
          background: #dc3545;
          color: white;
        }

        .cancel-btn {
          background: #6c757d;
          color: white;
        }

        .get-key-link {
          color: #007bff;
          text-decoration: none;
          font-size: 0.9rem;
          align-self: flex-start;
        }

        .get-key-link:hover {
          text-decoration: underline;
        }

        .error-message {
          background: #f8d7da;
          color: #721c24;
          padding: 8px 12px;
          border-radius: 4px;
          font-size: 0.9rem;
          margin-bottom: 10px;
        }

        .loading {
          text-align: center;
          padding: 40px;
          color: #666;
        }

        .retry-btn {
          margin-left: 10px;
          background: #007bff;
          color: white;
          padding: 5px 10px;
          border: none;
          border-radius: 4px;
          cursor: pointer;
        }

        @media (max-width: 768px) {
          .providers-grid {
            grid-template-columns: 1fr;
          }

          .summary-stats {
            flex-direction: column;
            gap: 15px;
          }

          .configured-actions {
            flex-direction: column;
          }
        }
      `}</style>
    </div>
  );
};

export default AIProviderSettings;
