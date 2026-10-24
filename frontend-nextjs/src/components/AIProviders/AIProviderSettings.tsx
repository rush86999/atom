import React, { useState, useEffect, useCallback } from "react";
import { useToast } from "@/components/ui/use-toast";
import { authHeaders } from "@/lib/auth-headers";


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
  check?: {
    success: boolean;
    message: string;
    status: string;
    at: string;
  } | null;
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

export interface ProviderPolicy {
  mode: "unset" | "automatic" | "selected" | "invalid";
  allowed_providers: string[];
  preferred: { provider: string; model: string } | null;
  source: "env" | "db" | "default" | "invalid";
  managed_by_env: boolean;
  revision: string;
  error: string | null;
  scope: string;
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
  const { toast } = useToast();
  const [userStatus, setUserStatus] = useState<UserAPIKeyStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [testing, setTesting] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [showKeyInput, setShowKeyInput] = useState<Record<string, boolean>>({});
  const [policy, setPolicy] = useState<ProviderPolicy | null>(null);
  const [policyMode, setPolicyMode] = useState<"automatic" | "selected">("automatic");
  const [policyAllowed, setPolicyAllowed] = useState<string[]>([]);
  const [policyPreferred, setPolicyPreferred] = useState("");
  const [policyPreferredModel, setPolicyPreferredModel] = useState("");
  const [policySaving, setPolicySaving] = useState(false);
  const [policyError, setPolicyError] = useState<string | null>(null);

  // Satellite Key State
  const [satelliteKey, setSatelliteKey] = useState<string | null>(null);
  const [showSatelliteKey, setShowSatelliteKey] = useState(false);
  const [rotatingKey, setRotatingKey] = useState(false);

  // Satellite Setup State
  const [installStatus, setInstallStatus] = useState<'idle' | 'installing' | 'success' | 'error'>('idle');
  const [installLogs, setInstallLogs] = useState("");

  const handleInitializeBrowser = async () => {
    // Check if we are in Tauri
    const isTauri = typeof window !== 'undefined' && (window as any).__TAURI__ !== undefined;

    if (!isTauri) {
      alert("Browser automation initialization is only available in the Desktop App.");
      return;
    }

    try {
      setInstallStatus('installing');
      setInstallLogs("Starting initialization...\n> Checking Python 3\n> Creating virtual environment\n> Installing playwright & websockets\n> Downloading Chromium...");

      const { invoke } = await import('@tauri-apps/api/core');
      const res = await invoke('install_satellite_dependencies') as any;

      if (res.success) {
        setInstallStatus('success');
        setInstallLogs(prev => prev + "\n\n✅ " + res.message);
      } else {
        setInstallStatus('error');
        setInstallLogs(prev => prev + "\n\n❌ Error: " + res.error + (res.details ? "\n" + res.details : ""));
      }
    } catch (err) {
      setInstallStatus('error');
      setInstallLogs(prev => prev + "\n\n❌ Exception: " + String(err));
    }
  };

  const loadSatelliteKey = useCallback(async () => {
    try {
      const response = await fetch(`${baseApiUrl}/satellite/key`);
      if (response.ok) {
        const data = await response.json();
        setSatelliteKey(data.api_key);
      }
    } catch (err) {
      console.error("Failed to load satellite key:", err);
    }
  }, [baseApiUrl]);

  const rotateSatelliteKey = async () => {
    if (!window.confirm("Are you sure you want to rotate your Satellite Key? Existing local connections will be disconnected.")) {
      return;
    }

    try {
      setRotatingKey(true);
      const response = await fetch(`${baseApiUrl}/satellite/rotate`, { method: "POST" });
      if (response.ok) {
        const data = await response.json();
        setSatelliteKey(data.api_key);
      } else {
        alert("Failed to rotate key");
      }
    } catch (err) {
      alert("Error rotating key");
    } finally {
      setRotatingKey(false);
    }
  };

