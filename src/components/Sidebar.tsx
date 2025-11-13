import React from 'react';
import { motion } from 'framer-motion';
import {
  LayoutDashboard,
  MessageCircle,
  CheckSquare,
  Users,
  Mic,
  Calendar,
  StickyNote,
  MessageSquare,
  Zap,
  DollarSign,
  Settings,
  Code,
  FileText,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { useAppStore } from '../store';
import { View } from '../types';

const navigation = [
  { name: 'Dashboard', view: 'dashboard' as const, icon: LayoutDashboard, shortcut: 'Alt+1' },
  { name: 'Tasks', view: 'tasks' as const, icon: CheckSquare, shortcut: 'Alt+2' },
  { name: 'Agents', view: 'agents' as const, icon: Users, shortcut: 'Alt+3' },
  { name: 'Calendar', view: 'calendar' as const, icon: Calendar, shortcut: 'Alt+4' },
  { name: 'Communications', view: 'communications' as const, icon: MessageSquare, shortcut: 'Alt+5' },
  { name: 'Settings', view: 'settings' as const, icon: Settings, shortcut: 'Alt+6' },
];

interface SidebarProps {
  className?: string;
}

const Sidebar: React.FC<SidebarProps> = ({ className = '' }) => {
  const { currentView, setCurrentView } = useAppStore();
  const [isCollapsed, setIsCollapsed] = React.useState(false);

  const handleNavigation = (view: View) => {
    setCurrentView(view);
  };

  return (
    <motion.div
      initial={false}
      animate={{ width: isCollapsed ? 64 : 256 }}
      className={`bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col ${className}`}
    >
      {/* Header */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center justify-between">
          {!isCollapsed && (
            <motion.h1
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="text-xl font-bold text-gray-900 dark:text-white"
            >
              Atom
            </motion.h1>
          )}
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {isCollapsed ? (
              <ChevronRight className="w-4 h-4" />
            ) : (
              <ChevronLeft className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4">
        <ul className="space-y-2">
          {navigation.map((item) => {
            const Icon = item.icon;
            const isActive = currentView === item.view;

            return (
              <li key={item.view}>
                <button
                  onClick={() => handleNavigation(item.view)}
                  className={`w-full flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                    isActive
                      ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-200'
                      : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100 dark:text-gray-400 dark:hover:text-white dark:hover:bg-gray-700'
                  }`}
                  title={`${item.name} (${item.shortcut})`}
                >
                  <Icon className="w-5 h-5 flex-shrink-0" />
                  {!isCollapsed && (
                    <motion.span
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -10 }}
                      className="ml-3"
                    >
                      {item.name}
                    </motion.span>
                  )}
                  {!isCollapsed && (
                    <span className="ml-auto text-xs text-gray-400">
                      {item.shortcut}
                    </span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-gray-200 dark:border-gray-700">
        {!isCollapsed && (
          <div className="text-xs text-gray-500 dark:text-gray-400">
            <p>Press Ctrl+K for voice commands</p>
          </div>
        )}
      </div>
    </motion.div>
  );
};

export default Sidebar;
