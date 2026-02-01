import React, { useState, useEffect } from 'react';
import { useUnifiedMemory, UseUnifiedMemoryConfig } from '../hooks/useUnifiedMemory';

export interface MemoryManagementProps {
  platform: 'desktop' | 'web';
  userId: string;
  workspaceId?: string;
  onMemorySelected?: (memory: any) => void;
  onError?: (error: string) => void;
  className?: string;
}

export interface MemoryCardProps {
  memory: any;
  platform: 'desktop' | 'web';
  onSelect?: (memory: any) => void;
  onDelete?: (memoryId: string) => void;
}

export interface MemoryStatsDisplayProps {
  stats: any;
  platform: 'desktop' | 'web';
  storageLocation: 'localStorage' | 's3';
}

/**
 * Memory Card Component
 * Displays individual memory with platform-appropriate styling
 */
const MemoryCard: React.FC<MemoryCardProps> = ({ memory, platform, onSelect, onDelete }) => {
  const handleSelect = () => {
    onSelect?.(memory);
  };

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    onDelete?.(memory.id);
  };

  const getPlatformIcon = () => {
    return platform === 'desktop' ? '💻' : '🌐';
  };

  const getTypeIcon = (type: string) => {
    const icons: Record<string, string> = {
      workflow: '⚙️',
      automation: '🤖',
      user_pattern: '👤',
      entity: '🏷️',
      context: '📋',
      insight: '💡',
      conversation: '💬'
    };
    return icons[type] || '📝';
  };

  const formatDate = (date: string | Date) => {
    return new Date(date).toLocaleDateString();
  };

  return (
    <div
      className={`memory-card ${platform} p-4 border rounded-lg shadow-sm hover:shadow-md transition-shadow cursor-pointer bg-white`}
      onClick={handleSelect}
    >
      <div className="flex justify-between items-start mb-2">
        <div className="flex items-center space-x-2">
          <span className="text-lg">{getTypeIcon(memory.type)}</span>
          <span className="text-sm text-gray-500">{getPlatformIcon()}</span>
        </div>
        <div className="flex items-center space-x-2">
          <span className="text-xs text-gray-400">{formatDate(memory.timestamp)}</span>
          {onDelete && (
            <button
              onClick={handleDelete}
              className="text-red-500 hover:text-red-700 text-sm"
              title="Delete memory"
            >
              🗑️
            </button>
          )}
        </div>
      </div>

      <div className="memory-content">
        <h4 className="font-medium text-gray-900 mb-1 capitalize">
          {memory.type.replace('_', ' ')}
        </h4>
        <p className="text-sm text-gray-600 line-clamp-2">
          {typeof memory.content === 'string'
            ? memory.content
            : JSON.stringify(memory.content)}
        </p>
      </div>

      {memory.metadata?.tags && memory.metadata.tags.length > 0 && (
        <div className="memory-tags mt-2">
          <div className="flex flex-wrap gap-1">
            {memory.metadata.tags.slice(0, 3).map((tag: string, index: number) => (
              <span
                key={index}
                className="inline-block px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded-full"
              >
                {tag}
              </span>
            ))}
            {memory.metadata.tags.length > 3 && (
              <span className="inline-block px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded-full">
                +{memory.metadata.tags.length - 3}
              </span>
            )}
          </div>
        </div>
      )}

      <div className="memory-meta mt-2 flex justify-between items-center text-xs text-gray-500">
        <span>Access: {memory.metadata?.accessCount || 0}</span>
        <span>Importance: {memory.metadata?.importance || 'N/A'}</span>
      </div>
    </div>
  );
};

/**
 * Memory Stats Display Component
 * Shows platform-appropriate storage statistics
 */
