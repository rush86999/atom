import React from 'react';
import { motion } from 'framer-motion';
import {
  Search,
  Bell,
  Mic,
  User,
  Sun,
  Moon,
  Monitor,
  LogOut,
  Settings
} from 'lucide-react';
import { useAppStore } from '../store';
import { useTheme } from './ThemeProvider';
import { NotificationCenter } from './NotificationSystem';
import { View } from '../types';

interface HeaderProps {
  onVoiceCommand: () => void;
  className?: string;
}

const Header: React.FC<HeaderProps> = ({ onVoiceCommand, className = '' }) => {
  const {
    searchQuery,
    setSearchQuery,
    userProfile,
    currentView,
    isConnected
  } = useAppStore();

  const { theme, setTheme, resolvedTheme } = useTheme();
  const [showUserMenu, setShowUserMenu] = React.useState(false);
  const [showSearch, setShowSearch] = React.useState(false);

  const getViewTitle = (view: View) => {
    const titles = {
      dashboard: 'Dashboard',
      tasks: 'Tasks',
      agents: 'Agents',
      calendar: 'Calendar',
      communications: 'Communications',
      settings: 'Settings',
    };
    return titles[view] || 'Dashboard';
  };

  const handleThemeChange = (newTheme: 'light' | 'dark' | 'system') => {
    setTheme(newTheme);
  };

  const handleLogout = () => {
    // Handle logout logic
    localStorage.removeItem('authToken');
    window.location.href = '/login';
  };

  return (
    <header className={`bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-4 ${className}`}>
      <div className="flex items-center justify-between">
        {/* Left side - Title and search */}
        <div className="flex items-center space-x-4 flex-1">
          <div className="flex items-center space-x-3">
            <motion.h1
              key={currentView}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              className="text-2xl font-bold text-gray-900 dark:text-white"
            >
              {getViewTitle(currentView)}
            </motion.h1>

            {/* Connection status */}
            <div className="flex items-center space-x-2">
              <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
              <span className="text-xs text-gray-500 dark:text-gray-400">
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          </div>

          {/* Search */}
          <div className="flex-1 max-w-md">
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Search className="h-5 w-5 text-gray-400" />
              </div>
              <input
                type="text"
                placeholder={`Search ${currentView}...`}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="block w-full pl-10 pr-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md leading-5 bg-white dark:bg-gray-700 placeholder-gray-500 dark:placeholder-gray-400 text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>
        </div>

        {/* Right side - Actions */}
        <div className="flex items-center space-x-4">
          {/* Voice Command */}
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={onVoiceCommand}
            className="p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            title="Voice Commands (Ctrl+K)"
          >
            <Mic className="w-5 h-5" />
          </motion.button>

          {/* Notifications */}
          <NotificationCenter />

          {/* Theme Toggle */}
          <div className="relative">
            <button
              onClick={() => setShowUserMenu(!showUserMenu)}
              className="flex items-center space-x-2 p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded-md hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            >
              <div className="w-8 h-8 bg-gray-300 dark:bg-gray-600 rounded-full flex items-center justify-center">
                {userProfile?.avatar ? (
                  <img
                    src={userProfile.avatar}
                    alt={userProfile.name}
                    className="w-8 h-8 rounded-full"
                  />
                ) : (
                  <User className="w-4 h-4" />
                )}
              </div>
              {!showUserMenu && (
                <span className="text-sm font-medium text-gray-700 dark:text-gray-200">
                  {userProfile?.name || 'User'}
                </span>
              )}
            </button>

            {/* User Menu */}
            {showUserMenu && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="absolute right-0 mt-2 w-48 bg-white dark:bg-gray-800 rounded-md shadow-lg border border-gray-200 dark:border-gray-700 z-50"
              >
                <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                  <p className="text-sm font-medium text-gray-900 dark:text-white">
                    {userProfile?.name || 'User'}
                  </p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {userProfile?.email || 'user@example.com'}
                  </p>
                </div>

                <div className="py-1">
                  <button
                    onClick={() => {
                      setShowUserMenu(false);
                      // Navigate to profile
                    }}
                    className="flex items-center w-full px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700"
                  >
                    <User className="w-4 h-4 mr-3" />
                    Profile
                  </button>

                  <button
                    onClick={() => {
                      setShowUserMenu(false);
                      // Navigate to settings
                    }}
                    className="flex items-center w-full px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700"
                  >
                    <Settings className="w-4 h-4 mr-3" />
                    Settings
                  </button>
                </div>

                <div className="py-1 border-t border-gray-200 dark:border-gray-700">
                  <button
                    onClick={handleLogout}
                    className="flex items-center w-full px-4 py-2 text-sm text-red-600 dark:text-red-400 hover:bg-gray-100 dark:hover:bg-gray-700"
                  >
                    <LogOut className="w-4 h-4 mr-3" />
                    Sign out
                  </button>
                </div>
              </motion.div>
            )}
          </div>

          {/* Theme Selector */}
          <div className="flex items-center space-x-1 bg-gray-100 dark:bg-gray-700 rounded-md p-1">
            <button
              onClick={() => handleThemeChange('light')}
              className={`p-1.5 rounded ${
                theme === 'light'
                  ? 'bg-white dark:bg-gray-600 text-yellow-500'
                  : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-200'
              }`}
              title="Light theme"
            >
              <Sun className="w-4 h-4" />
            </button>
            <button
              onClick={() => handleThemeChange('system')}
              className={`p-1.5 rounded ${
                theme === 'system'
                  ? 'bg-white dark:bg-gray-600 text-blue-500'
                  : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-200'
              }`}
              title="System theme"
            >
              <Monitor className="w-4 h-4" />
            </button>
            <button
              onClick={() => handleThemeChange('dark')}
              className={`p-1.5 rounded ${
                theme === 'dark'
                  ? 'bg-white dark:bg-gray-600 text-gray-300'
                  : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-200'
              }`}
              title="Dark theme"
            >
              <Moon className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
