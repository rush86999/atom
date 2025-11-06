/**
 * Jira Integration Component - Tauri Desktop
 * Fully integrated with ATOM desktop app and workflow automation
 */

import React, { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/tauri";
import { listen } from "@tauri-apps/api/event";

interface JiraUser {
  id: string;
  name: string;
  email: string;
  avatarUrl?: string;
}

interface JiraProject {
  id: string;
  key: string;
  name: string;
  projectTypeKey: string;
  avatarUrls?: Record<string, string>;
}

interface JiraIssue {
  id: string;
  key: string;
  summary: string;
  description?: string;
  status: {
    name: string;
    category: string;
  };
  assignee?: JiraUser;
  reporter?: JiraUser;
  created: string;
  updated: string;
  priority?: {
    name: string;
    iconUrl?: string;
  };
}

interface JiraConnectionStatus {
  connected: boolean;
  user?: JiraUser;
  projects: JiraProject[];
  issues: JiraIssue[];
  error?: string;
}

interface JiraDesktopManagerProps {
  userId: string;
  onConnectionChange?: (connected: boolean) => void;
}

export const JiraDesktopManager: React.FC<JiraDesktopManagerProps> = ({
  userId,
  onConnectionChange,
}) => {
  const [jiraStatus, setJiraStatus] = useState<JiraConnectionStatus>({
    connected: false,
    projects: [],
    issues: [],
  });
  const [isLoading, setIsLoading] = useState(false);
  const [user, setUser] = useState<JiraUser | null>(null);

  // Check Jira connection status on mount
  useEffect(() => {
    checkJiraConnection();

    // Listen for Jira events
    const unsubscribe = listen("jira:connection:updated", (event) => {
      console.log("Jira connection updated:", event.payload);
      checkJiraConnection();
    });

    return () => {
      unsubscribe.then((fn) => fn());
    };
  }, [userId]);

  const checkJiraConnection = async () => {
    try {
      setIsLoading(true);

      const result = await invoke<JiraConnectionStatus>("get_jira_connection", {
        userId,
      });

      setJiraStatus(result);

      if (onConnectionChange) {
        onConnectionChange(result.connected);
      }
    } catch (error) {
      console.error("Failed to check Jira connection:", error);
      setJiraStatus({
        connected: false,
        projects: [],
        issues: [],
        error: "Failed to check connection",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const initiateJiraOAuth = async () => {
    try {
      setIsLoading(true);

      const result = await invoke<{ success: boolean; oauth_url: string }>(
        "initiate_jira_oauth",
        {
          userId,
        },
      );

      if (result.success && result.oauth_url) {
        // Open OAuth URL in system browser
        const { open } = await import("@tauri-apps/api/shell");
        await open(result.oauth_url);
      } else {
        throw new Error("Failed to initiate OAuth");
      }
    } catch (error) {
      console.error("Failed to initiate Jira OAuth:", error);
      alert("Failed to start Jira OAuth process");
    } finally {
      setIsLoading(false);
    }
  };

  const disconnectJira = async () => {
    try {
      setIsLoading(true);

      const result = await invoke<{ success: boolean }>("disconnect_jira", {
        userId,
      });

      if (result.success) {
        setJiraStatus({
          connected: false,
          projects: [],
          issues: [],
        });

        if (onConnectionChange) {
          onConnectionChange(false);
        }
      } else {
        throw new Error("Failed to disconnect");
      }
    } catch (error) {
      console.error("Failed to disconnect Jira:", error);
      alert("Failed to disconnect Jira");
    } finally {
      setIsLoading(false);
    }
  };

  const refreshJiraData = async () => {
    try {
      setIsLoading(true);

      const result = await invoke<JiraConnectionStatus>("refresh_jira_data", {
        userId,
      });

      setJiraStatus(result);
    } catch (error) {
      console.error("Failed to refresh Jira data:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const createJiraIssue = async (
    projectKey: string,
    summary: string,
    description?: string,
  ) => {
    try {
      const result = await invoke<{ success: boolean; issue?: JiraIssue }>(
        "create_jira_issue",
        {
          userId,
          projectKey,
          summary,
          description,
        },
      );

      if (result.success && result.issue) {
        // Refresh issues list
        await refreshJiraData();
        return result.issue;
      } else {
        throw new Error("Failed to create issue");
      }
    } catch (error) {
      console.error("Failed to create Jira issue:", error);
      throw error;
    }
  };

  return (
    <div className="jira-desktop-manager">
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <span className="text-blue-600 font-bold text-lg">J</span>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">
                Jira Integration
              </h2>
              <p className="text-sm text-gray-500">
                Manage your Jira projects and issues
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <div
              className={`w-3 h-3 rounded-full ${jiraStatus.connected ? "bg-green-500" : "bg-red-500"}`}
            ></div>
            <span className="text-sm font-medium">
              {jiraStatus.connected ? "Connected" : "Disconnected"}
            </span>
          </div>
        </div>

        {/* Connection Status */}
        <div className="mb-6">
          {!jiraStatus.connected ? (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-medium text-yellow-800">
                    Jira not connected
                  </h3>
                  <p className="text-sm text-yellow-700 mt-1">
                    Connect your Jira account to manage projects and issues
                  </p>
                </div>
                <button
                  onClick={initiateJiraOAuth}
                  disabled={isLoading}
                  className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isLoading ? "Connecting..." : "Connect Jira"}
                </button>
              </div>
            </div>
          ) : (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-medium text-green-800">
                    Jira connected
                  </h3>
                  <p className="text-sm text-green-700 mt-1">
                    {jiraStatus.user
                      ? `Connected as ${jiraStatus.user.name}`
                      : "Successfully connected to Jira"}
                  </p>
                </div>
                <div className="flex space-x-2">
                  <button
                    onClick={refreshJiraData}
                    disabled={isLoading}
                    className="bg-gray-600 text-white px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Refresh
                  </button>
                  <button
                    onClick={disconnectJira}
                    disabled={isLoading}
                    className="bg-red-600 text-white px-3 py-2 rounded-md text-sm font-medium hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Disconnect
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Projects and Issues */}
        {jiraStatus.connected && (
          <div className="space-y-6">
            {/* Projects Section */}
            {jiraStatus.projects.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-900 mb-3">
                  Projects
                </h4>
                <div className="grid grid-cols-1 gap-2">
                  {jiraStatus.projects.slice(0, 5).map((project) => (
                    <div
                      key={project.id}
                      className="flex items-center space-x-3 p-2 bg-white border border-gray-200 rounded-md hover:bg-gray-50 transition-colors"
                    >
                      <div className="w-8 h-8 bg-blue-100 rounded flex items-center justify-center">
                        <span className="text-blue-600 font-medium text-sm">
                          {project.key}
                        </span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {project.name}
                        </p>
                        <p className="text-xs text-gray-500 truncate">
                          {project.projectTypeKey}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Issues Section */}
            {jiraStatus.issues.length > 0 && (
              <div>
                <h4 className="text-sm font-medium text-gray-900 mb-3">
                  Recent Issues
                </h4>
                <div className="space-y-2">
                  {jiraStatus.issues.slice(0, 5).map((issue) => (
                    <div
                      key={issue.id}
                      className="flex items-center justify-between p-3 bg-white border border-gray-200 rounded-md hover:bg-gray-50 transition-colors"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center space-x-2 mb-1">
                          <span className="text-xs font-medium text-blue-600 bg-blue-100 px-2 py-1 rounded">
                            {issue.key}
                          </span>
                          <span
                            className={`text-xs font-medium px-2 py-1 rounded ${
                              issue.status.category === "done"
                                ? "bg-green-100 text-green-800"
                                : issue.status.category === "indeterminate"
                                  ? "bg-yellow-100 text-yellow-800"
                                  : "bg-gray-100 text-gray-800"
                            }`}
                          >
                            {issue.status.name}
                          </span>
                        </div>
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {issue.summary}
                        </p>
                        {issue.assignee && (
                          <p className="text-xs text-gray-500 mt-1">
                            Assigned to: {issue.assignee.name}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Error Display */}
        {jiraStatus.error && (
          <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-sm text-red-700">{jiraStatus.error}</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default JiraDesktopManager;
