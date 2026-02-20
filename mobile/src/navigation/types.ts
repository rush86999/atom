/**
 * Navigation Types
 *
 * Central type definitions for all navigation structures
 */

/**
 * Auth Stack Navigation Types
 */
export type AuthStackParamList = {
  Login: undefined;
  Register: undefined;
  ForgotPassword: undefined;
  BiometricAuth: { onSuccessNavigate?: string };
  Main: undefined;
};

/**
 * Main Tab Navigation Types
 */
export type MainTabParamList = {
  WorkflowsTab: undefined;
  AnalyticsTab: undefined;
  AgentsTab: undefined;
  ChatTab: undefined;
  SettingsTab: undefined;
};

/**
 * Workflow Stack Navigation Types
 */
export type WorkflowStackParamList = {
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
