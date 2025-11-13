import React, { useEffect, Suspense, startTransition } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from './components/ThemeProvider';
import { ErrorBoundary } from './components/ErrorBoundary';
import { NotificationSystem } from './components/NotificationSystem';
import { VoiceCommandInterface } from './components/VoiceCommandInterface';
import { useRealtimeSync } from './hooks/useWebSocket';
import { useVoiceCommands } from './components/VoiceCommandInterface';
import { useAppStore } from './store';
import { View } from './types';

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

// Components
import Sidebar from './components/Sidebar';
import Header from './components/Header';

// Loading component for Suspense
const LoadingFallback = () => (
  <div className="flex items-center justify-center min-h-screen">
    <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-500"></div>
  </div>
);

// Create a client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      retry: 3,
    },
  },
});

function AppContent() {
  const { currentView, setCurrentView } = useAppStore();
  const [voiceInterfaceOpen, setVoiceInterfaceOpen] = React.useState(false);

  // Initialize real-time sync
  useRealtimeSync();

  // Voice commands
  const { processCommand } = useVoiceCommands();

  const handleVoiceCommand = (command: string, confidence: number) => {
    processCommand(command, confidence);
  };

  // Keyboard shortcuts with startTransition for non-urgent updates
  useEffect(() => {
    const handleKeyPress = (event: KeyboardEvent) => {
      // Ctrl/Cmd + K for voice commands
      if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
        event.preventDefault();
        setVoiceInterfaceOpen(true);
      }

      // Alt + number for navigation
      if (event.altKey && event.key >= '1' && event.key <= '9') {
        event.preventDefault();
        const views: View[] = ['dashboard', 'chat', 'agents', 'voice', 'calendar', 'tasks', 'notes', 'communications', 'integrations'];
        const index = parseInt(event.key) - 1;
        if (views[index]) {
          startTransition(() => {
            setCurrentView(views[index]);
          });
        }
      }
    };

    document.addEventListener('keydown', handleKeyPress);
    return () => document.removeEventListener('keydown', handleKeyPress);
  }, [setCurrentView]);

  const renderCurrentView = () => {
    const viewComponent = (() => {
      switch (currentView) {
        case 'dashboard':
          return <DashboardView />;
        case 'chat':
          return <ChatView />;
        case 'agents':
          return <AgentsView />;
        case 'voice':
          return <VoiceView />;
        case 'calendar':
          return <CalendarView />;
        case 'tasks':
          return <TasksView />;
        case 'notes':
          return <NotesView />;
        case 'communications':
          return <CommunicationsView />;
        case 'integrations':
          return <IntegrationsView />;
        case 'workflows':
          return <WorkflowsView />;
        case 'finances':
          return <FinancesView />;
        case 'settings':
          return <SettingsView />;
        case 'dev':
          return <DevStudioView />;
        case 'docs':
          return <DocsView />;
        default:
          return <DashboardView />;
      }
    })();

    return (
      <Suspense fallback={<LoadingFallback />}>
        {viewComponent}
      </Suspense>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="flex">
        <Sidebar />
        <div className="flex-1 flex flex-col">
          <Header onVoiceCommand={() => setVoiceInterfaceOpen(true)} />
          <main className="flex-1 overflow-auto">
            <ErrorBoundary>
              {renderCurrentView()}
            </ErrorBoundary>
          </main>
        </div>
      </div>

      {/* Voice Command Interface */}
      <VoiceCommandInterface
        isOpen={voiceInterfaceOpen}
        onClose={() => setVoiceInterfaceOpen(false)}
        onCommand={handleVoiceCommand}
      />

      {/* Notification System */}
      <NotificationSystem />
    </div>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <Router>
          <ThemeProvider>
            <Routes>
              <Route path="/" element={<AppContent />} />
              <Route path="/dashboard" element={<AppContent />} />
              <Route path="/tasks" element={<AppContent />} />
              <Route path="/agents" element={<AppContent />} />
              <Route path="/calendar" element={<AppContent />} />
              <Route path="/communications" element={<AppContent />} />
              <Route path="/settings" element={<AppContent />} />
            </Routes>
          </ThemeProvider>
        </Router>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
