import React, { useState, useEffect } from 'react';
import { MemoryManagement } from '../ui-shared/components/MemoryManagement';
import { useUnifiedMemory, createDesktopMemoryConfig, createWebMemoryConfig } from '../ui-shared/hooks/useUnifiedMemory';
import { currentPlatformConfig, getCurrentPlatform } from '../services/utils/platformConfig';

/**
 * Unified Memory System Integration Example
 *
 * Demonstrates how to use the unified memory system across desktop and web platforms
 * with full UI and feature parity, only differing in storage backend:
 * - Desktop: Uses localStorage for offline capability
 * - Web: Uses AWS S3 for cloud storage
 */

export interface UnifiedMemoryExampleProps {
  userId: string;
  workspaceId?: string;
  onPlatformChange?: (platform: 'desktop' | 'web') => void;
}

/**
 * Example component showing memory system usage with platform switching
 */
export const UnifiedMemoryExample: React.FC<UnifiedMemoryExampleProps> = ({
  userId,
  workspaceId,
  onPlatformChange
}) => {
  const [currentPlatform, setCurrentPlatform] = useState<'desktop' | 'web'>(getCurrentPlatform());
  const [demoMemories, setDemoMemories] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<'management' | 'stats' | 'demo'>('management');

  // Create platform-appropriate memory configuration
  const memoryConfig = currentPlatform === 'desktop'
    ? createDesktopMemoryConfig(userId, workspaceId)
    : createWebMemoryConfig(userId, {
        bucketName: 'atom-platform-demo',
        region: 'us-east-1'
      }, workspaceId);

  const {
    memories,
    memoryStats,
    isLoading,
    error,
    storeMemory,
    deleteMemory,
    getMemoryStats,
    cleanupExpiredMemories,
    refresh,
    platform,
    storageLocation,
    isOfflineCapable
  } = useUnifiedMemory(memoryConfig);

  // Handle platform change
  const handlePlatformChange = (newPlatform: 'desktop' | 'web') => {
    setCurrentPlatform(newPlatform);
    onPlatformChange?.(newPlatform);
  };

  // Create demo memories to showcase the system
  const createDemoMemories = async () => {
    const demoData = [
      {
        type: 'workflow' as const,
        content: 'Automated daily standup meeting workflow',
        metadata: {
          userId,
          workspaceId,
          tags: ['meeting', 'daily', 'automation'],
          importance: 8,
          accessCount: 0,
          lastAccessed: new Date(),
          confidence: 0.9
        },
        expires: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000) // 7 days
      },
      {
        type: 'automation' as const,
        content: 'Email categorization and routing automation',
        metadata: {
          userId,
          workspaceId,
          tags: ['email', 'categorization', 'routing'],
          importance: 9,
          accessCount: 0,
          lastAccessed: new Date(),
          confidence: 0.85
        }
      },
      {
        type: 'user_pattern' as const,
        content: 'User prefers morning productivity sessions',
        metadata: {
          userId,
          workspaceId,
          tags: ['preference', 'schedule', 'productivity'],
          importance: 7,
          accessCount: 0,
          lastAccessed: new Date(),
          confidence: 0.8
        }
      },
      {
        type: 'conversation' as const,
        content: 'Recent discussion about project timeline and deliverables',
        metadata: {
          userId,
          workspaceId,
          tags: ['conversation', 'project', 'timeline'],
          importance: 6,
          accessCount: 0,
          lastAccessed: new Date(),
          confidence: 0.75
        }
      },
      {
        type: 'insight' as const,
        content: 'Team collaboration improves with structured check-ins',
        metadata: {
          userId,
          workspaceId,
          tags: ['insight', 'collaboration', 'team'],
          importance: 8,
          accessCount: 0,
          lastAccessed: new Date(),
          confidence: 0.9
        }
      }
    ];

    const createdMemories = [];
    for (const data of demoData) {
      try {
        const memoryId = await storeMemory(data);
        createdMemories.push({ ...data, id: memoryId });
      } catch (err) {
        console.error('Failed to create demo memory:', err);
      }
    }

    setDemoMemories(createdMemories);
    await refresh();
  };

  // Clear all demo memories
  const clearDemoMemories = async () => {
    for (const memory of demoMemories) {
      try {
        await deleteMemory(memory.id);
      } catch (err) {
        console.error('Failed to delete demo memory:', err);
      }
    }
    setDemoMemories([]);
    await refresh();
  };

  // Platform information display
  const PlatformInfo: React.FC = () => (
    <div className="platform-info p-4 bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg mb-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 mb-2">
            Unified Memory System Demo
          </h3>
          <div className="flex flex-wrap gap-2">
            <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
              currentPlatform === 'desktop'
                ? 'bg-blue-100 text-blue-800'
                : 'bg-green-100 text-green-800'
            }`}>
              {currentPlatform === 'desktop' ? '💻 Desktop App' : '🌐 Web App'}
            </span>
            <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800">
              {storageLocation === 'localStorage' ? '💾 Local Storage' : '☁️ S3 Cloud Storage'}
            </span>
            {isOfflineCapable && (
              <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-yellow-100 text-yellow-800">
                📴 Offline Capable
              </span>
            )}
          </div>
        </div>

        <div className="mt-4 md:mt-0">
          <div className="flex space-x-2">
            <button
              onClick={() => handlePlatformChange('desktop')}
              className={`px-4 py-2 text-sm rounded-md transition-colors ${
                currentPlatform === 'desktop'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              Switch to Desktop
            </button>
            <button
              onClick={() => handlePlatformChange('web')}
              className={`px-4 py-2 text-sm rounded-md transition-colors ${
                currentPlatform === 'web'
                  ? 'bg-green-600 text-white'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              Switch to Web
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  // Stats display component
  const StatsDisplay: React.FC = () => (
    <div className="stats-display p-6 bg-white rounded-lg shadow-sm">
      <h3 className="text-xl font-semibold text-gray-900 mb-4">Memory Statistics</h3>

      {memoryStats ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="stat-card p-4 bg-blue-50 rounded-lg">
            <div className="text-2xl font-bold text-blue-600">
              {memoryStats.totalMemories?.toLocaleString() || 0}
            </div>
            <div className="text-sm text-blue-800">Total Memories</div>
          </div>

          <div className="stat-card p-4 bg-green-50 rounded-lg">
            <div className="text-2xl font-bold text-green-600">
              {(memoryStats.totalSize / 1024 / 1024).toFixed(2)} MB
            </div>
            <div className="text-sm text-green-800">Storage Used</div>
          </div>

          <div className="stat-card p-4 bg-purple-50 rounded-lg">
            <div className="text-2xl font-bold text-purple-600">
              {memoryStats.desktopMemories?.toLocaleString() || 0}
            </div>
            <div className="text-sm text-purple-800">Desktop Memories</div>
          </div>

          <div className="stat-card p-4 bg-orange-50 rounded-lg">
            <div className="text-2xl font-bold text-orange-600">
              {memoryStats.webMemories?.toLocaleString() || 0}
            </div>
            <div className="text-sm text-orange-800">Web Memories</div>
          </div>
        </div>
      ) : (
        <div className="text-center py-8 text-gray-500">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
          <div>Loading statistics...</div>
        </div>
      )}

      {memoryStats?.memoryTypes && (
        <div className="mt-6">
          <h4 className="font-medium text-gray-900 mb-3">Memory Types Distribution</h4>
          <div className="flex flex-wrap gap-2">
            {Object.entries(memoryStats.memoryTypes).map(([type, count]) => (
              <span
                key={type}
                className="inline-flex items-center px-3 py-1 bg-gray-100 text-gray-800 rounded-full text-sm"
              >
                <span className="capitalize">{type.replace('_', ' ')}</span>
                <span className="ml-2 bg-gray-200 px-2 py-0.5 rounded-full text-xs">
                  {count as number}
                </span>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  // Demo controls component
  const DemoControls: React.FC = () => (
    <div className="demo-controls p-6 bg-white rounded-lg shadow-sm">
      <h3 className="text-xl font-semibold text-gray-900 mb-4">Demo Controls</h3>

      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:space-x-4 space-y-2 sm:space-y-0">
          <button
            onClick={createDemoMemories}
            disabled={isLoading}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {isLoading ? 'Creating...' : 'Create Demo Memories'}
          </button>

          <button
            onClick={clearDemoMemories}
            disabled={isLoading || demoMemories.length === 0}
            className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50 transition-colors"
          >
            Clear Demo Memories
          </button>

          <button
            onClick={cleanupExpiredMemories}
            disabled={isLoading}
            className="px-4 py-2 bg-orange-600 text-white rounded-md hover:bg-orange-700 disabled:opacity-50 transition-colors"
          >
            Cleanup Expired
          </button>

          <button
            onClick={refresh}
            disabled={isLoading}
            className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 disabled:opacity-50 transition-colors"
          >
            {isLoading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>

        {demoMemories.length > 0 && (
          <div className="bg-green-50 border border-green-200 rounded-md p-3">
            <div className="flex items-center">
              <span className="text-green-500 mr-2">✅</span>
              <span className="text-green-800 text-sm">
                Created {demoMemories.length} demo memories. Check the Management tab to view them.
              </span>
            </div>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-md p-3">
            <div className="flex items-center">
              <span className="text-red-500 mr-2">⚠️</span>
              <span className="text-red-800 text-sm">{error}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="unified-memory-example min-h-screen bg-gray-50 p-4">
      <PlatformInfo />

      {/* Navigation Tabs */}
      <div className="tabs-navigation mb-6">
        <div className="flex space-x-1 bg-white rounded-lg p-1 shadow-sm">
          {[
            { id: 'management' as const, label: 'Memory Management', icon: '📚' },
            { id: 'stats' as const, label: 'Statistics', icon: '📊' },
            { id: 'demo' as const, label: 'Demo Controls', icon: '🎮' }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 flex items-center justify-center px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
              }`}
            >
              <span className="mr-2">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div className="tab-content">
        {activeTab === 'management' && (
          <MemoryManagement
            platform={currentPlatform}
            userId={userId}
            workspaceId={workspaceId}
            onError={(errorMsg) => console.error('Memory Management Error:', errorMsg)}
            className="mb-6"
          />
        )}

        {activeTab === 'stats' && <StatsDisplay />}

        {activeTab === 'demo' && <DemoControls />}
      </div>

      {/* Feature Parity Notice */}
      <div className="mt-8 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
        <div className="flex items-start">
          <span className="text-yellow-500 mr-2 text-lg">💡</span>
          <div>
            <h4 className="font-semibold text-yellow-800 mb-1">Feature Parity Notice</h4>
            <p className="text-yellow-700 text-sm">
              This demo showcases complete UI and feature parity between desktop and web platforms.
              The only difference is the storage backend:
              <strong> Desktop uses localStorage</strong> for offline capability, while
              <strong> Web uses AWS S3</strong> for cloud storage. All other features,
              interfaces, and user experiences are identical across both platforms.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UnifiedMemoryExample;
