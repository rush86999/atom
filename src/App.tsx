import React, { Suspense } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './components/ThemeProvider';
import { ErrorBoundary } from './components/ErrorBoundary';
import { NotificationSystem } from './components/NotificationSystem';
import { WebSocketProvider } from './contexts/WebSocketProvider';
import { initializePerformanceMonitoring } from './utils/performance';
import MainLayout from './components/MainLayout';

// Lazy-loaded Views for performance
const DashboardView = React.lazy(() => import('./views/DashboardView').then(module => ({ default: module.DashboardView })));
const TasksView = React.lazy(() => import('./views/TasksView').then(module => ({ default: module.TasksView })));
const AgentsView = React.lazy(() => import('./views/AgentsView').then(module => ({ default: module.AgentsView })));
const CommunicationsView = React.lazy(() => import('./views/CommunicationsView').then(module => ({ default: module.CommunicationsView })));
const SettingsView = React.lazy(() => import('./views/SettingsView').then(module => ({ default: module.SettingsView })));
const CalendarView = React.lazy(() => import('./views/CalendarView'));
const ChatView = React.lazy(() => import('./views/ChatView').then(module => ({ default: module.ChatView })));
const VoiceView = React.lazy(() => import('./views/VoiceView').then(module => ({ default: module.VoiceView })));
const NotesView = React.lazy(() => import('./views/NotesView').then(module => ({ default: module.NotesView })));
const IntegrationsView = React.lazy(() => import('./views/IntegrationsView').then(module => ({ default: module.IntegrationsView })));
const WorkflowsView = React.lazy(() => import('./views/WorkflowsView').then(module => ({ default: module.WorkflowsView })));
const FinancesView = React.lazy(() => import('./views/FinancesView').then(module => ({ default: module.FinancesView })));
const DevStudioView = React.lazy(() => import('./views/DevStudioView').then(module => ({ default: module.DevStudioView })));
const DocsView = React.lazy(() => import('./views/DocsView').then(module => ({ default: module.DocsView })));

// Loading component for Suspense
const LoadingFallback = () => (
  <div className="flex items-center justify-center min-h-screen">
    <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-500"></div>
  </div>
);

// Create a client with advanced configuration
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      retry: (failureCount, error) => {
        // Exponential backoff with jitter
        return failureCount < 3;
      },
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
      networkMode: 'online',
    },
    mutations: {
      retry: 1,
      networkMode: 'online',
    },
  },
});

// Initialize performance monitoring
initializePerformanceMonitoring({
  enableWebVitals: true,
  enableCustomMetrics: true,
  sampleRate: 0.1, // 10% sampling for performance
});

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <Router>
          <ThemeProvider>
            <WebSocketProvider>
              <Suspense fallback={<LoadingFallback />}>
                <Routes>
                  <Route path="/" element={<MainLayout />}>
                    <Route index element={<Navigate to="/dashboard" replace />} />
                    <Route path="dashboard" element={<DashboardView />} />
                    <Route path="tasks" element={<TasksView />} />
                    <Route path="agents" element={<AgentsView />} />
                    <Route path="calendar" element={<CalendarView />} />
                    <Route path="communications" element={<CommunicationsView />} />
                    <Route path="settings" element={<SettingsView />} />
                    <Route path="chat" element={<ChatView />} />
                    <Route path="voice" element={<VoiceView />} />
                    <Route path="notes" element={<NotesView />} />
                    <Route path="integrations" element={<IntegrationsView />} />
                    <Route path="workflows" element={<WorkflowsView />} />
                    <Route path="finances" element={<FinancesView />} />
                    <Route path="dev" element={<DevStudioView />} />
                    <Route path="docs" element={<DocsView />} />
                  </Route>
                </Routes>
              </Suspense>
            </WebSocketProvider>
            <NotificationSystem />
          </ThemeProvider>
        </Router>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
