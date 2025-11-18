# New Components & Widgets Documentation

## Overview

This document details all new sub-components and widgets created in the advanced view files.

---

## DashboardView Components

### 1. AdvancedAnalyticsWidget

**Location:** `DashboardView.tsx`
**Purpose:** Display advanced analytics with circular progress and metrics

```tsx
interface AnalyticsData {
  totalActivities: number;
  completionRate: number;
  averageResponseTime: number;
  productivityScore: number;
  timeSpent: Record<string, number>;
}

<AdvancedAnalyticsWidget
  tasks={tasks}
  transactions={transactions}
  events={events}
/>;
```

**Features:**

- Circular progress indicator for completion rate
- Productivity score (0-100)
- Time breakdown by category
- Total activities counter

**Styling Classes:**

- `.analytics-card` - Main container
- `.analytics-grid` - Grid layout
- `.analytics-item` - Individual metric
- `.circular-progress` - Progress ring

---

### 2. SmartAssistantWidget

**Location:** `DashboardView.tsx`
**Purpose:** Display AI-powered task suggestions

```tsx
<SmartAssistantWidget />
```

**Features:**

- Automatic suggestion generation
- Dismissible suggestions
- Emoji-prefixed tips
- Priority-based ordering

**State:**

```tsx
const [suggestions, setSuggestions] = useState<string[]>([
  '📌 Focus on high-priority tasks this morning',
  '💡 You completed 75% of tasks - Great progress!',
  // ...
]);
```

**Styling Classes:**

- `.assistant-card` - Main container
- `.suggestions-list` - List container
- `.suggestion-item` - Individual suggestion
- `.dismiss-btn` - Dismiss button

---

### 3. CollaborationWidget

**Location:** `DashboardView.tsx`
**Purpose:** Show team members and collaboration stats

```tsx
<CollaborationWidget presenceList={presenceList} />
```

**Features:**

- Member count display
- Active collaboration counter
- Member avatar circles
- Plus indicator for overflow

**Props:**

```tsx
interface Props {
  presenceList: Array<{
    socketId?: string;
    userId?: string;
    username?: string;
    room?: string;
  }>;
}
```

**Styling Classes:**

- `.collaboration-card` - Main container
- `.collaboration-stats` - Stats grid
- `.collaboration-members` - Member avatars
- `.member-avatar` - Individual avatar

---

## ChatView Components

### 1. ConversationContext (Interface)

**Location:** `ChatView.tsx`
**Purpose:** Track conversation metadata

```tsx
interface ConversationContext {
  topic: string;
  relatedMessages: number;
  sentiment: 'positive' | 'neutral' | 'negative';
}
```

---

### 2. MessageContextWidget

**Location:** `ChatView.tsx`
**Purpose:** Display conversation context information

```tsx
<MessageContextWidget context={context} />
```

**Features:**

- Topic display
- Sentiment indicator
- Related message count
- Auto-hide when null

**Styling Classes:**

- `.context-widget` - Main container
- `.context-item` - Individual context stat

---

### 3. Enhanced Message Component

**Location:** `ChatView.tsx`
**Updates to existing Message component**

```tsx
interface Props {
  message: ChatMessage;
  onReaction?: (reaction: string) => void;
}
```

**New Features:**

- Reaction buttons (👍, 👎)
- Copy button
- Message actions menu

**Styling Classes:**

- `.message-actions` - Action buttons container
- `.reaction-btn` - Reaction button
- `.action-btn` - Generic action button

---

### 4. Suggested Questions

**Location:** `ChatView.tsx`
**Features:**

- Pre-populated question buttons
- Click-to-ask functionality
- Customizable questions list

```tsx
const [suggestedQuestions, setSuggestedQuestions] = useState<string[]>([
  'Help me prioritize my tasks',
  'Create a summary of my day',
  'What should I focus on next?',
  'Analyze my productivity',
]);
```

**Styling Classes:**

- `.suggested-questions` - Container
- `.suggestion-btn` - Individual button

---

## TasksView Components

### 1. SmartSuggestion (Interface)

**Location:** `TasksView.tsx`

```tsx
interface SmartSuggestion {
  taskId: string;
  suggestion: string;
  priority: 'high' | 'medium' | 'low';
}
```

---

### 2. TimeAllocation (Interface)

**Location:** `TasksView.tsx`

