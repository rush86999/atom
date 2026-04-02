/**
 * Canvas Marketplace Components
 *
 * Showcase components demonstrating canvas-skill integration.
 * These components are designed to work seamlessly with agent skills.
 */

export { ApiDataTable } from './ApiDataTable';
export { SmartChart } from './SmartChart';
export { FormToApi } from './FormToApi';
export { AgentChatWidget } from './AgentChatWidget';
export { AutoSyncDashboard } from './AutoSyncDashboard';

// Component types for TypeScript
export type {
  ApiDataTableProps,
  ColumnConfig
} from './ApiDataTable';

export type {
  SmartChartProps
} from './SmartChart';

export type {
  FormToApiProps,
  FormField,
  SubmissionHistory
} from './FormToApi';

export type {
  AgentChatWidgetProps,
  Message
} from './AgentChatWidget';

export type {
  AutoSyncDashboardProps,
  SyncConfig,
  SyncStatus,
  DataConflict
} from './AutoSyncDashboard';
