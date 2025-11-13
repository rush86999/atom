import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import {
  UserProfile,
  Agent,
  Task,
  CalendarEvent,
  CommunicationsMessage,
  Integration,
  Workflow,
  Transaction,
  Note,
  VoiceCommand,
  DevProject,
  WidgetConfig,
  AgentLog,
  IntegrationConfig,
  View,
  CollaborationSession,
  TaskSuggestion,
  AnalyticsMetric,
  VoiceTranscription,
  SearchResult,
  NotificationPreference,
  PerformanceMetric
} from '../types';

interface AppState {
  // Current view state
  currentView: View;
  setCurrentView: (view: View) => void;

  // User profile
  userProfile: UserProfile | null;
  setUserProfile: (profile: UserProfile) => void;

  // Agents
  agents: Agent[];
  setAgents: (agents: Agent[]) => void;
  updateAgent: (id: string, updates: Partial<Agent>) => void;

  // Tasks
  tasks: Task[];
  setTasks: (tasks: Task[]) => void;
  addTask: (task: Task) => void;
  updateTask: (id: string, updates: Partial<Task>) => void;
  deleteTask: (id: string) => void;

  // Calendar events
  calendarEvents: CalendarEvent[];
  setCalendarEvents: (events: CalendarEvent[]) => void;
  addCalendarEvent: (event: CalendarEvent) => void;
  updateCalendarEvent: (id: string, updates: Partial<CalendarEvent>) => void;
  deleteCalendarEvent: (id: string) => void;

  // Communications
  messages: CommunicationsMessage[];
  setMessages: (messages: CommunicationsMessage[]) => void;
  markMessageAsRead: (id: string) => void;
  deleteMessage: (id: string) => void;

  // Integrations
  integrations: Integration[];
  setIntegrations: (integrations: Integration[]) => void;
  updateIntegration: (id: string, updates: Partial<Integration>) => void;

  // Workflows
  workflows: Workflow[];
  setWorkflows: (workflows: Workflow[]) => void;
  addWorkflow: (workflow: Workflow) => void;
  updateWorkflow: (id: string, updates: Partial<Workflow>) => void;
  deleteWorkflow: (id: string) => void;

  // Transactions
  transactions: Transaction[];
  setTransactions: (transactions: Transaction[]) => void;
  addTransaction: (transaction: Transaction) => void;

  // Notes
  notes: Note[];
  setNotes: (notes: Note[]) => void;
  addNote: (note: Note) => void;
  updateNote: (id: string, updates: Partial<Note>) => void;
  deleteNote: (id: string) => void;

  // Voice commands
  voiceCommands: VoiceCommand[];
  setVoiceCommands: (commands: VoiceCommand[]) => void;
  updateVoiceCommand: (id: string, updates: Partial<VoiceCommand>) => void;

  // Dev projects
  devProjects: DevProject[];
  setDevProjects: (projects: DevProject[]) => void;
  updateDevProject: (id: string, updates: Partial<DevProject>) => void;

  // Dashboard widgets
  widgets: WidgetConfig[];
  setWidgets: (widgets: WidgetConfig[]) => void;
  updateWidget: (id: string, updates: Partial<WidgetConfig>) => void;
  reorderWidgets: (widgets: WidgetConfig[]) => void;

  // Agent logs
  agentLogs: AgentLog[];
  setAgentLogs: (logs: AgentLog[]) => void;
  addAgentLog: (log: AgentLog) => void;

  // Integration configs
  integrationConfigs: IntegrationConfig[];
  setIntegrationConfigs: (configs: IntegrationConfig[]) => void;
  updateIntegrationConfig: (id: string, updates: Partial<IntegrationConfig>) => void;

  // Collaboration sessions
  collaborationSessions: CollaborationSession[];
  setCollaborationSessions: (sessions: CollaborationSession[]) => void;
  addCollaborationSession: (session: CollaborationSession) => void;
  updateCollaborationSession: (id: string, updates: Partial<CollaborationSession>) => void;

  // Task suggestions
  taskSuggestions: TaskSuggestion[];
  setTaskSuggestions: (suggestions: TaskSuggestion[]) => void;
  addTaskSuggestion: (suggestion: TaskSuggestion) => void;

