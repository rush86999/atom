/**
 * Unified Platform Architecture for ATOM
 *
 * Provides complete UI and feature parity between desktop and web platforms
 * with platform-appropriate implementations for system-specific capabilities
 */

// Platform types and interfaces
export type Platform = 'desktop' | 'web';
export type Environment = 'development' | 'production' | 'test';

export interface UnifiedPlatformConfig {
  platform: Platform;
  environment: Environment;
  features: PlatformFeatures;
  ui: PlatformUIConfig;
  storage: PlatformStorageConfig;
  integrations: PlatformIntegrationsConfig;
  capabilities: PlatformCapabilities;
}

export interface PlatformFeatures {
  // Core features available on both platforms
  chatInterface: boolean;
  automationEngine: boolean;
  workflowManagement: boolean;
  taskManagement: boolean;
  calendarIntegration: boolean;
  fileManagement: boolean;
  search: boolean;
  analytics: boolean;
  notifications: boolean;

  // Platform-specific feature flags
  desktopOnly: DesktopFeatures;
  webOnly: WebFeatures;
}

export interface DesktopFeatures {
  systemTray: boolean;
  globalShortcuts: boolean;
  fileSystemAccess: boolean;
  hardwareAcceleration: boolean;
  backgroundService: boolean;
  autoStart: boolean;
  systemNotifications: boolean;
  offlineMode: boolean;
  voiceProcessing: boolean;
  wakeWordDetection: boolean;
}

export interface WebFeatures {
  serviceWorker: boolean;
  pushNotifications: boolean;
  indexedDB: boolean;
  realTimeSync: boolean;
  collaborativeEditing: boolean;
  multiDeviceAccess: boolean;
  cloudBackup: boolean;
  progressiveWebApp: boolean;
}

export interface PlatformUIConfig {
  responsive: boolean;
  touchFriendly: boolean;
  systemThemeIntegration: boolean;
  nativeControls: boolean;
  animations: boolean;
  layout: UILayoutConfig;
  navigation: UINavigationConfig;
}

export interface UILayoutConfig {
  desktop: {
    minWidth: number;
    minHeight: number;
    defaultWidth: number;
    defaultHeight: number;
    resizable: boolean;
    frame: boolean;
  };
  web: {
    responsiveBreakpoints: {
      mobile: number;
      tablet: number;
      desktop: number;
    };
    mobileFirst: boolean;
  };
}

export interface UINavigationConfig {
  sidebar: boolean;
  breadcrumbs: boolean;
  keyboardShortcuts: boolean;
  mobileNavigation: boolean;
}

export interface PlatformStorageConfig {
  memory: StorageBackendConfig;
  files: StorageBackendConfig;
  cache: StorageBackendConfig;
  preferences: StorageBackendConfig;
}

export interface StorageBackendConfig {
  desktop: StorageImplementation;
  web: StorageImplementation;
}

export interface StorageImplementation {
  type: 'localStorage' | 'indexedDB' | 'fileSystem' | 's3' | 'cloudStorage';
  encryption: boolean;
  sync: boolean;
  offline: boolean;
  capacity?: number;
}

export interface PlatformIntegrationsConfig {
  available: string[];
  oauth: boolean;
  apiKeys: boolean;
  webhooks: boolean;
  realTime: boolean;
}

export interface PlatformCapabilities {
  performance: PerformanceCapabilities;
  security: SecurityCapabilities;
  networking: NetworkingCapabilities;
  hardware: HardwareCapabilities;
}

export interface PerformanceCapabilities {
  memoryLimit: number;
  cacheSize: number;
  backgroundProcessing: boolean;
  resourceOptimization: boolean;
  parallelProcessing: boolean;
}

export interface SecurityCapabilities {
  encryption: boolean;
  sandbox: boolean;
  permissions: boolean;
  auditLogging: boolean;
  dataIsolation: boolean;
}

export interface NetworkingCapabilities {
  offline: boolean;
  realTime: boolean;
  fileUpload: boolean;
  streaming: boolean;
  compression: boolean;
}

export interface HardwareCapabilities {
  audio: boolean;
  video: boolean;
  sensors: boolean;
  bluetooth: boolean;
  usb: boolean;
}

