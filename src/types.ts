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
  | 'dev';

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

export interface Task {
    id: string;
    title: string;
    description: string;
    status: 'pending' | 'in_progress' | 'completed';
    priority: 'low' | 'medium' | 'high' | 'critical';
    dueDate: string; // ISO string
    isImportant?: boolean;
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
        notifications: {
            email: boolean;
            push: boolean;
        }
    }
}

export interface VoiceCommand {
    id: string;
    phrase: string;
    description: string;
    enabled: boolean;
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

// FIX: Add missing DocContent type export.
export interface DocContent {
    id: string;
    title: string;
    content: string;
}
