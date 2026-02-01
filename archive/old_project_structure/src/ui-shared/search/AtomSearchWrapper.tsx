/**
 * ATOM Search Integration - Web & Desktop Bridge
 * Platform abstraction layer for search functionality
 */

import React from 'react';
import { AtomUnifiedSearch } from './AtomUnifiedSearch';

// Platform detection utilities
export const detectPlatform = (): 'web' | 'desktop' | 'mobile' => {
  // Check if running in Tauri (desktop)
  if (typeof window !== 'undefined' && window.__TAURI__) {
    return 'desktop';
  }
  
  // Check if mobile (can be expanded with more sophisticated detection)
  if (typeof window !== 'undefined' && /Mobi|Android/i.test(navigator.userAgent)) {
    return 'mobile';
  }
  
  // Default to web
  return 'web';
};

export const getPlatformConfig = () => {
  const platform = detectPlatform();
  
  const baseConfig = {
    isWeb: platform === 'web',
    isDesktop: platform === 'desktop',
    isMobile: platform === 'mobile',
    platform,
    capabilities: {
      notifications: false,
      fileSystem: false,
      systemIntegration: false,
      offlineMode: false,
      nativeMenus: false,
      hotkeys: false,
      autoUpdate: false
    }
  };
  
  // Desktop-specific capabilities
  if (platform === 'desktop') {
    baseConfig.capabilities.notifications = 'Notification' in window;
    baseConfig.capabilities.fileSystem = true; // Tauri provides file system APIs
    baseConfig.capabilities.systemIntegration = true; // Can integrate with system
    baseConfig.capabilities.offlineMode = true; // Desktop can work offline
    baseConfig.capabilities.nativeMenus = true; // Native menu support
    baseConfig.capabilities.hotkeys = true; // Global hotkeys
    baseConfig.capabilities.autoUpdate = true; // Auto-update capability
  }
  
  // Web-specific capabilities
  if (platform === 'web') {
    baseConfig.capabilities.notifications = 'Notification' in window;
    baseConfig.capabilities.offlineMode = 'serviceWorker' in navigator; // Service worker support
    baseConfig.capabilities.hotkeys = true; // Keyboard shortcuts work in web
  }
  
  // Mobile-specific capabilities
  if (platform === 'mobile') {
    baseConfig.capabilities.notifications = 'Notification' in window;
    baseConfig.capabilities.hotkeys = true;
    baseConfig.capabilities.offlineMode = 'serviceWorker' in navigator;
  }
  
  return baseConfig;
};

// Default app configuration
export const getDefaultAppConfig = () => {
  return {
    version: process.env.REACT_APP_VERSION || '1.0.0',
    environment: process.env.NODE_ENV || 'development' as 'development' | 'staging' | 'production',
    theme: 'system' as 'light' | 'dark' | 'system',
    language: 'en',
    integrations: ['gitlab', 'github', 'slack', 'gmail', 'notion', 'jira'],
    features: {
      vectorSearch: true,
      aiSearch: true,
      voiceSearch: false,
      offlineSearch: false,
      collaborativeSearch: false,
      realtimeSearch: true
    },
    performance: {
      maxResults: 50,
      searchTimeout: 5000,
      cacheEnabled: true,
      prefetchEnabled: true,
      lazyLoading: true
    }
  };
};

// Platform-specific search component wrapper
export const AtomSearchWrapper: React.FC<{
  onSearch?: (query: string, filters: any, options: any) => void;
  onResultClick?: (result: any) => void;
  onIntegrationClick?: (integration: string) => void;
}> = ({ onSearch, onResultClick, onIntegrationClick }) => {
  const platformConfig = getPlatformConfig();
  const appConfig = getDefaultAppConfig();
  
  // Load recent searches from appropriate storage
  const getRecentSearches = (): string[] => {
    if (platformConfig.isWeb || platformConfig.isDesktop) {
      const saved = localStorage.getItem('atom-search-recent');
      return saved ? JSON.parse(saved) : [];
    }
    return [];
  };
  
  // Load saved searches from appropriate storage
  const getSavedSearches = (): any[] => {
    if (platformConfig.isWeb || platformConfig.isDesktop) {
      const saved = localStorage.getItem('atom-search-saved');
      return saved ? JSON.parse(saved) : [];
    }
    return [];
  };
  
  // Get available integrations based on platform
  const getAvailableIntegrations = (): string[] => {
    let integrations = appConfig.integrations;
    
    // Filter integrations based on platform capabilities
    if (platformConfig.isDesktop) {
      // Add local integrations for desktop
      integrations = [...integrations, 'local_files', 'system_emails', 'system_contacts'];
    }
    
    return integrations;
  };
  
  // Enable/disable features based on platform
  const getFeatureFlags = () => {
    const flags = {
      vectorSearchEnabled: appConfig.features.vectorSearch,
      aiSearchEnabled: appConfig.features.aiSearch,
      voiceSearchEnabled: appConfig.features.voiceSearch && platformConfig.isDesktop, // Voice search only on desktop initially
      offlineModeEnabled: platformConfig.capabilities.offlineMode,
      collaborationEnabled: appConfig.features.collaborativeSearch
    };
    
    return flags;
  };
  
  const recentSearches = getRecentSearches();
  const savedSearches = getSavedSearches();
  const integrations = getAvailableIntegrations();
  const featureFlags = getFeatureFlags();
  
  // Platform-specific search handler
  const handleSearch = async (query: string, filters: any, options: any) => {
    // Call user-provided search handler
    if (onSearch) {
      await onSearch(query, filters, options);
      return;
    }
    
    // Default search implementation
    console.log('Platform search:', { platform: platformConfig.platform, query, filters, options });
  };
  
  // Platform-specific result click handler
  const handleResultClick = (result: any) => {
    // Call user-provided click handler
    if (onResultClick) {
      onResultClick(result);
      return;
    }
    
    // Default click behavior based on platform
    if (platformConfig.isDesktop && result.url) {
      if (result.url.startsWith('file://')) {
        // Open local file in system default app
        window.__TAURI__?.shell?.open(result.url).catch(console.error);
      } else {
        // Open external URL in default browser
        window.__TAURI__?.shell?.open(result.url).catch(console.error);
      }
    } else {
      // Web: open in new tab
      window.open(result.url, '_blank', 'noopener,noreferrer');
    }
  };
  
  // Integration click handler
  const handleIntegrationClick = (integration: string) => {
    // Call user-provided integration handler
    if (onIntegrationClick) {
      onIntegrationClick(integration);
      return;
    }
    
    // Default integration behavior
    console.log('Integration clicked:', integration);
  };
  
  return (
    <AtomUnifiedSearch
      platformConfig={platformConfig}
      appConfig={appConfig}
      onSearch={handleSearch}
      onResultClick={handleResultClick}
      onIntegrationClick={handleIntegrationClick}
      recentSearches={recentSearches}
      savedSearches={savedSearches}
      integrations={integrations}
      vectorSearchEnabled={featureFlags.vectorSearchEnabled}
      aiSearchEnabled={featureFlags.aiSearchEnabled}
      voiceSearchEnabled={featureFlags.voiceSearchEnabled}
      offlineMode={featureFlags.offlineModeEnabled}
      collaborationEnabled={featureFlags.collaborationEnabled}
    />
  );
};

// Export for use in both web and desktop applications
export default AtomSearchWrapper;