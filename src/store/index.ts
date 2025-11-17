import { create } from 'zustand';
import { devtools, persist, subscribeWithSelector } from 'zustand/middleware';
import { getPerformanceMonitor } from '../utils/performance';
import { withOptimisticUpdates } from './optimisticUpdates';
import { updateTask as apiUpdateTask } from '../data';
import {
  UserProfile,
  Agent,
  Task,
  CalendarEvent,
  CommunicationsMessage,
  Integration,
  Workflow,
  Notification,
  WidgetConfig,
  VoiceCommand,
  Transaction,
  Budget,
  Note,
  ChatMessage,
} from '../types';

export interface AppState {
  // User
  userProfile: UserProfile | null;
  setUserProfile: (profile: UserProfile) => void;

  // Tasks
  tasks: Task[];
  setTasks: (tasks: Task[]) => void;
  addTask: (task: Task) => void;
  updateTask: (id: string, updates: Partial<Task>) => void;
  deleteTask: (id: string) => void;

  // Calendar
  calendarEvents: CalendarEvent[];
  setCalendarEvents: (events: CalendarEvent[]) => void;

  // Messages
  messages: CommunicationsMessage[];
  setMessages: (messages: CommunicationsMessage[]) => void;

  // Integrations
  integrations: Integration[];
  setIntegrations: (integrations: Integration[]) => void;
  updateIntegration: (id: string, updates: Partial<Integration>) => void;

  // Workflows
  workflows: Workflow[];
  setWorkflows: (workflows: Workflow[]) => void;
  addWorkflow: (workflow: Workflow) => void;

  // Agents
  agents: Agent[];
  setAgents: (agents: Agent[]) => void;

  // Voice Commands
  voiceCommands: VoiceCommand[];
  setVoiceCommands: (commands: VoiceCommand[]) => void;

  // Notes
  notes: Note[];
  setNotes: (notes: Note[]) => void;
  addNote: (note: Note) => void;
  updateNote: (id: string, updates: Partial<Note>) => void;
  deleteNote: (id: string) => void;

  // Chat
  chatMessages: ChatMessage[];
  setChatMessages: (messages: ChatMessage[]) => void;
  addChatMessage: (message: ChatMessage) => void;

  // Finances
  transactions: Transaction[];
  budgets: Budget[];
  setTransactions: (transactions: Transaction[]) => void;
  setBudgets: (budgets: Budget[]) => void;

  // UI State
  loading: Record<string, boolean>;
  setLoading: (key: string, value: boolean) => void;

  errors: Record<string, string | null>;
  setError: (key: string, error: string | null) => void;

  notifications: Notification[];
  addNotification: (notification: Notification) => void;
  removeNotification: (id: string) => void;
  clearNotifications: () => void;

  // Connection State
  connected: boolean;
  setConnected: (connected: boolean) => void;

  // Widgets
  widgets: WidgetConfig[];
  setWidgets: (widgets: WidgetConfig[]) => void;
  toggleWidget: (id: string) => void;

  // View
  currentView: string;
  setCurrentView: (view: string) => void;

  // Additional methods for WebSocket and optimistic updates
  markMessageAsRead: (messageId: string) => void;
  updateWorkflow: (id: string, updates: Partial<Workflow>) => void;
  deleteWorkflow: (id: string) => void;
  addCalendarEvent: (event: CalendarEvent) => void;
  updateCalendarEvent: (id: string, updates: Partial<CalendarEvent>) => void;
  deleteCalendarEvent: (id: string) => void;
  addAgentLog: (log: any) => void;
  optimisticUpdateTask: (id: string, updates: Partial<Task>) => void;
  revertOptimisticUpdate: (id: string, originalData: Task) => void;
}