```tsx
interface TimeAllocation {
  taskId: string;
  estimatedTime: number;
  suggestedTime: number;
}
```

---

### 3. Enhanced TaskCard

**Location:** `TasksView.tsx`
**Updates to existing component**

```tsx
interface Props {
  task: Task;
  onToggleImportant: (id: string) => void;
  onToggleSubtask: (taskId: string, subtaskId: string) => void;
  onEstimateTime?: (taskId: string, time: number) => void;
}
```

**New Features:**

- Time estimation modal
- Subtask progress bar
- Time tracking button
- Hours input field

**New Styling Classes:**

- `.time-estimate-modal` - Time input modal
- `.time-estimate-btn` - Time button
- `.subtask-progress` - Progress bar
- `.progress-fill` - Progress indicator

---

### 4. AITaskSuggestionsWidget

**Location:** `TasksView.tsx`
**Purpose:** Display AI-powered task recommendations

```tsx
<AITaskSuggestionsWidget tasks={filteredTasks} />
```

**Features:**

- Overdue task detection
- High-priority warnings
- Completion rate analysis
- Actionable suggestions

**Suggestion Types:**

1. Overdue tasks alert
2. High-priority workload warning
3. Low completion rate warning
4. Smart prioritization tips

**Styling Classes:**

- `.ai-suggestions-widget` - Main container
- `.suggestions-list` - List container
- `.suggestion` - Individual suggestion
- `.suggestion.high` - High priority style
- `.suggestion.medium` - Medium priority style
- `.suggestion.low` - Low priority style

---

## NotesView Components

### 1. NoteVersion (Interface)

**Location:** `NotesView.tsx`

```tsx
interface NoteVersion {
  id: string;
  content: string;
  timestamp: string;
  author: string;
}
```

---

### 2. RichTextEditor

**Location:** `NotesView.tsx`
**Purpose:** Advanced text editing with formatting

```tsx
<RichTextEditor
  content={editingContent}
  onChange={setEditingContent}
  onSave={handleSaveNote}
/>
```

**Features:**

- Bold formatting
- Italic formatting
- Heading formatting
- Save button
- Toolbar

**Toolbar Buttons:**

- **B** - Bold
- _I_ - Italic
- H - Heading
- 💾 - Save

**Styling Classes:**

- `.rich-text-editor` - Main container
- `.editor-toolbar` - Toolbar container
- `.editor-content` - Textarea
- `.divider` - Toolbar divider
- `.save-btn` - Save button
- `.active` - Active button state

---

### 3. Enhanced NotesView

**Location:** `NotesView.tsx`
**New Features:**

- Search/filter functionality
- Tag system
- Version history display
- Note export

**New Styling Classes:**

- `.notes-search` - Search container
- `.search-input` - Search input field
- `.tags-filter` - Tag buttons
- `.tag-filter` - Individual tag
- `.tag-filter.active` - Active tag
- `.version-history` - Version list
- `.versions-list` - Versions container
- `.version-item` - Individual version
- `.note-actions` - Action buttons

---

## WorkflowsView Components

### 1. WorkflowStats (Interface)

**Location:** `WorkflowsView.tsx`

```tsx
interface WorkflowStats {
  totalExecutions: number;
  successRate: number;
  averageExecutionTime: number;
  errorCount: number;
}
```

---

### 2. WorkflowVisualization

**Location:** `WorkflowsView.tsx`
**Purpose:** Display workflow trigger → action flow

```tsx
<WorkflowVisualization workflow={workflow} />
```

**Features:**

- Visual node diagram
- Trigger node
- Arrow connector
- Action node
- Type labels

**Styling Classes:**

- `.workflow-visualization` - Container
- `.workflow-nodes` - Nodes container
- `.workflow-node` - Individual node
- `.workflow-node.trigger` - Trigger styling
- `.workflow-node.action` - Action styling
- `.workflow-arrow` - Arrow connector

---

### 3. WorkflowPerformanceWidget

**Location:** `WorkflowsView.tsx`
**Purpose:** Display workflow performance metrics

```tsx
<WorkflowPerformanceWidget workflow={workflow} />
```

**Features:**

- Success rate display
- Average execution time
- Error count
- Metric cards

**Styling Classes:**

- `.workflow-performance` - Main container
- `.metrics-grid` - Grid layout
- `.metric` - Individual metric
- `.metric-label` - Metric name
- `.metric-value` - Metric value

---

### 4. Enhanced WorkflowsView