  // Analytics metrics
  analyticsMetrics: AnalyticsMetric[];
  setAnalyticsMetrics: (metrics: AnalyticsMetric[]) => void;
  addAnalyticsMetric: (metric: AnalyticsMetric) => void;

  // Voice transcriptions
  voiceTranscriptions: VoiceTranscription[];
  setVoiceTranscriptions: (transcriptions: VoiceTranscription[]) => void;
  addVoiceTranscription: (transcription: VoiceTranscription) => void;

  // Search results
  searchResults: SearchResult[];
  setSearchResults: (results: SearchResult[]) => void;

  // Notification preferences
  notificationPreferences: NotificationPreference[];
  setNotificationPreferences: (preferences: NotificationPreference[]) => void;
  updateNotificationPreference: (id: string, updates: Partial<NotificationPreference>) => void;

  // Performance metrics
  performanceMetrics: PerformanceMetric[];
  setPerformanceMetrics: (metrics: PerformanceMetric[]) => void;
  addPerformanceMetric: (metric: PerformanceMetric) => void;

  // UI state
  isLoading: { [key: string]: boolean };
  setLoading: (key: string, loading: boolean) => void;

  errors: { [key: string]: string | undefined };
  setError: (key: string, error: string | null) => void;

  // Modal states
  modals: { [key: string]: boolean };
  openModal: (key: string) => void;
  closeModal: (key: string) => void;

  // Search and filters
  searchQuery: string;
  setSearchQuery: (query: string) => void;

  filters: { [key: string]: any };
  setFilter: (key: string, value: any) => void;
  clearFilters: () => void;

  // Real-time connection
  isConnected: boolean;
  setConnected: (connected: boolean) => void;

  // Theme
  theme: 'light' | 'dark' | 'system';
  setTheme: (theme: 'light' | 'dark' | 'system') => void;

  // Notifications
  notifications: Notification[];
  addNotification: (notification: Omit<Notification, 'id' | 'timestamp' | 'read'>) => void;
  removeNotification: (id: string) => void;
  clearNotifications: () => void;
}

interface Notification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
}

