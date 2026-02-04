// Core communication types
export type CommunicationType =
  | "follow-up"
  | "relationship-maintenance"
  | "celebration"
  | "crisis"
  | "proactive-reachout"
  | "introduction"
  | "content-sharing"
  | "urgent";

export type CommunicationChannel =
  | "email"
  | "slack"
  | "teams"
  | "discord"
  | "linkedin"
  | "twitter"
  | "sms"
  | "phone"
  | "voicemail"
  | "in-person"
  | "all";

export type CommunicationPriority = "urgent" | "high" | "medium" | "low";

export interface CommunicationPreferences {
  preferredChannels: Record<string, CommunicationChannel[]>;
  nonWorkingHours: {
    start: number; // Hour (0-23)
    end: number; // Hour (0-23)
  };
  responseTimeExpectations: Record<string, number>; // ContactId -> expected response hours
  autoResponseTriggers: string[];
  doNotDisturbList: string[];
  tonePreferences: Record<
    string,
    "formal" | "casual" | "friendly" | "professional"
  >;
  messageLengthPreference: "short" | "medium" | "long";
  emojiUsage: boolean;
}

export interface ContactRelationship {
  id: string;
  name: string;
  email: string;
  phone?: string;
  relationshipType:
    | "family"
    | "friend"
    | "colleague"
    | "client"
    | "vendor"
    | "network"
    | "mentor"
    | "mentee";
  closenessScore: number; // 0-100
  lastCommunicationAt: Date;
  preferredChannel: CommunicationChannel;
  timezone: string;
  lastInteractionType: CommunicationType;
  responseRate: number; // 0-100
  averageResponseTime: number; // hours
  topicsOfInterest: string[];
  importantMilestones: ContactMilestone[];
  relationshipHistory: RelationshipEvent[];
  mutualConnections: string[];
}

export interface ContactMilestone {
  type:
    | "work-anniversary"
    | "birthday"
    | "promotion"
    | "birth"
    | "marriage"
    | "achievement";
  date: Date;
  description: string;
  importance: number; // 0-1
  acknowledged: boolean;
  lastAcknowledged?: Date;
}

export interface RelationshipEvent {
  type: "positive" | "neutral" | "negative";
  date: Date;
  description: string;
  channel: CommunicationChannel;
  sentiment: number; // -1 to 1
}

export interface CommunicationContext {
  timestamp: Date;
  userId: string;
  recentCommunications: CommunicationRecord[];
  activeRelationships: ContactRelationship[];
  platformStatus: Record<CommunicationChannel, boolean>;
  preferences: CommunicationPreferences;
  emotionalContext: EmotionalContext;
  externalFactors: ExternalFactors;
  crisisDetails?: any;
  userAvailability: {
    busy: boolean;
    nextAvailable: Date;
    currentFocus: string;
  };
}

export interface EmotionalContext {
  currentMood:
    | "positive"
    | "neutral"
    | "negative"
    | "stressed"
    | "excited"
    | "calm";
  recentSentiment: number; // -1 to 1
  factors: string[];
  lastUpdated: Date;
}

export interface ExternalFactors {
  isWeekend: boolean;
  timeOfDay: number;
  scheduleBusy: boolean;
  weather: string;
  moodIndicators: any;
  holidays: string[];
  events: CalendarEvent[];
}

export interface CalendarEvent {
  title: string;
  start: Date;
  end: Date;
  attendees: string[];
  category: "meeting" | "focus-time" | "travel" | "social" | "personal";
}

export interface CommunicationRecord {
  id: string;
  type: CommunicationType;
  senderId: string;
  recipientId: string;
  channel: CommunicationChannel;
  timestamp: Date;
  message: string;
  status: "sent" | "failed" | "pending";
  context: any;
  requiresFollowUp?: boolean;
  followUpScheduled?: boolean;
  responseReceived?: boolean;
  priority: CommunicationPriority;
  sentimentScore?: number;
  categories: string[];
  tokensUsed: number;
  performance: CommunicationPerformance;
}

export interface CommunicationPerformance {
  openRate?: number;
  clickRate?: number;
  responseRate?: number;
  positiveFeedback?: number;
  replyTime?: number; // minutes
  conversionRate?: number; // for sales/inbound
}

export interface ScheduledCommunication extends AutonomousCommunications {
  id: string;
  createdAt: Date;
  scheduledFor: Date;
  executedAt?: Date;
  canceled?: boolean;
  retryCount: number;
  dependencies: string[];
}

// Core communication object for the autonomous system
export interface AutonomousCommunications {
  type: CommunicationType;
  priority: CommunicationPriority;
+  recipient: string;
+  channel: CommunicationChannel;
+  context: any;
+  scheduledTime: Date;
+  reasoning: string;
+  message?: string;
+  suggestions?: string[];
+  expectedResponseTime?: number;
+}

// Learning and memory interfaces
+export interface LearningPoint {
+  communication: AutonomousCommunications;
+  result: any;
+  timestamp: Date;
+  success: boolean;
+  feedback: string;
+}

// System status and analytics
+export interface SystemStatus {
+  isRunning: boolean;
+  lastCheck: Date;
+  pendingCommunications: number;
+  completedCommunications: number;
+  failedCommunications: number;
+  averageResponseTime: number;
+  systemHealth: 'healthy' | 'warning' | 'error';
+}

+export interface CommunicationAnalytics {
+  totalCommunications: number;
+  successRate: number;
+  responseRate: number;
+  engagementScore: number;
+  relationshipHealth: Record<string, number>;
+  channelUsage: Record<CommunicationChannel, number>;
+  timeDistribution: Record<string, number>;
+}