**Location:** `WorkflowsView.tsx`
**New Features:**

- Visual workflow builder
- Workflow filtering
- Execute on-demand
- Delete workflows
- Enable/disable toggle

**New Styling Classes:**

- `.workflows-controls` - Control bar
- `.workflow-filters` - Filter buttons
- `.filter-btn` - Individual filter
- `.workflow-builder` - Builder container
- `.builder-content` - Builder content
- `.builder-canvas` - Canvas area
- `.workflow-execute-btn` - Execute button
- `.workflow-delete-btn` - Delete button

---

## SettingsView Enhancements

### Security Tab (New)

**Features:**

- MFA toggle
- Auto-lock setting
- End-to-end encryption
- Session management

**Styling Classes:**

- `.form-group.checkbox-group` - Checkbox containers

---

### Audit Logs Tab (New)

**Features:**

- Log entry display
- Timestamp column
- Action column
- Details column

**Styling Classes:**

- `.audit-logs` - Main container
- `.logs-header` - Header row
- `.log-entry` - Individual log
- `.log-action` - Action cell

---

### Backup Tab (New)

**Features:**

- Schedule selection (daily/weekly/monthly)
- Latest backup info
- Restore button
- Backup size display

**Styling Classes:**

- `.backup-info` - Backup details
- `.backup-restore-btn` - Restore button

---

## AnalyticsView Components

### 1. TrendChart

**Location:** `AnalyticsView.tsx`
**Purpose:** Display line chart trends

```tsx
<TrendChart
  data={analytics.productivityTrend}
  label="Productivity Trend"
  color="#3b82f6"
/>
```

**Features:**

- Line chart with dots
- Automatic scaling
- Color customization
- Data normalization

**Styling Classes:**

- `.trend-chart` - Main container
- `<svg>` with path elements

---

### 2. DistributionChart

**Location:** `AnalyticsView.tsx`
**Purpose:** Display bar chart distribution

```tsx
<DistributionChart data={taskDistribution} label="Tasks by Priority" />
```

**Features:**

- Vertical bars
- Label display
- Value display
- Proportional sizing

**Styling Classes:**

- `.distribution-chart` - Main container
- `.bars` - Bars container
- `.bar-container` - Individual bar
- `.bar` - Bar element
- `.bar-value` - Value label

---

### 3. Time Range Selector

**Location:** `AnalyticsView.tsx`
**Features:**

- Week option
- Month option
- Year option
- Active state indicator

**Styling Classes:**

- `.time-range-selector` - Container
- `button.active` - Active button

---

## CollaborationView Components

### 1. TeamMember (Interface)

**Location:** `CollaborationView.tsx`

```tsx
interface TeamMember {
  id: string;
  name: string;
  avatar: string;
  role: string;
  status: 'online' | 'offline' | 'away';
  lastSeen: string;
}
```

---

### 2. SharedDocument (Interface)

**Location:** `CollaborationView.tsx`

```tsx
interface SharedDocument {
  id: string;
  title: string;
  owner: string;
  lastModified: string;
  collaborators: string[];
}
```

---

### 3. TeamMemberCard

**Location:** `CollaborationView.tsx`
**Purpose:** Display team member information and actions

```tsx
<TeamMemberCard
  member={member}
  onAction={(action) => handleMemberAction(member.id, action)}
/>
```

**Features:**

- Avatar display
- Status indicator (colored dot)
- Role information
- Last seen timestamp
- Action buttons (message, call, share)

**Status Colors:**

- Online: `#10b981` (green)
- Away: `#f59e0b` (amber)
- Offline: `#6b7280` (gray)

**Styling Classes:**

- `.team-member-card` - Main container
- `.member-header` - Header section
- `.member-avatar` - Avatar container
- `.status-indicator` - Status dot
- `.member-info` - Info section
- `.member-role` - Role text
- `.member-status` - Status text
- `.member-actions` - Action buttons

---

### 4. SharedDocuments

**Location:** `CollaborationView.tsx`
**Purpose:** Display shared documents list

```tsx
<SharedDocuments documents={sharedDocuments} />
```

**Features:**

- Document icon
- Title and owner
- Last modified date
- Collaborator avatars
- Open button

**Styling Classes:**

