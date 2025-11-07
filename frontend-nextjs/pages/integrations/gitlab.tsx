import React, { useState, useEffect } from 'react';
import { NextPage } from 'next';
import Head from 'next/head';
import { GitLabManager } from '../../../src/ui-shared/integrations/gitlab';
import { useRouter } from 'next/router';

const GitLabIntegrationPage: NextPage = () => {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    // Check GitLab connection status
    const checkConnection = async () => {
      try {
        const response = await fetch('/api/integrations/gitlab/status');
        if (response.ok) {
          const data = await response.json();
          setIsConnected(data.connected || false);
        }
      } catch (error) {
        console.error('Failed to check GitLab connection:', error);
        setIsConnected(false);
      } finally {
        setLoading(false);
      }
    };

    checkConnection();
  }, []);

  const tabs = [
    { id: 'overview', name: 'Overview', icon: '📊' },
    { id: 'projects', name: 'Projects', icon: '📁' },
    { id: 'issues', name: 'Issues', icon: '🐛' },
    { id: 'merge-requests', name: 'Merge Requests', icon: '🔄' },
    { id: 'pipelines', name: 'Pipelines', icon: '⚙️' },
    { id: 'settings', name: 'Settings', icon: '⚙️' },
  ];

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return (
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-semibold mb-4">GitLab Integration Overview</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-blue-50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-blue-600">Projects</div>
                  <div className="text-sm text-blue-800">Manage repositories</div>
                </div>
                <div className="bg-green-50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-green-600">Issues</div>
                  <div className="text-sm text-green-800">Track and create issues</div>
                </div>
                <div className="bg-purple-50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-purple-600">CI/CD</div>
                  <div className="text-sm text-purple-800">Monitor pipelines</div>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4">Quick Actions</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <button
                  onClick={() => setActiveTab('projects')}
                  className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Browse Projects
                </button>
                <button
                  onClick={() => setActiveTab('issues')}
                  className="bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  View Issues
                </button>
                <button
                  onClick={() => setActiveTab('merge-requests')}
                  className="bg-purple-500 hover:bg-purple-600 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Merge Requests
                </button>
                <button
                  onClick={() => setActiveTab('pipelines')}
                  className="bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  CI/CD Pipelines
                </button>
              </div>
            </div>
          </div>
        );

      case 'projects':
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

      case 'issues':
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

      case 'merge-requests':
        return (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">GitLab Merge Requests</h2>
            <p className="text-gray-600 mb-4">
              Review and manage merge requests across your repositories.
            </p>
            <div className="border rounded-lg p-4">
              <GitLabManager view="merge-requests" />
            </div>
          </div>
        );

      case 'pipelines':
        return (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">GitLab CI/CD Pipelines</h2>
            <p className="text-gray-600 mb-4">
              Monitor and trigger CI/CD pipelines for your projects.
            </p>
            <div className="border rounded-lg p-4">
              <GitLabManager view="pipelines" />
            </div>
          </div>
        );

      case 'settings':
        return (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">GitLab Settings</h2>
            <div className="space-y-4">
              <div className="border rounded-lg p-4">
                <h3 className="text-lg font-medium mb-2">Connection Status</h3>
                <div className="flex items-center space-x-2">
                  <div
                    className={`w-3 h-3 rounded-full ${
                      isConnected ? 'bg-green-500' : 'bg-red-500'
                    }`}
                  ></div>
                  <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
                </div>
              </div>

              <div className="border rounded-lg p-4">
                <h3 className="text-lg font-medium mb-2">OAuth Configuration</h3>
                <p className="text-sm text-gray-600 mb-4">
                  Configure GitLab OAuth integration for secure access.
                </p>
                <button
                  onClick={() => {
                    // Trigger OAuth flow
                    window.location.href = '/api/integrations/gitlab/authorize';
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
        <meta name="description" content="GitLab integration for ATOM platform" />
      </Head>

      <div className="min-h-screen bg-gray-50">
        {/* Header */}
        <div className="bg-white shadow">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center py-6">
              <div className="flex items-center">
                <button
                  onClick={() => router.push('/integrations')}
                  className="mr-4 text-gray-500 hover:text-gray-700"
                >
                  ← Back to Integrations
                </button>
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 bg-orange-500 rounded-lg flex items-center justify-center">
                    <span className="text-white font-bold">GL</span>
                  </div>
                  <div>
                    <h1 className="text-2xl font-bold text-gray-900">GitLab Integration</h1>
                    <p className="text-gray-600">Manage your GitLab repositories and CI/CD pipelines</p>
                  </div>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <div
                  className={`px-3 py-1 rounded-full text-sm font-medium ${
                    isConnected
                      ? 'bg-green-100 text-green-800'
                      : 'bg-red-100 text-red-800'
                  }`}
                >
                  {loading ? 'Checking...' : isConnected ? 'Connected' : 'Disconnected'}
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
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
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
