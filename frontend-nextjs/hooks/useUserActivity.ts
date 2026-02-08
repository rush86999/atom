/**
 * useUserActivity Hook
 *
 * Custom hook for tracking user activity and sending heartbeats.
 * Automatically sends heartbeats every 30 seconds to track user availability.
 */

import { useEffect, useRef, useCallback, useState } from 'react';

interface UserActivityState {
  state: 'online' | 'away' | 'offline';
  last_activity_at: string;
  manual_override: boolean;
}

interface UseUserActivityOptions {
  userId: string;
  enabled?: boolean;
  interval?: number; // milliseconds
  onStateChange?: (state: UserActivityState) => void;
}

export const useUserActivity = ({
  userId,
  enabled = true,
  interval = 30000, // 30 seconds default
  onStateChange
}: UseUserActivityOptions) => {
  const [state, setState] = useState<UserActivityState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const sessionTokenRef = useRef<string | null>(null);

  // Generate session token on mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      sessionTokenRef.current = `web_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
  }, []);

  // Track user activity (mouse, keyboard, scroll, touch)
  useEffect(() => {
    if (!enabled) return;

    let activityTimeout: NodeJS.Timeout;

    const recordActivity = () => {
      // Clear existing timeout
      if (activityTimeout) {
        clearTimeout(activityTimeout);
      }

      // Set new timeout
      activityTimeout = setTimeout(() => {
        // User has been inactive for a while
        // This is handled by the backend state transitions
      }, 60000); // 1 minute of inactivity
    };

    // Add event listeners
    const events = ['mousedown', 'keydown', 'scroll', 'touchstart'];
    events.forEach(event => {
      window.addEventListener(event, recordActivity, { passive: true });
    });

    return () => {
      if (activityTimeout) {
        clearTimeout(activityTimeout);
      }
      events.forEach(event => {
        window.removeEventListener(event, recordActivity);
      });
    };
  }, [enabled]);

  // Send heartbeat
  const sendHeartbeat = useCallback(async () => {
    if (!enabled || !userId || !sessionTokenRef.current) return;

    try {
      const response = await fetch(`/api/users/${userId}/activity/heartbeat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_token: sessionTokenRef.current,
          session_type: 'web',
          user_agent: navigator.userAgent,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data: UserActivityState = await response.json();
      setState(data);

      if (onStateChange) {
        onStateChange(data);
      }

      setError(null);
    } catch (err: any) {
      console.error('Failed to send heartbeat:', err);
      setError(err.message);
    }
  }, [enabled, userId, onStateChange]);

  // Start heartbeat interval
  useEffect(() => {
    if (!enabled) return;

    // Send first heartbeat immediately
    sendHeartbeat();

    // Set up interval
    intervalRef.current = setInterval(() => {
      sendHeartbeat();
    }, interval);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [enabled, interval, sendHeartbeat]);

  // Manual state override
  const setManualOverride = useCallback(async (
    overrideState: 'online' | 'away' | 'offline',
    expiresAt?: Date
  ) => {
    if (!userId) return;

    try {
      const response = await fetch(`/api/users/${userId}/activity/override`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          state: overrideState,
          expires_at: expiresAt?.toISOString(),
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data: UserActivityState = await response.json();
      setState(data);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    }
  }, [userId]);

  const clearManualOverride = useCallback(async () => {
    if (!userId) return;

    try {
      const response = await fetch(`/api/users/${userId}/activity/override`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data: UserActivityState = await response.json();
      setState(data);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    }
  }, [userId]);

  return {
    state,
    error,
    sendHeartbeat,
    setManualOverride,
    clearManualOverride,
  };
};