const createAppStore = () =>
  create<AppState>()(
    devtools(
      subscribeWithSelector(
        persist(
          (set, get) => ({
            // User
            userProfile: null,
            setUserProfile: (profile) => set({ userProfile: profile }),

            // Tasks
            tasks: [],
            setTasks: (tasks) => set({ tasks }),
            addTask: (task) => set((state) => ({ tasks: [...state.tasks, task] })),
            updateTask: withOptimisticUpdates(set, get, 'tasks', apiUpdateTask),
            deleteTask: (id) =>
              set((state) => ({
                tasks: state.tasks.filter((task) => task.id !== id),
              })),

            // Calendar
            calendarEvents: [],
            setCalendarEvents: (events) => set({ calendarEvents: events }),

            // Messages
            messages: [],
            setMessages: (messages) => set({ messages }),

            // Integrations
            integrations: [],
            setIntegrations: (integrations) => set({ integrations }),
            updateIntegration: (id, updates) =>
              set((state) => ({
                integrations: state.integrations.map((int) =>
                  int.id === id ? { ...int, ...updates } : int
                ),
              })),

            // Workflows
            workflows: [],
            setWorkflows: (workflows) => set({ workflows }),
            addWorkflow: (workflow) =>
              set((state) => ({ workflows: [...state.workflows, workflow] })),

            // Agents
            agents: [],
            setAgents: (agents) => set({ agents }),

            // Voice Commands
            voiceCommands: [],
            setVoiceCommands: (commands) => set({ voiceCommands: commands }),

            // Notes
            notes: [],
            setNotes: (notes) => set({ notes }),
            addNote: (note) =>
              set((state) => ({ notes: [...state.notes, note] })),
            updateNote: (id, updates) =>
              set((state) => ({
                notes: state.notes.map((note) =>
                  note.id === id ? { ...note, ...updates } : note
                ),
              })),
            deleteNote: (id) =>
              set((state) => ({
                notes: state.notes.filter((note) => note.id !== id),
              })),

            // Chat
            chatMessages: [],
            setChatMessages: (messages) => set({ chatMessages: messages }),
            addChatMessage: (message) =>
              set((state) => ({ chatMessages: [...state.chatMessages, message] })),

            // Finances
            transactions: [],
            budgets: [],
            setTransactions: (transactions) => set({ transactions }),
            setBudgets: (budgets) => set({ budgets }),

            // UI State
            loading: {},
            setLoading: (key, value) =>
              set((state) => ({
                loading: { ...state.loading, [key]: value },
              })),

            errors: {},
            setError: (key, error) =>
              set((state) => ({
                errors: { ...state.errors, [key]: error },
              })),

            notifications: [],
            addNotification: (notification) =>
              set((state) => ({
                notifications: [
                  ...state.notifications,
                  { ...notification, id: Date.now().toString() },
                ],
              })),
            removeNotification: (id) =>
              set((state) => ({
                notifications: state.notifications.filter((n) => n.id !== id),
              })),
            clearNotifications: () => set({ notifications: [] }),

            // Connection State
            connected: false,
            setConnected: (connected) => set({ connected }),

            // Widgets
            widgets: [],
            setWidgets: (widgets) => set({ widgets }),
            toggleWidget: (id) =>
              set((state) => ({
                widgets: state.widgets.map((w) =>
                  w.id === id ? { ...w, visible: !w.visible } : w
                ),
              })),

            // View
            currentView: 'dashboard',
            setCurrentView: (view) => set({ currentView: view }),

            // Additional methods for WebSocket and optimistic updates
            markMessageAsRead: (messageId) =>
              set((state) => ({
                messages: state.messages.map((m) =>
                  m.id === messageId ? { ...m, unread: false, read: true } : m
                ),
              })),

            updateWorkflow: (id, updates) =>
              set((state) => ({
                workflows: state.workflows.map((w) =>
                  w.id === id ? { ...w, ...updates } : w
                ),
              })),

            deleteWorkflow: (id) =>
              set((state) => ({
                workflows: state.workflows.filter((w) => w.id !== id),
              })),

            addCalendarEvent: (event) =>
              set((state) => ({
                calendarEvents: [...state.calendarEvents, event],
              })),

            updateCalendarEvent: (id, updates) =>
              set((state) => ({
                calendarEvents: state.calendarEvents.map((e) =>
                  e.id === id ? { ...e, ...updates } : e
                ),
              })),

            deleteCalendarEvent: (id) =>
              set((state) => ({
                calendarEvents: state.calendarEvents.filter((e) => e.id !== id),
              })),

            addAgentLog: (log) =>
              set((state) => ({
                // Assuming agent logs are stored in a new agentLogs field
                // This is a placeholder - adapt based on your actual structure
              })),

            optimisticUpdateTask: (id, updates) =>
              set((state) => ({
                tasks: state.tasks.map((t) =>
                  t.id === id ? { ...t, ...updates, _optimistic: true } : t
                ),
              })),

            revertOptimisticUpdate: (id, originalData) =>
              set((state) => ({
                tasks: state.tasks.map((t) =>
                  t.id === id ? originalData : t
                ),
              })),
          }),
          {
            name: 'atom-store',
            version: 1,
          }
        )
      ),
      { name: 'AppStore', enabled: process.env.NODE_ENV === 'development' }
    )
  );

export const useAppStore = createAppStore();

// Selectors
export const selectTasks = (state: AppState) => state.tasks;
export const selectTaskById = (id: string) => (state: AppState) =>
  state.tasks.find((t) => t.id === id);
export const selectLoading = (state: AppState) => state.loading;
export const selectErrors = (state: AppState) => state.errors;
export const selectNotifications = (state: AppState) => state.notifications;
export const selectUserProfile = (state: AppState) => state.userProfile;
export const selectConnected = (state: AppState) => state.connected;