export const useAppStore = create<AppState>()(
  devtools(
    persist(
      (set, get) => ({
        // Current view
        currentView: 'dashboard',
        setCurrentView: (view) => set({ currentView: view }),

        // User profile
        userProfile: null,
        setUserProfile: (profile) => set({ userProfile: profile }),

        // Agents
        agents: [],
        setAgents: (agents) => set({ agents }),
        updateAgent: (id, updates) => set((state) => ({
          agents: state.agents.map(agent =>
            agent.id === id ? { ...agent, ...updates } : agent
          )
        })),

        // Tasks
        tasks: [],
        setTasks: (tasks) => set({ tasks }),
        addTask: (task) => set((state) => ({ tasks: [...state.tasks, task] })),
        updateTask: (id, updates) => set((state) => ({
          tasks: state.tasks.map(task =>
            task.id === id ? { ...task, ...updates } : task
          )
        })),
        deleteTask: (id) => set((state) => ({
          tasks: state.tasks.filter(task => task.id !== id)
        })),

        // Calendar events
        calendarEvents: [],
        setCalendarEvents: (events) => set({ calendarEvents: events }),
        addCalendarEvent: (event) => set((state) => ({
          calendarEvents: [...state.calendarEvents, event]
        })),
        updateCalendarEvent: (id, updates) => set((state) => ({
          calendarEvents: state.calendarEvents.map(event =>
            event.id === id ? { ...event, ...updates } : event
          )
        })),
        deleteCalendarEvent: (id) => set((state) => ({
          calendarEvents: state.calendarEvents.filter(event => event.id !== id)
        })),

        // Communications
        messages: [],
        setMessages: (messages) => set({ messages }),
        markMessageAsRead: (id) => set((state) => ({
          messages: state.messages.map(msg =>
            msg.id === id ? { ...msg, unread: false, read: true } : msg
          )
        })),
        deleteMessage: (id) => set((state) => ({
          messages: state.messages.filter(msg => msg.id !== id)
        })),

        // Integrations
        integrations: [],
        setIntegrations: (integrations) => set({ integrations }),
        updateIntegration: (id, updates) => set((state) => ({
          integrations: state.integrations.map(integration =>
            integration.id === id ? { ...integration, ...updates } : integration
          )
        })),

        // Workflows
        workflows: [],
        setWorkflows: (workflows) => set({ workflows }),
        addWorkflow: (workflow) => set((state) => ({ workflows: [...state.workflows, workflow] })),
        updateWorkflow: (id, updates) => set((state) => ({
          workflows: state.workflows.map(workflow =>
            workflow.id === id ? { ...workflow, ...updates } : workflow
          )
        })),
        deleteWorkflow: (id) => set((state) => ({
          workflows: state.workflows.filter(workflow => workflow.id !== id)
        })),

        // Transactions
        transactions: [],
        setTransactions: (transactions) => set({ transactions }),
        addTransaction: (transaction) => set((state) => ({
          transactions: [...state.transactions, transaction]
        })),

        // Notes
        notes: [],
        setNotes: (notes) => set({ notes }),
        addNote: (note) => set((state) => ({ notes: [...state.notes, note] })),
        updateNote: (id, updates) => set((state) => ({
          notes: state.notes.map(note =>
            note.id === id ? { ...note, ...updates } : note
          )
        })),
        deleteNote: (id) => set((state) => ({
          notes: state.notes.filter(note => note.id !== id)
        })),

        // Voice commands
        voiceCommands: [],
        setVoiceCommands: (commands) => set({ voiceCommands: commands }),
        updateVoiceCommand: (id, updates) => set((state) => ({
          voiceCommands: state.voiceCommands.map(cmd =>
            cmd.id === id ? { ...cmd, ...updates } : cmd
          )
        })),

        // Dev projects
        devProjects: [],
        setDevProjects: (projects) => set({ devProjects: projects }),
        updateDevProject: (id, updates) => set((state) => ({
          devProjects: state.devProjects.map(project =>
            project.id === id ? { ...project, ...updates } : project
          )
        })),

        // Dashboard widgets
        widgets: [],
        setWidgets: (widgets) => set({ widgets }),
        updateWidget: (id, updates) => set((state) => ({
          widgets: state.widgets.map(widget =>
            widget.id === id ? { ...widget, ...updates } : widget
          )
        })),
        reorderWidgets: (widgets) => set({ widgets }),

        // Agent logs
        agentLogs: [],
        setAgentLogs: (logs) => set({ agentLogs: logs }),
        addAgentLog: (log) => set((state) => ({ agentLogs: [...state.agentLogs, log] })),

        // Integration configs
        integrationConfigs: [],
        setIntegrationConfigs: (configs) => set({ integrationConfigs: configs }),
        updateIntegrationConfig: (id, updates) => set((state) => ({
          integrationConfigs: state.integrationConfigs.map(config =>
            config.id === id ? { ...config, ...updates } : config
          )
        })),

        // Collaboration sessions
        collaborationSessions: [],
        setCollaborationSessions: (sessions) => set({ collaborationSessions: sessions }),
        addCollaborationSession: (session) => set((state) => ({
          collaborationSessions: [...state.collaborationSessions, session]
        })),
        updateCollaborationSession: (id, updates) => set((state) => ({
          collaborationSessions: state.collaborationSessions.map(session =>
            session.id === id ? { ...session, ...updates } : session
          )
        })),

        // Task suggestions
        taskSuggestions: [],
        setTaskSuggestions: (suggestions) => set({ taskSuggestions: suggestions }),
        addTaskSuggestion: (suggestion) => set((state) => ({
          taskSuggestions: [...state.taskSuggestions, suggestion]
        })),

        // Analytics metrics
        analyticsMetrics: [],
        setAnalyticsMetrics: (metrics) => set({ analyticsMetrics: metrics }),
        addAnalyticsMetric: (metric) => set((state) => ({
          analyticsMetrics: [...state.analyticsMetrics, metric]
        })),

        // Voice transcriptions
        voiceTranscriptions: [],
        setVoiceTranscriptions: (transcriptions) => set({ voiceTranscriptions: transcriptions }),
        addVoiceTranscription: (transcription) => set((state) => ({
          voiceTranscriptions: [...state.voiceTranscriptions, transcription]
        })),

        // Search results
        searchResults: [],
        setSearchResults: (results) => set({ searchResults: results }),

        // Notification preferences
        notificationPreferences: [],
        setNotificationPreferences: (preferences) => set({ notificationPreferences: preferences }),
        updateNotificationPreference: (id, updates) => set((state) => ({
          notificationPreferences: state.notificationPreferences.map(pref =>
            pref.id === id ? { ...pref, ...updates } : pref
          )
        })),

        // Performance metrics
        performanceMetrics: [],
        setPerformanceMetrics: (metrics) => set({ performanceMetrics: metrics }),
        addPerformanceMetric: (metric) => set((state) => ({
          performanceMetrics: [...state.performanceMetrics, metric]
        })),

        // UI state
        isLoading: {},
        setLoading: (key, loading) => set((state) => ({
          isLoading: { ...state.isLoading, [key]: loading }
        })),

        errors: {},
        setError: (key, error) => set((state) => ({
          errors: error ? { ...state.errors, [key]: error } : { ...state.errors, [key]: undefined }
        })),

        // Modal states
        modals: {},
        openModal: (key) => set((state) => ({
          modals: { ...state.modals, [key]: true }
        })),
        closeModal: (key) => set((state) => ({
          modals: { ...state.modals, [key]: false }
        })),

        // Search and filters
        searchQuery: '',
        setSearchQuery: (query) => set({ searchQuery: query }),

        filters: {},
        setFilter: (key, value) => set((state) => ({
          filters: { ...state.filters, [key]: value }
        })),
        clearFilters: () => set({ filters: {} }),

        // Real-time connection
        isConnected: false,
        setConnected: (connected) => set({ isConnected: connected }),

        // Theme
        theme: 'system',
        setTheme: (theme) => set({ theme }),

        // Notifications
        notifications: [],
        addNotification: (notification) => set((state) => ({
          notifications: [{
            ...notification,
            id: Date.now().toString(),
            timestamp: new Date().toISOString(),
            read: false
          }, ...state.notifications]
        })),
        removeNotification: (id) => set((state) => ({
          notifications: state.notifications.filter(n => n.id !== id)
        })),
        clearNotifications: () => set({ notifications: [] }),
      }),
      {
        name: 'atom-app-store',
        partialize: (state) => ({
          currentView: state.currentView,
          userProfile: state.userProfile,
          theme: state.theme,
          widgets: state.widgets,
          voiceCommands: state.voiceCommands,
          filters: state.filters,
        }),
      }
    ),
    {
      name: 'Atom App Store',
    }
  )
);

