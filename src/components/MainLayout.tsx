import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';
import { VoiceCommandInterface } from './VoiceCommandInterface';
import { useVoiceCommands } from './VoiceCommandInterface';
import { getPerformanceMonitor } from '../utils/performance';
import { useAppStore } from '../store';
import { useRealtimeSync } from '../hooks/useWebSocket';
import useCurrentView from '../hooks/useCurrentView';
import useKeyboardShortcuts from '../hooks/useKeyboardShortcuts';

const MainLayout: React.FC = () => {
  const [voiceInterfaceOpen, setVoiceInterfaceOpen] = React.useState(false);
  const { processCommand } = useVoiceCommands();

  useRealtimeSync();
  useCurrentView();
  useKeyboardShortcuts({ onVoiceCommand: () => setVoiceInterfaceOpen(true) });

  const handleVoiceCommand = (command: string, confidence: number) => {
    const monitor = getPerformanceMonitor();
    monitor.timeFunction('voice_command_processing', () => {
      processCommand(command, confidence);
    });
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="flex">
        <Sidebar />
        <div className="flex-1 flex flex-col">
          <Header onVoiceCommand={() => setVoiceInterfaceOpen(true)} />
          <main className="flex-1 overflow-auto">
            <Outlet />
          </main>
        </div>
      </div>

      <VoiceCommandInterface
        isOpen={voiceInterfaceOpen}
        onClose={() => setVoiceInterfaceOpen(false)}
        onCommand={handleVoiceCommand}
      />
    </div>
  );
};

export default MainLayout;