  const loadUserAPIKeyStatus = useCallback(async () => {
    try {
      setLoading(true);
      // Use the correct BYOK endpoint. GET /api/ai/providers is auth-gated
      // (byok_routes.get_ai_providers) — round 80 documented this exact bug
      // class: raw fetch() callers dropping the Authorization header.
      const response = await fetch(`${baseApiUrl}/ai/providers`, {
        headers: authHeaders(),
      });
      if (!response.ok) {
        throw new Error("Failed to load AI providers");
      }
      const data = await response.json();

      // The endpoint wraps its payload in the standard ApiResponse envelope
      // ({success, data: {providers, ...}}); older callers read top-level
      // `providers`, which is undefined → an empty/erroring page. Accept both.
      const payload = data?.data?.providers ? data.data : data;

      // Transform backend response to expected state format
      // Backend returns { providers: [{provider: {...}, usage: {...}, has_api_keys: bool, status: str}], ... }
      if (payload.providers) {
        const statusMap: Record<string, AIProviderStatus> = {};
        let configuredCount = 0;
        let workingCount = 0;

        payload.providers.forEach((p: any) => {
          const check = p.has_api_keys && p.usage?.last_check_at
            ? {
                success: p.usage.last_check_ok === true,
                message: p.usage.last_check_message || "",
                status: p.usage.last_check_status || "unavailable",
                at: p.usage.last_check_at,
              }
            : null;
          statusMap[p.provider.id] = {
            configured: p.has_api_keys,
            // "active" means a key exists and the provider is enabled. It
            // is NOT a successful connection check. Only last_check_* from
            // an explicit Test action may say Ready/Authentication/Quota.
            test_result: {
              success: check?.success === true,
              message: check
                ? check.message
                : p.has_api_keys
                  ? "Key saved — not checked"
                  : "Not configured",
            },
            check,
            provider_info: {
              name: p.provider.name,
              description: p.provider.description,
              acquisition_url: p.provider.base_url || "", // Backend might not have this, default to empty
              expected_format: "Provider-specific key",
              capabilities: p.provider.supported_tasks,
              models: [p.provider.model || "default"]
            }
          };
          if (p.has_api_keys) configuredCount++;
          if (check?.success === true) workingCount++;
        });

        setUserStatus({
          user_id: userId,
          status: statusMap,
          summary: {
            total_available: payload.total_providers,
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
  }, [baseApiUrl, userId]);

  const applyPolicy = useCallback((next: ProviderPolicy | null) => {
    setPolicy(next);
    if (!next) return;
    setPolicyMode(next.mode === "selected" ? "selected" : "automatic");
    setPolicyAllowed(next.allowed_providers || []);
    setPolicyPreferred(next.preferred?.provider || "");
    setPolicyPreferredModel(next.preferred?.model || "");
  }, []);

  const loadProviderPolicy = useCallback(async () => {
    try {
      const response = await fetch(`${baseApiUrl}/ai/provider-policy`, {
        headers: authHeaders(),
      });
      if (response.status === 404) {
        // Older backend: keep the provider list usable, but say so.
        setPolicy(null);
        setPolicyError(
          "Provider routing policy is not available on this backend build.");
        return;
      }
      if (!response.ok) {
        throw new Error(`Failed to load provider policy (${response.status})`);
      }
      const body = await response.json();
      const next = body?.data?.policy ?? body?.policy ?? null;
      applyPolicy(next);
      setPolicyError(next?.error || null);
    } catch (err) {
      setPolicyError(
        err instanceof Error ? err.message : "Failed to load provider policy");
    }
  }, [baseApiUrl, applyPolicy]);

  const saveProviderPolicy = async () => {
    try {
      setPolicySaving(true);
      setPolicyError(null);
      const allowed = policyMode === "selected" ? policyAllowed : [];
      const preferred = policyPreferred && policyPreferredModel
        ? { provider: policyPreferred, model: policyPreferredModel }
        : null;
      if (preferred && policyMode === "selected"
          && !allowed.includes(preferred.provider)) {
        throw new Error(
          "Preferred provider must also be selected in the allowed set.");
      }
      const response = await fetch(`${baseApiUrl}/ai/provider-policy`, {
        method: "PUT",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          mode: policyMode,
          allowed_providers: allowed,
          preferred,
        }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(
          body?.detail || body?.message
          || `Provider policy was rejected (${response.status})`);
      }
      const next = body?.data?.policy ?? body?.policy ?? null;
      applyPolicy(next);
      toast({
        title: "Routing policy saved",
        description: next?.mode === "selected"
          ? "Only the selected providers may receive requests."
          : "Any enabled provider may receive requests.",
      });
    } catch (err) {
      // The prior effective policy remains in force on failed saves; put
      // the controls back to it instead of leaving the rejected draft
      // looking effective.
      applyPolicy(policy);
      setPolicyError(
        err instanceof Error ? err.message : "Failed to save provider policy");
    } finally {
      setPolicySaving(false);
    }
  };

  useEffect(() => {
    loadUserAPIKeyStatus();
    loadProviderPolicy();
    loadSatelliteKey();
  }, [userId, baseApiUrl, loadSatelliteKey, loadUserAPIKeyStatus,
      loadProviderPolicy]);

  const saveAPIKey = async (provider: string, apiKey: string) => {
    try {
      setSaving(provider);
      // BUG-105: Previously fired a duplicate body-less POST first (dead code
      // left over from an exploration). Now sends a single POST with the key
      // in the body (BUG-069 fix).
      const saveResponse = await fetch(
        `${baseApiUrl}/ai/providers/${provider}/keys?key_name=default`,
        {
          method: "POST",
          headers: authHeaders({ "Content-Type": "application/json" }),
          body: JSON.stringify({ api_key: apiKey }),
        }
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
          headers: authHeaders(),
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
      // BUG-104: Previously just re-read cached status — never actually tested
      // the key against the provider. Now calls the backend test endpoint.
      const testResponse = await fetch(
        `${baseApiUrl}/ai/providers/${provider}/test`,
        { method: "POST", headers: authHeaders() }
      );
      if (testResponse.ok) {
        const testData = await testResponse.json();
        const detailMessage =
          testData.message || testData.data?.message
          || testData.error || testData.detail;
        if (testData.success || testData.valid) {
          const checkedAt = testData.data?.checked_at
            ? new Date(testData.data.checked_at).toLocaleString()
            : "just now";
          toast({
            title: "Connection checked",
            description: `${provider} answered a bounded models-list check at ${checkedAt}.`,
          });
        } else {
          toast({
            title: "Connection check failed",
            description: detailMessage || "The provider did not answer the check.",
            variant: "error",
          });
        }
      } else {
        toast({ title: "Connection Failed", description: `Server returned ${testResponse.status}.`, variant: "error" });
      }
      await loadUserAPIKeyStatus();
    } catch {
      toast({ title: "Connection Failed", description: "Network error during test.", variant: "error" });
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
        their own keys. A saved key is permission to store a credential; it is
        not permission to send every request to that provider.
      </p>

      <div className="summary-card provider-policy-section">
        <div className="provider-header">
          <div>
            <h3>Where Atom may send requests</h3>
            <p className="detail">
              This policy is enforced for replies, planning, pins, retries, and
              fallback. Saved keys are never deleted by changing it.
            </p>
          </div>
          <div className={`status-badge ${policy?.managed_by_env ? "not-configured" : "success"}`}>
            {policy?.managed_by_env ? "Managed by this installation" : "Saved policy"}
          </div>
        </div>

        {policy?.managed_by_env && (
          <div className="error-message">
            An environment override controls this installation. The controls
            below are read-only; a UI save will not take effect.
          </div>
        )}
        {policy?.error && (
          <div className="error-message">
            Policy error: {policy.error}. Requests fail closed until this is fixed.
          </div>
        )}
        {policyError && <div className="error-message">{policyError}</div>}

        <div className="policy-options" style={{ marginTop: 12 }}>
          <label className="policy-option">
            <input
              type="radio"
              name="provider-policy-mode"
              checked={policyMode === "automatic"}
              disabled={policy?.managed_by_env}
              onChange={() => setPolicyMode("automatic")}
            />
            <span>
              <strong>Automatic among enabled providers</strong>
              <span className="detail">
                Any enabled provider may receive request content. Preferred
                is an order, not a guarantee.
              </span>
            </span>
          </label>
          <label className="policy-option">
            <input
              type="radio"
              name="provider-policy-mode"
              checked={policyMode === "selected"}
              disabled={policy?.managed_by_env}
              onChange={() => setPolicyMode("selected")}
            />
            <span>
              <strong>Only selected providers</strong>
              <span className="detail">
                Fallback is confined to this set. If none is usable, Atom
                reports an unavailable route instead of sending elsewhere.
              </span>
            </span>
          </label>
        </div>

        {policyMode === "selected" && (
          <div className="policy-provider-grid" style={{ marginTop: 10 }}>
            {Object.entries(userStatus?.status || {})
              .filter(([id, s]) => s.configured || id === "ollama")
              .map(([id, s]) => (
                <label key={id} className="policy-provider-option">
                  <input
                    type="checkbox"
                    checked={policyAllowed.includes(id)}
                    disabled={policy?.managed_by_env}
                    onChange={(e) => {
                      setPolicyAllowed((prev) => e.target.checked
                        ? Array.from(new Set([...prev, id]))
                        : prev.filter((p) => p !== id));
                      if (!e.target.checked && policyPreferred === id) {
                        setPolicyPreferred("");
                      }
                    }}
                  />
                  <span>{s.provider_info.name}</span>
                  {!s.configured && id === "ollama" && (
                    <span className="detail"> (local, no key)</span>
                  )}
                </label>
              ))}
            {Object.entries(userStatus?.status || {})
              .filter(([id, s]) => s.configured || id === "ollama").length === 0 && (
              <p className="detail">Save a provider key first.</p>
            )}
          </div>
        )}

        <div className="policy-preferred" style={{ marginTop: 12 }}>
          <label htmlFor="policy-preferred-provider">
            <strong>Preferred provider</strong> (optional)
          </label>
          <span className="detail" style={{ display: "block", marginBottom: 4 }}>
            The first eligible route. Capability, access, local-only, and
            billing checks still apply; this is not a guarantee.
          </span>
          <select
            id="policy-preferred-provider"
            value={policyPreferred}
            disabled={policy?.managed_by_env}
            onChange={(e) => {
              const next = e.target.value;
              setPolicyPreferred(next);
              if (next) {
                const defaultModel =
                  userStatus?.status[next]?.provider_info.models[0] || "";
                setPolicyPreferredModel((prev) => prev || defaultModel);
              } else {
                setPolicyPreferredModel("");
              }
            }}
            className="key-input"
            style={{ maxWidth: 320 }}
          >
            <option value="">No preferred provider</option>
            {(policyMode === "selected" ? policyAllowed : Object.keys(userStatus?.status || {}))
              .filter((id) => id === "ollama" || userStatus?.status[id]?.configured)
              .map((id) => (
                <option key={id} value={id}>
                  {userStatus?.status[id]?.provider_info.name || id}
                </option>
              ))}
          </select>
          {policyPreferred && (
            <div style={{ marginTop: 8 }}>
              <label htmlFor="policy-preferred-model">
                <strong>Preferred model</strong>
              </label>
              <input
                id="policy-preferred-model"
                className="key-input"
                value={policyPreferredModel}
                disabled={policy?.managed_by_env}
                onChange={(e) => setPolicyPreferredModel(e.target.value)}
                placeholder="e.g. llama3.1:8b"
                style={{ display: "block", maxWidth: 320, marginTop: 4 }}
              />
            </div>
          )}
        </div>

        <div className="detail" style={{ marginTop: 10 }}>
          <strong>Fallback:</strong>{" "}
          {policyMode === "selected"
            ? `only ${policyAllowed.length
                ? policyAllowed.join(", ")
                : "the selected set (currently empty — requests will be unavailable)"}.`
            : "any enabled provider from the saved BYOK store."}
        </div>

        <div className="provider-actions" style={{ marginTop: 12 }}>
          <button
            className="save-btn"
            onClick={saveProviderPolicy}
            disabled={policySaving || policy?.managed_by_env}
          >
            {policySaving ? "Saving..." : "Save Routing Policy"}
          </button>
          {policy?.revision && (
            <span className="detail" style={{ alignSelf: "center" }}>
              Effective revision {policy.revision}
              {policy.source ? ` · source: ${policy.source}` : ""}
            </span>
          )}
        </div>
      </div>

      {/* Satellite Key Section */}
      <div className="satellite-key-section">
        <div className="summary-card">
          <div className="provider-header">
            <div>
              <h3>Satellite Platform Key</h3>
              <p className="detail">Connect your local machine using the Atom Satellite bridge.</p>
            </div>
          </div>
          <div className="key-input-section" style={{ marginTop: '10px' }}>
            <div style={{ display: 'flex', gap: '10px' }}>
              <input
                type={showSatelliteKey ? "text" : "password"}
                value={satelliteKey || "Loading..."}
                readOnly
                className="key-input"
                style={{ flex: 1 }}
              />
              <button
                onClick={() => setShowSatelliteKey(!showSatelliteKey)}
                className="update-btn"
                style={{ width: '100px' }}
              >
                {showSatelliteKey ? "Hide" : "Show"}
              </button>
              <button
                onClick={rotateSatelliteKey}
                disabled={rotatingKey}
                className="delete-btn"
                style={{ width: '100px' }}
              >
                {rotatingKey ? "..." : "Rotate"}
              </button>
            </div>

            {/* Browser Automation Setup */}
            <div style={{ marginTop: '15px', borderTop: '1px solid #e9ecef', paddingTop: '15px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                <div style={{ flex: 1 }}>
                  <h4 style={{ margin: 0, fontSize: '14px', color: '#2d3748' }}>Browser Automation</h4>
                  <p style={{ fontSize: '11px', color: '#718096', margin: '2px 0 0 0' }}>
                    Setup Chromium and required libraries for local web exploration.
                  </p>
                </div>
                <button
                  onClick={handleInitializeBrowser}
                  disabled={installStatus === 'installing' || installStatus === 'success'}
                  className={installStatus === 'success' ? "test-btn" : "save-btn"}
                  style={{
                    padding: '6px 12px',
                    fontSize: '12px',
                    minWidth: '120px'
                  }}
                >
                  {installStatus === 'installing' ? "Initializing..." : installStatus === 'success' ? "Ready" : "Setup Browser"}
                </button>
              </div>

              {installStatus !== 'idle' && (
                <div style={{
                  background: '#1a202c',
                  color: '#68d391',
                  padding: '12px',
                  borderRadius: '6px',
                  fontFamily: '\'Courier New\', Courier, monospace',
                  fontSize: '10px',
                  maxHeight: '120px',
                  overflowY: 'auto',
                  whiteSpace: 'pre-wrap',
                  border: '1px solid #2d3748',
                  marginTop: '10px'
                }}>
                  {installLogs}
                </div>
              )}
            </div>

            <div style={{ marginTop: '15px', background: 'rgba(49, 130, 206, 0.1)', border: '1px solid rgba(49, 130, 206, 0.2)', borderRadius: '8px', padding: '10px' }}>
              <p style={{ fontSize: '11px', color: '#63B3ED', fontWeight: 'bold' }}>
                💡 Human-in-the-loop:
              </p>
              <p style={{ fontSize: '11px', color: '#A0AEC0' }}>
                The agent&apos;s browser window is visible locally so you can assist with MFA or initial logins. Results are saved to a persistent profile.
              </p>
            </div>
            <p style={{ fontSize: '10px', color: '#666', marginTop: '5px' }}>
              Use this key with the <code>--key</code> flag when running <code>atom_satellite.py</code>.
            </p>
          </div>
        </div>
      </div>

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
                      className={`status-badge ${
                        status.check?.success
                          ? "success"
                          : status.check
                            ? "error"
                            : status.configured
                              ? "not-configured"
                              : "not-configured"
                      }`}
                    >
                      {status.check
                        ? status.check.success
                          ? `Ready — checked ${new Date(status.check.at).toLocaleString()}`
                          : status.check.status === "authentication_failed"
                            ? "Authentication failed"
                            : status.check.status === "usage_limit"
                              ? "Usage limit reached"
                              : "Unavailable"
                        : status.configured
                          ? "Key saved — not checked"
                          : "Not configured"}
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
                    {policy?.mode === "selected"
                      && !policy.allowed_providers.includes(provider) && (
                      <div className="detail">
                        Enabled, excluded by routing policy
                      </div>
                    )}
                  </div>

                  {status.check && !status.check.success && (
                    <div className="error-message">
                      {status.check.message}
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
                      Provider site
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

        .satellite-key-section {
          margin-bottom: 30px;
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

        .provider-policy-section {
          margin-bottom: 24px;
        }

        .policy-options {
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .policy-option,
        .policy-provider-option {
          display: flex;
          gap: 8px;
          align-items: flex-start;
          cursor: pointer;
        }

        .policy-option .detail {
          display: block;
          margin-top: 2px;
          color: #666;
          font-size: 0.9rem;
        }

        .policy-provider-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 8px 16px;
        }

        .policy-provider-option {
          align-items: center;
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
