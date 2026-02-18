/**
 * Canvas Type Definitions
 *
 * TypeScript definitions for specialized canvas types.
 */

// Base Canvas Types
export type CanvasType = 'generic' | 'docs' | 'email' | 'sheets' | 'orchestration' | 'terminal' | 'coding';

export interface BaseCanvasData {
  canvas_id: string;
  canvas_type: CanvasType;
  title?: string;
  layout?: string;
  created_at: string;
}

// Documentation Canvas Types
export interface DocsCanvasData extends BaseCanvasData {
  canvas_type: 'docs';
  title: string;
  content: string;
  layout: 'document' | 'split_view' | 'focus';
  enable_comments: boolean;
  enable_versioning: boolean;
  versions: DocumentVersion[];
  comments: DocumentComment[];
}

export interface DocumentVersion {
  version_id: string;
  content: string;
  author: string;
  created_at: string;
  changes: string;
}

export interface DocumentComment {
  comment_id: string;
  content: string;
  author: string;
  selection?: {
    start: number;
    end: number;
    text: string;
  };
  resolved: boolean;
  resolved_by?: string;
  resolved_at?: string;
  created_at: string;
}

export interface TableOfContentsEntry {
  level: number;
  title: string;
  anchor: string;
  position: number;
}

// Email Canvas Types
export interface EmailCanvasData extends BaseCanvasData {
  canvas_type: 'email';
  subject: string;
  layout: 'inbox' | 'conversation' | 'compose';
  thread_id: string;
  draft: EmailDraft;
  messages: EmailMessage[];
  attachments: EmailAttachment[];
  categories: EmailCategory[];
}

export interface EmailMessage {
  message_id: string;
  from_email: string;
  to_emails: string[];
  cc_emails: string[];
  subject: string;
  body: string;
  timestamp: string;
  thread_id: string;
  attachments: EmailAttachment[];
  read: boolean;
}

export interface EmailDraft {
  draft_id: string;
  to_emails: string[];
  cc_emails: string[];
  subject: string;
  body: string;
  attachments: EmailAttachment[];
}

export interface EmailAttachment {
  attachment_id: string;
  filename: string;
  file_type: string;
  size: number;
  url?: string;
}

export interface EmailCategory {
  name: string;
  color?: string;
  categorized_by: string;
  categorized_at: string;
}

// Spreadsheet Canvas Types
export interface SheetsCanvasData extends BaseCanvasData {
  canvas_type: 'sheets';
  title: string;
  layout: 'sheet' | 'dashboard' | 'split_pane';
  cells: Record<string, SpreadsheetCell>;
  formulas: string[];
  charts: SpreadsheetChart[];
  pivot_tables: PivotTable[];
}

export interface SpreadsheetCell {
  cell_ref: string;  // A1, B2, etc.
  value: any;
  cell_type: 'text' | 'number' | 'date' | 'formula';
  formula?: string;
  formatting?: {
    bold?: boolean;
    italic?: boolean;
    color?: string;
    background?: string;
  };
}

export interface SpreadsheetChart {
  chart_id: string;
  chart_type: 'line' | 'bar' | 'pie' | 'scatter';
  data_range: string;  // A1:B10
  title: string;
  position?: {
    row: number;
    col: number;
  };
}

export interface PivotTable {
  pivot_id: string;
  name: string;
  source_range: string;
  rows: string[];
  columns: string[];
  values: string[];
}

// Orchestration Canvas Types
export interface OrchestrationCanvasData extends BaseCanvasData {
  canvas_type: 'orchestration';
  title: string;
  layout: 'board' | 'timeline' | 'calendar';
  tasks: WorkflowTask[];
  nodes: IntegrationNode[];
  connections: WorkflowConnection[];
  milestones: Milestone[];
  integrations: string[];
}

export interface WorkflowTask {
  task_id: string;
  title: string;
  status: 'todo' | 'in_progress' | 'done';
  assignee?: string;
  due_date?: string;
  tags: string[];
  integrations: string[];  // App integrations involved
}

export interface IntegrationNode {
  node_id: string;
  app_name: string;  // e.g., "slack", "gmail", "notion"
  node_type: 'trigger' | 'action' | 'condition';
  config: Record<string, any>;
  position: {
    x: number;
    y: number;
  };
}

