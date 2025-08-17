// Configuration file for Autonomous Communication System

export interface ACSConfig {
  // System settings
  autonomousMode: boolean;
  learningEnabled: boolean;
  maxConcurrentMessages: number;
  retryPolicy: {
    maxRetries: number;
    baseDelay: number; // milliseconds
    backOffMultiplier: number;
  };

  // Scheduling settings
  maxMessagesPerDay: number;
  cooldownPeriod: number; // milliseconds between messages
  businessHours: {
    start: number; // hour (0-23)
    end: number; // hour (0-23)
  };

  // Platform settings
  enabledPlatforms: string[];
  platformLimits: {
    [platform: string]: {
      dailyLimit: number;
      optimalHours?: number[];
      rateLimit?: number;
    };
  };

  // Relationship settings
  staleThresholdDays: number;
  milestoneAlertWindow: number; // days before milestone
  maxOutreachPerContact: number; // per week
}

export const DEFAULT_CONFIG: ACSConfig = {
  autonomousMode: true,
  learningEnabled: true,
  maxConcurrentMessages: 10,
  retryPolicy: {
    maxRetries: 3,
    baseDelay: 60000, // 1 minute
    backOffMultiplier: 2
  },
  maxMessagesPerDay: 15,
  cooldownPeriod: 300000, // 5 minutes
  businessHours: {
    start: 9,
    end: 17
  },
  enabledPlatforms: ['email', 'slack', 'teams', 'linkedin'],
  platformLimits: {
    email: { dailyLimit: 10, optimalHours: [9, 14, 16] },
    slack: { dailyLimit: 5, optimalHours: [10, 14] },
    teams: { dailyLimit: 3, optimalHours: [11, 15] },
    linkedin: { dailyLimit: 2, optimalHours: [9, 17] }
  },
  staleThresholdDays: 30,
  milestoneAlertWindow: 3,
  maxOutreachPerContact: 2
};

// Export instance for dynamic configuration
export const ACS_CONFIG = { ...DEFAULT_CONFIG };