// Platform configuration presets
export const desktopPlatformConfig: UnifiedPlatformConfig = {
  platform: 'desktop',
  environment: 'development',
  features: {
    chatInterface: true,
    automationEngine: true,
    workflowManagement: true,
    taskManagement: true,
    calendarIntegration: true,
    fileManagement: true,
    search: true,
    analytics: true,
    notifications: true,
    desktopOnly: {
      systemTray: true,
      globalShortcuts: true,
      fileSystemAccess: true,
      hardwareAcceleration: true,
      backgroundService: true,
      autoStart: true,
      systemNotifications: true,
      offlineMode: true,
      voiceProcessing: true,
      wakeWordDetection: true,
    },
    webOnly: {
      serviceWorker: false,
      pushNotifications: false,
      indexedDB: false,
      realTimeSync: false,
      collaborativeEditing: false,
      multiDeviceAccess: false,
      cloudBackup: false,
      progressiveWebApp: false,
    },
  },
  ui: {
    responsive: true,
    touchFriendly: false,
    systemThemeIntegration: true,
    nativeControls: true,
    animations: true,
    layout: {
      desktop: {
        minWidth: 800,
        minHeight: 600,
        defaultWidth: 1200,
        defaultHeight: 800,
        resizable: true,
        frame: true,
      },
      web: {
        responsiveBreakpoints: {
          mobile: 768,
          tablet: 1024,
          desktop: 1200,
        },
        mobileFirst: false,
      },
    },
    navigation: {
      sidebar: true,
      breadcrumbs: true,
      keyboardShortcuts: true,
      mobileNavigation: false,
    },
  },
  storage: {
    memory: {
      desktop: {
        type: 'localStorage',
        encryption: true,
        sync: false,
        offline: true,
        capacity: 50 * 1024 * 1024, // 50MB
      },
      web: {
        type: 's3',
        encryption: true,
        sync: true,
        offline: false,
      },
    },
    files: {
      desktop: {
        type: 'fileSystem',
        encryption: true,
        sync: false,
        offline: true,
      },
      web: {
        type: 'cloudStorage',
        encryption: true,
        sync: true,
        offline: false,
      },
    },
    cache: {
      desktop: {
        type: 'fileSystem',
        encryption: false,
        sync: false,
        offline: true,
        capacity: 100 * 1024 * 1024, // 100MB
      },
      web: {
        type: 'indexedDB',
        encryption: false,
        sync: false,
        offline: true,
        capacity: 50 * 1024 * 1024, // 50MB
      },
    },
    preferences: {
      desktop: {
        type: 'localStorage',
        encryption: true,
        sync: false,
        offline: true,
      },
      web: {
        type: 'localStorage',
        encryption: true,
        sync: false,
        offline: true,
      },
    },
  },
  integrations: {
    available: [
      'slack', 'teams', 'notion', 'trello', 'figma', 'linear', 'asana',
      'gmail', 'outlook', 'github', 'jira', 'stripe', 'box', 'dropbox', 'gdrive'
    ],
    oauth: true,
    apiKeys: true,
    webhooks: true,
    realTime: true,
  },
  capabilities: {
    performance: {
      memoryLimit: 1024 * 1024 * 1024, // 1GB
      cacheSize: 100 * 1024 * 1024, // 100MB
      backgroundProcessing: true,
      resourceOptimization: true,
      parallelProcessing: true,
    },
    security: {
      encryption: true,
      sandbox: true,
      permissions: true,
      auditLogging: true,
      dataIsolation: true,
    },
    networking: {
      offline: true,
      realTime: true,
      fileUpload: true,
      streaming: true,
      compression: true,
    },
    hardware: {
      audio: true,
      video: true,
      sensors: true,
      bluetooth: true,
      usb: true,
    },
  },
};

