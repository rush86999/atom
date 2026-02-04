/**
 * Platform-specific configuration for ATOM
 *
 * Provides consistent configuration across desktop and web platforms
 * Ensures UI and feature parity with appropriate storage backends
 */

export interface PlatformConfig {
  platform: 'desktop' | 'web';
  storage: {
    useLocalStorage: boolean;
    offlineCapable: boolean;
    encryptionEnabled: boolean;
    localDataPath?: string;
    s3Config?: S3StorageConfig;
  };
  features: {
    voiceProcessing: boolean;
    wakeWordDetection: boolean;
    realTimeProcessing: boolean;
    backgroundTasks: boolean;
    systemIntegration: boolean;
  };
  ui: {
    responsive: boolean;
    touchFriendly: boolean;
    systemThemeIntegration: boolean;
    nativeControls: boolean;
  };
  performance: {
    memoryLimit: number;
    cacheSize: number;
    backgroundProcessing: boolean;
    resourceOptimization: boolean;
  };
}

export interface S3StorageConfig {
  bucketName: string;
  region: string;
  accessKeyId?: string;
  secretAccessKey?: string;
  endpoint?: string;
}

export interface MemorySystemConfig {
  maxAge: number;
  maxSize?: number;
  cleanupInterval: number;
  syncInterval?: number;
}

/**
 * Desktop Platform Configuration
 * Optimized for offline use with local storage
 */
export const desktopPlatformConfig: PlatformConfig = {
  platform: 'desktop',
  storage: {
    useLocalStorage: true,
    offlineCapable: true,
    encryptionEnabled: true,
    localDataPath: undefined, // Will be set by the desktop app
  },
  features: {
    voiceProcessing: true,
    wakeWordDetection: true,
    realTimeProcessing: true,
    backgroundTasks: true,
    systemIntegration: true,
  },
  ui: {
    responsive: true,
    touchFriendly: false, // Desktop typically doesn't need touch optimization
    systemThemeIntegration: true,
    nativeControls: true,
  },
  performance: {
    memoryLimit: 50 * 1024 * 1024, // 50MB for localStorage
    cacheSize: 100 * 1024 * 1024, // 100MB cache
    backgroundProcessing: true,
    resourceOptimization: true,
  },
};

/**
 * Web Platform Configuration
 * Optimized for cloud storage and browser compatibility
 */
export const webPlatformConfig: PlatformConfig = {
  platform: 'web',
  storage: {
    useLocalStorage: false,
    offlineCapable: false,
    encryptionEnabled: true,
    s3Config: {
      bucketName: 'atom-platform-data',
      region: 'us-east-1',
      // accessKeyId and secretAccessKey should be provided at runtime
    },
  },
  features: {
    voiceProcessing: false, // Limited in browsers
    wakeWordDetection: false, // Not supported in browsers
    realTimeProcessing: true,
    backgroundTasks: false, // Limited in browsers
    systemIntegration: false, // Limited in browsers
  },
  ui: {
    responsive: true,
    touchFriendly: true, // Web apps should be touch-friendly
    systemThemeIntegration: false,
    nativeControls: false,
  },
  performance: {
    memoryLimit: 10 * 1024 * 1024, // 10MB for browser memory
    cacheSize: 50 * 1024 * 1024, // 50MB cache
    backgroundProcessing: false,
    resourceOptimization: true,
  },
};

/**
 * Memory System Configuration
 * Consistent across platforms with platform-specific optimizations
 */
export const desktopMemoryConfig: MemorySystemConfig = {
  maxAge: 30 * 24 * 60 * 60 * 1000, // 30 days
  maxSize: 50 * 1024 * 1024, // 50MB limit for desktop
  cleanupInterval: 24 * 60 * 60 * 1000, // 24 hours
  syncInterval: undefined, // Desktop doesn't need sync
};

export const webMemoryConfig: MemorySystemConfig = {
  maxAge: 30 * 24 * 60 * 60 * 1000, // 30 days
  maxSize: undefined, // No size limit for cloud storage
  cleanupInterval: 24 * 60 * 60 * 1000, // 24 hours
  syncInterval: 5 * 60 * 1000, // 5 minutes sync interval
};

/**
 * Feature flags for platform-specific capabilities
 */
export const platformFeatures = {
  desktop: {
    // Desktop-specific features
    systemTray: true,
    globalShortcuts: true,
    fileSystemAccess: true,
    hardwareAcceleration: true,
    backgroundService: true,
    autoStart: true,
    notifications: true,
    // Memory features
    localVectorStorage: true,
    offlineEmbedding: true,
    persistentCache: true,
  },
  web: {
    // Web-specific features
    serviceWorker: true,
    pushNotifications: true,
    indexedDB: true,
    webRTC: false,
    geolocation: false,
    // Memory features
    cloudVectorStorage: true,
    realTimeSync: true,
    collaborativeEditing: true,
  },
};

/**
 * UI Configuration for consistent experience
 */
export const uiConfig = {
  desktop: {
    window: {
      minWidth: 800,
      minHeight: 600,
      defaultWidth: 1200,
      defaultHeight: 800,
      resizable: true,
      frame: true,
    },
    theme: {
      systemIntegration: true,
      darkMode: 'auto',
      animations: true,
    },
    navigation: {
      sidebar: true,
      breadcrumbs: true,
      keyboardShortcuts: true,
    },
  },
  web: {
    layout: {
      responsiveBreakpoints: {
        mobile: 768,
        tablet: 1024,
        desktop: 1200,
      },
      mobileFirst: true,
    },
    theme: {
      systemIntegration: false,
      darkMode: 'media',
      animations: true,
    },
    navigation: {
      sidebar: false, // Use bottom navigation on mobile
      breadcrumbs: true,
      keyboardShortcuts: false,
    },
  },
};

/**
 * Storage configuration helpers
 */
export function createStorageConfig(platform: 'desktop' | 'web', customConfig?: Partial<PlatformConfig>): PlatformConfig {
  const baseConfig = platform === 'desktop' ? desktopPlatformConfig : webPlatformConfig;
  return {
    ...baseConfig,
    ...customConfig,
    storage: {
      ...baseConfig.storage,
      ...customConfig?.storage,
    },
    features: {
      ...baseConfig.features,
      ...customConfig?.features,
    },
    ui: {
      ...baseConfig.ui,
      ...customConfig?.ui,
    },
    performance: {
      ...baseConfig.performance,
      ...customConfig?.performance,
    },
  };
}

export function createMemoryConfig(platform: 'desktop' | 'web'): MemorySystemConfig {
  return platform === 'desktop' ? desktopMemoryConfig : webMemoryConfig;
}

/**
 * Platform detection utilities
 */
export function isDesktopEnvironment(): boolean {
  // Check for Tauri environment
  if (typeof window !== 'undefined' && (window as any).__TAURI__) {
    return true;
  }

  // Check for Electron environment
  if (typeof window !== 'undefined' && (window as any).electron) {
    return true;
  }

  // Check for Node.js environment (desktop apps typically run in Node)
  if (typeof process !== 'undefined' && process.versions?.node) {
    return true;
  }

  return false;
}

export function isWebEnvironment(): boolean {
  return typeof window !== 'undefined' && !isDesktopEnvironment();
}

export function getCurrentPlatform(): 'desktop' | 'web' {
  return isDesktopEnvironment() ? 'desktop' : 'web';
}

/**
 * Export platform configuration based on current environment
 */
export const currentPlatformConfig: PlatformConfig = createStorageConfig(getCurrentPlatform());
export const currentMemoryConfig: MemorySystemConfig = createMemoryConfig(getCurrentPlatform());