// Selectors for computed state
export const useTasksStats = () => {
  const tasks = useAppStore((state) => state.tasks);
  return {
    total: tasks.length,
    completed: tasks.filter(t => t.status === 'completed').length,
    pending: tasks.filter(t => t.status === 'pending').length,
    inProgress: tasks.filter(t => t.status === 'in_progress').length,
    overdue: tasks.filter(t => new Date(t.dueDate) < new Date() && t.status !== 'completed').length,
  };
};

export const useUnreadMessagesCount = () => {
  const messages = useAppStore((state) => state.messages);
  return messages.filter(m => m.unread).length;
};

export const useTodaysEvents = () => {
  const events = useAppStore((state) => state.calendarEvents);
  const today = new Date();
  return events.filter(event =>
    new Date(event.startTime).toDateString() === today.toDateString()
  );
};

export const useFilteredTasks = () => {
  const tasks = useAppStore((state) => state.tasks);
  const searchQuery = useAppStore((state) => state.searchQuery);
  const filters = useAppStore((state) => state.filters);

  return tasks.filter(task => {
    // Search filter
    if (searchQuery && !task.title.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !task.description.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }

    // Status filter
    if (filters.status && task.status !== filters.status) {
      return false;
    }

    // Priority filter
    if (filters.priority && task.priority !== filters.priority) {
      return false;
    }

    // Assignee filter
    if (filters.assignee && task.assignee !== filters.assignee) {
      return false;
    }

    return true;
  });
};
