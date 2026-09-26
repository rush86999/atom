import React, { useSyncExternalStore } from "react";
import { Badge } from "@/components/ui/badge";
import { Wifi, WifiOff } from "lucide-react";

const subscribeToOnlineStatus = (onChange: () => void) => {
  window.addEventListener("online", onChange);
  window.addEventListener("offline", onChange);
  return () => {
    window.removeEventListener("online", onChange);
    window.removeEventListener("offline", onChange);
  };
};

const getOnlineSnapshot = () => navigator.onLine;
const getOnlineServerSnapshot = () => true;

/**
 * Offline Indicator Component
 *
 * Displays connection status and warns when offline.
 */
export const OfflineIndicator: React.FC = () => {
  const isOnline = useSyncExternalStore(
    subscribeToOnlineStatus,
    getOnlineSnapshot,
    getOnlineServerSnapshot
  );

  if (isOnline) {
    return null; // Don't show anything when online
  }

  return (
    <div className="fixed bottom-4 right-4 z-50">
      <Badge variant="destructive" className="px-3 py-2 flex items-center gap-2">
        <WifiOff className="h-4 w-4" />
        <span>You&apos;re offline. Some features may not work.</span>
      </Badge>
    </div>
  );
};
