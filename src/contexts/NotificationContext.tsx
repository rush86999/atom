import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { useAppStore } from '../store';

interface NotificationPreferences {
  enableSound: boolean;
  enableDesktop: boolean;
  quietHours: {
    enabled: boolean;
    start: string; // HH:MM format
    end: string; // HH:MM format
  };
  categories: {
    [key: string]: {
      enabled: boolean;
      sound: boolean;
      desktop: boolean;
    };
  };
}

interface NotificationContextType {
  preferences: NotificationPreferences;
  updatePreferences: (prefs: Partial<NotificationPreferences>) => void;
  showNotification: (notification: Omit<Notification, 'id' | 'timestamp' | 'read'>) => void;
  dismissNotification: (id: string) => void;
  dismissAll: () => void;
  markAsRead: (id: string) => void;
  markAllAsRead: () => void;
  getUnreadCount: () => number;
  isQuietHours: () => boolean;
}

interface Notification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title: string;
  message?: string;
  category?: string;
  timestamp: string;
  read: boolean;
  persistent?: boolean;
  action?: {
    label: string;
    onClick: () => void;
  };
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

const defaultPreferences: NotificationPreferences = {
  enableSound: true,
  enableDesktop: false,
  quietHours: {
    enabled: false,
    start: '22:00',
    end: '08:00',
  },
  categories: {
    tasks: { enabled: true, sound: true, desktop: false },
    messages: { enabled: true, sound: true, desktop: true },
    calendar: { enabled: true, sound: true, desktop: true },
    system: { enabled: true, sound: false, desktop: false },
    agents: { enabled: true, sound: true, desktop: false },
  },
};

interface NotificationProviderProps {
  children: ReactNode;
}

export const NotificationProvider: React.FC<NotificationProviderProps> = ({ children }) => {
  const [preferences, setPreferences] = useState<NotificationPreferences>(() => {
    const stored = localStorage.getItem('notificationPreferences');
    return stored ? { ...defaultPreferences, ...JSON.parse(stored) } : defaultPreferences;
  });

  const { addNotification, removeNotification, clearNotifications } = useAppStore();

  const updatePreferences = useCallback((newPrefs: Partial<NotificationPreferences>) => {
    setPreferences(prev => {
      const updated = { ...prev, ...newPrefs };
      localStorage.setItem('notificationPreferences', JSON.stringify(updated));
      return updated;
    });
  }, []);

  const isQuietHours = useCallback(() => {
    if (!preferences.quietHours.enabled) return false;

    const now = new Date();
    const currentTime = now.getHours() * 60 + now.getMinutes();

    const [startHour, startMinute] = preferences.quietHours.start.split(':').map(Number);
    const [endHour, endMinute] = preferences.quietHours.end.split(':').map(Number);

    const startTime = startHour * 60 + startMinute;
    const endTime = endHour * 60 + endMinute;

    if (startTime <= endTime) {
      // Same day range
      return currentTime >= startTime && currentTime <= endTime;
    } else {
      // Overnight range
      return currentTime >= startTime || currentTime <= endTime;
    }
  }, [preferences.quietHours]);

  const shouldShowNotification = useCallback((category?: string) => {
    if (isQuietHours()) return false;

    if (category) {
      const categoryPrefs = preferences.categories[category];
      return categoryPrefs?.enabled ?? true;
    }

    return true;
  }, [preferences.categories, isQuietHours]);

  const playSound = useCallback((type: Notification['type'], category?: string) => {
    if (!preferences.enableSound) return;

    if (category) {
      const categoryPrefs = preferences.categories[category];
      if (!categoryPrefs?.sound) return;
    }

    // Simple audio feedback - you can replace with actual sound files
    const audio = new Audio();
    audio.volume = 0.3;

    switch (type) {
      case 'success':
        // Success sound (you can add actual audio files)
        break;
      case 'error':
        // Error sound
        break;
      case 'warning':
        // Warning sound
        break;
      case 'info':
      default:
        // Info sound
        break;
    }
  }, [preferences.enableSound, preferences.categories]);

  const showDesktopNotification = useCallback((title: string, options?: NotificationOptions) => {
    if (!preferences.enableDesktop || !('Notification' in window)) return;

    if (Notification.permission === 'granted') {
      new Notification(title, options);
    } else if (Notification.permission !== 'denied') {
      Notification.requestPermission().then(permission => {
        if (permission === 'granted') {
          new Notification(title, options);
        }
      });
    }
  }, [preferences.enableDesktop]);

  const showNotification = useCallback((notification: Omit<Notification, 'id' | 'timestamp' | 'read'>) => {
    if (!shouldShowNotification(notification.category)) return;

    // Add to store
    addNotification({
      ...notification,
      read: false,
    });

    // Play sound
    playSound(notification.type, notification.category);

    // Show desktop notification
    if (notification.category) {
      const categoryPrefs = preferences.categories[notification.category];
      if (categoryPrefs?.desktop) {
        showDesktopNotification(notification.title, {
          body: notification.message,
          icon: '/favicon.ico', // Add your app icon
        });
      }
    }
  }, [shouldShowNotification, playSound, showDesktopNotification, preferences.categories, addNotification]);

  const dismissNotification = useCallback((id: string) => {
    removeNotification(id);
  }, [removeNotification]);

  const dismissAll = useCallback(() => {
    clearNotifications();
  }, [clearNotifications]);

  const markAsRead = useCallback((id: string) => {
    // This would need to be implemented in the store
    // For now, we'll just remove it (assuming read = dismissed)
    removeNotification(id);
  }, [removeNotification]);

  const markAllAsRead = useCallback(() => {
    clearNotifications();
  }, [clearNotifications]);

  const getUnreadCount = useCallback(() => {
    // This would need to be implemented to track unread count
    return 0; // Placeholder
  }, []);

  const value: NotificationContextType = {
    preferences,
    updatePreferences,
    showNotification,
    dismissNotification,
    dismissAll,
    markAsRead,
    markAllAsRead,
    getUnreadCount,
    isQuietHours,
  };

  return (
    <NotificationContext.Provider value={value}>
      {children}
    </NotificationContext.Provider>
  );
};

