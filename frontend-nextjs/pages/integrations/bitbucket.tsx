import React, { useState, useEffect } from "react";
import { NextPage } from "next";
import Head from "next/head";
import { useRouter } from "next/router";

const BitbucketIntegrationPage: NextPage = () => {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<string>("overview");
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [workspaces, setWorkspaces] = useState<any[]>([]);
  const [repositories, setRepositories] = useState<any[]>([]);
  const [pullRequests, setPullRequests] = useState<any[]>([]);
  const [pipelines, setPipelines] = useState<any[]>([]);
  const [issues, setIssues] = useState<any[]>([]);
  const [stats, setStats] = useState({
    totalWorkspaces: 0,
    totalRepositories: 0,
    openPRs: 0,
    runningPipelines: 0,
    openIssues: 0,
  });

  useEffect(() => {
    // Check Bitbucket connection status
    const checkConnection = async () => {
      try {
        const accessToken = localStorage.getItem("bitbucket_access_token");
        if (accessToken) {
          const response = await fetch("/api/integrations/bitbucket/health", {
            headers: {
              Authorization: `Bearer ${accessToken}`,
            },
          });
          if (response.ok) {
            const data = await response.json();
            setIsConnected(data.status === "healthy");
            if (data.status === "healthy") {
              loadInitialData(accessToken);
            }
          }
        } else {
          setIsConnected(false);
        }
      } catch (error) {
        console.error("Failed to check Bitbucket connection:", error);
        setIsConnected(false);
      } finally {
        setLoading(false);
      }
    };

    checkConnection();
  }, []);

  const loadInitialData = async (accessToken: string) => {
    try {
      // Load workspaces
      const workspacesResponse = await fetch(
        "/api/integrations/bitbucket/workspaces",
        {
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        },
      );
      if (workspacesResponse.ok) {
        const workspacesData = await workspacesResponse.json();
        setWorkspaces(workspacesData.workspaces || []);
        setStats((prev) => ({
          ...prev,
          totalWorkspaces: workspacesData.workspaces?.length || 0,
        }));
      }

      // Load repositories
      const reposResponse = await fetch(
        "/api/integrations/bitbucket/repositories",
        {
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        },
      );
      if (reposResponse.ok) {
        const reposData = await reposResponse.json();
        setRepositories(reposData.repositories || []);
        setStats((prev) => ({
          ...prev,
          totalRepositories: reposData.repositories?.length || 0,
        }));
      }

      // Load pull requests
      const prResponse = await fetch(
        "/api/integrations/bitbucket/pull-requests",
        {
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        },
      );
      if (prResponse.ok) {
        const prData = await prResponse.json();
        setPullRequests(prData.pull_requests || []);
        setStats((prev) => ({
          ...prev,
          openPRs: prData.pull_requests?.length || 0,
        }));
      }

      // Load pipelines
      const pipelinesResponse = await fetch(
        "/api/integrations/bitbucket/pipelines",
        {
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        },
      );
      if (pipelinesResponse.ok) {
        const pipelinesData = await pipelinesResponse.json();
        setPipelines(pipelinesData.pipelines || []);
        const running =
          pipelinesData.pipelines?.filter(
            (p: any) => p.state?.name === "IN_PROGRESS",
          ).length || 0;
        setStats((prev) => ({
          ...prev,
          runningPipelines: running,
        }));
      }

      // Load issues
      const issuesResponse = await fetch("/api/integrations/bitbucket/issues", {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      if (issuesResponse.ok) {
        const issuesData = await issuesResponse.json();
        setIssues(issuesData.issues || []);
        setStats((prev) => ({
          ...prev,
          openIssues: issuesData.issues?.length || 0,
        }));
      }
    } catch (error) {
      console.error("Failed to load Bitbucket data:", error);
    }
  };

  const handleConnect = async () => {
    try {
      const response = await fetch("/api/integrations/bitbucket/authorize");
      if (response.ok) {
        const data = await response.json();
        window.location.href = data.authorization_url;
      }
    } catch (error) {
      console.error("Failed to start Bitbucket OAuth flow:", error);
    }
  };

  const tabs = [
    { id: "overview", name: "Overview", icon: "📊" },
    { id: "workspaces", name: "Workspaces", icon: "🏢" },
    { id: "repositories", name: "Repositories", icon: "📁" },
    { id: "pull-requests", name: "Pull Requests", icon: "🔄" },
    { id: "pipelines", name: "Pipelines", icon: "⚙️" },
    { id: "issues", name: "Issues", icon: "🐛" },
    { id: "search", name: "Code Search", icon: "🔍" },
    { id: "settings", name: "Settings", icon: "⚙️" },
  ];

  const renderTabContent = () => {
    switch (activeTab) {
      case "overview":
        return (
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-semibold mb-4">
                Bitbucket Integration Overview
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
                <div className="bg-blue-50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-blue-600">
                    {stats.totalWorkspaces}
                  </div>
                  <div className="text-sm text-blue-800">Workspaces</div>
                </div>
                <div className="bg-green-50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-green-600">
                    {stats.totalRepositories}
                  </div>
                  <div className="text-sm text-green-800">Repositories</div>
                </div>
                <div className="bg-purple-50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-purple-600">
                    {stats.openPRs}
                  </div>
                  <div className="text-sm text-purple-800">Open PRs</div>
                </div>
                <div className="bg-orange-50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-orange-600">
                    {stats.runningPipelines}
                  </div>
                  <div className="text-sm text-orange-800">
                    Running Pipelines
                  </div>
                </div>
                <div className="bg-red-50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-red-600">
                    {stats.openIssues}
                  </div>
                  <div className="text-sm text-red-800">Open Issues</div>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4">Quick Actions</h3>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <button
                  onClick={() => setActiveTab("repositories")}
                  className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Browse Repositories
                </button>
                <button
                  onClick={() => setActiveTab("pull-requests")}
                  className="bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  View Pull Requests
                </button>
                <button
                  onClick={() => setActiveTab("pipelines")}
                  className="bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  CI/CD Pipelines
                </button>
                <button
                  onClick={() => setActiveTab("search")}
                  className="bg-teal-500 hover:bg-teal-600 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Search Code
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-semibold mb-4">
                  Recent Repositories
                </h3>
                <div className="space-y-3">
                  {repositories.slice(0, 5).map((repo, index) => (
                    <div
                      key={index}
                      className="border rounded-lg p-3 hover:bg-gray-50 transition-colors"
                    >
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <div className="font-medium text-gray-900">
                            {repo.name}
                          </div>
                          <div className="text-sm text-gray-600">
                            {repo.description || "No description"}
                          </div>
                          <div className="text-xs text-gray-500 mt-1">
                            {repo.workspace?.slug} •{" "}
                            {repo.language || "Unknown"}
                          </div>
                        </div>
                        <div className="text-xs text-gray-500">
                          {repo.size} KB
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-semibold mb-4">
                  Recent Pull Requests
                </h3>
                <div className="space-y-3">
                  {pullRequests.slice(0, 5).map((pr, index) => (
                    <div
                      key={index}
                      className="border rounded-lg p-3 hover:bg-gray-50 transition-colors"
                    >
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <div className="font-medium text-gray-900">
                            {pr.title}
                          </div>
                          <div className="text-sm text-gray-600">
                            #{pr.id} • {pr.state}
                          </div>
                          <div className="text-xs text-gray-500 mt-1">
                            Created:{" "}
                            {new Date(pr.created_on).toLocaleDateString()}
                          </div>
                        </div>
                        <div
                          className={`text-xs px-2 py-1 rounded-full ${
                            pr.state === "OPEN"
                              ? "bg-green-100 text-green-800"
                              : pr.state === "MERGED"
                                ? "bg-purple-100 text-purple-800"
                                : "bg-gray-100 text-gray-800"
                          }`}
                        >
                          {pr.state}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        );

      case "workspaces":
        return (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Bitbucket Workspaces</h2>
            <p className="text-gray-600 mb-4">
              Manage your Bitbucket workspaces and teams.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {workspaces.map((workspace, index) => (
                <div
                  key={index}
                  className="border rounded-lg p-4 hover:shadow-md transition-shadow"
                >
                  <div className="flex items-center space-x-3 mb-3">
                    <div className="w-10 h-10 bg-blue-500 rounded-lg flex items-center justify-center">
                      <span className="text-white font-bold text-sm">
                        {workspace.slug?.charAt(0).toUpperCase() || "W"}
                      </span>
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-900">
                        {workspace.name}
                      </h3>
                      <p className="text-sm text-gray-600">{workspace.slug}</p>
                    </div>
                  </div>
                  <div className="text-xs text-gray-500">
                    Type: {workspace.type || "Team"}
                  </div>
                  <div className="text-xs text-gray-500">
                    Created:{" "}
                    {new Date(workspace.created_on).toLocaleDateString()}
                  </div>
                </div>
              ))}
            </div>
          </div>
        );

      case "repositories":
        return (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">
              Bitbucket Repositories
            </h2>
            <p className="text-gray-600 mb-4">
              Browse and manage your Bitbucket repositories.
            </p>
            <div className="space-y-4">
              {repositories.map((repo, index) => (
                <div
                  key={index}
                  className="border rounded-lg p-4 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-2">
                        <h3 className="font-semibold text-gray-900">
                          {repo.name}
                        </h3>
                        <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">
                          {repo.language || "Unknown"}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mb-2">
                        {repo.description || "No description available"}
                      </p>
                      <div className="flex space-x-4 text-xs text-gray-500">
                        <span>Workspace: {repo.workspace?.slug}</span>
                        <span>Size: {repo.size} KB</span>
                        <span>
                          Updated:{" "}
                          {new Date(repo.updated_on).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                    <div className="flex space-x-2">
                      <button className="text-blue-600 hover:text-blue-800 text-sm">
                        View
                      </button>
                      <button className="text-green-600 hover:text-green-800 text-sm">
                        Clone
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );

      case "pull-requests":
        return (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">
              Bitbucket Pull Requests
            </h2>
            <p className="text-gray-600 mb-4">
              Review and manage pull requests across your repositories.
            </p>
            <div className="space-y-4">
              {pullRequests.map((pr, index) => (
                <div
                  key={index}
                  className="border rounded-lg p-4 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-2">
                        <h3 className="font-semibold text-gray-900">
                          {pr.title}
                        </h3>
                        <span
                          className={`text-xs px-2 py-1 rounded-full ${
                            pr.state === "OPEN"
                              ? "bg-green-100 text-green-800"
                              : pr.state === "MERGED"
                                ? "bg-purple-100 text-purple-800"
                                : "bg-gray-100 text-gray-800"
                          }`}
                        >
                          {pr.state}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mb-2">
                        #{pr.id} • {pr.source?.branch?.name} →{" "}
                        {pr.destination?.branch?.name}
                      </p>
                      <div className="flex space-x-4 text-xs text-gray-500">
                        <span>Author: {pr.author?.display_name}</span>
                        <span>
                          Created:{" "}
                          {new Date(pr.created_on).toLocaleDateString()}
                        </span>
                        <span>
                          Updated:{" "}
                          {new Date(pr.updated_on).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                    <div className="flex space-x-2">
                      <button className="text-blue-600 hover:text-blue-800 text-sm">
                        Review
                      </button>
                      <button className="text-green-600 hover:text-green-800 text-sm">
                        Approve
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );

      case "pipelines":
        return (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Bitbucket Pipelines</h2>
            <p className="text-gray-600 mb-4">
              Monitor and manage CI/CD pipelines for your repositories.
            </p>
            <div className="space-y-4">
              {pipelines.map((pipeline, index) => (
                <div
                  key={index}
                  className="border rounded-lg p-4 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-2">
                        <h3 className="font-semibold text-gray-900">
                          Pipeline #{pipeline.build_number}
                        </h3>
                        <span
                          className={`text-xs px-2 py-1 rounded-full ${
                            pipeline.state?.name === "SUCCESSFUL"
                              ? "bg-green-100 text-green-800"
                              : pipeline.state?.name === "FAILED"
                                ? "bg-red-100 text-red-800"
                                : pipeline.state?.name === "IN_PROGRESS"
                                  ? "bg-blue-100 text-blue-800"
                                  : "bg-gray-100 text-gray-800"
                          }`}
                        >
                          {pipeline.state?.name || "UNKNOWN"}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mb-2">
                        Repository: {pipeline.repository?.name} • Trigger:{" "}
                        {pipeline.trigger?.name}
                      </p>
                      <div className="flex space-x-4 text-xs text-gray-500">
                        <span>
                          Created:{" "}
                          {new Date(pipeline.created_on).toLocaleDateString()}
                        </span>
                        <span>
                          Duration: {pipeline.build_seconds_used || 0}s
                        </span>
                        <span>
                          Steps:{" "}
                          {pipeline.target?.commit?.hash?.slice(0, 7) || "N/A"}
                        </span>
                      </div>
                    </div>
                    <div className="flex space-x-2">
                      <button className="text-blue-600 hover:text-blue-800 text-sm">
                        View Logs
                      </button>
                      <button className="text-green-600 hover:text-green-800 text-sm">
                        Rerun
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );

      case "issues":
        return (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Bitbucket Issues</h2>
            <p className="text-gray-600 mb-4">
              Track and manage issues across your repositories.
            </p>
            <div className="space-y-4">
              {issues.map((issue, index) => (
                <div
                  key={index}
                  className="border rounded-lg p-4 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center space-x-2 mb-2">
                        <h3 className="font-semibold text-gray-900">
                          {issue.title}
                        </h3>
                        <span
                          className={`text-xs px-2 py-1 rounded-full ${
                            issue.state === "open"
                              ? "bg-green-100 text-green-800"
                              : issue.state === "closed"
                                ? "bg-red-100 text-red-800"
                                : "bg-gray-100 text-gray-800"
                          }`}
                        >
                          {issue.state}
                        </span>
                        <span
                          className={`text-xs px-2 py-1 rounded-full ${
                            issue.kind === "bug"
                              ? "bg-red-100 text-red-800"
                              : issue.kind === "enhancement"
                                ? "bg-blue-100 text-blue-800"
                                : "bg-gray-100 text-gray-800"
                          }`}
                        >
                          {issue.kind}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mb-2">
                        {issue.content?.raw || "No description"}
                      </p>
                      <div className="flex space-x-4 text-xs text-gray-500">
                        <span>Priority: {issue.priority}</span>
                        <span>Reporter: {issue.reporter?.display_name}</span>
                        <span>
                          Created:{" "}
                          {new Date(issue.created_on).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                    <div className="flex space-x-2">
                      <button className="text-blue-600 hover:text-blue-800 text-sm">
                        View
                      </button>
                      <button className="text-green-600 hover:text-green-800 text-sm">
                        Edit
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );

      case "search":
        return (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">
              Bitbucket Code Search
            </h2>
            <p className="text-gray-600 mb-4">
              Search across all your Bitbucket repositories and code.
            </p>
            <div className="space-y-4">
              <div className="flex space-x-4">
                <input
                  type="text"
                  placeholder="Search code..."
                  className="flex-1 px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button className="bg-blue-500 hover:bg-blue-600 text-white px-6 py-2 rounded-lg transition-colors">
                  Search
                </button>
              </div>
              <div className="text-sm text-gray-500">
                Search across {stats.totalRepositories} repositories and{" "}
                {stats.totalWorkspaces} workspaces
              </div>
            </div>
          </div>
        );

      case "settings":
        return (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Bitbucket Settings</h2>
            <div className="space-y-4">
              <div className="border rounded-lg p-4">
                <h3 className="text-lg font-medium mb-2">Connection Status</h3>
                <div className="flex items-center space-x-2">
                  <div
                    className={`w-3 h-3 rounded-full ${
                      isConnected ? "bg-green-500" : "bg-red-500"
                    }`}
                  ></div>
                  <span>{isConnected ? "Connected" : "Disconnected"}</span>
                </div>
              </div>

              <div className="border rounded-lg p-4">
                <h3 className="text-lg font-medium mb-2">
                  OAuth Configuration
                </h3>
                <p className="text-sm text-gray-600 mb-4">
                  Configure Bitbucket OAuth integration for secure access.
                </p>
                {!isConnected ? (
                  <button
                    onClick={handleConnect}
                    className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg transition-colors"
                  >
                    Connect Bitbucket Account
                  </button>
                ) : (
                  <button
                    onClick={() => {
                      localStorage.removeItem("bitbucket_access_token");
                      localStorage.removeItem("bitbucket_refresh_token");
                      setIsConnected(false);
                      setWorkspaces([]);
                      setRepositories([]);
                      setPullRequests([]);
                      setPipelines([]);
                      setIssues([]);
                    }}
                    className="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded-lg transition-colors"
                  >
                    Disconnect Bitbucket
                  </button>
                )}
              </div>

              <div className="border rounded-lg p-4">
                <h3 className="text-lg font-medium mb-2">API Configuration</h3>
                <p className="text-sm text-gray-600 mb-4">
                  Manage Bitbucket API settings and access tokens.
                </p>
                <div className="space-y-2">
                  <input
                    type="text"
                    placeholder="Bitbucket Workspace"
                    className="w-full px-3 py-2 border rounded-lg"
                  />
                  <input
                    type="password"
                    placeholder="App Password"
                    className="w-full px-3 py-2 border rounded-lg"
                  />
                  <button className="bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded-lg transition-colors">
                    Save Configuration
                  </button>
                </div>
              </div>

              <div className="border rounded-lg p-4">
                <h3 className="text-lg font-medium mb-2">Sync Settings</h3>
                <p className="text-sm text-gray-600 mb-4">
                  Configure how often ATOM syncs with your Bitbucket instance.
                </p>
                <div className="space-y-2">
                  <div className="flex items-center space-x-2">
                    <input
                      type="radio"
                      id="sync-realtime"
                      name="sync"
                      defaultChecked
                    />
                    <label htmlFor="sync-realtime" className="text-sm">
                      Real-time sync
                    </label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <input type="radio" id="sync-hourly" name="sync" />
                    <label htmlFor="sync-hourly" className="text-sm">
                      Hourly sync
                    </label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <input type="radio" id="sync-daily" name="sync" />
                    <label htmlFor="sync-daily" className="text-sm">
                      Daily sync
                    </label>
                  </div>
                </div>
              </div>

              <div className="border rounded-lg p-4">
                <h3 className="text-lg font-medium mb-2">Search Settings</h3>
                <p className="text-sm text-gray-600 mb-4">
                  Configure search behavior and indexing preferences.
                </p>
                <div className="space-y-2">
                  <div className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      id="semantic-search"
                      defaultChecked
                    />
                    <label htmlFor="semantic-search" className="text-sm">
                      Enable semantic search
                    </label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <input type="checkbox" id="auto-index" defaultChecked />
                    <label htmlFor="auto-index" className="text-sm">
                      Auto-index new content
                    </label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <input type="checkbox" id="search-history" />
                    <label htmlFor="search-history" className="text-sm">
                      Save search history
                    </label>
                  </div>
                </div>
              </div>
            </div>
          </div>
        );

      default:
        return (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold">Bitbucket Integration</h2>
            <p className="text-gray-600">Select a tab to get started.</p>
          </div>
        );
    }
  };

  return (
    <>
      <Head>
        <title>Bitbucket Integration | ATOM</title>
        <meta
          name="description"
          content="Bitbucket integration for ATOM platform"
        />
      </Head>

      <div className="min-h-screen bg-gray-50">
        {/* Header */}
        <div className="bg-white shadow">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center py-6">
              <div className="flex items-center">
                <button
                  onClick={() => router.push("/integrations")}
                  className="mr-4 text-gray-500 hover:text-gray-700"
                >
                  ← Back to Integrations
                </button>
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 bg-blue-500 rounded-lg flex items-center justify-center">
                    <span className="text-white font-bold">BB</span>
                  </div>
                  <div>
                    <h1 className="text-2xl font-bold text-gray-900">
                      Bitbucket Integration
                    </h1>
                    <p className="text-gray-600">
                      Manage your Bitbucket repositories, pull requests, and
                      CI/CD pipelines
                    </p>
                  </div>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <div
                  className={`px-3 py-1 rounded-full text-sm font-medium ${
                    isConnected
                      ? "bg-green-100 text-green-800"
                      : "bg-red-100 text-red-800"
                  }`}
                >
                  {loading
                    ? "Checking..."
                    : isConnected
                      ? "Connected"
                      : "Disconnected"}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="bg-white border-b">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <nav className="flex space-x-8 overflow-x-auto">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm ${
                    activeTab === tab.id
                      ? "border-blue-500 text-blue-600"
                      : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
                  }`}
                >
                  <span className="mr-2">{tab.icon}</span>
                  {tab.name}
                </button>
              ))}
            </nav>
          </div>
        </div>

        {/* Main Content */}
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {renderTabContent()}
        </main>
      </div>
    </>
  );
};

export default BitbucketIntegrationPage;
