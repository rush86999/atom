/**
 * ATOM Unified Communication Services Management Dashboard
 * Real-time monitoring and control for Slack/Teams implementations
 */

import React, { useState, useEffect, useCallback } from 'react';
import { UnifiedServicesStatus, ServiceHealth, ImplementationConfig } from './types/communication';

interface ServicesManagerProps {
  onImplementationChange?: (service: string, impl: string) => void;
  onServiceHealthChange?: (health: ServiceHealth) => void;
  className?: string;
}

export const UnifiedServicesManager: React.FC<ServicesManagerProps> = ({
  onImplementationChange,
  onServiceHealthChange,
  className = ''
}) => {
  const [servicesStatus, setServicesStatus] = useState<UnifiedServicesStatus>({
    timestamp: '',
    environment: 'mock',
    services: {
      Slack: {
        current: 'mock',
        mock_available: true,
        real_available: false,
        health: { status: 'unknown' }
      },
      MicrosoftTeams: {
        current: 'mock',
        mock_available: true,
        real_available: false,
        health: { status: 'unknown' }
      }
    }
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedService, setExpandedService] = useState<string | null>(null);

  const apiConfig = {
    baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000',
    endpoints: {
      implementations: '/implementations',
      health: '/health',
      switch: '/implementations/switch',
      workspaces: '/workspaces',
      channels: '/channels'
    }
  };

  // Fetch current implementation status
  const fetchImplementationStatus = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${apiConfig.baseUrl}${apiConfig.endpoints.implementations}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch status: ${response.status}`);
      }

      const data = await response.json();
      
      // Add health status to each service
      const servicesWithHealth = { ...data };
      for (const serviceName in servicesWithHealth.services) {
        if (servicesWithHealth.services[serviceName]) {
          servicesWithHealth.services[serviceName].health = await fetchServiceHealth(serviceName);
        }
      }

      setServicesStatus(servicesWithHealth);
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(errorMessage);
      console.error('Failed to fetch implementation status:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch individual service health
  const fetchServiceHealth = useCallback(async (serviceName: string): Promise<ServiceHealth> => {
    try {
      const response = await fetch(`${apiConfig.baseUrl}${apiConfig.endpoints.health}`);
      if (!response.ok) {
        return { status: 'error', error: `HTTP ${response.status}` };
      }

      const healthData = await response.json();
      const serviceHealth = healthData.services?.[serviceName.toLowerCase()] || {};
      
      return {
        status: serviceHealth.status || 'unknown',
        api_healthy: serviceHealth.api_healthy,
        config_healthy: serviceHealth.config_healthy,
        token_valid: serviceHealth.token_valid,
        last_check: serviceHealth.checked_at,
        error: serviceHealth.error
      };
      
    } catch (err) {
      return { status: 'error', error: err instanceof Error ? err.message : 'Health check failed' };
    }
  }, []);

  // Switch implementation for a service
  const switchImplementation = useCallback(async (serviceName: string, implementationType: string) => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${apiConfig.baseUrl}${apiConfig.endpoints.switch}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({
          service_name: serviceName,
          implementation_type: implementationType
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || `Failed to switch: ${response.status}`);
      }

      const result = await response.json();
      
      if (result.ok) {
        // Refresh status
        await fetchImplementationStatus();
        
        if (onImplementationChange) {
          onImplementationChange(serviceName, implementationType);
        }
        
        // Also update health
        setTimeout(() => {
          fetchServiceHealth(serviceName).then(health => {
            if (onServiceHealthChange) {
              onServiceHealthChange({ service: serviceName, ...health });
            }
          });
        }, 1000);
        
      } else {
        throw new Error(result.error || 'Switch failed');
      }
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Switch failed';
      setError(errorMessage);
      console.error('Failed to switch implementation:', err);
    } finally {
      setLoading(false);
    }
  }, [fetchImplementationStatus, fetchServiceHealth, onImplementationChange, onServiceHealthChange]);

  // Refresh all data
  const refreshData = useCallback(async () => {
    await Promise.all([
      fetchImplementationStatus(),
      // Refresh health for each service
      ...Object.keys(servicesStatus.services).map(service => 
        fetchServiceHealth(service).then(health => {
          if (onServiceHealthChange) {
            onServiceHealthChange({ service, ...health });
          }
        })
      )
    ]);
  }, [fetchImplementationStatus, fetchServiceHealth, onServiceHealthChange, servicesStatus.services]);

  // Auto-refresh on interval
  useEffect(() => {
    const interval = setInterval(refreshData, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, [refreshData]);

  // Initial load
  useEffect(() => {
    fetchImplementationStatus();
  }, [fetchImplementationStatus]);

  // Get status color
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'text-green-600';
      case 'warning': return 'text-yellow-600';
      case 'error': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };

  // Get implementation badge color
  const getImplementationColor = (implementation: string) => {
    switch (implementation) {
      case 'mock': return 'bg-purple-100 text-purple-800';
      case 'real': return 'bg-blue-100 text-blue-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  // Render service status
  const renderServiceStatus = (serviceName: string, serviceConfig: any) => {
    const isExpanded = expandedService === serviceName;
    const health = serviceConfig.health || { status: 'unknown' };
    
    return (
      <div key={serviceName} className="border border-gray-200 rounded-lg p-4 mb-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-3">
            {/* Service Icon */}
            <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center">
              {serviceName === 'Slack' ? '💬' : '👥'}
            </div>
            
            <div>
              <h3 className="font-semibold text-gray-800">{serviceName}</h3>
              <div className="flex items-center space-x-2">
                {/* Current Implementation */}
                <span className={`px-2 py-1 text-xs rounded-full ${getImplementationColor(serviceConfig.current)}`}>
                  {serviceConfig.current}
                </span>
                
                {/* Health Status */}
                <span className={`text-sm ${getStatusColor(health.status)}`}>
                  {health.status}
                </span>
              </div>
            </div>
          </div>
          
          {/* Action Buttons */}
          <div className="flex items-center space-x-2">
            <button
              onClick={() => fetchServiceHealth(serviceName).then(h => {
                if (onServiceHealthChange) {
                  onServiceHealthChange({ service: serviceName, ...h });
                }
              })}
              className="p-2 text-gray-500 hover:text-gray-700 rounded"
              title="Check health"
            >
              🔄
            </button>
            
            <button
              onClick={() => setExpandedService(isExpanded ? null : serviceName)}
              className="p-2 text-gray-500 hover:text-gray-700 rounded"
              title="Toggle details"
            >
              {isExpanded ? '▲' : '▼'}
            </button>
          </div>
        </div>

        {/* Expanded Details */}
        {isExpanded && (
          <div className="mt-4 space-y-4">
            {/* Implementation Status */}
            <div>
              <h4 className="font-medium text-gray-700 mb-2">Implementation Status</h4>
              <div className="grid grid-cols-2 gap-3">
                <div className={`p-3 rounded-lg border ${serviceConfig.mock_available ? 'border-green-200 bg-green-50' : 'border-gray-200 bg-gray-50'}`}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium">Mock Implementation</span>
                    <span className="text-sm">{serviceConfig.mock_available ? '✅' : '❌'}</span>
                  </div>
                  <div className="text-xs text-gray-600">Mock data service available</div>
                </div>
                
                <div className={`p-3 rounded-lg border ${serviceConfig.real_available ? 'border-green-200 bg-green-50' : 'border-gray-200 bg-gray-50'}`}>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium">Real Implementation</span>
                    <span className="text-sm">{serviceConfig.real_available ? '✅' : '❌'}</span>
                  </div>
                  <div className="text-xs text-gray-600">Real API service available</div>
                </div>
              </div>
            </div>

            {/* Implementation Switch */}
            <div>
              <h4 className="font-medium text-gray-700 mb-2">Switch Implementation</h4>
              <div className="flex space-x-2">
                <button
                  onClick={() => switchImplementation(serviceName, 'mock')}
                  disabled={serviceConfig.current === 'mock' || !serviceConfig.mock_available || loading}
                  className={`px-4 py-2 rounded-lg transition-colors ${
                    serviceConfig.current === 'mock'
                      ? 'bg-purple-600 text-white'
                      : serviceConfig.mock_available
                      ? 'bg-purple-100 text-purple-700 hover:bg-purple-200'
                      : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                  } disabled:opacity-50`}
                >
                  🎭 Switch to Mock
                </button>
                
                <button
                  onClick={() => switchImplementation(serviceName, 'real')}
                  disabled={serviceConfig.current === 'real' || !serviceConfig.real_available || loading}
                  className={`px-4 py-2 rounded-lg transition-colors ${
                    serviceConfig.current === 'real'
                      ? 'bg-blue-600 text-white'
                      : serviceConfig.real_available
                      ? 'bg-blue-100 text-blue-700 hover:bg-blue-200'
                      : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                  } disabled:opacity-50`}
                >
                  🌐 Switch to Real
                </button>
              </div>
            </div>

            {/* Health Details */}
            <div>
              <h4 className="font-medium text-gray-700 mb-2">Health Details</h4>
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">API Status:</span>
                    <span className={health.api_healthy ? 'text-green-600' : 'text-red-600'}>
                      {health.api_healthy ? '✅ Healthy' : '❌ Unhealthy'}
                    </span>
                  </div>
                  
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-600">Configuration:</span>
                    <span className={health.config_healthy ? 'text-green-600' : 'text-red-600'}>
                      {health.config_healthy ? '✅ Valid' : '❌ Invalid'}
                    </span>
                  </div>
                  
                  {health.token_valid !== undefined && (
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600">Token Status:</span>
                      <span className={health.token_valid ? 'text-green-600' : 'text-red-600'}>
                        {health.token_valid ? '✅ Valid' : '❌ Invalid/Expired'}
                      </span>
                    </div>
                  )}
                  
                  {health.last_check && (
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600">Last Check:</span>
                      <span className="text-gray-500">
                        {new Date(health.last_check).toLocaleString()}
                      </span>
                    </div>
                  )}
                  
                  {health.error && (
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-600">Error:</span>
                      <span className="text-red-600 text-xs truncate max-w-xs">
                        {health.error}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Quick Actions */}
            <div>
              <h4 className="font-medium text-gray-700 mb-2">Quick Actions</h4>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => {
                    // Navigate to service-specific dashboard
                    window.location.href = `/dashboard/communication/${serviceName.toLowerCase()}`;
                  }}
                  className="p-2 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition-colors"
                >
                  📊 View Dashboard
                </button>
                
                <button
                  onClick={() => {
                    // Navigate to service-specific logs
                    window.location.href = `/logs/communication/${serviceName.toLowerCase()}`;
                  }}
                  className="p-2 text-sm bg-gray-100 text-gray-700 rounded hover:bg-gray-200 transition-colors"
                >
                  📝 View Logs
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className={`w-full max-w-6xl mx-auto p-6 ${className}`}>
      <div className="bg-white rounded-lg shadow-lg">
        {/* Header */}
        <div className="border-b border-gray-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-gray-800">Unified Communication Services</h2>
              <p className="text-gray-600">Monitor and manage Slack & Teams implementations</p>
            </div>
            <div className="flex items-center space-x-4">
              {/* Environment Badge */}
              <div className="px-3 py-1 bg-gray-100 rounded-full text-sm text-gray-700">
                Environment: {servicesStatus.environment}
              </div>
              
              {/* Refresh Button */}
              <button
                onClick={refreshData}
                disabled={loading}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 transition-colors flex items-center space-x-2"
              >
                <span>{loading ? '🔄' : '🔄'}</span>
                <span>{loading ? 'Refreshing...' : 'Refresh'}</span>
              </button>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="p-6">
          {/* Error Display */}
          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
              <div className="flex items-center">
                <span className="text-red-600 mr-2">❌</span>
                <span className="text-red-800 font-medium">Error:</span>
                <span className="text-red-700 ml-2">{error}</span>
              </div>
            </div>
          )}

          {/* Loading State */}
          {loading && (
            <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="flex items-center">
                <span className="text-blue-600 mr-2 animate-spin">⚙️</span>
                <span className="text-blue-800">Loading services status...</span>
              </div>
            </div>
          )}

          {/* Services List */}
          <div className="space-y-4">
            {Object.entries(servicesStatus.services).map(([serviceName, serviceConfig]) => 
              renderServiceStatus(serviceName, serviceConfig)
            )}
          </div>

          {/* Quick Actions Panel */}
          <div className="mt-8 p-4 bg-gray-50 rounded-lg">
            <h3 className="font-semibold text-gray-800 mb-3">Quick Actions</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <button
                onClick={() => {
                  Object.keys(servicesStatus.services).forEach(service => {
                    switchImplementation(service, 'mock');
                  });
                }}
                disabled={loading}
                className="p-3 bg-purple-100 text-purple-700 rounded-lg hover:bg-purple-200 transition-colors text-sm font-medium"
              >
                🎭 All to Mock
              </button>
              
              <button
                onClick={() => {
                  Object.keys(servicesStatus.services).forEach(service => {
                    if (servicesStatus.services[service].real_available) {
                      switchImplementation(service, 'real');
                    }
                  });
                }}
                disabled={loading}
                className="p-3 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 transition-colors text-sm font-medium"
              >
                🌐 All to Real
              </button>
              
              <button
                onClick={refreshData}
                disabled={loading}
                className="p-3 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 transition-colors text-sm font-medium"
              >
                🔄 Refresh All
              </button>
              
              <button
                onClick={() => {
                  window.location.href = '/dashboard/communication/settings';
                }}
                className="p-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors text-sm font-medium"
              >
                ⚙️ Settings
              </button>
            </div>
          </div>

          {/* Statistics */}
          <div className="mt-8 grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
              <div className="text-2xl font-bold text-green-600">
                {Object.values(servicesStatus.services).filter(s => s.health?.status === 'healthy').length}
              </div>
              <div className="text-sm text-green-700">Healthy Services</div>
            </div>
            
            <div className="p-4 bg-purple-50 border border-purple-200 rounded-lg">
              <div className="text-2xl font-bold text-purple-600">
                {Object.values(servicesStatus.services).filter(s => s.current === 'mock').length}
              </div>
              <div className="text-sm text-purple-700">Mock Implementations</div>
            </div>
            
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="text-2xl font-bold text-blue-600">
                {Object.values(servicesStatus.services).filter(s => s.current === 'real').length}
              </div>
              <div className="text-sm text-blue-700">Real Implementations</div>
            </div>
            
            <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
              <div className="text-2xl font-bold text-yellow-600">
                {Object.values(servicesStatus.services).filter(s => s.health?.status === 'error').length}
              </div>
              <div className="text-sm text-yellow-700">Services with Errors</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UnifiedServicesManager;