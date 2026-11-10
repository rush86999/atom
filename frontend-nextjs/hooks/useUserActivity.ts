/**
 * useUserActivity Hook
 *
 * Custom hook for tracking user activity and sending heartbeats.
 * Automatically sends heartbeats every 30 seconds to track user availability.
 */

import { useEffect, useRef, useCallback, useState } from 'react';
import { extractApiErrorMessage } from '@/lib/api-error';

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
      // Don't send heartbeats while the tab is hidden — it wastes battery/
      // bandwidth and reports the user as active when they're not (BUG-048).
      if (typeof document !== 'undefined' && document.hidden) return;
      sendHeartbeat();
    }, interval);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [enabled, interval, sendHeartbeat]);

  const readPresenceResponse = useCallback(async (
    response: Response
  ): Promise<UserActivityState> => {
    let data: any = null;
    try {
      data = await response.json();
    } catch {
      data = null;
    }
    const verification = data?.verification;
    const ambiguous = (
      data?.success === false
      || verification?.effect === 'unknown'
      || verification?.status === 'unavailable'
      || verification?.status === 'refuted'
    );
    if (!response.ok || ambiguous) {
      const fallback = ambiguous
        ? 'Presence change could not be confirmed; refresh before retrying.'
        : `HTTP ${response.status}`;
      const hasMessage = data && typeof data === 'object' && (
        typeof data.detail === 'string'
        || typeof data.message === 'string'
        || typeof data.error === 'string'
        || (Array.isArray(data.detail) && data.detail.length > 0)
      );
      throw new Error(hasMessage
        ? extractApiErrorMessage(data, fallback)
        : fallback);
    }
    const validState = data && (
      data.state === 'online'
      || data.state === 'away'
      || data.state === 'offline'
    );
    if (!validState
        || typeof data.last_activity_at !== 'string'
        || typeof data.manual_override !== 'boolean') {
      throw new Error(
        'Presence response was missing its state; refresh before retrying.');
    }
    return data as UserActivityState;
  }, []);

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

      const data = await readPresenceResponse(response);
      setState(data);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    }
  }, [userId, readPresenceResponse]);

  const clearManualOverride = useCallback(async () => {
    if (!userId) return;

    try {
      const response = await fetch(`/api/users/${userId}/activity/override`, {
        method: 'DELETE',
      });

      const data = await readPresenceResponse(response);
      setState(data);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    }
  }, [userId, readPresenceResponse]);

  return {
    state,
    error,
    sendHeartbeat,
    setManualOverride,
    clearManualOverride,
  };
};
