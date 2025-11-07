import React, { useState, useEffect } from 'react';
import { NextPage } from 'next';
import Head from 'next/head';
import { useRouter } from 'next/router';

const GmailIntegrationPage: NextPage = () => {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [emails, setEmails] = useState<any[]>([]);
  const [emailStats, setEmailStats] = useState({
    total: 0,
    unread: 0,
    important: 0,
    starred: 0
  });

  useEffect(() => {
    // Check Gmail connection status
    const checkConnection = async () => {
      try {
        const response = await fetch('/api/integrations/gmail/status');
        if (response.ok) {
          const data = await response.json();
          setIsConnected(data.connected || false);
        }
      } catch (error) {
        console.error('Failed to check Gmail connection:', error);
        setIsConnected(false);
      } finally {
        setLoading(false);
      }
    };

    checkConnection();
  }, []);

  const tabs = [
    { id: 'overview', name: 'Overview', icon: '📊' },
    { id: 'inbox', name: 'Inbox', icon: '📥' },
    { id: 'compose', name: 'Compose', icon: '✏️' },
    { id: 'labels', name: 'Labels', icon: '🏷️' },
    { id: 'settings', name: 'Settings', icon: '⚙️' },
  ];

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return (
          <div className="space-y-6">
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-xl font-semibold mb-4">Gmail Integration Overview</h2>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-red-50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-red-600">{emailStats.total}</div>
                  <div className="text-sm text-red-800">Total Emails</div>
                </div>
                <div className="bg-blue-50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-blue-600">{emailStats.unread}</div>
                  <div className="text-sm text-blue-800">Unread</div>
                </div>
                <div className="bg-yellow-50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-yellow-600">{emailStats.important}</div>
                  <div className="text-sm text-yellow-800">Important</div>
                </div>
                <div className="bg-purple-50 rounded-lg p-4">
                  <div className="text-2xl font-bold text-purple-600">{emailStats.starred}</div>
                  <div className="text-sm text-purple-800">Starred</div>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4">Quick Actions</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <button
                  onClick={() => setActiveTab('inbox')}
                  className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  View Inbox
                </button>
                <button
                  onClick={() => setActiveTab('compose')}
                  className="bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Compose Email
                </button>
                <button
                  onClick={() => setActiveTab('labels')}
                  className="bg-purple-500 hover:bg-purple-600 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Manage Labels
                </button>
                <button
                  onClick={() => window.open('https://mail.google.com', '_blank')}
                  className="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Open Gmail
                </button>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-semibold mb-4">Recent Emails</h3>
              <div className="space-y-3">
                {emails.length > 0 ? (
                  emails.slice(0, 5).map((email, index) => (
                    <div key={index} className="border rounded-lg p-3 hover:bg-gray-50 transition-colors">
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <div className="font-medium text-gray-900">{email.from}</div>
                          <div className="text-sm text-gray-600">{email.subject}</div>
                          <div className="text-xs text-gray-500 mt-1">{email.preview}</div>
                        </div>
                        <div className="text-xs text-gray-500">{email.time}</div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center text-gray-500 py-8">
                    No emails found. Connect your Gmail account to get started.
                  </div>
                )}
              </div>
            </div>
          </div>
        );

      case 'inbox':
        return (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Gmail Inbox</h2>
            <p className="text-gray-600 mb-4">
              Browse and manage your Gmail inbox with advanced filtering and search capabilities.
            </p>
            <div className="border rounded-lg p-4">
              <div className="flex space-x-4 mb-4">
                <input
                  type="text"
                  placeholder="Search emails..."
                  className="flex-1 px-3 py-2 border rounded-lg"
                />
                <select className="px-3 py-2 border rounded-lg">
                  <option>All Mail</option>
                  <option>Primary</option>
                  <option>Social</option>
                  <option>Promotions</option>
                </select>
              </div>
              <div className="space-y-2">
                <div className="text-center text-gray-500 py-8">
                  Gmail inbox integration coming soon. Connect your account to enable email management.
                </div>
              </div>
            </div>
          </div>
        );

      case 'compose':
        return (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Compose Email</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">To</label>
                <input
                  type="email"
                  placeholder="recipient@example.com"
                  className="w-full px-3 py-2 border rounded-lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Subject</label>
                <input
                  type="text"
                  placeholder="Email subject"
                  className="w-full px-3 py-2 border rounded-lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Message</label>
                <textarea
                  rows={8}
                  placeholder="Write your email message here..."
                  className="w-full px-3 py-2 border rounded-lg"
                />
              </div>
              <div className="flex space-x-3">
                <button className="bg-blue-500 hover:bg-blue-600 text-white px-6 py-2 rounded-lg transition-colors">
                  Send Email
                </button>
                <button className="bg-gray-500 hover:bg-gray-600 text-white px-6 py-2 rounded-lg transition-colors">
                  Save Draft
                </button>
              </div>
            </div>
          </div>
        );

      case 'labels':
        return (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Gmail Labels</h2>
            <p className="text-gray-600 mb-4">
              Manage your Gmail labels and categories for better email organization.
            </p>
            <div className="border rounded-lg p-4">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <div className="border rounded-lg p-4">
                  <div className="font-medium text-gray-900">Primary</div>
                  <div className="text-sm text-gray-600">Personal and important emails</div>
                  <div className="text-xs text-gray-500 mt-2">245 emails</div>
                </div>
                <div className="border rounded-lg p-4">
                  <div className="font-medium text-gray-900">Social</div>
                  <div className="text-sm text-gray-600">Social media notifications</div>
                  <div className="text-xs text-gray-500 mt-2">89 emails</div>
                </div>
                <div className="border rounded-lg p-4">
                  <div className="font-medium text-gray-900">Promotions</div>
                  <div className="text-sm text-gray-600">Marketing and promotional emails</div>
                  <div className="text-xs text-gray-500 mt-2">156 emails</div>
                </div>
                <div className="border rounded-lg p-4">
                  <div className="font-medium text-gray-900">Work</div>
                  <div className="text-sm text-gray-600">Professional and work-related</div>
                  <div className="text-xs text-gray-500 mt-2">432 emails</div>
                </div>
                <div className="border rounded-lg p-4">
                  <div className="font-medium text-gray-900">Important</div>
                  <div className="text-sm text-gray-600">Starred and important messages</div>
                  <div className="text-xs text-gray-500 mt-2">67 emails</div>
                </div>
                <div className="border rounded-lg p-4">
                  <div className="font-medium text-gray-900">Archive</div>
                  <div className="text-sm text-gray-600">Archived emails</div>
                  <div className="text-xs text-gray-500 mt-2">1,234 emails</div>
                </div>
              </div>
            </div>
          </div>
        );

      case 'settings':
        return (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Gmail Settings</h2>
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
                  Configure Gmail OAuth integration for secure email access.
                </p>
                <button
                  onClick={() => {
                    // Trigger OAuth flow
                    window.location.href = '/api/integrations/gmail/authorize';
                  }}
                  className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Connect Gmail Account
                </button>
              </div>

              <div className="border rounded-lg p-4">
                <h3 className="text-lg font-medium mb-2">Sync Settings</h3>
                <p className="text-sm text-gray-600 mb-4">
                  Configure how often ATOM syncs with your Gmail account.
                </p>
                <div className="space-y-2">
                  <div className="flex items-center space-x-2">
                    <input type="radio" id="sync-realtime" name="sync" defaultChecked />
                    <label htmlFor="sync-realtime" className="text-sm">Real-time sync</label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <input type="radio" id="sync-hourly" name="sync" />
                    <label htmlFor="sync-hourly" className="text-sm">Hourly sync</label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <input type="radio" id="sync-daily" name="sync" />
                    <label htmlFor="sync-daily" className="text-sm">Daily sync</label>
                  </div>
                </div>
              </div>

              <div className="border rounded-lg p-4">
                <h3 className="text-lg font-medium mb-2">Privacy & Security</h3>
                <p className="text-sm text-gray-600 mb-4">
                  Manage data retention and security settings for your Gmail integration.
                </p>
                <div className="space-y-2">
                  <div className="flex items-center space-x-2">
                    <input type="checkbox" id="retain-data" defaultChecked />
                    <label htmlFor="retain-data" className="text-sm">Retain email data for AI processing</label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <input type="checkbox" id="encrypt-data" defaultChecked />
                    <label htmlFor="encrypt-data" className="text-sm">Encrypt all email data</label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <input type="checkbox" id="auto-cleanup" />
                    <label htmlFor="auto-cleanup" className="text-sm">Automatically clean up old data</label>
                  </div>
                </div>
              </div>
            </div>
          </div>
        );

      default:
        return (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold">Gmail Integration</h2>
            <p className="text-gray-600">Select a tab to get started.</p>
          </div>
        );
    }
  };

  return (
    <>
      <Head>
        <title>Gmail Integration | ATOM</title>
        <meta name="description" content="Gmail integration for ATOM platform" />
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
                  <div className="w-10 h-10 bg-red-500 rounded-lg flex items-center justify-center">
                    <span className="text-white font-bold">G</span>
                  </div>
                  <div>
                    <h1 className="text-2xl font-bold text-gray-900">Gmail Integration</h1>
                    <p className="text-gray-600">Manage your Gmail inbox and email communications</p>
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
                      ? 'border-red-500 text-red-600'
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

export default GmailIntegrationPage;