export interface WorkflowConnection {
  connection_id: string;
  from_node: string;
  to_node: string;
  condition?: string;
}

export interface Milestone {
  milestone_id: string;
  title: string;
  date: string;
  status: 'pending' | 'completed';
}

// Terminal Canvas Types
export interface TerminalCanvasData extends BaseCanvasData {
  canvas_type: 'terminal';
  layout: 'terminal' | 'split_shell' | 'monitor';
  working_dir: string;
  command: string;
  outputs: TerminalOutput[];
  file_tree: FileTreeNode;
  processes: ProcessInfo[];
  logs: LogEntry[];
}

export interface TerminalOutput {
  output_id: string;
  command: string;
  output: string;
  exit_code: number;
  timestamp: string;
}

export interface FileTreeNode {
  node_id: string;
  name: string;
  node_type: 'file' | 'directory';
  path: string;
  children?: FileTreeNode[];
  size?: number;
}

export interface ProcessInfo {
  pid: number;
  name: string;
  cpu_percent: number;
  memory_mb: number;
  user: string;
}

export interface LogEntry {
  log_id: string;
  level: 'INFO' | 'WARN' | 'ERROR' | 'DEBUG';
  message: string;
  timestamp: string;
  source?: string;
}

// Coding Canvas Types
export interface CodingCanvasData extends BaseCanvasData {
  canvas_type: 'coding';
  repo: string;
  branch: string;
  layout: 'editor' | 'split_diff' | 'repo_view';
  files: CodeFile[];
  diffs: DiffView[];
  pull_requests: PullRequestReview[];
  comments: CodeComment[];
}

export interface CodeFile {
  file_id: string;
  path: string;
  content: string;
  language: string;
  status: 'added' | 'modified' | 'deleted';
}

export interface DiffView {
  diff_id: string;
  file_path: string;
  old_content: string;
  new_content: string;
  hunks: DiffHunk[];
  created_at: string;
}

export interface DiffHunk {
  hunk_id: string;
  old_start: number;
  old_lines: string[];
  new_start: number;
  new_lines: string[];
}

export interface PullRequestReview {
  review_id: string;
  pr_number: number;
  title: string;
  description: string;
  status: 'open' | 'merged' | 'closed';
  author: string;
  created_at: string;
}

export interface CodeComment {
  comment_id: string;
  file_path: string;
  line_number: number;
  content: string;
  author: string;
  created_at: string;
  resolved: boolean;
}

// WebSocket Message Types
export interface CanvasUpdateMessage {
  type: 'canvas:update';
  data: {
    action: 'present' | 'update' | 'close';
    canvas_type?: CanvasType;
    component: string;
    canvas_id: string;
    session_id?: string;
    title?: string;
    layout?: string;
    data: any;
  };
}

// Canvas Type Metadata
export interface CanvasTypeMetadata {
  type: CanvasType;
  display_name: string;
  description: string;
  components: string[];
  layouts: string[];
  min_maturity: 'student' | 'intern' | 'supervised' | 'autonomous';
  permissions: Record<string, string[]>;
  examples: string[];
}

// Helper type for canvas data union
export type CanvasData =
  | DocsCanvasData
  | EmailCanvasData
  | SheetsCanvasData
  | OrchestrationCanvasData
  | TerminalCanvasData
  | CodingCanvasData;

// Generic canvas data (for backward compatibility)
export interface GenericCanvasData extends BaseCanvasData {
  canvas_type: 'generic';
  component: 'line_chart' | 'bar_chart' | 'pie_chart' | 'markdown' | 'form' | 'status_panel';
  data: any;
}

// ============================================================================
// Canvas State API Types
// ============================================================================

/**
 * Base canvas state interface for AI agent accessibility
 * All canvas types should extend this base interface
 */
export interface BaseCanvasState {
  canvas_type: CanvasType;
  canvas_id: string;
  timestamp: string;
  title?: string;
}

/**
 * Terminal canvas state
 */
export interface TerminalCanvasState extends BaseCanvasState {
  canvas_type: 'terminal';
  working_dir: string;
  command: string;
  lines: string[];
  cursor_pos: { row: number; col: number };
  scroll_offset: number;
  exit_code?: number;
}

/**
 * Chart canvas state (applies to LineChart, BarChart, PieChart)
 */