export const webPlatformConfig: UnifiedPlatformConfig = {
  platform: 'web',
  environment: 'development',
  features: {
    chatInterface: true,
    automationEngine: true,
    workflowManagement: true,
    taskManagement: true,
    calendarIntegration: true,
    fileManagement: true,
    search: true,
    analytics: true,
    notifications: true,
    desktopOnly: {
      systemTray: false,
      globalShortcuts: false,
      fileSystemAccess: false,
      hardwareAcceleration: false,
      backgroundService: false,
      autoStart: false,
      systemNotifications: false,
      offlineMode: false,
      voiceProcessing: false,
      wakeWordDetection: false,
    },
    webOnly: {
      serviceWorker: true,
      pushNotifications: true,
      indexedDB: true,
      realTimeSync: true,
      collaborativeEditing: true,
      multiDeviceAccess: true,
      cloudBackup: true,
      progressiveWebApp: true,
    },
  },
  ui: {
    responsive: true,
    touchFriendly: true,
    systemThemeIntegration: false,
    nativeControls: false,
    animations: true,
    layout: {
      desktop: {
        minWidth: 800,
        minHeight: 600,
        defaultWidth: 1200,
        defaultHeight: 800,
        resizable: false,
        frame: false,
      },
      web: {
        responsiveBreakpoints: {
          mobile: 768,
          tablet: 1024,
          desktop: 1200,
        },
        mobileFirst: true,
      },
    },
    navigation: {
      sidebar: false,
      breadcrumbs: true,
      keyboardShortcuts: false,
      mobileNavigation: true,
    },
  },
  storage: {
    memory: {
      desktop: {
        type: 'localStorage',
        encryption: true,
        sync: false,
        offline: true,
        capacity: 50 * 1024 * 1024,
      },
      web: {
        type: 's3',
        encryption: true,
        sync: true,
        offline: false,
      },
    },
    files: {
      desktop: {
        type: 'fileSystem',
        encryption: true,
        sync: false,
        offline: true,
      },
      web: {
        type: 'cloudStorage',
        encryption: true,
        sync: true,
        offline: false,
      },
    },
    cache: {
      desktop: {
        type: 'fileSystem',
        encryption: false,
        sync: false,
        offline: true,
        capacity: 100 * 1024 * 1024,
      },
      web: {
        type: 'indexedDB',
        encryption: false,
        sync: false,
        offline: true,
        capacity: 50 * 1024 * 1024,
      },
    },
    preferences: {
      desktop: {
        type: 'localStorage',
        encryption: true,
        sync: false,
        offline: true,
      },
      web: {
        type: 'localStorage',
        encryption: true,
        sync: false,
        offline: true,
      },
    },
  },
  integrations: {
    available: [
      'slack', 'teams', 'notion', 'trello', 'figma', 'linear', 'asana',
      'gmail', 'outlook', 'github', 'jira', 'stripe', 'box', 'dropbox', 'gdrive'
    ],
    oauth: true,
    apiKeys: true,
    webhooks: true,
    realTime: true,
  },
  capabilities: {
    performance: {
      memoryLimit: 256 * 1024 * 1024, // 256MB
      cacheSize: 50 * 1024 * 1024, // 50MB
      backgroundProcessing: false,
      resourceOptimization: true,
      parallelProcessing: false,
    },
    security: {
      encryption: true,
      sandbox: true,
      permissions: true,
      auditLogging: true,
      dataIsolation: true,
    },
    networking: {
      offline: false,
      realTime: true,
      fileUpload: true,
      streaming: true,
      compression: true,
    },
    hardware: {
      audio: false,
      video: false,
      sensors: false,
      bluetooth: false,
      usb: false,
    },
  },
};

// Platform detection and utilities
export class UnifiedPlatform {
  private static instance: UnifiedPlatform;
  private config: UnifiedPlatformConfig;

  private constructor() {
    this.config = this.detectPlatform();
  }

  public static getInstance(): UnifiedPlatform {
    if (!UnifiedPlatform.instance) {
      UnifiedPlatform.instance = new UnifiedPlatform();
    }
    return UnifiedPlatform.instance;
  }

  private detectPlatform(): UnifiedPlatformConfig {
    // Check for Tauri environment (desktop)
    if (typeof window !== 'undefined' && (window as any).__TAURI__) {
      return desktopPlatformConfig;
    }

    // Check for Electron environment (desktop)
    if (typeof window !== 'undefined' && (window as any).electron) {
      return desktopPlatformConfig;
    }

    // Check for Node.js environment (desktop apps typically run in Node)
    if (typeof process !== 'undefined' && process.versions?.node) {
      return desktopPlatformConfig;
    }

    // Default to web platform
    return webPlatformConfig;
  }

  public getConfig(): UnifiedPlatformConfig {
    return this.config;
  }

  public getPlatform(): Platform {
    return this.config.platform;
  }

  public isDesktop(): boolean {
    return this.config.platform === 'desktop';
  }

  public isWeb(): boolean {
    return this.config.platform === 'web';
  }

  public getFeature<T extends keyof PlatformFeatures>(feature: T): PlatformFeatures[T] {
    return this.config.features[feature];
  }

  public hasFeature(feature: keyof PlatformFeatures): boolean {
    return this.config.features[feature] === true;
  }

  public getStorageConfig(storageType: keyof PlatformStorageConfig): StorageImplementation {
    const storageConfig = this.config.storage[storageType];
    return this.isDesktop() ? storageConfig.desktop : storageConfig.web;
  }

