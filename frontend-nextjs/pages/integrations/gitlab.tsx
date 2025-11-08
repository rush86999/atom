import React, { useState, useEffect } from "react";
import { NextPage } from "next";
import Head from "next/head";
import { useRouter } from "next/router";
import {
  GitLabManager,
  GitLabSearch,
} from "../../../src/ui-shared/integrations/gitlab";

const GitLabIntegrationPage: NextPage = () => {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<string>("overview");
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [projects, setProjects] = useState<any[]>([]);
  const [issues, setIssues] = useState<any[]>([]);
  const [mergeRequests, setMergeRequests] = useState<any[]>([]);
  const [pipelines, setPipelines] = useState<any[]>([]);
  const [stats, setStats] = useState({
    totalProjects: 0,
    openIssues: 0,
    activeMRs: 0,
    runningPipelines: 0,
    failedPipelines: 0,
    successfulPipelines: 0,
  });

  useEffect(() => {
    // Check GitLab connection status
    const checkConnection = async () => {
      try {
        const response = await fetch("/api/integrations/gitlab/status");
        if (response.ok) {
          const data = await response.json();
          setIsConnected(data.connected || false);
          if (data.connected) {
            loadInitialData();
          }
        }
      } catch (error) {
        console.error("Failed to check GitLab connection:", error);
        setIsConnected(false);
      } finally {
        setLoading(false);
      }
    };

    checkConnection();
  }, []);

  const loadInitialData = async () => {
    try {
      // Load projects
      const projectsResponse = await fetch("/api/integrations/gitlab/projects");
      if (projectsResponse.ok) {
        const projectsData = await projectsResponse.json();
        setProjects(projectsData.projects || []);
        setStats((prev) => ({
          ...prev,
          totalProjects: projectsData.projects?.length || 0,
        }));
      }

      // Load issues
      const issuesResponse = await fetch("/api/integrations/gitlab/issues");
      if (issuesResponse.ok) {
        const issuesData = await issuesResponse.json();
        setIssues(issuesData.issues || []);
        setStats((prev) => ({
          ...prev,
          openIssues: issuesData.issues?.length || 0,
        }));
      }

      // Load merge requests
      const mrResponse = await fetch("/api/integrations/gitlab/merge-requests");
      if (mrResponse.ok) {
        const mrData = await mrResponse.json();
        setMergeRequests(mrData.merge_requests || []);
        setStats((prev) => ({
          ...prev,
          activeMRs: mrData.merge_requests?.length || 0,
        }));
      }

      // Load pipelines
      const pipelinesResponse = await fetch(
        "/api/integrations/gitlab/pipelines",
      );
      if (pipelinesResponse.ok) {
        const pipelinesData = await pipelinesResponse.json();
        setPipelines(pipelinesData.pipelines || []);

        const running =
          pipelinesData.pipelines?.filter((p: any) => p.status === "running")
            .length || 0;
        const failed =
          pipelinesData.pipelines?.filter((p: any) => p.status === "failed")
            .length || 0;
        const successful =
          pipelinesData.pipelines?.filter((p: any) => p.status === "success")
            .length || 0;

        setStats((prev) => ({
          ...prev,
          runningPipelines: running,
          failedPipelines: failed,
          successfulPipelines: successful,
        }));
      }
    } catch (error) {
      console.error("Failed to load GitLab data:", error);
    }
  };

  const tabs = [
    { id: "overview", name: "Overview", icon: "📊" },
    { id: "projects", name: "Projects", icon: "📁" },
    { id: "issues", name: "Issues", icon: "🐛" },
    { id: "merge-requests", name: "Merge Requests", icon: "🔄" },
    { id: "pipelines", name: "Pipelines", icon: "⚙️" },
    { id: "search", name: "Advanced Search", icon: "🔍" },
    { id: "settings", name: "Settings", icon: "⚙️" },
  ];

  const renderTabContent = () => {
    switch (activeTab) {
      case "overview":
        return (
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-semibold mb-4">
                GitLab Integration Overview
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="bg-blue-50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-blue-600">
                    {stats.totalProjects}
                  </div>
                  <div className="text-sm text-blue-800">Total Projects</div>
                </div>
                <div className="bg-green-50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-green-600">
                    {stats.openIssues}
                  </div>
                  <div className="text-sm text-green-800">Open Issues</div>
                </div>
                <div className="bg-purple-50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-purple-600">
                    {stats.activeMRs}
                  </div>
                  <div className="text-sm text-purple-800">Active MRs</div>
                </div>
                <div className="bg-orange-50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-orange-600">
                    {stats.runningPipelines}
                  </div>
                  <div className="text-sm text-orange-800">
                    Running Pipelines
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4">Pipeline Status</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-green-50 rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-green-600">
                    {stats.successfulPipelines}
                  </div>
                  <div className="text-sm text-green-800">Successful</div>
                </div>
                <div className="bg-red-50 rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-red-600">
                    {stats.failedPipelines}
                  </div>
                  <div className="text-sm text-red-800">Failed</div>
                </div>
                <div className="bg-yellow-50 rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold text-yellow-600">
                    {stats.runningPipelines}
                  </div>
                  <div className="text-sm text-yellow-800">Running</div>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4">Quick Actions</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <button
                  onClick={() => setActiveTab("projects")}
                  className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Browse Projects
                </button>
                <button
                  onClick={() => setActiveTab("issues")}
                  className="bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  View Issues
                </button>
                <button
                  onClick={() => setActiveTab("merge-requests")}
                  className="bg-purple-500 hover:bg-purple-600 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Merge Requests
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
                  Advanced Search
                </button>
                <button
                  onClick={() => window.open("https://gitlab.com", "_blank")}
                  className="bg-gray-500 hover:bg-gray-600 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Open GitLab
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-semibold mb-4">Recent Projects</h3>
                <div className="space-y-3">
                  {projects.slice(0, 5).map((project, index) => (
                    <div
                      key={index}
                      className="border rounded-lg p-3 hover:bg-gray-50 transition-colors"
                    >
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <div className="font-medium text-gray-900">
                            {project.name}
                          </div>
                          <div className="text-sm text-gray-600">
                            {project.description || "No description"}
                          </div>
                          <div className="text-xs text-gray-500 mt-1">
                            Last updated:{" "}
                            {new Date(
                              project.last_activity_at,
                            ).toLocaleDateString()}
                          </div>
                        </div>
                        <div className="text-xs text-gray-500">
                          {project.star_count} ⭐
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="text-lg font-semibold mb-4">Recent Issues</h3>
                <div className="space-y-3">
                  {issues.slice(0, 5).map((issue, index) => (
                    <div
                      key={index}
                      className="border rounded-lg p-3 hover:bg-gray-50 transition-colors"
                    >
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <div className="font-medium text-gray-900">
                            {issue.title}
                          </div>
                          <div className="text-sm text-gray-600">
                            #{issue.iid} • {issue.state}
                          </div>
                          <div className="text-xs text-gray-500 mt-1">
                            Created:{" "}
                            {new Date(issue.created_at).toLocaleDateString()}
                          </div>
                        </div>
                        <div
                          className={`text-xs px-2 py-1 rounded-full ${
                            issue.state === "opened"
                              ? "bg-green-100 text-green-800"
                              : "bg-gray-100 text-gray-800"
                          }`}
                        >
                          {issue.state}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        );

      case "projects":
        return (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">GitLab Projects</h2>
            <p className="text-gray-600 mb-4">
              Browse and manage your GitLab repositories and projects.
            </p>
            <div className="border rounded-lg p-4">
              <GitLabManager view="projects" />
            </div>
          </div>
        );

      case "issues":
        return (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">GitLab Issues</h2>
            <p className="text-gray-600 mb-4">
              Track, create, and manage issues across your GitLab projects.
            </p>
            <div className="border rounded-lg p-4">
              <GitLabManager view="issues" />
            </div>
          </div>
        );

      case "merge-requests":
        return (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">
              GitLab Merge Requests
            </h2>
            <p className="text-gray-600 mb-4">
              Review and manage merge requests across your repositories.
            </p>
            <div className="border rounded-lg p-4">
              <GitLabManager view="merge-requests" />
            </div>
          </div>
        );

      case "pipelines":
        return (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">
              GitLab CI/CD Pipelines
            </h2>
            <p className="text-gray-600 mb-4">
              Monitor and trigger CI/CD pipelines for your projects.
            </p>
            <div className="border rounded-lg p-4">
              <GitLabManager view="pipelines" />
            </div>
          </div>
        );

      case "search":
        return (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">
              Advanced GitLab Search
            </h2>
            <p className="text-gray-600 mb-4">
              Search across all your GitLab data with advanced filters and
              semantic search capabilities.
            </p>
            <div className="border rounded-lg p-4">
              <GitLabSearch
                data={[...projects, ...issues, ...mergeRequests, ...pipelines]}
                dataType="all"
                onSearch={(results: any[], filters: any, sort: any) => {
                  console.log("Search results:", results);
                  console.log("Filters:", filters);
                  console.log("Sort:", sort);
                }}
                loading={loading}
                totalCount={
                  projects.length +
                  issues.length +
                  mergeRequests.length +
                  pipelines.length
                }
              />
            </div>
          </div>
        );

      case "settings":
        return (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">GitLab Settings</h2>
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
                  Configure GitLab OAuth integration for secure access.
                </p>
                <button
                  onClick={() => {
                    // Trigger OAuth flow
                    window.location.href = "/api/integrations/gitlab/authorize";
                  }}
                  className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Connect GitLab Account
                </button>
              </div>

              <div className="border rounded-lg p-4">
                <h3 className="text-lg font-medium mb-2">API Configuration</h3>
                <p className="text-sm text-gray-600 mb-4">
                  Manage GitLab API settings and access tokens.
                </p>
                <div className="space-y-2">
                  <input
                    type="text"
                    placeholder="GitLab Instance URL"
                    className="w-full px-3 py-2 border rounded-lg"
                    defaultValue="https://gitlab.com"
                  />
                  <input
                    type="password"
                    placeholder="Personal Access Token"
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
                  Configure how often ATOM syncs with your GitLab instance.
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
            <h2 className="text-xl font-semibold">GitLab Integration</h2>
            <p className="text-gray-600">Select a tab to get started.</p>
          </div>
        );
    }
  };

  return (
    <>
      <Head>
        <title>GitLab Integration | ATOM</title>
        <meta
          name="description"
          content="GitLab integration for ATOM platform"
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
                  <div className="w-10 h-10 bg-orange-500 rounded-lg flex items-center justify-center">
                    <span className="text-white font-bold">GL</span>
                  </div>
                  <div>
                    <h1 className="text-2xl font-bold text-gray-900">
                      GitLab Integration
                    </h1>
                    <p className="text-gray-600">
                      Manage your GitLab repositories and CI/CD pipelines
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

export default GitLabIntegrationPage;
