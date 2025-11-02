/**
 * ATOM Unified Communication Services Dashboard
 * Real-time monitoring and management interface
 */

import React, { useState, useEffect } from 'react';
import { UnifiedServicesManager } from '../components/UnifiedServicesManager';
import { 
  UnifiedServicesStatus, 
  ServiceHealth, 
  ServiceConfiguration,
  UnifiedStatistics 
} from '../components/types/communication';

export default function UnifiedCommunicationDashboard() {
  const [activeTab, setActiveTab] = useState<'overview' | 'services' | 'statistics' | 'settings'>('services');
  const [servicesStatus, setServicesStatus] = useState<UnifiedServicesStatus | null>(null);
  const [statistics, setStatistics] = useState<UnifiedStatistics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const apiConfig = {
    baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000',
    endpoints: {
      health: '/health',
      implementations: '/implementations',
      statistics: '/statistics'
    }
  };

  // Fetch dashboard data
  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch services status
      const statusResponse = await fetch(`${apiConfig.baseUrl}${apiConfig.endpoints.implementations}`);
      if (statusResponse.ok) {
        const statusData = await statusResponse.json();
        setServicesStatus(statusData);
      }

      // Fetch statistics
      const statsResponse = await fetch(`${apiConfig.baseUrl}${apiConfig.endpoints.statistics}`);
      if (statsResponse.ok) {
        const statsData = await statsResponse.json();
        setStatistics(statsData);
      }

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch dashboard data';
      setError(errorMessage);
      console.error('Dashboard fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  // Handle implementation change
  const handleImplementationChange = (service: string, implementation: string) => {
    console.log(`Switched ${service} to ${implementation}`);
    // Refresh data after a brief delay
    setTimeout(fetchDashboardData, 2000);
  };

  // Handle service health change
  const handleServiceHealthChange = (health: ServiceHealth) => {
    console.log(`Health update for ${health.service}:`, health);
  };

  // Auto-refresh data
  useEffect(() => {
    fetchDashboardData();
    
    // Set up auto-refresh interval
    const interval = setInterval(fetchDashboardData, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  // Render overview tab
  const renderOverview = () => (
    <div className="space-y-6">
      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Total Services</p>
              <p className="text-2xl font-bold text-gray-800">2</p>
            </div>
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
              <span className="text-xl">🚀</span>
            </div>
          </div>
        </div>
        
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Healthy Services</p>
              <p className="text-2xl font-bold text-green-600">
                {servicesStatus?.services ? 
                  Object.values(servicesStatus.services).filter(s => 
                    s.health?.status === 'healthy'
                  ).length : 0
                }
              </p>
            </div>
            <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
              <span className="text-xl">✅</span>
            </div>
          </div>
        </div>
        
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Real Implementations</p>
              <p className="text-2xl font-bold text-blue-600">
                {servicesStatus?.services ? 
                  Object.values(servicesStatus.services).filter(s => 
                    s.current === 'real'
                  ).length : 0
                }
              </p>
            </div>
            <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
              <span className="text-xl">🌐</span>
            </div>
          </div>
        </div>
        
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Mock Implementations</p>
              <p className="text-2xl font-bold text-purple-600">
                {servicesStatus?.services ? 
                  Object.values(servicesStatus.services).filter(s => 
                    s.current === 'mock'
                  ).length : 0
                }
              </p>
            </div>
            <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
              <span className="text-xl">🎭</span>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Service Status</h3>
          <div className="space-y-3">
            {servicesStatus?.services && Object.entries(servicesStatus.services).map(([name, config]) => (
              <div key={name} className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <span className="text-lg">{name === 'Slack' ? '💬' : '👥'}</span>
                  <span className="font-medium text-gray-700">{name}</span>
                </div>
                <div className="flex items-center space-x-2">
                  <span className={`px-2 py-1 text-xs rounded-full ${
                    config.current === 'real' ? 'bg-blue-100 text-blue-800' : 'bg-purple-100 text-purple-800'
                  }`}>
                    {config.current}
                  </span>
                  <span className={`px-2 py-1 text-xs rounded-full ${
                    config.health?.status === 'healthy' ? 'bg-green-100 text-green-800' :
                    config.health?.status === 'error' ? 'bg-red-100 text-red-800' :
                    'bg-yellow-100 text-yellow-800'
                  }`}>
                    {config.health?.status || 'unknown'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">System Information</h3>
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-sm text-gray-600">Environment</span>
              <span className="text-sm font-medium text-gray-800">
                {servicesStatus?.environment || 'Unknown'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-gray-600">Last Updated</span>
              <span className="text-sm font-medium text-gray-800">
                {servicesStatus?.timestamp ? 
                  new Date(servicesStatus.timestamp).toLocaleString() : 
                  'Never'
                }
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-gray-600">API Status</span>
              <span className="text-sm font-medium text-green-600">Online</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm text-gray-600">Auto-refresh</span>
              <span className="text-sm font-medium text-gray-800">30 seconds</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  // Render statistics tab
  const renderStatistics = () => (
    <div className="space-y-6">
      {statistics && (
        <>
          {/* Total Metrics */}
          <div className="bg-white border border-gray-200 rounded-lg p-6">
            <h3 className="text-lg font-semibold text-gray-800 mb-4">Total Metrics</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-sm text-gray-600">Total Workspaces</p>
                <p className="text-2xl font-bold text-gray-800">
                  {statistics.total_metrics.total_workspaces}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Total Channels</p>
                <p className="text-2xl font-bold text-gray-800">
                  {statistics.total_metrics.total_channels}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Total Messages</p>
                <p className="text-2xl font-bold text-gray-800">
                  {statistics.total_metrics.total_messages.toLocaleString()}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600">API Calls Today</p>
                <p className="text-2xl font-bold text-gray-800">
                  {statistics.total_metrics.total_api_calls.toLocaleString()}
                </p>
              </div>
            </div>
          </div>

          {/* Service-specific Statistics */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {Object.entries(statistics.services).map(([serviceName, stats]) => (
              <div key={serviceName} className="bg-white border border-gray-200 rounded-lg p-6">
                <h4 className="text-lg font-semibold text-gray-800 mb-4 flex items-center space-x-2">
                  <span>{serviceName === 'slack' ? '💬' : '👥'}</span>
                  <span>{serviceName === 'slack' ? 'Slack' : 'Microsoft Teams'}</span>
                  <span className={`px-2 py-1 text-xs rounded-full ${
                    stats.implementation === 'real' ? 'bg-blue-100 text-blue-800' : 'bg-purple-100 text-purple-800'
                  }`}>
                    {stats.implementation}
                  </span>
                </h4>
                
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">Workspaces</span>
                    <span className="text-sm font-medium text-gray-800">
                      {stats.metrics.workspaces_count}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">Channels</span>
                    <span className="text-sm font-medium text-gray-800">
                      {stats.metrics.channels_count}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">Messages</span>
                    <span className="text-sm font-medium text-gray-800">
                      {stats.metrics.messages_count.toLocaleString()}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">API Calls Today</span>
                    <span className="text-sm font-medium text-gray-800">
                      {stats.metrics.api_calls_today.toLocaleString()}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">Average Response Time</span>
                    <span className="text-sm font-medium text-gray-800">
                      {stats.metrics.average_response_time.toFixed(0)}ms
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">Uptime</span>
                    <span className={`text-sm font-medium ${
                      stats.metrics.uptime_percentage >= 99 ? 'text-green-600' :
                      stats.metrics.uptime_percentage >= 95 ? 'text-yellow-600' :
                      'text-red-600'
                    }`}>
                      {stats.metrics.uptime_percentage.toFixed(1)}%
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {!statistics && (
        <div className="bg-white border border-gray-200 rounded-lg p-6 text-center">
          <div className="text-gray-500">No statistics data available</div>
          <button
            onClick={fetchDashboardData}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Refresh Statistics
          </button>
        </div>
      )}
    </div>
  );

  // Render settings tab
  const renderSettings = () => (
    <div className="space-y-6">
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Dashboard Settings</h3>
        
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-gray-700">Auto-refresh</p>
              <p className="text-sm text-gray-500">Automatically refresh dashboard data</p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" defaultChecked className="sr-only peer" />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          </div>
          
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-gray-700">Refresh Interval</p>
              <p className="text-sm text-gray-500">How often to refresh data</p>
            </div>
            <select className="px-3 py-2 border border-gray-300 rounded-lg text-sm">
              <option value="30">30 seconds</option>
              <option value="60">1 minute</option>
              <option value="300">5 minutes</option>
              <option value="0">Manual only</option>
            </select>
          </div>
          
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-gray-700">Notifications</p>
              <p className="text-sm text-gray-500">Show service status notifications</p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" defaultChecked className="sr-only peer" />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          </div>
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">API Configuration</h3>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">API Base URL</label>
            <input
              type="text"
              defaultValue={apiConfig.baseUrl}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg"
              placeholder="http://localhost:8000"
            />
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Connection Timeout</label>
              <input
                type="number"
                defaultValue="30"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                placeholder="30"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Retry Attempts</label>
              <input
                type="number"
                defaultValue="3"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                placeholder="3"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            Unified Communication Services
          </h1>
          <p className="text-gray-600">
            Monitor and manage Slack and Microsoft Teams integrations
          </p>
        </div>

        {/* Tab Navigation */}
        <div className="mb-8 border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            {[
              { id: 'overview', label: 'Overview', icon: '📊' },
              { id: 'services', label: 'Services', icon: '🚀' },
              { id: 'statistics', label: 'Statistics', icon: '📈' },
              { id: 'settings', label: 'Settings', icon: '⚙️' }
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center space-x-2 py-2 px-1 border-b-2 font-medium text-sm transition-colors ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <span>{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            ))}
          </nav>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex items-center">
              <span className="text-red-600 mr-2">❌</span>
              <span className="text-red-800 font-medium">Error:</span>
              <span className="text-red-700 ml-2">{error}</span>
            </div>
          </div>
        )}

        {/* Tab Content */}
        <div>
          {activeTab === 'overview' && renderOverview()}
          {activeTab === 'services' && (
            <UnifiedServicesManager
              onImplementationChange={handleImplementationChange}
              onServiceHealthChange={handleServiceHealthChange}
            />
          )}
          {activeTab === 'statistics' && renderStatistics()}
          {activeTab === 'settings' && renderSettings()}
        </div>
      </div>
    </div>
  );
}