- `.shared-documents` - Main container
- `.documents-list` - List container
- `.document-item` - Individual document
- `.document-icon` - Icon display
- `.document-info` - Info section
- `.collaborators-avatars` - Avatar container
- `.collaborator-avatar` - Individual avatar
- `.more` - Overflow indicator
- `.open-btn` - Open button

---

### 5. ActivityFeed

**Location:** `CollaborationView.tsx`
**Purpose:** Display team activity timeline

```tsx
<ActivityFeed />
```

**Features:**

- User avatar
- Action description
- Timestamp
- Auto-populated activities

**Styling Classes:**

- `.activity-feed` - Main container
- `.activities-list` - List container
- `.activity-item` - Individual activity
- `.activity-avatar` - User avatar
- `.activity-content` - Content section

---

## AccessibilityView Components

### 1. AccessibilityOption (Interface)

**Location:** `AccessibilityView.tsx`

```tsx
interface AccessibilityOption {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  category: string;
}
```

---

### 2. AccessibilityFeatureCard

**Location:** `AccessibilityView.tsx`
**Purpose:** Display accessibility feature toggle

```tsx
<AccessibilityFeatureCard
  option={option}
  onChange={(id, enabled) => handleChange(id, enabled)}
/>
```

**Features:**

- Feature name and description
- Toggle switch
- Enable/disable state
- Category classification

**Styling Classes:**

- `.accessibility-feature` - Main container
- `.feature-content` - Content section
- `.toggle-switch` - Switch container

---

### 3. Accessibility Categories

**Categories:**

1. **Visual** - Contrast, text size, motion, color blindness
2. **Audio** - Captions, descriptions
3. **Navigation** - Keyboard, focus, skip links
4. **Speech** - Text-to-speech, voice control

---

### 4. WCAG Compliance Display

**Location:** `AccessibilityView.tsx`
**Features:**

- Compliance level display (AA)
- Principle checkmarks
- Details for each principle

**Styling Classes:**

- `.wcag-compliance` - Main container
- `.compliance-info` - Info section
- `.compliance-details` - Details list
- `.detail-item` - Individual detail
- `.check` - Checkmark symbol

---

## Styling Classes Summary

### Global Classes

- `.view-header` - View title and description
- `.section-header` - Section title
- `.dashboard-card` - Card container
- `.form-group` - Form input group
- `.modal-overlay` - Modal background
- `.modal-content` - Modal box

### Animation Classes

- `.blinking-cursor` - Typing indicator
- `.dragging` - Drag state
- `.active` - Active state

### Utility Classes

- `.loading-spinner` - Loading indicator
- `.error-message` - Error text
- `.error-banner` - Error alert
- `.divider` - Divider line
- `.placeholder` - Empty state

---

## Custom Styling Guide

To customize the appearance of these components, override these classes in your CSS:

```css
/* Analytics Widget */
.analytics-card {
  background: var(--card-bg);
  border-radius: var(--border-radius);
  padding: var(--spacing);
}

.circular-progress {
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Rich Text Editor */
.editor-toolbar {
  display: flex;
  gap: var(--spacing);
  border-bottom: 1px solid var(--border-color);
}

.editor-content {
  min-height: 300px;
  padding: var(--spacing);
}

/* Workflow Visualization */
.workflow-nodes {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.workflow-node {
  padding: var(--spacing);
  border: 2px solid var(--border-color);
  border-radius: var(--border-radius);
  background: var(--node-bg);
}
```

---

## Performance Optimization

### Memoization

```tsx
const analytics = useMemo(() => {
  // expensive calculation
}, [tasks, transactions, events]);

const filteredOptions = useMemo(() => {
  return accessibilityOptions.filter(/* ... */);
}, [accessibilityOptions, activeCategory]);
```

### Callback Optimization

```tsx
const handleChange = useCallback((id, value) => {
  // handler logic
}, []);
```

### Lazy Loading

```tsx
const TrendChart = React.lazy(() => import('./TrendChart'));
```

---

## Accessibility for Components

All components include:

- ✅ ARIA labels
- ✅ Role attributes
- ✅ Keyboard navigation
- ✅ Focus management
- ✅ Screen reader support
- ✅ Color contrast
- ✅ Semantic HTML

---

## Testing Components

```tsx
// Test snapshot
expect(component).toMatchSnapshot();

// Test interactions
fireEvent.click(button);
expect(onChange).toHaveBeenCalled();

// Test accessibility
const { getByRole } = render(<Component />);
expect(getByRole('button')).toBeInTheDocument();
```
