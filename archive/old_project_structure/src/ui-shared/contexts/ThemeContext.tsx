atom/src/ui-shared/contexts/ThemeContext.tsx
import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { designSystem, ThemeContextType } from '../design-system';

interface ThemeProviderProps {
  children: ReactNode;
  defaultTheme?: 'dark' | 'light';
  storageKey?: string;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const ThemeProvider: React.FC<ThemeProviderProps> = ({
  children,
  defaultTheme = 'dark',
  storageKey = 'atom-ui-theme',
}) => {
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem(storageKey);
      return (stored as 'dark' | 'light') || defaultTheme;
    }
    return defaultTheme;
  });

  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem(storageKey, theme);
      document.documentElement.setAttribute('data-theme', theme);

      // Apply theme colors as CSS variables
      const root = document.documentElement;
      const colors = designSystem.colors[theme];

      Object.entries(colors).forEach(([key, value]) => {
        root.style.setProperty(`--${key}`, value);
      });
    }
  }, [theme, storageKey]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  };

  const value: ThemeContextType = {
    theme,
    toggleTheme,
    setTheme,
  };

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = (): ThemeContextType => {
  const context = useContext(ThemeContext);
  if (context === undefined) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};

// Utility hook to get current theme colors
export const useThemeColors = () => {
  const { theme } = useTheme();
  return designSystem.colors[theme];
};

// Higher-order component for theme consumption
export const withTheme = <P extends object>(Component: React.ComponentType<P>) => {
  return function WithTheme(props: P) {
    const theme = useTheme();
    return <Component {...props} theme={theme} />;
  };
};

export default ThemeContext;
