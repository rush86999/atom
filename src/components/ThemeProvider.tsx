import React, { createContext, useContext, useEffect, useState } from 'react';
import { useAppStore } from '../store';

type Theme = 'light' | 'dark' | 'system';

interface ThemeContextType {
  theme: Theme;
  resolvedTheme: 'light' | 'dark';
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};

interface ThemeProviderProps {
  children: React.ReactNode;
}

export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
  const { theme: storeTheme, setTheme: setStoreTheme } = useAppStore();
  const [resolvedTheme, setResolvedTheme] = useState<'light' | 'dark'>('light');

  // Resolve system theme
  const getSystemTheme = (): 'light' | 'dark' => {
    if (typeof window === 'undefined') return 'light';
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  };

  // Update resolved theme when store theme changes
  useEffect(() => {
    const newResolvedTheme = storeTheme === 'system' ? getSystemTheme() : storeTheme;
    setResolvedTheme(newResolvedTheme);
  }, [storeTheme]);

  // Listen for system theme changes
  useEffect(() => {
    if (storeTheme !== 'system') return;

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = () => {
      const newResolvedTheme = getSystemTheme();
      setResolvedTheme(newResolvedTheme);
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [storeTheme]);

  // Apply theme to document
  useEffect(() => {
    const root = document.documentElement;

    // Remove existing theme classes
    root.classList.remove('light', 'dark');

    // Add current theme class
    root.classList.add(resolvedTheme);

    // Update meta theme-color for mobile browsers
    const metaThemeColor = document.querySelector('meta[name="theme-color"]');
    if (metaThemeColor) {
      metaThemeColor.setAttribute(
        'content',
        resolvedTheme === 'dark' ? '#1f2937' : '#ffffff'
      );
    }
  }, [resolvedTheme]);

  const setTheme = (theme: Theme) => {
    setStoreTheme(theme);
  };

  const toggleTheme = () => {
    const newTheme = resolvedTheme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
  };

  const value: ThemeContextType = {
    theme: storeTheme,
    resolvedTheme,
    setTheme,
    toggleTheme,
  };

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
};

// Theme-aware wrapper components
export const ThemeWrapper: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className = '',
}) => {
  const { resolvedTheme } = useTheme();

  return (
    <div className={`theme-${resolvedTheme} ${className}`}>
      {children}
    </div>
  );
};

// CSS Variables for dynamic theming
export const ThemeStyles: React.FC = () => {
  const { resolvedTheme } = useTheme();

  const lightVars = {
    '--bg-primary': '#ffffff',
    '--bg-secondary': '#f9fafb',
    '--bg-tertiary': '#f3f4f6',
    '--text-primary': '#111827',
    '--text-secondary': '#6b7280',
    '--text-tertiary': '#9ca3af',
    '--border-primary': '#e5e7eb',
    '--border-secondary': '#d1d5db',
    '--accent-primary': '#3b82f6',
    '--accent-secondary': '#60a5fa',
    '--success': '#10b981',
    '--warning': '#f59e0b',
    '--error': '#ef4444',
    '--shadow-sm': '0 1px 2px 0 rgb(0 0 0 / 0.05)',
    '--shadow-md': '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
    '--shadow-lg': '0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)',
  };

  const darkVars = {
    '--bg-primary': '#111827',
    '--bg-secondary': '#1f2937',
    '--bg-tertiary': '#374151',
    '--text-primary': '#f9fafb',
    '--text-secondary': '#d1d5db',
    '--text-tertiary': '#9ca3af',
    '--border-primary': '#374151',
    '--border-secondary': '#4b5563',
    '--accent-primary': '#60a5fa',
    '--accent-secondary': '#93c5fd',
    '--success': '#34d399',
    '--warning': '#fbbf24',
    '--error': '#f87171',
    '--shadow-sm': '0 1px 2px 0 rgb(0 0 0 / 0.3)',
    '--shadow-md': '0 4px 6px -1px rgb(0 0 0 / 0.4), 0 2px 4px -2px rgb(0 0 0 / 0.4)',
    '--shadow-lg': '0 10px 15px -3px rgb(0 0 0 / 0.4), 0 4px 6px -4px rgb(0 0 0 / 0.4)',
  };

  const vars = resolvedTheme === 'dark' ? darkVars : lightVars;

  return (
    <style jsx global>{`
      :root {
        ${Object.entries(vars)
          .map(([key, value]) => `${key}: ${value};`)
          .join('\n        ')}
      }
    `}</style>
  );
};

// Theme toggle button component
export const ThemeToggle: React.FC<{ className?: string }> = ({ className = '' }) => {
  const { theme, resolvedTheme, setTheme } = useTheme();

  const handleThemeChange = (newTheme: Theme) => {
    setTheme(newTheme);
  };

  return (
    <div className={`flex items-center space-x-2 ${className}`}>
      <button
        onClick={() => handleThemeChange('light')}
        className={`p-2 rounded-md transition-colors ${
          resolvedTheme === 'light' && theme !== 'system'
            ? 'bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-400'
            : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'
        }`}
        aria-label="Light theme"
      >
        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
          <path
            fillRule="evenodd"
            d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      <button
        onClick={() => handleThemeChange('system')}
        className={`p-2 rounded-md transition-colors ${
          theme === 'system'
            ? 'bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-400'
            : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'
        }`}
        aria-label="System theme"
      >
        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
          <path
            fillRule="evenodd"
            d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      <button
        onClick={() => handleThemeChange('dark')}
        className={`p-2 rounded-md transition-colors ${
          resolvedTheme === 'dark' && theme !== 'system'
            ? 'bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-400'
            : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'
        }`}
        aria-label="Dark theme"
      >
        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
          <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
        </svg>
      </button>
    </div>
  );
};
