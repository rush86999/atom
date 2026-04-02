/**
 * Canvas Components
 *
 * Specialized editors for different content types:
 * - EmailCanvas: Rich email composer with AI rewrite and tone assist
 * - DocumentCanvas: Document editor with formatting, version history, and AI
 * - SpreadsheetCanvas: Spreadsheet with formulas, cell formatting, and AI analyze
 * - IntegrationCanvas: Visual integration management with agent orchestration
 *
 * Visualization Components (ported from upstream):
 * - BarChartCanvas, LineChartCanvas, PieChartCanvas: Chart visualizations
 * - InteractiveForm: Multi-tenant form component with governance
 * - CanvasHost: Real-time canvas host with WebSocket support
 */

// Specialized Canvas Editors
export { EmailCanvas } from './EmailCanvas';
export { DocumentCanvas } from './DocumentCanvas';
export { SpreadsheetCanvas } from './SpreadsheetCanvas';
export { IntegrationCanvas } from './IntegrationCanvas';
export { BrowserCanvas } from './BrowserCanvas';
export { TerminalCanvas } from './TerminalCanvas';
export { CodingWorkspace } from './CodingWorkspace';
export { GuidancePanel } from './GuidancePanel';
export { PlaybackViewer } from './PlaybackViewer';
export { RecordingsList } from './RecordingsList';
export { AgentOperationTracker } from './AgentOperationTracker';
export { AgentRequestPrompt } from './AgentRequestPrompt';
export { InternProposalReview } from './InternProposalReview';
export { SupervisedAgentMonitor } from './SupervisedAgentMonitor';

// Visualization Components (multi-tenant with governance)
export { BarChartCanvas } from './BarChart';
export { LineChartCanvas } from './LineChart';
export { PieChartCanvas } from './PieChart';
export { InteractiveForm } from './InteractiveForm';
export { CanvasHost } from './CanvasHost';

// Types
export type {
  BarChartProps,
  LineChartProps,
  PieChartProps,
  InteractiveFormProps,
  FormField,
  CanvasHostProps,
  CanvasState,
  AgentOperationData,
  RequestData,
  RequestOption,
  OperationLog,
  OperationContext
} from './types';