  public getUIConfig(): PlatformUIConfig {
    return this.config.ui;
  }

  public getCapabilities(): PlatformCapabilities {
    return this.config.capabilities;
  }

  public getIntegrations(): PlatformIntegrationsConfig {
    return this.config.integrations;
  }

  // Platform-specific feature checks
  public canUseSystemTray(): boolean {
    return this.config.features.desktopOnly.systemTray;
  }

  public canUseGlobalShortcuts(): boolean {
    return this.config.features.desktopOnly.globalShortcuts;
  }

  public canUseFileSystem(): boolean {
    return this.config.features.desktopOnly.fileSystemAccess;
  }

  public canUseServiceWorker(): boolean {
    return this.config.features.webOnly.serviceWorker;
  }

  public canUsePushNotifications(): boolean {
    return this.config.features.webOnly.pushNotifications;
  }

  public canUseRealTimeSync(): boolean {
    return this.config.features.webOnly.realTimeSync;
  }

  // Environment helpers
  public setEnvironment(environment: Environment): void {
    this.config.environment = environment;
  }

  public isDevelopment(): boolean {
    return this.config.environment === 'development';
  }

  public isProduction(): boolean {
    return this.config.environment === 'production';
  }

  public isTest(): boolean {
    return this.config.environment === 'test';
  }
}

// Export singleton instance
export const platform = UnifiedPlatform.getInstance();

// Utility functions for common platform checks
export function isDesktopEnvironment(): boolean {
  return platform.isDesktop();
}

export function isWebEnvironment(): boolean {
  return platform.isWeb();
}

export function getCurrentPlatform(): Platform {
  return platform.getPlatform();
}

export function createPlatformConfig(customConfig?: Partial<UnifiedPlatformConfig>): UnifiedPlatformConfig {
  const baseConfig = platform.getConfig();
  return {
    ...baseConfig,
    ...customConfig,
    features: {
      ...baseConfig.features,
      ...customConfig?.features,
    },
    ui: {
      ...baseConfig.ui,
      ...customConfig?.ui,
    },
    storage: {
      ...baseConfig.storage,
      ...customConfig?.storage,
    },
    integrations: {
      ...baseConfig.integrations,
      ...customConfig?.integrations,
    },
    capabilities: {
      ...baseConfig.capabilities,
      ...customConfig?.capabilities,
    },
  };
}

// Feature availability checks
export const featureFlags = {
  // Core features available on both platforms
  chatInterface: () => platform.hasFeature('chatInterface'),
  automationEngine: () => platform.hasFeature('automationEngine'),
  workflowManagement: () => platform.hasFeature('workflowManagement'),
  taskManagement: () => platform.hasFeature('taskManagement'),
  calendarIntegration: () => platform.hasFeature('calendarIntegration'),
  fileManagement: () => platform.hasFeature('fileManagement'),
  search: () => platform.hasFeature('search'),
  analytics: () => platform.hasFeature('analytics'),
  notifications: () => platform.hasFeature('notifications'),

  // Platform-specific features
  systemTray: () => platform.canUseSystemTray(),
  globalShortcuts: () => platform.canUseGlobalShortcuts(),
  fileSystemAccess: () => platform.canUseFileSystem(),
  serviceWorker: () => platform.canUseServiceWorker(),
  pushNotifications: () => platform.canUsePushNotifications(),
  realTimeSync: () => platform.canUseRealTimeSync(),
  offlineMode: () => platform.getFeature('desktopOnly').offlineMode,
  voiceProcessing: () => platform.getFeature('desktopOnly').voiceProcessing,
  collaborativeEditing: () => platform.getFeature('webOnly').collaborativeEditing,
  multiDeviceAccess: () => platform.getFeature('webOnly').multiDeviceAccess,
};

// Storage utility functions
export function getStorageBackend(type: keyof PlatformStorageConfig): StorageImplementation {
  return platform.getStorageConfig(type);
}

export function getMemoryStorage(): StorageImplementation {
  return getStorageBackend('memory');
}

export function getFileStorage(): StorageImplementation {
  return getStorageBackend('files');
}

export function getCacheStorage(): StorageImplementation {
  return getStorageBackend('cache');
}

export function getPreferencesStorage(): StorageImplementation {
  return getStorageBackend('preferences');
}

// Export types for external use
export type {
  PlatformFeatures,
  DesktopFeatures,
  WebFeatures,
  PlatformUIConfig,
  PlatformStorageConfig,
  PlatformIntegrationsConfig,
  PlatformCapabilities
};