export interface ChartCanvasState extends BaseCanvasState {
  canvas_type: 'generic';  // Charts use 'generic' with specific components
  component: 'line_chart' | 'bar_chart' | 'pie_chart';
  chart_type: 'line' | 'bar' | 'pie';
  data_points: Array<{ x: string | number; y: number; label?: string }>;
  axes_labels?: { x?: string; y?: string };
  title?: string;
  legend?: boolean;
}

/**
 * Form canvas state
 */
export interface FormCanvasState extends BaseCanvasState {
  canvas_type: 'generic';
  component: 'form';
  form_schema: {
    fields: Array<{
      name: string;
      type: string;
      label: string;
      required: boolean;
    }>;
  };
  form_data: Record<string, any>;
  validation_errors: Array<{
    field: string;
    message: string;
  }>;
  submit_enabled: boolean;
  submitted?: boolean;
}

/**
 * Orchestration canvas state
 */
export interface OrchestrationCanvasState extends BaseCanvasState {
  canvas_type: 'orchestration';
  layout: 'board' | 'timeline' | 'calendar';
  tasks: Array<{
    task_id: string;
    title: string;
    status: 'todo' | 'in_progress' | 'done';
    assignee?: string;
  }>;
  nodes: Array<{
    node_id: string;
    app_name: string;
    node_type: 'trigger' | 'action' | 'condition';
  }>;
}

/**
 * Agent operation tracker state
 */
export interface AgentOperationState extends BaseCanvasState {
  canvas_type: 'generic';
  component: 'agent_operation_tracker';
  operation_id: string;
  agent_id: string;
  agent_name: string;
  operation_type: string;
  status: 'running' | 'waiting' | 'completed' | 'failed';
  current_step: string;
  current_step_index: number;
  total_steps?: number;
  progress: number;
  context: {
    what?: string;
    why?: string;
    next?: string;
  };
  logs_count: number;
  started_at: string;
  completed_at?: string;
}

/**
 * View orchestrator state
 */
export interface ViewOrchestratorState extends BaseCanvasState {
  canvas_type: 'generic';
  component: 'view_orchestrator';
  layout: 'split_horizontal' | 'split_vertical' | 'grid' | 'tabs';
  current_view: string;
  active_views: Array<{
    view_id: string;
    view_type: 'canvas' | 'browser' | 'terminal' | 'app';
    title: string;
    status: 'active' | 'background' | 'closed';
    url?: string;
    command?: string;
  }>;
  canvas_guidance?: {
    agent_id: string;
    message: string;
    what_youre_seeing: string;
    controls: Array<{ label: string; action: string }>;
  };
}

/**
 * Union type for all canvas states
 */
export type AnyCanvasState =
  | TerminalCanvasState
  | ChartCanvasState
  | FormCanvasState
  | OrchestrationCanvasState
  | AgentOperationState
  | ViewOrchestratorState;

/**
 * Canvas state API response
 */
export interface CanvasStateResponse {
  canvas_id: string;
  state: AnyCanvasState;
  timestamp: string;
}

/**
 * WebSocket event types for canvas state changes
 */
export interface CanvasStateChangeEvent {
  type: 'canvas:state_change';
  canvas_id: string;
  canvas_type: CanvasType;
  component: string;
  state: AnyCanvasState;
  timestamp: string;
}

/**
 * Canvas state API (global window.atom.canvas)
 */
export interface CanvasStateAPI {
  /**
   * Get current state for a specific canvas
   * @param canvasId - The canvas ID to query
   * @returns Canvas state or null if not found
   */
  getState: (canvasId: string) => AnyCanvasState | null;

  /**
   * Get all active canvas states
   * @returns Array of all canvas states
   */
  getAllStates: () => Array<{ canvas_id: string; state: AnyCanvasState }>;

  /**
   * Subscribe to state changes for a specific canvas
   * @param canvasId - The canvas ID to watch
   * @param callback - Function called when state changes
   * @returns Unsubscribe function
   */
  subscribe: (canvasId: string, callback: (state: AnyCanvasState) => void) => () => void;

  /**
   * Subscribe to all canvas state changes
   * @param callback - Function called when any canvas state changes
   * @returns Unsubscribe function
   */
  subscribeAll: (callback: (event: CanvasStateChangeEvent) => void) => () => void;
}

// Declare global window augmentation
declare global {
  interface Window {
    atom?: {
      canvas?: CanvasStateAPI;
    };
  }
}
