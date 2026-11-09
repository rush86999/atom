/**
 * Navigation Types
 *
 * Central type definitions for all navigation structures
 */

import type { LinkingOptions, NavigatorScreenParams } from '@react-navigation/native';
import type { CanvasType } from '../types/canvas';

/**
 * Canvas Viewer Navigation Types
 */
export type CanvasViewerParams = {
  canvasId: string;
  canvasType?: CanvasType;
  sessionId?: string;
  agentId?: string;
};

/**
 * Auth Stack Navigation Types
 */
export type AuthStackParamList = {
  Login: undefined;
  Register: undefined;
  ForgotPassword: undefined;
  BiometricAuth: { onSuccessNavigate?: string };
  Main: NavigatorScreenParams<MainTabParamList> | undefined;
  CanvasViewer: CanvasViewerParams;
};

/**
 * Main Tab Navigation Types
 */
export type MainTabParamList = {
  WorkflowsTab: NavigatorScreenParams<WorkflowStackParamList> | undefined;
  AnalyticsTab: NavigatorScreenParams<AnalyticsStackParamList> | undefined;
  AgentsTab: NavigatorScreenParams<AgentStackParamList> | undefined;
  ChatTab: NavigatorScreenParams<ChatStackParamList> | undefined;
  SettingsTab: undefined;
};

/**
 * Workflow Stack Navigation Types
 */
export type WorkflowStackParamList = {
  Approvals: undefined;
  WorkflowsList: undefined;
  WorkflowDetail: { workflowId: string };
  WorkflowTrigger: { workflowId: string; workflowName: string };
  ExecutionProgress: { executionId: string };
  WorkflowLogs: { executionId: string };
};

/**
 * Analytics Stack Navigation Types
 */
export type AnalyticsStackParamList = {
  AnalyticsDashboard: undefined;
};

/**
 * Agent Stack Navigation Types
 */
export type AgentStackParamList = {
  AgentList: undefined;
  AgentChat: { agentId: string; agentName?: string };
};

/**
 * Chat Stack Navigation Types
 */
export type ChatStackParamList = {
  ChatTab: undefined;
  ConversationList: undefined;
  NewConversation: undefined;
  AgentChat: { agentId: string; conversationId?: string };
};

/**
 * Settings Stack Navigation Types
 */
export type SettingsStackParamList = {
  Settings: undefined;
  Profile: undefined;
  Preferences: undefined;
  Notifications: undefined;
  Security: undefined;
  About: undefined;
};

/**
 * Deep Link Types
 */
export type DeepLinkParams = {
  screen: string;
  params?: Record<string, string | number | boolean>;
};

/**
 * Root Linking Configuration Type
 *
 * The root navigator is the authentication stack, so its linking config is
 * typed against AuthStackParamList. Nested navigators are represented with
 * NavigatorScreenParams in the param lists above.
 */
export type AuthLinkingOptions = LinkingOptions<AuthStackParamList>;

/**
 * Navigation State Types
 */
export type NavigationState = {
  key: string;
  index: number;
  routeNames: string[];
  routes: Array<{
    key: string;
    name: string;
    params?: any;
  }>;
  history?: unknown;
  stale: boolean;
  type: string;
};

/**
 * Auth Screen Navigation Props
 */
export type AuthScreenNavigationProp = import('@react-navigation/native').NavigationProp<AuthStackParamList>;

/**
 * Main Tab Navigation Props
 */
export type MainTabNavigationProp = import('@react-navigation/native').NavigationProp<MainTabParamList>;

/**
 * Workflow Stack Navigation Props
 */
export type WorkflowStackNavigationProp = import('@react-navigation/native').NavigationProp<WorkflowStackParamList>;

/**
 * Agent Stack Navigation Props
 */
export type AgentStackNavigationProp = import('@react-navigation/native').NavigationProp<AgentStackParamList>;
