/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

export type View =
  | 'dashboard'
  | 'chat'
  | 'agents'
  | 'voice'
  | 'calendar'
  | 'tasks'
  | 'notes'
  | 'communications'
  | 'integrations'
  | 'workflows'
  | 'finances'
  | 'settings'
  | 'dev'
  | 'docs';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  isStreaming?: boolean;
}

export interface Agent {
  id: string;
  name: string;
  role: string;
  status: 'online' | 'offline' | 'busy';
  capabilities: string[];
  performance: {
    tasksCompleted: number;
    successRate: number;
    avgResponseTime: number;
  };
}

export interface CalendarEvent {
  id: string;
  title: string;
  startTime: string; // ISO string
  endTime: string; // ISO string
  color: 'blue' | 'green' | 'red' | 'purple' | 'orange';
}

export interface Subtask {
    id: string;
    title: string;
    completed: boolean;
}

export interface Task {
    id: string;
    title: string;
    description: string;
    status: 'pending' | 'in_progress' | 'completed';
    priority: 'low' | 'medium' | 'high' | 'critical';
    dueDate: string; // ISO string
    isImportant?: boolean;
    assignee?: string;
    tags?: string[];
    subtasks?: Subtask[];
    version: number;
    _optimistic?: boolean;
}

export interface Note {
    id: string;
    title: string;
    content: string;
    createdAt: string; // ISO string
    updatedAt: string; // ISO string
    type: 'meeting_notes' | 'personal_memo' | 'project_brief';
    eventId?: string;
}

export interface CommunicationsMessage {
    id: string;
    platform: string;
    from: {
        name: string;
        email?: string;
    };
    subject: string;
    preview: string;
    body: string;
    timestamp: string; // ISO string
    unread: boolean;
    read: boolean; // New field for read status
}

export interface Integration {
    id: string;
    displayName: string;
    serviceType: string;
    category: string;
    connected: boolean;
    lastSync?: string; // ISO string
    syncStatus?: 'success' | 'failed' | 'in_progress';
    devStatus: 'implemented' | 'development' | 'planned';
}

export interface Workflow {
    id: string;
    name: string;
    description: string;
    enabled: boolean;
    triggers: { type: string; config: Record<string, any> }[];
    actions: { type: string; config: Record<string, any> }[];
    executionCount: number;
    lastExecuted: string; // ISO string
}

export interface Transaction {
    id: string;
    date: string; // ISO string
    description: string;
    amount: number;
    category: string;
    type: 'debit' | 'credit';
}

export interface Budget {
    id: string;
    category: string;
    amount: number;
    spent: number;
}


export interface UserProfile {
    name: string;
    email: string;
    preferences: {
        language: string;
        timezone: string;
        theme: 'light' | 'dark';
        notifications: {
            email: boolean;
            push: boolean;
            channels: {
                tasks: boolean;
                calendar: boolean;
                communications: boolean;
            };
        }
    };
    advancedSettings?: AdvancedSettings;
}

export interface WidgetConfig {
    id: string;
    title: string;
    visible: boolean;
    position: number;
}

export interface AdvancedSettings {
    security: {
        twoFactorEnabled: boolean;
        passwordLastChanged: string; // ISO string
        sessionTimeout: number; // minutes
    };
    apiKeys: {
        openai: string;
        google: string;
        github: string;
    };
    privacy: {
        dataSharing: boolean;
        analytics: boolean;
        crashReports: boolean;
    };
    customization: {
        dashboardLayout: 'grid' | 'list';
        widgetOrder: string[];
        widgets: WidgetConfig[];
    };
}

export interface VoiceCommand {
    id: string;
    phrase: string;
    description: string;
    enabled: boolean;
    usageCount?: number;
    lastUsed?: string; // ISO string
    averageConfidence?: number;
}

export interface DevProject {
    id: string;
    name: string;
    status: 'building' | 'live' | 'error';
    progress: number;
    liveUrl: string;
    previewUrl: string;
    metrics: DevMetrics;
}

export interface DevMetrics {
    performance: number;
    mobile: number;
    seo: number;
    rebuildTime: number;
}

export interface DocContent {
    id: string;
    title: string;
    content: string;
}

export interface WeatherData {
    location: string;
    temperature: number;
    condition: string;
    humidity: number;
    windSpeed: number;
    icon: string;
}

export interface NewsItem {
    id: string;
    title: string;
    summary: string;
    source: string;
    publishedAt: string; // ISO string
    url: string;
}

export interface HealthMetrics {
    steps: number;
    sleepHours: number;
    heartRate: number;
    caloriesBurned: number;
}

export interface AgentLog {
    id: string;
    timestamp: string; // ISO string
    level: 'info' | 'warning' | 'error';
    message: string;
}

export interface IntegrationConfig {
    id: string;
    name: string;
    connected: boolean;
    config: Record<string, any>;
}

export interface CollaborationSession {
    id: string;
    taskId: string;
    participants: string[];
    activeUsers: string[];
    lastActivity: string; // ISO string
}

export interface TaskSuggestion {
    id: string;
    taskId: string;
    suggestion: string;
    confidence: number;
    type: 'priority' | 'deadline' | 'assignee' | 'subtask';
    createdAt: string; // ISO string
}

export interface AnalyticsMetric {
    id: string;
    name: string;
    value: number;
    change: number;
    trend: 'up' | 'down' | 'stable';
    period: string;
}

export interface VoiceTranscription {
    id: string;
    noteId: string;
    audioUrl: string;
    transcription: string;
    confidence: number;
    language: string;
    duration: number;
    createdAt: string; // ISO string
}

export interface SearchResult {
    id: string;
    type: 'task' | 'note' | 'message' | 'agent';
    title: string;
    content: string;
    relevance: number;
    metadata: Record<string, any>;
}

export interface NotificationPreference {
    id: string;
    type: 'task_due' | 'message_received' | 'agent_action' | 'system_update';
    enabled: boolean;
    channels: ('email' | 'push' | 'in_app')[];
    frequency: 'immediate' | 'hourly' | 'daily' | 'weekly';
}

export interface Notification {
    id?: string;
    type: 'success' | 'error' | 'info' | 'warning';
    title: string;
    message: string;
    timestamp?: number;
    duration?: number;
}

export interface PerformanceMetric {
    id: string;
    component: string;
    metric: string;
    value: number;
    timestamp: string; // ISO string
}