export const useNotification = () => {
  const context = useContext(NotificationContext);
  if (context === undefined) {
    throw new Error('useNotification must be used within a NotificationProvider');
  }
  return context;
};

// Enhanced notification hook with presets
export const useNotifications = () => {
  const { showNotification } = useNotification();

  const success = useCallback((title: string, message?: string, category?: string) => {
    showNotification({ type: 'success', title, message, category });
  }, [showNotification]);

  const error = useCallback((title: string, message?: string, category?: string) => {
    showNotification({ type: 'error', title, message, category });
  }, [showNotification]);

  const warning = useCallback((title: string, message?: string, category?: string) => {
    showNotification({ type: 'warning', title, message, category });
  }, [showNotification]);

  const info = useCallback((title: string, message?: string, category?: string) => {
    showNotification({ type: 'info', title, message, category });
  }, [showNotification]);

  return { success, error, warning, info };
};

// Notification center component
export const NotificationCenter: React.FC = () => {
  const { notifications, removeNotification, clearNotifications } = useAppStore();
  const { preferences, updatePreferences } = useNotification();
  const [isOpen, setIsOpen] = useState(false);

  const unreadCount = notifications.filter(n => !n.read).length;

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 transition-colors"
        aria-label={`Notifications ${unreadCount > 0 ? `(${unreadCount} unread)` : ''}`}
      >
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 17h5l-5 5v-5zM4.868 12.683A17.925 17.925 0 0112 21c7.962 0 12-1.21 12-2.683m-12 2.683a17.925 17.925 0 01-7.132-8.317M12 21V9m0 0a3 3 0 100-6 3 3 0 000 6z"
          />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full h-5 w-5 flex items-center justify-center">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {/* Notification dropdown/panel would go here */}
    </div>
  );
};