const MemoryStatsDisplay: React.FC<MemoryStatsDisplayProps> = ({ stats, platform, storageLocation }) => {
  if (!stats) return null;

  const getStorageIcon = () => {
    return storageLocation === 'localStorage' ? '💾' : '☁️';
  };

  const getUsageColor = (percentage: number) => {
    if (percentage < 50) return 'text-green-600';
    if (percentage < 80) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="memory-stats p-4 bg-gray-50 rounded-lg">
      <h3 className="font-semibold text-gray-900 mb-3 flex items-center">
        <span className="mr-2">{getStorageIcon()}</span>
        Memory Statistics ({platform})
      </h3>

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <div className="text-gray-600">Total Memories</div>
          <div className="font-medium">{stats.totalMemories?.toLocaleString() || 0}</div>
        </div>

        <div>
          <div className="text-gray-600">Storage Used</div>
          <div className="font-medium">
            {(stats.totalSize / 1024 / 1024).toFixed(2)} MB
          </div>
        </div>

        {storageLocation === 'localStorage' && stats.storageUsage?.desktop && (
          <>
            <div>
              <div className="text-gray-600">Storage Limit</div>
              <div className="font-medium">
                {(stats.storageUsage.desktop.maxSize / 1024 / 1024).toFixed(2)} MB
              </div>
            </div>

            <div>
              <div className="text-gray-600">Usage</div>
              <div className={`font-medium ${getUsageColor(stats.storageUsage.desktop.usagePercentage || 0)}`}>
                {stats.storageUsage.desktop.usagePercentage?.toFixed(1) || 0}%
              </div>
            </div>
          </>
        )}

        {storageLocation === 's3' && stats.storageUsage?.web && (
          <div className="col-span-2">
            <div className="text-gray-600">S3 Bucket</div>
            <div className="font-medium">{stats.storageUsage.web.bucketName || 'Unknown'}</div>
          </div>
        )}
      </div>

      {stats.memoryTypes && Object.keys(stats.memoryTypes).length > 0 && (
        <div className="mt-4">
          <div className="text-sm text-gray-600 mb-2">Memory Types</div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(stats.memoryTypes).map(([type, count]) => (
              <span
                key={type}
                className="inline-block px-2 py-1 text-xs bg-purple-100 text-purple-800 rounded-full"
              >
                {type}: {count as number}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

/**
 * Main Memory Management Component
 * Provides unified UI for memory management across desktop and web platforms
 */
export const MemoryManagement: React.FC<MemoryManagementProps> = ({
  platform,
  userId,
  workspaceId,
  onMemorySelected,
  onError,
  className = ''
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [showStats, setShowStats] = useState(true);

  // Create platform-appropriate memory configuration
  const memoryConfig: UseUnifiedMemoryConfig = {
    platform,
    userId,
    workspaceId,
    enableMemory: true,
    autoInitialize: true,
    storage: {
      useLocalStorage: platform === 'desktop',
      offlineCapable: platform === 'desktop',
      encryptionEnabled: true
    },
    memory: {
      maxAge: 30 * 24 * 60 * 60 * 1000, // 30 days
      maxSize: platform === 'desktop' ? 50 * 1024 * 1024 : undefined, // 50MB limit for desktop
      cleanupInterval: 24 * 60 * 60 * 1000 // 24 hours
    }
  };

  const {
    memories,
    memoryStats,
    isLoading,
    isInitializing,
    error,
    isOnline,
    storeMemory,
    retrieveMemory,
    queryMemories,
    deleteMemory,
    getMemoryStats,
    cleanupExpiredMemories,
    refresh,
    platform: currentPlatform,
    storageLocation,
    isOfflineCapable
  } = useUnifiedMemory(memoryConfig);

  // Handle errors
  useEffect(() => {
    if (error && onError) {
      onError(error);
    }
  }, [error, onError]);

  // Filter memories based on search and type
  const filteredMemories = memories.filter(memory => {
    const matchesSearch = searchQuery === '' ||
      JSON.stringify(memory.content).toLowerCase().includes(searchQuery.toLowerCase()) ||
      memory.metadata?.tags?.some((tag: string) =>
        tag.toLowerCase().includes(searchQuery.toLowerCase())
      );

    const matchesType = selectedType === 'all' || memory.type === selectedType;

    return matchesSearch && matchesType;
  });

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
  };

  const handleTypeFilter = (type: string) => {
    setSelectedType(type);
  };

  const handleRefresh = async () => {
    await refresh();
  };

  const handleCleanup = async () => {
    const cleanedCount = await cleanupExpiredMemories();
    if (cleanedCount > 0) {
      await refresh();
    }
  };

  const handleDeleteMemory = async (memoryId: string) => {
    if (window.confirm('Are you sure you want to delete this memory?')) {
      await deleteMemory(memoryId);
      await refresh();
    }
  };

  const handleMemorySelect = (memory: any) => {
    onMemorySelected?.(memory);
  };

  const memoryTypes = [
    { value: 'all', label: 'All Types' },
    { value: 'workflow', label: 'Workflows' },
    { value: 'automation', label: 'Automations' },
    { value: 'user_pattern', label: 'User Patterns' },
    { value: 'conversation', label: 'Conversations' },
    { value: 'insight', label: 'Insights' }
  ];

  if (isInitializing) {
    return (
      <div className={`memory-management ${className} p-6`}>
        <div className="flex items-center justify-center py-8">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
            <div className="text-gray-600">Initializing Memory System...</div>
            <div className="text-sm text-gray-500 mt-1">
              Platform: {platform} | Storage: {storageLocation}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`memory-management ${className} bg-white rounded-lg shadow-sm`}>
      {/* Header */}
      <div className="p-4 border-b">
        <div className="flex justify-between items-center mb-4">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">Memory Management</h2>
            <div className="flex items-center space-x-2 mt-1">
              <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                platform === 'desktop'
                  ? 'bg-blue-100 text-blue-800'
                  : 'bg-green-100 text-green-800'
              }`}>
                {platform === 'desktop' ? '💻 Desktop' : '🌐 Web'}
              </span>
              <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                {storageLocation === 'localStorage' ? '💾 Local Storage' : '☁️ S3 Storage'}
              </span>
              {!isOnline && isOfflineCapable && (
                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                  🔌 Offline Mode
                </span>
              )}
            </div>
          </div>

          <div className="flex space-x-2">
            <button
              onClick={handleRefresh}
              disabled={isLoading}
              className="px-3 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {isLoading ? 'Refreshing...' : 'Refresh'}
            </button>
            <button
              onClick={handleCleanup}
              disabled={isLoading}
              className="px-3 py-2 text-sm bg-orange-600 text-white rounded-md hover:bg-orange-700 disabled:opacity-50"
            >
              Cleanup
            </button>
            <button
              onClick={() => setShowStats(!showStats)}
              className="px-3 py-2 text-sm bg-gray-600 text-white rounded-md hover:bg-gray-700"
            >
              {showStats ? 'Hide Stats' : 'Show Stats'}
            </button>
          </div>
        </div>

        {/* Search and Filters */}
        <div className="flex space-x-4">
          <div className="flex-1">
            <input
              type="text"
              placeholder="Search memories..."
              value={searchQuery}
              onChange={handleSearch}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div className="flex space-x-2">
            {memoryTypes.map(type => (
              <button
                key={type.value}
                onClick={() => handleTypeFilter(type.value)}
                className={`px-3 py-2 text-sm rounded-md ${
                  selectedType === type.value
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                {type.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Stats Panel */}
      {showStats && memoryStats && (
        <div className="p-4 border-b">
          <MemoryStatsDisplay
            stats={memoryStats}
            platform={platform}
            storageLocation={storageLocation}
          />
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="p-4 bg-red-50 border-b border-red-200">
          <div className="flex items-center">
            <span className="text-red-500 mr-2">⚠️</span>
            <span className="text-red-700 text-sm">{error}</span>
          </div>
        </div>
      )}

      {/* Memories Grid */}
      <div className="p-4">
        {filteredMemories.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            {searchQuery || selectedType !== 'all' ? (
              <>
                <div className="text-lg mb-2">No memories found</div>
                <div className="text-sm">
                  Try adjusting your search or filter criteria
                </div>
              </>
            ) : (
              <>
                <div className="text-lg mb-2">No memories yet</div>
                <div className="text-sm">
                  Memories will appear here as you use the {platform} app
                </div>
              </>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredMemories.map(memory => (
              <MemoryCard
                key={memory.id}
                memory={memory}
                platform={platform}
                onSelect={handleMemorySelect}
                onDelete={handleDeleteMemory}
              />
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t bg-gray-50">
        <div className="flex justify-between items-center text-sm text-gray-600">
          <div>
            Showing {filteredMemories.length} of {memories.length} memories
          </div>
          <div className="flex space-x-4">
            <span>Platform: {platform}</span>
            <span>Storage: {storageLocation}</span>
            <span>Status: {isOnline ? 'Online' : 'Offline'}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MemoryManagement;
