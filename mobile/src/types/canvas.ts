/**
 * Canvas Types
 * Type definitions for canvas presentations on mobile
 */

// Canvas types
export enum CanvasType {
  GENERIC = 'generic',
  DOCS = 'docs',
  EMAIL = 'email',
  SHEETS = 'sheets',
  ORCHESTRATION = 'orchestration',
  TERMINAL = 'terminal',
  CODING = 'coding',
}

// Canvas component types
export enum CanvasComponentType {
  MARKDOWN = 'markdown',
  CHART = 'chart',
  FORM = 'form',
  SHEET = 'sheet',
  TABLE = 'table',
  CODE = 'code',
  CUSTOM = 'custom',
}

// Canvas audit record
export interface CanvasAudit {
  id: string;
  canvas_id: string;
  canvas_type: CanvasType;
  action: 'present' | 'submit' | 'close' | 'update' | 'execute';
  agent_id: string;
  agent_name: string;
  user_id: string;
  session_id: string;
  component_count: number;
  metadata: Record<string, any>;
  created_at: string;
}

// Chart data
export interface ChartData {
  type: 'line' | 'bar' | 'pie' | 'area';
  title: string;
  data: any[];
  x_key: string;
  y_keys: string[];
  colors?: string[];
}

// Form field
export interface FormField {
  name: string;
  label: string;
  type: 'text' | 'number' | 'email' | 'password' | 'select' | 'multiselect' | 'checkbox' | 'textarea';
  required: boolean;
  options?: string[];
  default_value?: any;
  placeholder?: string;
  validation?: {
    min?: number;
    max?: number;
    pattern?: string;
  };
}

// Form data
export interface FormData {
  title: string;
  description?: string;
  fields: FormField[];
  submit_button_text?: string;
  cancel_button_text?: string;
}

// Sheet row
export interface SheetRow {
  id: string;
  data: Record<string, any>;
}

// Sheet data
export interface SheetData {
  title: string;
  columns: {
    key: string;
    label: string;
    type: 'text' | 'number' | 'date' | 'boolean';
    width?: number;
  }[];
  rows: SheetRow[];
  editable?: boolean;
  sortable?: boolean;
}

// Canvas presentation request
export interface CanvasPresentationRequest {
  canvas_type: CanvasType;
  title: string;
  components: CanvasComponent[];
  session_id: string;
  agent_id: string;
  metadata?: Record<string, any>;
}

// Canvas component
export interface CanvasComponent {
  id: string;
  type: CanvasComponentType;
  order: number;
  data: any;
  props?: Record<string, any>;
}

// Mobile canvas view config
export interface MobileCanvasViewConfig {
  canvas_id: string;
  canvas_type: CanvasType;
  platform: 'mobile';
  optimized: true;
  scale_to_fit: boolean;
  enable_zoom: boolean;
  enable_interactions: boolean;
}
