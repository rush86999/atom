import React, { useState } from 'react';
import { View } from './types';
import { ChatView } from './views/ChatView';
import { AgentsView } from './views/AgentsView';
import { VoiceView } from './views/VoiceView';
import { CalendarView } from './views/CalendarView';
import { TasksView } from './views/TasksView';
import { CommunicationsView } from './views/CommunicationsView';
import { IntegrationsView } from './views/IntegrationsView';
import { WorkflowsView } from './views/WorkflowsView';
import { FinancesView } from './views/FinancesView';
import { SettingsView } from './views/SettingsView';
import { DevStudioView } from './views/DevStudioView';
import { DashboardView } from './views/DashboardView';
import { NotesView } from './views/NotesView';

export const App = () => {
  const [currentView, setCurrentView] = useState<View>("dashboard");

  const renderView = () => {
    switch (currentView) {
      case "dashboard": return <DashboardView />;
      case "chat": return <ChatView />;
      case "agents": return <AgentsView />;
      case "voice": return <VoiceView />;
      case "calendar": return <CalendarView />;
      case "tasks": return <TasksView />;
      case "notes": return <NotesView />;
      case "communications": return <CommunicationsView />;
      case "integrations": return <IntegrationsView />;
      case "workflows": return <WorkflowsView />;
      case "finances": return <FinancesView />;
      case "settings": return <SettingsView />;
      case "dev": return <DevStudioView />;
      default: return <DashboardView />;
    }
  };

  return (
    <div className="app-container">
      <aside className="sidebar">
        <div className="sidebar-header">
             <svg className="sidebar-header-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M12.75 2.25a.75.75 0 00-1.5 0v.854A4.496 4.496 0 009 4.887V2.25a.75.75 0 00-1.5 0v2.637a4.496 4.496 0 00-2.343 1.787A.75.75 0 006 8.25v2.854a4.496 4.496 0 00-1.263 2.343A.75.75 0 005.25 15v2.637a4.496 4.496 0 001.787 2.343.75.75 0 001.213-.67V16.5a4.496 4.496 0 002.343-1.263A.75.75 0 0012 14.25v-2.854a4.496 4.496 0 001.263-2.343A.75.75 0 0012.75 9V6.363a4.496 4.496 0 00-1.787-2.343A.75.75 0 009.75 3.34V4.5a4.496 4.496 0 002.343 1.263A.75.75 0 0013.5 6v2.854a4.496 4.496 0 001.263 2.343.75.75 0 00.67 1.213H16.5a4.496 4.496 0 001.263-2.343.75.75 0 00-.67-1.213h-1.087a4.496 4.496 0 00-2.343-1.263A.75.75 0 0012 8.25V5.613a4.496 4.496 0 001.787-2.343.75.75 0 00-.437-.92z" /></svg>
          <h1>Atom</h1>
        </div>
        <nav className="sidebar-nav">
           <button className={`nav-item ${currentView === 'dashboard' ? 'active' : ''}`} onClick={() => setCurrentView('dashboard')}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path d="M10 2a.75.75 0 01.75.75v.5a.75.75 0 01-1.5 0v-.5A.75.75 0 0110 2zM8.5 4.5a.75.75 0 00-1.5 0v.5a.75.75 0 001.5 0v-.5zM11.5 4.5a.75.75 0 00-1.5 0v.5a.75.75 0 001.5 0v-.5zM8 7.5a.75.75 0 01.75-.75h2.5a.75.75 0 010 1.5h-2.5A.75.75 0 018 7.5zM8.25 10a.75.75 0 000 1.5h3.5a.75.75 0 000-1.5h-3.5zM8 13.25a.75.75 0 01.75-.75h2.5a.75.75 0 010 1.5h-2.5a.75.75 0 01-.75-.75zM10 18a7 7 0 100-14 7 7 0 000 14zM11.5 10.75a.75.75 0 00-1.5 0v2.5a.75.75 0 001.5 0v-2.5z" clipRule="evenodd" /></svg>
            Dashboard
          </button>
          <button className={`nav-item ${currentView === 'dev' ? 'active' : ''}`} onClick={() => setCurrentView('dev')}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M12.316 3.051a1 1 0 01.633 1.265l-4 12a1 1 0 11-1.898-.632l4-12a1 1 0 011.265-.633zM5.707 6.293a1 1 0 010 1.414L3.414 10l2.293 2.293a1 1 0 11-1.414 1.414l-3-3a1 1 0 010-1.414l3-3a1 1 0 011.414 0zm8.586 0a1 1 0 011.414 0l3 3a1 1 0 010 1.414l-3 3a1 1 0 11-1.414-1.414L16.586 10l-2.293-2.293a1 1 0 010-1.414z" clipRule="evenodd" /></svg>
            Dev Studio
          </button>
          <button className={`nav-item ${currentView === 'chat' ? 'active' : ''}`} onClick={() => setCurrentView('chat')}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path d="M10 3a7 7 0 100 14 7 7 0 000-14zM2 10a8 8 0 1116 0 8 8 0 01-16 0z" /><path d="M6.39 8.31a.75.75 0 011.08-.22l2.35 1.76a.75.75 0 010 1.3l-2.35 1.76a.75.75 0 11-.86-1.52l1.63-1.22-1.63-1.22a.75.75 0 01-.22-1.08z" /></svg>
            Chat
          </button>
          <button className={`nav-item ${currentView === 'communications' ? 'active' : ''}`} onClick={() => setCurrentView('communications')}>
             <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path d="M3 4a2 2 0 00-2 2v1.161l8.441 4.221a1.25 1.25 0 001.118 0L19 7.162V6a2 2 0 00-2-2H3z" /><path d="M19 8.839l-7.77 3.885a2.75 2.75 0 01-2.46 0L1 8.839V14a2 2 0 002 2h14a2 2 0 002-2V8.839z" /></svg>
            Inbox
          </button>
           <button className={`nav-item ${currentView === 'tasks' ? 'active' : ''}`} onClick={() => setCurrentView('tasks')}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path d="M5.5 3a.75.75 0 000 1.5h9a.75.75 0 000-1.5h-9zM5.5 6.5A.75.75 0 004 7.25v5.5a.75.75 0 001.5 0v-5.5A.75.75 0 005.5 6.5zM8 7.25a.75.75 0 01.75-.75h5.5a.75.75 0 010 1.5h-5.5a.75.75 0 01-.75-.75zM8 10.25a.75.75 0 01.75-.75h5.5a.75.75 0 010 1.5h-5.5a.75.75 0 01-.75-.75zM8 13.25a.75.75 0 01.75-.75h5.5a.75.75 0 010 1.5h-5.5a.75.75 0 01-.75-.75z" /></svg>
            Tasks
          </button>
          <button className={`nav-item ${currentView === 'notes' ? 'active' : ''}`} onClick={() => setCurrentView('notes')}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path d="M5.433 13.917l1.262-3.155A4 4 0 017.58 9.42l6.92-6.918a2.121 2.121 0 013 3l-6.92 6.918c-.383.383-.84.685-1.343.886l-3.154 1.262a.5.5 0 01-.65-.65z" /><path d="M3.5 5.75c0-.69.56-1.25 1.25-1.25H10A.75.75 0 0010 3H4.75A2.75 2.75 0 002 5.75v9.5A2.75 2.75 0 004.75 18h9.5A2.75 2.75 0 0017 15.25V10a.75.75 0 00-1.5 0v5.25c0 .69-.56 1.25-1.25 1.25h-9.5c-.69 0-1.25-.56-1.25-1.25v-9.5z" /></svg>
            Notes
          </button>
           <button className={`nav-item ${currentView === 'calendar' ? 'active' : ''}`} onClick={() => setCurrentView('calendar')}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M5.75 2a.75.75 0 01.75.75V4h7V2.75a.75.75 0 011.5 0V4h.25A2.75 2.75 0 0118 6.75v8.5A2.75 2.75 0 0115.25 18H4.75A2.75 2.75 0 012 15.25v-8.5A2.75 2.75 0 014.75 4H5V2.75A.75.75 0 015.75 2zM4.5 8.5a.75.75 0 00-1.5 0v6.25c0 .414.336.75.75.75h10.5a.75.75 0 00.75-.75V8.5a.75.75 0 00-1.5 0v2.5h-2.5a.75.75 0 00-1.5 0v-2.5H8.5a.75.75 0 00-1.5 0v2.5H4.5v-2.5z" clipRule="evenodd" /></svg>
            Calendar
          </button>
          <button className={`nav-item ${currentView === 'finances' ? 'active' : ''}`} onClick={() => setCurrentView('finances')}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path d="M3.5 4.5a.5.5 0 00-.5.5v10a.5.5 0 00.5.5h13a.5.5 0 00.5-.5v-10a.5.5 0 00-.5-.5h-13zM16 4a2 2 0 00-2-2h-9a2 2 0 00-2 2v12a2 2 0 002 2h9a2 2 0 002-2V4z" /><path d="M12.5 8.5a.5.5 0 01.5.5v2a.5.5 0 01-1 0v-2a.5.5 0 01.5-.5zM10.5 8.5a.5.5 0 01.5.5v4a.5.5 0 01-1 0v-4a.5.5 0 01.5-.5zM8.5 8.5a.5.5 0 01.5.5v6a.5.5 0 01-1 0v-6a.5.5 0 01.5-.5zM6.5 8.5a.5.5 0 01.5.5v3a.5.5 0 01-1 0v-3a.5.5 0 01.5-.5z" /></svg>
            Finances
          </button>
           <button className={`nav-item ${currentView === 'workflows' ? 'active' : ''}`} onClick={() => setCurrentView('workflows')}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path d="M10 3.5a1.5 1.5 0 01.82 2.81l5.24 3.14a1.5 1.5 0 010 2.1l-5.24 3.14A1.5 1.5 0 119.18 12L13.5 9.5 9.18 7A1.5 1.5 0 1110 3.5zM3.5 6a1.5 1.5 0 113 0 1.5 1.5 0 01-3 0zM15 12.5a1.5 1.5 0 100 3 1.5 1.5 0 000-3z" /></svg>
            Workflows
          </button>
           <button className={`nav-item ${currentView === 'integrations' ? 'active' : ''}`} onClick={() => setCurrentView('integrations')}>
             <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M11.91 2.22a.75.75 0 011.06 0l4.25 4.25a.75.75 0 010 1.06l-4.25 4.25a.75.75 0 01-1.06-1.06L14.69 8 8 8a.75.75 0 010-1.5l6.69 0-2.78-2.78a.75.75 0 010-1.06z" clipRule="evenodd" /><path fillRule="evenodd" d="M3.25 4a.75.75 0 01.75.75v10.5a.75.75 0 01-1.5 0V4.75A.75.75 0 013.25 4zM8.09 17.78a.75.75 0 01-1.06 0l-4.25-4.25a.75.75 0 010-1.06l4.25-4.25a.75.75 0 011.06 1.06L5.31 12l6.69 0a.75.75 0 010 1.5L5.31 13.5l2.78 2.78a.75.75 0 010 1.06z" clipRule="evenodd" /></svg>
             Integrations
          </button>
          <button className={`nav-item ${currentView === 'agents' ? 'active' : ''}`} onClick={() => setCurrentView('agents')}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M15.98 1.8V1.84a2.25 2.25 0 012.249 2.248v11.838A2.25 2.25 0 0115.98 18.17v.033a2.25 2.25 0 01-2.249-2.25V4.1a2.25 2.25 0 012.249-2.25v-.04zM4.02 18.2V18.16a2.25 2.25 0 01-2.249-2.248V4.074A2.25 2.25 0 014.02 1.83v-.033a2.25 2.25 0 012.249 2.25v11.85A2.25 2.25 0 014.02 18.2zM10 1.8a2.25 2.25 0 00-2.25 2.25v11.85a2.25 2.25 0 002.25 2.25 2.25 2.25 0 002.25-2.25V4.05A2.25 2.25 0 0010 1.8z" clipRule="evenodd" /></svg>
            Agents
          </button>
          <button className={`nav-item ${currentView === 'voice' ? 'active' : ''}`} onClick={() => setCurrentView('voice')}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path d="M7 4a3 3 0 016 0v6a3 3 0 11-6 0V4z" /><path d="M5.5 8.5a.5.5 0 01.5.5v1a4 4 0 008 0v-1a.5.5 0 011 0v1a5 5 0 01-4.5 4.975V17h3a.5.5 0 010 1h-7a.5.5 0 010-1h3v-2.025A5 5 0 014.5 10v-1a.5.5 0 01.5-.5z" /></svg>
            Voice
          </button>
          <button className={`nav-item ${currentView === 'settings' ? 'active' : ''}`} onClick={() => setCurrentView('settings')}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M11.078 2.25c-.217-.065-.438-.11-.67-.143a7.5 7.5 0 100 15.786c.232-.033.453-.078.67-.143a.75.75 0 00.282-1.488A5.25 5.25 0 019.5 4.504a.75.75 0 00.282-1.488zM12.61 3.66a.75.75 0 01.97-.246 6 6 0 013.363 3.363.75.75 0 01-.246.97l-.02.012a.75.75 0 01-.97.246 4.5 4.5 0 00-2.52-2.52.75.75 0 01.246-.97z" clipRule="evenodd" /></svg>
            Settings
          </button>
        </nav>
      </aside>
      <main className="main-content">
        {renderView()}
      </main>
    </div>
  );
};