import React, { useState, useEffect } from 'react';
import { UnifiedPlatform, platform, featureFlags } from './UnifiedPlatform';
import { UnifiedUI, Button, Card, Layout, IntegrationStatus } from './UnifiedUI';

export interface UnifiedDashboardProps {
  userId: string;
  workspaceId?: string;
  onIntegrationClick?: (integrationId: string) => void;
  onFeatureClick?: (featureId: string) => void;
  className?: string;
  platform?: 'desktop' | 'web' | 'auto';
}

export interface DashboardStats {
  connectedIntegrations: number;
  totalIntegrations: number;
  activeWorkflows: number;
  totalTasks: number;
  completedTasks: number;
  systemHealth: 'excellent' | 'good' | 'fair' | 'poor';
  lastSync: string;
  memoryUsage: number;
  storageUsage: number;
}

export interface Integration {
  id: string;
  name: string;
  category: string;
  status: 'connected' | 'disconnected' | 'error' | 'loading';
  lastSync?: string;
  health: 'healthy' | 'warning' | 'error';
  icon?: string;
}

export interface DashboardFeature {
  id: string;
  name: string;
  description: string;
  icon: string;
  available: boolean;
  route?: string;
  requiresFeature?: keyof ReturnType<typeof featureFlags>;
}

export const UnifiedDashboard: React.FC<UnifiedDashboardProps> = ({
  userId,
  workspaceId,
  onIntegrationClick,
  onFeatureClick,
  className = '',
  platform: forcePlatform,
}) => {
  const currentPlatform = forcePlatform || platform.getPlatform();
  const isDesktop = currentPlatform === 'desktop';

  const [stats, setStats] = useState<DashboardStats>({
    connectedIntegrations: 0,
    totalIntegrations: 0,
    activeWorkflows: 0,
    totalTasks: 0,
    completedTasks: 0,
    systemHealth: 'good',
    lastSync: new Date().toISOString(),
    memoryUsage: 0,
    storageUsage: 0,
  });

  const [integrations, setIntegrations] = useState<Integration[]>([
    {
      id: 'slack',
      name: 'Slack',
      category: 'communication',
      status: 'connected',
      lastSync: '2 minutes ago',
      health: 'healthy',
      icon: '💬',
    },
    {
      id: 'notion',
      name: 'Notion',
      category: 'productivity',
      status: 'connected',
      lastSync: '5 minutes ago',
      health: 'healthy',
      icon: '📝',
    },
    {
      id: 'github',
      name: 'GitHub',
      category: 'development',
      status: 'connected',
      lastSync: '10 minutes ago',
      health: 'healthy',
      icon: '🐙',
    },
    {
      id: 'gmail',
      name: 'Gmail',
      category: 'communication',
      status: 'disconnected',
      health: 'error',
      icon: '📧',
    },
    {
      id: 'asana',
      name: 'Asana',
      category: 'productivity',
      status: 'connected',
      lastSync: '15 minutes ago',
      health: 'warning',
      icon: '📋',
    },
    {
      id: 'stripe',
      name: 'Stripe',
      category: 'finance',
      status: 'connected',
      lastSync: '1 hour ago',
      health: 'healthy',
      icon: '💳',
    },
  ]);

  const [features, setFeatures] = useState<DashboardFeature[]>([
    {
      id: 'chat',
      name: 'AI Chat',
      description: 'Conversational AI assistant',
      icon: '🤖',
      available: true,
      route: '/chat',
    },
    {
      id: 'automations',
      name: 'Automations',
      description: 'Create and manage workflows',
      icon: '⚙️',
      available: true,
      route: '/automations',
    },
    {
      id: 'tasks',
      name: 'Task Manager',
      description: 'Manage your tasks and projects',
      icon: '✅',
      available: true,
      route: '/tasks',
    },
    {
      id: 'calendar',
      name: 'Calendar',
      description: 'Schedule and events',
      icon: '📅',
      available: true,
      route: '/calendar',
    },
    {
      id: 'analytics',
      name: 'Analytics',
      description: 'Performance insights',
      icon: '📊',
      available: true,
      route: '/analytics',
    },
    {
      id: 'settings',
      name: 'Settings',
      description: 'Platform configuration',
      icon: '⚙️',
      available: true,
      route: '/settings',
    },
  ]);

  const [isLoading, setIsLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  useEffect(() => {
    loadDashboardData();

    // Auto-refresh every 2 minutes
    const interval = setInterval(loadDashboardData, 120000);
    return () => clearInterval(interval);
  }, [userId, workspaceId]);

  const loadDashboardData = async () => {
    setIsLoading(true);
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 1000));

      // Update stats based on current integrations
      const connectedCount = integrations.filter(i => i.status === 'connected').length;

      setStats(prev => ({
        ...prev,
        connectedIntegrations: connectedCount,
        totalIntegrations: integrations.length,
        activeWorkflows: Math.floor(Math.random() * 20) + 5,
        totalTasks: Math.floor(Math.random() * 100) + 50,
        completedTasks: Math.floor(Math.random() * 80) + 20,
        lastSync: new Date().toISOString(),
        memoryUsage: Math.floor(Math.random() * 80) + 10,
        storageUsage: Math.floor(Math.random() * 70) + 15,
      }));

      setLastRefresh(new Date());
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRefresh = () => {
    loadDashboardData();
  };

  const handleIntegrationClick = (integration: Integration) => {
    onIntegrationClick?.(integration.id);
  };

  const handleFeatureClick = (feature: DashboardFeature) => {
    if (feature.available) {
      onFeatureClick?.(feature.id);
    }
  };

  const getHealthColor = (health: string) => {
    switch (health) {
      case 'healthy': return '#10B981';
      case 'warning': return '#F59E0B';
      case 'error': return '#EF4444';
      default: return '#6B7280';
    }
  };

  const getSystemHealthColor = (health: DashboardStats['systemHealth']) => {
    switch (health) {
      case 'excellent': return '#10B981';
      case 'good': return '#3B82F6';
      case 'fair': return '#F59E0B';
      case 'poor': return '#EF4444';
      default: return '#6B7280';
    }
  };

  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`;
    return `${Math.floor(diffMins / 1440)}d ago`;
  };

  const navigationItems = [
    { id: 'dashboard', label: 'Dashboard', icon: '📊', active: true },
    { id: 'integrations', label: 'Integrations', icon: '🔌' },
    { id: 'automations', label: 'Automations', icon: '⚙️' },
    { id: 'analytics', label: 'Analytics', icon: '📈' },
    { id: 'settings', label: 'Settings', icon: '⚙️' },
  ];

  const sidebar = (
    <div className="dashboard-sidebar">
      <div className="sidebar-header">
        <h2>ATOM</h2>
        <div className="platform-badge">
          {isDesktop ? '💻 Desktop' : '🌐 Web'}
        </div>
      </div>
      <UnifiedUI.Navigation
        items={navigationItems}
        orientation="vertical"
      />
      <div className="sidebar-footer">
        <div className="user-info">
          <div className="user-avatar">👤</div>
          <div className="user-details">
            <div className="user-name">User {userId}</div>
            <div className="user-status">Online</div>
          </div>
        </div>
      </div>
    </div>
  );

  const header = (
    <div className="dashboard-header">
      <div className="header-left">
        <h1>ATOM Dashboard</h1>
        <div className="header-subtitle">
          Unified platform for automation and productivity
        </div>
      </div>
      <div className="header-right">
        <Button
          variant="outline"
          onClick={handleRefresh}
          loading={isLoading}
        >
          Refresh
        </Button>
        <div className="last-refresh">
          Last refresh: {formatTimeAgo(lastRefresh.toISOString())}
        </div>
      </div>
    </div>
  );

  return (
    <Layout
      sidebar={sidebar}
      header={header}
      className={`unified-dashboard ${className}`}
      platform={currentPlatform}
    >
      <div className="dashboard-content">
        {/* Stats Overview */}
        <div className="stats-grid">
          <Card variant="elevated" className="stat-card">
            <div className="stat-content">
              <div className="stat-icon">🔌</div>
              <div className="stat-info">
                <div className="stat-value">{stats.connectedIntegrations}</div>
                <div className="stat-label">Connected Integrations</div>
                <div className="stat-subtext">
                  {stats.connectedIntegrations} of {stats.totalIntegrations} available
                </div>
              </div>
            </div>
          </Card>

          <Card variant="elevated" className="stat-card">
            <div className="stat-content">
              <div className="stat-icon">⚙️</div>
              <div className="stat-info">
                <div className="stat-value">{stats.activeWorkflows}</div>
                <div className="stat-label">Active Workflows</div>
                <div className="stat-subtext">Running automations</div>
              </div>
            </div>
          </Card>

          <Card variant="elevated" className="stat-card">
            <div className="stat-content">
              <div className="stat-icon">✅</div>
              <div className="stat-info">
                <div className="stat-value">{stats.completedTasks}</div>
                <div className="stat-label">Completed Tasks</div>
                <div className="stat-subtext">
                  {stats.completedTasks} of {stats.totalTasks} total
                </div>
              </div>
            </div>
          </Card>

          <Card variant="elevated" className="stat-card">
            <div className="stat-content">
              <div className="stat-icon">💚</div>
              <div className="stat-info">
                <div className="stat-value" style={{ color: getSystemHealthColor(stats.systemHealth) }}>
                  {stats.systemHealth}
                </div>
                <div className="stat-label">System Health</div>
                <div className="stat-subtext">
                  Last sync: {formatTimeAgo(stats.lastSync)}
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Quick Features */}
        <Card className="features-section">
          <div className="section-header">
            <h2>Quick Features</h2>
            <div className="section-subtitle">
              Access core platform features
            </div>
          </div>
          <div className="features-grid">
            {features.map(feature => (
              <Card
                key={feature.id}
                variant="outlined"
                className={`feature-card ${!feature.available ? 'disabled' : ''}`}
                onClick={() => handleFeatureClick(feature)}
              >
                <div className="feature-content">
                  <div className="feature-icon">{feature.icon}</div>
                  <div className="feature-info">
                    <h3 className="feature-name">{feature.name}</h3>
                    <p className="feature-description">{feature.description}</p>
                  </div>
                  {!feature.available && (
                    <div className="feature-badge">Coming Soon</div>
                  )}
                </div>
              </Card>
            ))}
          </div>
        </Card>

        {/* Integrations */}
        <Card className="integrations-section">
          <div className="section-header">
            <div className="section-title">
              <h2>Integrations</h2>
              <div className="section-subtitle">
                Connected services and their status
              </div>
            </div>
            <Button variant="outline" size="sm">
              Manage All
            </Button>
          </div>
          <div className="integrations-grid">
            {integrations.map(integration => (
              <Card
                key={integration.id}
                variant="outlined"
                className="integration-card"
                onClick={() => handleIntegrationClick(integration)}
              >
                <div className="integration-content">
                  <div className="integration-header">
                    <div className="integration-icon">{integration.icon}</div>
                    <div className="integration-info">
                      <h3 className="integration-name">{integration.name}</h3>
                      <div className="integration-category">{integration.category}</div>
                    </div>
                    <div
                      className="integration-health"
                      style={{ backgroundColor: getHealthColor(integration.health) }}
                    />
                  </div>
                  <div className="integration-status">
                    <IntegrationStatus
                      integration={integration.name}
                      status={integration.status}
                      lastSync={integration.lastSync}
                    />
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </Card>

        {/* System Status */}
        <div className="system-status-grid">
          <Card className="system-card">
            <div className="section-header">
              <h3>Memory Usage</h3>
            </div>
            <div className="usage-display">
              <div className="usage-bar">
                <div
                  className="usage-fill"
                  style={{ width: `${stats.memoryUsage}%` }}
                />
              </div>
              <div className="usage-text">{stats.memoryUsage}%</div>
            </div>
          </Card>

          <Card className="system-card">
            <div className="section-header">
              <h3>Storage Usage</h3>
            </div>
            <div className="usage-display">
              <div className="usage-bar">
                <div
                  className="usage-fill"
                  style={{ width: `${stats.storageUsage}%` }}
                />
              </div>
              <div className="usage-text">{stats.storageUsage}%</div>
            </div>
          </Card>

          <Card className="system-card">
            <div className="section-header">
              <h3>Platform Info</h3>
            </div>
            <div className="platform-info">
              <div className="info-item">
                <span className="info-label">Platform:</span>
                <span className="info-value">{isDesktop ? 'Desktop' : 'Web'}</span>
              </div>
              <div className="info-item">
                <span className="info-label">Environment:</span>
                <span className="info-value">{platform.isDevelopment() ? 'Development' : 'Production'}</span>
              </div>
              <div className="info-item">
                <span className="info-label">User ID:</span>
                <span className="info-value">{userId}</span>
              </div>
            </div>
          </Card>
        </div>
      </div>

      <style jsx>{`
        .unified-dashboard {
          min-height: 100vh;
          background-color: #f8fafc;
        }

        .dashboard-content {
          padding: 24px;
          max-width: 1400px;
          margin: 0 auto;
        }

        .stats-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
          gap: 16px;
          margin-bottom: 24px;
        }

        .stat-card {
          padding: 20px;
        }

        .stat-content {
          display: flex;
          align-items: center;
          gap: 16px;
        }

        .stat-icon {
          font-size: 32px;
        }

        .stat-value {
          font-size: 28px;
          font-weight: bold;
          color: #1f2937;
        }

        .stat-label {
          font-size: 14px;
          color: #6b7280;
          margin-top: 4px;
        }

        .stat-subtext {
          font-size: 12px;
          color: #9ca3af;
          margin-top: 2px;
        }

        .features-section,
        .integrations-section {
          margin-bottom: 24px;
          padding: 24px;
        }

        .section-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 20px;
        }

        .section-title h2 {
          margin: 0 0 4px 0;
          font-size: 24px;
          color: #1f2937;
        }

        .section-subtitle {
          color: #6b7280;
          font-size: 14px;
        }

        .features-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: 16px;
        }

        .feature-card {
          padding: 20px;
          cursor: pointer;
          transition: all 0.2s ease;
        }

        .feature-card:hover:not(.disabled) {
          transform: translateY(-2px);
          box-shadow: 0 4
